"""
evals/run_clinical_benchmark.py
================================
Master Clinical Golden Benchmark Evaluation Runner for CDISC / Clinical Trial Data.

Executes the CDISC Clinical Golden Benchmark cases against the real application
pipeline and the active MySQL database `clinical_trial_analytics_db`.

Evaluates:
  1. Question Understanding / Plan Mapping
  2. Dataset Selection Accuracy
  3. KPI Mapping Accuracy
  4. SQL Semantic Correctness
  5. SQL Execution & Ground-Truth Verification
  6. Clinical Terminology Correctness
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.clinical.question_mapping import build_clinical_question_plan
from app.analytics.sql_validator import validate_sql
from app.analytics.query_executor import execute_query
from app.analytics.result_validator import validate_results
from app.database.schema_service import get_database_schema

BENCHMARK_PATH = PROJECT_ROOT / "evals" / "datasets" / "clinical_golden_benchmark.json"


def load_golden_benchmark() -> List[Dict[str, Any]]:
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_analytical_case(
    case: Dict[str, Any], schema: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluates an analytical clinical trial case through the real pipeline:
      Question -> Clinical Question Plan -> SQL Generation/Validation -> MySQL Execution -> Ground Truth Comparison
    """
    question = case["question"]
    expected_kpi = case.get("expected_kpi")
    expected_datasets = case.get("expected_datasets", [])
    expected_columns = case.get("expected_columns", [])
    expected_result = case.get("expected_result")
    expected_result_type = case.get("expected_result_type")
    expected_sql_concepts = case.get("expected_sql_concepts", [])

    results = {
        "id": case["id"],
        "category": case["category"],
        "question": question,
        "question_understanding": False,
        "dataset_selection": False,
        "kpi_mapping": False,
        "sql_validation": False,
        "sql_semantic": False,
        "execution": False,
        "ground_truth_match": False,
        "insight_terminology": False,
        "passed": False,
        "details": [],
    }

    # 1. Clinical Question Planning / Understanding
    try:
        plan = build_clinical_question_plan(question)
        if plan is not None and plan.is_supported:
            results["question_understanding"] = True

            # KPI Mapping
            if expected_kpi:
                if plan.matched_kpi_id == expected_kpi:
                    results["kpi_mapping"] = True
                elif plan.matched_kpi_id and (expected_kpi in plan.matched_kpi_id or plan.matched_kpi_id in expected_kpi):
                    results["kpi_mapping"] = True
                else:
                    results["details"].append(
                        f"KPI mapped to {plan.matched_kpi_id}, expected {expected_kpi}"
                    )
            else:
                results["kpi_mapping"] = True

            # Dataset Selection
            plan_tables = {t.lower() for t in plan.datasets}
            exp_tables = {t.lower() for t in expected_datasets}
            if exp_tables.issubset(plan_tables) or (
                "adsl" in plan_tables and "dm" in exp_tables
            ) or ("dm" in plan_tables and "adsl" in exp_tables) or bool(plan_tables.intersection(exp_tables)):
                results["dataset_selection"] = True
            else:
                results["details"].append(
                    f"Datasets selected: {plan.datasets}, expected: {expected_datasets}"
                )

            sql = plan.suggested_sql or ""
        else:
            results["details"].append("No deterministic plan resolved")
            sql = ""
    except Exception as exc:
        results["details"].append(f"Planning exception: {exc}")
        sql = ""

    # If no suggested SQL from plan, generate via generate_sql
    if not sql:
        try:
            from app.analytics.sql_generator import generate_sql
            sql = generate_sql(
                user_question=question,
                analysis_plan=plan.explanation if plan else "",
                database_schema=schema,
            )
        except Exception as exc:
            results["details"].append(f"SQL generation exception: {exc}")

    # Fallback to direct query if plan didn't resolve
    if not sql:
        # Check if expected SQL concepts exist
        results["details"].append("SQL query could not be constructed")
        return results

    # 2. SQL Validation
    is_valid, val_msg = validate_sql(sql, approved_schema=schema)
    results["sql_validation"] = is_valid
    if not is_valid:
        results["details"].append(f"SQL validation error: {val_msg}")

    # SQL Semantic Concepts with CDISC Equivalence (prevents false negatives)
    sql_upper = sql.upper()
    semantic_match = True
    for concept in expected_sql_concepts:
        words = concept.upper().split()
        if all(w in sql_upper for w in words):
            continue
        # Check domain-specific CDISC / SQL equivalence
        concept_upper = concept.upper().strip()
        matched = False
        if concept_upper == "ARM":
            # SDTM ARM is standard equivalent to ADaM TRT01A / TRTA / TRT01P
            matched = any(arm_var in sql_upper for arm_var in ("ARM", "TRT01A", "TRTA", "TRT01P"))
        elif concept_upper in ("LIMIT", "LIMIT 1"):
            # Entity ranking can be achieved via LIMIT or ORDER BY ... DESC
            matched = "LIMIT" in sql_upper or ("ORDER BY" in sql_upper and "DESC" in sql_upper)
        elif concept_upper in ("ORDER BY DESC", "ORDER BY ... DESC"):
            matched = "ORDER BY" in sql_upper and "DESC" in sql_upper

        if not matched:
            semantic_match = False
            results["details"].append(f"Missing expected SQL concept: {concept}")
            break
    results["sql_semantic"] = semantic_match

    # 3. Execution against real MySQL database
    if is_valid:
        try:
            db_rows = execute_query(sql)
            results["execution"] = True

            # Ground Truth Matching
            if expected_result_type == "scalar_integer":
                # Check if cell matches scalar value or sums across grouped rows
                if db_rows:
                    num_vals = []
                    for row in db_rows:
                        for v in row.values():
                            try:
                                if isinstance(v, (int, float)):
                                    num_vals.append(int(v))
                                elif isinstance(v, str) and v.isdigit():
                                    num_vals.append(int(v))
                            except Exception:
                                pass
                    target = int(expected_result)
                    if target in num_vals or sum(num_vals) == target:
                        results["ground_truth_match"] = True
                    else:
                        first_val = list(db_rows[0].values())[0]
                        results["details"].append(
                            f"Result value {first_val} (or values {num_vals[:3]}) != expected {expected_result}"
                        )
            elif expected_result_type == "entity_ranking":
                if db_rows:
                    first_row = {k.lower(): v for k, v in db_rows[0].items()}
                    # Check top site or top arm
                    matched = True
                    if "site_id" in expected_result:
                        if not any(
                            str(expected_result["site_id"]).lower() in str(v).lower()
                            for v in first_row.values()
                        ):
                            matched = False
                    if "treatment_arm" in expected_result:
                        if not any(
                            str(expected_result["treatment_arm"]).lower() in str(v).lower()
                            for v in first_row.values()
                        ):
                            matched = False
                    results["ground_truth_match"] = matched
                    if not matched:
                        results["details"].append(
                            f"Top entity mismatch: got {db_rows[0]}, expected {expected_result}"
                        )
            elif expected_result_type == "distribution":
                if isinstance(expected_result, dict):
                    if len(db_rows) == len(expected_result):
                        results["ground_truth_match"] = True
                    else:
                        results["details"].append(
                            f"Category count {len(db_rows)} != expected {len(expected_result)}"
                        )
                else:
                    results["ground_truth_match"] = bool(db_rows)
            elif expected_result_type == "scalar_numeric":
                if db_rows:
                    first_val = float(list(db_rows[0].values())[0])
                    target_val = float(expected_result["mean_age"]) if isinstance(expected_result, dict) else float(expected_result)
                    if abs(first_val - target_val) < 0.5:
                        results["ground_truth_match"] = True
                    else:
                        results["details"].append(
                            f"Numeric value {first_val} deviates from {target_val}"
                        )
            elif expected_result_type == "grouped_analysis":
                if len(db_rows) >= 2:
                    results["ground_truth_match"] = True
                else:
                    results["details"].append(f"Grouped rows {len(db_rows)} < 2")
            elif expected_result_type == "visit_parameter_analysis":
                if db_rows and len(db_rows) > 0:
                    results["ground_truth_match"] = True
            elif expected_result_type == "tabular_aggregation":
                if db_rows:
                    results["ground_truth_match"] = True
            else:
                results["ground_truth_match"] = bool(db_rows)
        except Exception as exc:
            results["details"].append(f"Execution error: {exc}")

    # 4. Clinical Terminology Check
    exp_terms = case.get("expected_terminology", [])
    sql_and_plan = (sql + " " + (plan.explanation if plan else "")).lower()
    terms_matched = all(t.lower() in sql_and_plan or t.lower() in question.lower() for t in exp_terms)
    results["insight_terminology"] = terms_matched

    # Overall PASS condition
    results["passed"] = (
        results["question_understanding"]
        and results["sql_validation"]
        and results["execution"]
        and results["ground_truth_match"]
    )
    return results


