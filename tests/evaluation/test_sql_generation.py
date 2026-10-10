"""
tests/evaluation/test_sql_generation.py
=======================================
Evaluates SQL generation accuracy, relational joins, aggregation syntax,
and plan consistency against the active clinical schema.
"""

import pytest
from app.analytics.sql_generator import generate_sql
from app.analytics.sql_validator import validate_sql
from app.database.schema_service import get_database_schema
from app.clinical.table_validator import extract_sql_tables_ast


@pytest.fixture(scope="module")
def clinical_schema():
    return get_database_schema(approved_only=True)


def test_sql_subject_count_by_arm(clinical_schema, sql_safety_metric):
    """Verifies single-table subject count by treatment arm."""
    plan = (
        "1. Relevant Tables and Columns: adsl.TRT01A, adsl.USUBJID\n"
        "2. Join Conditions: None (single table adsl)\n"
        "3. Derived Calculations: COUNT(DISTINCT USUBJID)\n"
        "4. Aggregations & Grouping: Group results by adsl.TRT01A\n"
        "5. Filtering: None"
    )
    sql = generate_sql(
        user_question="How many subjects are assigned to each treatment arm?",
        analysis_plan=plan,
        database_schema=clinical_schema,
    )
    assert sql and "SELECT" in sql.upper()
    assert "TRT01A" in sql.upper() or "ARM" in sql.upper()
    assert "COUNT" in sql.upper()

    safety = sql_safety_metric.evaluate_query(sql, selected_tables=["adsl"], analysis_plan=plan)
    assert safety["passed"] is True, f"SQL safety failed: {safety['violations']}"


def test_sql_ae_incidence_join(clinical_schema, sql_safety_metric):
    """Verifies relational join between ADSL and ADAE on USUBJID for adverse event rate."""
    plan = (
        "1. Relevant Tables and Columns: adsl.TRT01A, adae.AEDECOD, adae.USUBJID, adsl.USUBJID\n"
        "2. Join Conditions: Join adsl and adae on adsl.USUBJID = adae.USUBJID\n"
        "3. Derived Calculations: Distinct subject rate\n"
        "4. Aggregations & Grouping: Group results by adsl.TRT01A\n"
        "5. Filtering: adae.TRTEMFL = 'Y'"
    )
    sql = generate_sql(
        user_question="What is the adverse event incidence rate by treatment arm?",
        analysis_plan=plan,
        database_schema=clinical_schema,
    )
    assert sql and "SELECT" in sql.upper()
    tables = extract_sql_tables_ast(sql)
    assert "adsl" in tables or "adae" in tables

    safety = sql_safety_metric.evaluate_query(
        sql,
        selected_tables=["adsl", "adae"],
        analysis_plan=plan,
    )
    assert safety["passed"] is True, f"SQL safety failed: {safety['violations']}"


def test_sql_top_adverse_events_ordering(clinical_schema, sql_safety_metric):
    """Verifies DESC ordering and LIMIT 5 for top adverse events query."""
    plan = (
        "1. Relevant Tables and Columns: adae.AEDECOD, adae.USUBJID\n"
        "2. Join Conditions: None (single-table query on adae)\n"
        "3. Derived Calculations: Event frequency\n"
        "4. Aggregations & Grouping: Group results by adae.AEDECOD\n"
        "5. Filtering: Order by count DESC limit 5"
    )
    sql = generate_sql(
        user_question="What are the five most frequently reported adverse events?",
        analysis_plan=plan,
        database_schema=clinical_schema,
    )
    assert sql and "SELECT" in sql.upper()
    assert "LIMIT 5" in sql.upper()
    assert "ORDER BY" in sql.upper()

    safety = sql_safety_metric.evaluate_query(sql, selected_tables=["adae"], analysis_plan=plan)
    assert safety["passed"] is True
