from typing import Any, TypedDict


class ClinicalAnalyticsState(TypedDict, total=False):
    user_question: str
    selected_tables: list[str]
    # Table boundary validation
    validation_status: str
    reason: str
    required_tables: list[str]
    missing_tables: list[str]
    validation_message: str
    next_action: str

    # Human-in-the-loop approval
    approval_status: str
    approval_source: str
    human_feedback: str
    feedback_history: list[str]
    plan_version: int

    # Schema & Plan
    database_schema: dict[str, Any]
    analysis_plan: str
    current_plan: str
    clinical_question_plan: Any

    sql_query: str
    query_result: list[dict[str, Any]]
    results: list[dict[str, Any]]
    result_validation: dict[str, Any]

    # Deterministic evidence for insight generation
    insight_evidence: dict[str, Any]

    insight: str
    insight_retry_count: int

    # Visualization
    chart_spec: dict[str, Any]
    chart_figure: Any
    visualization_error: str

    error: str
    failed_node: str
    exception_type: str
    resume_from: str
    regenerate_sql: bool
    eda_findings: dict[str, Any]
    chart_validation: dict[str, Any]
    stage_status: dict[str, Any]
    stage_history: list[dict[str, Any]]
    validation_attempts: list[dict[str, Any]]
    retry_counts: dict[str, int]
    entry_stage: str
    analysis_id: str
    cancelled: bool
    data_signature: dict[str, Any]
    state_version: int
    result_retry_count: int
    validation_feedback: str
    cache_status: str
    quality_approved: bool
