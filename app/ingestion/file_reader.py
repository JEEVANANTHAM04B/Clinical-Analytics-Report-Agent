"""
app/ingestion/file_reader.py
=============================
File Reading Layer

WHY THIS EXISTS:
    Reading a CSV and reading an XLSX are different operations.
    This module provides a single unified function: read_uploaded_file()

    The caller (api/ingestion.py) doesn't care if the file is CSV or Excel.
    It just gets back a pandas DataFrame.

FILE STORAGE FLOW:
    1. File comes in via FastAPI UploadFile (in-memory bytes)
    2. file_validator.py already confirmed it's acceptable
    3. This module:
        a) Saves the file to disk safely (data/uploads/)
        b) Reads it into a pandas DataFrame
        c) Returns BOTH the saved path AND the DataFrame

WHY SAVE FIRST, THEN READ?
    - We save first to persist the original file for future phases
      (schema comparison, re-processing, audit trail)
    - We read from the saved file path to ensure data integrity
      (avoids double-reading in-memory bytes, which can cause Excel issues)

SAFE FILENAME GENERATION:
    We never use the original filename directly for storage.
    Reasons:
      1. Path traversal: "../../system/passwd.csv" could escape data/uploads/
      2. Overwriting: Two users uploading "data.csv" would collide
      3. Special chars: Spaces, Unicode, etc. cause filesystem issues

    Solution: Generate a UUID-based safe filename, keep the original extension.
    The original filename is preserved in DatasetMetadata for display purposes.

PANDAS READ SETTINGS:
    CSV:
        - Attempts to parse common date formats automatically
        - Uses default dtype inference (Pandas decides int/float/object)

    XLSX:
        - Uses openpyxl engine (already installed)
        - Reads first sheet by default
        - Same dtype inference as CSV

ERROR HANDLING:
    If pandas cannot parse the file (e.g., corrupt Excel, bad CSV encoding),
    we catch the exception, log it, and raise a clean ValueError that the
    API route converts into a 400 response.
"""

import os
import io
import uuid
from pathlib import Path

import pandas as pd
from fastapi import UploadFile

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# Result container
# =============================================================================

class FileReadResult:
    """
    Container for the output of reading an uploaded file.

    Attributes:
        dataframe       — The pandas DataFrame loaded from the file
        saved_path      — Absolute filesystem path where the file is stored
        saved_filename  — The safe, unique filename used on disk
        original_filename — The name the user gave the file (for display)
        file_type       — "csv" or "xlsx"
    """

    def __init__(
        self,
        dataframe: pd.DataFrame,
        saved_path: str,
        saved_filename: str,
        original_filename: str,
        file_type: str,
    ):
        self.dataframe = dataframe
        self.saved_path = saved_path
        self.saved_filename = saved_filename
        self.original_filename = original_filename
        self.file_type = file_type


# =============================================================================
# Safe filename generator
# =============================================================================

def _generate_safe_filename(original_filename: str, extension: str) -> str:
    """
    Generate a safe, unique filename for local storage.

    Format: <uuid4>_<sanitized_original_name><extension>

    Example:
        Input:  "patient data 2024.xlsx"
        Output: "a3f7b2c1-d4e5-...._patient_data_2024.xlsx"

    WHY UUID?
        - Globally unique → no collisions between uploads
        - No predictable pattern → prevents enumeration attacks

    WHY KEEP ORIGINAL NAME?
        - Useful for debugging and audit logs
        - Makes it clear which safe file came from which source

    Args:
        original_filename: The name provided by the user
        extension: The normalized extension (e.g., ".csv")

    Returns:
        A safe filename string.
    """
    # Sanitize original name: keep only alphanumeric, dash, underscore, dot
    base_name = os.path.splitext(original_filename)[0]
    safe_base = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)
    safe_base = safe_base[:50]  # Truncate to avoid excessively long filenames

    unique_id = str(uuid.uuid4())
    return f"{unique_id}_{safe_base}{extension}"


# =============================================================================
# Upload directory setup
# =============================================================================

def _ensure_upload_directory() -> Path:
    """
    Ensure the upload directory exists. Create it if it doesn't.

    Uses settings.UPLOAD_DIRECTORY (default: "data/uploads").
    Path is relative to the project root (where uvicorn is launched from).

    Returns:
        Path object pointing to the upload directory.
    """
    upload_dir = Path(settings.UPLOAD_DIRECTORY)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


# =============================================================================
# Main read function
# =============================================================================

