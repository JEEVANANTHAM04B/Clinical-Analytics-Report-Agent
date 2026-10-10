"""
tests/evaluation/test_security_boundaries.py
============================================
Comprehensive test suite verifying the 8 critical security boundaries:
1. Approved & selected tables proceed.
2. Missing required table is blocked without SQL execution.
3. Custom unapproved table (biomarker_results) is blocked.
4. Second unapproved custom table (clinical_endpoints) is blocked.
5. Hidden/unauthorized table in generated SQL is rejected by AST.
6. Test/demo table (sample_clinical_data) is blocked.
7. Approved table that is NOT selected by user is blocked.
8. Destructive or malicious SQL injection is blocked.
"""

import pytest
from app.clinical.table_validator import (
    get_registered_tables,
    validate_selected_table_allowlist,
    check_table_selection,
    enforce_sql_table_boundaries,
)
from app.analytics.sql_validator import validate_sql
from app.workflow.graph import clinical_analytics_graph


def test_sec_1_approved_and_selected_tables():
    """TEST 1: Approved and selected tables proceed normally."""
    question = "What is the adverse event incidence rate by treatment arm?"
    selected = ["adsl", "adae"]

    res = check_table_selection(question, selected)
    assert res["status"] == "passed", f"Expected check_table_selection to pass, got: {res}"
    assert len(res["missing_tables"]) == 0

    # AST validation confirms authorized tables
    sql = "SELECT TRT01A, COUNT(DISTINCT USUBJID) FROM adsl GROUP BY TRT01A"
    is_auth, unauth = enforce_sql_table_boundaries(sql, selected)
    assert is_auth is True
    assert len(unauth) == 0


def test_sec_2_required_table_missing_from_selection():
    """
    TEST 2: Required table missing from selection.
    Question requires ADAE and ADSL, but user only selected ADSL.
    Expected: Blocked; no SQL generated or executed; no fake KPIs.
    """
    question = "What is the adverse event incidence rate by treatment arm?"
    selected = ["adsl"]

    res = check_table_selection(question, selected)
    assert res["status"] == "blocked"
    assert res["reason"] == "required_tables_not_selected"
    assert "adae" in res["missing_tables"]

    # Graph invocation must stop at boundary guard
    state_input = {
        "user_question": question,
        "selected_tables": selected,
        "approval_status": "approved",
    }
    graph_out = clinical_analytics_graph.invoke(state_input)
    assert graph_out.get("validation_status") == "blocked"
    assert graph_out.get("sql_query") is None
    assert graph_out.get("results") is None or len(graph_out.get("results", [])) == 0
    assert graph_out.get("chart_spec") is None


def test_sec_3_custom_unapproved_table_biomarker_results():
    """
    TEST 3: Custom unapproved table.
    'biomarker_results' exists in MySQL with 4 rows, but registry status is CUSTOM / PENDING.
    Expected: Blocked from selection and query.
    """
    question = "Analyze the records in biomarker_results."
    selected = ["biomarker_results"]

    is_valid, valid, unknown = validate_selected_table_allowlist(selected)
    assert is_valid is False
    assert "biomarker_results" in unknown

    res = check_table_selection(question, selected)
    assert res["status"] == "blocked"
    assert res["reason"] == "invalid_table_selection"


def test_sec_4_custom_unapproved_table_clinical_endpoints():
    """
    TEST 4: Another unapproved custom table.
    'clinical_endpoints' exists in MySQL with 3 rows, but registry status is CUSTOM / PENDING.
    Expected: Blocked from selection and query.
    """
    question = "Summarize clinical_endpoints."
    selected = ["clinical_endpoints"]

    is_valid, valid, unknown = validate_selected_table_allowlist(selected)
    assert is_valid is False
    assert "clinical_endpoints" in unknown

    res = check_table_selection(question, selected)
    assert res["status"] == "blocked"
    assert res["reason"] == "invalid_table_selection"


def test_sec_5_hidden_table_referenced_by_sql():
    """
    TEST 5: Hidden or unapproved table referenced by SQL.
    User selected only approved 'adsl', but SQL attempts to join 'biomarker_results'.
    Expected: AST parser detects unauthorized table reference and rejects query.
    """
    unauthorized_sql = (
        "SELECT a.USUBJID, b.GENE FROM adsl a "
        "JOIN biomarker_results b ON a.USUBJID = b.USUBJID"
    )
    selected = ["adsl"]

    is_auth, unauth = enforce_sql_table_boundaries(unauthorized_sql, selected)
    assert is_auth is False
    assert "biomarker_results" in unauth


def test_sec_6_test_demo_table_access():
    """
    TEST 6: Test/demo table.
    'sample_clinical_data' exists in MySQL (40 rows) classified as DEMO.
    Expected: Excluded from registered clinical tables and blocked.
    """
    registered = get_registered_tables()
    assert "sample_clinical_data" not in registered

    res = check_table_selection("What is in sample_clinical_data?", ["sample_clinical_data"])
    assert res["status"] == "blocked"
    assert res["reason"] == "invalid_table_selection"


def test_sec_7_approved_table_not_selected():
    """
    TEST 7: Approved clinical table that was NOT selected by user.
    User selected 'dm', but query tries to access approved 'adae'.
    Expected: Rejected because 'adae' is not in the active selection allowlist.
    """
    sql = "SELECT AEDECOD, COUNT(*) FROM adae GROUP BY AEDECOD"
    selected = ["dm"]

    is_auth, unauth = enforce_sql_table_boundaries(sql, selected)
    assert is_auth is False
    assert "adae" in unauth


def test_sec_8_destructive_malicious_sql(sql_safety_metric):
    """
    TEST 8: Malicious and destructive SQL queries.
    Expected: Regex and AST safety guards block destructive operations.
    """
    malicious_queries = [
        "DROP TABLE dm;",
        "SELECT * FROM dm; DELETE FROM adsl;",
        "ALTER TABLE adae ADD COLUMN hacked VARCHAR(100);",
        "TRUNCATE TABLE vs;",
        "SELECT * FROM dm WHERE 1=1; DROP TABLE ae; --",
        "INSERT INTO sites (SITEID) VALUES ('HACK');",
        "UPDATE adsl SET ARM = 'Poison' WHERE 1=1;",
    ]
    selected = ["dm", "adsl", "adae", "vs", "ae", "sites"]

    for query in malicious_queries:
        eval_res = sql_safety_metric.evaluate_query(query, selected)
        assert eval_res["passed"] is False, f"Malicious query was not blocked: '{query}'"
        assert len(eval_res["violations"]) > 0
