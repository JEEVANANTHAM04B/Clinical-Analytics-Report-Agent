"""
app/ingestion/analyzer.py
=========================
Core Analysis Orchestrator for Phase 3 Data Quality & Schema Validation

WHY THIS EXISTS:
    Coordinates reading, profiling, relational evaluation, and quality flag
    generation across single or multiple clinical datasets.

PERFORMANCE DESIGN:
    - Loads each CSV/XLSX file exactly ONCE into memory.
    - Uses vectorized pandas operations for null counts, uniqueness, duplicates,
      numeric statistics, and date parsing.
    - Referential checks use in-memory Python hash sets for O(1) membership lookups.
    - Memory is managed carefully and no data is written back to the source files.
"""

import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import pandas as pd

from app.ingestion.relationship_review import set_relationship_candidates

from app.core.logging_config import get_logger
from app.schemas.validation import (
    ColumnAnalysis,
    DatasetAnalysis,
    RelationshipAnalysis,
    OverallQuality,
    AnalyzeResponse,
)
from app.ingestion.schema_inference import (
    profile_column,
    analyze_observations_special,
)
from app.ingestion.relationship_detector import (
    find_primary_key_candidates,
    detect_relationships_across_datasets,
)


logger = get_logger(__name__)


# =============================================================================
# Helper: Build Quality Flags for a Dataset
# =============================================================================

def generate_dataset_quality_flags(
    df: pd.DataFrame,
    columns: List[ColumnAnalysis],
    duplicate_rows: int,
    empty_cols: List[str],
    constant_cols: List[str],
    sensitive_cols: list,
    pk_candidates: list,
    filename: str,
) -> List[str]:
    """Generates human-readable, severity-ranked quality flags for an individual dataset."""

    flags: List[str] = []
    total_rows = len(df)

    # 1. Row count flags
    if total_rows == 0:
        flags.append("CRITICAL: Dataset contains 0 rows.")

    elif total_rows < 10:
        flags.append(
            f"WARNING: Dataset contains only {total_rows} rows. "
            f"Statistical results may not be representative."
        )

    else:
        flags.append(
            f"INFO: Successfully parsed {total_rows:,} rows "
            f"across {len(columns)} columns."
        )

    # 2. Duplicate rows
    if duplicate_rows > 0:
        pct = round(
            duplicate_rows / total_rows * 100.0,
            2,
        )

        flags.append(
            f"WARNING: {duplicate_rows:,} duplicate row(s) detected "
            f"({pct}% of dataset)."
        )

    # 3. Empty columns (100% null)
    for col in empty_cols:
        flags.append(
            f"WARNING: Column '{col}' is 100% empty "
            f"(contains only null/missing values)."
        )

    # 4. Constant columns (1 unique value)
    for col in constant_cols:
        flags.append(
            f"INFO: Column '{col}' is constant "
            f"(contains exactly 1 unique value across all rows)."
        )

    # 5. Missing values per column
    for col in columns:

        if col.null_percentage > 50.0 and not col.is_all_null:
            flags.append(
                f"WARNING: Column '{col.name}' contains "
                f"{col.null_percentage}% missing values "
                f"({col.null_count:,} nulls)."
            )

        elif 5.0 <= col.null_percentage <= 50.0:
            flags.append(
                f"INFO: Column '{col.name}' contains "
                f"{col.null_percentage}% missing values "
                f"({col.null_count:,} nulls)."
            )

    # 6. Primary Key Candidates
    if pk_candidates:

        high_conf = [
            pk.column
            for pk in pk_candidates
            if pk.confidence == "HIGH"
        ]

        if high_conf:
            flags.append(
                "INFO: High-confidence Primary Key candidate identified: "
                f"{', '.join(high_conf)} (100% unique, 0 nulls)."
            )

    else:
        flags.append(
            "WARNING: No column satisfies strict Primary Key criteria "
            "(unique, non-null ID)."
        )

    # 7. Sensitive / Direct Identifier Columns
    if sensitive_cols:

        sens_names = [
            s.column
            for s in sensitive_cols
        ]

        flags.append(
            "WARNING: Potential sensitive direct-identifier columns "
            f"detected: {', '.join(sens_names)}. "
            "Requires masking/safeguards."
        )

    return flags


