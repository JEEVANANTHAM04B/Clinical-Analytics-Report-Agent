"""
app/api/relationships.py
========================
Relationship Review and Human Confirmation API (Phase 4 Step 3)

WORKFLOW:
    1. POST /ingestion/analyze
       Discovers relational foreign-key candidates across datasets.
    2. GET /relationships/candidates
       Analyst views all detected candidates with referential evidence.
    3. POST /relationships/review
       Analyst explicitly acts on a candidate:
         - APPROVE: candidate confirmed for downstream schema mapping
         - REJECT: candidate declined (not loaded into approved store)
         - EDIT: candidate corrected and approved with new coordinates
    4. GET /relationships/approved & GET /relationships/rejected
       View approved and rejected relationships.

CRITICAL PRINCIPLES:
    - Candidate existence is validated before any action is permitted.
    - Arbitrary/fake relationships cannot be approved.
    - All business logic lives in app/ingestion/relationship_review.py.
    - No MySQL persistence yet (in-memory state during Phase 4 Step 3).
"""

from fastapi import APIRouter, HTTPException, status

from app.schemas.relationships import (
    RelationshipAction,
    RelationshipReviewRequest,
    RelationshipReviewResponse,
    RelationshipCandidatesResponse,
    ApprovedRelationshipsResponse,
    RejectedRelationshipsResponse,
)
from app.ingestion.relationship_review import (
    get_relationship_candidates,
    get_approved_relationships,
    get_rejected_relationships,
    approve_relationship,
    reject_relationship,
    edit_relationship,
    CandidateNotFoundError,
)
from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/relationships",
    tags=["Relationships"],
)


# =============================================================================
# GET /relationships/candidates
# =============================================================================

@router.get(
    "/candidates",
    response_model=RelationshipCandidatesResponse,
    summary="List Detected Relationship Candidates",
    description=(
        "Returns all relationship candidates detected by the Phase 3 analysis engine (/ingestion/analyze). "
        "Provides referential integrity metrics (match %, child row counts, null counts) "
        "for human confirmation."
    ),
    status_code=status.HTTP_200_OK,
)
def list_relationship_candidates():
    """
    Retrieve all relationship candidates discovered during dataset analysis.

    If /ingestion/analyze has not been executed yet, this returns an empty list.
    """
    candidates = get_relationship_candidates()
    logger.info(f"GET /relationships/candidates | returning {len(candidates)} candidate(s)")
    return RelationshipCandidatesResponse(
        status="success",
        message="Relationship candidates retrieved successfully." if candidates else "No candidates detected yet. Run POST /ingestion/analyze first.",
        count=len(candidates),
        candidates=candidates,
    )


# =============================================================================
# GET /relationships/approved
# =============================================================================

@router.get(
    "/approved",
    response_model=ApprovedRelationshipsResponse,
    summary="List Approved Relationships",
    description=(
        "Returns all relationships that have been explicitly confirmed and approved by a human analyst. "
        "These approved relationships form the foundation for Phase 5 MySQL relational loading."
    ),
    status_code=status.HTTP_200_OK,
)
def list_approved_relationships():
    """Retrieve all relationships approved by the analyst."""
    approved = get_approved_relationships()
    logger.info(f"GET /relationships/approved | returning {len(approved)} approved relationship(s)")
    return ApprovedRelationshipsResponse(
        status="success",
        count=len(approved),
        relationships=approved,
    )


# =============================================================================
# GET /relationships/rejected
# =============================================================================

@router.get(
    "/rejected",
    response_model=RejectedRelationshipsResponse,
    summary="List Rejected Relationships",
    description="Returns all relationship candidates that have been reviewed and rejected by the analyst.",
    status_code=status.HTTP_200_OK,
)
def list_rejected_relationships():
    """Retrieve all relationship candidates rejected by the analyst."""
    rejected = get_rejected_relationships()
    logger.info(f"GET /relationships/rejected | returning {len(rejected)} rejected relationship(s)")
    return RejectedRelationshipsResponse(
        status="success",
        count=len(rejected),
        relationships=rejected,
    )


