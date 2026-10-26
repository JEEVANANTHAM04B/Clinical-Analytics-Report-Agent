"""Stage recovery using the existing operational tables in MySQL."""
from threading import RLock
from sqlalchemy import select, func
from fastapi import HTTPException
from app.workflow.store import Store
from app.database.models import DatasetVersion
from app.database.schema_service import get_database_schema
from app.workflow.graph import build_graph
from app.workflow.reliability import retry_limit

LOCK = RLock()  # This synchronous service supports one API worker.
ORDER = ["preflight_table_selection", "load_schema", "analyze_question", "human_approval", "validate_table_selection", "generate_sql", "validate_sql",
         "execute_sql", "validate_results", "generate_insight", "validate_insight", "generate_chart"]
OUTPUTS = {"generate_sql": ["sql_query"], "execute_sql": ["query_result"],
    "validate_results": ["result_validation", "insight_evidence"],
    "generate_insight": ["insight"], "generate_chart": ["chart_spec", "chart_validation"]}


def signature(engine, tables):
    schema = get_database_schema()
    with engine.connect() as conn:
        versions = dict(conn.execute(select(DatasetVersion.dataset_name, func.max(DatasetVersion.id))
            .where(DatasetVersion.status == "LOADED", DatasetVersion.dataset_name.in_(tables))
            .group_by(DatasetVersion.dataset_name)).all())
    return {"schema": schema, "versions": {t: versions.get(t) for t in tables}}


def execute(request, engine, initial):
    with LOCK:
        store = Store(engine=engine)
        if request.analysis_id:
            try:
                run = store.get(request.analysis_id)
                state = store.latest_artifact(request.analysis_id, "main_state")
            except KeyError:
                raise HTTPException(404, "Analysis not found.")
            if request.state_version != state["state_version"]:
                raise HTTPException(409, "This analysis changed. Refresh before submitting a decision.")
            if request.action in {"stop", "reject_quality"}:
                state.update(cancelled=True, error="Analysis cancelled.", stage_status={"stage": state.get("failed_node", "human_approval"), "status": "CANCELLED"})
                state["state_version"] += 1
                store.artifact(run["id"], "main_state", state["state_version"], state)
                store.status(run["id"], "CANCELLED")
                store.event(run["id"], "analysis_cancelled", {"decision": request.action})
                return state
            if state.get("cancelled"): raise HTTPException(409, "This analysis was cancelled. Start a new analysis.")
            if request.question != state["user_question"] or sorted(request.selected_tables or []) != sorted(state.get("selected_tables", [])):
                raise HTTPException(409, "Question or datasets changed. Start a new analysis and approve a fresh plan.")
            current = signature(engine, state["selected_tables"])
            if current != state["data_signature"]:
                raise HTTPException(409, "Dataset or schema changed. Start a new analysis.")
            # A snapshot written by the former graph may contain a superseded
            # analysis-time profile; never carry it into a new execution path.
            state.pop("eda_findings", None)
            state.pop("quality_approved", None)
            if request.action == "approve_quality":
                raise HTTPException(409, "This analysis has no pending quality-review stage. Refresh the analysis.")
            elif request.action == "retry":
                stage = state.get("failed_node")
                if not stage or stage not in ORDER or not state.get("stage_status", {}).get("recoverable"):
                    raise HTTPException(409, "This failure requires review or a new analysis.")
                if stage in ORDER[ORDER.index("validate_results"):] and not all(current["versions"].values()):
                    raise HTTPException(409, "Dataset versions are unavailable; start a new analysis to avoid stale results.")
                counts = state.get("retry_counts", {})
                if counts.get(stage, 0) >= retry_limit(): raise HTTPException(409, "Retry limit reached.")
                state["retry_counts"] = {**counts, stage: counts.get(stage, 0)+1}
                for dependent in ORDER[ORDER.index(stage):]:
                    for key in OUTPUTS.get(dependent, []): state.pop(key, None)
                state.update(error="", failed_node=None, entry_stage=stage)
                store.event(run["id"], "retry_started", {"stage": stage, "attempt": counts.get(stage, 0)+1})
            else:
                if state.get("approval_status") != "pending" or state.get("error"):
                    raise HTTPException(409, "No plan decision is pending.")
                state.update(approval_status=request.approval_status, human_feedback=request.human_feedback or "", entry_stage="human_approval")
                store.event(run["id"], "plan_decision", {"decision": request.approval_status})
        else:
            if request.action != "continue": raise HTTPException(409, "Select a saved analysis first.")
            run = store.create({"study_id": "__main_workspace__", "question": request.question})
            state = {**initial, "analysis_id": run["id"], "state_version": 0,
                     "data_signature": signature(engine, initial["selected_tables"])}
            # Never accept a first-request approval of a client-authored plan on the durable path.
            state.update(approval_status="pending")
            state.pop("analysis_plan", None)
            state.pop("sql_query", None)
        def save(snapshot):
            snapshot["state_version"] = snapshot.get("state_version", 0)+1
            store.artifact(run["id"], "main_state", snapshot["state_version"], snapshot)
            store.status(run["id"], snapshot.get("stage_status", {}).get("status", "RUNNING"), snapshot["state_version"])
            store.event(run["id"], "stage", snapshot.get("stage_status", {}))
            state["state_version"] = snapshot["state_version"]
        result = build_graph(on_stage=save).invoke(state, {"recursion_limit": 100})
        # The callback owns the persisted revision; return its exact last snapshot.
        return store.latest_artifact(run["id"], "main_state")
