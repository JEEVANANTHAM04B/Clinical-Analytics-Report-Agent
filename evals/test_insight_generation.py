import json
import re
import sys
from pathlib import Path

# Ensure line-buffered output so test logs appear immediately
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.analytics.insight_evidence import build_insight_evidence
from app.ai.insight_generator import generate_insight
from app.ai.insight_validator import validate_insight

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "insight_test_cases.json"


def load_test_cases():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def check_fact_present(fact_def: dict, insight_text: str) -> bool:
    """Deterministically check if an expected fact is present in the insight."""
    insight_lower = insight_text.lower()
    insight_cleaned = insight_lower.replace(",", "").replace("$", "")

    if "keywords" in fact_def:
        for kw in fact_def["keywords"]:
            kw_clean = kw.lower().replace(",", "").replace("$", "")
            if kw_clean not in insight_cleaned and kw.lower() not in insight_lower:
                return False

    if "keywords_any" in fact_def:
        any_matched = any(
            (kw.lower() in insight_lower or kw.lower().replace(",", "") in insight_cleaned)
            for kw in fact_def["keywords_any"]
        )
        if not any_matched:
            return False

    if fact_def.get("requires_highest"):
        if not re.search(r"\b(highest|maximum|max)\b", insight_lower):
            return False

    return True


def run_insight_generation_eval():
    test_cases = load_test_cases()
    total_tests = len(test_cases)
    passed_tests = 0
    failed_tests = 0

    insights_validated = 0
    validation_failures = 0

    print("=" * 80)
    print("DETERMINISTIC INSIGHT GENERATION & VALIDATION EVALUATION RUNNER")
    print(f"Dataset: {DATASET_PATH.name} ({total_tests} test cases)")
    print("=" * 80)

    for idx, case in enumerate(test_cases, 1):
        case_id = case["id"]
        category = case.get("category", "General")
        question = case["question"]
        query_results = case.get("query_results", [])
        expected_facts = case.get("expected_facts", [])
        requires_empty_warning = case.get("requires_empty_warning", False)

        print(f"\n--- [{idx}/{total_tests}] Test ID: {case_id} ({category}) ---")
        print(f"Question: \"{question}\"")
        print(f"Verified SQL Results ({len(query_results)} rows): {query_results}")

        # 1. Build deterministic insight evidence using the project's real function
        evidence = build_insight_evidence(query_results)

        # 2. Generate insight using real production function
        try:
            insight = generate_insight(
                user_question=question,
                query_results=query_results,
                insight_evidence=evidence,
            )
        except Exception as e:
            insight = ""
            print(f"Insight generation error: {e}")

        print("\nGenerated Insight:")
        print("-" * 50)
        print(insight if insight else "[NO INSIGHT GENERATED]")
        print("-" * 50)

        # 4. Deterministic validation using production validate_insight
        validation = validate_insight(insight, query_results, evidence)
        insights_validated += 1

        is_valid = validation.get("valid", False)
        validation_message = validation.get("message", "")
        unsupported_numbers = validation.get("unsupported_numbers", [])
        ranking_issue = validation.get("ranking_issue")

        if not is_valid:
            validation_failures += 1

        print(f"\nValidation Result  : {'VALID' if is_valid else 'INVALID'}")
        print(f"Validation Message : {validation_message}")

        # 5. Check expected facts
        matched_facts = []
        missing_facts = []

        for fact_def in expected_facts:
            fact_label = fact_def.get("fact", "Unnamed fact")
            if check_fact_present(fact_def, insight):
                matched_facts.append(fact_label)
            else:
                missing_facts.append(fact_label)

        print("\nExpected Facts Status:")
        for fact in matched_facts:
            print(f"  [MATCHED] {fact}")
        for fact in missing_facts:
            print(f"  [MISSING] {fact}")

        # 6. Check unsupported claims
        unsupported_claims = []
        if unsupported_numbers:
            unsupported_claims.append(f"Unsupported numbers: {unsupported_numbers}")
        if ranking_issue:
            unsupported_claims.append(f"Ranking issue: {ranking_issue}")

        # Empty result set specific checks
        if requires_empty_warning and len(query_results) == 0:
            if not any(kw in insight.lower() for kw in ["no ", "0", "empty", "none"]):
                unsupported_claims.append("Did not state that no records were returned for empty result set.")

        print("\nUnsupported Claims Status:")
        if unsupported_claims:
            for claim in unsupported_claims:
                print(f"  [CLAIM] {claim}")
        else:
            print("  [NONE] No unsupported claims detected")

        # 7. Determine overall PASS / FAIL
        test_passed = (
            bool(insight)
            and is_valid
            and len(missing_facts) == 0
            and len(unsupported_claims) == 0
        )

        status = "PASS" if test_passed else "FAIL"
        if test_passed:
            passed_tests += 1
            print(f"\nOverall Status: {status} (All requirements satisfied)")
        else:
            failed_tests += 1
            fail_reasons = []
            if not is_valid:
                fail_reasons.append("deterministic validation failed")
            if missing_facts:
                fail_reasons.append(f"{len(missing_facts)} missing facts")
            if unsupported_claims:
                fail_reasons.append(f"{len(unsupported_claims)} unsupported claims")
            print(f"\nOverall Status: {status} ({', '.join(fail_reasons)})")

    # 8. Print final summaries
    pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0.0

    print("\n" + "=" * 50)
    print("FINAL EVALUATION SUMMARY")
    print("=" * 50)
    print(f"Total Tests : {total_tests}")
    print(f"Passed      : {passed_tests}")
    print(f"Failed      : {failed_tests}")
    print(f"Pass Rate   : {pass_rate:.1f}%")

    print("\n" + "=" * 50)
    print("VALIDATION SUMMARY")
    print("=" * 50)
    print(f"Generated Insights Validated : {insights_validated}")
    print(f"Validation Failures          : {validation_failures}")
    print("=" * 50)

    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_insight_generation_eval()
    sys.exit(0 if success else 1)
