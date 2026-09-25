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

from typing import Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, status, Body

from app.ingestion.file_validator import validate_upload
from app.ingestion.file_reader import read_uploaded_file
from app.ingestion.metadata import extract_metadata
from app.ingestion.quality_checker import check_quality
from app.ingestion.analyzer import resolve_files_to_analyze, analyze_datasets
from app.ingestion.relationship_review import set_relationship_candidates
from app.schemas.ingestion import UploadResponse, ErrorResponse
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

    # ── STEP 6: Build and return the response ─────────────────────────────────
    logger.info(
        f"Upload processed successfully | filename='{filename}' | "
        f"rows={dataset_metadata.row_count} | cols={dataset_metadata.column_count} | "
        f"saved='{read_result.saved_path}'"
    )

    return UploadResponse(
        status="success",
        message=(
            f"Dataset '{read_result.original_filename}' uploaded and validated successfully. "
            f"{dataset_metadata.row_count} rows × {dataset_metadata.column_count} columns detected."
        ),
        dataset=dataset_metadata,
        quality=quality_report,
        saved_path=read_result.saved_path,
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
