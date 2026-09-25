"""
app/ingestion/relationship_detector.py
======================================
Primary Key and Foreign Key Candidate Discovery and Validation

WHY THIS EXISTS:
    Healthcare data is relational. In the Synthea/clinical schema, entities
    revolve around:
      - patients (parent)
      - encounters (child of patients, parent of clinical events)
      - conditions, medications, observations, procedures (children of both)

CRITICAL CLINICAL LOGIC:
    - observations.ENCOUNTER contains legitimate NULL values (e.g. ambulatory lab tests,
      remote monitoring, or historical measurements recorded outside a hospital visit).
    - The detector MUST distinguish:
        * Legitimate nullable relationships (child NULLs exist, but 100% of non-nulls match)
        * True relational integrity violations (child references an ID that does NOT exist in parent)
    - Source CSV files are NOT modified.
    - No foreign keys or tables are created in MySQL yet (Phase 4).
"""

from typing import List, Dict, Tuple, Optional
import pandas as pd

from app.schemas.validation import PrimaryKeyCandidate, RelationshipAnalysis


# =============================================================================
# Primary Key Candidate Discovery
# =============================================================================

def find_primary_key_candidates(df: pd.DataFrame, table_name: str) -> List[PrimaryKeyCandidate]:
    """
    Evaluates columns in a DataFrame to identify potential primary key candidates.

    Criteria:
      - 0 null values
      - 100% uniqueness
      - Column name suggests an identifier (e.g. 'ID', 'PATIENT_ID', 'ENCOUNTER_ID')
    """
    total_rows = len(df)
    candidates = []

    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        non_null_count = total_rows - null_count
        if non_null_count == 0:
            continue

        unique_count = int(series.nunique())
        uniqueness_pct = round((unique_count / total_rows * 100.0), 2)
        is_unique = (unique_count == total_rows) and (null_count == 0)

        col_upper = col.strip().upper()
        name_is_id = (col_upper == "ID" or col_upper.endswith("_ID") or col_upper.endswith("ID"))

        if is_unique and name_is_id:
            candidates.append(
                PrimaryKeyCandidate(
                    column=col,
                    is_unique=True,
                    null_count=0,
                    uniqueness_percentage=100.0,
                    data_type="identifier",
                    confidence="HIGH",
                    notes=f"Ideal primary key candidate: 100% unique ({total_rows:,} distinct values) and zero nulls.",
                )
            )
        elif is_unique:
            candidates.append(
                PrimaryKeyCandidate(
                    column=col,
                    is_unique=True,
                    null_count=0,
                    uniqueness_percentage=100.0,
                    data_type=str(series.dtype),
                    confidence="MEDIUM",
                    notes=f"Column is unique ({total_rows:,} distinct values) with zero nulls, but name '{col}' does not explicitly follow ID naming conventions.",
                )
            )
        elif name_is_id and uniqueness_pct >= 95.0:
            candidates.append(
                PrimaryKeyCandidate(
                    column=col,
                    is_unique=False,
                    null_count=null_count,
                    uniqueness_percentage=uniqueness_pct,
                    data_type="identifier",
                    confidence="LOW",
                    notes=f"ID-like column but has duplicate or null values ({null_count} nulls, {total_rows - unique_count} duplicate values).",
                )
            )

    return candidates


# =============================================================================
# Foreign Key Relationship Validation
# =============================================================================

# Known clinical relationships to evaluate systematically
STANDARD_RELATIONSHIPS = [
    # (parent_table, parent_col, child_table, child_col, is_expected_nullable)
    ("patients", "ID", "encounters", "PATIENT", False),
    ("patients", "ID", "conditions", "PATIENT", False),
    ("patients", "ID", "medications", "PATIENT", False),
    ("patients", "ID", "observations", "PATIENT", False),
    ("patients", "ID", "procedures", "PATIENT", False),
    ("encounters", "ID", "conditions", "ENCOUNTER", False),
    ("encounters", "ID", "medications", "ENCOUNTER", False),
    ("encounters", "ID", "procedures", "ENCOUNTER", False),
    ("encounters", "ID", "observations", "ENCOUNTER", True),  # observations.ENCOUNTER is legitimately nullable
]


