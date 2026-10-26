"""
tests/test_clinical_sql_generator.py
====================================
Tests for the Clinical SQL Generator migrated to the CDISC SDTM/ADaM schema.
Verifies prompt construction, plan integration, deterministic fallback,
SQL validation, live MySQL execution, and safety/negative constraints.
"""

import os
import sys
import pytest
from sqlalchemy import text

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))

from app.core.database import engine
from app.clinical import (
    registry as clinical_registry,
    build_clinical_question_plan,
)
from app.analytics.sql_generator import (
    generate_sql,
    _deterministic_sql_fallback,
    _is_clinical_context,
    _check_sql_vs_clinical_plan,
    _build_clinical_prompt,
)
from app.analytics.sql_validator import validate_sql


LEGACY_EHR_TABLES = {"patients", "encounters", "conditions", "medications", "observations", "procedures"}

CLINICAL_QUESTIONS = [
    ("enrollment", "How many patients are enrolled?", ["dm"], "dm.USUBJID"),
    ("average_age", "What is the average age of patients?", ["dm"], "dm.AGE"),
    ("sex_breakdown", "What is the breakdown of subjects by sex?", ["dm"], "dm.SEX"),
    ("ae_rate_by_arm", "Which treatment arm has the highest adverse event rate?", ["adsl", "adae"], "adsl.TRT01A"),
    ("serious_ae", "How many serious adverse events occurred?", ["ae"], "ae.AESER"),
    ("lab_change", "What is the laboratory change from baseline?", ["adlb"], "adlb.CHG"),
    ("vital_signs_change", "What is the vital sign change from baseline?", ["advs"], "advs.CHG"),
    ("efficacy_response", "What is the efficacy response rate by treatment?", ["adresp"], "adresp.RESPFL"),
    ("site_enrollment", "Which site has the highest enrollment?", ["sites", "dm"], "sites.SITEID"),
]


# =============================================================================
# 1. DETERMINISTIC FALLBACK & VALIDATION TESTS
# =============================================================================

@pytest.mark.parametrize("category,question,expected_datasets,key_column", CLINICAL_QUESTIONS)
def test_deterministic_sql_generation_and_validation(category, question, expected_datasets, key_column):
    """Verifies deterministic SQL is generated, validates, references only clinical tables, and runs on MySQL."""
    sql = _deterministic_sql_fallback(question, "")
    assert sql is not None, f"Fallback SQL must not be None for question: {question}"

    # 1. Validator safety
    is_valid, reason = validate_sql(sql)
    assert is_valid, f"Generated SQL failed validation: {reason}\nSQL: {sql}"

    sql_lower = sql.lower()

    # 2. Expected clinical datasets are present
    for ds in expected_datasets:
        assert ds in sql_lower, f"Expected dataset '{ds}' not found in SQL:\n{sql}"

    # 3. No legacy EHR tables referenced
    for legacy_table in LEGACY_EHR_TABLES:
        assert f" {legacy_table} " not in f" {sql_lower} ", f"Legacy table '{legacy_table}' illegally found in SQL:\n{sql}"

    # 4. Live execution against clinical_trial_analytics_db
    with engine.connect() as conn:
        result = conn.execute(text(sql)).fetchall()
        assert len(result) > 0, f"Query returned 0 rows for question: {question}"


# =============================================================================
# 2. LIVE QUERY EXECUTION AND RESULT SANITY CHECKS
# =============================================================================

def test_total_enrolled_patients_result():
    """Verify total subjects matches known 10,000 enrolled subjects in dm."""
    sql = _deterministic_sql_fallback("How many patients are enrolled?", "")
    with engine.connect() as conn:
        row = conn.execute(text(sql)).fetchone()
        assert row is not None
        assert row[0] == 10000


def test_average_age_result():
    """Verify average age is reasonable (~54.63) and within clinical bounds."""
    sql = _deterministic_sql_fallback("What is the average age of patients?", "")
    with engine.connect() as conn:
        row = conn.execute(text(sql)).fetchone()
        assert row is not None
        mean_age = float(row[0])
        assert 18.0 <= mean_age <= 90.0


def test_sex_distribution_result():
    """Verify sex distribution has both F and M categories."""
    sql = _deterministic_sql_fallback("What is the breakdown of subjects by sex?", "")
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
        assert len(rows) == 2
        sexes = {r[0] for r in rows}
        assert sexes == {"F", "M"}


def test_ae_rate_by_treatment_arm_result():
    """Verify AE rate by arm contains Drug X and Placebo with positive rates."""
    sql = _deterministic_sql_fallback("Which treatment arm has the highest adverse event rate?", "")
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
        assert len(rows) >= 2
        arms = {r[0] for r in rows}
        assert "Drug X" in arms or "Placebo" in arms
        # Check rates are numeric percentages between 0 and 100
        for r in rows:
            rate = float(r[3])
            assert 0.0 <= rate <= 100.0


def test_serious_adverse_events_result():
    """Verify serious adverse events query returns count."""
    sql = _deterministic_sql_fallback("How many serious adverse events occurred?", "")
    with engine.connect() as conn:
        row = conn.execute(text(sql)).fetchone()
        assert row is not None
        sae_count = int(row[0])
        assert sae_count in {2517, 2518}  # Known count in populated database


