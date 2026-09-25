"""
app/ingestion/metadata.py
==========================
Dataset Metadata Extraction

WHY THIS EXISTS:
    After we have a pandas DataFrame, we need to describe it:
      - How many rows and columns?
      - What are the column names?
      - What data type did pandas infer for each column?
      - How much memory does this dataset use?

    This module is pure Python/pandas — no FastAPI, no SQLAlchemy.
    It takes a DataFrame and returns a DatasetMetadata Pydantic model.

WHY SEPARATE FROM quality_checker.py?
    metadata.py answers: "What IS this dataset structurally?"
    quality_checker.py answers: "How CLEAN is this dataset?"

    Keeping them separate means:
      - Each module has one clear job
      - You can call either independently in future phases
      - Easier to test in isolation

DATA TYPE REPORTING:
    We report pandas dtype names as strings (e.g., "int64", "float64", "object").
    "object" in pandas usually means string/text, but can also mean mixed types.
    Phase 3+ will do deeper type inference and clinical schema mapping.

NUMERIC STATISTICS:
    Per-column min/max/mean/median are computed only for numeric columns.
    This uses pandas' built-in .describe() which is highly optimized.
    For non-numeric columns, these fields are None.
"""

import pandas as pd
import numpy as np

from app.schemas.ingestion import DatasetMetadata, ColumnMetadata
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Main metadata extraction function
# =============================================================================

def extract_metadata(
    df: pd.DataFrame,
    original_filename: str,
    saved_filename: str,
    file_type: str,
) -> DatasetMetadata:
    """
    Extract structural metadata from a pandas DataFrame.

    Args:
        df:                The DataFrame loaded from the uploaded file
        original_filename: The name the user gave the file (for display)
        saved_filename:    The safe UUID-based name stored on disk
        file_type:         "csv" or "xlsx"

    Returns:
        DatasetMetadata Pydantic model ready to include in the API response.
    """
    logger.debug(f"Extracting metadata | filename='{original_filename}' | shape={df.shape}")

    # ── Basic dimensions ──────────────────────────────────────────────────────
    row_count = len(df)
    column_count = len(df.columns)
    column_names = df.columns.tolist()

    # ── Data types ────────────────────────────────────────────────────────────
    # Convert pandas dtype objects to plain strings for JSON serialization
    # Example: dtype('int64') → "int64"
    data_types = {col: str(df[col].dtype) for col in df.columns}

    # ── Memory usage ─────────────────────────────────────────────────────────
    # deep=True includes the memory used by object (string) columns
    memory_usage_bytes = int(df.memory_usage(deep=True).sum())

    # ── Per-column metadata ───────────────────────────────────────────────────
    columns_meta = [_extract_column_metadata(df, col) for col in df.columns]

    logger.info(
        f"Metadata extracted | rows={row_count} | cols={column_count} | "
        f"memory={memory_usage_bytes / 1024:.1f} KB"
    )

    return DatasetMetadata(
        original_filename=original_filename,
        saved_filename=saved_filename,
        file_type=file_type,
        row_count=row_count,
        column_count=column_count,
        column_names=column_names,
        data_types=data_types,
        memory_usage_bytes=memory_usage_bytes,
        columns=columns_meta,
    )


# =============================================================================
# Per-column metadata extraction
# =============================================================================

def _extract_column_metadata(df: pd.DataFrame, col_name: str) -> ColumnMetadata:
    """
    Extract metadata for a single column.

    Args:
        df:       The full DataFrame
        col_name: Name of the column to analyze

    Returns:
        ColumnMetadata with type, null counts, and optional numeric stats.
    """
    series = df[col_name]
    total_rows = len(series)

    # ── Null counts ───────────────────────────────────────────────────────────
    null_count = int(series.isna().sum())
    non_null_count = total_rows - null_count
    null_percentage = round((null_count / total_rows * 100) if total_rows > 0 else 0.0, 2)

    # ── Unique value count ────────────────────────────────────────────────────
    # nunique() counts distinct non-null values
    unique_count = int(series.nunique())

    # ── Flags ─────────────────────────────────────────────────────────────────
    is_all_null = null_count == total_rows
    # A column is "constant" if all non-null values are the same (1 unique value)
    # We ignore null-only columns from the constant check
    is_constant = (not is_all_null) and (unique_count == 1)

    # ── Numeric statistics ────────────────────────────────────────────────────
    min_val = max_val = mean_val = median_val = None

    # pd.api.types.is_numeric_dtype handles int64, float64, etc.
    if pd.api.types.is_numeric_dtype(series) and not is_all_null:
        numeric_series = series.dropna()  # Exclude NaN from stats
        if len(numeric_series) > 0:
            min_val = _safe_float(numeric_series.min())
            max_val = _safe_float(numeric_series.max())
            mean_val = _safe_float(numeric_series.mean())
            median_val = _safe_float(numeric_series.median())

    return ColumnMetadata(
        name=col_name,
        dtype=str(series.dtype),
        non_null_count=non_null_count,
        null_count=null_count,
        null_percentage=null_percentage,
        unique_count=unique_count,
        is_constant=is_constant,
        is_all_null=is_all_null,
        min_value=min_val,
        max_value=max_val,
        mean_value=mean_val,
        median_value=median_val,
    )


# =============================================================================
# Helper
# =============================================================================

def _safe_float(value) -> float | None:
    """
    Convert a numpy numeric value to a Python float safely.

    WHY THIS?
        numpy types like np.float64 are NOT JSON-serializable by default.
        Pydantic handles this, but being explicit prevents edge cases.
        Also handles numpy infinity and NaN by returning None.

    Args:
        value: A numeric value (numpy or Python)

    Returns:
        Python float, or None if the value is NaN/infinite.
    """
    try:
        f = float(value)
        # Return None for NaN or infinite — they are not valid JSON numbers
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, 6)
    except (TypeError, ValueError):
        return None
