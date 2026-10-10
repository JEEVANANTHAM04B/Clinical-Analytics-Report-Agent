"""
app/ingestion/relationship_review.py
====================================

Relationship Candidate Store & Review Service

Responsibilities:
    1. Store relationship candidates discovered during ingestion analysis.
    2. Allow analysts to APPROVE, REJECT, or EDIT relationships.
    3. Generate alternative relationships after rejection.
    4. Deterministically validate LLM-generated alternatives.
    5. Persist human review decisions to MySQL metadata.
    6. Create audit logs for review actions.

Architecture:

    Relationship Detector
            |
            v
    Candidate Relationship
            |
            v
       Human Review
        /    |    \
       /     |     \
   APPROVE  REJECT  EDIT
              |
              v
       LLM Regenerator
              |
              v
      Schema Validation
              |
              v
   Deterministic Validation
              |
        +-----+------+
        |            |
      VALID      NO_ALTERNATIVE
        |            |
        v            v
   Human Review     Stop
"""

from typing import List, Dict, Optional, Tuple, Any

from app.core.logging_config import get_logger
from app.schemas.validation import RelationshipAnalysis
from app.schemas.relationships import (
    ApprovedRelationship,
    RejectedRelationship,
)

logger = get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================

class CandidateNotFoundError(Exception):
    """
    Raised when an analyst attempts to review a relationship
    that was never detected.
    """

    pass


# =============================================================================
# In-Memory Storage State
# =============================================================================

# Map normalized relationship key -> RelationshipAnalysis
_candidates: Dict[str, RelationshipAnalysis] = {}

# Map normalized relationship key -> ApprovedRelationship
_approved: Dict[str, ApprovedRelationship] = {}

# Map normalized relationship key -> RejectedRelationship
_rejected: Dict[str, RejectedRelationship] = {}


# =============================================================================
# Utility
# =============================================================================

def _make_key(
    parent_table: str,
    parent_col: str,
    child_table: str,
    child_col: str,
) -> str:
    """
    Creates a normalized, case-insensitive key for relationship lookups.
    """

    return (
        f"{parent_table.strip().lower()}."
        f"{parent_col.strip().lower()}"
        f"->"
        f"{child_table.strip().lower()}."
        f"{child_col.strip().lower()}"
    )


# =============================================================================
# Candidate Management
# =============================================================================

def set_relationship_candidates(
    candidates: List[RelationshipAnalysis],
) -> int:
    """
    Stores detected relationship candidates from dataset analysis.

    Args:
        candidates:
            List of RelationshipAnalysis objects produced by
            relationship_detector.

    Returns:
        Number of candidates stored.
    """

    global _candidates

    _candidates.clear()

    for candidate in candidates:
        key = _make_key(
            candidate.parent_table,
            candidate.parent_column,
            candidate.child_table,
            candidate.child_column,
        )

        _candidates[key] = candidate

    logger.info(
        f"Registered {len(_candidates)} detected relationship "
        f"candidate(s) for human review."
    )

    return len(_candidates)


def get_relationship_candidates() -> List[RelationshipAnalysis]:
    """
    Returns all currently registered relationship candidates.
    """

    return list(_candidates.values())


def find_candidate(
    parent_table: str,
    parent_column: str,
    child_table: str,
    child_column: str,
) -> Optional[RelationshipAnalysis]:
    """
    Finds a candidate relationship by parent and child coordinates.

    Lookup is case-insensitive.
    """

    key = _make_key(
        parent_table,
        parent_column,
        child_table,
        child_column,
    )

    return _candidates.get(key)


# =============================================================================
# APPROVE
# =============================================================================

