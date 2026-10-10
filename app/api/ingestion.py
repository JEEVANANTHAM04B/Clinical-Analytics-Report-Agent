"""
app/api/ingestion.py
=====================
Dataset Ingestion API Endpoints

WHY THIS FILE IS THIN:
    The API layer should only:
      1. Receive the HTTP request
      2. Call the appropriate service functions
      3. Return the structured response

    All business logic lives in app/ingestion/.
    This makes it easy to test the ingestion logic independently of FastAPI.

ENDPOINTS:
    POST /ingestion/upload
        Accept a multipart/form-data file upload (CSV or XLSX).
        Validate, save, read, extract metadata, and run quality checks.
        Returns structured JSON with dataset metadata and quality report.

ERROR RESPONSE STRATEGY:
    We use HTTPException for clean HTTP error codes.
    We never expose raw Python stack traces to the API caller.
    Detailed errors are logged internally.

    400 Bad Request:
        - Unsupported file type
        - File too large
        - Empty file
        - File cannot be parsed (corrupt Excel, bad CSV)
        - Dataset has no data rows (header-only file)

    500 Internal Server Error:
        - Unexpected exceptions (disk failure, out of memory, etc.)
"""

from typing import Optional, List, Dict, Any
import os
import re
from fastapi import APIRouter, File, UploadFile, HTTPException, status, Body, Form

from app.ingestion.file_validator import validate_upload
from app.ingestion.file_reader import read_uploaded_file
from app.ingestion.metadata import extract_metadata
from app.ingestion.quality_checker import check_quality
from app.ingestion.analyzer import resolve_files_to_analyze, analyze_datasets
from app.ingestion.relationship_review import set_relationship_candidates
from app.ingestion.mysql_loader import (
    load_dataset_to_mysql,
    validate_and_sanitize_column_names,
    validate_table_name,
    sanitize_table_name,
    map_pandas_dtype,
    PROTECTED_METADATA_TABLES,
)
from app.schemas.ingestion import UploadResponse, ErrorResponse, PreviewResponse, ColumnPreview
from app.schemas.validation import AnalyzeRequest, AnalyzeResponse
from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/ingestion",
    tags=["Ingestion"],
)


# =============================================================================
# POST /ingestion/upload
# =============================================================================

