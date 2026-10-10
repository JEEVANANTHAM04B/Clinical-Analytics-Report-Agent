"""
tests/test_clinical_sql_validator.py
====================================
Tests for the Clinical SQL Validator migrated to the CDISC SDTM/ADaM schema.
Verifies valid SELECT queries, table checks, column checks (qualified and unqualified),
relationship conformance, alias resolution, security/syntax enforcement,
and end-to-end integration with the Clinical SQL Generator.
"""

import os
import sys
import pytest
from sqlalchemy import text

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))

from app.core.database import engine
from app.analytics.sql_validator import validate_sql
from app.analytics.sql_generator import generate_sql


# =============================================================================
# 1. VALID CLINICAL TRIAL QUERIES
# =============================================================================

VALID_CLINICAL_QUERIES = [
    ("dm_total_subjects", "SELECT COUNT(DISTINCT USUBJID) AS total_enrolled_patients FROM dm;"),
    ("dm_average_age", "SELECT ROUND(AVG(AGE), 2) AS average_age FROM dm;"),
    ("dm_sex_distribution", "SELECT SEX AS sex, COUNT(DISTINCT USUBJID) AS subject_count FROM dm GROUP BY SEX;"),
    ("ae_rate_unaliased", """
        SELECT adsl.TRT01A AS treatment_arm,
               COUNT(DISTINCT adsl.USUBJID) AS total_subjects,
               COUNT(DISTINCT adae.USUBJID) AS ae_subjects,
               ROUND(COUNT(DISTINCT adae.USUBJID) * 100.0 / COUNT(DISTINCT adsl.USUBJID), 2) AS ae_rate_pct
        FROM adsl
        LEFT JOIN adae ON adsl.USUBJID = adae.USUBJID
        GROUP BY adsl.TRT01A
        ORDER BY ae_rate_pct DESC;
    """),
    ("ae_rate_aliased", """
        SELECT s.TRT01A AS treatment_arm,
               COUNT(DISTINCT s.USUBJID) AS total_subjects,
               COUNT(DISTINCT e.USUBJID) AS ae_subjects,
               ROUND(COUNT(DISTINCT e.USUBJID) * 100.0 / COUNT(DISTINCT s.USUBJID), 2) AS ae_rate_pct
        FROM adsl s
        LEFT JOIN adae e ON s.USUBJID = e.USUBJID
        GROUP BY s.TRT01A
        ORDER BY ae_rate_pct DESC;
    """),
    ("ae_serious_count", "SELECT COUNT(*) AS serious_adverse_events FROM ae WHERE AESER = 'Y';"),
    ("adlb_change", """
        SELECT PARAMCD AS param_cd, TRT01A AS treatment_arm, AVISIT AS visit,
               ROUND(AVG(BASE), 2) AS mean_baseline,
               ROUND(AVG(AVAL), 2) AS mean_visit_value,
               ROUND(AVG(CHG), 2) AS mean_change,
               ROUND(AVG(PCHG), 2) AS mean_pct_change
        FROM adlb
        WHERE AVISIT = 'WEEK 8'
        GROUP BY PARAMCD, TRT01A, AVISIT
        ORDER BY PARAMCD, TRT01A;
    """),
    ("advs_change", """
        SELECT PARAMCD AS param_cd, TRT01A AS treatment_arm, AVISIT AS visit,
               ROUND(AVG(BASE), 2) AS mean_baseline,
               ROUND(AVG(AVAL), 2) AS mean_visit_val,
               ROUND(AVG(CHG), 2) AS mean_change,
               ROUND(AVG(PCHG), 2) AS mean_pct_change
        FROM advs
        WHERE AVISIT = 'WEEK 8'
        GROUP BY PARAMCD, TRT01A, AVISIT
        ORDER BY PARAMCD, TRT01A;
    """),
    ("adresp_response_rate", """
        SELECT TRT01A AS treatment_arm, AVISIT AS visit,
               COUNT(DISTINCT USUBJID) AS evaluable_subjects,
               COUNT(DISTINCT CASE WHEN RESPFL = 'Y' THEN USUBJID END) AS responders,
               ROUND(COUNT(DISTINCT CASE WHEN RESPFL = 'Y' THEN USUBJID END) * 100.0 / COUNT(DISTINCT USUBJID), 2) AS response_rate_pct
        FROM adresp
        WHERE AVISIT = 'WEEK 8'
        GROUP BY TRT01A, AVISIT
        ORDER BY response_rate_pct DESC;
    """),
    ("site_enrollment", """
        SELECT sites.SITEID AS site_id, sites.SITE_NAME AS site_name, COUNT(DISTINCT dm.USUBJID) AS enrolled_subjects
        FROM sites
        JOIN dm ON sites.SITEID = dm.SITEID
        GROUP BY sites.SITEID, sites.SITE_NAME
        ORDER BY enrolled_subjects DESC;
    """),
    ("informational_message", "SELECT 'Billing is not in CDISC schema' AS message;"),
]


