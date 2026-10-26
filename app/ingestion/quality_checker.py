"""
app/ingestion/quality_checker.py
==================================
Initial Data Quality Analysis

WHY THIS EXISTS:
    After reading a dataset, we need to assess its quality BEFORE deciding
    what to do with it. This module computes deterministic quality metrics:

      - Duplicate rows      → Exact row duplicates reduce analysis accuracy
      - Missing values      → Columns with nulls may need imputation or exclusion
      - Empty columns       → Columns with 100% nulls are unusable
      - Constant columns    → Columns with 1 unique value add no analytical value
      - Quality flags       → Human-readable warnings summarizing key issues

WHAT THIS IS NOT:
    - This is NOT clinical interpretation (no "this gender column looks odd")
    - This is NOT imputation or cleaning (we don't modify the data)
    - This is NOT schema mapping (no assumed column semantics)

    All of those belong to later phases.

QUALITY FLAGS:
    Flags are plain English strings that summarize important findings.
    Examples:
      - "WARNING: 4 duplicate rows detected (0.08%)"
      - "WARNING: Column 'diagnosis_code' has 15.3% missing values"
      - "INFO: 2 constant columns detected — may be safe to exclude"

    These flags will eventually feed into:
      - Phase 5: LLM narrative generation
      - Phase 7: LangGraph analysis plan
"""

from typing import List

import pandas as pd

from app.schemas.ingestion import QualityReport
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# =============================================================================
# Thresholds for quality flags (could be moved to config later)
# =============================================================================

# A column is flagged for "high missing" if its null percentage exceeds this
HIGH_MISSING_THRESHOLD_PCT = 20.0

# Duplicate rows above this percentage trigger a high-severity warning
HIGH_DUPLICATE_THRESHOLD_PCT = 5.0


# =============================================================================
# Main quality check function
# =============================================================================

def check_quality(df: pd.DataFrame, filename: str) -> QualityReport:
    """
    Perform initial data quality analysis on a DataFrame.

    Args:
        df:       The pandas DataFrame loaded from the uploaded file
        filename: Original filename (used in log messages and flags)

    Returns:
        QualityReport Pydantic model ready to include in the API response.
    """
    logger.debug(f"Running quality checks | filename='{filename}' | shape={df.shape}")

    total_rows = len(df)
    total_columns = len(df.columns)
    total_cells = total_rows * total_columns

    # ── 1. Duplicate rows ─────────────────────────────────────────────────────
    duplicate_row_count, duplicate_row_percentage = _check_duplicates(df, total_rows)

    # ── 2. Missing values ─────────────────────────────────────────────────────
    (
        columns_with_missing,
        total_missing_cells,
        missing_cell_percentage,
    ) = _check_missing_values(df, total_cells)

    # Empty and whitespace-only strings are distinct from null/missing values.
    blank_counts = {
        column: int(
            df[column]
            .map(lambda value: isinstance(value, str) and not value.strip())
            .sum()
        )
        for column in df.columns
    }

    # ── 3. Empty columns ──────────────────────────────────────────────────────
    empty_columns = _find_empty_columns(df)

    # ── 4. Constant columns ───────────────────────────────────────────────────
    constant_columns = _find_constant_columns(df)

    # ── 5. Generate quality flags ─────────────────────────────────────────────
    flags = _generate_quality_flags(
        filename=filename,
        total_rows=total_rows,
        duplicate_row_count=duplicate_row_count,
        duplicate_row_percentage=duplicate_row_percentage,
        columns_with_missing=columns_with_missing,
        total_missing_cells=total_missing_cells,
        missing_cell_percentage=missing_cell_percentage,
        empty_columns=empty_columns,
        constant_columns=constant_columns,
        df=df,
    )

    for column, count in blank_counts.items():
        if count:
            flags.append(
                f"WARNING: Column {column!r} contains {count} blank text values, "
                "distinct from SQL NULL; review the dataset definition."
            )

    logger.info(
        f"Quality check complete | filename='{filename}' | "
        f"duplicates={duplicate_row_count} | "
        f"missing_cells={total_missing_cells} | "
        f"empty_cols={len(empty_columns)} | "
        f"constant_cols={len(constant_columns)} | "
        f"flags={len(flags)}"
    )

    return QualityReport(
        total_rows=total_rows,
        total_columns=total_columns,
        duplicate_row_count=duplicate_row_count,
        duplicate_row_percentage=duplicate_row_percentage,
        columns_with_missing_values=columns_with_missing,
        total_missing_cells=total_missing_cells,
        missing_cell_percentage=missing_cell_percentage,
        empty_columns=empty_columns,
        constant_columns=constant_columns,
        quality_flags=flags,
    )


# =============================================================================
# Individual check functions
# =============================================================================

def _check_duplicates(df: pd.DataFrame, total_rows: int) -> tuple[int, float]:
    """
    Count fully duplicate rows (every column value is identical).

    HOW IT WORKS:
        df.duplicated() returns a boolean Series: True for each row that
        is an exact duplicate of a row appearing earlier.
        keep='first' means the first occurrence is NOT marked as duplicate.

    Returns:
        (duplicate_count, duplicate_percentage)
    """
    if total_rows == 0:
        return 0, 0.0

    duplicate_mask = df.duplicated(keep="first")
    duplicate_count = int(duplicate_mask.sum())
    duplicate_pct = round((duplicate_count / total_rows) * 100, 2)

    return duplicate_count, duplicate_pct