@router.post(
    "/upload",
    summary="Upload a Dataset",
    description=(
        "Upload a clinical dataset in CSV or XLSX format. "
        "The system will validate the file, save it locally, "
        "extract structural metadata, and run initial data quality checks. "
        "Returns a detailed JSON report including column types, "
        "missing value counts, duplicate rows, and quality flags."
    ),
    response_model=UploadResponse,
    responses={
        200: {"description": "File uploaded and processed successfully"},
        400: {"description": "Invalid file (unsupported type, empty, too large, or corrupt)"},
        500: {"description": "Unexpected server error during processing"},
    },
    status_code=status.HTTP_200_OK,
)
async def upload_dataset(
    file: UploadFile = File(
        ...,
        description="Dataset file to upload. Supported formats: .csv, .xlsx",
    ),
    target_table: Optional[str] = Form(
        None,
        description="Target MySQL table name override (auto-detected if omitted)",
    ),
    if_exists: Optional[str] = Form(
        "append",
        description="'append' (default), 'replace', or 'fail'",
    ),
    is_new_table: Optional[bool] = Form(
        False,
        description="True if explicitly creating a new MySQL table",
    ),
    classification: Optional[str] = Form(
        "CLINICAL",
        description="Dataset classification: CLINICAL, TEST, DEMO, QUARANTINED",
    ),
    approval_status: Optional[str] = Form(
        "APPROVED",
        description="Initial approval status: APPROVED, PENDING, REJECTED",
    ),
    category: Optional[str] = Form(
        None,
        description="Optional category tag (e.g. 'SDTM', 'ADaM', 'Custom Clinical')",
    ),
):
    """
    Upload and validate a clinical dataset file.

    **Processing pipeline:**
    1. **Validate** — Check extension, size, and emptiness
    2. **Save** — Store file locally with a safe UUID-based filename
    3. **Read** — Parse into pandas DataFrame (CSV or XLSX)
    4. **Metadata** — Extract row count, column names, data types
    5. **Quality** — Check for duplicates, missing values, empty/constant columns

    **Supported formats:**
    - `.csv` — Comma-separated values
    - `.xlsx` — Modern Excel format (2007+)

    **Not supported:**
    - `.xls` — Legacy Excel (requires xlrd package, not installed)
    - `.pdf`, `.txt`, `.json`, `.png`, and all other formats

    **File size limit:** Configurable (default 50 MB)
    """
    filename = file.filename or "unknown"
    logger.info(f"POST /ingestion/upload received | filename='{filename}' | content_type='{file.content_type}'")

    # ── STEP 1: Validate the file ─────────────────────────────────────────────
    validation = await validate_upload(file)

    if not validation.is_valid:
        logger.warning(
            f"Upload rejected | error_code={validation.error_code} | "
            f"filename='{filename}' | message='{validation.error_message}'"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "error_code": validation.error_code,
                "message": validation.error_message,
            },
        )

    # ── STEP 2 & 3: Save to disk and read into DataFrame ─────────────────────
    try:
        read_result = await read_uploaded_file(
            file=file,
            file_type=validation.file_type,
            file_ext=validation.file_ext,
        )
    except ValueError as e:
        # Parsing error — bad CSV, corrupt Excel, header-only file, etc.
        logger.error(f"File parsing failed | filename='{filename}' | error='{e}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "error_code": "PARSE_ERROR",
                "message": str(e),
            },
        )
    except OSError as e:
        # Disk/filesystem error — permissions, disk full, etc.
        logger.error(f"File storage failed | filename='{filename}' | error='{e}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "error_code": "STORAGE_ERROR",
                "message": "Failed to save uploaded file. Please try again.",
            },
        )
    except Exception as e:
        # Truly unexpected error — log full details internally
        logger.exception(f"Unexpected error during file read | filename='{filename}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred during file processing.",
            },
        )

    df = read_result.dataframe

    # ── STEP 4: Extract dataset metadata ─────────────────────────────────────
    try:
        dataset_metadata = extract_metadata(
            df=df,
            original_filename=read_result.original_filename,
            saved_filename=read_result.saved_filename,
            file_type=read_result.file_type,
        )
    except Exception as e:
        logger.exception(f"Metadata extraction failed | filename='{filename}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "error_code": "METADATA_ERROR",
                "message": "Failed to extract dataset metadata.",
            },
        )

    # ── STEP 5: Run quality checks ────────────────────────────────────────────
    try:
        quality_report = check_quality(df=df, filename=read_result.original_filename)
    except Exception as e:
        logger.exception(f"Quality check failed | filename='{filename}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "error_code": "QUALITY_CHECK_ERROR",
                "message": "Failed to run data quality checks.",
            },
        )

    # ── STEP 6: Load dataset into MySQL ───────────────────────────────────────
    try:
        load_result = load_dataset_to_mysql(
            file_path=read_result.saved_path,
            custom_table_name=target_table,
            if_exists=if_exists or "append",
            is_new_table=bool(is_new_table),
            classification=classification or "CLINICAL",
            approval_status=approval_status or "APPROVED",
            category=category,
        )
        loaded_table_name = load_result.get("table_name")
        rows_loaded = load_result.get("rows_loaded", 0)
        rows_received = load_result.get("rows_received", dataset_metadata.row_count)
        rows_inserted = load_result.get("rows_inserted", rows_loaded)
        rows_skipped = load_result.get("rows_skipped", 0)
        rows_failed = load_result.get("rows_failed", 0)
        logger.info(
            f"Successfully processed upload into MySQL table '{loaded_table_name}' | "
            f"received={rows_received} | inserted={rows_inserted} | skipped={rows_skipped}"
        )
        # ── Step 6.1: Record persistent audit event ──────────────────────────────
        from app.audit.service import record_audit_event
        record_audit_event(
            action="DATASET_UPLOAD",
            details=f"Dataset '{filename}' uploaded and loaded into '{loaded_table_name}'. Received: {rows_received}, Inserted: {rows_inserted}, Skipped: {rows_skipped}.",
            user_agent="Clinical Analytics API",
            status="SUCCESS",
            entity_type="TABLE",
            entity_name=loaded_table_name or filename,
        )
    except ValueError as e:
        logger.warning(f"Validation / schema mismatch error during upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "error_code": "SCHEMA_VALIDATION_ERROR",
                "message": str(e),
            },
        )
    except Exception as e:
        logger.exception(f"Failed to load dataset into MySQL | filename='{filename}' | error='{e}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "error_code": "DATABASE_LOAD_ERROR",
                "message": f"Dataset validated successfully but failed to load into MySQL: {str(e)}",
            },
        )

    # ── STEP 7: Build and return the response ─────────────────────────────────
    logger.info(
        f"Upload processed successfully | filename='{filename}' | "
        f"rows={dataset_metadata.row_count} | cols={dataset_metadata.column_count} | "
        f"loaded_to='{loaded_table_name}' | rows_inserted={rows_inserted} | saved='{read_result.saved_path}'"
    )

    return UploadResponse(
        status="success",
        message=load_result.get("message") or (
            f"Upload completed. Target table: '{loaded_table_name}'. "
            f"Rows received: {rows_received}, Rows inserted: {rows_inserted}, "
            f"Rows skipped: {rows_skipped}, Rows failed: {rows_failed}."
        ),
        dataset=dataset_metadata,
        quality=quality_report,
        saved_path=read_result.saved_path,
        table_name=loaded_table_name,
        rows_loaded=rows_inserted,
        rows_received=rows_received,
        rows_inserted=rows_inserted,
        rows_skipped=rows_skipped,
        rows_failed=rows_failed,
        columns=dataset_metadata.column_count,
    )