@pytest.mark.parametrize("name,sql", VALID_CLINICAL_QUERIES)
def test_valid_clinical_queries_pass_validation(name, sql):
    """Verifies that all standard CDISC queries pass validation and execute cleanly on MySQL."""
    is_valid, reason = validate_sql(sql)
    assert is_valid, f"Validation failed for {name}: {reason}"

    # Also verify MySQL execution
    with engine.connect() as conn:
        res = conn.execute(text(sql)).fetchall()
        assert len(res) >= 0


# =============================================================================
# 2. INVALID TABLES REJECTION
# =============================================================================

@pytest.mark.parametrize("bad_sql,expected_msg", [
    ("SELECT * FROM billing_records;", "Unauthorized table(s): billing_records"),
    ("SELECT * FROM patients;", "Unauthorized table(s): patients"),
    ("SELECT * FROM encounters;", "Unauthorized table(s): encounters"),
    ("SELECT * FROM pharmacy_prescriptions;", "Unauthorized table(s): pharmacy_prescriptions"),
])
def test_unauthorized_tables_rejected(bad_sql, expected_msg):
    """Verifies unknown or non-clinical tables are rejected."""
    is_valid, reason = validate_sql(bad_sql)
    assert not is_valid
    assert expected_msg in reason


# =============================================================================
# 3. INVALID COLUMNS REJECTION
# =============================================================================

def test_unqualified_nonexistent_column_rejected():
    """Verifies unqualified non-existent columns are caught and rejected."""
    sql = "SELECT nonexistent_column FROM dm;"
    is_valid, reason = validate_sql(sql)
    assert not is_valid
    assert "Unauthorized column: nonexistent_column" in reason


def test_qualified_nonexistent_column_rejected():
    """Verifies qualified table.column non-existent columns are rejected."""
    sql = "SELECT dm.nonexistent_column FROM dm;"
    is_valid, reason = validate_sql(sql)
    assert not is_valid
    assert "Unauthorized column: dm.nonexistent_column" in reason


def test_aliased_nonexistent_column_rejected():
    """Verifies table alias d.nonexistent_column is resolved and rejected."""
    sql = "SELECT d.nonexistent_column FROM dm d;"
    is_valid, reason = validate_sql(sql)
    assert not is_valid
    assert "Unauthorized column: d.nonexistent_column" in reason


# =============================================================================
# 4. INVALID RELATIONSHIPS REJECTION
# =============================================================================

def test_unapproved_relationship_rejected():
    """Verifies joins across columns not forming an approved relationship are rejected."""
    # dm and ae both have STUDYID, but the approved join is dm.USUBJID = ae.USUBJID
    sql = "SELECT * FROM dm JOIN ae ON dm.STUDYID = ae.STUDYID;"
    is_valid, reason = validate_sql(sql)
    assert not is_valid
    assert "Unauthorized relationship: dm.STUDYID = ae.STUDYID" in reason


def test_adsl_adae_approved_usubjid_relationship_accepted():
    """Verifies the verified relationship adsl.USUBJID = adae.USUBJID is approved and passes."""
    sql = (
        "SELECT adsl.TRT01A, COUNT(DISTINCT adsl.USUBJID) AS total_subjs, "
        "COUNT(DISTINCT adae.USUBJID) AS ae_subjs "
        "FROM adsl LEFT JOIN adae ON adsl.USUBJID = adae.USUBJID "
        "GROUP BY adsl.TRT01A;"
    )
    is_valid, reason = validate_sql(sql)
    assert is_valid, f"Expected adsl.USUBJID = adae.USUBJID to pass, got: {reason}"
    assert "safe" in reason.lower()


