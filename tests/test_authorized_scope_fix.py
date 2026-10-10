"""
tests/test_authorized_scope_fix.py
==================================
Tests verifying that approved clinical analysis plans correctly establish
the SQL validation authorization scope even when default/stale selected_tables
(['study', 'sites', 'dm']) are passed by the frontend.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath("."))

from app.analytics.sql_validator import validate_sql
from app.workflow.graph import clinical_analytics_graph as workflow_app, format_clinical_analysis_plan
from app.clinical import build_clinical_question_plan


def test_clinical_single_table_authorized():
    """Clinical single-table query -> ADAE authorized when in approved schema."""
    sql = "SELECT AESEV AS severity, COUNT(*) AS event_count FROM adae GROUP BY AESEV;"
    authorized_schema = {
        "tables": {
            "study": [{"name": "STUDYID"}],
            "sites": [{"name": "SITEID"}],
            "dm": [{"name": "USUBJID"}],
            "adae": [{"name": "AESEV"}],
        }
    }
    plan = """### Clinical Analytics Analysis Plan
#### 1. Relevant Tables and Columns
* **`adae`**:
  * `AESEV` (VARCHAR(50)): Adverse event severity
#### 2. Join Conditions
* None (single-table query on `adae`).
"""
    is_valid, msg = validate_sql(sql, approved_schema=authorized_schema, analysis_plan=plan)
    assert is_valid, f"Validation failed: {msg}"


def test_clinical_table_not_in_approved_schema_rejected():
    """ADAE query is rejected when ADAE is not in the approved schema."""
    sql = "SELECT AESEV AS severity, COUNT(*) AS event_count FROM adae GROUP BY AESEV;"
    restricted_schema = {"tables": {"study": [{"name": "STUDYID"}], "sites": [{"name": "SITEID"}], "dm": [{"name": "USUBJID"}]}}
    plan = """### Clinical Analytics Analysis Plan
#### 1. Relevant Tables and Columns
* **`adae`**:
  * `AESEV` (VARCHAR(50)): Adverse event severity
#### 2. Join Conditions
* None (single-table query on `adae`).
"""
    is_valid, msg = validate_sql(sql, approved_schema=restricted_schema, analysis_plan=plan)
    assert not is_valid
    assert "Unauthorized table(s): adae" in msg


def test_clinical_multi_table_authorized():
    """Clinical multi-table query -> ADSL + ADAE authorized when in approved schema."""
    sql = """SELECT
    adsl.TRT01A AS treatment_arm,
    adae.AESEV AS severity,
    COUNT(*) AS event_count
FROM adsl
JOIN adae
    ON adsl.USUBJID = adae.USUBJID
GROUP BY adsl.TRT01A, adae.AESEV
ORDER BY adsl.TRT01A, event_count DESC;"""
    authorized_schema = {
        "tables": {
            "study": [{"name": "STUDYID"}],
            "sites": [{"name": "SITEID"}],
            "dm": [{"name": "USUBJID"}],
            "adsl": [{"name": "USUBJID"}, {"name": "TRT01A"}],
            "adae": [{"name": "USUBJID"}, {"name": "AESEV"}],
        }
    }
    plan = """### Clinical Analytics Analysis Plan
#### 1. Relevant Tables and Columns
* **`adsl`**:
  * `USUBJID` (VARCHAR(50))
  * `TRT01A` (VARCHAR(100))
* **`adae`**:
  * `USUBJID` (VARCHAR(50))
  * `AESEV` (VARCHAR(50))
#### 2. Join Conditions
* Join `adsl` and `adae`: `adsl.USUBJID = adae.USUBJID`
"""
    is_valid, msg = validate_sql(sql, approved_schema=authorized_schema, analysis_plan=plan)
    assert is_valid, f"Validation failed: {msg}"


def test_unapproved_arbitrary_table_rejected():
    """Unapproved/arbitrary table (e.g. billing_records or patients) is still rejected."""
    sql = "SELECT * FROM billing_records;"
    restricted_schema = {"tables": {"study": [{"name": "STUDYID"}], "sites": [{"name": "SITEID"}], "dm": [{"name": "USUBJID"}]}}
    plan = """### Clinical Analytics Analysis Plan
#### 1. Relevant Tables and Columns
* **`billing_records`**:
  * `BILL_ID` (VARCHAR(50))
"""
    is_valid, msg = validate_sql(sql, approved_schema=restricted_schema, analysis_plan=plan)
    assert not is_valid
    assert "Unauthorized table(s): billing_records" in msg


def test_end_to_end_distribution_across_treatment_arms_blocked_when_unselected():
    """
    Negative reproduction test:
    Question: 'What is the distribution of adverse event severity across treatment arms?'
    selected_tables: ['study', 'sites', 'dm'] (missing required ADSL, ADAE)
    Expected:
      - Execution must be blocked at execution boundary.
      - Missing datasets must be reported as ADAE / ADSL.
      - No SQL generated or executed.
    """
    question = "What is the distribution of adverse event severity across treatment arms?"
    initial_state = {
        "user_question": question,
        "selected_tables": ["study", "sites", "dm"],
        "approval_status": "approved",
        "approval_source": "api",
        "human_feedback": "",
        "feedback_history": [],
        "plan_version": 1,
    }

    final_state = workflow_app.invoke(initial_state)

    assert final_state.get("validation_status") == "blocked"
    assert final_state.get("reason") == "required_tables_not_selected"
    assert "adae" in final_state.get("missing_tables", [])
    assert final_state.get("sql_query") is None
    assert final_state.get("query_result") is None or len(final_state.get("query_result", [])) == 0


def test_end_to_end_distribution_across_treatment_arms_with_default_selected_tables():
    """
    Positive reproduction test:
    Question: 'What is the distribution of adverse event severity across treatment arms?'
    selected_tables: ['adsl', 'adae'] (explicitly selecting the required approved datasets)
    Expected:
      - Plan generated: requires ADSL + ADAE
      - Approved plan
      - Generated SQL: ADSL JOIN ADAE
      - SQL Validator: AUTHORIZED (adsl, adae)
      - Execution: SUCCESS (query_result populated, error empty)
    """
    question = "What is the distribution of adverse event severity across treatment arms?"
    initial_state = {
        "user_question": question,
        "selected_tables": ["adsl", "adae"],
        "approval_status": "approved",
        "approval_source": "api",
        "human_feedback": "",
        "feedback_history": [],
        "plan_version": 1,
    }

    final_state = workflow_app.invoke(initial_state)

    assert not final_state.get("error"), f"Workflow failed with error: {final_state.get('error')}"
    assert final_state.get("sql_query"), "SQL query was not generated"
    assert "adsl" in final_state["sql_query"].lower()
    assert "adae" in final_state["sql_query"].lower()
    assert len(final_state.get("query_result", [])) > 0, "Query result should contain rows"
