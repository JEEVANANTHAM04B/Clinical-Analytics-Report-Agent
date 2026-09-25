"""
app/ingestion/relationship_review.py
====================================
Relationship Candidate Store & Review Service

WHY THIS MODULE EXISTS:
    Separates relationship candidate persistence and human review logic
    from the FastAPI router layer.
    
    In Phase 4 Step 3:
      1. Relationship candidates discovered by /ingestion/analyze are registered here.
      2. The analyst retrieves candidates via GET /relationships/candidates.
      3. The analyst reviews candidates via POST /relationships/review:
         - Candidate existence is validated (prevents approving fake/arbitrary links).
         - APPROVE: stores in the approved store.
         - REJECT: stores in the rejected store.
         - EDIT: verifies original candidate, validates edited fields, stores as approved.
      4. Approved and rejected relationships are accessible via GET endpoints.
    
    Persistence is currently in-memory. MySQL persistence will be added in later phases.
"""

from typing import List, Dict, Optional, Tuple
from app.core.logging_config import get_logger
from app.schemas.validation import RelationshipAnalysis
from app.schemas.relationships import ApprovedRelationship, RejectedRelationship

logger = get_logger(__name__)


class CandidateNotFoundError(Exception):
    """Raised when an analyst attempts to review a relationship that was never detected."""
    pass


# =============================================================================
# In-Memory Storage State
# =============================================================================

# Map normalized key -> RelationshipAnalysis
_candidates: Dict[str, RelationshipAnalysis] = {}

# Map normalized key -> ApprovedRelationship
_approved: Dict[str, ApprovedRelationship] = {}

# Map normalized key -> RejectedRelationship
_rejected: Dict[str, RejectedRelationship] = {}


def _make_key(parent_table: str, parent_col: str, child_table: str, child_col: str) -> str:
    """Creates a normalized, case-insensitive key for relationship lookups."""
    return f"{parent_table.strip().lower()}.{parent_col.strip().lower()}->{child_table.strip().lower()}.{child_col.strip().lower()}"


# =============================================================================
# Candidate Management
# =============================================================================

def set_relationship_candidates(candidates: List[RelationshipAnalysis]) -> int:
    """
    Stores detected relationship candidates from dataset analysis.
    
    Args:
        candidates: List of RelationshipAnalysis objects produced by relationship_detector.
    
    Returns:
        Number of candidates stored.
    """
    global _candidates
    _candidates.clear()
    for c in candidates:
        key = _make_key(c.parent_table, c.parent_column, c.child_table, c.child_column)
        _candidates[key] = c
    logger.info(f"Registered {len(_candidates)} detected relationship candidate(s) for human review.")
    return len(_candidates)


def get_relationship_candidates() -> List[RelationshipAnalysis]:
    """Returns the list of all currently registered relationship candidates."""
    return list(_candidates.values())


def find_candidate(
    parent_table: str,
    parent_column: str,
    child_table: str,
    child_column: str,
) -> Optional[RelationshipAnalysis]:
    """Finds a candidate relationship by parent and child coordinates (case-insensitive)."""
    key = _make_key(parent_table, parent_column, child_table, child_column)
    return _candidates.get(key)


