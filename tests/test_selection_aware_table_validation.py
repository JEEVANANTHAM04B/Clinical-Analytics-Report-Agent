"""
Tests for Selection-Aware Table Validation in Clinical Analytics Platform.

Validates Requirements TEST A through TEST H:
- TEST A: Question requires ADAE and ADSL; only ADSL selected -> Block and request ADAE.
- TEST B: Question requires ADAE and ADSL; both selected -> Run complete pipeline.
- TEST C: Question requires ADLB and ADSL; only ADSL selected -> Request ADLB.
- TEST D: Question requires an unavailable/non-existent table -> Data source unavailable.
- TEST E: Question requires ADAE and ADSL; both selected, but generated SQL references ADLB -> Block unauthorized query.
- TEST F: Both selected initially, but user deselects ADAE before SQL execution -> Prevent execution with stale selection.
- TEST G: Question can be answered using ADSL alone; only ADSL selected -> Run without unnecessarily requesting ADAE.
- TEST H: Pipeline blocked because ADAE is missing; user selects ADAE and retries -> Revalidate and complete pipeline.
"""

import pytest
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.clinical.table_validator import (
    get_registered_tables,
    validate_selected_table_allowlist,
    identify_required_tables,
    check_table_selection,
    extract_sql_tables_ast,
    enforce_sql_table_boundaries,
)
from app.analytics.sql_validator import validate_sql
from app.workflow.graph import clinical_analytics_graph


def test_registered_tables_allowlist():
    """Verify application registered table allowlist."""
    registered = get_registered_tables()
    assert "adsl" in registered
    assert "adae" in registered
    assert "adlb" in registered
    assert "advs" in registered
    assert "dm" in registered


def test_a_block_when_adae_missing():
    """TEST A: Question requires ADAE and ADSL. Only ADSL is selected.
    Expected: Block analysis and request ADAE.
    """
    question = "What is the adverse event rate by treatment arm?"
    selected = ["adsl"]

    result = check_table_selection(question, selected)
    assert result["status"] == "blocked"
    assert result["reason"] == "required_tables_not_selected"
    assert "adae" in result["missing_tables"]
    assert "adsl" in result["required_tables"]
    assert "ADAE" in result["message"]

    # Graph invocation test
    state_input = {
        "user_question": question,
        "selected_tables": selected,
        "approval_status": "approved",
        "plan_version": 1,
    }
    graph_res = clinical_analytics_graph.invoke(state_input)
    assert graph_res["validation_status"] == "blocked"
    assert "adae" in graph_res["missing_tables"]
    # Ensure analytical pipeline did NOT run
    assert graph_res.get("sql_query") is None
    assert graph_res.get("results") is None or len(graph_res.get("results", [])) == 0


def test_b_run_when_both_selected():
    """TEST B: Question requires ADAE and ADSL. Both are selected.
    Expected: Run the complete analytical pipeline.
    """
    question = "What is the adverse event rate by treatment arm?"
    selected = ["adsl", "adae"]

    result = check_table_selection(question, selected)
    assert result["status"] == "passed"
    assert len(result["missing_tables"]) == 0

    # Step 1: Pending approval generates analysis plan
    res_pending = clinical_analytics_graph.invoke({
        "user_question": question,
        "selected_tables": selected,
        "approval_status": "pending",
        "plan_version": 1,
    })
    assert res_pending.get("validation_status") != "blocked"
    assert res_pending.get("analysis_plan") is not None
    assert res_pending.get("approval_status") == "pending"

    # Step 2: Approved plan executes complete pipeline
    res_approved = clinical_analytics_graph.invoke({
        "user_question": question,
        "selected_tables": selected,
        "approval_status": "approved",
        "current_plan": res_pending["analysis_plan"],
        "plan_version": 1,
    })
    assert res_approved.get("validation_status") != "blocked"
    assert res_approved.get("sql_query") is not None
    assert "adae" in res_approved["sql_query"].lower()
    query_rows = res_approved.get("query_result") or res_approved.get("results") or []
    assert len(query_rows) > 0


def test_c_request_adlb_when_missing():
    """TEST C: Question requires ADLB and ADSL. Only ADSL is selected.
    Expected: Request ADLB.
    """
    question = "What is the change in hemoglobin from baseline by treatment arm?"
    selected = ["adsl"]

    result = check_table_selection(question, selected)
    assert result["status"] == "blocked"
    assert "adlb" in result["missing_tables"]
    assert "ADLB" in result["message"]

    graph_res = clinical_analytics_graph.invoke({
        "user_question": question,
        "selected_tables": selected,
        "approval_status": "approved",
        "plan_version": 1,
    })
    assert graph_res["validation_status"] == "blocked"
    assert "adlb" in graph_res["missing_tables"]
    assert graph_res.get("sql_query") is None


