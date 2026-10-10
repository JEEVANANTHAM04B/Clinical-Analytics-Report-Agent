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
    RelationshipRegenerateRequest,
    RelationshipRegenerateResponse,
)

from app.ingestion.relationship_review import (
    get_relationship_candidates,
    get_approved_relationships,
    get_rejected_relationships,
    approve_relationship,
    reject_relationship,
    edit_relationship,
    regenerate_relationship,
    CandidateNotFoundError,
)
from app.ingestion.analyzer import (
    resolve_files_to_analyze,
    analyze_single_dataset,
    read_dataset_schema,
)
from app.core.logging_config import get_logger
from pathlib import Path

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
# =============================================================================
# POST /relationships/regenerate
# =============================================================================

@router.post(
    "/regenerate",
    response_model=RelationshipRegenerateResponse,
    summary="Generate an Alternative Relationship",
    description=(
        "Generates an alternative relationship proposal after an analyst "
        "rejects the current relationship. The proposal is generated by "
        "the LLM and then deterministically validated against the actual "
        "dataset schemas and referential integrity."
    ),
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/regenerate",
    response_model=RelationshipRegenerateResponse,
    summary="Generate an Alternative Relationship",
    description=(
        "Generates an alternative relationship proposal after an analyst "
        "rejects the current relationship. The proposal is generated by "
        "the LLM and then deterministically validated against the actual "
        "dataset schemas and referential integrity."
    ),
    status_code=status.HTTP_200_OK,
)
def regenerate_relationship_endpoint(
    request: RelationshipRegenerateRequest,
):
    """
    Generate and validate an alternative relationship proposal.

    Workflow:
        Rejected relationship
                ↓
        Analyst feedback
                ↓
        Read schemas only
                ↓
        AI proposes alternative
                ↓
        Load only proposed parent/child datasets
                ↓
        Deterministic relationship validation
                ↓
        Return proposal and validation evidence
    """

    logger.info(
        "POST /relationships/regenerate | "
        f"rejected='{request.parent_table}.{request.parent_column} -> "
        f"{request.child_table}.{request.child_column}'"
    )

    # -------------------------------------------------------------------------
    # Step 1: Resolve dataset files
    # -------------------------------------------------------------------------

    try:
        file_paths = resolve_files_to_analyze(
            directory_path=request.directory_path,
            file_paths=request.file_paths,
            filenames=request.filenames,
        )

    except FileNotFoundError as e:
        logger.warning(
            f"Relationship regeneration dataset resolution failed: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except Exception as e:
        logger.exception(
            "Unexpected error resolving datasets for relationship regeneration"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # -------------------------------------------------------------------------
    # Step 2: Read schemas only
    # -------------------------------------------------------------------------

    schema_catalog = {}

    try:
        for file_path in file_paths:
            dataset_name, columns = read_dataset_schema(file_path)
            schema_catalog[dataset_name] = columns

        logger.info(
            "Read schema for %d dataset(s) for relationship regeneration",
            len(schema_catalog),
        )

    except Exception as e:
        logger.exception(
            "Failed to read dataset schemas for relationship regeneration"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read dataset schemas: {str(e)}",
        )

    # -------------------------------------------------------------------------
    # Step 3: Generate alternative relationship using schema only
    # -------------------------------------------------------------------------

    try:
        result = regenerate_relationship(
            parent_table=request.parent_table,
            parent_column=request.parent_column,
            child_table=request.child_table,
            child_column=request.child_column,
            analyst_feedback=request.analyst_feedback,
            datasets=schema_catalog,
        )

        proposal = result["proposal"]
        validation = result["validation"]

        # ---------------------------------------------------------------------
        # Step 4: If LLM found an alternative, load ONLY the two datasets
        # ---------------------------------------------------------------------

        if (
            proposal.status == "VALID_ALTERNATIVE"
            and proposal.is_valid_schema
        ):
            proposed_tables = {
                proposal.parent_table.lower(),
                proposal.child_table.lower(),
            }

            selected_datasets = {}

            for file_path in file_paths:
                path_obj = Path(file_path)

                dataset_name = (
                    path_obj.stem.lower()
                    .replace("analytics_", "")
                )

                if dataset_name in proposed_tables:
                    analysis, df = analyze_single_dataset(file_path)

                    selected_datasets[analysis.dataset_name] = (
                        analysis.filename,
                        df,
                    )

            logger.info(
                "Loaded %d dataset(s) for deterministic relationship validation",
                len(selected_datasets),
            )

            # -------------------------------------------------------------
            # Step 5: Run deterministic validation on selected datasets
            # -------------------------------------------------------------

            from app.ingestion.relationship_regenerator import (
                validate_proposed_relationship,
            )

            validation = validate_proposed_relationship(
                proposal=proposal,
                datasets=selected_datasets,
            )

        logger.info(
            "Relationship regeneration completed | "
            f"status={proposal.status}"
        )

        return RelationshipRegenerateResponse(
            status="success",
            message=(
                "Alternative relationship proposal generated successfully."
                if proposal.status == "VALID_ALTERNATIVE"
                else "No valid alternative relationship was found."
            ),
            proposal=proposal.model_dump(),
            validation=validation,
        )

    except Exception as e:
        logger.exception(
            "Relationship regeneration failed"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Relationship regeneration failed: {str(e)}",
        )