def test_adsl_adae_unapproved_studyid_relationship_rejected():
    """Verifies unapproved relationship adsl.STUDYID = adae.STUDYID is blocked as unauthorized."""
    sql = (
        "SELECT adsl.TRT01A, COUNT(DISTINCT adae.USUBJID) "
        "FROM adsl JOIN adae ON adsl.STUDYID = adae.STUDYID "
        "GROUP BY adsl.TRT01A;"
    )
    is_valid, reason = validate_sql(sql)
    assert not is_valid
    assert "Unauthorized relationship: adsl.STUDYID = adae.STUDYID" in reason


def test_disconnected_tables_rejected():
    """Verifies joining tables that cannot connect is rejected."""
    sql = "SELECT * FROM dm JOIN lb ON dm.SITEID = lb.SITEID;"
    is_valid, reason = validate_sql(sql)
    assert not is_valid


# =============================================================================
# 5. SECURITY & SYNTAX DEFENSES
# =============================================================================

@pytest.mark.parametrize("dangerous_sql", [
    "DROP TABLE dm;",
    "DELETE FROM dm;",
    "UPDATE dm SET AGE = 50;",
    "INSERT INTO dm (USUBJID) VALUES ('SUBJ01');",
    "ALTER TABLE dm ADD COLUMN test INT;",
    "TRUNCATE TABLE dm;",
    "GRANT ALL PRIVILEGES ON *.* TO 'user'@'%';",
    "SELECT * FROM dm; DROP TABLE dm;",
    "SELECT ;",
    "SELECT * FROM dm WHERE ;",
])
def test_security_and_syntax_violations_blocked(dangerous_sql):
    """Verifies DDL, DML, multiple statements, and malformed queries are blocked."""
    is_valid, reason = validate_sql(dangerous_sql)
    assert not is_valid


# =============================================================================
# 6. PLAN CONSISTENCY VALIDATION
# =============================================================================

def test_clinical_plan_single_table_violation():
    """Verifies single-table plan constraint rejects queries with JOINs."""
    plan = "#### 2. Join Conditions\n* None (single-table query on dm)"
    sql = "SELECT dm.USUBJID FROM dm JOIN ae ON dm.USUBJID = ae.USUBJID;"
    is_valid, reason = validate_sql(sql, analysis_plan=plan)
    assert not is_valid
    assert "single-table" in reason


def test_clinical_plan_serious_ae_filter():
    """Verifies serious AE plan constraint rejects queries without AESER = 'Y'."""
    plan = "#### 3. Filtering\n* Filter for serious adverse events (AESER = 'Y')"
    bad_sql = "SELECT COUNT(*) FROM ae;"
    is_valid, reason = validate_sql(bad_sql, analysis_plan=plan)
    assert not is_valid
    assert "AESER" in reason

    good_sql = "SELECT COUNT(*) FROM ae WHERE AESER = 'Y';"
    is_valid, reason = validate_sql(good_sql, analysis_plan=plan)
    assert is_valid


# =============================================================================
# 7. SQL GENERATOR → SQL VALIDATOR INTEGRATION
# =============================================================================

INTEGRATION_QUESTIONS = [
    "How many patients are enrolled?",
    "What is the average age of patients?",
    "What is the breakdown of subjects by sex?",
    "Which treatment arm has the highest adverse event rate?",
    "How many serious adverse events occurred?",
    "What is the laboratory change from baseline?",
    "What is the vital sign change from baseline?",
    "What is the efficacy response rate by treatment?",
    "Which site has the highest enrollment?",
]


@pytest.mark.parametrize("question", INTEGRATION_QUESTIONS)
def test_sql_generator_output_passes_validator(question):
    """Verifies SQL generated by the SQL Generator passes the SQL Validator and executes."""
    generated_sql = generate_sql(question, "")
    assert generated_sql is not None

    is_valid, reason = validate_sql(generated_sql)
    assert is_valid, f"Generated SQL for '{question}' failed validation: {reason}\nSQL:\n{generated_sql}"

    with engine.connect() as conn:
        result = conn.execute(text(generated_sql)).fetchall()
        assert len(result) >= 0
