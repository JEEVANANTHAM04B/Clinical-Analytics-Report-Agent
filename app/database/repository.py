"""
app/database/repository.py
===========================
Database Repository & Service Layer for Phase 5

WHY THIS MODULE EXISTS:
    Encapsulates all SQLAlchemy database read and write operations, keeping
    SQL queries and ORM interactions out of API routes and ingestion services.

RESPONSIBILITIES:
    - Dataset version creation and retrieval
    - Column metadata persistence
    - Approved and rejected relationship persistence
    - Platform audit logging
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.database.models import (
    DatasetVersion,
    DatasetColumn,
    ApprovedRelationship,
    AuditLog,
)

logger = get_logger(__name__)


# =============================================================================
# Dataset Version Operations
# =============================================================================

def create_dataset_version(
    db: Session,
    dataset_name: str,
    source_filename: str,
    source_file_type: str,
    row_count: int,
    column_count: int,
    status: str = "LOADED",
    version_number: Optional[int] = None,
) -> DatasetVersion:
    """
    Creates and persists a new DatasetVersion record.
    If version_number is not provided, computes (highest current version + 1).
    """
    if version_number is None:
        highest_v = db.query(func.max(DatasetVersion.version_number)).filter(
            DatasetVersion.dataset_name == dataset_name
        ).scalar()
        version_number = (highest_v or 0) + 1

    version = DatasetVersion(
        dataset_name=dataset_name,
        source_filename=source_filename,
        source_file_type=source_file_type,
        version_number=version_number,
        row_count=row_count,
        column_count=column_count,
        status=status,
        loaded_at=datetime.utcnow() if status == "LOADED" else None,
        created_at=datetime.utcnow(),
    )

    db.add(version)
    db.commit()
    db.refresh(version)
    logger.info(f"Created DatasetVersion id={version.id} for '{dataset_name}' (v{version_number})")
    return version


def get_dataset_versions(
    db: Session,
    dataset_name: Optional[str] = None,
) -> List[DatasetVersion]:
    """Retrieves dataset versions, optionally filtered by dataset_name."""
    query = db.query(DatasetVersion)
    if dataset_name:
        query = query.filter(DatasetVersion.dataset_name == dataset_name)
    return query.order_by(DatasetVersion.id.desc()).all()


def get_dataset_version_by_id(
    db: Session,
    version_id: int,
) -> Optional[DatasetVersion]:
    """Retrieves a single dataset version by its primary key ID."""
    return db.query(DatasetVersion).filter(DatasetVersion.id == version_id).first()


# =============================================================================
# Dataset Column Operations
# =============================================================================

def save_dataset_columns(
    db: Session,
    dataset_version_id: int,
    dataset_name: str,
    columns_metadata: List[Dict[str, Any]],
) -> List[DatasetColumn]:
    """
    Persists column-level schema and profiling metadata for a dataset version.
    """
    records: List[DatasetColumn] = []
    for col in columns_metadata:
        rec = DatasetColumn(
            dataset_version_id=dataset_version_id,
            dataset_name=dataset_name,
            column_name=col["column_name"],
            data_type=col["data_type"],
            semantic_type=col.get("semantic_type", "unknown"),
            nullable=col.get("nullable", True),
            missing_count=col.get("missing_count", 0),
            missing_percentage=col.get("missing_percentage", 0.0),
            is_primary_key_candidate=col.get("is_primary_key_candidate", False),
            created_at=datetime.utcnow(),
        )
        records.append(rec)

    db.add_all(records)
    db.commit()
    logger.info(f"Saved {len(records)} column metadata record(s) for version id={dataset_version_id}")
    return records


def get_dataset_columns(
    db: Session,
    dataset_version_id: int,
) -> List[DatasetColumn]:
    """Retrieves column metadata for a given dataset version."""
    return (
        db.query(DatasetColumn)
        .filter(DatasetColumn.dataset_version_id == dataset_version_id)
        .order_by(DatasetColumn.id.asc())
        .all()
    )


# =============================================================================
# Approved Relationship Operations
# =============================================================================

def save_relationship_review(
    db: Session,
    parent_table: str,
    parent_column: str,
    child_table: str,
    child_column: str,
    status: str,
    analyst_note: Optional[str] = None,
    was_edited: bool = False,
    original_candidate: Optional[str] = None,
) -> ApprovedRelationship:
    """
    Persists an analyst review decision (APPROVE or REJECT) in MySQL.
    If the relationship already exists, updates the record in-place.
    """
    # Look for existing record by normalized table/col coordinates
    existing = (
        db.query(ApprovedRelationship)
        .filter(
            func.lower(ApprovedRelationship.parent_table) == parent_table.strip().lower(),
            func.lower(ApprovedRelationship.parent_column) == parent_column.strip().lower(),
            func.lower(ApprovedRelationship.child_table) == child_table.strip().lower(),
            func.lower(ApprovedRelationship.child_column) == child_column.strip().lower(),
        )
        .first()
    )

    if existing:
        existing.status = status.upper()
        existing.analyst_note = analyst_note
        existing.was_edited = was_edited
        existing.original_candidate = original_candidate
        existing.created_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        logger.info(f"Updated relationship in MySQL: id={existing.id} status={existing.status}")
        return existing
    else:
        new_rel = ApprovedRelationship(
            parent_table=parent_table.strip(),
            parent_column=parent_column.strip(),
            child_table=child_table.strip(),
            child_column=child_column.strip(),
            status=status.upper(),
            analyst_note=analyst_note,
            was_edited=was_edited,
            original_candidate=original_candidate,
            created_at=datetime.utcnow(),
        )
        db.add(new_rel)
        db.commit()
        db.refresh(new_rel)
        logger.info(f"Persisted relationship in MySQL: id={new_rel.id} status={new_rel.status}")
        return new_rel


def get_approved_relationships_from_db(
    db: Session,
    status: Optional[str] = None,
) -> List[ApprovedRelationship]:
    """Retrieves relationships persisted in MySQL, optionally filtered by status (e.g. 'APPROVED' or 'REJECTED')."""
    query = db.query(ApprovedRelationship)
    if status:
        query = query.filter(ApprovedRelationship.status == status.upper())
    return query.order_by(ApprovedRelationship.id.asc()).all()


# =============================================================================
# Audit Log Operations
# =============================================================================

def create_audit_log(
    db: Session,
    action: str,
    entity_type: str,
    entity_name: str,
    status: str,
    message: Optional[str] = None,
    user_agent: Optional[str] = "Clinical Analyst",
) -> AuditLog:
    """Creates a persistent platform audit log record in MySQL."""
    try:
        log_entry = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_name=entity_name,
            status=status,
            message=message,
            user_agent=user_agent or "Clinical Analyst",
            created_at=datetime.utcnow(),
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        logger.info(f"AuditLog created: [{action}] {entity_type}='{entity_name}' status='{status}'")
        return log_entry
    except Exception as e:
        logger.exception(f"Failed to create audit log entry: {e}")
        db.rollback()
        raise


def get_audit_logs(
    db: Session,
    limit: int = 100,
) -> List[AuditLog]:
    """Retrieves the most recent audit logs."""
    return db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
