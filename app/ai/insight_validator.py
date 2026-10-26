import re
from decimal import Decimal
from typing import Any


def _is_numeric(value: Any) -> bool:
    """
    Check whether a value is a supported numeric type.

    Supports:
    - int
    - float
    - Decimal
    """

    return isinstance(value, (int, float, Decimal))


def _extract_numbers(text: str) -> list[float]:
    """
    Extract numeric values from insight text.

    Supports:
    1484.76
    1,484.76
    45.06
    0.00
    35.13%
    """

    matches = re.findall(
        r"(?<!\w)-?\d[\d,]*(?:\.\d+)?%?",
        text,
    )

    numbers = []

    for match in matches:
        cleaned = match.replace(",", "").replace("%", "")

        try:
            numbers.append(float(cleaned))
        except ValueError:
            continue

    return numbers


def _result_numeric_values(
    query_results: list[dict[str, Any]],
) -> list[float]:
    """
    Extract numeric values from verified SQL results.

    Handles MySQL Decimal values as well as int, float,
    and numbers embedded in category strings (e.g. 'Site 10', 'Week 8').
    """

    values = []

    for row in query_results:
        for value in row.values():

            if _is_numeric(value):
                values.append(float(value))
            elif isinstance(value, str):
                for num in _extract_numbers(value):
                    values.append(num)

    return values


def _result_categories(
    query_results: list[dict[str, Any]],
) -> set[str]:
    """
    Extract textual category values from verified SQL results.
    """

    categories = set()

    for row in query_results:
        for value in row.values():

            if isinstance(value, str):
                categories.add(
                    value.strip().lower()
                )

    return categories


def _number_exists_in_results(
    number: float,
    result_numbers: list[float],
    tolerance: float = 0.0001,
) -> bool:
    """
    Check whether a number exists in the verified SQL results.

    Exact values are preferred.

    Two-decimal rounded values are also accepted because
    the LLM may format a verified value for readability.
    """

    # Exact / very-close match
    if any(
        abs(number - result_number) <= tolerance
        for result_number in result_numbers
    ):
        return True

    # Allow normal one- or two-decimal presentation
    for result_number in result_numbers:

        if round(number, 2) == round(result_number, 2) or round(number, 1) == round(result_number, 1):
            return True

    # Allow magnitude reporting for negative changes/reductions (e.g. "decreased by 0.8" for change = -0.8)
    if number > 0:
        for result_number in result_numbers:
            if result_number < 0:
                if abs(number - abs(result_number)) <= tolerance:
                    return True
                if round(number, 2) == round(abs(result_number), 2) or round(number, 1) == round(abs(result_number), 1):
                    return True

    return False