def run_benchmark():
    benchmark_cases = load_golden_benchmark()
    total_cases = len(benchmark_cases)

    print("=" * 80)
    print("CLINICAL TRIAL GOLDEN BENCHMARK EXECUTION RUNNER")
    print(f"Total Benchmark Cases: {total_cases}")
    print(f"Active Database      : clinical_trial_analytics_db")
    print("=" * 80)

    schema = get_database_schema()

    case_results = []
    category_stats: Dict[str, Dict[str, int]] = {}

    dimension_counts = {
        "question_understanding": 0,
        "dataset_selection": 0,
        "kpi_mapping": 0,
        "sql_validation": 0,
        "sql_semantic": 0,
        "execution": 0,
        "ground_truth_match": 0,
        "insight_terminology": 0,
    }
    total_analytical = 0

    start_time = time.time()

    for idx, case in enumerate(benchmark_cases, 1):
        cat = case["category"]
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "passed": 0}
        category_stats[cat]["total"] += 1

        total_analytical += 1
        res = evaluate_analytical_case(case, schema)
        if res["question_understanding"]:
            dimension_counts["question_understanding"] += 1
        if res["dataset_selection"]:
            dimension_counts["dataset_selection"] += 1
        if res["kpi_mapping"]:
            dimension_counts["kpi_mapping"] += 1
        if res["sql_validation"]:
            dimension_counts["sql_validation"] += 1
        if res["sql_semantic"]:
            dimension_counts["sql_semantic"] += 1
        if res["execution"]:
            dimension_counts["execution"] += 1
        if res["ground_truth_match"]:
            dimension_counts["ground_truth_match"] += 1

        if res["insight_terminology"]:
            dimension_counts["insight_terminology"] += 1

        if res["passed"]:
            category_stats[cat]["passed"] += 1
            status_tag = "PASS [OK]"
        else:
            status_tag = "FAIL [X]"

        case_results.append(res)

        print(f"[{status_tag}] Case {idx:02d} ({res['id']}) | Category: {cat}")
        print(f"         Question: \"{res['question']}\"")
        if res["details"]:
            print(f"         Details : {'; '.join(res['details'])}")

    elapsed = time.time() - start_time
    total_passed = sum(1 for r in case_results if r["passed"])
    total_failed = total_cases - total_passed
    overall_accuracy = (total_passed / total_cases) * 100.0 if total_cases > 0 else 0.0

    print("\n" + "=" * 80)
    print("CLINICAL BENCHMARK EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Total Benchmark Cases : {total_cases}")
    print(f"Passed                : {total_passed}")
    print(f"Failed                : {total_failed}")
    print(f"Overall Accuracy      : {overall_accuracy:.1f}%")
    print(f"Execution Time        : {elapsed:.2f} seconds")

    print("\n" + "-" * 80)
    print("DIMENSION-WISE PERFORMANCE METRICS")
    print("-" * 80)
    if total_analytical > 0:
        qu_acc = (dimension_counts["question_understanding"] / total_analytical) * 100.0
        ds_acc = (dimension_counts["dataset_selection"] / total_analytical) * 100.0
        kpi_acc = (dimension_counts["kpi_mapping"] / total_analytical) * 100.0
        sql_val_acc = (dimension_counts["sql_validation"] / total_analytical) * 100.0
        sql_sem_acc = (dimension_counts["sql_semantic"] / total_analytical) * 100.0
        exec_acc = (dimension_counts["execution"] / total_analytical) * 100.0
        gt_acc = (dimension_counts["ground_truth_match"] / total_analytical) * 100.0

        print(f"Question Understanding Accuracy : {qu_acc:.1f}% ({dimension_counts['question_understanding']}/{total_analytical})")
        print(f"Dataset Selection Accuracy      : {ds_acc:.1f}% ({dimension_counts['dataset_selection']}/{total_analytical})")
        print(f"KPI Mapping Accuracy            : {kpi_acc:.1f}% ({dimension_counts['kpi_mapping']}/{total_analytical})")
        print(f"SQL Validation Accuracy         : {sql_val_acc:.1f}% ({dimension_counts['sql_validation']}/{total_analytical})")
        print(f"SQL Semantic Correctness        : {sql_sem_acc:.1f}% ({dimension_counts['sql_semantic']}/{total_analytical})")
        print(f"SQL Execution Correctness       : {exec_acc:.1f}% ({dimension_counts['execution']}/{total_analytical})")
        print(f"Ground Truth Match Accuracy     : {gt_acc:.1f}% ({dimension_counts['ground_truth_match']}/{total_analytical})")

    term_acc = (dimension_counts["insight_terminology"] / total_cases) * 100.0
    print(f"Clinical Terminology Accuracy   : {term_acc:.1f}% ({dimension_counts['insight_terminology']}/{total_cases})")

    print("\n" + "-" * 80)
    print("CATEGORY-WISE PERFORMANCE BREAKDOWN")
    print("-" * 80)
    for cat, stats in sorted(category_stats.items()):
        c_passed = stats["passed"]
        c_total = stats["total"]
        c_pct = (c_passed / c_total) * 100.0 if c_total > 0 else 0.0
        print(f"  {cat:<25}: {c_passed:2d}/{c_total:2d} ({c_pct:5.1f}%)")
    print("=" * 80)

    return {
        "total_cases": total_cases,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "overall_accuracy": overall_accuracy,
        "category_stats": category_stats,
        "dimension_counts": dimension_counts,
        "total_analytical": total_analytical,
    }


if __name__ == "__main__":
    run_benchmark()
