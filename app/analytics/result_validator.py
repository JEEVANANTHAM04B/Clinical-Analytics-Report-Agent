from decimal import Decimal
from typing import Any


def normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)

    return value


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: normalize_value(value)
        for key, value in row.items()
    }


def validate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(results, list):
        return {
            "valid": False,
            "message": "Query result must be a list",
            "rows": [],
        }

    for row in results:
        if not isinstance(row, dict):
            return {
                "valid": False,
                "message": "Each result row must be a dictionary",
                "rows": [],
            }

    normalized_rows = [
        normalize_row(row)
        for row in results
    ]

    return {
        "valid": True,
        "message": "Query results are valid",
        "row_count": len(normalized_rows),
        "rows": normalized_rows,
    }