# =============================================================================
# POST /relationships/review
# =============================================================================

@router.post(
    "/review",
    response_model=RelationshipReviewResponse,
    summary="Review a Relationship Candidate",
    description=(
        "Allows an analyst to APPROVE, REJECT, or EDIT a detected relationship candidate. "
        "Verifies that the target relationship actually exists in the detected candidate list. "
        "Arbitrary or non-existent relationships cannot be approved."
    ),
    responses={
        200: {"description": "Review action processed successfully"},
        400: {"description": "Invalid review parameters (e.g. missing fields for EDIT action)"},
        404: {"description": "Candidate relationship not found in detected candidates"},
    },
    status_code=status.HTTP_200_OK,
)
def review_relationship(request: RelationshipReviewRequest):
    """
    Process an analyst decision on a candidate relationship.

    **Actions:**
    - **APPROVE**: Confirms candidate as valid for analytical schema.
    - **REJECT**: Declines candidate (records rejection note).
    - **EDIT**: Corrects target coordinates (requires edited_parent_table, edited_parent_column, edited_child_table, edited_child_column).
    """
    logger.info(
        f"POST /relationships/review | action={request.action} | "
        f"target='{request.parent_table}.{request.parent_column} -> {request.child_table}.{request.child_column}'"
    )

    # ── APPROVE ──────────────────────────────────────────────────────────────
    if request.action == RelationshipAction.APPROVE:
        try:
            approved = approve_relationship(
                parent_table=request.parent_table,
                parent_column=request.parent_column,
                child_table=request.child_table,
                child_column=request.child_column,
                analyst_note=request.analyst_note,
            )
            return RelationshipReviewResponse(
                status="success",
                message=(
                    f"Relationship '{approved.parent_table}.{approved.parent_column} -> "
                    f"{approved.child_table}.{approved.child_column}' approved successfully."
                ),
                relationship=approved,
            )
        except CandidateNotFoundError as e:
            logger.warning(f"Approve failed: candidate not found | {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )

    # ── REJECT ───────────────────────────────────────────────────────────────
    elif request.action == RelationshipAction.REJECT:
        try:
            rejected = reject_relationship(
                parent_table=request.parent_table,
                parent_column=request.parent_column,
                child_table=request.child_table,
                child_column=request.child_column,
                analyst_note=request.analyst_note,
            )
            return RelationshipReviewResponse(
                status="success",
                message=(
                    f"Relationship '{rejected.parent_table}.{rejected.parent_column} -> "
                    f"{rejected.child_table}.{rejected.child_column}' rejected successfully."
                ),
                relationship=rejected,
            )
        except CandidateNotFoundError as e:
            logger.warning(f"Reject failed: candidate not found | {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )

    # ── EDIT ─────────────────────────────────────────────────────────────────
    elif request.action == RelationshipAction.EDIT:
        try:
            edited = edit_relationship(
                parent_table=request.parent_table,
                parent_column=request.parent_column,
                child_table=request.child_table,
                child_column=request.child_column,
                edited_parent_table=request.edited_parent_table,
                edited_parent_column=request.edited_parent_column,
                edited_child_table=request.edited_child_table,
                edited_child_column=request.edited_child_column,
                analyst_note=request.analyst_note,
            )
            return RelationshipReviewResponse(
                status="success",
                message=(
                    f"Relationship edited and approved successfully: '{edited.parent_table}.{edited.parent_column} -> "
                    f"{edited.child_table}.{edited.child_column}' (original: '{edited.original_candidate}')."
                ),
                relationship=edited,
            )
        except CandidateNotFoundError as e:
            logger.warning(f"Edit failed: candidate not found | {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        except ValueError as e:
            logger.warning(f"Edit failed: validation error | {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported relationship action: '{request.action}'. Allowed: APPROVE, REJECT, EDIT.",
    )