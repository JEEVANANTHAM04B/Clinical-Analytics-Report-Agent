"""
app/api/database.py
====================
MySQL Clinical Data Layer API Endpoints (Phase 5)

WHY THIS API EXISTS:
    Exposes endpoints for loading validated clinical datasets into MySQL
    and retrieving platform metadata (versions, column profiling, audit logs).

ENDPOINTS:
    POST /database/load
        Loads a validated CSV/XLSX dataset into a dedicated MySQL clinical table,
        generating safe identifiers, mapping types, and recording metadata.

    GET /database/versions
        Lists all loaded dataset versions and row counts.

    GET /database/versions/{version_id}/columns
        Lists column schema, semantic types, and missing-value profiling.

    GET /database/relationships
        Lists analyst-reviewed relationships persisted in MySQL.

    GET /database/audit-logs
        Lists audit log entries for platform operations.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.database.session import get_db
from app.database import repository
from app.ingestion.mysql_loader import load_dataset_to_mysql
from app.schemas.database import (
    DatasetLoadRequest,
    DatasetLoadResponse,
    DatasetVersionOut,
    ListVersionsResponse,
    DatasetColumnOut,
    ListColumnsResponse,
    ApprovedRelationshipOut,
    AuditLogOut,
    ListAuditLogsResponse,
    ListTablesResponse,
    TableMetadataOut,
    TableColumnInfo,
    ListRegistryResponse,
    RegistryEntryOut,
    UpdateRegistryStatusRequest,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/database",
    tags=["Database Layer (Phase 5)"],
)


# =============================================================================
# POST /database/load
# =============================================================================

@router.post(
    "/load",
    response_model=DatasetLoadResponse,
    summary="Load Validated Dataset into MySQL",
    description=(
        "Loads a validated CSV or XLSX clinical dataset into a dedicated MySQL table. "
        "Performs complete Phase 2/3 validation, schema profiling, safe table name sanitization, "
        "deterministic type mapping, and records platform metadata in 'dataset_versions', "
        "'dataset_columns', and 'audit_logs'.\n\n"
        "Files must reside in allowed directories (data/sample/, data/uploads/, or verified dataset dir)."
    ),
    responses={
        200: {"description": "Dataset loaded successfully into MySQL"},
        400: {"description": "Invalid input, path security violation, or empty dataset"},
        404: {"description": "Dataset file not found in allowed directories"},
        409: {"description": "Target table already exists (use if_exists='replace' to overwrite)"},
        500: {"description": "Database insertion or connection error"},
    },
    status_code=status.HTTP_200_OK,
)
def load_clinical_dataset(request: DatasetLoadRequest):
    """
    Load a validated clinical dataset into MySQL.

    - **filename**: Name of file in `data/sample/` or `data/uploads/` (e.g. `'sample_clinical_data.csv'`)
    - **file_path**: Explicit path within allowed directory boundaries
    - **table_name**: Optional custom table name override (sanitized deterministically)
    - **if_exists**: `'fail'` (default), `'replace'`, or `'append'`
    """
    logger.info(
        f"POST /database/load received | filename='{request.filename}' | "
        f"file_path='{request.file_path}' | if_exists='{request.if_exists}'"
    )

    try:
        result = load_dataset_to_mysql(
            filename=request.filename,
            file_path=request.file_path,
            custom_table_name=request.table_name,
            if_exists=request.if_exists,
        )

        return DatasetLoadResponse(
            status="success",
            message=result["message"],
            table_name=result["table_name"],
            rows_loaded=result["rows_loaded"],
            columns_loaded=result["columns_loaded"],
            dataset_version_id=result["dataset_version_id"],
            version_number=result["version_number"],
            loaded_at=result["loaded_at"],
        )

    except FileNotFoundError as e:
        logger.warning(f"Dataset load 404: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "error_code": "FILE_NOT_FOUND", "message": str(e)},
        )

    except ValueError as e:
        msg = str(e)
        if "already exists" in msg.lower():
            logger.warning(f"Dataset load 409 Conflict: {msg}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"status": "error", "error_code": "TABLE_ALREADY_EXISTS", "message": msg},
            )
        logger.warning(f"Dataset load 400 Bad Request: {msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "error_code": "INVALID_REQUEST", "message": msg},
        )

    except Exception as e:
        logger.exception(f"Dataset load 500 Server Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "error_code": "DATABASE_LOAD_ERROR",
                "message": f"Failed to load dataset into MySQL: {str(e)}",
            },
        )


# =============================================================================
# GET /database/versions
# =============================================================================

@router.get(
    "/versions",
    response_model=ListVersionsResponse,
    summary="List Loaded Dataset Versions",
    description="Returns all dataset versions loaded into MySQL along with row counts and status.",
    status_code=status.HTTP_200_OK,
)
def list_dataset_versions(
    dataset_name: Optional[str] = Query(None, description="Filter versions by dataset or table name"),
    db: Session = Depends(get_db),
):
    """Retrieve history of loaded dataset versions."""
    versions = repository.get_dataset_versions(db=db, dataset_name=dataset_name)
    return ListVersionsResponse(
        status="success",
        count=len(versions),
        versions=[DatasetVersionOut.model_validate(v) for v in versions],
    )


# =============================================================================
# GET /database/versions/{version_id}/columns
# =============================================================================

@router.get(
    "/versions/{version_id}/columns",
    response_model=ListColumnsResponse,
    summary="Get Column Metadata for a Dataset Version",
    description="Returns column schemas, data types, semantic profiles, and missing-value statistics.",
    responses={
        200: {"description": "Column metadata retrieved successfully"},
        404: {"description": "Dataset version not found"},
    },
    status_code=status.HTTP_200_OK,
)
def get_version_columns(
    version_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve column metadata for a specific dataset version."""
    version = repository.get_dataset_version_by_id(db=db, version_id=version_id)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DatasetVersion with id={version_id} not found.",
        )

    columns = repository.get_dataset_columns(db=db, dataset_version_id=version_id)
    return ListColumnsResponse(
        status="success",
        dataset_version_id=version_id,
        count=len(columns),
        columns=[DatasetColumnOut.model_validate(c) for c in columns],
    )


