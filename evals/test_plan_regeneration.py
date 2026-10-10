import json
import sys
from pathlib import Path

# Ensure unbuffered standard output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.schema_service import get_database_schema
from app.workflow.graph import (
    regenerate_analysis_plan,
    approval_router,
    regeneration_router,
)
from langgraph.graph import END

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "plan_regeneration_test_cases.json"

BASE_PLAN = """### Clinical Analytics Analysis Plan

#### 1. Relevant Tables and Columns
* **`dm`**:
  * `USUBJID` (VARCHAR): Unique identifier for the subject.
  * `ARM` (VARCHAR): Treatment arm.
  * `AGE` (DOUBLE): Subject age.
* **`ae`**:
  * `USUBJID` (VARCHAR): Subject identifier.
  * `AETERM` (VARCHAR): Adverse event verbatim term.
  * `AESEV` (VARCHAR): Severity classification.
  * `AESER` (VARCHAR): Serious adverse event flag.

#### 2. Join Conditions
* `dm.USUBJID = ae.USUBJID`

#### 3. Derived Calculations
* **Adverse Event Count**:
  `COUNT(*)`

#### 4. Aggregations & Grouping
* **Grouping**:
  Group results by `ae.AESEV`.

#### 5. Filtering
* **Valid Subject Identifier**:
  * `dm.USUBJID IS NOT NULL`
  * `ae.USUBJID IS NOT NULL`
* **Age Range**:
  * Include only subjects with age between 18 and 65:
    * `dm.AGE BETWEEN 18 AND 65`"""


def load_test_cases():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run_router_tests(data: dict):
    approval_cases = data.get("approval_router_cases", [])
    regen_cases = data.get("regeneration_router_cases", [])

    approval_passed = 0
    regen_passed = 0

    print("\n" + "=" * 80)
    print("WORKFLOW ROUTER TESTS")
    print("=" * 80)

    # 1. Approval Router
    print("\n[A] Testing approval_router():")
    for case in approval_cases:
        case_id = case["id"]
        status = case["approval_status"]
        expected = case["expected_destination"]
        expected_sym = END if expected == "__end__" else expected

        state = {"approval_status": status}
        actual = approval_router(state)
        passed = (actual == expected_sym)
        if passed:
            approval_passed += 1
            print(f"  [PASS] {case_id}: status='{status}' -> destination='{actual}'")
        else:
            print(f"  [FAIL] {case_id}: status='{status}' -> expected='{expected_sym}', got='{actual}'")

    # 2. Regeneration Router
    print("\n[B] Testing regeneration_router():")
    for case in regen_cases:
        case_id = case["id"]
        source = case.get("approval_source", "")
        status = case.get("approval_status", "")
        expected = case["expected_destination"]
        expected_sym = END if expected == "__end__" else expected

        state = {"approval_source": source, "approval_status": status}
        actual = regeneration_router(state)
        passed = (actual == expected_sym)
        if passed:
            regen_passed += 1
            print(f"  [PASS] {case_id}: source='{source}', status='{status}' -> destination='{actual}'")
        else:
            print(f"  [FAIL] {case_id}: source='{source}', status='{status}' -> expected='{expected_sym}', got='{actual}'")

    return approval_passed, len(approval_cases), regen_passed, len(regen_cases)


