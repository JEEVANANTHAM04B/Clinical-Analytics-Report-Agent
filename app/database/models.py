"""
app/database/models.py
======================
SQLAlchemy ORM Metadata Models for Phase 5

WHY THESE MODELS EXIST:
    Phase 5 establishes the MySQL metadata layer for tracking:
      1. Dataset versions and load lifecycle (dataset_versions)
      2. Column-level schema and semantic metadata (dataset_columns)
      3. Analyst-confirmed relationships (approved_relationships)
      4. Platform operation logs (audit_logs)

NOTE ON CLINICAL TABLES:
    The actual clinical tables (e.g. patients, encounters, conditions, etc.)
    are dynamic analytical tables created directly via pandas.to_sql() upon loading.
    Only the metadata models above are defined here as fixed ORM entities.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    LargeBinary,
)
from sqlalchemy.dialects.mysql import MEDIUMBLOB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# =============================================================================
# Model 1: DatasetVersion
# =============================================================================

class DatasetVersion(Base):
    """
    Tracks versions and load history of clinical datasets in MySQL.

    Status values:
      - ANALYZED: Successfully passed ingestion analysis.
      - LOADED: Successfully persisted to MySQL clinical table.
      - FAILED: Loading encountered an error.
    """
    __tablename__ = "dataset_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="LOADED")
    loaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # One-to-many relationship with column metadata
    columns: Mapped[List["DatasetColumn"]] = relationship(
        "DatasetColumn",
        back_populates="version",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<DatasetVersion(id={self.id}, dataset='{self.dataset_name}', "
            f"v{self.version_number}, rows={self.row_count}, status='{self.status}')>"
        )


# =============================================================================
# Model 2: DatasetColumn
# =============================================================================

class DatasetColumn(Base):
    """
    Stores column-level schema, data type, and semantic profiling metadata
    for a specific dataset version.
    """
    __tablename__ = "dataset_columns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dataset_versions.id"),
        nullable=False,
        index=True,
    )
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    column_name: Mapped[str] = mapped_column(String(100), nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    semantic_type: Mapped[str] = mapped_column(String(50), nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_primary_key_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship back to version
    version: Mapped["DatasetVersion"] = relationship("DatasetVersion", back_populates="columns")

    def __repr__(self) -> str:
        return (
            f"<DatasetColumn(id={self.id}, dataset='{self.dataset_name}', "
            f"col='{self.column_name}', semantic='{self.semantic_type}')>"
        )


# =============================================================================
# Model 3: ApprovedRelationship
# =============================================================================

class ApprovedRelationship(Base):
    """
    Stores analyst-reviewed relationships (approved or rejected).
    Acts as the source of truth for analytical foreign keys before MySQL constraints.
    """
    __tablename__ = "approved_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_table: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_column: Mapped[str] = mapped_column(String(100), nullable=False)
    child_table: Mapped[str] = mapped_column(String(100), nullable=False)
    child_column: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="APPROVED")
    analyst_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    was_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    original_candidate: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<ApprovedRelationship(id={self.id}, {self.parent_table}.{self.parent_column} -> "
            f"{self.child_table}.{self.child_column}, status='{self.status}')>"
        )


# =============================================================================
# Model 4: AuditLog
# =============================================================================

class AuditLog(Base):
    """
    Records clinical data platform operations (ingestion, loads, review decisions).
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="Clinical Analytics API")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action='{self.action}', entity='{self.entity_name}', "
            f"user_agent='{self.user_agent}', status='{self.status}')>"
        )


# =============================================================================
# Model 5: ClinicalDatasetRegistry
# =============================================================================

class ClinicalDatasetRegistry(Base):
    """
    Tracks clinical dataset registration, approval status, and classification.
    Distinguishes approved CDISC/clinical datasets from temporary test/demo tables.

    Classifications:
      - CLINICAL: Approved clinical dataset for analytical queries and planning.
      - TEST: Synthetic or unit/integration test dataset.
      - DEMO: Synthetic demonstration or mock dataset.
      - QUARANTINED: Unverified, unapproved, or isolated dataset.

    Approval statuses:
      - APPROVED: Authorized for clinical analytics and table selection.
      - PENDING: Uploaded, awaiting analyst review / registration.
      - REJECTED: Denied from analytical queries.
    """
    __tablename__ = "clinical_dataset_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    classification: Mapped[str] = mapped_column(String(50), nullable=False, default="CLINICAL")
    approval_status: Mapped[str] = mapped_column(String(50), nullable=False, default="APPROVED")
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<ClinicalDatasetRegistry(id={self.id}, name='{self.dataset_name}', "
            f"classification='{self.classification}', status='{self.approval_status}')>"
        )


class ClinicalReport(Base):
    """Acknowledged PDFs only. Legacy user_id is a fixed local-prototype value."""

    __tablename__ = "clinical_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    analysis_run_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    analysis_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    insight: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    results: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sql_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selected_tables: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    analysis_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    generation_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pdf_bytes: Mapped[Optional[bytes]] = mapped_column(LargeBinary().with_variant(MEDIUMBLOB, "mysql"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