# =============================================================================
# Read Dataset Schema Only
# =============================================================================

def read_dataset_schema(
    file_path: str,
) -> tuple[str, list[str]]:
    """
    Reads only the dataset header/schema without loading the full dataset.

    Returns:
        (dataset_name, column_names)
    """

    path_obj = Path(file_path)

    filename = path_obj.name

    file_ext = path_obj.suffix.lower().lstrip(".")

    dataset_name = (
        path_obj.stem
        .lower()
        .replace("analytics_", "")
    )

    if file_ext == "csv":

        try:

            header_df = pd.read_csv(
                file_path,
                nrows=0,
                encoding="utf-8",
            )

        except UnicodeDecodeError:

            header_df = pd.read_csv(
                file_path,
                nrows=0,
                encoding="latin-1",
            )

    elif file_ext in ("xlsx", "xls"):

        header_df = pd.read_excel(
            file_path,
            engine="openpyxl",
            nrows=0,
        )

    else:

        raise ValueError(
            f"Unsupported file type '.{file_ext}' for schema reading."
        )

    return dataset_name, list(header_df.columns)


# =============================================================================
# Single Dataset Analysis
# =============================================================================

def analyze_single_dataset(
    file_path: str,
    df: Optional[pd.DataFrame] = None,
) -> Tuple[DatasetAnalysis, pd.DataFrame]:
    """
    Performs full schema and data quality analysis on a single dataset file.

    If df is not provided, reads the file from disk (read-only).

    Returns:
        (DatasetAnalysis, df)
    """

    path_obj = Path(file_path)

    filename = path_obj.name

    file_ext = path_obj.suffix.lower().lstrip(".")

    # Determine logical dataset name
    dataset_name = (
        path_obj.stem
        .lower()
        .replace("analytics_", "")
    )

    # Read if not provided
    if df is None:

        logger.info(
            f"Reading dataset for analysis: {filename}"
        )

        if file_ext == "csv":

            try:

                df = pd.read_csv(
                    file_path,
                    low_memory=False,
                    encoding="utf-8",
                )

            except UnicodeDecodeError:

                df = pd.read_csv(
                    file_path,
                    low_memory=False,
                    encoding="latin-1",
                )

        elif file_ext in ("xlsx", "xls"):

            df = pd.read_excel(
                file_path,
                engine="openpyxl",
            )

        else:

            raise ValueError(
                f"Unsupported file type '.{file_ext}' for analysis."
            )

    total_rows = len(df)

    total_cols = len(df.columns)

    col_names = list(df.columns)

    # 1. Duplicate row check
    duplicate_rows = int(
        df.duplicated().sum()
    )

    duplicate_pct = (
        round(
            duplicate_rows / total_rows * 100.0,
            2,
        )
        if total_rows > 0
        else 0.0
    )

    # 2. Profile each column
    columns_analysis: List[ColumnAnalysis] = []

    empty_cols: List[str] = []

    constant_cols: List[str] = []

    date_cols: List[str] = []

    for col_name in col_names:

        col_prof = profile_column(
            df[col_name],
            col_name,
            total_rows,
        )

        columns_analysis.append(
            col_prof
        )

        if col_prof.is_all_null:
            empty_cols.append(col_name)

        elif col_prof.is_constant:
            constant_cols.append(col_name)

        if col_prof.semantic_type in (
            "date",
            "datetime",
        ):
            date_cols.append(col_name)

    # 3. Primary Key Candidates
    pk_candidates = find_primary_key_candidates(
        df,
        dataset_name,
    )

    # 4. Sensitive direct-identifier columns
    sensitive_cols = [
        c.sensitive_details
        for c in columns_analysis
        if c.sensitive_details is not None
    ]

    # 5. Observations special handling
    observations_analysis = None

    if (
        "observation" in dataset_name
        or "VALUE" in col_names
    ):

        observations_analysis = (
            analyze_observations_special(df)
        )

    # 6. Quality flags
    quality_flags = generate_dataset_quality_flags(
        df=df,
        columns=columns_analysis,
        duplicate_rows=duplicate_rows,
        empty_cols=empty_cols,
        constant_cols=constant_cols,
        sensitive_cols=sensitive_cols,
        pk_candidates=pk_candidates,
        filename=filename,
    )

    analysis = DatasetAnalysis(
        filename=filename,
        dataset_name=dataset_name,
        file_path=str(file_path),
        file_type=file_ext,
        row_count=total_rows,
        column_count=total_cols,
        column_names=col_names,
        columns=columns_analysis,
        duplicate_row_count=duplicate_rows,
        duplicate_row_percentage=duplicate_pct,
        empty_columns=empty_cols,
        constant_columns=constant_cols,
        date_columns=date_cols,
        primary_key_candidates=pk_candidates,
        potential_sensitive_columns=sensitive_cols,
        observations_analysis=observations_analysis,
        quality_flags=quality_flags,
    )

    return analysis, df


