"""
app/schemas/relationships.py
============================
Pydantic schemas for Phase 4 — Relationship Review & Human Confirmation.

Workflow:
    POST /ingestion/analyze
            ↓
    Detected relationship candidates
            ↓
    GET /relationships/candidates
            ↓
    Analyst reviews actual candidates
            ↓
    POST /relationships/review (APPROVE / REJECT / EDIT)
            ↓
    GET /relationships/approved | GET /relationships/rejected
"""

from enum import Enum
from typing import Optional, List, Union
from pydantic import BaseModel, Field

from app.schemas.validation import RelationshipAnalysis


class RelationshipAction(str, Enum):
    """Allowed actions an analyst can take on a relationship candidate."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EDIT = "EDIT"


class RelationshipReviewRequest(BaseModel):
    """
    Analyst decision for a detected relationship candidate.
    Must reference an existing detected relationship candidate.
    """
    parent_table: str = Field(
        ...,
        description="Parent table name of the detected candidate, e.g. 'patients'",
    )
    parent_column: str = Field(
        ...,
        description="Parent primary-key column, e.g. 'ID'",
    )
    child_table: str = Field(
        ...,
        description="Child table name of the detected candidate, e.g. 'encounters'",
    )
    child_column: str = Field(
        ...,
        description="Child foreign-key column, e.g. 'PATIENT'",
    )
    action: RelationshipAction = Field(
        ...,
        description="Analyst action: APPROVE, REJECT, or EDIT",
    )
    edited_parent_table: Optional[str] = Field(
        None,
        description="New parent table when action is EDIT",
    )
    edited_parent_column: Optional[str] = Field(
        None,
        description="New parent column when action is EDIT",
    )
    edited_child_table: Optional[str] = Field(
        None,
        description="New child table when action is EDIT",
    )
    edited_child_column: Optional[str] = Field(
        None,
        description="New child column when action is EDIT",
    )
    analyst_note: Optional[str] = Field(
        None,
        description="Optional rationale or clinical explanation for the decision",
    )


class ApprovedRelationship(BaseModel):
    """
    Relationship that has been explicitly approved by a human analyst.
    """
    parent_table: str
    parent_column: str
    child_table: str
    child_column: str
    status: str = Field(
        default="APPROVED",
        description="Approval status",
    )
    analyst_note: Optional[str] = None
    was_edited: bool = Field(
        default=False,
        description="True if this relationship was modified from the original detected candidate",
    )
    original_candidate: Optional[str] = Field(
        default=None,
        description="Original candidate reference if edited, e.g. 'patients.ID -> encounters.PATIENT'",
    )


class RejectedRelationship(BaseModel):
    """
    Relationship candidate that has been rejected by a human analyst.
    """
    parent_table: str
    parent_column: str
    child_table: str
    child_column: str
    status: str = Field(
        default="REJECTED",
        description="Rejection status",
    )
    analyst_note: Optional[str] = None


class RelationshipReviewResponse(BaseModel):
    """
    Response returned after processing an analyst relationship decision.
    """
    status: str = Field("success", description="'success' or 'error'")
    message: str = Field(..., description="Action outcome description")
    relationship: Union[ApprovedRelationship, RejectedRelationship] = Field(
        ...,
        description="The resulting approved or rejected relationship record",
    )


class RelationshipCandidatesResponse(BaseModel):
    """
    Response returned by GET /relationships/candidates containing all detected candidates.
    """
    status: str = Field("success", description="'success' or 'error'")
    message: str = Field(..., description="Status message")
    count: int = Field(..., description="Number of candidate relationships")
    candidates: List[RelationshipAnalysis] = Field(
        default_factory=list,
        description="List of detected relationship candidates from Phase 3 analysis",
    )


class ApprovedRelationshipsResponse(BaseModel):
    """
    Response returned by GET /relationships/approved.
    """
    status: str = Field("success", description="'success' or 'error'")
    count: int = Field(..., description="Total number of approved relationships")
    relationships: List[ApprovedRelationship] = Field(
        default_factory=list,
        description="List of approved relationships",
    )


class RejectedRelationshipsResponse(BaseModel):
    """
    Response returned by GET /relationships/rejected.
    """
    status: str = Field("success", description="'success' or 'error'")
    count: int = Field(..., description="Total number of rejected relationships")
    relationships: List[RejectedRelationship] = Field(
        default_factory=list,
        description="List of rejected relationships",
    )
class RelationshipRegenerateRequest(BaseModel):
    """
    Request to generate an alternative relationship proposal
    after an analyst rejects the current relationship.
    """
    parent_table: str = Field(
        ...,
        description="Rejected relationship parent table",
    )
    parent_column: str = Field(
        ...,
        description="Rejected relationship parent column",
    )
    child_table: str = Field(
        ...,
        description="Rejected relationship child table",
    )
    child_column: str = Field(
        ...,
        description="Rejected relationship child column",
    )
    analyst_feedback: str = Field(
        ...,
        min_length=1,
        description="Analyst explanation of why the relationship is not appropriate",
    )

    directory_path: Optional[str] = Field(
        None,
        description="Directory containing the clinical datasets",
    )
    file_paths: Optional[List[str]] = Field(
        None,
        description="Explicit dataset file paths",
    )
    filenames: Optional[List[str]] = Field(
        None,
        description="Dataset filenames to locate",
    )


class RelationshipRegenerateResponse(BaseModel):
    """
    Response containing the AI-proposed alternative relationship
    and deterministic validation evidence.
    """
    status: str = Field(
        default="success",
        description="'success' or 'error'",
    )
    message: str
    proposal: dict
    validation: Optional[dict] = None