def approve_relationship(
    parent_table: str,
    parent_column: str,
    child_table: str,
    child_column: str,
    analyst_note: Optional[str] = None,
) -> ApprovedRelationship:
    """
    Approves an existing relationship candidate.

    Only relationships previously detected by the deterministic
    relationship detector can be approved.
    """

    candidate = find_candidate(
        parent_table,
        parent_column,
        child_table,
        child_column,
    )

    if not candidate:
        raise CandidateNotFoundError(
            f"Relationship candidate "
            f"'{parent_table}.{parent_column} -> "
            f"{child_table}.{child_column}' "
            f"was not detected during dataset analysis. "
            f"Only detected candidates can be reviewed."
        )

    # Use candidate's exact casing.
    approved = ApprovedRelationship(
        parent_table=candidate.parent_table,
        parent_column=candidate.parent_column,
        child_table=candidate.child_table,
        child_column=candidate.child_column,
        status="APPROVED",
        analyst_note=analyst_note,
        was_edited=False,
    )

    key = _make_key(
        candidate.parent_table,
        candidate.parent_column,
        candidate.child_table,
        candidate.child_column,
    )

    _approved[key] = approved

    # Remove from rejected if it was previously rejected.
    _rejected.pop(key, None)

    logger.info(
        f"Approved relationship: "
        f"{approved.parent_table}.{approved.parent_column} -> "
        f"{approved.child_table}.{approved.child_column}"
    )

    # -------------------------------------------------------------------------
    # Persist to MySQL metadata
    # -------------------------------------------------------------------------

    try:
        from app.core.database import get_db_context
        from app.database.repository import (
            save_relationship_review,
            create_audit_log,
        )

        with get_db_context() as db:

            save_relationship_review(
                db=db,
                parent_table=approved.parent_table,
                parent_column=approved.parent_column,
                child_table=approved.child_table,
                child_column=approved.child_column,
                status="APPROVED",
                analyst_note=approved.analyst_note,
                was_edited=False,
                original_candidate=None,
            )

            create_audit_log(
                db=db,
                action="RELATIONSHIP_APPROVED",
                entity_type="RELATIONSHIP",
                entity_name=(
                    f"{approved.parent_table}."
                    f"{approved.parent_column}->"
                    f"{approved.child_table}."
                    f"{approved.child_column}"
                ),
                status="SUCCESS",
                message=(
                    f"Approved relationship: "
                    f"{approved.parent_table}.{approved.parent_column} -> "
                    f"{approved.child_table}.{approved.child_column}"
                ),
            )

    except Exception as e:
        logger.warning(
            f"Could not persist approved relationship to MySQL: {e}"
        )

    return approved


# =============================================================================
# REJECT
# =============================================================================

def reject_relationship(
    parent_table: str,
    parent_column: str,
    child_table: str,
    child_column: str,
    analyst_note: Optional[str] = None,
) -> RejectedRelationship:
    """
    Rejects an existing relationship candidate.

    Only relationships previously detected by the deterministic
    relationship detector can be rejected.
    """

    candidate = find_candidate(
        parent_table,
        parent_column,
        child_table,
        child_column,
    )

    if not candidate:
        raise CandidateNotFoundError(
            f"Relationship candidate "
            f"'{parent_table}.{parent_column} -> "
            f"{child_table}.{child_column}' "
            f"was not detected during dataset analysis. "
            f"Only detected candidates can be reviewed."
        )

    rejected = RejectedRelationship(
        parent_table=candidate.parent_table,
        parent_column=candidate.parent_column,
        child_table=candidate.child_table,
        child_column=candidate.child_column,
        status="REJECTED",
        analyst_note=analyst_note,
    )

    key = _make_key(
        candidate.parent_table,
        candidate.parent_column,
        candidate.child_table,
        candidate.child_column,
    )

    _rejected[key] = rejected

    # Remove from approved if it was previously approved.
    _approved.pop(key, None)

    logger.info(
        f"Rejected relationship: "
        f"{rejected.parent_table}.{rejected.parent_column} -> "
        f"{rejected.child_table}.{rejected.child_column}"
    )

    # -------------------------------------------------------------------------
    # Persist to MySQL metadata
    # -------------------------------------------------------------------------

    try:
        from app.core.database import get_db_context
        from app.database.repository import (
            save_relationship_review,
            create_audit_log,
        )

        with get_db_context() as db:

            save_relationship_review(
                db=db,
                parent_table=rejected.parent_table,
                parent_column=rejected.parent_column,
                child_table=rejected.child_table,
                child_column=rejected.child_column,
                status="REJECTED",
                analyst_note=rejected.analyst_note,
                was_edited=False,
                original_candidate=None,
            )

            create_audit_log(
                db=db,
                action="RELATIONSHIP_REJECTED",
                entity_type="RELATIONSHIP",
                entity_name=(
                    f"{rejected.parent_table}."
                    f"{rejected.parent_column}->"
                    f"{rejected.child_table}."
                    f"{rejected.child_column}"
                ),
                status="SUCCESS",
                message=(
                    f"Rejected relationship: "
                    f"{rejected.parent_table}.{rejected.parent_column} -> "
                    f"{rejected.child_table}.{rejected.child_column}"
                ),
            )

    except Exception as e:
        logger.warning(
            f"Could not persist rejected relationship to MySQL: {e}"
        )

    return rejected

