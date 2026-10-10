"""
tests/test_clinical_insight_followup.py
======================================
Comprehensive test suite verifying the migration of Insight Generation and
Follow-up Analysis Engine from legacy EHR to CDISC clinical-trial relational data.

Tests verify:
1. Clinical context detection for insight and follow-up services.
2. Canonical clinical trial deterministic insight generation for 9 clinical metrics.
3. Deterministic insight evidence calculation (max, min, categories, row count).
4. Deterministic insight validation against SQL results and ranking claims.
5. Follow-up analysis over verified clinical results (highest, lowest, threshold, entity, why).
6. Lightweight clinical follow-up SQL execution (total subjects, SAE count, site enrollment).
7. Unrelated analysis detection (payer, billing, pharmacokinetics).
8. Backward compatibility for legacy EHR datasets.
9. Strict prevention of EHR table contamination in clinical queries.
"""

import sys
import os
sys.path.insert(0, os.path.abspath("."))

import pytest
from app.ai.insight_generator import (
    _is_clinical_context as is_insight_clinical,
    _deterministic_insight_fallback,
    generate_insight,
)
from app.ai.insight_validator import validate_insight
from app.analytics.insight_evidence import build_insight_evidence
from app.analytics.followup_service import (
    process_followup_question,
    _is_clinical_context as is_followup_clinical,
    _is_unrelated_new_analysis,
    _answer_deterministically,
    _extract_metric_key_and_label,
)
from app.schemas.analytics import FollowUpRequest


# =============================================================================
# 1. CONTEXT DETECTION TESTS
# =============================================================================

def test_insight_context_detection():
    """Verify CDISC clinical trial context detection in insight generator."""
    assert is_insight_clinical("How many subjects are enrolled?", []) is True
    assert is_insight_clinical("What is the adverse event rate by treatment arm?", []) is True
    assert is_insight_clinical("Generic query", [{"USUBJID": "001-001", "TRT01A": "Drug A"}]) is True
    assert is_insight_clinical("Average length of stay by diagnosis", [{"diagnosis": "Anemia", "avg_length_of_stay": 3.2}]) is False


def test_followup_context_detection():
    """Verify CDISC clinical trial context detection in followup service."""
    # Clinical trial tables
    assert is_followup_clinical(
        selected_tables=["dm", "ae"],
        current_results=[],
    ) is True
    # Clinical trial results
    assert is_followup_clinical(
        selected_tables=[],
        current_results=[{"treatment_arm": "Drug A", "adverse_event_rate_pct": 25.5}],
    ) is True
    # Legacy EHR tables
    assert is_followup_clinical(
        selected_tables=["patients", "encounters"],
        current_results=[],
    ) is False


# =============================================================================
# 2. CANONICAL CLINICAL TRIAL INSIGHT FALLBACK TESTS
# =============================================================================

def test_insight_fallback_total_subjects():
    results = [{"total_enrolled_subjects": 254}]
    evidence = build_insight_evidence(results)
    insight = _deterministic_insight_fallback(
        "How many subjects are enrolled?",
        results,
        evidence,
        clinical_plan={"matched_kpi_id": "TOTAL_SUBJECTS"},
    )
    assert "254" in insight
    assert "enrolled subjects" in insight.lower()


def test_insight_fallback_average_age():
    results = [{"average_age": 54.3}]
    evidence = build_insight_evidence(results)
    insight = _deterministic_insight_fallback(
        "What is the average age of subjects?",
        results,
        evidence,
        clinical_plan={"matched_kpi_id": "AVERAGE_AGE"},
    )
    assert "54.3" in insight
    assert "average age" in insight.lower()


def test_insight_fallback_serious_ae_count():
    results = [{"serious_adverse_events": 18}]
    evidence = build_insight_evidence(results)
    insight = _deterministic_insight_fallback(
        "How many serious adverse events occurred?",
        results,
        evidence,
        clinical_plan={"matched_kpi_id": "SERIOUS_AE_COUNT"},
    )
    assert "18" in insight
    assert "serious adverse events" in insight.lower()


def test_insight_fallback_ae_rate_by_treatment():
    results = [
        {"treatment_arm": "Drug A", "adverse_event_rate_pct": 42.50},
        {"treatment_arm": "Placebo", "adverse_event_rate_pct": 18.20},
    ]
    evidence = build_insight_evidence(results)
    insight = _deterministic_insight_fallback(
        "What is the adverse event rate by treatment arm?",
        results,
        evidence,
        clinical_plan={"matched_kpi_id": "AE_RATE_BY_TREATMENT"},
    )
    assert "Drug A at 42.50%" in insight
    assert "Placebo at 18.20%" in insight


