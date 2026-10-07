import json
import sys
from pathlib import Path

# Ensure unbuffered output so logs print immediately
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.visualization.chart_generator import create_chart_spec

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "chart_test_cases.json"


def load_test_cases():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_chart_spec(
    spec: dict | None,
    input_rows: list[dict],
    case_def: dict,
    caught_exception: Exception | None = None,
) -> tuple[bool, list[str]]:
    """
    Deterministically validate the generated chart specification against expected requirements.
    """
    failures = []
    input_columns = list(input_rows[0].keys()) if input_rows else []

    # Handle empty-result test case
    if not case_def.get("expect_spec", True):
        if caught_exception is not None:
            expected_exceptions = tuple(
                getattr(__builtins__, exc_name, Exception)
                for exc_name in case_def.get("expected_exception_types", ["ValueError"])
            )
            if isinstance(caught_exception, expected_exceptions):
                return True, []
            else:
                failures.append(
                    f"Unexpected exception type: {type(caught_exception).__name__}: {caught_exception}"
                )
                return False, failures
        elif spec is None or spec == {}:
            return True, []
        else:
            failures.append(f"Expected empty spec or ValueError, but got non-empty spec: {spec}")
            return False, failures

    # Cases expecting a valid specification
    if caught_exception is not None:
        failures.append(f"Unexpected exception during chart spec generation: {caught_exception}")
        return False, failures

    if not isinstance(spec, dict):
        failures.append(f"Chart specification is not a dictionary: {spec}")
        return False, failures

    # 1. Structure check
    required_keys = ["chart_type", "x_column", "y_column", "title"]
    missing_keys = [k for k in required_keys if k not in spec]
    if missing_keys:
        failures.append(f"Missing required keys in chart_spec: {missing_keys}")

    chart_type = spec.get("chart_type")
    x_column = spec.get("x_column")
    y_column = spec.get("y_column")
    title = spec.get("title")

    # 2. Chart type check
    valid_types = case_def.get("valid_chart_types", ["bar", "line", "scatter"])
    if chart_type not in valid_types:
        failures.append(f"Invalid chart_type '{chart_type}'. Expected one of: {valid_types}")

    # 3. X Column validation
    expected_x = case_def.get("expected_x_columns", [])
    if expected_x and x_column not in expected_x:
        failures.append(f"x_column '{x_column}' not in expected columns: {expected_x}")

    # 4. Y Column validation
    expected_y = case_def.get("expected_y_columns", [])
    if expected_y and y_column not in expected_y:
        failures.append(f"y_column '{y_column}' not in expected columns: {expected_y}")

    # 5. Title validation
    if case_def.get("require_non_empty_title", True):
        if not title or not str(title).strip():
            failures.append("Chart title is empty or missing")

    # 6. Column existence in input dataset
    if x_column not in input_columns:
        failures.append(f"x_column '{x_column}' does not exist in input row columns: {input_columns}")

    if y_column not in input_columns:
        failures.append(f"y_column '{y_column}' does not exist in input row columns: {input_columns}")

    return len(failures) == 0, failures


def run_chart_generation_eval():
    test_cases = load_test_cases()
    total_tests = len(test_cases)
    passed_tests = 0
    failed_tests = 0

    print("=" * 80)
    print("DETERMINISTIC CHART SPECIFICATION GENERATION EVALUATION RUNNER")
    print(f"Dataset: {DATASET_PATH.name} ({total_tests} test cases)")
    print("=" * 80)

    for idx, case in enumerate(test_cases, 1):
        case_id = case["id"]
        category = case.get("category", "General")
        description = case.get("description", "")
        input_rows = case.get("input_rows", [])
        input_columns = list(input_rows[0].keys()) if input_rows else []

        print(f"\n--- [{idx}/{total_tests}] Test ID: {case_id} ({category}) ---")
        print(f"Description   : {description}")
        print(f"Input Columns : {input_columns}")
        print(f"Input Rows ({len(input_rows)} rows): {input_rows}")

        spec = None
        caught_exception = None

        # 1. Call the REAL create_chart_spec() function
        try:
            spec = create_chart_spec(input_rows)
            print(f"Generated Spec: {spec}")
        except Exception as exc:
            caught_exception = exc
            print(f"Caught Exception: {type(exc).__name__}: {exc}")

        # 2. Validate specification
        is_valid, failures = validate_chart_spec(
            spec=spec,
            input_rows=input_rows,
            case_def=case,
            caught_exception=caught_exception,
        )

        # 3. Print validation details
        if is_valid:
            passed_tests += 1
            if spec:
                print(f"Validation    : [VALID] chart_type='{spec.get('chart_type')}', x='{spec.get('x_column')}', y='{spec.get('y_column')}', title='{spec.get('title')}'")
                print("All referenced columns exist in the input data.")
            else:
                print("Validation    : [VALID] Handled empty result set safely without unexpected exceptions.")
            print("Status        : PASS")
        else:
            failed_tests += 1
            print("Validation    : [INVALID]")
            for failure in failures:
                print(f"  [ERROR] {failure}")
            print("Status        : FAIL")

    # 4. Print final evaluation summary
    pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0.0

    print("\n" + "=" * 50)
    print("FINAL CHART EVALUATION SUMMARY")
    print("=" * 50)
    print(f"Total Tests : {total_tests}")
    print(f"Passed      : {passed_tests}")
    print(f"Failed      : {failed_tests}")
    print(f"Pass Rate   : {pass_rate:.1f}%")
    print("=" * 50)

    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_chart_generation_eval()
    sys.exit(0 if success else 1)