# =============================================================================
# POST /ingestion/preview
# =============================================================================

@router.post(
    "/preview",
    summary="Preview Upload Dataset and Inferred Schema",
    description=(
        "Inspects uploaded CSV or XLSX dataset file, validates column names, "
        "infers MySQL data types, checks existing database schemas, and proposes "
        "target MySQL table."
    ),
    response_model=PreviewResponse,
    status_code=status.HTTP_200_OK,
)
async def preview_dataset(
    file: UploadFile = File(
        ...,
        description="Dataset file to preview (.csv or .xlsx)",
    ),
    target_mode: Optional[str] = Form(
        "auto",
        description="'auto', 'new', or 'existing'",
    ),
    target_table: Optional[str] = Form(
        None,
        description="Explicit table name override if specified",
    ),
):
    """
    Previews dataset file before committing to MySQL.
    Infers data types, detects schema matches against existing tables,
    and proposes either creating a new table or mapping to an existing table.
    """
    import pandas as pd
    from datetime import datetime
    filename = file.filename or "unknown"
    logger.info(f"POST /ingestion/preview received | filename='{filename}' | mode='{target_mode}' | table='{target_table}'")

    # 1. Validate file
    validation = await validate_upload(file)
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "error_code": validation.error_code,
                "message": validation.error_message,
            },
        )

    # 2. Read file into DataFrame
    try:
        read_result = await read_uploaded_file(
            file=file,
            file_type=validation.file_type,
            file_ext=validation.file_ext,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "error_code": "PARSE_ERROR",
                "message": str(e),
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "error_code": "READ_ERROR",
                "message": f"Failed to read dataset file: {str(e)}",
            },
        )

    df = read_result.dataframe
    if len(df) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "error_code": "EMPTY_DATASET",
                "message": "Cannot preview empty dataset. Zero data rows detected.",
            },
        )

    # 3. Validate and sanitize column headers
    try:
        sanitized_cols, col_mapping = validate_and_sanitize_column_names(df.columns)
        df = df.rename(columns=col_mapping)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "error_code": "INVALID_COLUMNS",
                "message": str(e),
            },
        )

    # 4. Infer column types and build preview
    columns_preview: List[ColumnPreview] = []
    for col in df.columns:
        series = df[col]
        sa_type, type_str = map_pandas_dtype(series)
        non_nulls = series.dropna()
        sample_vals = [str(x) for x in non_nulls.head(3).tolist()]
        orig_name = next((k for k, v in col_mapping.items() if v == col), col)
        columns_preview.append(
            ColumnPreview(
                name=str(col),
                original_name=str(orig_name),
                inferred_type=type_str,
                null_count=int(series.isna().sum()),
                sample_values=sample_vals,
            )
        )

    # 5. Check MySQL existing tables
    from app.core.database import engine
    from sqlalchemy import inspect
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()
    clinical_tables = [t for t in all_tables if t not in PROTECTED_METADATA_TABLES]

    # Pre-compute column compatibility across all clinical tables
    df_cols = {str(c).strip().upper() for c in df.columns}
    table_matches: Dict[str, Dict[str, Any]] = {}
    if df_cols and clinical_tables:
        for t in clinical_tables:
            try:
                t_cols = {c["name"].strip().upper() for c in inspector.get_columns(t)}
                if not t_cols:
                    continue
                intersection = df_cols.intersection(t_cols)
                coverage = len(intersection) / len(df_cols)
                jaccard = len(intersection) / len(df_cols.union(t_cols))
                table_matches[t] = {
                    "coverage": coverage,
                    "intersection_count": len(intersection),
                    "total_csv_cols": len(df_cols),
                    "score": coverage * 0.7 + jaccard * 0.3,
                }
            except Exception:
                pass

    base = os.path.basename(filename)
    base = os.path.splitext(base)[0]
    clean_base = re.sub(r"^[0-9a-fA-F\-]{36}_", "", base).strip().lower()

    mode_req = (target_mode or "auto").strip().lower()
    clean_explicit = target_table.strip() if target_table and target_table.strip() else None

    # Step 6: Target mode handling
    if mode_req == "new" or clean_explicit == "__new__":
        detected_mode = "new"
        cand_name = clean_explicit if clean_explicit and clean_explicit != "__new__" else clean_base
        try:
            proposed_table = validate_table_name(cand_name or "clinical_dataset")
        except ValueError:
            proposed_table = sanitize_table_name(cand_name or "clinical_dataset")

        table_already_exists = proposed_table.lower() in [t.lower() for t in all_tables]
        warning = (
            f"Table {proposed_table} already exists. Choose another name or explicitly select an existing table as the upload target."
            if table_already_exists
            else None
        )
        match_confidence = None
        match_message = f"Proposing new table '{proposed_table}'."

    elif clean_explicit and clean_explicit.lower() not in ("auto", "none"):
        # Explicit existing target table requested
        detected_mode = "existing"
        proposed_table = clean_explicit
        table_already_exists = proposed_table.lower() in [t.lower() for t in all_tables]
        match_info = table_matches.get(proposed_table, {"coverage": 0.0})
        match_confidence = match_info.get("coverage", 0.0)
        warning = None
        if not table_already_exists:
            warning = f"Table '{proposed_table}' does not exist in MySQL."
        elif match_confidence < 0.50:
            warning = f"Only {match_confidence:.0%} of uploaded columns match table '{proposed_table}'."
        match_message = f"Targeting existing table '{proposed_table}'."

    else:
        # Auto-detect mode
        sorted_matches = sorted(table_matches.items(), key=lambda x: x[1]["score"], reverse=True) if table_matches else []
        if sorted_matches and sorted_matches[0][1]["coverage"] >= 0.70:
            best_tbl, best_data = sorted_matches[0]
            if len(sorted_matches) > 1 and sorted_matches[1][1]["coverage"] >= 0.70 and abs(best_data["score"] - sorted_matches[1][1]["score"]) < 0.05:
                detected_mode = "ambiguous"
                proposed_table = ""
                table_already_exists = False
                match_confidence = best_data["coverage"]
                warning = f"Ambiguous schema match: uploaded columns equally match '{best_tbl}' and '{sorted_matches[1][0]}'. Please choose target table."
                match_message = warning
            else:
                detected_mode = "existing"
                proposed_table = best_tbl
                table_already_exists = True
                match_confidence = best_data["coverage"]
                warning = None
                match_message = f"Schema matches existing table '{best_tbl}' ({match_confidence:.0%} column match)."
        else:
            # Propose new table
            detected_mode = "new"
            proposed_table = sanitize_table_name(clean_base or "clinical_dataset")
            table_already_exists = proposed_table.lower() in [t.lower() for t in all_tables]
            warning = (
                f"Table {proposed_table} already exists. Choose another name or explicitly select an existing table as the upload target."
                if table_already_exists
                else None
            )
            match_confidence = None
            match_message = f"No matching existing table found. Proposing new table '{proposed_table}'."

    # Preview records (first 5 rows with safe conversion)
    preview_records = []
    for r in df.head(5).to_dict(orient="records"):
        clean_row = {}
        for k, v in r.items():
            if pd.isna(v):
                clean_row[k] = None
            elif isinstance(v, (pd.Timestamp, datetime)):
                clean_row[k] = str(v)
            else:
                clean_row[k] = v
        preview_records.append(clean_row)

    return PreviewResponse(
        status="success",
        detected_mode=detected_mode,
        proposed_table=proposed_table,
        table_already_exists=table_already_exists,
        match_confidence=match_confidence,
        match_message=match_message,
        warning=warning,
        total_rows=len(df),
        total_columns=len(df.columns),
        columns=columns_preview,
        preview_rows=preview_records,
    )


