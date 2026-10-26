"""Deterministic result contracts. No clinical values are imputed or deleted."""
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def normalize_row(row):
    return {key: normalize_value(value) for key, value in row.items()}


def result_contract(sql: str, schema=None) -> dict:
    """Derive output names/grain only when the SELECT explicitly supplies them."""
    import sqlglot
    from sqlglot import exp
    tree = sqlglot.parse_one(sql, read="mysql")
    if not isinstance(tree, exp.Select):
        return {}
    names = [x.alias_or_name for x in tree.expressions]
    if any(x.find(exp.Star) and not x.find(exp.AggFunc) for x in tree.expressions):
        names = []
    numeric = [x.alias_or_name for x in tree.expressions if x.find(exp.AggFunc)]
    groups = tree.args.get("group")
    keys = []
    if groups:
        for group in groups.expressions:
            matching = next((x.alias_or_name for x in tree.expressions
                if (x.this if isinstance(x, exp.Alias) else x) == group), None)
            if not matching and group.alias_or_name in names:
                matching = group.alias_or_name
            if not matching:
                keys = []
                break
            keys.append(matching)
    definitions = {}
    if schema:
        aliases = {t.alias_or_name.lower(): t.name for t in tree.find_all(exp.Table)}
        for projection in tree.expressions:
            expr = projection.this if isinstance(projection, exp.Alias) else projection
            if not isinstance(expr, exp.Column): continue
            tables = [aliases.get(expr.table.lower())] if expr.table else list(aliases.values())
            matches = [c for t in tables for c in schema.get("tables", {}).get(t, []) if c.get("name", "").lower() == expr.name.lower()]
            if len(matches) == 1:
                meta = matches[0]
                rule = {k: meta[k] for k in ("sentinels", "not_applicable", "allowed_values", "role", "required", "blank_is_missing") if k in meta}
                if "DATE" in meta.get("type", "").upper() or "TIME" in meta.get("type", "").upper(): rule["type"] = "date"
                definitions[projection.alias_or_name] = rule
    return {"columns": definitions, "expected_columns": names, "numeric_columns": numeric, "business_keys": keys,
            "grain": "aggregate groups" if groups else "query result rows"}


def validate_results(results: list[dict[str, Any]], contract=None) -> dict[str, Any]:
    contract = contract or {}
    def invalid(code, message, columns=None):
        return {"valid": False, "code": code, "message": message, "columns": columns or [], "rows": []}
    if not isinstance(results, list) or any(not isinstance(r, dict) for r in results):
        return invalid("RESULT_STRUCTURE", "The returned data has an unexpected structure.")
    if not results:
        return invalid("EMPTY_RESULT", "No records match this analysis. Review the approved filters or dataset.")
    columns = list(results[0])
    if not columns or any(set(r) != set(columns) for r in results):
        return invalid("RESULT_SCHEMA", "Result rows have inconsistent columns.")
    expected = contract.get("expected_columns", [])
    if expected and (len(expected) != len(set(expected)) or set(expected) != set(columns)):
        return invalid("RESULT_SCHEMA", "Returned columns do not match the validated query.", expected)
    rows = [normalize_row(row) for row in results]
    for column in columns:
        values = [r[column] for r in rows if r[column] is not None]
        if any(isinstance(v, (float, int)) and not isinstance(v, bool) and not math.isfinite(v) for v in values):
            return invalid("NONFINITE_VALUE", "A calculation returned a non-finite value.", [column])
        if any(not isinstance(v, (str, int, float, bool)) for v in values):
            return invalid("RESULT_TYPE", "A result contains unsupported value types.", [column])
        kinds = {"number" if isinstance(v, (float, int)) and not isinstance(v, bool) else type(v).__name__ for v in values}
        if len(kinds) > 1 or (column in contract.get("numeric_columns", []) and kinds - {"number"}):
            return invalid("RESULT_TYPE", "A result column contains inconsistent data types.", [column])
    for column in contract.get("required_columns", []):
        if column not in columns or any(r.get(column) is None or (isinstance(r.get(column), str) and not r[column].strip()) for r in rows):
            return invalid("REQUIRED_VALUE", "Required analysis values are missing; review the data before continuing.", [column])
    keys = contract.get("business_keys", [])
    if keys and set(keys).issubset(columns):
        seen = set()
        for row in rows:
            key = tuple(row[k] for k in keys)
            if key in seen:
                return invalid("DUPLICATE_GRAIN", "Repeated analysis groups may inflate counts. Review the query and data grain.", keys)
            seen.add(key)
    # Only this explicitly named, existing endpoint has a known denominator contract.
    for row in rows:
        if {"total_subjects", "ae_subjects", "ae_rate_pct"}.issubset(row):
            d, n, pct = row["total_subjects"], row["ae_subjects"], row["ae_rate_pct"]
            if any(v is None or isinstance(v, bool) or not isinstance(v, (int, float)) for v in (d, n, pct)) or d <= 0 or not 0 <= n <= d or abs(pct - round(100*n/d, 2)) > .011:
                return invalid("DENOMINATOR", "The event count, population size and reported percentage do not agree.")
    return {"valid": True, "code": "VALID", "message": "Results passed the configured checks.", "row_count": len(rows), "rows": rows}