def validate_insight(
    insight: str,
    query_results: list[dict[str, Any]],
    insight_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Deterministically validate an LLM-generated insight.

    Ranking claims use deterministic evidence generated
    by Python rather than calculating rankings from the
    LLM output.
    """

    # ---------------------------------------------------------
    # Empty insight check
    # ---------------------------------------------------------

    if not insight or not insight.strip():

        return {
            "valid": False,
            "message": "Insight is empty.",
            "unsupported_numbers": [],
            "unsupported_categories": [],
            "ranking_issue": "Insight is empty.",
        }

    if insight_evidence is None:
        insight_evidence = {}

    # ---------------------------------------------------------
    # Extract verified SQL numbers
    # ---------------------------------------------------------

    result_numbers = _result_numeric_values(
        query_results
    )

    # ---------------------------------------------------------
    # Add deterministic row_count
    # ---------------------------------------------------------

    row_count = insight_evidence.get(
        "row_count"
    )

    if _is_numeric(row_count):

        result_numbers.append(
            float(row_count)
        )

    # Allow total sums of numeric columns across verified rows
    for key in insight_evidence.get("numeric_columns", []):
        col_vals = [float(row[key]) for row in query_results if _is_numeric(row.get(key))]
        if col_vals:
            result_numbers.append(sum(col_vals))

    # Allow numbers from verified query filters and evidence context (e.g. 'WEEK 8')
    for ev_key in ("sql_query", "applied_filters", "visit", "parameter"):
        ev_val = insight_evidence.get(ev_key)
        if isinstance(ev_val, str):
            for num in _extract_numbers(ev_val):
                result_numbers.append(num)
        elif isinstance(ev_val, (list, tuple, set)):
            for item in ev_val:
                if _is_numeric(item):
                    result_numbers.append(float(item))
                elif isinstance(item, str):
                    for num in _extract_numbers(item):
                        result_numbers.append(num)

    # ---------------------------------------------------------
    # Extract categories
    # ---------------------------------------------------------

    result_categories = _result_categories(
        query_results
    )

    # ---------------------------------------------------------
    # Extract numbers from insight
    # ---------------------------------------------------------

    insight_numbers = _extract_numbers(
        insight
    )

    # ---------------------------------------------------------
    # Validate numerical claims
    # ---------------------------------------------------------

    unsupported_numbers = []

    for number in insight_numbers:

        if not _number_exists_in_results(
            number,
            result_numbers,
        ):

            unsupported_numbers.append(
                number
            )

    # ---------------------------------------------------------
    # Ranking evidence
    # ---------------------------------------------------------

    insight_lower = insight.lower()

    maximum_evidence = insight_evidence.get(
        "maximum"
    )

    minimum_evidence = insight_evidence.get(
        "minimum"
    )

    # ---------------------------------------------------------
    # Detect ranking claims
    # ---------------------------------------------------------

    has_highest_claim = bool(
        re.search(
            r"\b(highest|maximum|max)\b",
            insight,
            re.IGNORECASE,
        )
    )

    has_lowest_claim = bool(
        re.search(
            r"\b(lowest|minimum|min)\b",
            insight,
            re.IGNORECASE,
        )
    )

    ranking_issue = None

    # ---------------------------------------------------------
    # Validate HIGHEST / MAXIMUM claim
    # ---------------------------------------------------------

    if has_highest_claim:

        if not maximum_evidence:

            ranking_issue = (
                "Insight contains a highest-value claim, "
                "but deterministic maximum evidence is unavailable."
            )

        else:

            expected_value = maximum_evidence.get(
                "value"
            )

            expected_category = maximum_evidence.get(
                "category"
            )

            expected_categories = list(maximum_evidence.get(
                "categories",
                [],
            ))
            if expected_category and expected_category not in expected_categories:
                expected_categories = [expected_category, *expected_categories]

            value_matches = False

            if expected_value is not None:

                value_matches = any(
                    _number_exists_in_results(
                        number,
                        [float(expected_value)],
                    )
                    for number in insight_numbers
                )

            category_matches = any(
                cat and cat.lower() in insight_lower
                for cat in expected_categories
            )

            if not value_matches or not category_matches:

                ranking_issue = (
                    "Highest-value claim does not match "
                    "the deterministic evidence. "
                    f"Expected category: {expected_category or expected_categories}; "
                    f"expected value: {expected_value}."
                )
    # ---------------------------------------------------------
    # Validate LOWEST / MINIMUM claim
    # ---------------------------------------------------------

    if (
        has_lowest_claim
        and ranking_issue is None
    ):

        if not minimum_evidence:

            ranking_issue = (
                "Insight contains a lowest-value claim, "
                "but deterministic minimum evidence is unavailable."
            )

        else:

            expected_value = minimum_evidence.get(
                "value"
            )

            expected_categories = list(minimum_evidence.get(
                "categories",
                [],
            ))
            if minimum_evidence.get("category") and minimum_evidence.get("category") not in expected_categories:
                expected_categories.append(minimum_evidence.get("category"))

            # Validate the minimum value.
            value_matches = False

            if expected_value is not None:

                value_matches = any(
                    _number_exists_in_results(
                        number,
                        [float(expected_value)],
                    )
                    for number in insight_numbers
                )

            # A lowest-value claim is valid when:
            # 1. The deterministic minimum value is present, and
            # 2. The insight either names one of the minimum
            #    categories OR explicitly says that the minimum
            #    occurs across multiple categories/diagnoses.
            category_matches = any(
                category
                and category.lower() in insight_lower
                for category in expected_categories
            )

            multiple_category_claim = bool(
                re.search(
                    r"\b(multiple|several|multiple diagnoses|multiple conditions|multiple categories)\b",
                    insight,
                    re.IGNORECASE,
                )
            )

            if not value_matches:

                ranking_issue = (
                    "Lowest-value claim does not match "
                    "the deterministic evidence. "
                    f"Expected value: {expected_value}."
                )

            elif not category_matches and not multiple_category_claim:

                ranking_issue = (
                    "Lowest-value claim contains the correct "
                    "minimum value but does not identify a "
                    "supported minimum category."
                )
    # ---------------------------------------------------------
    # Final validation
    # ---------------------------------------------------------

    valid = (
        len(unsupported_numbers) == 0
        and ranking_issue is None
    )

    if valid:

        message = (
            "Insight passed deterministic validation."
        )

    else:

        reasons = []
        if unsupported_numbers:
            reasons.append(f"unsupported numbers: {unsupported_numbers}")
        if ranking_issue:
            reasons.append(ranking_issue)
        details = "; ".join(reasons) if reasons else "unverified claims detected"
        message = f"Insight failed deterministic validation: {details}"

    return {
        "valid": valid,
        "message": message,
        "unsupported_numbers": unsupported_numbers,
        "unsupported_categories": [],
        "ranking_issue": ranking_issue,
    }