# =============================================================================
# GET /database/relationships
# =============================================================================

@router.get(
    "/relationships",
    response_model=List[ApprovedRelationshipOut],
    summary="List Reviewed Relationships Persisted in MySQL",
    description="Returns all relationships (APPROVED or REJECTED) stored in the MySQL metadata table.",
    status_code=status.HTTP_200_OK,
)
def list_persisted_relationships(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: APPROVED or REJECTED"),
    db: Session = Depends(get_db),
):
    """Retrieve analyst-reviewed relationships persisted in MySQL."""
    rels = repository.get_approved_relationships_from_db(db=db, status=status_filter)
    return [ApprovedRelationshipOut.model_validate(r) for r in rels]


# =============================================================================
# GET /database/audit-logs
# =============================================================================

@router.get(
    "/audit-logs",
    response_model=ListAuditLogsResponse,
    summary="List Platform Audit Logs",
    description="Returns recent platform operations recorded in the MySQL audit log table.",
    status_code=status.HTTP_200_OK,
)
def list_audit_logs(
    limit: int = Query(50, ge=1, le=500, description="Max logs to return"),
    db: Session = Depends(get_db),
):
    """Retrieve platform audit logs from MySQL, ordered newest first."""
    logs = repository.get_audit_logs(db=db, limit=limit)
    out_items: List[AuditLogOut] = []
    for log in logs:
        user_val = getattr(log, "user_agent", None) or "Clinical Analyst"
        details_val = log.message or f"{log.entity_type}: {log.entity_name}"
        ts_val = log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else ""

        out_items.append(
            AuditLogOut(
                id=log.id,
                action=log.action,
                entity_type=log.entity_type,
                entity_name=log.entity_name,
                status=log.status,
                message=log.message,
                details=details_val,
                user=user_val,
                user_agent=user_val,
                timestamp=ts_val,
                created_at=log.created_at,
            )
        )

    return ListAuditLogsResponse(
        status="success",
        count=len(out_items),
        logs=out_items,
        audit_logs=out_items,
        items=out_items,
    )


# =============================================================================
# GET /database/tables
# =============================================================================

# =============================================================================
# GET /database/tables
# =============================================================================

