import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.analytics.sql_validator import validate_sql

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "sql_test_cases.json"


def load_test_cases():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run_sql_validator_eval():
    test_cases = load_test_cases()
    total_tests = len(test_cases)
    passed_tests = 0
    failed_tests = 0

    print("=" * 80)
    print("DETERMINISTIC SQL VALIDATOR EVALUATION RUNNER")
    print(f"Dataset: {DATASET_PATH.name} ({total_tests} test cases)")
    print("=" * 80)

    for case in test_cases:
        case_id = case["id"]
        category = case["category"]
        expected_valid = case["expected_valid"]
        sql = case["sql"]

        # Call the production SQL validator
        actual_valid, validator_reason = validate_sql(sql)

        # Check if actual boolean matches expected
        test_passed = (actual_valid == expected_valid)

        if test_passed:
            passed_tests += 1
            status = "PASS [OK]"
        else:
            failed_tests += 1
            status = "FAIL [X]"

        print(f"\n[{status}] ID: {case_id} | Category: {category}")
        print(f"  SQL: {sql}")
        print(f"  Expected: {expected_valid} | Actual: {actual_valid}")
        print(f"  Reason:   {validator_reason}")

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
    run_sql_validator_eval()
