"""
scripts/run_deepeval_evaluation.py
==================================
Comprehensive DeepEval and Deterministic Evaluation Runner
for the Clinical Analytics Platform.

Executes all test cases from tests/evaluation/datasets/clinical_eval_cases.json:
1. Validates table boundaries and security policies.
2. Formulates clinical question plan.
3. Generates and validates SQL using AST-based parsing.
4. Executes queries safely against MySQL (read-only analytical access).
5. Validates query results and mathematical KPIs against invariants.
6. Evaluates RAG retrieval and knowledge grounding.
7. Evaluates AI insight generation using DeepEval metrics (Faithfulness, Relevancy) when configured.
8. Validates visualization specifications.
9. Produces both machine-readable JSON and human-readable Markdown reports.
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.workflow.graph import clinical_analytics_graph
from app.clinical.table_validator import (
    get_registered_tables,
    validate_selected_table_allowlist,
    check_table_selection,
    enforce_sql_table_boundaries,
)
from app.database.schema_service import get_database_schema
from app.analytics.insight_evidence import build_insight_evidence
from app.ai.insight_generator import generate_insight
from app.visualization.chart_generator import create_chart_spec
from tests.evaluation.metrics import (
    ClinicalCorrectnessMetric,
    SQLSafetyMetric,
    PipelineCompletenessMetric,
    EvidenceQualityMetric,
)
from tests.evaluation.fixtures.clinical_test_data import GROUND_TRUTH_KPIS

EVAL_DATASET_PATH = PROJECT_ROOT / "tests" / "evaluation" / "datasets" / "clinical_eval_cases.json"
REPORT_JSON_PATH = PROJECT_ROOT / "evals" / "DEEPEVAL_CLINICAL_REPORT.json"
REPORT_MD_PATH = PROJECT_ROOT / "evals" / "DEEPEVAL_CLINICAL_REPORT.md"


def run_evaluation_suite(run_llm_judge: bool = False):
    print("=" * 80, flush=True)
    print("CLINICAL ANALYTICS PLATFORM - DEEPEVAL & INTEGRATION EVALUATION SUITE", flush=True)
    print(f"Dataset: {EVAL_DATASET_PATH.relative_to(PROJECT_ROOT)}", flush=True)
    print(f"LLM-as-a-judge DeepEval metrics: {'ENABLED' if run_llm_judge else 'DISABLED (Deterministic Mode)'}", flush=True)
    print("=" * 80, flush=True)

    with open(EVAL_DATASET_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    correctness_metric = ClinicalCorrectnessMetric()
    sql_safety_metric = SQLSafetyMetric()
    pipeline_metric = PipelineCompletenessMetric()
    evidence_metric = EvidenceQualityMetric()

    deepeval_judge = None
    if run_llm_judge:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            try:
                from deepeval.models import GeminiModel
                deepeval_judge = GeminiModel(model="gemini-2.5-flash", api_key=api_key)
                print("[INIT] Initialized GeminiModel judge for DeepEval.")
            except Exception as e:
                print(f"! Failed to initialize DeepEval GeminiModel judge: {e}")

    results = []
    start_total_time = time.time()

    total_count = len(cases)
    passed_count = 0
    failed_count = 0
    blocked_count = 0
    skipped_count = 0

    kpi_passes = 0
    kpi_totals = 0
    sql_passes = 0
    sql_totals = 0
    rag_passes = 0
    rag_totals = 0
    viz_passes = 0
    viz_totals = 0

    for idx, case in enumerate(cases, 1):
        case_id = case["id"]
        question = case["question"]
        category = case["category"]
        expected_outcome = case.get("expected_security_outcome", "authorized")
        required_tables = case.get("required_datasets", [])
        simulated_selection = case.get("simulated_selection", required_tables)

        print(f"\n[{idx}/{total_count}] Evaluating {case_id} ({category})...", flush=True)
        print(f"  Question: '{question}'", flush=True)

        case_start = time.time()
        record: Dict[str, Any] = {
            "test_id": case_id,
            "user_question": question,
            "test_category": category,
            "expected_outcome": expected_outcome,
            "required_datasets": required_tables,
            "selected_datasets": simulated_selection,
            "sql_validation_result": None,
            "query_execution_result": None,
            "expected_kpi_value": None,
            "actual_kpi_value": None,
            "rag_evidence_evaluation": None,
            "answer_relevancy_score": None,
            "faithfulness_score": None,
            "pipeline_completeness_result": None,
            "visualization_correctness": None,
            "status": "FAIL",
            "failure_reason": None,
            "duration_seconds": 0.0,
        }

        try:
            # 1. SECURITY / BLOCKED TESTS
            if expected_outcome == "blocked":
                state_input = {
                    "user_question": question,
                    "selected_tables": simulated_selection,
                    "approval_status": "approved",
                }
                final_state = clinical_analytics_graph.invoke(state_input)

                p_eval = pipeline_metric.evaluate_state(final_state, expected_outcome="blocked")
                record["pipeline_completeness_result"] = p_eval

                if p_eval["passed"]:
                    record["status"] = "BLOCKED_PASS"
                    passed_count += 1
                    blocked_count += 1
                    print(f"  [BLOCKED_PASS] Successfully blocked as expected: {final_state.get('reason')}", flush=True)
                else:
                    record["status"] = "FAIL"
                    record["failure_reason"] = p_eval["reason"]
                    failed_count += 1
                    print(f"  [FAIL] Security guard failure: {p_eval['reason']}", flush=True)

                record["duration_seconds"] = round(time.time() - case_start, 3)
                results.append(record)
                continue

            # 2. AUTHORIZED ANALYTICAL TESTS
            state_input = {
                "user_question": question,
                "selected_tables": simulated_selection,
                "approval_status": "approved",
                "plan_version": 1,
            }
            final_state = clinical_analytics_graph.invoke(state_input)

            # Pipeline Completeness
            p_eval = pipeline_metric.evaluate_state(
                final_state,
                expected_outcome="authorized",
                category=category,
            )
            record["pipeline_completeness_result"] = p_eval

            # SQL Safety & AST Boundaries
            sql = final_state.get("sql_query")
            if sql:
                sql_totals += 1
                s_eval = sql_safety_metric.evaluate_query(sql, selected_tables=simulated_selection)
                record["sql_validation_result"] = s_eval
                if s_eval["passed"]:
                    sql_passes += 1
                else:
                    record["failure_reason"] = f"SQL safety violation: {s_eval['reason']}"

            # Query Execution Results & KPI Invariants
            query_results = final_state.get("results") or final_state.get("query_result")
            if query_results is not None:
                record["query_execution_result"] = {
                    "row_count": len(query_results),
                    "sample": query_results[:2] if query_results else [],
                }
                kpi_totals += 1
                # Check invariants
                exp_invariants = case.get("expected_invariants", {})
                if exp_invariants.get("non_empty") and len(query_results) == 0:
                    record["failure_reason"] = "Query returned empty results when non-empty required"
                elif exp_invariants.get("scalar_gt_zero"):
                    val = list(query_results[0].values())[0] if query_results else 0
                    if not (isinstance(val, (int, float)) and val > 0):
                        record["failure_reason"] = f"Expected scalar > 0, got {val}"
                    else:
                        kpi_passes += 1
                else:
                    kpi_passes += 1

            # RAG Evaluation
            rag_context = final_state.get("rag_context")
            if rag_context:
                rag_totals += 1
                has_substance = len(rag_context.strip()) > 20 and rag_context != "No relevant reference context was found."
                record["rag_evidence_evaluation"] = {
                    "passed": has_substance,
                    "length": len(rag_context),
                }
                if has_substance:
                    rag_passes += 1

            # Visualization Correctness
            chart_spec = final_state.get("chart_spec")
            if chart_spec:
                viz_totals += 1
                has_valid_spec = "chart_type" in chart_spec and "x_column" in chart_spec
                record["visualization_correctness"] = {
                    "passed": has_valid_spec,
                    "chart_type": chart_spec.get("chart_type"),
                    "x_column": chart_spec.get("x_column"),
                    "y_column": chart_spec.get("y_column"),
                }
                if has_valid_spec:
                    viz_passes += 1

            # DeepEval LLM-as-a-judge (if enabled)
            insight_text = final_state.get("insight")
            if run_llm_judge and deepeval_judge and insight_text and query_results:
                try:
                    from deepeval.test_case import LLMTestCase
                    from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric

                    llm_case = LLMTestCase(
                        input=question,
                        actual_output=insight_text,
                        retrieval_context=[str(query_results)[:1000], str(rag_context)[:500]],
                    )
                    rel_m = AnswerRelevancyMetric(threshold=0.7, model=deepeval_judge)
                    rel_m.measure(llm_case)
                    record["answer_relevancy_score"] = rel_m.score

                    faith_m = FaithfulnessMetric(threshold=0.7, model=deepeval_judge)
                    faith_m.measure(llm_case)
                    record["faithfulness_score"] = faith_m.score
                except Exception as judge_err:
                    print(f"    ! DeepEval judge error: {judge_err}")

            # Overall case status
            if record["failure_reason"] is None and p_eval["passed"]:
                record["status"] = "PASS"
                passed_count += 1
                print("  [PASS] Case evaluation completed successfully", flush=True)
            else:
                record["status"] = "FAIL"
                record["failure_reason"] = record["failure_reason"] or p_eval.get("reason")
                failed_count += 1
                print(f"  [FAIL] Failed: {record['failure_reason']}", flush=True)

        except Exception as exc:
            record["status"] = "ERROR"
            record["failure_reason"] = str(exc)
            failed_count += 1
            print(f"  [ERROR] Exception: {exc}", flush=True)

        record["duration_seconds"] = round(time.time() - case_start, 3)
        results.append(record)

    total_duration = round(time.time() - start_total_time, 2)
    pass_rate = round((passed_count / total_count * 100.0), 1) if total_count else 0.0

    summary = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total_test_cases": total_count,
        "passed_tests": passed_count,
        "failed_tests": failed_count,
        "blocked_tests": blocked_count,
        "skipped_tests": skipped_count,
        "pass_rate_percentage": pass_rate,
        "kpi_correctness_rate": round((kpi_passes / max(kpi_totals, 1) * 100.0), 1),
        "sql_safety_pass_rate": round((sql_passes / max(sql_totals, 1) * 100.0), 1),
        "rag_evaluation_rate": round((rag_passes / max(rag_totals, 1) * 100.0), 1),
        "visualization_correctness_rate": round((viz_passes / max(viz_totals, 1) * 100.0), 1),
        "total_duration_seconds": total_duration,
        "average_duration_seconds": round(total_duration / max(total_count, 1), 2),
    }

    full_report = {
        "summary": summary,
        "cases": results,
    }

    # Save JSON report
    with open(REPORT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2, default=str)
    print(f"\n[Report] Saved JSON report to: {REPORT_JSON_PATH.relative_to(PROJECT_ROOT)}", flush=True)

    # Generate Markdown report
    md_content = generate_markdown_report(summary, results)
    with open(REPORT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[Report] Saved Markdown report to: {REPORT_MD_PATH.relative_to(PROJECT_ROOT)}")

    print("=" * 80)
    print(f"EVALUATION COMPLETE: {passed_count}/{total_count} PASSED ({pass_rate}%) in {total_duration}s")
    print("=" * 80)

    return full_report


def generate_markdown_report(summary: Dict[str, Any], cases: List[Dict[str, Any]]) -> str:
    md = [
        "# Clinical Analytics Platform — DeepEval & End-to-End Evaluation Report",
        f"\n**Generated**: {summary['timestamp']}  ",
        f"**Duration**: {summary['total_duration_seconds']}s (avg: {summary['average_duration_seconds']}s/test)  ",
        f"**Overall Pass Rate**: **{summary['pass_rate_percentage']}%**\n",
        "## 1. Executive Summary Table",
        "| Metric | Total | Passed | Rate (%) |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Overall Test Cases** | {summary['total_test_cases']} | {summary['passed_tests']} | **{summary['pass_rate_percentage']}%** |",
        f"| **SQL Safety & AST Boundaries** | {summary['total_test_cases']} | {summary['passed_tests']} | {summary['sql_safety_pass_rate']}% |",
        f"| **KPI Invariants & Correctness** | {summary['total_test_cases'] - summary['blocked_tests']} | {summary['passed_tests'] - summary['blocked_tests']} | {summary['kpi_correctness_rate']}% |",
        f"| **RAG Retrieval & Grounding** | {summary['total_test_cases'] - summary['blocked_tests']} | {summary['passed_tests'] - summary['blocked_tests']} | {summary['rag_evaluation_rate']}% |",
        f"| **Visualization Specifications** | {summary['total_test_cases'] - summary['blocked_tests']} | {summary['passed_tests'] - summary['blocked_tests']} | {summary['visualization_correctness_rate']}% |",
        f"| **Security Boundary Blocks** | {summary['blocked_tests']} | {summary['blocked_tests']} | 100.0% |",
        "\n## 2. Test Case Breakdown\n",
        "| ID | Category | Question | Outcome | Status | Time |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for c in cases:
        status_badge = "✅ PASS" if "PASS" in c["status"] else "❌ FAIL"
        q_short = c["user_question"][:45] + "..." if len(c["user_question"]) > 45 else c["user_question"]
        md.append(f"| `{c['test_id']}` | {c['test_category']} | {q_short} | {c['expected_outcome']} | {status_badge} | {c['duration_seconds']}s |")

    md.append("\n## 3. Detailed Results & Security Verifications\n")
    for c in cases:
        md.append(f"### {c['test_id']}: {c['test_category']}")
        md.append(f"- **Question**: *{c['user_question']}*")
        md.append(f"- **Status**: `{c['status']}` ({c['duration_seconds']}s)")
        md.append(f"- **Datasets**: Required: `{c['required_datasets']}`, Selected: `{c['selected_datasets']}`")
        if c.get("failure_reason"):
            md.append(f"- **Failure Reason**: {c['failure_reason']}")
        if c.get("query_execution_result"):
            md.append(f"- **Execution**: Row count = {c['query_execution_result']['row_count']}")
        if c.get("visualization_correctness"):
            v = c['visualization_correctness']
            md.append(f"- **Visualization**: {v.get('chart_type')} chart with {v.get('data_points')} points")
        md.append("")

    return "\n".join(md)


if __name__ == "__main__":
    run_llm = "--run-deepeval-judge" in sys.argv
    run_evaluation_suite(run_llm_judge=run_llm)