def _check_missing_values(
    df: pd.DataFrame, total_cells: int
) -> tuple[int, int, float]:
    """
    Compute missing value statistics across all columns.

    Returns:
        (columns_with_missing_count, total_missing_cells, missing_cell_percentage)
    """
    # Count missing values per column
    null_counts_per_col = df.isna().sum()

    # Number of columns that have AT LEAST one null
    columns_with_missing = int((null_counts_per_col > 0).sum())

    # Total null cells across the entire DataFrame
    total_missing = int(null_counts_per_col.sum())

    # Percentage of all cells that are null
    missing_pct = round((total_missing / total_cells * 100) if total_cells > 0 else 0.0, 2)

    return columns_with_missing, total_missing, missing_pct


def _find_empty_columns(df: pd.DataFrame) -> List[str]:
    """
    Find columns where every single value is null/NaN.

    These columns contribute nothing to analysis and should be
    flagged for removal or investigation.

    Returns:
        List of column names that are 100% null.
    """
    return [col for col in df.columns if df[col].isna().all()]


def _find_constant_columns(df: pd.DataFrame) -> List[str]:
    """
    Find columns where all non-null values are identical.

    A constant column (e.g., "hospital_name" = "General Hospital" for all rows)
    provides no discriminatory power for analysis.

    WHY nunique(dropna=True)?
        - We use dropna=True (default) to ignore null values.
        - A column with only NaN would show nunique=0, handled by _find_empty_columns.
        - A column with 1 unique non-null value (regardless of nulls) is constant.

    Returns:
        List of column names that are constant (1 unique non-null value).
    """
    constant = []
    for col in df.columns:
        non_null_series = df[col].dropna()
        if len(non_null_series) > 0 and non_null_series.nunique() == 1:
            constant.append(col)
    return constant


# =============================================================================
# Quality flag generator
# =============================================================================

def _generate_quality_flags(
    filename: str,
    total_rows: int,
    duplicate_row_count: int,
    duplicate_row_percentage: float,
    columns_with_missing: int,
    total_missing_cells: int,
    missing_cell_percentage: float,
    empty_columns: List[str],
    constant_columns: List[str],
    df: pd.DataFrame,
) -> List[str]:
    """
    Generate human-readable quality warning flags.

    Flags are ordered by severity:
      - CRITICAL → data is essentially unusable
      - WARNING  → significant issues that need attention
      - INFO     → noteworthy but may be acceptable

    These flags will later be used by:
      - The frontend dashboard to show data quality alerts
      - Phase 5 LLM narrative generation
      - Phase 7 LangGraph analysis plan decisions

    Returns:
        List of flag strings, ordered from most to least severe.
    """
    flags: List[str] = []

    # ── Dataset size flags ─────────────────────────────────────────────────────
    if total_rows == 0:
        flags.append("CRITICAL: Dataset has no data rows.")
        return flags  # No point checking further

    if total_rows < 10:
        flags.append(
            f"WARNING: Dataset has only {total_rows} rows. "
            "Statistical results may not be reliable."
        )

    # ── Duplicate row flags ────────────────────────────────────────────────────
    if duplicate_row_count > 0:
        severity = "WARNING" if duplicate_row_percentage >= HIGH_DUPLICATE_THRESHOLD_PCT else "INFO"
        flags.append(
            f"{severity}: {duplicate_row_count} duplicate row(s) detected "
            f"({duplicate_row_percentage}% of total rows)."
        )

    # ── Missing value flags ────────────────────────────────────────────────────
    if missing_cell_percentage > HIGH_MISSING_THRESHOLD_PCT:
        flags.append(
            f"WARNING: {missing_cell_percentage}% of all cells are missing "
            f"({total_missing_cells} cells across {columns_with_missing} column(s))."
        )
    elif total_missing_cells > 0:
        flags.append(
            f"INFO: {total_missing_cells} missing cell(s) detected "
            f"across {columns_with_missing} column(s) ({missing_cell_percentage}% of all cells)."
        )

    # Per-column high-missing flags (top offenders)
    null_pct_series = (df.isna().sum() / len(df) * 100).round(2)
    high_missing_cols = null_pct_series[null_pct_series > HIGH_MISSING_THRESHOLD_PCT]
    for col, pct in high_missing_cols.items():
        flags.append(
            f"WARNING: Column '{col}' has {pct}% missing values."
        )

    # ── Empty column flags ─────────────────────────────────────────────────────
    if empty_columns:
        col_list = ", ".join(f"'{c}'" for c in empty_columns)
        flags.append(
            f"WARNING: {len(empty_columns)} column(s) are completely empty (all values null): "
            f"{col_list}."
        )

    # ── Constant column flags ──────────────────────────────────────────────────
    if constant_columns:
        col_list = ", ".join(f"'{c}'" for c in constant_columns)
        flags.append(
            f"INFO: {len(constant_columns)} column(s) contain only one unique value "
            f"(constant, may be safe to exclude): {col_list}."
        )

    # ── Clean dataset flag ─────────────────────────────────────────────────────
    if not flags:
        flags.append(
            "INFO: No major quality issues detected. "
            "Dataset appears clean based on initial inspection."
        )

    return flags
