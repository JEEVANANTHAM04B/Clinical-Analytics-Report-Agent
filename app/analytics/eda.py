"""Read-only EDA over verified results, driven by explicit analysis definitions."""
from collections import Counter
from datetime import datetime
import pandas as pd
from app.analytics.result_validator import validate_results


def assess_results(rows, definitions=None):
    definitions = definitions or {}
    validation = validate_results(rows, definitions)
    findings, missingness, numeric, categorical, dates = [], {}, {}, {}, {}
    def finding(code, columns, count, message, severity="WARNING"):
        findings.append({"code": code, "columns": columns, "count": count, "severity": severity,
            "message": message, "impact": "May affect analytical interpretation.",
            "recommended_action": "Review the source and approved analysis; no values were changed."})
    if not validation["valid"]:
        finding(validation["code"], validation.get("columns", []), len(rows) if isinstance(rows, list) else 0,
                validation["message"], "CRITICAL")
        return {"validation_status": "rejected", "safe_to_continue": False, "findings": findings, "severity": "CRITICAL"}
    rows = validation["rows"]
    n = len(rows)
    frame = pd.DataFrame(rows)
    for col in frame.columns:
        values = [r[col] for r in rows]
        rules = definitions.get("columns", {}).get(col, {})
        nulls = sum(v is None for v in values)
        empty = sum(v == "" for v in values)
        whitespace = sum(isinstance(v, str) and v != "" and not v.strip() for v in values)
        sentinels = sum(v is not None and v in rules.get("sentinels", []) for v in values)
        na = sum(v is not None and v in rules.get("not_applicable", []) for v in values)
        missingness[col] = {"sql_null": nulls, "empty_string": empty, "whitespace": whitespace,
            "specified_sentinel": sentinels, "not_applicable": na, "null_percentage": round(nulls/n*100, 2)}
        missing = nulls + sentinels + ((empty + whitespace) if rules.get("blank_is_missing") else 0)
        if missing:
            critical = rules.get("required", False)
            finding("MISSING", [col], missing,
                f"{col}: {missing} of {n} result values are missing. Available observations may have a smaller denominator.",
                "CRITICAL" if critical else "WARNING")
        if empty or whitespace:
            finding("BLANK", [col], empty + whitespace, f"{col}: {empty + whitespace} blank text values require interpretation using the dataset definition.")
        nonmissing = [v for v in values if v is not None and v not in rules.get("sentinels", []) and v not in rules.get("not_applicable", [])]
        # Identifiers are not continuous measurements even when stored as numbers.
        is_number = nonmissing and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in nonmissing)
        if is_number and rules.get("role") != "identifier":
            series = pd.Series(nonmissing, dtype=float)
            q1, q3 = float(series.quantile(.25)), float(series.quantile(.75))
            outliers = int(((series < q1 - 1.5*(q3-q1)) | (series > q3 + 1.5*(q3-q1))).sum()) if len(series) >= 4 else 0
            numeric[col] = {"n": len(series), "min": float(series.min()), "max": float(series.max()),
                "mean": float(series.mean()), "median": float(series.median()),
                "std": float(series.std()) if len(series) > 1 else None,
                "q25": q1, "q75": q3, "potential_outliers": outliers,
                "outlier_method": "1.5 IQR; minimum four observations"}
            if outliers:
                finding("OUTLIER", [col], outliers, f"{col}: {outliers} potential outliers were retained unchanged.", "INFO")
        elif rules.get("type") != "date" and rules.get("role") != "identifier":
            counts = Counter(nonmissing)
            # Avoid exposing high-cardinality values/identifiers in summaries.
            categorical[col] = {"unique_count": len(counts), "frequencies": dict(counts) if len(counts) <= 20 else {},
                "rare_category_count": sum(count == 1 for count in counts.values())}
            allowed = rules.get("allowed_values")
            if allowed is not None:
                bad = sum(v not in allowed for v in nonmissing)
                if bad: finding("CATEGORY", [col], bad, f"{col}: {bad} values are outside the dataset's defined categories.", "HIGH")
            if all(isinstance(v, str) for v in nonmissing) and len({v.strip().casefold() for v in nonmissing}) < len(counts):
                finding("REPRESENTATION", [col], len(counts), f"{col}: category spelling, spacing or capitalization may be inconsistent.")
        if rules.get("type") == "date":
            parsed = []
            bad = 0
            for value in values:
                try: parsed.append(datetime.fromisoformat(str(value)) if value is not None else None)
                except (ValueError, TypeError): parsed.append(None); bad += 1
            dates[col] = parsed
            if bad: finding("DATE", [col], bad, f"{col}: {bad} dates cannot be interpreted.", "HIGH")
    for start, end in definitions.get("date_pairs", []):
        if start in dates and end in dates:
            bad = sum(a is not None and b is not None and a.isoformat() > b.isoformat() for a,b in zip(dates[start], dates[end]))
            if bad: finding("DATE_ORDER", [start, end], bad, f"{bad} records have a start date after the end date.", "HIGH")
    duplicates = int(frame.duplicated().sum())
    if duplicates:
        finding("EXACT_DUPLICATE", list(frame.columns), duplicates,
            f"{duplicates} repeated result rows were found. These may be valid at the specified grain; no rows were deleted.")
    critical = any(f["severity"] == "CRITICAL" for f in findings)
    return {"validation_status": "rejected" if critical else "passed", "safe_to_continue": not critical,
        "severity": "CRITICAL" if critical else "HIGH" if any(f["severity"] == "HIGH" for f in findings) else "WARNING" if findings else "INFO",
        "review_required": any(f["severity"] == "HIGH" for f in findings), "row_count": n, "column_count": len(frame.columns),
        "columns": list(frame.columns), "data_types": {c: str(frame[c].dtype) for c in frame},
        "missingness": missingness, "numeric": numeric, "categorical": categorical, "exact_duplicate_rows": duplicates,
        "findings": findings, "transformations": [],
        "scope": "Summaries describe " + definitions.get("grain", "returned result rows") + "; they do not certify source records or patient-level distributions."}