async def read_uploaded_file(file: UploadFile, file_type: str, file_ext: str) -> FileReadResult:
    """
    Save an uploaded file to disk and read it into a pandas DataFrame.

    Steps:
        1. Read raw bytes from the UploadFile object
        2. Generate a safe filename
        3. Save raw bytes to data/uploads/<safe_filename>
        4. Parse the saved file into a DataFrame using pandas
        5. Return FileReadResult with both the DataFrame and file info

    Args:
        file:      FastAPI UploadFile (cursor at position 0, validator already ran)
        file_type: Clean type string — "csv" or "xlsx"
        file_ext:  Normalized extension — ".csv" or ".xlsx"

    Returns:
        FileReadResult containing the DataFrame and storage metadata.

    Raises:
        ValueError: If pandas cannot parse the file (corrupt data, bad encoding)
        OSError:    If the file cannot be saved to disk (permissions, disk full)
    """
    original_filename = file.filename or f"upload{file_ext}"

    # ── Step 1: Read raw bytes ─────────────────────────────────────────────────
    content: bytes = await file.read()
    logger.debug(f"Read {len(content)} bytes from upload | filename='{original_filename}'")

    # ── Step 2: Generate safe filename ────────────────────────────────────────
    safe_filename = _generate_safe_filename(original_filename, file_ext)

    # ── Step 3: Save to disk ──────────────────────────────────────────────────
    upload_dir = _ensure_upload_directory()
    save_path = upload_dir / safe_filename

    try:
        save_path.write_bytes(content)
        logger.info(f"File saved to disk | path='{save_path}'")
    except OSError as e:
        logger.error(f"Failed to save file to disk: {e}")
        raise OSError(f"Could not save uploaded file: {e}") from e

    # ── Step 4: Parse into DataFrame ──────────────────────────────────────────
    try:
        df = _parse_file(content, file_type, original_filename)
    except Exception as e:
        # If parsing fails, clean up the saved file (don't leave partial data)
        try:
            save_path.unlink(missing_ok=True)
        except OSError:
            pass
        logger.error(f"Failed to parse uploaded file: {e} | filename='{original_filename}'")
        raise ValueError(str(e)) from e

    logger.info(
        f"File read successfully | filename='{original_filename}' | "
        f"rows={len(df)} | columns={len(df.columns)}"
    )

    return FileReadResult(
        dataframe=df,
        saved_path=str(save_path),
        saved_filename=safe_filename,
        original_filename=original_filename,
        file_type=file_type,
    )


# =============================================================================
# Internal parser — handles CSV vs XLSX branching
# =============================================================================

def _parse_file(content: bytes, file_type: str, filename: str) -> pd.DataFrame:
    """
    Parse raw file bytes into a pandas DataFrame.

    Args:
        content:   Raw bytes of the uploaded file
        file_type: "csv" or "xlsx"
        filename:  Original filename (used in error messages only)

    Returns:
        A pandas DataFrame with all rows and columns from the file.

    Raises:
        ValueError: If the file cannot be parsed or results in an empty DataFrame.
    """
    buffer = io.BytesIO(content)

    if file_type == "csv":
        return _read_csv(buffer, filename)
    elif file_type in ("xlsx", "xls"):
        return _read_excel(buffer, filename)
    else:
        raise ValueError(f"No parser available for file type: '{file_type}'")


def _read_csv(buffer: io.BytesIO, filename: str) -> pd.DataFrame:
    """
    Read a CSV file from a bytes buffer into a DataFrame.

    Settings:
        - low_memory=False    Reads the entire file before inferring types
                              (avoids "mixed type" DtypeWarning on large files)
        - encoding detection  Tries UTF-8, then Latin-1 as a fallback

    Raises:
        ValueError if the file cannot be parsed or is empty after reading.
    """
    # Try UTF-8 first (most modern CSVs), fall back to latin-1 (legacy Windows)
    for encoding in ("utf-8", "latin-1"):
        try:
            buffer.seek(0)
            df = pd.read_csv(buffer, encoding=encoding, low_memory=False)

            _check_dataframe_not_empty(df, filename)
            logger.debug(f"CSV parsed with encoding='{encoding}' | shape={df.shape}")
            return df

        except UnicodeDecodeError:
            logger.debug(f"CSV encoding '{encoding}' failed, trying next | filename='{filename}'")
            continue
        except pd.errors.EmptyDataError:
            raise ValueError(
                f"The CSV file '{filename}' is empty or contains only a header row with no data."
            )
        except pd.errors.ParserError as e:
            raise ValueError(f"Could not parse CSV file '{filename}': {e}")

    raise ValueError(
        f"Could not decode CSV file '{filename}'. "
        "Please ensure the file is saved with UTF-8 or Latin-1 encoding."
    )


def _read_excel(buffer: io.BytesIO, filename: str) -> pd.DataFrame:
    """
    Read an Excel (.xlsx) file from a bytes buffer into a DataFrame.

    Settings:
        - engine="openpyxl"   Uses the already-installed openpyxl package
        - sheet_name=0        Reads the FIRST sheet only (index 0)
                              Multi-sheet support is a future phase feature

    Raises:
        ValueError if the file is corrupt, not a real Excel file,
        or the first sheet has no data.
    """
    try:
        buffer.seek(0)
        df = pd.read_excel(buffer, engine="openpyxl", sheet_name=0)

        _check_dataframe_not_empty(df, filename)
        logger.debug(f"Excel parsed successfully | shape={df.shape}")
        return df

    except ValueError as e:
        # openpyxl raises ValueError for corrupt or non-Excel files
        raise ValueError(f"Could not read Excel file '{filename}': {e}") from e
    except Exception as e:
        raise ValueError(
            f"Unexpected error reading Excel file '{filename}': {type(e).__name__}: {e}"
        ) from e


def _check_dataframe_not_empty(df: pd.DataFrame, filename: str) -> None:
    """
    Raise ValueError if the DataFrame has no rows or no columns.

    WHY CHECK BOTH?
        - A file with only a header row: 0 rows, N columns → no usable data
        - A truly empty file would already be caught by file_validator.py,
          but a header-only file passes the byte-size check and arrives here

    Raises:
        ValueError if the DataFrame is empty.
    """
    if df.empty or len(df.columns) == 0:
        raise ValueError(
            f"The file '{filename}' contains no data rows. "
            "Please upload a file with at least one data row below the header."
        )
