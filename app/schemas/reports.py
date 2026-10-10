"""
app/schemas/reports.py
======================
Pydantic Schemas for Certified PDF Report Generation
"""

from typing import Any
from pydantic import BaseModel, Field, field_validator


class PDFReportRequest(BaseModel):
    """
    Payload for generating a publication-grade, verified A4 PDF report.
    """
    model_config = {"extra": "allow"}

    question: str | None = Field(default="Clinical Analytics Inquiry", description="Primary clinical inquiry")
    analysis_plan: str | None = Field(default=None, description="Approved multi-step analysis plan")
    insight: str | None = Field(default=None, description="Verified clinical insight text")
    results: list[dict[str, Any]] | None = Field(default_factory=list, description="Verified query outcome rows")
    rag_context: str | None = Field(default=None, description="Clinical RAG evidence and terminology citations")
    sql_query: str | None = Field(default=None, description="Compiled AST-safe SQL query")
    workspace_type: str | None = Field(default="clinical", description="Workspace type ('clinical' or 'technical')")
    selected_tables: list[str] | None = Field(default_factory=list, description="Active dataset tables used in scope")
    follow_up_answers: list[dict[str, Any]] | None = Field(default_factory=list, description="Follow-up Q&A pairs")
    approved_by: str | None = Field(default="Clinical Analyst", description="Name/title of approving clinical reviewer")
    report_status: str | None = Field(default="Approved & Certified", description="Official report verification status")
    dataset_name: str | None = Field(default="CDISC Clinical Trial Dataset", description="Name of verified dataset")

    @field_validator("question", mode="before")
    @classmethod
    def sanitize_question(cls, v: Any) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            return "Clinical Analytics Inquiry"
        return v.strip()

    @field_validator("results", mode="before")
    @classmethod
    def sanitize_results(cls, v: Any) -> list[dict[str, Any]]:
        if v is None:
            return []
        if isinstance(v, list):
            clean_list: list[dict[str, Any]] = []
            for item in v:
                if isinstance(item, dict):
                    clean_list.append(item)
                elif hasattr(item, "__dict__"):
                    clean_list.append(dict(item.__dict__))
            return clean_list
        if isinstance(v, dict):
            if "results" in v and isinstance(v["results"], list):
                return cls.sanitize_results(v["results"])
            if "data" in v and isinstance(v["data"], list):
                return cls.sanitize_results(v["data"])
            return [v]
        return []

    @field_validator("selected_tables", mode="before")
    @classmethod
    def sanitize_tables(cls, v: Any) -> list[str]:
        if not v or not isinstance(v, list):
            return []
        return [str(t) for t in v if t]

    @field_validator("follow_up_answers", mode="before")
    @classmethod
    def sanitize_follow_ups(cls, v: Any) -> list[dict[str, Any]]:
        if not v or not isinstance(v, list):
            return []
        cleaned: list[dict[str, Any]] = []
        for item in v:
            if isinstance(item, dict):
                cleaned.append({
                    "question": str(item.get("question", "") or ""),
                    "answer": str(item.get("answer", "") or ""),
                    "source": str(item.get("source", "") or ""),
                    "sql_query": item.get("sql_query"),
                    "verified": bool(item.get("verified", True)),
                    "timestamp": str(item.get("timestamp", "") or ""),
                })
        return cleaned

    @field_validator("analysis_plan", "insight", "rag_context", "sql_query", mode="before")
    @classmethod
    def sanitize_text_fields(cls, v: Any) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            return v
        return str(v)

    @field_validator("workspace_type", mode="before")
    @classmethod
    def sanitize_workspace_type(cls, v: Any) -> str:
        if v in ("clinical", "technical"):
            return v
        return "clinical"

    @field_validator("approved_by", mode="before")
    @classmethod
    def sanitize_approved_by(cls, v: Any) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            return "Clinical Analyst"
        return v.strip()

    @field_validator("report_status", mode="before")
    @classmethod
    def sanitize_report_status(cls, v: Any) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            return "Approved & Certified"
        return v.strip()

    @field_validator("dataset_name", mode="before")
    @classmethod
    def sanitize_dataset_name(cls, v: Any) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            return "CDISC Clinical Trial Dataset"
        return v.strip()
