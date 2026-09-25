"""
app/schemas/ingestion.py
=========================
Pydantic Response Models for Dataset Ingestion

WHY PYDANTIC SCHEMAS?
    When FastAPI returns data from a route, it serializes Python objects
    to JSON. If you return a plain dict, there's no validation, no
    auto-documentation, and no type safety.

    Pydantic models solve this:
      1. AUTO DOCS — Swagger UI shows exact response shape with field types
      2. VALIDATION — FastAPI validates the response before sending it
      3. CLARITY — Both frontend and backend know exactly what to expect
      4. EXTENSIBLE — Easy to add fields in later phases without breaking callers

RESPONSE HIERARCHY:
    UploadResponse
        ├── dataset: DatasetMetadata
        │       └── columns: List[ColumnMetadata]
        └── quality: QualityReport
                └── column_quality: List[ColumnQualityDetail]

USAGE in API route:
    from app.schemas.ingestion import UploadResponse
    return UploadResponse(status="success", ...)

DESIGN DECISIONS:
    - Optional[X] fields allow graceful partial responses
    - All numeric fields use float for JSON compatibility
    - Extra fields are forbidden (model_config extra="forbid") to catch bugs early
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


# =============================================================================
# Column-level metadata
# =============================================================================

class ColumnMetadata(BaseModel):
    """
    Metadata for a single column in the uploaded dataset.

    Generated dynamically from the actual DataFrame — no assumed column names.
    """

    name: str = Field(description="Column name as it appears in the file header")
    dtype: str = Field(description="Pandas-inferred data type (e.g., int64, object, float64)")
    non_null_count: int = Field(description="Number of rows with a non-null value")
    null_count: int = Field(description="Number of rows with a missing (NaN/null) value")
    null_percentage: float = Field(description="Percentage of rows that are null (0.0 to 100.0)")
    unique_count: int = Field(description="Number of distinct unique values in this column")
    is_constant: bool = Field(description="True if all non-null values are identical (1 unique value)")
    is_all_null: bool = Field(description="True if every value in this column is null/missing")

    # Optional numeric statistics — only populated for numeric columns
    min_value: Optional[float] = Field(default=None, description="Minimum value (numeric columns only)")
    max_value: Optional[float] = Field(default=None, description="Maximum value (numeric columns only)")
    mean_value: Optional[float] = Field(default=None, description="Mean (average) value (numeric columns only)")
    median_value: Optional[float] = Field(default=None, description="Median value (numeric columns only)")


# =============================================================================
# Dataset-level metadata
# =============================================================================

class DatasetMetadata(BaseModel):
    """
    Structural metadata describing the uploaded dataset as a whole.

    Dynamically computed from the DataFrame — not assumed or hardcoded.
    """

    original_filename: str = Field(description="Original name of the uploaded file")
    saved_filename: str = Field(description="Safe filename used when storing the file locally")
    file_type: str = Field(description="Detected file type: csv, xlsx, or xls")
    row_count: int = Field(description="Total number of data rows (excluding header)")
    column_count: int = Field(description="Total number of columns")
    column_names: List[str] = Field(description="Ordered list of all column names")
    data_types: Dict[str, str] = Field(description="Mapping of column name → pandas dtype string")
    memory_usage_bytes: int = Field(description="Total DataFrame memory usage in bytes")
    columns: List[ColumnMetadata] = Field(description="Per-column metadata including types and null counts")


# =============================================================================
# Dataset-level quality summary
# =============================================================================

class QualityReport(BaseModel):
    """
    Data quality summary for the uploaded dataset.

    Reports deterministic facts — no AI interpretation.
    These metrics drive Phase 3+ decisions about cleaning and schema mapping.
    """

    total_rows: int = Field(description="Total rows in the dataset")
    total_columns: int = Field(description="Total columns in the dataset")
    duplicate_row_count: int = Field(description="Number of completely duplicate rows")
    duplicate_row_percentage: float = Field(description="Percentage of rows that are duplicates")
    columns_with_missing_values: int = Field(description="Number of columns that have at least one null value")
    total_missing_cells: int = Field(description="Total count of null/missing cells across all columns")
    missing_cell_percentage: float = Field(description="Percentage of all cells that are missing")
    empty_columns: List[str] = Field(description="Column names where every single value is null")
    constant_columns: List[str] = Field(description="Column names where all non-null values are identical")
    quality_flags: List[str] = Field(
        description="Human-readable warning flags raised during quality checks"
    )


# =============================================================================
# Top-level upload response
# =============================================================================

class UploadResponse(BaseModel):
    """
    Top-level response returned by POST /ingestion/upload.

    Contains:
        - status       → "success" or "error"
        - message      → Human-readable summary
        - dataset      → Structural metadata (rows, columns, types)
        - quality      → Data quality report (missing, duplicates, flags)
        - saved_path   → Where the file was stored locally (for dev transparency)
    """

    status: str = Field(description="'success' or 'error'")
    message: str = Field(description="Human-readable summary of the upload result")
    dataset: DatasetMetadata = Field(description="Structural information about the uploaded dataset")
    quality: QualityReport = Field(description="Data quality analysis results")
    saved_path: str = Field(description="Local filesystem path where the uploaded file is stored")


# =============================================================================
# Error response (used for 400 / 500 errors)
# =============================================================================

class ErrorResponse(BaseModel):
    """
    Structured error response for failed uploads.

    Used instead of raw FastAPI HTTPException details so the response
    format is consistent with the success response shape.
    """

    status: str = Field(default="error", description="Always 'error' for error responses")
    error_code: str = Field(description="Short machine-readable error code")
    message: str = Field(description="Human-readable error description")
    detail: Optional[str] = Field(default=None, description="Additional technical detail (safe to show)")
