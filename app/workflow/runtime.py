"""Bounded stage execution with sanitized outcomes and optional durable snapshots."""
from app.workflow.reliability import failure, retry_limit, transient
from app.audit.service import record_audit_event


def stage_wrapper(stage, fn, on_stage=None):
    def run(state):
        if state.get("cancelled"):
            return {"error": "Analysis cancelled.", "stage_status": {"stage": stage, "status": "CANCELLED"}}
        if state.get("error") and stage not in {"regenerate_insight", "correct_results"}:
            return {}
        limit = retry_limit()
        result = {}
        for attempt in range(limit + 1):
            retryable = False
            try:
                result = fn(state)
                if not result.get("error"):
                    required = {"load_schema": "database_schema", "analyze_question": "analysis_plan", "regenerate_analysis_plan": "analysis_plan",
                        "generate_sql": "sql_query", "generate_insight": "insight", "regenerate_insight": "insight"}.get(stage)
                    if required and not result.get(required): raise ValueError("Required output is missing")
                    if stage == "load_schema" and not result.get("database_schema", {}).get("tables"):
                        raise ValueError("Dataset schema is empty")
                    break
                retryable = result.get("exception_type") in {"ConnectionError"}
            except Exception as exc:
                retryable = transient(exc)
                result = {"error": "Stage failed", "exception_type": type(exc).__name__, "failed_node": stage}
            if not retryable or attempt == limit: break
            record_audit_event(action="STAGE_RETRY", details=f"{stage}: attempt {attempt+1}", status="RETRYING")
        if result.get("error"):
            outcome = failure(stage, result.get("exception_type", "VALIDATION_FAILED"), retryable, attempt)
            if result.get("validation_feedback"):
                outcome["message"] = result["validation_feedback"]
            result.update(error=outcome["message"], failed_node=stage)
        else:
            outcome = {"stage": stage, "status": "SUCCESS", "retry_count": attempt, "max_retries": limit}
            if stage == "human_approval" and result.get("approval_status") != "approved":
                outcome["status"] = "USER_DECISION_REQUIRED"
        result["stage_status"] = outcome
        result["stage_history"] = [*state.get("stage_history", []), outcome]
        record_audit_event(action="WORKFLOW_STAGE", details=f"{stage}: {outcome['status']}; attempt={attempt}",
            status=outcome["status"], entity_name=state.get("analysis_id", "clinical_analytics"))
        if on_stage:
            snapshot = {**state, **result}
            on_stage(snapshot)
            result["state_version"] = snapshot.get("state_version", 0)
        return result
    return run
