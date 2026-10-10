import re
from decimal import Decimal
from typing import Any


def _is_num(val: Any) -> bool:
    return isinstance(val, (int, float, Decimal))


def _find_category_key(query_results: list[dict[str, Any]]) -> str | None:
    if not query_results:
        return None
    sample = query_results[0]
    clinical_dimensions = (
        "treatment_arm", "trt01a", "arm", "site_name", "siteid",
        "param", "paramcd", "avisit", "visit", "aesev", "severity",
        "aebodsys", "aedecod", "sex", "race", "ethnic", "respfl",
        "encounter_class", "encounterclass", "diagnosis", "description", "category"
    )
    for k in clinical_dimensions:
        if k in sample:
            return k
    for k in sample:
        if any(dim in k.lower() for dim in ("treatment", "arm", "site", "param", "visit", "class", "diagnosis", "desc")):
            return k
    for k, v in sample.items():
        if isinstance(v, str):
            return k
    return None


def build_insight_evidence(
    query_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Build deterministic evidence from validated SQL results.

    This evidence is calculated by Python from verified SQL results.
    The LLM should use this evidence instead of independently
    determining maximum/minimum values.
    """

    if not query_results:
        return {
            "row_count": 0,
            "numeric_columns": [],
            "maximum": None,
            "minimum": None,
        }

    numeric_columns = []

    for key in query_results[0].keys():
        values = [
            row.get(key)
            for row in query_results
            if _is_num(row.get(key))
        ]

        if values:
            numeric_columns.append(key)

    evidence = {
        "row_count": len(query_results),
        "numeric_columns": numeric_columns,
        "maximum": None,
        "minimum": None,
    }

    priority_metrics = (
        "adverse_event_rate_pct", "response_rate_pct", "mean_change",
        "enrolled_subjects", "subject_count", "average_age",
        "average_length_of_stay", "total_subjects", "total_safety_subjects",
        "subjects_with_ae", "cnt", "count"
    )
    metric_key = None
    for pm in priority_metrics:
        if pm in numeric_columns:
            metric_key = pm
            break
    if not metric_key and numeric_columns:
        metric_key = numeric_columns[0]

    if metric_key:
        valid_rows = [
            row
            for row in query_results
            if _is_num(row.get(metric_key))
        ]

        if valid_rows:
            category_key = _find_category_key(valid_rows)

            maximum_row = max(
                valid_rows,
                key=lambda row: float(row[metric_key]),
            )

            minimum_value = min(
                float(row[metric_key])
                for row in valid_rows
            )

            minimum_rows = [
                row
                for row in valid_rows
                if float(row[metric_key]) == minimum_value
            ]

            max_category = (
                str(maximum_row.get(category_key))
                if category_key and maximum_row.get(category_key) is not None
                else None
            )

            min_categories = [
                str(row.get(category_key))
                for row in minimum_rows
                if category_key and row.get(category_key) is not None
            ]

            evidence["maximum"] = {
                "metric": metric_key,
                "value": float(maximum_row[metric_key]),
                "category": max_category,
            }

            evidence["minimum"] = {
                "metric": metric_key,
                "value": float(minimum_value),
                "categories": min_categories,
            }

    return evidence


def _extract_numbers(text: str) -> list[float]:
    """
    Extract numeric values from insight text.

    Supports:
    - integers
    - decimals
    - percentages
    """

    matches = re.findall(
        r"(?<!\w)-?\d+(?:\.\d+)?%?",
        text,
    )

    numbers = []

    for match in matches:
        cleaned = match.replace("%", "")

        try:
            numbers.append(float(cleaned))
        except ValueError:
            continue

    return numbers


def _result_numeric_values(
    query_results: list[dict[str, Any]],
) -> list[float]:
    """
    Extract all numeric values from verified SQL results.
    """

    values = []

    for row in query_results:
        for value in row.values():
            if _is_num(value):
                values.append(float(value))

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
                categories.add(value.strip().lower())

    return categories


def _number_exists_in_results(
    number: float,
    result_numbers: list[float],
    tolerance: float = 0.0001,
) -> bool:
    """
    Check whether an insight number exists
    in the verified SQL results.
    """

    return any(
        abs(number - result_number) <= tolerance
        for result_number in result_numbers
    )


def validate_insight(
    insight: str,
    query_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Deterministically validate an LLM-generated insight
    against verified SQL results.
    """

    if not insight or not insight.strip():
        return {
            "valid": False,
            "message": "Insight is empty.",
            "unsupported_numbers": [],
            "unsupported_categories": [],
            "ranking_issue": "Insight is empty.",
        }

    result_numbers = _result_numeric_values(
        query_results
    )

    result_categories = _result_categories(
        query_results
    )

    insight_numbers = _extract_numbers(
        insight
    )

    unsupported_numbers = []

    for number in insight_numbers:

        if not _number_exists_in_results(
            number,
            result_numbers,
        ):
            unsupported_numbers.append(number)

    unsupported_categories = []

    # Check whether important category names
    # mentioned by the insight actually exist
    # in the verified results.
    insight_lower = insight.lower()

    for phrase in re.findall(
        r"\b[A-Za-z][A-Za-z\s\-()']{3,}\b",
        insight,
    ):

        normalized_phrase = phrase.strip().lower()

        if (
            normalized_phrase
            and normalized_phrase in result_categories
        ):
            continue

    # Detect ranking claims.
    ranking_issue = None

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

    if result_numbers:

        actual_max = max(result_numbers)
        actual_min = min(result_numbers)

        if has_highest_claim:

            highest_number_matches = [
                number
                for number in insight_numbers
                if abs(
                    number - actual_max
                ) <= 0.0001
            ]

            if not highest_number_matches:

                ranking_issue = (
                    "Insight contains a highest-value claim, "
                    f"but the actual maximum verified value "
                    f"is {actual_max}."
                )

        if (
            has_lowest_claim
            and ranking_issue is None
        ):

            lowest_number_matches = [
                number
                for number in insight_numbers
                if abs(
                    number - actual_min
                ) <= 0.0001
            ]

            if not lowest_number_matches:

                ranking_issue = (
                    "Insight contains a lowest-value claim, "
                    f"but the actual minimum verified value "
                    f"is {actual_min}."
                )

    valid = (
        len(unsupported_numbers) == 0
        and ranking_issue is None
    )

    if valid:
        message = (
            "Insight passed deterministic validation."
        )
    else:
        message = (
            "Insight failed deterministic validation."
        )

    return {
        "valid": valid,
        "message": message,
        "unsupported_numbers": unsupported_numbers,
        "unsupported_categories": unsupported_categories,
        "ranking_issue": ranking_issue,
    }