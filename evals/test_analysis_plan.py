import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.schema_service import get_database_schema
from app.workflow.graph import analyze_question

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "analysis_plan_test_cases.json"


def load_test_cases():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def check_requirement(requirement_item, plan_text: str) -> tuple[str, bool]:
    """
    Deterministically check if an expected requirement is present in the plan text.
    Supports either a dict with 'requirement' and 'patterns', or a plain string description.
    """
    plan_lower = plan_text.lower()

    if isinstance(requirement_item, dict):
        req_name = requirement_item.get("requirement") or requirement_item.get("name", "Unknown Requirement")
        patterns = requirement_item.get("patterns") or requirement_item.get("keywords", [])
        
        # If explicit patterns are provided, all must be present
        if patterns:
            matched = all(pattern.lower() in plan_lower for pattern in patterns)
            return req_name, matched
        else:
            return req_name, req_name.lower() in plan_lower
    else:
        req_name = str(requirement_item)
        return req_name, req_name.lower() in plan_lower


def run_analysis_plan_eval():
    test_cases = load_test_cases()
    total_tests = len(test_cases)
    passed_tests = 0
    failed_tests = 0

    print("=" * 80)
    print("DETERMINISTIC ANALYSIS PLAN GENERATION EVALUATION RUNNER")
    print(f"Dataset: {DATASET_PATH.name} ({total_tests} test cases)")
    print("=" * 80)

    # Load approved database schema using production schema service
    database_schema = get_database_schema()

    for idx, case in enumerate(test_cases, 1):
        case_id = case["id"]
        category = case.get("category", "General")
        question = case["question"]
        expected_requirements = case.get("expected_requirements", [])

        print(f"\n--- [{idx}/{total_tests}] Test ID: {case_id} ({category}) ---")
        print(f"Question: \"{question}\"")

        # 1. Generate analysis plan using real production workflow logic
        try:
            state = {
                "user_question": question,
                "database_schema": database_schema,
            }
            result = analyze_question(state)
            generated_plan = result.get("analysis_plan", "")
        except Exception as e:
            generated_plan = ""
            print(f"Generation error: {e}")

        # 2. Print generated analysis plan
        print("\nGenerated Analysis Plan:")
        print("-" * 50)
        print(generated_plan if generated_plan else "[NO PLAN GENERATED]")
        print("-" * 50)

        # 3. Check each requirement deterministically
        matched_requirements = []
        missing_requirements = []

        for req in expected_requirements:
            req_name, is_matched = check_requirement(req, generated_plan)
            if is_matched:
                matched_requirements.append(req_name)
            else:
                missing_requirements.append(req_name)

        # 4. Report requirement matching
        print("\nMatched Requirements:")
        if matched_requirements:
            for req in matched_requirements:
                print(f"  [MATCHED] {req}")
        else:
            print("  (None)")

        print("\nMissing Requirements:")
        if missing_requirements:
            for req in missing_requirements:
                print(f"  [MISSING] {req}")
        else:
            print("  (None)")

        # 5. Determine PASS / FAIL
        test_passed = (len(missing_requirements) == 0 and bool(generated_plan))
        status = "PASS" if test_passed else "FAIL"

        if test_passed:
            passed_tests += 1
            print(f"\nStatus: {status} ({len(matched_requirements)}/{len(expected_requirements)} requirements satisfied)")
        else:
            failed_tests += 1
            print(f"\nStatus: {status} ({len(missing_requirements)} missing requirements)")

    # 6. Print final summary
    pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0.0

    print("\n" + "=" * 80)
    print("FINAL EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Total Tests : {total_tests}")
    print(f"Passed      : {passed_tests}")
    print(f"Failed      : {failed_tests}")
    print(f"Pass Rate   : {pass_rate:.1f}%")
    print("=" * 80)

    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_analysis_plan_eval()
    sys.exit(0 if success else 1)
