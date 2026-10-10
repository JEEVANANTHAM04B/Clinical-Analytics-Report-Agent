import json
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.analytics.query_executor import execute_query
from app.analytics.result_validator import validate_results

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "sql_execution_test_cases.json"


def load_test_cases():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


from decimal import Decimal


def verify_numeric_fields(rows: list[dict[str, Any]], expected_type: str) -> tuple[bool, str]:
    """Verify that expected numeric aggregations contain valid numeric values."""
    if not rows or expected_type not in ("numeric_aggregation", "count_aggregation", "ranked_aggregation"):
        return True, "No numeric checks required"

    for row in rows:
        for key, val in row.items():
            key_lower = key.lower()
            is_numeric_metric = (
                key_lower in ("avg_los", "total_claim_cost", "total_payer_coverage", "encounter_count", "patient_count", "diagnosis_count", "subject_count", "total_subjects", "enrolled_subjects", "serious_adverse_events")
                or key_lower.endswith("_count")
                or key_lower.endswith("_cost")
                or key_lower.endswith("_coverage")
                or key_lower.endswith("_rate")
                or key_lower.endswith("_pct")
                or key_lower.startswith("avg_")
                or key_lower.startswith("sum_")
                or key_lower.startswith("mean_")
            )
            if is_numeric_metric:
                if val is not None and not isinstance(val, (int, float, Decimal)):
                    return False, f"Column '{key}' value {val!r} is not numeric"

    return True, "All numeric values are valid"


def run_sql_execution_eval():
    test_cases = load_test_cases()
    total_tests = len(test_cases)
    passed_tests = 0
    failed_tests = 0

    print("=" * 80)
    print("DETERMINISTIC SQL EXECUTION & RESULT VALIDATION RUNNER")
    print(f"Dataset: {DATASET_PATH.name} ({total_tests} test cases)")
    print("=" * 80)

    for case in test_cases:
        case_id = case["id"]
        category = case["category"]
        sql = case["sql"]
        expected_columns = case.get("expected_columns", [])
        expect_non_empty = case.get("expect_non_empty", True)
        expected_result_type = case.get("expected_result_type", "")

        exec_status = "SUCCESS"
        exec_error = None
        rows = []
        validation_info = {}
        pass_reasons = []
        fail_reasons = []

        # 1. Execute query using production query executor
        try:
            rows = execute_query(sql)
        except Exception as e:
            exec_status = "ERROR"
            exec_error = str(e)
            fail_reasons.append(f"Execution error: {exec_error}")

        # 2. Validate results using production result validator
        if exec_status == "SUCCESS":
            validation_info = validate_results(rows)
            if not validation_info.get("valid", False):
                fail_reasons.append(f"Result validator rejected rows: {validation_info.get('message')}")

            # 3. Check row count / non-empty expectation
            row_count = len(rows)
            if expect_non_empty and row_count == 0:
                fail_reasons.append("Expected non-empty result set, but got 0 rows")
            elif not expect_non_empty and row_count > 0:
                fail_reasons.append(f"Expected empty result set, but got {row_count} rows")
            else:
                pass_reasons.append(f"Row count ({row_count}) matches non-empty expectation ({expect_non_empty})")

            # 4. Check expected columns
            actual_columns = list(rows[0].keys()) if row_count > 0 else expected_columns
            missing_cols = [col for col in expected_columns if col not in actual_columns]
            if missing_cols:
                fail_reasons.append(f"Missing expected columns: {missing_cols}")
            else:
                pass_reasons.append(f"All expected columns present: {expected_columns}")

            # 5. Check numeric value validity
            num_ok, num_msg = verify_numeric_fields(rows, expected_result_type)
            if not num_ok:
                fail_reasons.append(num_msg)
            else:
                pass_reasons.append(num_msg)
        else:
            actual_columns = []
            row_count = 0

        # Determine overall test pass/fail
        test_passed = (exec_status == "SUCCESS" and len(fail_reasons) == 0)

        if test_passed:
            passed_tests += 1
            status_tag = "PASS [OK]"
        else:
            failed_tests += 1
            status_tag = "FAIL [X]"

        print(f"\n[{status_tag}] ID: {case_id} | Category: {category}")
        print(f"  Question:     {case.get('question')}")
        print(f"  SQL:          {sql}")
        print(f"  Exec Status:  {exec_status}")
        print(f"  Row Count:    {row_count}")
        print(f"  Columns:      {actual_columns}")
        print(f"  Validation:   {validation_info.get('message', 'N/A')}")
        if fail_reasons:
            print(f"  Issues:       {'; '.join(fail_reasons)}")

    pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0.0

    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Total Tests : {total_tests}")
    print(f"Passed      : {passed_tests}")
    print(f"Failed      : {failed_tests}")
    print(f"Pass Rate   : {pass_rate:.1f}%")
    print("=" * 80)


if __name__ == "__main__":
    run_sql_execution_eval()