@router.get(
    "/tables",
    response_model=ListTablesResponse,
    summary="List Available Clinical Data Tables",
    description="Returns available clinical data tables in MySQL with columns and row counts for dynamic dashboard selection.",
    status_code=status.HTTP_200_OK,
)
def list_clinical_tables(
    classification: Optional[str] = Query("CLINICAL", description="Dataset classification filter"),
    approval_status: Optional[str] = Query("APPROVED", description="Dataset approval status filter"),
    include_all: bool = Query(False, description="Whether to include all datasets regardless of classification"),
):
    """Retrieve approved clinical data tables and schema columns from the authoritative registry."""
    from sqlalchemy import text
    from app.core.database import engine
    from app.database.schema_service import get_database_schema
    from app.clinical.dataset_registry_service import list_all_registry_entries

    # If include_all is False, get schema for approved clinical tables only
    schema = get_database_schema(approved_only=not include_all)

    # Fetch registry metadata mapping (without duplicating row count queries)
    registry_entries = {r["dataset_name"].lower(): r for r in list_all_registry_entries(include_all=True, include_row_counts=False)}

    tables_out = []
    with engine.connect() as conn:
        for table_name, cols in schema["tables"].items():
            t_lower = table_name.lower()
            reg_info = registry_entries.get(t_lower, {})

            # When not include_all, strictly ensure classification and approval_status match
            if not include_all:
                tbl_class = reg_info.get("classification", "CLINICAL")
                tbl_status = reg_info.get("approval_status", "APPROVED")
                if classification and tbl_class != classification:
                    continue
                if approval_status and tbl_status != approval_status:
                    continue

            try:
                row_cnt = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`")).scalar() or 0
            except Exception:
                row_cnt = 0

            display_name = reg_info.get("display_name") or table_name.capitalize()
            tbl_class = reg_info.get("classification", "CLINICAL")
            tbl_status = reg_info.get("approval_status", "APPROVED")
            tbl_cat = reg_info.get("category")

            tables_out.append(
                TableMetadataOut(
                    name=table_name,
                    display_name=display_name,
                    row_count=int(row_cnt),
                    classification=tbl_class,
                    approval_status=tbl_status,
                    category=tbl_cat,
                    columns=[
                        TableColumnInfo(
                            name=c["name"],
                            type=c["type"],
                            nullable=c.get("nullable", True),
                        )
                        for c in cols
                    ],
                )
            )

    return ListTablesResponse(
        status="success",
        count=len(tables_out),
        tables=tables_out,
    )


# =============================================================================
# Dataset Registry Endpoints
# =============================================================================

@router.get(
    "/registry",
    response_model=ListRegistryResponse,
    summary="List Clinical Dataset Registry Entries",
    description="Lists all tracked datasets across classifications (CLINICAL, TEST, DEMO, QUARANTINED).",
    status_code=status.HTTP_200_OK,
)
def get_dataset_registry(
    include_all: bool = Query(True, description="Whether to include test/demo/quarantined datasets"),
):
    """Returns dataset registry entries with classifications and approval status."""
    from app.clinical.dataset_registry_service import list_all_registry_entries

    entries = list_all_registry_entries(include_all=include_all)
    return ListRegistryResponse(
        status="success",
        count=len(entries),
        entries=[
            RegistryEntryOut(
                id=e["id"],
                dataset_name=e["dataset_name"],
                display_name=e["display_name"],
                classification=e["classification"],
                approval_status=e["approval_status"],
                category=e.get("category"),
                description=e.get("description"),
                row_count=e.get("row_count", 0),
                is_present_in_db=e.get("is_present_in_db", True),
                created_at=e.get("created_at"),
                updated_at=e.get("updated_at"),
            )
            for e in entries
        ],
    )


@router.put(
    "/registry/{dataset_name}/status",
    summary="Update Dataset Classification or Approval Status",
    description="Updates classification (CLINICAL, TEST, DEMO, QUARANTINED) and approval status (APPROVED, PENDING, REJECTED).",
    status_code=status.HTTP_200_OK,
)
def update_dataset_registry_status(
    dataset_name: str,
    req: UpdateRegistryStatusRequest,
):
    """Updates dataset classification and approval status in the registry."""
    from app.clinical.dataset_registry_service import update_dataset_status

    try:
        updated = update_dataset_status(
            dataset_name=dataset_name,
            classification=req.classification,
            approval_status=req.approval_status,
            category=req.category,
            description=req.description,
        )
        return {"status": "success", "entry": updated}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update dataset '{dataset_name}': {str(e)}",
        )


@router.post(
    "/registry/{dataset_name}/approve",
    summary="Approve Dataset for Clinical Analytics",
    description="Approves a dataset and sets its classification to CLINICAL and status to APPROVED.",
    status_code=status.HTTP_200_OK,
)
def approve_clinical_dataset(dataset_name: str):
    """Approves a dataset for clinical analytics."""
    from app.clinical.dataset_registry_service import approve_dataset

    try:
        updated = approve_dataset(dataset_name)
        return {"status": "success", "message": f"Dataset '{dataset_name}' approved for clinical analytics.", "entry": updated}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to approve dataset '{dataset_name}': {str(e)}",
        )