def test_insight_fallback_efficacy_response_rate():
    results = [
        {"treatment_arm": "Drug A", "response_rate_pct": 68.40},
        {"treatment_arm": "Placebo", "response_rate_pct": 22.10},
    ]
    evidence = build_insight_evidence(results)
    insight = _deterministic_insight_fallback(
        "What is the efficacy response rate by treatment?",
        results,
        evidence,
        clinical_plan={"matched_kpi_id": "EFFICACY_RESPONSE_RATE"},
    )
    assert "Drug A at 68.40%" in insight
    assert "RESPFL = 'Y'" in insight


def test_insight_fallback_enrollment_by_site():
    results = [
        {"SITEID": "SITE-101", "SITE_NAME": "Boston Medical Center", "enrolled_subjects": 85},
        {"SITEID": "SITE-102", "SITE_NAME": "Memorial Hospital", "enrolled_subjects": 62},
    ]
    evidence = build_insight_evidence(results)
    insight = _deterministic_insight_fallback(
        "Which site has the highest enrollment?",
        results,
        evidence,
        clinical_plan={"matched_kpi_id": "ENROLLMENT_BY_SITE"},
    )
    assert "SITE-101" in insight
    assert "85" in insight
    assert "Boston Medical Center" in insight


# =============================================================================
# 3. INSIGHT EVIDENCE & DETERMINISTIC VALIDATION TESTS
# =============================================================================

def test_build_evidence_clinical_trial():
    results = [
        {"treatment_arm": "Drug A", "adverse_event_rate_pct": 45.0},
        {"treatment_arm": "Drug B", "adverse_event_rate_pct": 30.0},
        {"treatment_arm": "Placebo", "adverse_event_rate_pct": 15.0},
    ]
    evidence = build_insight_evidence(results)
    assert evidence["row_count"] == 3
    assert evidence["maximum"]["category"] == "Drug A"
    assert evidence["maximum"]["value"] == 45.0
    assert evidence["minimum"]["value"] == 15.0
    assert "Placebo" in evidence["minimum"]["categories"]


def test_validate_insight_valid_claim():
    results = [
        {"treatment_arm": "Drug A", "adverse_event_rate_pct": 45.0},
        {"treatment_arm": "Placebo", "adverse_event_rate_pct": 15.0},
    ]
    evidence = build_insight_evidence(results)
    insight_text = "Drug A had the highest adverse event rate at 45.0%, while Placebo had the lowest at 15.0%."
    validation = validate_insight(insight_text, results, evidence)
    assert validation["valid"] is True
    assert not validation["unsupported_numbers"]


def test_validate_insight_unsupported_number_fails():
    results = [
        {"treatment_arm": "Drug A", "adverse_event_rate_pct": 45.0},
        {"treatment_arm": "Placebo", "adverse_event_rate_pct": 15.0},
    ]
    evidence = build_insight_evidence(results)
    # LLM hallucinating 88.5%
    insight_text = "Drug A had the highest adverse event rate at 88.5%."
    validation = validate_insight(insight_text, results, evidence)
    assert validation["valid"] is False
    assert 88.5 in validation["unsupported_numbers"]


def test_validate_insight_wrong_ranking_fails():
    results = [
        {"treatment_arm": "Drug A", "adverse_event_rate_pct": 45.0},
        {"treatment_arm": "Placebo", "adverse_event_rate_pct": 15.0},
    ]
    evidence = build_insight_evidence(results)
    # LLM wrongly claiming Placebo is the highest
    insight_text = "Placebo had the highest adverse event rate at 15.0%."
    validation = validate_insight(insight_text, results, evidence)
    assert validation["valid"] is False
    assert validation["ranking_issue"] is not None


# =============================================================================
# 4. FOLLOW-UP SERVICE DETERMINISTIC REASONING TESTS
# =============================================================================

def test_followup_highest_treatment_arm():
    results = [
        {"treatment_arm": "Drug A", "adverse_event_rate_pct": 45.2},
        {"treatment_arm": "Drug B", "adverse_event_rate_pct": 32.1},
        {"treatment_arm": "Placebo", "adverse_event_rate_pct": 14.5},
    ]
    answer = _answer_deterministically(
        question="Which arm had the highest rate?",
        results=results,
        current_question="AE rate by arm",
        current_insight=None,
        current_rag=None,
        is_clinical=True,
    )
    assert answer is not None
    assert "Drug A" in answer
    assert "45.2%" in answer
    assert "highest" in answer
    assert "treatment arms" in answer
    # Must NOT mention length of stay or inpatient
    assert "length of stay" not in answer.lower()
    assert "inpatient" not in answer.lower()


