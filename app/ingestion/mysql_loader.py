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
    text,
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
    Path(r"C:\Users\sathy\OneDrive\Documents\Desktop\Jeeva\data_cleaning\csv").resolve(),
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
# Helper 1b: Target Table Name Resolver
# =============================================================================

def resolve_target_table_name(
    filename: Optional[str] = None,
    df: Optional[pd.DataFrame] = None,
    explicit_table_name: Optional[str] = None,
    engine_obj: Any = engine,
) -> str:
    """
    Deterministically resolves the target MySQL table name for an uploaded dataset.

    Order of resolution & Safety Guards:
      1. Inspect existing clinical tables and compute column compatibility for each.
      2. If explicit_table_name is provided:
         - Verify that the uploaded CSV is actually compatible with that table.
         - If compatibility is poor (< 50% column match) and another table is a strong match,
           REJECT with a clear validation error so columns are NEVER silently dropped.
      3. If Auto-Detect (explicit_table_name is None, '', or 'auto'):
         - Choose the table with the strongest valid schema match (coverage >= 70%).
         - Check for ambiguous matches; if ambiguous, verify with filename tokens or raise.
      4. Filename token match fallback against clinical tables.
      5. Safe table name sanitization fallback.
    """
    inspector = inspect(engine_obj)
    all_tables = inspector.get_table_names()
    clinical_tables = [t for t in all_tables if t not in PROTECTED_METADATA_TABLES]

    # Clean filename base by removing UUID prefix if present
    base_name = ""
    if filename:
        base = os.path.basename(filename)
        base = os.path.splitext(base)[0]
        base_name = re.sub(r"^[0-9a-fA-F\-]{36}_", "", base).strip().lower()

    # Pre-compute column compatibility across all clinical tables
    df_cols = {str(c).strip().upper() for c in df.columns} if df is not None and not df.empty else set()
    table_matches: Dict[str, Dict[str, Any]] = {}

    if df_cols and clinical_tables:
        for t in clinical_tables:
            try:
                t_cols = {col["name"].strip().upper() for col in inspector.get_columns(t)}
                if not t_cols:
                    continue
                intersection = df_cols.intersection(t_cols)
                coverage = len(intersection) / len(df_cols)
                jaccard = len(intersection) / len(df_cols.union(t_cols))
                table_matches[t] = {
                    "coverage": coverage,
                    "intersection_count": len(intersection),
                    "total_csv_cols": len(df_cols),
                    "table_cols_count": len(t_cols),
                    "score": coverage * 0.7 + jaccard * 0.3,
                }
            except Exception as e:
                logger.debug(f"Error inspecting table '{t}': {e}")

    # Check if explicit_table_name is an actual table or 'auto'
    clean_explicit = None
    if explicit_table_name and explicit_table_name.strip() and explicit_table_name.strip().lower() not in ("auto", "auto-detect", "none"):
        clean_explicit = sanitize_table_name(explicit_table_name)

    # ── Step 1: Explicit table validation & Safety Guard ──────────────────────
    if clean_explicit:
        if clean_explicit in clinical_tables and df_cols:
            explicit_info = table_matches.get(
                clean_explicit,
                {"coverage": 0.0, "intersection_count": 0, "total_csv_cols": len(df_cols)}
            )
            explicit_coverage = explicit_info["coverage"]

            # Check if another table has a significantly better match
            best_other = None
            if table_matches:
                sorted_by_score = sorted(
                    [(k, v) for k, v in table_matches.items() if k != clean_explicit],
                    key=lambda x: x[1]["score"],
                    reverse=True
                )
                if sorted_by_score:
                    best_other = sorted_by_score[0]

            # If fewer than 50% of the uploaded columns match the explicit table
            if explicit_coverage < 0.50:
                if best_other and best_other[1]["coverage"] >= 0.70:
                    raise ValueError(
                        f"Uploaded file matches '{best_other[0]}' schema ({best_other[1]['coverage']:.0%} column match), "
                        f"but the selected target table is '{clean_explicit}' (only {explicit_coverage:.0%} match: "
                        f"{explicit_info['intersection_count']} of {explicit_info['total_csv_cols']} columns). "
                        f"Please select '{best_other[0]}' or use 'Auto-Detect'."
                    )
                else:
                    raise ValueError(
                        f"Uploaded file columns do not match the schema of selected table '{clean_explicit}'. "
                        f"Only {explicit_info['intersection_count']} of {explicit_info['total_csv_cols']} columns match ({explicit_coverage:.0%}). "
                        f"Columns must not be silently dropped. Please select the correct table or use 'Auto-Detect'."
                    )

        logger.info(f"Target table validated from explicit selection: '{clean_explicit}'")
        return clean_explicit

    # ── Step 2: Auto-Detect from column schema match ─────────────────────────
    if table_matches:
        sorted_matches = sorted(table_matches.items(), key=lambda x: x[1]["score"], reverse=True)
        best_table, best_data = sorted_matches[0]

        if best_data["coverage"] >= 0.70:
            # Check for ambiguity
            if len(sorted_matches) > 1:
                second_table, second_data = sorted_matches[1]
                if second_data["coverage"] >= 0.70 and abs(best_data["score"] - second_data["score"]) < 0.05:
                    # Disambiguate using filename
                    for cand in (best_table, second_table):
                        if re.search(rf"(^|_){re.escape(cand)}(_|$)", base_name):
                            logger.info(f"Auto-detected target table with filename disambiguation: '{cand}'")
                            return cand
                    raise ValueError(
                        f"Ambiguous schema match: uploaded columns equally match '{best_table}' and '{second_table}'. "
                        f"Please explicitly select the target table."
                    )
            logger.info(f"Auto-detected target table by column schema match ({best_data['coverage']:.0%}): '{best_table}'")
            return best_table

    # ── Step 3: Filename token match fallback ────────────────────────────────
    if base_name:
        for table in sorted(clinical_tables, key=len, reverse=True):
            pattern = rf"(^|_){re.escape(table)}(_|$)"
            if re.search(pattern, base_name):
                logger.info(f"Target table resolved by filename token match: '{table}' (from '{base_name}')")
                return table

    # ── Step 4: Fallback to sanitized filename ────────────────────────────────
    fallback_name = base_name if base_name else "clinical_dataset"
    return sanitize_table_name(fallback_name)


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

    Special Handling:
      - If an object/string column contains mixed numeric and text values,
        it is stored as VARCHAR or TEXT rather than DOUBLE to prevent MySQL
        data truncation errors.
    """
    # 1. Boolean
    if series.dtype == "bool":
        return Boolean(), "BOOLEAN"
    elif col_meta and col_meta.semantic_type == "boolean":
        if pd.api.types.is_object_dtype(series.dtype) or isinstance(series.dtype, pd.StringDtype):
            non_nulls = series.dropna()
            if not non_nulls.empty:
                unique_vals = {str(x).strip().lower() for x in non_nulls.unique()}
                if unique_vals.issubset({"true", "false", "t", "f", "1", "0", "y", "n", "yes", "no"}):
                    return Boolean(), "BOOLEAN"
            else:
                return Boolean(), "BOOLEAN"
        else:
            return Boolean(), "BOOLEAN"

    # 2. Datetime or Date
    if (
        pd.api.types.is_datetime64_any_dtype(series.dtype)
        or (col_meta and col_meta.date_metadata is not None)
        or (col_meta and col_meta.semantic_type in ("date", "datetime"))
    ):
        detected = (
            col_meta.date_metadata.detected_type
            if (col_meta and col_meta.date_metadata)
            else "datetime"
        )
        if detected == "date" and col_meta and col_meta.semantic_type == "date":
            return Date(), "DATE"
        else:
            return DateTime(), "DATETIME"

    # 3. Check for Mixed Numeric / Text in Object/String columns
    # If a column has object or string dtype and was inferred as numeric,
    # verify whether it contains non-numeric text values.
    is_object_or_string = (
        pd.api.types.is_object_dtype(series.dtype)
        or isinstance(series.dtype, pd.StringDtype)
        or series.dtype == "object"
    )

    if is_object_or_string:
        non_nulls = series.dropna()
        if not non_nulls.empty:
            numeric_converted = pd.to_numeric(non_nulls, errors="coerce")
            has_non_numeric = numeric_converted.isna().any()

            if has_non_numeric:
                # Column contains mixed numeric and text or pure text;
                # must be stored as VARCHAR or TEXT rather than DOUBLE / INTEGER.
                non_null_strings = non_nulls.astype(str)
                max_len = non_null_strings.map(len).max() if not non_null_strings.empty else 0

                if max_len > 255:
                    return Text(), "TEXT"
                else:
                    return String(255), "VARCHAR(255)"
            else:
                # All non-null values in this object column are valid numbers
                if col_meta and col_meta.semantic_type == "integer" and (numeric_converted % 1 == 0).all():
                    min_val = numeric_converted.min()
                    max_val = numeric_converted.max()
                    if min_val < -2147483648 or max_val > 2147483647:
                        return BigInteger(), "BIGINT"
                    else:
                        return Integer(), "INTEGER"
                elif col_meta and col_meta.semantic_type in ("decimal", "numeric"):
                    return Double(), "DOUBLE"

    # 4. Native Integer (evaluate 32-bit vs 64-bit BigInteger)
    if pd.api.types.is_integer_dtype(series.dtype) or (
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

    # 5. Native Floating-point
    elif pd.api.types.is_float_dtype(series.dtype) or (
        col_meta and col_meta.semantic_type in ("decimal", "numeric")
    ):
        return Double(), "DOUBLE"

    # 6. String / Object / Text (fallback)
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
    table_name = resolve_target_table_name(
        filename=source_filename,
        df=df,
        explicit_table_name=custom_table_name,
    )

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

    # ── Step 5: Clean column headers, align with existing schema, and convert dates ───
    # Strip whitespace from column headers
    df.columns = [str(c).strip() for c in df.columns]

    existing_columns = inspector.get_columns(table_name) if table_exists else []
    existing_col_map = {col["name"].lower(): col["name"] for col in existing_columns}

    if table_exists and existing_col_map:
        # Align casing to match existing MySQL table columns
        df = df.rename(columns=lambda c: existing_col_map.get(str(c).strip().lower(), str(c).strip()))

        # Safety Guard: Ensure we do NOT silently drop columns
        matching_cols = [c for c in df.columns if c in existing_col_map.values()]
        dropped_cols = [c for c in df.columns if c not in existing_col_map.values()]
        if dropped_cols and len(matching_cols) < len(df.columns) * 0.50:
            raise ValueError(
                f"Cannot load into '{table_name}': {len(dropped_cols)} of {len(df.columns)} columns "
                f"do not exist in table '{table_name}' ({', '.join(dropped_cols[:5])}...). "
                f"Columns must not be silently dropped. Please select the matching table or use 'Auto-Detect'."
            )
        if matching_cols:
            df = df[matching_cols]

    # Convert date/datetime columns to native pandas datetime/date for MySQL storage
    date_col_names = set()
    if table_exists:
        for col in existing_columns:
            type_name = str(col["type"]).upper()
            if "DATE" in type_name or "TIME" in type_name:
                date_col_names.add(col["name"])

    for col_meta in analysis_report.columns:
        if col_meta.date_metadata is not None or col_meta.semantic_type in ("date", "datetime"):
            target_c = existing_col_map.get(col_meta.name.lower(), col_meta.name)
            date_col_names.add(target_c)

    for c in df.columns:
        if c in date_col_names or c.upper() in ("START", "STOP", "BIRTHDATE", "DEATHDATE", "DATE"):
            try:
                df[c] = pd.to_datetime(df[c], errors="coerce")
                target_col_info = next((col for col in existing_columns if col["name"] == c), None)
                if target_col_info and str(target_col_info["type"]).upper() == "DATE":
                    df[c] = df[c].dt.date
            except Exception as e:
                logger.warning(f"Could not convert column '{c}' to date/datetime: {e}")

    # Track row metrics for transparent user reporting
    rows_received = len(df)
    rows_skipped = 0
    rows_failed = 0

    # Deduplicate candidate IDs if appending to existing table with an ID column
    id_col = None
    for cand in ("ID", "id", "Id"):
        if cand in df.columns:
            id_col = cand
            break

    if id_col:
        file_dup_count = int(df.duplicated(subset=[id_col]).sum())
        if file_dup_count > 0:
            logger.info(f"Filtering out {file_dup_count} duplicate rows within uploaded file on column '{id_col}'")
            rows_skipped += file_dup_count
            df = df.drop_duplicates(subset=[id_col], keep="last")

        if table_exists and if_exists == "append":
            try:
                candidate_ids = [str(x).strip() for x in df[id_col].dropna().unique() if str(x).strip()]
                if candidate_ids:
                    with engine.connect() as conn:
                        existing_ids = set()
                        for i in range(0, len(candidate_ids), 1000):
                            batch = candidate_ids[i:i+1000]
                            placeholders = ", ".join([f":id_{j}" for j in range(len(batch))])
                            params = {f"id_{j}": val for j, val in enumerate(batch)}
                            q = text(f"SELECT `{id_col}` FROM `{table_name}` WHERE `{id_col}` IN ({placeholders})")
                            res = conn.execute(q, params)
                            for r in res.fetchall():
                                existing_ids.add(str(r[0]).strip())

                        if existing_ids:
                            logger.info(
                                f"Skipping {len(existing_ids)} rows because IDs already exist in '{table_name}'"
                            )
                            rows_skipped += len(existing_ids)
                            df = df[~df[id_col].astype(str).str.strip().isin(existing_ids)]
            except Exception as e:
                logger.warning(f"Could not check existing IDs for table '{table_name}': {e}")

    rows_inserted = len(df)

    # ── Step 6: Map dtypes deterministically ──────────────────────────────────
    sqlalchemy_dtypes, sql_type_strings = map_pandas_to_sqlalchemy_dtypes(
        df=df,
        col_analyses=analysis_report.columns,
    )

    # ── Step 7: Load DataFrame into MySQL ────────────────────────────────────
    load_start = datetime.utcnow()
    logger.info(
        f"Writing {rows_inserted:,} rows × {len(df.columns)} cols to MySQL table '{table_name}' "
        f"with mode if_exists='{if_exists}' (received={rows_received}, skipped={rows_skipped})..."
    )

    try:
        if rows_inserted > 0:
            # If table already exists and appending, let MySQL's established column types govern
            to_sql_dtype = None if (table_exists and if_exists == "append") else sqlalchemy_dtypes
            load_dataframe_to_mysql(
                df=df,
                table_name=table_name,
                con=engine,
                if_exists=if_exists,
                dtype=to_sql_dtype,
                chunksize=5000,
            )
            logger.info(f"Successfully loaded {rows_inserted:,} rows into MySQL table '{table_name}'.")
        else:
            logger.info(f"Zero new rows to insert into '{table_name}' (all candidate rows already exist).")

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
            row_count=rows_inserted,
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
            f"Upload completed. Target table: '{table_name}'. "
            f"Rows received: {rows_received}, Rows inserted: {rows_inserted}, "
            f"Rows skipped: {rows_skipped}, Rows failed: {rows_failed}."
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
            "rows_loaded": rows_inserted,
            "rows_received": rows_received,
            "rows_inserted": rows_inserted,
            "rows_skipped": rows_skipped,
            "rows_failed": rows_failed,
            "columns_loaded": len(df.columns),
            "dataset_version_id": version_rec.id,
            "version_number": version_rec.version_number,
            "loaded_at": version_rec.loaded_at or load_start,
        }
