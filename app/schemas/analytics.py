"""
app/schemas/analytics.py
=========================
Pydantic Schemas for Clinical Analytics API
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalyticsRequest(BaseModel):
    analysis_id: str | None = None
    action: Literal["continue", "retry", "stop", "approve_quality", "reject_quality"] = "continue"
    state_version: int | None = None
    """
    Request payload for running a clinical analytics question.
    """

    question: str = Field(
        ...,
        min_length=3,
        description="Natural-language clinical analytics question.",
        examples=[
            "What is the average length of stay by diagnosis?"
        ],
    )

    approval_status: str = Field(
        default="pending",
        description="Human approval status for the analysis plan.",
        examples=["pending", "approved", "rejected"],
    )

    human_feedback: str | None = Field(
        default=None,
        description="Human feedback provided when the analysis plan is rejected.",
    )

    selected_tables: list[str] | None = Field(
        default=None,
        description="Optional list of active tables to constrain query generation and analysis.",
    )

    current_plan: str | None = Field(
        default=None,
        description="The current analysis plan being reviewed, rejected, or approved.",
    )

    feedback_history: list[str] | None = Field(
        default=None,
        description="History of all previous human corrections across iterations.",
    )

    plan_version: int | None = Field(
        default=1,
        description="Version iteration counter of the analysis plan.",
    )

    sql_query: str | None = Field(
        default=None,
        description="Existing generated SQL query to resume or execute without re-generating.",
    )

    resume_from: str | None = Field(
        default=None,
        description="Specific workflow node to resume execution from (e.g. execute_sql).",
    )

    regenerate_sql: bool = Field(
        default=False,
        description="Whether to force regeneration of the SQL query.",
    )


class AnalyticsResponse(BaseModel):
    """
    Response returned by the clinical analytics workflow.
    """

    status: str
    question: str
    analysis_id: str | None = None
    state_version: int | None = None
    stage_status: dict[str, Any] | None = None
    eda_findings: dict[str, Any] | None = None
    validation_attempts: list[dict[str, Any]] = Field(default_factory=list)
    reason: str | None = None
    required_tables: list[str] = Field(default_factory=list)
    selected_tables: list[str] = Field(default_factory=list)
    missing_tables: list[str] = Field(default_factory=list)
    message: str | None = None
    next_action: str | None = None
    analysis_plan: str | None = None
    approval_status: str | None = None
    feedback_history: list[str] | None = None
    plan_version: int | None = None
    sql_query: str | None = None
    results: list[dict[str, Any]] = []
    insight: str | None = None
    chart_spec: dict[str, Any] | None = None
    visualization_error: str | None = None
    result_validation: dict[str, Any] | None = None
    insight_evidence: dict[str, Any] | None = None
    error: str | None = None
    failed_node: str | None = None
    exception_type: str | None = None


class OverviewResponse(BaseModel):
    """
    Response for general clinical overview dashboard.
    """
    status: str = "success"
    total_patients: int
    total_encounters: int
    avg_length_of_stay: float
    readmission_rate: float
    data_quality_status: str = "Fully Validated"
    organization_dataset: str = "Connected"
    dataset_name: str = "Organization EHR Dataset"
    encounter_classes: list[dict[str, Any]] = []
    top_diagnoses: list[dict[str, Any]] = []
    monthly_trends: list[dict[str, Any]] = []


class DashboardCustomizationRequest(BaseModel):
    """
    Request payload for customizing the dashboard by table selection.
    """
    tables: list[str] = Field(
        default_factory=list,
        description="List of selected clinical tables to include in dashboard calculation."
    )


class DashboardCustomizationResponse(BaseModel):
    """
    Response containing real MySQL calculations for selected tables.
    """
    status: str = "success"
    valid_combination: bool = True
    message: str | None = None
    selected_tables: list[str] = []
    total_patients: int | None = None
    total_encounters: int | None = None
    primary_metric_label: str = "TOTAL PATIENTS"
    primary_metric_value: str = "0"
    kpi_cards: list[dict[str, Any]] = []
    chart_spec: dict[str, Any] | None = None
    chart_categories: list[str] = []
    chart_values: list[float] = []
    chart_title: str = "Clinical Analytics Overview"
    secondary_chart_title: str | None = None
    encounter_classes: list[dict[str, Any]] = []
    monthly_trends: list[dict[str, Any]] = []
    verified_results: list[dict[str, Any]] = []
    insight: str | None = None
    key_finding: str = "Key Clinical Finding"
    key_finding_value: str = "--"
    suggested_questions: list[str] = []


class ConversationTurn(BaseModel):
    """A single turn in the session conversation history."""
    role: str = "user"  # "user" | "assistant"
    content: str


class FollowUpRequest(BaseModel):
    """
    Request payload for answering a lightweight clinical follow-up question.
    """
    question: str = Field(..., min_length=1, description="Follow-up question")
    current_question: str | None = None
    current_results: list[dict[str, Any]] = Field(default_factory=list)
    original_results: list[dict[str, Any]] = Field(default_factory=list)
    current_sql: str | None = None
    current_plan: str | None = None
    current_insight: str | None = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    selected_tables: list[str] = Field(default_factory=list)


class FollowUpResponse(BaseModel):
    """
    Response returned by the lightweight follow-up analysis engine.
    """
    status: str = "success"
    question: str
    answer: str
    source: str = "verified_results"  # "verified_results" | "follow_up_sql" | "new_analysis"
    is_new_analysis: bool = False
    sql_query: str | None = None
    verified: bool = True
    confidence: float = 0.95
    follow_up_results: list[dict[str, Any]] = Field(default_factory=list)