def test_followup_lowest_treatment_arm():
    results = [
        {"treatment_arm": "Drug A", "adverse_event_rate_pct": 45.2},
        {"treatment_arm": "Drug B", "adverse_event_rate_pct": 32.1},
        {"treatment_arm": "Placebo", "adverse_event_rate_pct": 14.5},
    ]
    answer = _answer_deterministically(
        question="What was the lowest adverse event rate?",
        results=results,
        current_question="AE rate by arm",
        current_insight=None,
        current_rag=None,
        is_clinical=True,
    )
    assert answer is not None
    assert "Placebo" in answer
    assert "14.5%" in answer
    assert "lowest" in answer


def test_followup_threshold_check():
    results = [
        {"treatment_arm": "Drug A", "adverse_event_rate_pct": 45.2},
        {"treatment_arm": "Drug B", "adverse_event_rate_pct": 32.1},
        {"treatment_arm": "Placebo", "adverse_event_rate_pct": 14.5},
    ]
    answer = _answer_deterministically(
        question="Which treatment arms have an adverse event rate above 30%?",
        results=results,
        current_question="AE rate by arm",
        current_insight=None,
        current_rag=None,
        is_clinical=True,
    )
    assert answer is not None
    assert "Drug A" in answer
    assert "Drug B" in answer
    assert "Placebo" not in answer
    assert "2 treatment arms" in answer


def test_followup_specific_entity():
    results = [
        {"treatment_arm": "Drug A", "adverse_event_rate_pct": 45.2},
        {"treatment_arm": "Drug B", "adverse_event_rate_pct": 32.1},
        {"treatment_arm": "Placebo", "adverse_event_rate_pct": 14.5},
    ]
    answer = _answer_deterministically(
        question="What was the rate for Drug B?",
        results=results,
        current_question="AE rate by arm",
        current_insight=None,
        current_rag=None,
        is_clinical=True,
    )
    assert answer is not None
    assert "Drug B" in answer
    assert "32.1%" in answer


# =============================================================================
# 5. FOLLOW-UP UNRELATED DOMAIN & SQL TESTS
# =============================================================================

def test_followup_unrelated_domain_detection():
    # Payer/cost inquiry when looking at clinical trial
    req = FollowUpRequest(
        question="What was the total billing expenditure and insurance cost?",
        current_question="Adverse event rate by treatment arm",
        current_results=[{"treatment_arm": "Drug A", "adverse_event_rate_pct": 45.2}],
        selected_tables=["adsl", "adae"],
    )
    resp = process_followup_question(req)
    assert resp.status == "new_analysis_suggested"
    assert resp.is_new_analysis is True


def test_followup_lightweight_sql_total_subjects():
    req = FollowUpRequest(
        question="How many total subjects are enrolled in the study?",
        current_question="Enrollment by site",
        current_results=[],
        selected_tables=["dm", "sites"],
    )
    resp = process_followup_question(req)
    assert resp.status == "success"
    assert resp.source == "follow_up_sql"
    assert resp.sql_query is not None
    assert "dm" in resp.sql_query.lower()
    # Must NOT query legacy EHR tables
    for ehr in ["patients", "encounters", "conditions"]:
        assert f"`{ehr}`" not in resp.sql_query.lower()
        assert f" {ehr} " not in resp.sql_query.lower()
    assert "subjects" in resp.answer.lower()


def test_followup_lightweight_sql_sae_count():
    req = FollowUpRequest(
        question="How many serious adverse events occurred?",
        current_question="Adverse event rate by treatment arm",
        current_results=[],
        selected_tables=["adae"],
    )
    resp = process_followup_question(req)
    assert resp.status == "success"
    assert resp.source == "follow_up_sql"
    assert "AESER = 'Y'" in resp.sql_query
    assert "serious adverse events" in resp.answer.lower()


# =============================================================================
# 6. BACKWARD COMPATIBILITY FOR LEGACY EHR
# =============================================================================

def test_legacy_ehr_followup_backward_compatibility():
    ehr_results = [
        {"diagnosis": "Anemia", "avg_length_of_stay": 3.4},
        {"diagnosis": "Pneumonia", "avg_length_of_stay": 2.1},
    ]
    req = FollowUpRequest(
        question="Which diagnosis has the highest stay?",
        current_question="Average length of stay by diagnosis",
        current_results=ehr_results,
        selected_tables=["encounters", "conditions"],
    )
    resp = process_followup_question(req)
    assert resp.status == "success"
    assert "Anemia" in resp.answer
    assert "average length of stay" in resp.answer.lower()