# =============================================================================
# Multi-Dataset Analysis Orchestrator
# =============================================================================

def analyze_datasets(
    file_paths: List[str],
) -> AnalyzeResponse:
    """
    Analyzes multiple datasets:

      1. Loads each dataset once and extracts schema + quality profiling.
      2. Validates relational integrity / foreign key candidates across all tables.
      3. Registers detected relationships for human review.
      4. Aggregates global quality metrics and flags.
    """

    dataset_reports: List[DatasetAnalysis] = []

    loaded_dfs: Dict[
        str,
        Tuple[str, pd.DataFrame],
    ] = {}

    total_rows_all = 0

    total_cols_all = 0

    total_dupes_all = 0

    total_missing_all = 0

    total_sensitive_all = 0

    # -------------------------------------------------------------------------
    # Analyze every dataset
    # -------------------------------------------------------------------------

    for fpath in file_paths:

        report, df = analyze_single_dataset(
            fpath
        )

        dataset_reports.append(
            report
        )

        loaded_dfs[
            report.dataset_name
        ] = (
            report.filename,
            df,
        )

        total_rows_all += report.row_count

        total_cols_all += report.column_count

        total_dupes_all += report.duplicate_row_count

        total_missing_all += sum(
            c.null_count
            for c in report.columns
        )

        total_sensitive_all += len(
            report.potential_sensitive_columns
        )

    # -------------------------------------------------------------------------
    # Evaluate relational integrity
    # -------------------------------------------------------------------------

    relationships = (
        detect_relationships_across_datasets(
            loaded_dfs
        )
    )

    # -------------------------------------------------------------------------
    # Calculate relationship metrics
    # -------------------------------------------------------------------------

    valid_rels = sum(
        1
        for r in relationships
        if r.status in (
            "VALID",
            "VALID_WITH_NULLS",
        )
    )

    violating_rels = sum(
        1
        for r in relationships
        if r.status == "VIOLATION"
    )

    # -------------------------------------------------------------------------
    # Register detected relationships for human review
    #
    # IMPORTANT:
    # This must happen after detection and before the AnalyzeResponse
    # is returned so the relationship review API can access the candidates.
    # -------------------------------------------------------------------------

    set_relationship_candidates(
        relationships
    )

    # -------------------------------------------------------------------------
    # Overall Quality Flags
    # -------------------------------------------------------------------------

    overall_flags: List[str] = []

    overall_flags.append(
        f"INFO: Analyzed "
        f"{len(dataset_reports)} relational dataset(s) "
        f"containing {total_rows_all:,} total records."
    )

    if total_dupes_all == 0:

        overall_flags.append(
            "INFO: Zero duplicate rows detected "
            "across all datasets."
        )

    else:

        overall_flags.append(
            f"WARNING: {total_dupes_all:,} duplicate row(s) "
            f"detected across datasets."
        )

    if relationships:

        if violating_rels == 0:

            overall_flags.append(
                f"INFO: All {len(relationships)} evaluated "
                f"foreign-key relationships verified with "
                f"100% referential integrity."
            )

        else:

            overall_flags.append(
                f"WARNING: {violating_rels} foreign-key "
                f"relationship(s) contain unmatched/orphaned records."
            )

    if total_sensitive_all > 0:

        overall_flags.append(
            f"WARNING: {total_sensitive_all} direct or "
            f"quasi-identifier column(s) detected requiring "
            f"HIPAA/privacy protection."
        )

    # -------------------------------------------------------------------------
    # Overall Quality Object
    # -------------------------------------------------------------------------

    overall_quality = OverallQuality(
        total_datasets=len(
            dataset_reports
        ),
        total_rows=total_rows_all,
        total_columns=total_cols_all,
        total_duplicate_rows=total_dupes_all,
        total_missing_cells=total_missing_all,
        relationships_evaluated=len(
            relationships
        ),
        relationships_valid=valid_rels,
        relationships_with_violations=violating_rels,
        total_sensitive_columns=total_sensitive_all,
        quality_flags=overall_flags,
    )

    # -------------------------------------------------------------------------
    # Final message
    # -------------------------------------------------------------------------

    message = (
        f"Successfully analyzed "
        f"{len(dataset_reports)} dataset(s) "
        f"with {total_rows_all:,} rows. "
        f"{len(relationships)} relational foreign-key "
        f"candidate(s) evaluated ({valid_rels} valid)."
    )

    # -------------------------------------------------------------------------
    # Return final analysis response
    # -------------------------------------------------------------------------

    return AnalyzeResponse(
        status="success",
        message=message,
        datasets=dataset_reports,
        relationships=relationships,
        overall_quality=overall_quality,
    )