# =============================================================================
# Review Actions (APPROVE / REJECT / EDIT)
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
    
    Raises:
        CandidateNotFoundError: If the relationship was not among detected candidates.
    """
    candidate = find_candidate(parent_table, parent_column, child_table, child_column)
    if not candidate:
        raise CandidateNotFoundError(
            f"Relationship candidate '{parent_table}.{parent_column} -> {child_table}.{child_column}' "
            f"was not detected during dataset analysis. Only detected candidates can be reviewed."
        )

    # Use candidate's exact casing
    approved = ApprovedRelationship(
        parent_table=candidate.parent_table,
        parent_column=candidate.parent_column,
        child_table=candidate.child_table,
        child_column=candidate.child_column,
        status="APPROVED",
        analyst_note=analyst_note,
        was_edited=False,
    )

    key = _make_key(candidate.parent_table, candidate.parent_column, candidate.child_table, candidate.child_column)
    _approved[key] = approved

    # Remove from rejected if it was previously rejected
    _rejected.pop(key, None)

    logger.info(f"Approved relationship: {approved.parent_table}.{approved.parent_column} -> {approved.child_table}.{approved.child_column}")
    return approved


def reject_relationship(
    parent_table: str,
    parent_column: str,
    child_table: str,
    child_column: str,
    analyst_note: Optional[str] = None,
) -> RejectedRelationship:
    """
    Rejects an existing relationship candidate.
    
    Raises:
        CandidateNotFoundError: If the relationship was not among detected candidates.
    """
    candidate = find_candidate(parent_table, parent_column, child_table, child_column)
    if not candidate:
        raise CandidateNotFoundError(
            f"Relationship candidate '{parent_table}.{parent_column} -> {child_table}.{child_column}' "
            f"was not detected during dataset analysis. Only detected candidates can be reviewed."
        )

    rejected = RejectedRelationship(
        parent_table=candidate.parent_table,
        parent_column=candidate.parent_column,
        child_table=candidate.child_table,
        child_column=candidate.child_column,
        status="REJECTED",
        analyst_note=analyst_note,
    )

    key = _make_key(candidate.parent_table, candidate.parent_column, candidate.child_table, candidate.child_column)
    _rejected[key] = rejected

    # Remove from approved if it was previously approved
    _approved.pop(key, None)

    logger.info(f"Rejected relationship: {rejected.parent_table}.{rejected.parent_column} -> {rejected.child_table}.{rejected.child_column}")
    return rejected


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
      1. Original candidate must exist in detected candidates.
      2. All edited fields must be provided and non-empty.
    
    Raises:
        CandidateNotFoundError: If the original relationship was not among detected candidates.
        ValueError: If any required edited fields are missing.
    """
    candidate = find_candidate(parent_table, parent_column, child_table, child_column)
    if not candidate:
        raise CandidateNotFoundError(
            f"Cannot EDIT: Original relationship candidate '{parent_table}.{parent_column} -> {child_table}.{child_column}' "
            f"was not detected during dataset analysis."
        )

    # Validate that all edited fields are provided
    if not all([edited_parent_table, edited_parent_column, edited_child_table, edited_child_column]):
        raise ValueError(
            "EDIT action requires all four target fields: 'edited_parent_table', "
            "'edited_parent_column', 'edited_child_table', and 'edited_child_column'."
        )

    orig_str = f"{candidate.parent_table}.{candidate.parent_column} -> {candidate.child_table}.{candidate.child_column}"

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

    # Store under edited key
    new_key = _make_key(approved.parent_table, approved.parent_column, approved.child_table, approved.child_column)
    _approved[new_key] = approved

    # Also clean old candidate key from rejected if needed
    orig_key = _make_key(candidate.parent_table, candidate.parent_column, candidate.child_table, candidate.child_column)
    _rejected.pop(orig_key, None)

    logger.info(f"Edited and approved relationship: {approved.parent_table}.{approved.parent_column} -> {approved.child_table}.{approved.child_column} (from: {orig_str})")
    return approved


# =============================================================================
# Approved & Rejected Retrieval
# =============================================================================

def get_approved_relationships() -> List[ApprovedRelationship]:
    """Returns all currently approved relationships."""
    return list(_approved.values())


def get_rejected_relationships() -> List[RejectedRelationship]:
    """Returns all currently rejected relationships."""
    return list(_rejected.values())


def clear_review_stores() -> None:
    """Resets all in-memory relationship stores (candidates, approved, rejected)."""
    _candidates.clear()
    _approved.clear()
    _rejected.clear()
    logger.info("All in-memory relationship stores reset.")