# =============================================================================
# RELATIONSHIP REGENERATION
# =============================================================================

def regenerate_relationship(
    parent_table: str,
    parent_column: str,
    child_table: str,
    child_column: str,
    analyst_feedback: str,
    datasets: Dict[str, Any],
):
    """
    Generate an alternative relationship proposal using schema information.

    Full datasets are NOT loaded or validated here.

    The API layer:
        1. Reads schemas for all datasets.
        2. Calls this function for LLM proposal generation.
        3. Loads only the proposed parent/child datasets.
        4. Performs deterministic validation.
    """

    from app.ingestion.relationship_regenerator import (
        propose_alternative_relationship,
    )

    rejected_relationship = {
        "parent_table": parent_table,
        "parent_column": parent_column,
        "child_table": child_table,
        "child_column": child_column,
    }

    logger.info(
        "Starting relationship regeneration for "
        f"{parent_table}.{parent_column} -> "
        f"{child_table}.{child_column}"
    )

    # -------------------------------------------------------------------------
    # Build schema catalog
    # -------------------------------------------------------------------------

    schema_catalog = {}

    for table_name, columns in datasets.items():

        # New memory-safe format:
        #
        # {
        #     "patients": ["Id", "BIRTHDATE", ...],
        #     "encounters": ["Id", "PATIENT", ...]
        # }

        if isinstance(columns, list):
            schema_catalog[table_name] = columns

        # Backward compatibility with the old DataFrame format.
        elif (
            isinstance(columns, tuple)
            and len(columns) == 2
            and hasattr(columns[1], "columns")
        ):
            schema_catalog[table_name] = list(columns[1].columns)

    if not schema_catalog:
        raise ValueError(
            "No valid dataset schemas were provided "
            "for relationship regeneration."
        )

    logger.info(
        "Relationship regeneration schema catalog contains %d dataset(s)",
        len(schema_catalog),
    )

    # -------------------------------------------------------------------------
    # Ask LLM for an alternative
    # -------------------------------------------------------------------------

    proposal = propose_alternative_relationship(
        rejected_relationship=rejected_relationship,
        analyst_feedback=analyst_feedback,
        available_schema=schema_catalog,
    )

    logger.info(
        "Relationship regeneration result: %s",
        proposal.status,
    )

    # -------------------------------------------------------------------------
    # No alternative
    # -------------------------------------------------------------------------

    if proposal.status == "NO_ALTERNATIVE":

        logger.info(
            "No alternative relationship found for "
            f"{parent_table}.{parent_column} -> "
            f"{child_table}.{child_column}"
        )

        return {
            "proposal": proposal,
            "validation": None,
        }

    # -------------------------------------------------------------------------
    # Return proposal only.
    #
    # The API will load ONLY the proposed parent and child datasets
    # and perform deterministic validation there.
    # -------------------------------------------------------------------------

    return {
        "proposal": proposal,
        "validation": None,
    }
# =============================================================================
# EDIT
# =============================================================================