def evaluate_relationship(
    parent_df: pd.DataFrame,
    parent_col: str,
    child_df: pd.DataFrame,
    child_col: str,
    parent_name: str,
    child_name: str,
    expected_nullable: bool = False,
) -> Optional[RelationshipAnalysis]:
    """
    Evaluates referential integrity between parent primary key and child foreign key.

    Uses efficient set lookups (O(1)) instead of nested loops.
    """
    if parent_col not in parent_df.columns or child_col not in child_df.columns:
        return None

    # Parent key set (in-memory hash set for O(1) membership checks)
    parent_keys = set(parent_df[parent_col].dropna().unique())
    child_series = child_df[child_col]
    child_row_count = len(child_series)
    child_null_count = int(child_series.isna().sum())

    non_null_child = child_series.dropna()
    non_null_count = len(non_null_child)

    if non_null_count == 0:
        return RelationshipAnalysis(
            parent_table=parent_name,
            parent_column=parent_col,
            child_table=child_name,
            child_column=child_col,
            child_row_count=child_row_count,
            child_null_count=child_null_count,
            is_nullable=True,
            matching_reference_count=0,
            unmatched_reference_count=0,
            match_percentage=0.0,
            status="CANDIDATE",
            notes="Child column contains 100% null values.",
        )

    # Vectorized match check using isin
    matching_mask = non_null_child.isin(parent_keys)
    matching_count = int(matching_mask.sum())
    unmatched_count = non_null_count - matching_count
    match_pct = round((matching_count / non_null_count * 100.0), 2)

    is_nullable = (child_null_count > 0)

    # Determine status and notes
    if unmatched_count == 0 and child_null_count == 0:
        status = "VALID"
        notes = (
            f"100% referential integrity verified. All {matching_count:,} child records "
            f"reference valid {parent_name}.{parent_col} keys with zero nulls."
        )
    elif unmatched_count == 0 and child_null_count > 0:
        status = "VALID_WITH_NULLS"
        notes = (
            f"Valid nullable relationship: 100% of non-null child values ({matching_count:,} records) "
            f"match {parent_name}.{parent_col}. {child_null_count:,} rows contain legitimate NULL encounters."
        )
    elif match_pct >= 90.0:
        status = "VIOLATION"
        notes = (
            f"Referential integrity violation: {unmatched_count:,} records ({round(100 - match_pct, 2)}%) "
            f"reference non-existent {parent_name}.{parent_col} keys."
        )
    else:
        status = "CANDIDATE"
        notes = f"Low referential overlap ({match_pct}%). Potential coincidence rather than true foreign key."

    return RelationshipAnalysis(
        parent_table=parent_name,
        parent_column=parent_col,
        child_table=child_name,
        child_column=child_col,
        child_row_count=child_row_count,
        child_null_count=child_null_count,
        is_nullable=is_nullable,
        matching_reference_count=matching_count,
        unmatched_reference_count=unmatched_count,
        match_percentage=match_pct,
        status=status,
        notes=notes,
    )


def detect_relationships_across_datasets(
    datasets: Dict[str, Tuple[str, pd.DataFrame]]
) -> List[RelationshipAnalysis]:
    """
    Evaluates referential relationships across a collection of datasets.

    Args:
        datasets: Dict mapping logical name (e.g. 'patients') to (filename, DataFrame)
    """
    relationships = []

    # Map logical names (lowercased without 'analytics_' or '.csv')
    normalized_dfs: Dict[str, pd.DataFrame] = {}
    for key, (filename, df) in datasets.items():
        clean_name = key.lower().replace("analytics_", "").replace(".csv", "").replace(".xlsx", "")
        normalized_dfs[clean_name] = df

    # Check standard clinical relationships
    for parent_name, parent_col, child_name, child_col, expected_nullable in STANDARD_RELATIONSHIPS:
        if parent_name in normalized_dfs and child_name in normalized_dfs:
            rel = evaluate_relationship(
                parent_df=normalized_dfs[parent_name],
                parent_col=parent_col,
                child_df=normalized_dfs[child_name],
                child_col=child_col,
                parent_name=parent_name,
                child_name=child_name,
                expected_nullable=expected_nullable,
            )
            if rel:
                relationships.append(rel)

    return relationships