# =============================================================================
# POST /ingestion/analyze
# =============================================================================

@router.post(
    "/analyze",
    summary="Analyze Datasets (Phase 3)",
    description=(
        "Performs complete data quality, schema inspection, semantic type inference, "
        "missing-value profiling, duplicate detection, primary/foreign key discovery, "
        "and sensitive/direct-identifier detection across one or multiple clinical datasets. "
        "Source datasets remain strictly read-only."
    ),
    response_model=AnalyzeResponse,
    responses={
        200: {"description": "Datasets successfully analyzed and profiled"},
        400: {"description": "Invalid directory or file request"},
        404: {"description": "Specified files or dataset directory not found"},
        500: {"description": "Internal server error during analysis"},
    },
    status_code=status.HTTP_200_OK,
)
def analyze_clinical_datasets(
    request: Optional[AnalyzeRequest] = Body(
        default=None,
        description="Optional request body to specify directory_path, file_paths, or filenames. Defaults to standard dataset directory if omitted.",
    ),
):
    """
    Analyzes one or more clinical CSV/XLSX datasets.

    **Phase 3 Capabilities:**
    - **Schema & Type Profiling:** Pandas dtype + semantic type (identifier, integer, decimal, categorical, date, datetime, mixed, boolean).
    - **Missing Value Analysis:** Null counts, percentages, and categorized tiers (0%, <5%, 5-20%, 20-50%, >50%).
    - **Duplicate Analysis:** Complete row duplicates and ID uniqueness percentages.
    - **Primary Key Candidates:** Evaluates uniqueness, null counts, and identifier heuristics.
    - **Foreign Key Candidates:** Validates cross-table references (e.g. patients.ID -> encounters.PATIENT) with match rates and nullable relationship detection.
    - **Privacy Protection:** Identifies direct identifiers (SSN, DRIVERS, PASSPORT, names, addresses) requiring HIPAA/GDPR safeguards.
    - **Clinical Observations Special Handling:** Profiles heterogeneous value distributions (numeric vs text), units, and measurement types.
    """
    logger.info("POST /ingestion/analyze received")
    
    dir_path = request.directory_path if request else None
    f_paths = request.file_paths if request else None
    f_names = request.filenames if request else None

    # Step 1: Resolve dataset files
    try:
        files = resolve_files_to_analyze(
            directory_path=dir_path,
            file_paths=f_paths,
            filenames=f_names,
        )
    except FileNotFoundError as e:
        logger.warning(f"File resolution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "error_code": "DATASETS_NOT_FOUND",
                "message": str(e),
            },
        )
    except Exception as e:
        logger.exception(f"Unexpected error resolving files: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "error_code": "INVALID_REQUEST",
                "message": str(e),
            },
        )

    # Step 2: Execute analysis
    try:
        response = analyze_datasets(files)
        logger.info(f"POST /ingestion/analyze completed successfully | analyzed={len(files)} files")

        # Phase 4 Step 3: Populate detected relationship candidates in review store
        if response.relationships:
            registered_count = set_relationship_candidates(response.relationships)
            logger.info(f"Populated {registered_count} relationship candidate(s) for human review")

        return response
    except Exception as e:
        logger.exception(f"Analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "error_code": "ANALYSIS_ERROR",
                "message": f"Failed to complete dataset analysis: {str(e)}",
            },
        )