def edit_relationship(
    parent_table: str,
    parent_column: str,
    child_table: str,
    child_column: str,
    edited_parent_table: Optional[str],
    edited_parent_column: Optional[str],
    edited_child_table: Optional[str],
    edited_child_column: Optional[str],
    analyst_note: Optional[str] = None,
) -> ApprovedRelationship:
    """
    Edits and approves a detected relationship candidate.

    Validates:

        1. Original candidate exists.
        2. All edited fields are provided.
    """

    candidate = find_candidate(
        parent_table,
        parent_column,
        child_table,
        child_column,
    )

    if not candidate:
        raise CandidateNotFoundError(
            f"Cannot EDIT: Original relationship candidate "
            f"'{parent_table}.{parent_column} -> "
            f"{child_table}.{child_column}' "
            f"was not detected during dataset analysis."
        )

    # -------------------------------------------------------------------------
    # Validate edited fields
    # -------------------------------------------------------------------------

    if not all(
        [
            edited_parent_table,
            edited_parent_column,
            edited_child_table,
            edited_child_column,
        ]
    ):
        raise ValueError(
            "EDIT action requires all four target fields: "
            "'edited_parent_table', "
            "'edited_parent_column', "
            "'edited_child_table', and "
            "'edited_child_column'."
        )

    orig_str = (
        f"{candidate.parent_table}.{candidate.parent_column} -> "
        f"{candidate.child_table}.{candidate.child_column}"
    )

    approved = ApprovedRelationship(
        parent_table=edited_parent_table.strip(),
        parent_column=edited_parent_column.strip(),
        child_table=edited_child_table.strip(),
        child_column=edited_child_column.strip(),
        status="APPROVED",
        analyst_note=analyst_note,
        was_edited=True,
        original_candidate=orig_str,
    )

    # -------------------------------------------------------------------------
    # Store under edited key
    # -------------------------------------------------------------------------

    new_key = _make_key(
        approved.parent_table,
        approved.parent_column,
        approved.child_table,
        approved.child_column,
    )

    _approved[new_key] = approved

    # Remove old candidate from rejected if needed.
    orig_key = _make_key(
        candidate.parent_table,
        candidate.parent_column,
        candidate.child_table,
        candidate.child_column,
    )

    _rejected.pop(orig_key, None)

    logger.info(
        f"Edited and approved relationship: "
        f"{approved.parent_table}.{approved.parent_column} -> "
        f"{approved.child_table}.{approved.child_column} "
        f"(from: {orig_str})"
    )

    # -------------------------------------------------------------------------
    # Persist to MySQL metadata
    # -------------------------------------------------------------------------

    try:
        from app.core.database import get_db_context
        from app.database.repository import (
            save_relationship_review,
            create_audit_log,
        )

        with get_db_context() as db:

            save_relationship_review(
                db=db,
                parent_table=approved.parent_table,
                parent_column=approved.parent_column,
                child_table=approved.child_table,
                child_column=approved.child_column,
                status="APPROVED",
                analyst_note=approved.analyst_note,
                was_edited=True,
                original_candidate=orig_str,
            )

            create_audit_log(
                db=db,
                action="RELATIONSHIP_EDIT",
                entity_type="RELATIONSHIP",
                entity_name=(
                    f"{approved.parent_table}."
                    f"{approved.parent_column}->"
                    f"{approved.child_table}."
                    f"{approved.child_column}"
                ),
                status="SUCCESS",
                message=(
                    f"Edited and approved relationship from "
                    f"original '{orig_str}'"
                ),
            )

    except Exception as e:
        logger.warning(
            f"Could not persist edited relationship to MySQL: {e}"
        )

    return approved


# =============================================================================
# Approved & Rejected Retrieval
# =============================================================================

def get_approved_relationships() -> List[ApprovedRelationship]:
    """
    Returns all approved relationships.

    Uses MySQL as the persistent source of truth.
    Falls back to in-memory state if the database cannot be accessed.
    """

    try:
        from app.core.database import get_db_context
        from app.database.repository import get_approved_relationships_from_db

        with get_db_context() as db:
            records = get_approved_relationships_from_db(
                db=db,
                status="APPROVED",
            )

            return [
                ApprovedRelationship(
                    parent_table=record.parent_table,
                    parent_column=record.parent_column,
                    child_table=record.child_table,
                    child_column=record.child_column,
                    status=record.status,
                    analyst_note=record.analyst_note,
                    was_edited=record.was_edited,
                    original_candidate=record.original_candidate,
                )
                for record in records
            ]

    except Exception as e:
        logger.warning(
            f"Could not retrieve approved relationships from MySQL: {e}. "
            "Falling back to in-memory state."
        )

        return list(_approved.values())


def get_rejected_relationships() -> List[RejectedRelationship]:
    """
    Returns all rejected relationships.

    Uses MySQL as the persistent source of truth.
    Falls back to in-memory state if the database cannot be accessed.
    """

    try:
        from app.core.database import get_db_context
        from app.database.repository import get_approved_relationships_from_db

        with get_db_context() as db:
            records = get_approved_relationships_from_db(
                db=db,
                status="REJECTED",
            )

            return [
                RejectedRelationship(
                    parent_table=record.parent_table,
                    parent_column=record.parent_column,
                    child_table=record.child_table,
                    child_column=record.child_column,
                    status=record.status,
                    analyst_note=record.analyst_note,
                )
                for record in records
            ]

    except Exception as e:
        logger.warning(
            f"Could not retrieve rejected relationships from MySQL: {e}. "
            "Falling back to in-memory state."
        )

        return list(_rejected.values())

# =============================================================================
# Clear Stores
# =============================================================================

def clear_review_stores() -> None:
    """
    Resets all in-memory relationship stores.
    """

    _candidates.clear()
    _approved.clear()
    _rejected.clear()

    logger.info(
        "All in-memory relationship stores reset."
    )