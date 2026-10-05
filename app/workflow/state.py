from typing import Any, TypedDict


class ClinicalAnalyticsState(TypedDict, total=False):
    user_question: str
    selected_tables: list[str]
    database_schema: dict
    analysis_plan: str

    # Human-in-the-loop approval
    approval_status: str
    approval_source: str
    human_feedback: str
    feedback_history: list[str]
    plan_version: int

    sql_query: str
    query_result: list[dict[str, Any]]
    result_validation: dict[str, Any]

    # Deterministic evidence for insight generation
    insight_evidence: dict[str, Any]

    rag_context: str
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