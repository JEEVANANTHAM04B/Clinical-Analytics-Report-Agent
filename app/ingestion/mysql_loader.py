"""
app/ingestion/mysql_loader.py
==============================
Clinical Dataset MySQL Loader for Phase 5

WHY THIS MODULE EXISTS:
    Coordinates loading validated clinical datasets into MySQL:
      1. Deterministic, safe table-name generation and validation
      2. Deterministic Pandas -> MySQL/SQLAlchemy data type mapping
      3. Full validation pipeline enforcement prior to loading
      4. Batch persistence into MySQL using pandas.to_sql() + SQLAlchemy engine
      5. Metadata persistence (dataset_versions, dataset_columns, audit_logs)

SECURITY & ARCHITECTURAL GUARANTEES:
    - Never uses raw string-built SQL for bulk data insertion.
    - Deterministic operations only: NO LLMs, NO probabilistic guessing.
    - Table names are strictly sanitized against SQL keywords and special characters.
    - Platform metadata tables are protected and cannot be overwritten.
    - Filesystem access is strictly restricted to allowed directories.
    - Credentials are never logged or returned in responses.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
from sqlalchemy import (
    inspect,
    Integer,
    BigInteger,
    Double,
    Boolean,
    DateTime,
    Date,
    String,
    Text,
)
from sqlalchemy.types import TypeEngine
from sqlalchemy.orm import Session

from app.core.database import engine, get_db_context
from app.core.logging_config import get_logger
from app.schemas.validation import DatasetAnalysis, ColumnAnalysis
from app.ingestion.analyzer import analyze_single_dataset
from app.database.repository import (
    create_dataset_version,
    save_dataset_columns,
    create_audit_log,
)

logger = get_logger(__name__)

# =============================================================================
# Reserved Words and Protected Tables
# =============================================================================

PROTECTED_METADATA_TABLES = {
    "dataset_versions",
    "dataset_columns",
    "approved_relationships",
    "audit_logs",
}

MYSQL_RESERVED_WORDS = {
    "accessible", "add", "all", "alter", "analyze", "and", "as", "asc", "asensitive",
    "before", "between", "bigint", "binary", "blob", "both", "by", "call", "cascade",
    "case", "change", "char", "character", "check", "collate", "column", "condition",
    "constraint", "continue", "convert", "create", "cross", "cube", "cume_dist",
    "current_date", "current_time", "current_timestamp", "current_user", "cursor",
    "database", "databases", "day_hour", "day_microsecond", "day_minute", "day_second",
    "dec", "decimal", "declare", "default", "delayed", "delete", "dense_rank", "desc",
    "describe", "deterministic", "distinct", "distinctrow", "div", "double", "drop",
    "dual", "each", "else", "elseif", "empty", "enclosed", "escaped", "except", "exists",
    "exit", "explain", "false", "fetch", "first_value", "float", "float4", "float8",
    "for", "force", "foreign", "from", "fulltext", "function", "group", "grouping",
    "groups", "having", "high_priority", "hour_microsecond", "hour_minute", "hour_second",
    "if", "ignore", "in", "index", "infile", "inner", "inout", "insensitive", "insert",
    "int", "int1", "int2", "int3", "int4", "int8", "integer", "intersect", "interval",
    "into", "io_after_gtids", "io_before_gtids", "is", "iterate", "join", "json_table",
    "key", "keys", "kill", "lag", "last_value", "lateral", "lead", "leading", "leave",
    "left", "like", "limit", "linear", "lines", "load", "localtime", "localtimestamp",
    "lock", "long", "longblob", "longtext", "loop", "low_priority", "master_bind",
    "match", "maxvalue", "mediumblob", "mediumint", "mediumtext", "middleint",
    "minute_microsecond", "minute_second", "mod", "modifies", "natural", "not",
    "nth_value", "ntile", "null", "numeric", "of", "on", "optimize", "option",
    "or", "order", "out", "outer", "outfile", "over", "partition", "precision",
    "primary", "procedure", "purge", "range", "rank", "read", "reads", "real",
    "references", "regexp", "release", "rename", "repeat", "replace", "require",
    "restrict", "return", "revoke", "right", "rlike", "row", "rows", "schema",
    "schemas", "select", "sensitive", "separator", "set", "show", "signal",
    "smallint", "spatial", "specific", "sql", "ssl", "starting", "stored",
    "straight_join", "system", "table", "terminated", "then", "tinyblob", "tinyint",
    "tinytext", "to", "trailing", "trigger", "true", "undo", "union", "unique",
    "unlock", "unsigned", "update", "usage", "use", "using", "utc_date", "utc_time",
    "utc_timestamp", "values", "varbinary", "varchar", "varying", "virtual", "when",
    "where", "while", "window", "with", "write", "xor", "year_month", "zerofill"
}

ALLOWED_DIRECTORIES = [
    Path("data/sample").resolve(),
    Path("data/uploads").resolve(),
    Path(r"C:\Users\sathy\OneDrive\Documents\Desktop\Office Bootcamp\Dataset\CSV Dataset").resolve(),
    Path(r"..\Dataset\CSV Dataset").resolve(),
]


# =============================================================================
# Helper 1: Safe Table-Name Handling
# =============================================================================

def sanitize_table_name(input_name: str) -> str:
    """
    Converts a dataset name or filename into a safe, valid MySQL identifier.

    Rules:
      1. Strip directory paths and file extensions (.csv, .xlsx).
      2. Lowercase all characters.
      3. Replace non-alphanumeric characters with underscores.
      4. Collapse consecutive underscores and strip leading/trailing underscores.
      5. Prefix with 'tbl_' if the name starts with a digit or matches a MySQL reserved word.
      6. Enforce maximum MySQL identifier length (64 characters).
      7. Reject empty strings or protected platform metadata table names.
    """
    if not input_name or not isinstance(input_name, str):
        raise ValueError("Dataset or table name must be a non-empty string.")

    # Remove path and extension
    base = os.path.basename(input_name)
    base = os.path.splitext(base)[0]

    # Lowercase
    clean = base.strip().lower()

    # Replace special chars and spaces with underscore
    clean = re.sub(r"[^a-z0-9_]", "_", clean)

    # Collapse multiple underscores
    clean = re.sub(r"_+", "_", clean).strip("_")

    if not clean:
        raise ValueError(f"Input '{input_name}' could not be sanitized into a valid MySQL table name.")

    # Must not start with a digit
    if clean[0].isdigit():
        clean = f"tbl_{clean}"

    # Avoid MySQL reserved keywords
    if clean in MYSQL_RESERVED_WORDS:
        clean = f"tbl_{clean}"

    # Enforce 64-char limit
    clean = clean[:64]

    # Guard against accidental overwrite of platform metadata tables
    if clean in PROTECTED_METADATA_TABLES:
        raise ValueError(
            f"Table name '{clean}' conflicts with reserved platform metadata table. "
            f"Protected tables: {', '.join(PROTECTED_METADATA_TABLES)}"
        )

    return clean


# =============================================================================
# Helper 2: Safe File Path Resolver
# =============================================================================

def resolve_safe_file_path(
    filename: Optional[str] = None,
    file_path: Optional[str] = None,
) -> str:
    """
    Resolves a dataset file path while strictly preventing directory traversal.

    Permitted search locations:
      - data/sample/
      - data/uploads/
      - Real dataset directory (if present on local system)

    Raises:
      ValueError: If neither filename nor file_path is provided, or if path traversal is detected.
      FileNotFoundError: If the specified file does not exist.
    """
    if not filename and not file_path:
        raise ValueError("Either 'filename' or 'file_path' must be provided.")

    resolved_path: Optional[Path] = None

    if file_path:
        candidate = Path(file_path).resolve()
        # Verify candidate resides within an allowed directory
        is_allowed = any(
            str(candidate).lower().startswith(str(d).lower())
            for d in ALLOWED_DIRECTORIES
            if d.exists()
        )
        if not is_allowed:
            raise ValueError(
                f"Security violation: Access denied to path '{file_path}'. "
                f"Files must be located within data/sample/, data/uploads/, or configured dataset directory."
            )
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError(f"Dataset file not found at: '{file_path}'")
        resolved_path = candidate

    elif filename:
        # Search allowed directories in priority order
        clean_fn = os.path.basename(filename)  # Strip any sneaky path prefix
        for d in ALLOWED_DIRECTORIES:
            if d.exists() and d.is_dir():
                cand = (d / clean_fn).resolve()
                if cand.exists() and cand.is_file():
                    resolved_path = cand
                    break

        if not resolved_path:
            raise FileNotFoundError(
                f"Dataset file '{clean_fn}' not found in any allowed directories: "
                f"data/sample/, data/uploads/, or dataset directory."
            )

    # Final extension check
    if resolved_path.suffix.lower() not in (".csv", ".xlsx"):
        raise ValueError(
            f"Unsupported file type: '{resolved_path.suffix}'. Only .csv and .xlsx datasets can be loaded."
        )

    return str(resolved_path)


# =============================================================================
# =============================================================================
# Helper 3: Deterministic Type Mapping (Pandas -> SQLAlchemy/MySQL)
# =============================================================================

def map_pandas_dtype(
    series: pd.Series,
    col_meta: Optional[ColumnAnalysis] = None,
) -> Tuple[TypeEngine, str]:
    """
    Deterministically maps a single pandas Series and optional ColumnAnalysis
    to a SQLAlchemy TypeEngine and a SQL type string.
    """
    # 1. Boolean
    if series.dtype == "bool" or (col_meta and col_meta.semantic_type == "boolean"):
        return Boolean(), "BOOLEAN"

    # 2. Integer (evaluate 32-bit vs 64-bit BigInteger)
    elif pd.api.types.is_integer_dtype(series.dtype) or (
        col_meta and col_meta.semantic_type == "integer"
    ):
        non_nulls = series.dropna()
        min_val = non_nulls.min() if not non_nulls.empty else 0
        max_val = non_nulls.max() if not non_nulls.empty else 0

        # MySQL standard INTEGER is -2147483648 to 2147483647
        if min_val < -2147483648 or max_val > 2147483647 or series.dtype == "int64":
            return BigInteger(), "BIGINT"
        else:
            return Integer(), "INTEGER"

    # 3. Floating-point
    elif pd.api.types.is_float_dtype(series.dtype) or (
        col_meta and col_meta.semantic_type in ("decimal", "numeric")
    ):
        return Double(), "DOUBLE"

    # 4. Datetime or Date
    elif (
        pd.api.types.is_datetime64_any_dtype(series.dtype)
        or (col_meta and col_meta.date_metadata is not None)
        or (col_meta and col_meta.semantic_type in ("date", "datetime"))
    ):
        detected = col_meta.date_metadata.detected_type if (col_meta and col_meta.date_metadata) else "datetime"
        if detected == "date" and col_meta.semantic_type == "date":
            return Date(), "DATE"
        else:
            return DateTime(), "DATETIME"

    # 5. String / Object / Text
    else:
        # Check maximum string length to choose VARCHAR vs TEXT
        non_null_strings = series.dropna().astype(str)
        max_len = non_null_strings.map(len).max() if not non_null_strings.empty else 0

        if max_len > 255:
            return Text(), "TEXT"
        else:
            return String(255), "VARCHAR(255)"


def map_pandas_to_sqlalchemy_dtypes(
    df: pd.DataFrame,
    col_analyses: Optional[List[ColumnAnalysis]] = None,
) -> Tuple[Dict[str, TypeEngine], Dict[str, str]]:
    """
    Deterministically maps Pandas DataFrame columns to SQLAlchemy types for MySQL.

    Returns:
      1. sqlalchemy_dtypes: Dict[col_name, SQLAlchemy TypeEngine] for pandas.to_sql(dtype=...)
      2. sql_type_strings: Dict[col_name, str] representation to store in dataset_columns
    """
    sqlalchemy_dtypes: Dict[str, TypeEngine] = {}
    sql_type_strings: Dict[str, str] = {}

    analysis_by_col = {c.name: c for c in (col_analyses or [])}

    for col in df.columns:
        col_name = str(col)
        series = df[col]
        col_meta = analysis_by_col.get(col_name)

        sa_type, type_str = map_pandas_dtype(series, col_meta)
        sqlalchemy_dtypes[col_name] = sa_type
        sql_type_strings[col_name] = type_str

    return sqlalchemy_dtypes, sql_type_strings


def load_dataframe_to_mysql(
    df: pd.DataFrame,
    table_name: str,
    con: Any = engine,
    if_exists: str = "fail",
    dtype: Optional[Dict[str, TypeEngine]] = None,
    chunksize: int = 5000,
) -> int:
    """
    Loads a pandas DataFrame directly into MySQL using pandas.to_sql and the provided engine/connection.
    Returns the number of rows loaded.
    """
    df.to_sql(
        name=table_name,
        con=con,
        if_exists=if_exists,
        index=False,
        dtype=dtype,
        chunksize=chunksize,
    )
    return len(df)


# =============================================================================
# Core Loader Function
# =============================================================================

def load_dataset_to_mysql(
    filename: Optional[str] = None,
    file_path: Optional[str] = None,
    custom_table_name: Optional[str] = None,
    if_exists: str = "fail",
) -> Dict[str, Any]:
    """
    Validates, profiles, and loads a clinical dataset into MySQL.

    Workflow:
      1. Resolve file safely within allowed directories.
      2. Execute Phase 2/3 analysis pipeline (schema profiling, quality flags, null checks).
      3. Sanitize dataset or custom name into a valid MySQL table name.
      4. Prepare DataFrame: parse dates to native datetime, clean column headers.
      5. Deterministically map Pandas dtypes to SQLAlchemy/MySQL types.
      6. Insert data into MySQL using pandas.to_sql(chunksize=5000).
      7. Record DatasetVersion, DatasetColumn metadata, and AuditLog.

    Args:
      filename: Dataset filename (e.g. 'sample_clinical_data.csv').
      file_path: Explicit path within allowed directories.
      custom_table_name: Optional custom table name (will still be sanitized).
      if_exists: 'fail' (default), 'replace', or 'append'.

    Returns:
      Dict with table_name, rows_loaded, columns_loaded, version_id, loaded_at.
    """
    # ── Step 1: Resolve file path safely ─────────────────────────────────────
    safe_path = resolve_safe_file_path(filename=filename, file_path=file_path)
    source_filename = os.path.basename(safe_path)
    source_file_ext = Path(safe_path).suffix.lower()

    logger.info(f"Initiating MySQL dataset load for: '{source_filename}' (path: {safe_path})")

    # ── Step 2: Validate & Analyze Dataset ───────────────────────────────────
    # Run full Phase 2/3 validation and schema inference pipeline
    analysis_report, df = analyze_single_dataset(safe_path)

    if len(df) == 0:
        raise ValueError(f"Cannot load empty dataset '{source_filename}'. Zero data rows detected.")

    # ── Step 3: Determine and sanitize MySQL table name ──────────────────────
    target_table_name = custom_table_name if custom_table_name else analysis_report.dataset_name
    table_name = sanitize_table_name(target_table_name)

    # ── Step 4: Check if table already exists in MySQL ────────────────────────
    inspector = inspect(engine)
    table_exists = inspector.has_table(table_name)

    if table_exists and if_exists == "fail":
        msg = (
            f"Table '{table_name}' already exists in MySQL database 'clinical_analytics_db'. "
            f"Specify if_exists='replace' to overwrite or 'append' to add rows."
        )
        logger.warning(msg)
        raise ValueError(msg)

    # ── Step 5: Clean column headers and convert dates ───────────────────────
    # Strip whitespace from column headers
    df.columns = [str(c).strip() for c in df.columns]

    # Convert date/datetime columns to native pandas datetime so MySQL stores them natively
    for col_meta in analysis_report.columns:
        if col_meta.name in df.columns:
            if col_meta.date_metadata is not None or col_meta.semantic_type in ("date", "datetime"):
                try:
                    df[col_meta.name] = pd.to_datetime(df[col_meta.name], errors="coerce")
                    logger.debug(f"Converted column '{col_meta.name}' to datetime for native MySQL storage.")
                except Exception as e:
                    logger.warning(f"Could not convert column '{col_meta.name}' to datetime: {e}")

    # ── Step 6: Map dtypes deterministically ──────────────────────────────────
    sqlalchemy_dtypes, sql_type_strings = map_pandas_to_sqlalchemy_dtypes(
        df=df,
        col_analyses=analysis_report.columns,
    )

    # ── Step 7: Load DataFrame into MySQL ────────────────────────────────────
    load_start = datetime.utcnow()
    logger.info(
        f"Writing {len(df):,} rows × {len(df.columns)} cols to MySQL table '{table_name}' "
        f"with mode if_exists='{if_exists}'..."
    )

    try:
        # Bulk load using helper
        load_dataframe_to_mysql(
            df=df,
            table_name=table_name,
            con=engine,
            if_exists=if_exists,
            dtype=sqlalchemy_dtypes,
            chunksize=5000,
        )
        logger.info(f"Successfully loaded {len(df):,} rows into MySQL table '{table_name}'.")

    except Exception as e:
        logger.exception(f"Failed to write dataset to MySQL table '{table_name}': {e}")
        # Log failure to audit log
        try:
            with get_db_context() as db:
                create_audit_log(
                    db=db,
                    action="DATASET_LOAD",
                    entity_type="TABLE",
                    entity_name=table_name,
                    status="FAILED",
                    message=f"Failed loading {source_filename}: {str(e)[:500]}",
                )
        except Exception:
            pass
        raise RuntimeError(f"Database insertion failed for table '{table_name}': {e}")

    # ── Step 8: Persist Metadata to MySQL ────────────────────────────────────
    with get_db_context() as db:
        # 1. DatasetVersion record
        version_rec = create_dataset_version(
            db=db,
            dataset_name=table_name,
            source_filename=source_filename,
            source_file_type=source_file_ext,
            row_count=len(df),
            column_count=len(df.columns),
            status="LOADED",
        )

        # 2. DatasetColumn metadata records
        cols_meta_list: List[Dict[str, Any]] = []
        for col_meta in analysis_report.columns:
            if col_meta.name in df.columns:
                cols_meta_list.append({
                    "column_name": col_meta.name,
                    "data_type": sql_type_strings.get(col_meta.name, "VARCHAR(255)"),
                    "semantic_type": col_meta.semantic_type,
                    "nullable": (col_meta.null_count > 0 or not col_meta.is_primary_key_candidate),
                    "missing_count": col_meta.null_count,
                    "missing_percentage": col_meta.null_percentage,
                    "is_primary_key_candidate": col_meta.is_primary_key_candidate,
                })

        save_dataset_columns(
            db=db,
            dataset_version_id=version_rec.id,
            dataset_name=table_name,
            columns_metadata=cols_meta_list,
        )

        # 3. Platform AuditLog entry
        audit_msg = (
            f"Successfully loaded {len(df):,} rows and {len(df.columns)} columns "
            f"from '{source_filename}' into MySQL table '{table_name}' (Version {version_rec.version_number})."
        )
        create_audit_log(
            db=db,
            action="DATASET_LOAD",
            entity_type="TABLE",
            entity_name=table_name,
            status="SUCCESS",
            message=audit_msg,
        )

        return {
            "status": "success",
            "message": audit_msg,
            "table_name": table_name,
            "rows_loaded": len(df),
            "columns_loaded": len(df.columns),
            "dataset_version_id": version_rec.id,
            "version_number": version_rec.version_number,
            "loaded_at": version_rec.loaded_at or load_start,
        }
