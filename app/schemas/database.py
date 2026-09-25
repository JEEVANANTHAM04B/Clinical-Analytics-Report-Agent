"""
app/schemas/database.py
========================
Pydantic Schemas for Phase 5 — MySQL Clinical Data Layer

WHY THIS FILE EXISTS:
    Defines request and response contracts for:
      - Clinical dataset loading into MySQL (POST /database/load)
      - Dataset version tracking (GET /database/versions)
      - Column schema and semantic profiling queries
      - Approved relationship persistence
      - Platform audit logging
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Dataset Load Schemas
# =============================================================================

class DatasetLoadRequest(BaseModel):
    """
    Request payload to load a validated clinical dataset into MySQL.
    
    Accepts either a simple filename (e.g. 'sample_clinical_data.csv' or 'analytics_patients.csv')
    or an explicit file path within the allowed directories.
    """
    filename: Optional[str] = Field(
        None,
        description="Filename of the validated dataset in data/uploads/ or data/sample/ (e.g. 'sample_clinical_data.csv').",
        examples=["sample_clinical_data.csv"]
    )
    file_path: Optional[str] = Field(
        None,
        description="Explicit relative or absolute path to a validated CSV/XLSX file within allowed directories.",
    )
    table_name: Optional[str] = Field(
        None,
        description="Optional custom MySQL table name. If omitted, safe table name is derived from filename.",
    )
    if_exists: Literal["fail", "replace", "append"] = Field(
        default="fail",
        description="Behavior if table already exists in MySQL: 'fail' (default), 'replace', or 'append'.",
    )


class DatasetLoadResponse(BaseModel):
    """
    Response returned when a clinical dataset is successfully loaded into MySQL.
    """
    status: str = Field("success", description="Status string: 'success' or 'error'")
    message: str = Field(..., description="Human-readable outcome message")
    table_name: str = Field(..., description="Sanitized MySQL clinical table name")
    rows_loaded: int = Field(..., description="Number of rows loaded into MySQL")
    columns_loaded: int = Field(..., description="Number of columns created in MySQL")
    dataset_version_id: Optional[int] = Field(None, description="Metadata ID in dataset_versions")
    version_number: Optional[int] = Field(None, description="Sequential version number of the dataset")
    loaded_at: Optional[datetime] = Field(None, description="UTC timestamp of the load")


# =============================================================================
# Dataset Version Schemas
# =============================================================================

class DatasetVersionOut(BaseModel):
    """Metadata schema representing a single loaded dataset version."""
    id: int
    dataset_name: str
    source_filename: str
    source_file_type: str
    version_number: int
    row_count: int
    column_count: int
    status: str
    loaded_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ListVersionsResponse(BaseModel):
    """Response containing a list of dataset versions."""
    status: str = "success"
    count: int
    versions: List[DatasetVersionOut]


# =============================================================================
# Dataset Column Metadata Schemas
# =============================================================================

class DatasetColumnOut(BaseModel):
    """Metadata schema for a column stored in dataset_columns."""
    id: int
    dataset_version_id: int
    dataset_name: str
    column_name: str
    data_type: str
    semantic_type: str
    nullable: bool
    missing_count: int
    missing_percentage: float
    is_primary_key_candidate: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ListColumnsResponse(BaseModel):
    """Response containing column metadata for a dataset version."""
    status: str = "success"
    dataset_version_id: int
    count: int
    columns: List[DatasetColumnOut]


# =============================================================================
# Approved Relationship Persistence Schemas
# =============================================================================

class ApprovedRelationshipOut(BaseModel):
    """Schema for an approved or rejected relationship persisted in MySQL."""
    id: int
    parent_table: str
    parent_column: str
    child_table: str
    child_column: str
    status: str
    analyst_note: Optional[str] = None
    was_edited: bool = False
    original_candidate: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Audit Log Schemas
# =============================================================================

class AuditLogOut(BaseModel):
    """Schema for a platform audit log record."""
    id: int
    action: str
    entity_type: str
    entity_name: str
    status: str
    message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ListAuditLogsResponse(BaseModel):
    """Response containing a list of audit logs."""
    status: str = "success"
    count: int
    logs: List[AuditLogOut]
