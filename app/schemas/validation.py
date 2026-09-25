"""
app/schemas/validation.py
=========================
Pydantic Schemas for Phase 3 — Data Quality & Schema / Type Validation

WHY THIS FILE EXISTS:
    Phase 3 introduces comprehensive data quality assessment, semantic type
    inference, primary/foreign key candidate discovery, sensitive data
    detection, and relational analysis across multi-table clinical datasets.

    These schemas define the structured contracts for:
      - Per-column schema and quality profiling
      - Date/datetime analysis details
      - Observations heterogeneous value breakdown
      - Primary and Foreign key relationship evidence
      - Dataset-level and multi-dataset overall quality summaries
      - Request/Response models for POST /ingestion/analyze
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


# =============================================================================
# Date Column Metadata
# =============================================================================

class DateColumnMetadata(BaseModel):
    """Details for a column identified as containing date or datetime values."""
    column: str = Field(..., description="Column name")
    detected_type: str = Field(..., description="'date' or 'datetime'")
    parse_success_percentage: float = Field(..., description="Percentage of non-null values successfully parsed as dates")
    invalid_date_count: int = Field(0, description="Count of non-null values that failed date parsing")
    null_count: int = Field(..., description="Count of null/empty values in this column")
    sample_dates: List[str] = Field(default_factory=list, description="Sample of parsed ISO date strings")


# =============================================================================
# Sensitive Column Metadata
# =============================================================================

class SensitiveColumnMetadata(BaseModel):
    """Identifies sensitive or direct-identifier fields requiring HIPAA/privacy safeguards."""
    column: str = Field(..., description="Column name")
    category: str = Field(..., description="Sensitivity category, e.g. Direct Identifier, Demographics, Geolocation")
    reason: str = Field(..., description="Explanation of why this field is considered sensitive")
    recommendation: str = Field(..., description="Recommended handling in analytics schema (e.g. hash, mask, redact)")


# =============================================================================
# Column Analysis Schema
# =============================================================================

class ColumnAnalysis(BaseModel):
    """Complete profiling and semantic analysis for a single column."""
    name: str = Field(..., description="Column name")
    pandas_dtype: str = Field(..., description="Native pandas dtype (e.g. int64, float64, object)")
    semantic_type: str = Field(
        ...,
        description="Inferred semantic type: identifier, integer, decimal, categorical, text, date, datetime, boolean, numeric, mixed, unknown"
    )
    row_count: int = Field(..., description="Total rows in dataset")
    non_null_count: int = Field(..., description="Count of non-null values")
    null_count: int = Field(..., description="Count of null values")
    null_percentage: float = Field(..., description="Percentage of null values (0.0 to 100.0)")
    missing_category: str = Field(..., description="Missingness tier: '0%', '<5%', '5-20%', '20-50%', '>50%'")
    unique_count: int = Field(..., description="Count of distinct non-null values")
    uniqueness_percentage: float = Field(..., description="Distinct count as percentage of non-null rows")
    is_unique: bool = Field(..., description="True if every row has a distinct non-null value")
    is_constant: bool = Field(..., description="True if column contains only 1 distinct value")
    is_all_null: bool = Field(..., description="True if column is 100% null")
    is_primary_key_candidate: bool = Field(False, description="True if column meets PK candidate criteria")
    is_sensitive: bool = Field(False, description="True if column contains direct identifiers or sensitive data")
    sensitive_details: Optional[SensitiveColumnMetadata] = Field(None, description="Details if marked sensitive")
    date_metadata: Optional[DateColumnMetadata] = Field(None, description="Details if column contains dates")
    min_value: Optional[Any] = Field(None, description="Minimum value for numeric/date columns")
    max_value: Optional[Any] = Field(None, description="Maximum value for numeric/date columns")
    mean_value: Optional[float] = Field(None, description="Mean for numeric columns")
    median_value: Optional[float] = Field(None, description="Median for numeric columns")
    std_value: Optional[float] = Field(None, description="Standard deviation for numeric columns")
    sample_values: List[Any] = Field(default_factory=list, description="Up to 5 representative sample values")


# =============================================================================
# Primary Key Candidate Schema
# =============================================================================

class PrimaryKeyCandidate(BaseModel):
    """Evidence evaluating a column as a primary key candidate."""
    column: str = Field(..., description="Candidate column name")
    is_unique: bool = Field(..., description="Whether all values are unique")
    null_count: int = Field(..., description="Number of nulls in column")
    uniqueness_percentage: float = Field(..., description="Uniqueness percentage")
    data_type: str = Field(..., description="Inferred semantic data type")
    confidence: str = Field(..., description="'HIGH', 'MEDIUM', or 'LOW'")
    notes: str = Field(..., description="Evidence rationale")


# =============================================================================
# Foreign Key Relationship Schema
# =============================================================================

class RelationshipAnalysis(BaseModel):
    """Analysis of relational foreign key candidate between parent and child tables."""
    parent_table: str = Field(..., description="Parent table name (e.g. patients)")
    parent_column: str = Field(..., description="Parent primary key column (e.g. ID)")
    child_table: str = Field(..., description="Child table name (e.g. encounters)")
    child_column: str = Field(..., description="Child foreign key column (e.g. PATIENT)")
    child_row_count: int = Field(..., description="Total rows in child table")
    child_null_count: int = Field(..., description="Null count in child FK column")
    is_nullable: bool = Field(..., description="True if child FK contains nulls (e.g. observations without encounter)")
    matching_reference_count: int = Field(..., description="Count of non-null child rows matching parent key")
    unmatched_reference_count: int = Field(..., description="Count of child rows that do NOT match any parent key")
    match_percentage: float = Field(..., description="Match rate: matching / (child_rows - child_nulls) * 100")
    status: str = Field(
        ...,
        description="'VALID' (100% match, no nulls), 'VALID_WITH_NULLS' (100% of non-nulls match), 'VIOLATION' (unmatched refs), 'CANDIDATE'"
    )
    notes: str = Field(..., description="Detailed clinical and technical relationship assessment")


# =============================================================================
# Special Observations Analysis Schema
# =============================================================================

class ObservationsAnalysis(BaseModel):
    """Specialized analysis for heterogeneous clinical observations table."""
    total_records: int = Field(..., description="Total observation rows")
    numeric_value_count: int = Field(..., description="Count of numeric measurement values in VALUE")
    numeric_value_percentage: float = Field(..., description="Percentage of numeric values")
    text_value_count: int = Field(..., description="Count of textual/categorical values in VALUE")
    text_value_percentage: float = Field(..., description="Percentage of text values")
    null_value_count: int = Field(..., description="Null count in VALUE")
    null_value_percentage: float = Field(..., description="Null percentage in VALUE")
    unique_value_count: int = Field(..., description="Distinct count of values")
    type_distribution: Dict[str, int] = Field(default_factory=dict, description="Distribution of the TYPE column")
    units_distribution: Dict[str, int] = Field(default_factory=dict, description="Top measurement units in UNITS column")
    top_observations: Dict[str, int] = Field(default_factory=dict, description="Top clinical observation descriptions")


# =============================================================================
# Dataset-Level Analysis Schema
# =============================================================================

class DatasetAnalysis(BaseModel):
    """Comprehensive schema and data quality analysis for an individual dataset file."""
    filename: str = Field(..., description="Filename of the dataset")
    dataset_name: str = Field(..., description="Logical dataset name (e.g. patients, encounters)")
    file_path: str = Field(..., description="Path to the file on disk")
    file_type: str = Field(..., description="'csv' or 'xlsx'")
    row_count: int = Field(..., description="Total row count")
    column_count: int = Field(..., description="Total column count")
    column_names: List[str] = Field(..., description="List of column names in order")
    columns: List[ColumnAnalysis] = Field(..., description="Per-column schema and quality profiling")
    duplicate_row_count: int = Field(..., description="Count of duplicate rows")
    duplicate_row_percentage: float = Field(..., description="Duplicate rows percentage")
    empty_columns: List[str] = Field(default_factory=list, description="List of 100% empty columns")
    constant_columns: List[str] = Field(default_factory=list, description="List of single-value constant columns")
    date_columns: List[str] = Field(default_factory=list, description="Columns identified as dates/datetimes")
    primary_key_candidates: List[PrimaryKeyCandidate] = Field(default_factory=list, description="Candidate PK columns")
    potential_sensitive_columns: List[SensitiveColumnMetadata] = Field(default_factory=list, description="Direct identifiers and sensitive fields")
    observations_analysis: Optional[ObservationsAnalysis] = Field(None, description="Special observations metrics if applicable")
    quality_flags: List[str] = Field(default_factory=list, description="Human-readable quality warning flags")


# =============================================================================
# Overall Cross-Dataset Quality Summary Schema
# =============================================================================

class OverallQuality(BaseModel):
    """Global quality and relational integrity summary across all analyzed datasets."""
    total_datasets: int = Field(..., description="Number of datasets analyzed")
    total_rows: int = Field(..., description="Total rows across all datasets")
    total_columns: int = Field(..., description="Total columns across all datasets")
    total_duplicate_rows: int = Field(..., description="Total duplicate rows across all datasets")
    total_missing_cells: int = Field(..., description="Total missing cells across all datasets")
    relationships_evaluated: int = Field(..., description="Total foreign key relationships checked")
    relationships_valid: int = Field(..., description="Valid relational relationships count")
    relationships_with_violations: int = Field(..., description="Relationships with orphaned records")
    total_sensitive_columns: int = Field(..., description="Count of sensitive/direct-identifier columns across all tables")
    quality_flags: List[str] = Field(default_factory=list, description="Global quality flags and warnings")


# =============================================================================
# API Request & Response Schemas for POST /ingestion/analyze
# =============================================================================

class AnalyzeRequest(BaseModel):
    """
    Request payload for POST /ingestion/analyze.

    Can specify:
      - `directory_path`: Directory containing CSV/XLSX files
      - `file_paths`: Explicit list of full file paths
      - `filenames`: Filenames to look for in the default dataset directory or uploads directory
      - If all are omitted/null: Automatically analyzes the default dataset directory.
    """
    directory_path: Optional[str] = Field(
        None,
        description="Path to directory containing dataset files (e.g. 'C:/.../Dataset/CSV Dataset')"
    )
    file_paths: Optional[List[str]] = Field(
        None,
        description="List of specific absolute or relative file paths to analyze"
    )
    filenames: Optional[List[str]] = Field(
        None,
        description="List of filenames to locate in the dataset or upload directory"
    )


class AnalyzeResponse(BaseModel):
    """Response payload returned by POST /ingestion/analyze."""
    status: str = Field("success", description="'success' or 'error'")
    message: str = Field(..., description="Human-readable summary message")
    datasets: List[DatasetAnalysis] = Field(..., description="Analysis report for each dataset")
    relationships: List[RelationshipAnalysis] = Field(default_factory=list, description="Relational integrity analysis")
    overall_quality: OverallQuality = Field(..., description="Summary metrics across the entire dataset group")