# =============================================================================
# Helper: Resolve Dataset Files from Request
# =============================================================================

DEFAULT_CANDIDATE_DIRS = [
    r"C:\Users\sathy\OneDrive\Documents\Desktop\Office Bootcamp\Dataset\CSV Dataset",
    r"..\Dataset\CSV Dataset",
    r"data/sample",
    r"data/uploads",
]


def resolve_files_to_analyze(
    directory_path: Optional[str] = None,
    file_paths: Optional[List[str]] = None,
    filenames: Optional[List[str]] = None,
) -> List[str]:
    """
    Resolves actual file paths based on request parameters
    or fallback defaults.
    """

    resolved_paths: List[str] = []

    # =========================================================================
    # 1. Explicit file paths
    # =========================================================================

    if file_paths:

        for p in file_paths:

            if os.path.exists(p):

                resolved_paths.append(
                    str(
                        Path(p).resolve()
                    )
                )

            else:

                raise FileNotFoundError(
                    f"Specified file path does not exist: {p}"
                )

        return resolved_paths

    # =========================================================================
    # 2. Explicit directory path
    # =========================================================================

    target_dir = None

    if directory_path:

        if (
            os.path.exists(directory_path)
            and os.path.isdir(directory_path)
        ):

            target_dir = directory_path

        else:

            raise FileNotFoundError(
                f"Specified directory path does not exist: "
                f"{directory_path}"
            )

    else:

        # Fallback to candidate default directories

        for cand in DEFAULT_CANDIDATE_DIRS:

            if (
                os.path.exists(cand)
                and os.path.isdir(cand)
            ):

                csv_count = len(
                    list(
                        Path(cand).glob("*.csv")
                    )
                )

                if csv_count > 0:

                    target_dir = cand

                    break

    if not target_dir:

        raise FileNotFoundError(
            "No valid dataset directory found. "
            "Please provide directory_path or file_paths."
        )

    # =========================================================================
    # 3. Filenames in directory or all CSV/XLSX files
    # =========================================================================

    target_path_obj = Path(
        target_dir
    )

    if filenames:

        for fn in filenames:

            candidate_file = (
                target_path_obj / fn
            )

            if candidate_file.exists():

                resolved_paths.append(
                    str(
                        candidate_file.resolve()
                    )
                )

            else:

                raise FileNotFoundError(
                    f"File '{fn}' not found in directory "
                    f"'{target_dir}'."
                )

    else:

        # Find all CSV / XLSX files in directory

        for f in sorted(
            target_path_obj.glob("*")
        ):

            if (
                f.is_file()
                and f.suffix.lower()
                in (".csv", ".xlsx")
            ):

                # Exclude hidden/temp files

                if not f.name.startswith("."):

                    resolved_paths.append(
                        str(
                            f.resolve()
                        )
                    )

    if not resolved_paths:

        raise FileNotFoundError(
            f"No CSV or XLSX dataset files found "
            f"in '{target_dir}'."
        )

    return resolved_paths