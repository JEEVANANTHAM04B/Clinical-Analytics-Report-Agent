"""
app/ingestion/file_validator.py
================================
File Validation Layer

WHY THIS EXISTS:
    Before we read, process, or store any uploaded file, we must validate it.
    Validation is separated from reading so each responsibility is clear:

    file_validator.py  → "Should we even accept this file?"
    file_reader.py     → "Read the file into a DataFrame"
    metadata.py        → "What does this dataset contain?"
    quality_checker.py → "How clean is this dataset?"

WHAT WE VALIDATE:
    1. File extension    — Only .csv, .xlsx, .xls
    2. File size         — Must not exceed MAX_UPLOAD_SIZE_MB
    3. Non-empty content — Must have at least some bytes

WHAT WE DO NOT VALIDATE HERE:
    - Column names (no assumed clinical schema at this stage)
    - Data types
    - Row counts (those are in metadata.py)
    - Data quality (that's in quality_checker.py)

SECURITY CONSIDERATIONS:
    - We validate the extension from the filename, NOT from MIME type alone,
      because MIME types can be spoofed by renaming files.
    - We also check the actual content bytes for Excel files (in file_reader.py).
    - Path traversal is prevented in file_storage.py by using safe filenames.
"""

import os
from fastapi import UploadFile

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# =============================================================================
# Supported extensions
# =============================================================================

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

# =============================================================================
# Validation result dataclass (plain Python — no SQLAlchemy, no FastAPI)
# =============================================================================

class ValidationResult:
    """
    Simple container for the outcome of file validation.

    Attributes:
        is_valid      — True if the file passed all checks
        error_code    — Short machine-readable code if is_valid is False
        error_message — Human-readable message explaining the rejection
        file_ext      — Detected file extension (e.g., ".csv")
        file_type     — Clean file type string (e.g., "csv")
        file_size     — File size in bytes (read from upload)
    """

    def __init__(
        self,
        is_valid: bool,
        file_ext: str = "",
        file_type: str = "",
        file_size: int = 0,
        error_code: str = "",
        error_message: str = "",
    ):
        self.is_valid = is_valid
        self.file_ext = file_ext
        self.file_type = file_type
        self.file_size = file_size
        self.error_code = error_code
        self.error_message = error_message


# =============================================================================
# Main validation function
# =============================================================================

async def validate_upload(file: UploadFile) -> ValidationResult:
    """
    Validate an uploaded file before processing.

    Runs these checks IN ORDER — fails fast on the first problem:
        1. Extension check   → Reject unsupported file types
        2. File size check   → Reject files over MAX_UPLOAD_SIZE_MB
        3. Empty file check  → Reject zero-byte files

    Args:
        file: The FastAPI UploadFile object from the multipart request

    Returns:
        ValidationResult with is_valid=True if all checks pass,
        or is_valid=False with error_code and error_message if rejected.

    NOTE: This function reads the entire file content to check size.
          The content is returned via file.seek(0) so the reader can
          re-read from the beginning afterwards.
    """

    # ── 1. Extension check ────────────────────────────────────────────────────
    # Extract extension from the original filename safely
    # os.path.splitext handles edge cases like ".hidden" or "file.CSV"
    filename = file.filename or "unknown"
    _, raw_ext = os.path.splitext(filename)
    file_ext = raw_ext.lower()  # Normalize: ".CSV" → ".csv"

    if file_ext not in SUPPORTED_EXTENSIONS:
        logger.warning(
            f"File rejected — unsupported extension: '{file_ext}' | "
            f"filename='{filename}'"
        )

        # Special message for .xls explaining the xlrd dependency
        if file_ext == ".xls":
            detail = (
                "Legacy .xls format requires the 'xlrd' package which is not currently installed. "
                "Please save your file as .xlsx (Excel 2007+) and re-upload."
            )
        else:
            detail = (
                f"'{file_ext}' is not a supported format. "
                f"Accepted formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        return ValidationResult(
            is_valid=False,
            file_ext=file_ext,
            error_code="UNSUPPORTED_FILE_TYPE",
            error_message=detail,
        )

    # Derive clean type string from extension
    file_type = file_ext.lstrip(".")  # ".csv" → "csv"

    # ── 2. Read file content to determine size ────────────────────────────────
    # We read all content now so we can:
    #   a) Check the size
    #   b) Detect empty files
    # The caller (file_reader.py) will re-read from the upload object,
    # so we MUST seek back to the beginning after reading.

    content = await file.read()
    file_size = len(content)

    # IMPORTANT: Reset the file cursor so subsequent reads work correctly
    await file.seek(0)

    # ── 3. File size check ────────────────────────────────────────────────────
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024  # Convert MB → bytes

    if file_size > max_bytes:
        size_mb = file_size / (1024 * 1024)
        logger.warning(
            f"File rejected — size too large: {size_mb:.2f} MB | "
            f"limit={settings.MAX_UPLOAD_SIZE_MB} MB | filename='{filename}'"
        )
        return ValidationResult(
            is_valid=False,
            file_ext=file_ext,
            file_type=file_type,
            file_size=file_size,
            error_code="FILE_TOO_LARGE",
            error_message=(
                f"File size {size_mb:.2f} MB exceeds the maximum allowed size "
                f"of {settings.MAX_UPLOAD_SIZE_MB} MB."
            ),
        )

    # ── 4. Empty file check ───────────────────────────────────────────────────
    if file_size == 0:
        logger.warning(f"File rejected — zero bytes | filename='{filename}'")
        return ValidationResult(
            is_valid=False,
            file_ext=file_ext,
            file_type=file_type,
            file_size=0,
            error_code="EMPTY_FILE",
            error_message="The uploaded file is empty (0 bytes). Please upload a file with data.",
        )

    # ── All checks passed ─────────────────────────────────────────────────────
    logger.info(
        f"File validation passed | filename='{filename}' | "
        f"type={file_type} | size={file_size / 1024:.1f} KB"
    )

    return ValidationResult(
        is_valid=True,
        file_ext=file_ext,
        file_type=file_type,
        file_size=file_size,
    )
