"""
app/ingestion/schema_inference.py
=================================
Semantic Data Type Inference and Column Profiling

WHY THIS EXISTS:
    Pandas dtypes (like 'object' or 'float64') do not capture clinical or
    relational semantics. For example:
      - 'ID' is an object in pandas, but semantically an Identifier / Primary Key candidate.
      - 'BIRTHDATE' is an object in pandas, but semantically a Date.
      - 'GENDER' is an object in pandas, but semantically Categorical.
      - 'observations.VALUE' is an object with mixed numeric measurements and text values.
      - 'ZIP' is float64 in pandas due to NaN representation, but semantically a Quasi-Identifier.

    This module performs comprehensive, deterministic profiling without AI,
    preserving read-only integrity on all source datasets.
"""

import math
import re
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
import pandas as pd

from app.schemas.validation import (
    ColumnAnalysis,
    DateColumnMetadata,
    ObservationsAnalysis,
)
from app.ingestion.privacy_detector import detect_sensitive_column


# =============================================================================
# Helper: Missingness Classification
# =============================================================================

def classify_missingness(null_percentage: float) -> str:
    """
    Classifies null percentage into standardized reporting brackets:
      - 0%
      - <5%
      - 5–20%
      - 20–50%
      - >50%
    """
    if null_percentage == 0.0:
        return "0%"
    elif null_percentage < 5.0:
        return "<5%"
    elif null_percentage < 20.0:
        return "5-20%"
    elif null_percentage < 50.0:
        return "20-50%"
    else:
        return ">50%"


# =============================================================================
# Helper: Date / Datetime Detection
# =============================================================================

DATE_NAME_HINTS = {"DATE", "START", "STOP", "BIRTHDATE", "DEATHDATE", "TIMESTAMP", "TIME"}