def run_plan_regeneration_tests(data: dict, schema: dict):
    cases = data.get("plan_regeneration_cases", [])
    passed_count = 0
    total_count = len(cases)

    print("\n" + "=" * 80)
    print("ANALYSIS PLAN REGENERATION TESTS")
    print(f"Dataset: {DATASET_PATH.name} ({total_count} regeneration cases)")
    print("=" * 80)

    for idx, case in enumerate(cases, 1):
        case_id = case["id"]
        category = case.get("category", "")
        name = case.get("name", "")
        question = case["question"]
        current_plan = BASE_PLAN
        human_feedback = case.get("human_feedback", "")
        feedback_history = list(case.get("feedback_history", []))
        initial_version = case.get("plan_version", 1)
        approval_source = case.get("approval_source", "api")

        print(f"\n--- [{idx}/{total_count}] Test ID: {case_id} ({category}) ---")
        print(f"Test Name       : {name}")
        print(f"User Question   : \"{question}\"")
        print(f"Current Feedback: \"{human_feedback}\"")
        print(f"Feedback History: {feedback_history}")
        print(f"Initial Version : {initial_version}")

        # 1. Build exact state required by production function
        state = {
            "user_question": question,
            "database_schema": schema,
            "analysis_plan": current_plan,
            "human_feedback": human_feedback,
            "feedback_history": feedback_history,
            "plan_version": initial_version,
            "approval_source": approval_source,
        }

        # 2. Call real production function
        try:
            result = regenerate_analysis_plan(state)
            revised_plan = result.get("analysis_plan", "")
            new_version = result.get("plan_version")
            new_status = result.get("approval_status")
            new_history = result.get("feedback_history", [])
        except Exception as exc:
            revised_plan = ""
            new_version = initial_version
            new_status = "error"
            new_history = []
            print(f"Execution Error: {exc}")

        # 3. Print details
        print("\nRevised Analysis Plan:")
        print("-" * 50)
        print(revised_plan if revised_plan else "[NO PLAN REVISED]")
        print("-" * 50)
        print(f"New Plan Version : {new_version}")
        print(f"Approval Status  : {new_status}")
        print(f"Updated History  : {new_history}")

        # 4. Deterministic verification
        failures = []
        revised_lower = revised_plan.lower()

        # Check required present items
        for req in case.get("expected_present", []):
            if req.lower() not in revised_lower:
                failures.append(f"Missing expected requirement: '{req}'")

        # Check required absent items
        for forbidden in case.get("expected_absent", []):
            if forbidden.lower() in revised_lower:
                failures.append(f"Forbidden requirement still present: '{forbidden}'")

        # Category-specific checks
        if case.get("check_serious_filter"):
            if "aeser" not in revised_lower:
                failures.append("Plan missing serious adverse events filter (AESER).")

        if case.get("check_grouping_arm"):
            if "arm" not in revised_lower:
                failures.append("Plan does not group by treatment arm.")

        if case.get("check_severity_grouping_removed"):
            if "group results by `ae.aesev`" in revised_lower or "group by `ae.aesev`" in revised_lower:
                failures.append("Severity grouping was not removed.")

        if case.get("check_version_increment"):
            if new_version != initial_version + 1:
                failures.append(f"plan_version did not increment correctly. Expected {initial_version + 1}, got {new_version}")

        if case.get("check_feedback_history_preservation"):
            for prior_fb in feedback_history:
                if prior_fb not in new_history:
                    failures.append(f"Prior feedback '{prior_fb}' was not preserved in feedback_history")
            if human_feedback and human_feedback not in new_history:
                failures.append(f"Current feedback '{human_feedback}' was not appended to feedback_history")

        # 5. Check approval status
        if new_status != "pending":
            failures.append(f"Expected approval_status to be 'pending', got '{new_status}'")

        # 6. Mark PASS/FAIL
        test_passed = (len(failures) == 0 and bool(revised_plan))
        if test_passed:
            passed_count += 1
            print("\nValidation      : [VALID] All deterministic preservation rules satisfied.")
            print("Status          : PASS")
        else:
            print("\nValidation      : [INVALID]")
            for failure in failures:
                print(f"  [ERROR] {failure}")
            print("Status          : FAIL")

    return passed_count, total_count


def run_full_evaluation():
    data = load_test_cases()
    schema = get_database_schema()

    # Run Router Tests
    app_passed, app_total, regen_passed, regen_total = run_router_tests(data)

    # Run Plan Regeneration Tests
    plan_passed, plan_total = run_plan_regeneration_tests(data, schema)

    total_tests = app_total + regen_total + plan_total
    passed_tests = app_passed + regen_passed + plan_passed
    failed_tests = total_tests - passed_tests
    pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0.0

    print("\n" + "=" * 50)
    print("FINAL PLAN REGENERATION EVALUATION SUMMARY")
    print("=" * 50)
    print(f"Total Tests : {total_tests}")
    print(f"Passed      : {passed_tests}")
    print(f"Failed      : {failed_tests}")
    print(f"Pass Rate   : {pass_rate:.1f}%")
    print("\nDetailed Category Breakdown:")
    print(f"  Approval Router Tests     : {app_passed}/{app_total} passed")
    print(f"  Regeneration Router Tests : {regen_passed}/{regen_total} passed")
    print(f"  Plan Regeneration Tests   : {plan_passed}/{plan_total} passed")
    print("=" * 50)

    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_full_evaluation()
    sys.exit(0 if success else 1)