def test_d_table_does_not_exist():
    """TEST D: Question requires a table that does not exist.
    Expected: Explain that the required data source is unavailable.
    """
    question = "Show the pharmacokinetic plasma concentration from the non_existent_pk_table"
    selected = ["adsl", "dm"]

    result = check_table_selection(question, selected)
    assert result["status"] == "blocked"
    assert (
        result["reason"] in ["required_table_unavailable", "required_tables_not_selected"]
        or "unavailable" in result["message"].lower()
    )


def test_e_ast_blocks_unauthorized_table_in_sql():
    """TEST E: Question requires ADAE and ADSL. Both are selected,
    but generated SQL also references ADLB.
    Expected: Block the unauthorized query via AST-based validation.
    """
    selected = ["adsl", "adae"]
    unauthorized_sql = """
        SELECT s.ARM, count(a.USUBJID) as ae_count
        FROM adsl s
        JOIN adae a ON s.USUBJID = a.USUBJID
        JOIN adlb l ON s.USUBJID = l.USUBJID
        GROUP BY s.ARM
    """

    allowed, unauth_tables = enforce_sql_table_boundaries(unauthorized_sql, selected)
    assert allowed is False
    assert "adlb" in unauth_tables

    is_valid, err = validate_sql(
        unauthorized_sql,
        approved_schema={"tables": {"adsl": [{"name": "arm"}, {"name": "usubjid"}], "adae": [{"name": "usubjid"}]}}
    )
    assert is_valid is False
    assert "adlb" in err.lower() or "unauthorized" in err.lower()


def test_f_deselect_before_execution_prevents_stale_run():
    """TEST F: Question requires ADAE and ADSL. Both are selected initially,
    but the user deselects ADAE before SQL execution.
    Expected: Prevent execution using the stale selection.
    """
    question = "What is the adverse event rate by treatment arm?"
    # Plan was generated when both were selected
    plan = "Join adsl and adae on USUBJID to calculate adverse event rates."

    # User deselects ADAE before approving
    stale_selected = ["adsl"]

    res_stale = clinical_analytics_graph.invoke({
        "user_question": question,
        "selected_tables": stale_selected,
        "approval_status": "approved",
        "current_plan": plan,
        "plan_version": 1,
    })

    assert res_stale.get("validation_status") == "blocked"
    assert "adae" in res_stale.get("missing_tables", [])
    # SQL must NOT have executed
    assert res_stale.get("sql_query") is None
    assert res_stale.get("results") is None or len(res_stale.get("results", [])) == 0


def test_g_adsl_alone_question():
    """TEST G: Question can be answered using ADSL alone. Only ADSL is selected.
    Expected: Run the pipeline without unnecessarily requesting ADAE.
    """
    question = "What is the total number of subjects by treatment arm in ADSL?"
    selected = ["adsl"]

    result = check_table_selection(question, selected)
    assert result["status"] == "passed"
    assert "adae" not in result["required_tables"]

    graph_res = clinical_analytics_graph.invoke({
        "user_question": question,
        "selected_tables": selected,
        "approval_status": "pending",
        "plan_version": 1,
    })
    assert graph_res.get("validation_status") != "blocked"
    assert graph_res.get("analysis_plan") is not None


def test_h_blocked_pipeline_resumes_when_user_selects_table():
    """TEST H: A pipeline is blocked because ADAE is missing.
    The user selects ADAE and retries.
    Expected: Revalidate and run the complete pipeline.
    """
    question = "What is the adverse event rate by treatment arm?"

    # Attempt 1: Blocked
    selected_1 = ["adsl"]
    res_1 = clinical_analytics_graph.invoke({
        "user_question": question,
        "selected_tables": selected_1,
        "approval_status": "approved",
        "plan_version": 1,
    })
    assert res_1["validation_status"] == "blocked"
    assert "adae" in res_1["missing_tables"]

    # Attempt 2: User adds ADAE to selection and retries
    selected_2 = ["adsl", "adae"]
    res_2 = clinical_analytics_graph.invoke({
        "user_question": question,
        "selected_tables": selected_2,
        "approval_status": "pending",
        "plan_version": 1,
    })
    assert res_2.get("validation_status") != "blocked"
    assert res_2.get("analysis_plan") is not None

    # Complete execution
    res_final = clinical_analytics_graph.invoke({
        "user_question": question,
        "selected_tables": selected_2,
        "approval_status": "approved",
        "current_plan": res_2["analysis_plan"],
        "plan_version": 1,
    })
    assert res_final.get("validation_status") != "blocked"
    query_rows = res_final.get("query_result") or res_final.get("results") or []
    assert len(query_rows) > 0