def detect_date_column(series: pd.Series, col_name: str) -> Optional[DateColumnMetadata]:
    """
    Evaluates whether a column contains date or datetime values.
    
    Vectorized and optimized for large datasets:
      - Samples up to 2,000 non-null values for fast heuristic test.
      - If parsing succeeds on >= 85% of sampled non-nulls, analyzes the full column.
      - Determines if it is pure date (YYYY-MM-DD) or datetime (has time component).
    """
    non_null_series = series.dropna()
    total_non_null = len(non_null_series)
    if total_non_null == 0:
        return None

    col_upper = col_name.strip().upper()
    has_date_name = any(hint in col_upper for hint in DATE_NAME_HINTS)

    # If dtype is already datetime
    if pd.api.types.is_datetime64_any_dtype(series):
        null_count = int(series.isna().sum())
        sample_str = [str(v) for v in non_null_series.head(3)]
        return DateColumnMetadata(
            column=col_name,
            detected_type="datetime",
            parse_success_percentage=100.0,
            invalid_date_count=0,
            null_count=null_count,
            sample_dates=sample_str,
        )

    # Only test object/string or integer/float if name matches or heuristic applies
    if not (has_date_name or series.dtype == "object"):
        return None

    # Sample for speed (up to 2,000 rows)
    sample_size = min(2000, total_non_null)
    sample = non_null_series.head(sample_size).astype(str)

    # Quick string check: does it look like date? (e.g. YYYY-MM-DD or contains '-' or '/')
    date_like_sample = sample.str.contains(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", regex=True)
    if not date_like_sample.any() and not has_date_name:
        return None

    # Attempt vectorized parse on the sample first
    parsed_sample = pd.to_datetime(sample, errors="coerce", format="mixed")
    success_rate = (parsed_sample.notna().sum() / sample_size) * 100.0

    if success_rate < 80.0:
        return None

    # Full column parse
    parsed_full = pd.to_datetime(non_null_series.astype(str), errors="coerce", format="mixed")
    valid_count = int(parsed_full.notna().sum())
    invalid_count = total_non_null - valid_count
    full_success_rate = round((valid_count / total_non_null) * 100.0, 2)

    if full_success_rate < 80.0:
        return None

    # Check if there is an active time component (hours, minutes, or seconds != 0)
    has_time = False
    valid_parsed = parsed_full.dropna()
    if len(valid_parsed) > 0:
        # Check first 500 records for non-midnight times
        check_times = valid_parsed.head(500)
        has_time = any((t.hour != 0 or t.minute != 0 or t.second != 0) for t in check_times)

    detected_type = "datetime" if has_time else "date"
    sample_dates = [str(v)[:19] for v in valid_parsed.head(3)]

    return DateColumnMetadata(
        column=col_name,
        detected_type=detected_type,
        parse_success_percentage=full_success_rate,
        invalid_date_count=invalid_count,
        null_count=int(series.isna().sum()),
        sample_dates=sample_dates,
    )


# =============================================================================
# Column Profiler
# =============================================================================

def profile_column(series: pd.Series, col_name: str, total_rows: int) -> ColumnAnalysis:
    """
    Profiles a single dataset column:
      - Computes nulls, uniqueness, cardinality
      - Performs semantic type inference
      - Detects dates and sensitive fields
      - Computes descriptive statistics for numeric data
    """
    raw_dtype = str(series.dtype)
    null_count = int(series.isna().sum())
    non_null_count = total_rows - null_count
    null_pct = round((null_count / total_rows * 100.0), 2) if total_rows > 0 else 0.0
    missing_cat = classify_missingness(null_pct)

    non_null_series = series.dropna()
    unique_count = int(non_null_series.nunique())
    uniqueness_pct = round((unique_count / non_null_count * 100.0), 2) if non_null_count > 0 else 0.0
    is_unique = (unique_count == non_null_count) and (non_null_count > 0)
    is_constant = (unique_count == 1)
    is_all_null = (non_null_count == 0)

    # Sample values (up to 5 representative non-null values)
    sample_vals = []
    if non_null_count > 0:
        for val in non_null_series.head(5):
            if isinstance(val, (np.integer, int)):
                sample_vals.append(int(val))
            elif isinstance(val, (np.floating, float)):
                sample_vals.append(round(float(val), 4) if not math.isnan(val) else None)
            else:
                sample_vals.append(str(val)[:80])

    # Date / Datetime detection
    date_meta = detect_date_column(series, col_name)

    # Sensitive column detection
    sensitive_meta = detect_sensitive_column(col_name, sample_vals)
    is_sensitive = sensitive_meta is not None

    # Primary key candidate heuristic:
    # 1. Zero nulls
    # 2. 100% uniqueness
    # 3. Name is ID, or ends with ID / _ID / KEY
    col_upper = col_name.strip().upper()
    is_pk_candidate = False
    if null_count == 0 and is_unique and total_rows > 1:
        if col_upper == "ID" or col_upper.endswith("_ID") or "IDENTIFIER" in col_upper:
            is_pk_candidate = True

    # Descriptive statistics for numeric columns
    min_val, max_val, mean_val, median_val, std_val = None, None, None, None, None

    # Infer semantic type
    semantic_type = "unknown"
    if is_all_null:
        semantic_type = "unknown"
    elif date_meta is not None:
        semantic_type = date_meta.detected_type  # "date" or "datetime"
    elif is_pk_candidate or (col_upper == "ID" and uniqueness_pct >= 99.0):
        semantic_type = "identifier"
    elif pd.api.types.is_bool_dtype(series):
        semantic_type = "boolean"
    elif pd.api.types.is_numeric_dtype(series):
        # Numeric calculations
        if non_null_count > 0:
            try:
                min_val = float(non_null_series.min())
                max_val = float(non_null_series.max())
                mean_val = round(float(non_null_series.mean()), 4)
                median_val = round(float(non_null_series.median()), 4)
                std_val = round(float(non_null_series.std()), 4) if non_null_count > 1 else 0.0
            except Exception:
                pass

        # Check if boolean disguised as 0/1
        if unique_count <= 2 and set(non_null_series.unique()).issubset({0, 1, 0.0, 1.0}):
            semantic_type = "boolean"
        # Check if ZIP code
        elif col_upper in ("ZIP", "POSTAL", "POSTAL_CODE"):
            semantic_type = "categorical"
        # Check if all values are whole integers
        elif pd.api.types.is_integer_dtype(series) or (
            np.all(np.mod(non_null_series.values, 1) == 0) if len(non_null_series) > 0 else False
        ):
            semantic_type = "integer"
        else:
            semantic_type = "decimal"
    else:
        # Object / String column
        # Check for boolean strings ('Y'/'N', 'true'/'false', 'T'/'F')
        unique_str_set = {str(x).strip().lower() for x in non_null_series.unique()}
        if unique_count <= 2 and unique_str_set.issubset({"true", "false", "t", "f", "y", "n", "yes", "no"}):
            semantic_type = "boolean"
        # Check for UUID / Identifier columns
        sample_first = str(non_null_series.iloc[0]).strip() if len(non_null_series) > 0 else ""
        looks_like_uuid = bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", sample_first))

        if col_upper in ("PATIENT", "ENCOUNTER", "ORGANIZATION", "PROVIDER", "PAYER", "CODE", "SSN", "PASSPORT", "DRIVERS") or col_upper.endswith("ID") or col_upper.endswith("_ID") or "UUID" in col_upper:
            semantic_type = "identifier"
        elif looks_like_uuid:
            semantic_type = "identifier"
        elif is_unique and uniqueness_pct >= 95.0 and total_rows > 10:
            semantic_type = "identifier"
        elif unique_count <= 50 or (uniqueness_pct < 5.0 and unique_count < 200):
            semantic_type = "categorical"
        else:
            # Check if mixed numeric / text (like observations.VALUE)
            numeric_parsed = pd.to_numeric(non_null_series.head(1000), errors="coerce")
            num_ratio = numeric_parsed.notna().mean()
            if 0.10 <= num_ratio <= 0.90:
                semantic_type = "mixed"
            elif num_ratio > 0.90:
                semantic_type = "numeric"
            else:
                semantic_type = "text"

    return ColumnAnalysis(
        name=col_name,
        pandas_dtype=raw_dtype,
        semantic_type=semantic_type,
        row_count=total_rows,
        non_null_count=non_null_count,
        null_count=null_count,
        null_percentage=null_pct,
        missing_category=missing_cat,
        unique_count=unique_count,
        uniqueness_percentage=uniqueness_pct,
        is_unique=is_unique,
        is_constant=is_constant,
        is_all_null=is_all_null,
        is_primary_key_candidate=is_pk_candidate,
        is_sensitive=is_sensitive,
        sensitive_details=sensitive_meta,
        date_metadata=date_meta,
        min_value=min_val,
        max_value=max_val,
        mean_value=mean_val,
        median_value=median_val,
        std_value=std_val,
        sample_values=sample_vals,
    )


# =============================================================================
# Special Observations Table Analysis
# =============================================================================

def analyze_observations_special(df: pd.DataFrame) -> Optional[ObservationsAnalysis]:
    """
    Performs specialized deep analysis of the clinical observations dataset.

    The observations table contains heterogeneous values in the 'VALUE' column:
      - 92.9% numeric clinical lab measurements (e.g. blood pressure, glucose, height)
      - 7.1% categorical/textual findings (e.g. findings, status, survey responses)
      - Accompanied by UNITS and TYPE columns
    """
    cols_upper = {c.upper(): c for c in df.columns}
    if "VALUE" not in cols_upper:
        return None

    val_col = cols_upper["VALUE"]
    total_records = len(df)
    val_series = df[val_col]
    null_count = int(val_series.isna().sum())
    null_pct = round((null_count / total_records * 100.0), 2) if total_records > 0 else 0.0
    non_null_val = val_series.dropna().astype(str)

    # Numeric vs Text breakdown
    numeric_parsed = pd.to_numeric(non_null_val, errors="coerce")
    numeric_count = int(numeric_parsed.notna().sum())
    text_count = int(numeric_parsed.isna().sum())

    total_non_null = len(non_null_val)
    num_pct = round((numeric_count / total_non_null * 100.0), 2) if total_non_null > 0 else 0.0
    text_pct = round((text_count / total_non_null * 100.0), 2) if total_non_null > 0 else 0.0
    unique_count = int(non_null_val.nunique())

    # TYPE distribution
    type_dist = {}
    if "TYPE" in cols_upper:
        type_col = cols_upper["TYPE"]
        type_dist = {str(k): int(v) for k, v in df[type_col].value_counts(dropna=False).items()}

    # Top Units distribution (top 12)
    units_dist = {}
    if "UNITS" in cols_upper:
        units_col = cols_upper["UNITS"]
        units_dist = {str(k): int(v) for k, v in df[units_col].value_counts(dropna=False).head(12).items()}

    # Top clinical observation descriptions (top 10)
    top_obs = {}
    if "DESCRIPTION" in cols_upper:
        desc_col = cols_upper["DESCRIPTION"]
        top_obs = {str(k): int(v) for k, v in df[desc_col].value_counts(dropna=False).head(10).items()}

    return ObservationsAnalysis(
        total_records=total_records,
        numeric_value_count=numeric_count,
        numeric_value_percentage=num_pct,
        text_value_count=text_count,
        text_value_percentage=text_pct,
        null_value_count=null_count,
        null_value_percentage=null_pct,
        unique_value_count=unique_count,
        type_distribution=type_dist,
        units_distribution=units_dist,
        top_observations=top_obs,
    )