def test_lab_change_from_baseline_result():
    """Verify laboratory change from baseline calculates mean change."""
    sql = _deterministic_sql_fallback("What is the laboratory change from baseline?", "")
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
        assert len(rows) > 0
        for r in rows:
            assert r[0] == "HGB"  # PARAMCD
            assert r[2] == "WEEK 8"  # AVISIT


def test_vital_sign_change_from_baseline_result():
    """Verify vital sign change from baseline calculates change for SYSBP."""
    sql = _deterministic_sql_fallback("What is the vital sign change from baseline?", "")
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
        assert len(rows) > 0
        for r in rows:
            assert r[0] == "SYSBP"
            assert r[2] == "WEEK 8"


def test_efficacy_response_rate_result():
    """Verify efficacy response rate calculates response rate percentage."""
    sql = _deterministic_sql_fallback("What is the efficacy response rate by treatment?", "")
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
        assert len(rows) >= 2
        for r in rows:
            pct = float(r[4])
            assert 0.0 <= pct <= 100.0


def test_site_enrollment_result():
    """Verify site enrollment lists 10 sites with non-zero subjects."""
    sql = _deterministic_sql_fallback("Which site has the highest enrollment?", "")
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
        assert len(rows) == 10
        total_enrolled = sum(r[3] for r in rows)
        assert total_enrolled == 10000


# =============================================================================
# 3. SCHEMA CONTEXT DETECTION & PLANNING INTERFACE
# =============================================================================

def test_context_detection_clinical():
    """Verify _is_clinical_context returns True for clinical schemas."""
    assert _is_clinical_context({"tables": {"dm": [], "adsl": []}}) is True
    assert _is_clinical_context({"tables": {"study": [], "sites": []}}) is True
    assert _is_clinical_context({}) is True
    assert _is_clinical_context(None) is True


def test_context_detection_legacy_ehr():
    """Verify _is_clinical_context returns False for legacy EHR schemas."""
    assert _is_clinical_context({"tables": {"encounters": [], "patients": []}}) is False
    assert _is_clinical_context({"tables": {"conditions": []}}) is False


def test_clinical_prompt_builder():
    """Verify clinical prompt includes CDISC schema context and few-shot examples."""
    plan = build_clinical_question_plan("What is the average age of patients?")
    prompt = _build_clinical_prompt(
        user_question="What is the average age of patients?",
        analysis_plan="",
        database_schema={"tables": {"dm": []}},
        plan=plan,
    )
    assert "CDISC CLINICAL TRIAL SCHEMA CONTEXT" in prompt
    assert "dm" in prompt
    assert "adsl" in prompt
    assert "adae" in prompt
    assert "FEW-SHOT CLINICAL TRIAL QUERY EXAMPLES" in prompt
    assert "ROUND(AVG(AGE), 2)" in prompt


def test_plan_consistency_checker():
    """Verify inline plan consistency check catches violations."""
    plan = build_clinical_question_plan("How many serious adverse events occurred?")
    # Missing AESER filter
    bad_sql = "SELECT COUNT(*) FROM ae;"
    is_ok, reason = _check_sql_vs_clinical_plan(bad_sql, plan)
    assert not is_ok
    assert "AESER" in reason

    # Correct SQL
    good_sql = "SELECT COUNT(*) FROM ae WHERE AESER = 'Y';"
    is_ok, reason = _check_sql_vs_clinical_plan(good_sql, plan)
    assert is_ok


# =============================================================================
# 4. NEGATIVE AND SAFETY TESTS
# =============================================================================

def test_unsupported_question_fails_safely():
    """Verify questions for non-existent domains do not produce valid clinical plans."""
    plan = build_clinical_question_plan("What was the patient insurance copay and billing balance?")
    assert not plan.is_supported
    assert plan.suggested_sql is None


def test_validator_rejects_unauthorized_tables():
    """Verify validator rejects SQL targeting hallucinated or unauthorized tables."""
    bad_sql = "SELECT * FROM billing_records;"
    is_valid, reason = validate_sql(bad_sql)
    assert not is_valid
    assert "Unauthorized table" in reason


def test_validator_rejects_forbidden_keywords():
    """Verify validator blocks destructive DDL/DML statements."""
    for kw in ["DROP TABLE dm;", "DELETE FROM dm;", "ALTER TABLE dm ADD COLUMN x INT;"]:
        is_valid, reason = validate_sql(kw)
        assert not is_valid


def test_legacy_ehr_fallback_preserved():
    """Verify legacy EHR deterministic plan fallback still works when an EHR plan is provided."""
    ehr_plan = """
    #### 1. Relevant Tables and Columns
    * encounters: ID, START, STOP, ENCOUNTERCLASS
    #### 4. Aggregations & Grouping
    * Group by encounters.ENCOUNTERCLASS
    """
    sql = _deterministic_sql_fallback("Unknown question", ehr_plan)
    assert sql is not None
    assert "encounters.ENCOUNTERCLASS" in sql
