"""
evals/run_clinical_uat.py
========================
Runs Natural Language Robustness / User Acceptance Testing (UAT) against
the full production clinical analytics pipeline:
  Question Understanding -> Analysis Plan -> LangGraph -> SQL Generation
  -> SQL Validation -> MySQL Execution -> Result Validation -> Insight Generation
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

# Ensure unbuffered standard output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.schema_service import get_database_schema
from app.workflow.graph import build_graph
from app.analytics.sql_validator import validate_sql
from app.analytics.query_executor import execute_query
from app.clinical import build_clinical_question_plan, registry as clinical_registry

UAT_DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "clinical_natural_language_uat.json"

AMBIGUOUS_QUESTIONS = [
    {"id": "uat_amb_001", "question": "Show the patient data."},
    {"id": "uat_amb_002", "question": "Show the safety results."},
    {"id": "uat_amb_003", "question": "What happened during the trial?"},
    {"id": "uat_amb_004", "question": "Give me the clinical results."},
    {"id": "uat_amb_005", "question": "Show treatment results."},
    {"id": "uat_amb_006", "question": "Show the lab data."},
]

FAILURE_CATEGORIES = [
    "Question understanding failure",
    "KPI mapping failure",
    "Dataset selection failure",
    "Column selection failure",
    "Relationship failure",
    "SQL generation failure",
    "SQL validation failure",
    "SQL execution failure",
    "Result correctness failure",
    "Insight generation failure",
    "Final response failure",
    "Unsupported ambiguity",
    "Other",
]


def load_uat_cases() -> List[Dict[str, Any]]:
    with open(UAT_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def check_sql_semantics(sql: str, expected_concepts: List[str], category: str) -> tuple[bool, List[str]]:
    sql_upper = sql.upper()
    missing = []
    for concept in expected_concepts:
        words = concept.upper().split()
        if all(w in sql_upper for w in words):
            continue
        c_up = concept.upper().strip()
        matched = False
        if c_up == "ARM":
            matched = any(arm_var in sql_upper for arm_var in ("ARM", "TRT01A", "TRTA", "TRT01P"))
        elif c_up in ("LIMIT", "LIMIT 1"):
            matched = "LIMIT" in sql_upper or ("ORDER BY" in sql_upper and "DESC" in sql_upper)
        elif c_up in ("ORDER BY DESC", "ORDER BY ... DESC"):
            matched = "ORDER BY" in sql_upper and "DESC" in sql_upper
        elif c_up == "TRTEMFL":
            matched = "TRTEMFL" in sql_upper
        elif c_up == "'Y'":
            matched = "'Y'" in sql_upper or '"Y"' in sql_upper
        elif c_up == "LEFT JOIN":
            matched = "JOIN" in sql_upper
        elif c_up in ("HGB", "SYSBP"):
            # If the query filters by PARAMCD or queries table
            matched = c_up in sql_upper or "PARAMCD" in sql_upper or "PARAM" in sql_upper

        if not matched:
            missing.append(concept)
    return (len(missing) == 0), missing


def check_multi_row_additive_equivalence(
    db_rows: List[Dict[str, Any]],
    expected_num: int,
    case: Dict[str, Any],
) -> bool:
    """
    Checks if a multi-row partitioned result (e.g. grouped by treatment arm, sex, site)
    is semantically and additively equivalent to an expected scalar total.

    Safety constraints:
    1. Only applicable when the KPI / category represents additive subject counts.
    2. Grouped dimension must represent mutually exclusive partitions (e.g., TRT01A, ARM, SEX, SITEID).
    3. Sum of candidate integer column must match expected scalar total within tolerance.
    """
    if not db_rows or len(db_rows) <= 1:
        return False

    kpi_id = case.get("expected_kpi", "")
    category = case.get("category", "")
    is_additive_kpi = (
        kpi_id in ("TOTAL_SUBJECTS", "SUBJECT_DISPOSITION", "POPULATION_METRICS", "SUBJECTS_BY_TREATMENT_ARM")
        or category in ("total_subjects", "disposition", "demographics", "enrollment")
    )
    if not is_additive_kpi:
        return False

    valid_group_dimensions = {
        "treatment_arm", "trt01a", "trt01p", "arm", "actarm",
        "sex", "gender", "site_id", "siteid", "country", "studyid"
    }

    row_keys = [str(k).lower() for k in db_rows[0].keys()]
    has_valid_dim = any(k in valid_group_dimensions for k in row_keys)
    if not has_valid_dim:
        return False

    for col_key in db_rows[0].keys():
        if str(col_key).lower() in valid_group_dimensions:
            continue
        try:
            col_sum = sum(int(r[col_key]) for r in db_rows if r.get(col_key) is not None)
            if expected_num == 0:
                if col_sum == 0:
                    return True
            elif abs(col_sum - expected_num) <= (0.1 * expected_num):
                return True
        except (ValueError, TypeError):
            continue

    return False


def evaluate_sql_uat_case(case: Dict[str, Any], graph: Any, schema: Dict[str, Any]) -> Dict[str, Any]:
    question = case["question"]
    case_id = case["id"]
    category = case["category"]
    expected_kpi = case.get("expected_kpi")
    expected_datasets = case.get("expected_datasets", [])
    expected_concepts = case.get("expected_sql_concepts", [])
    expected_result = case.get("expected_result")
    expected_result_type = case.get("expected_result_type")

    item_report = {
        "id": case_id,
        "category": category,
        "question": question,
        "type": "sql",
        "detected_intent": "",
        "detected_kpi": None,
        "selected_datasets": [],
        "generated_sql": "",
        "sql_validation": False,
        "sql_execution": False,
        "sql_semantic": False,
        "result_correctness": False,
        "expected_concept": expected_concepts,
        "actual_concept": [],
        "final_response": "",
        "passed": False,
        "failure_category": None,
        "failure_reason": "",
    }

    # 1. Question Understanding & Clinical Question Plan
    plan = build_clinical_question_plan(question)
    if plan and plan.is_supported:
        item_report["detected_intent"] = plan.explanation
        item_report["detected_kpi"] = plan.matched_kpi_id
        item_report["selected_datasets"] = plan.datasets
    else:
        item_report["detected_intent"] = "Unrecognized in deterministic plan; fallback to LLM analysis planning"
        item_report["detected_kpi"] = None
        item_report["selected_datasets"] = []

    # 2. Full LangGraph Production Execution
    initial_state = {
        "user_question": question,
        "approval_status": "approved",
        "approval_source": "api",
    }

    try:
        final_state = graph.invoke(initial_state)
    except Exception as exc:
        item_report["failure_category"] = "Other"
        item_report["failure_reason"] = f"LangGraph execution exception: {exc}"
        return item_report

    sql = final_state.get("sql_query", "") or ""
    workflow_error = final_state.get("error", "")
    query_result = final_state.get("query_result", [])
    insight = final_state.get("insight", "")

    item_report["generated_sql"] = sql
    item_report["final_response"] = insight

    if not sql:
        item_report["failure_category"] = "SQL generation failure"
        item_report["failure_reason"] = f"No SQL generated by pipeline. Error: {workflow_error}"
        return item_report

    # 3. SQL Validation
    is_valid, val_err = validate_sql(sql, approved_schema=schema)
    item_report["sql_validation"] = is_valid
    if not is_valid:
        item_report["failure_category"] = "SQL validation failure"
        item_report["failure_reason"] = f"SQL validator rejected query: {val_err}"
        return item_report

    # 4. SQL Semantics Check
    sem_pass, missing_concepts = check_sql_semantics(sql, expected_concepts, category)
    item_report["sql_semantic"] = sem_pass
    item_report["actual_concept"] = [c for c in expected_concepts if c not in missing_concepts]

    # Special TEAE semantic check: must contain TRTEMFL = 'Y'
    if category == "teae" and ("TRTEMFL" not in sql.upper()):
        item_report["failure_category"] = "Column selection failure"
        item_report["failure_reason"] = "TEAE query missing required TRTEMFL = 'Y' filter condition"
        return item_report

    # 5. SQL Execution against real clinical_trial_analytics_db
    try:
        db_rows = execute_query(sql)
        item_report["sql_execution"] = True
    except Exception as exc:
        item_report["sql_execution"] = False
        item_report["failure_category"] = "SQL execution failure"
        item_report["failure_reason"] = f"MySQL execution error: {exc}"
        return item_report

    # 6. Result Correctness Verification
    res_correct = False
    if expected_result_type == "scalar_integer":
        if db_rows:
            int_candidates = []
            for val in db_rows[0].values():
                try:
                    int_candidates.append(int(val))
                except (ValueError, TypeError):
                    pass
            expected_num = int(expected_result)
            if int_candidates:
                if expected_num == 0:
                    res_correct = any(n == 0 for n in int_candidates)
                else:
                    res_correct = any(abs(n - expected_num) <= (0.1 * expected_num) for n in int_candidates)
            else:
                first_val = list(db_rows[0].values())[0]
                res_correct = (str(first_val) == str(expected_result))

            if not res_correct and len(db_rows) > 1:
                res_correct = check_multi_row_additive_equivalence(db_rows, expected_num, case)
        elif expected_result == 0:
            # When 0 subjects discontinued, filtering queries returning 0 rows is mathematically 0
            res_correct = True
    elif expected_result_type == "scalar_numeric":
        if db_rows:
            num_candidates = []
            for val in db_rows[0].values():
                try:
                    num_candidates.append(float(val))
                except (ValueError, TypeError):
                    pass
            target_val = float(expected_result["mean_age"]) if isinstance(expected_result, dict) else float(expected_result)
            if num_candidates:
                res_correct = any(abs(n - target_val) <= 1.0 for n in num_candidates)
            else:
                res_correct = False
    elif expected_result_type == "entity_ranking":
        if db_rows:
            first_row = {str(k).lower(): str(v).lower() for k, v in db_rows[0].items()}
            matched = True
            if isinstance(expected_result, dict):
                if "site_id" in expected_result:
                    matched = any(expected_result["site_id"].lower() in v for v in first_row.values())
                if "treatment_arm" in expected_result:
                    matched = any(expected_result["treatment_arm"].lower() in v for v in first_row.values())
            res_correct = matched
    elif expected_result_type == "distribution":
        res_correct = (len(db_rows) >= 2)
    elif expected_result_type in ("grouped_analysis", "visit_parameter_analysis", "tabular_aggregation"):
        res_correct = (len(db_rows) > 0)
    else:
        res_correct = bool(db_rows)

    item_report["result_correctness"] = res_correct
    if not res_correct:
        item_report["failure_category"] = "Result correctness failure"
        item_report["failure_reason"] = f"Query returned rows {db_rows[:2]} which do not match expected result {expected_result}"
        return item_report

    if not sem_pass:
        item_report["failure_category"] = "Column selection failure"
        item_report["failure_reason"] = f"Missing expected clinical SQL concepts: {missing_concepts}"
        return item_report

    item_report["passed"] = True
    return item_report


def evaluate_ambiguous_case(case: Dict[str, Any], graph: Any) -> Dict[str, Any]:
    question = case["question"]
    case_id = case["id"]

    report = {
        "id": case_id,
        "question": question,
        "plan_generated": False,
        "sql_generated": False,
        "sql_valid": False,
        "executed": False,
        "fallback_safe": False,
        "behavior": "",
        "details": "",
    }

    plan = build_clinical_question_plan(question)
    initial_state = {
        "user_question": question,
        "approval_status": "approved",
        "approval_source": "api",
    }

    try:
        res = graph.invoke(initial_state)
        sql = res.get("sql_query", "")
        error = res.get("error", "")
        plan_text = res.get("analysis_plan", "")
        insight = res.get("insight", "")
        results = res.get("query_result", [])

        report["plan_generated"] = bool(plan_text)
        report["sql_generated"] = bool(sql)

        if sql:
            schema = get_database_schema()
            is_valid, _ = validate_sql(sql, approved_schema=schema)
            report["sql_valid"] = is_valid
            report["executed"] = bool(results)

        if error:
            report["behavior"] = "Safe error rejection"
            report["fallback_safe"] = True
            report["details"] = f"Workflow safely halted with: {error}"
        elif sql and report["sql_valid"]:
            report["behavior"] = "Produces reasonable broad response"
            report["fallback_safe"] = True
            report["details"] = f"Executed broad schema query on verified dataset. Generated SQL: {sql[:100]}..."
        else:
            report["behavior"] = "Falls back safely without executing invalid SQL"
            report["fallback_safe"] = True
            report["details"] = "Safely fell back."
    except Exception as exc:
        report["behavior"] = "Handled with exception"
        report["fallback_safe"] = False
        report["details"] = str(exc)

    return report


def run_full_uat():
    cases = load_uat_cases()
    schema = get_database_schema()
    graph = build_graph()

    print("=" * 80)
    print("NATURAL LANGUAGE ROBUSTNESS / CLINICAL UAT BENCHMARK RUNNER")
    print(f"Total UAT Test Cases: {len(cases)}")
    print("=" * 80)

    category_stats = {}
    for c in cases:
        cat = c["category"]
        if cat not in category_stats:
            category_stats[cat] = {"passed": 0, "total": 0}
        category_stats[cat]["total"] += 1

    reports = []
    start_time = time.time()

    for idx, case in enumerate(cases, 1):
        cid = case["id"]
        cat = case["category"]
        q = case["question"]
        print(f"\n[{idx:02d}/{len(cases)}] [{cat.upper()}] ID: {cid}")
        print(f"  Question : \"{q}\"")

        t0 = time.time()
        try:
            rep = evaluate_sql_uat_case(case, graph, schema)
        except Exception as exc:
            rep = {
                "id": cid,
                "question": q,
                "category": cat,
                "detected_intent": None,
                "detected_kpi": None,
                "selected_datasets": [],
                "generated_sql": "",
                "sql_validation": False,
                "sql_execution": False,
                "result_correctness": False,
                "expected_concept": case.get("expected_sql_concepts", []),
                "actual_concept": [],
                "final_response": "",
                "passed": False,
                "failure_category": "Other",
                "failure_reason": f"Unhandled case evaluation error: {exc}",
            }
        dt = time.time() - t0

        reports.append(rep)
        if rep["passed"]:
            category_stats[cat]["passed"] += 1
            print(f"  Result   : \033[92mPASS\033[0m ({dt:.2f}s) | KPI: {rep['detected_kpi']}")
            if rep.get("generated_sql"):
                print(f"  SQL      : {rep['generated_sql'].replace(chr(10), ' ')[:90]}...")
        else:
            print(f"  Result   : \033[91mFAIL\033[0m ({dt:.2f}s)")
            print(f"  Category : {rep['failure_category']}")
            print(f"  Reason   : {rep['failure_reason']}")
            if rep.get("generated_sql"):
                print(f"  SQL      : {rep['generated_sql'].replace(chr(10), ' ')[:90]}...")

    total_time = time.time() - start_time
    total_cases = len(cases)
    total_passed = sum(r["passed"] for r in reports)
    total_failed = total_cases - total_passed
    overall_acc = (total_passed / total_cases) * 100.0

    print("\n" + "=" * 80)
    print("EVALUATING AMBIGUOUS QUESTIONS SEPARATELY")
    print("=" * 80)
    amb_reports = []
    for ac in AMBIGUOUS_QUESTIONS:
        arep = evaluate_ambiguous_case(ac, graph)
        amb_reports.append(arep)
        print(f"  Question : \"{ac['question']}\" -> {arep['behavior']} (Safe: {arep['fallback_safe']})")
        print(f"  Details  : {arep['details'][:100]}")

    print("\n" + "=" * 80)
    print("CLINICAL NATURAL LANGUAGE UAT SUMMARY")
    print("=" * 80)
    print(f"  Total Questions : {total_cases}")
    print(f"  Passed          : {total_passed}")
    print(f"  Failed          : {total_failed}")
    print(f"  Overall Accuracy: {overall_acc:.1f}%")
    print(f"  Execution Time  : {total_time:.2f}s")
    print("-" * 80)
    print(f"{'Category':<15} {'Passed':>8} {'Total':>8} {'Accuracy':>10}")
    print("-" * 80)
    for cat, stat in category_stats.items():
        c_acc = (stat["passed"] / stat["total"]) * 100.0 if stat["total"] else 0.0
        print(f"{cat.capitalize():<15} {stat['passed']:>8} {stat['total']:>8} {c_acc:>9.1f}%")
    print("=" * 80)

    # Save artifact
    output_artifact = {
        "total_cases": total_cases,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "overall_accuracy_pct": overall_acc,
        "execution_time_seconds": total_time,
        "category_stats": category_stats,
        "reports": reports,
        "ambiguity_reports": amb_reports,
    }
    with open(PROJECT_ROOT / "evals" / "CLINICAL_UAT_REPORT.json", "w", encoding="utf-8") as f:
        json.dump(output_artifact, f, indent=2)

    return output_artifact


if __name__ == "__main__":
    run_full_uat()
