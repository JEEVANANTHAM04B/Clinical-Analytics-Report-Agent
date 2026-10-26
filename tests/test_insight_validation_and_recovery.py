"""
tests/test_insight_validation_and_recovery.py
=============================================
Targeted tests for:
1. An insight containing supported numeric values.
2. An unsupported numeric claim.
3. A highest/lowest claim with valid evidence.
4. A ranking claim with missing or mismatched evidence.
5. Insight regeneration after validation failure.
6. Exhaustion of the allowed retry count.
"""

import pytest
from app.ai.insight_validator import validate_insight, _number_exists_in_results
from app.analytics.insight_evidence import build_insight_evidence
from app.workflow.graph import validate_insight_node, regenerate_insight_node, insight_validation_router


# Synthetic clinical test fixture
SYNTHETIC_QUERY_RESULTS = [
    {
        "PARAMCD": "HGB",
        "TRT01A": "Drug X",
        "AVISIT": "WEEK 8",
        "mean_baseline": 13.54,
        "mean_visit_value": 12.74,
        "mean_change": -0.8,
        "mean_pct_change": -5.96,
    },
    {
        "PARAMCD": "HGB",
        "TRT01A": "Placebo",
        "AVISIT": "WEEK 8",
        "mean_baseline": 13.50,
        "mean_visit_value": 13.40,
        "mean_change": -0.1,
        "mean_pct_change": -0.75,
    },
]


def test_1_insight_containing_supported_numeric_values():
    """1. An insight containing supported numeric values passes validation."""
    evidence = build_insight_evidence(SYNTHETIC_QUERY_RESULTS)
    insight = (
        "At Week 8, Drug X subjects had a mean baseline hemoglobin of 13.54 and a mean "
        "visit value of 12.74, representing a mean change of -0.8 (-5.96%). Placebo subjects "
        "had a mean baseline of 13.50 and a visit value of 13.40, with a change of -0.1 (-0.75%)."
    )
    result = validate_insight(insight, SYNTHETIC_QUERY_RESULTS, evidence)
    assert result["valid"] is True
    assert result["unsupported_numbers"] == []
    assert result["ranking_issue"] is None
    assert "passed" in result["message"]


def test_2_unsupported_numeric_claim():
    """2. An unsupported numeric claim is caught and fails validation."""
    evidence = build_insight_evidence(SYNTHETIC_QUERY_RESULTS)
    insight = (
        "At Week 8, Drug X subjects showed a massive mean change of -45.5 g/dL, "
        "compared to a change of -0.1 in the Placebo arm."
    )
    result = validate_insight(insight, SYNTHETIC_QUERY_RESULTS, evidence)
    assert result["valid"] is False
    assert -45.5 in result["unsupported_numbers"]
    assert "unsupported numbers" in result["message"]


def test_3_highest_lowest_claim_with_valid_evidence():
    """3. A highest/lowest claim matching deterministic evidence passes validation."""
    evidence = build_insight_evidence(SYNTHETIC_QUERY_RESULTS)
    assert evidence["maximum"]["category"] == "Placebo"
    assert evidence["maximum"]["value"] == -0.1
    assert "Drug X" in evidence["minimum"]["categories"]
    assert evidence["minimum"]["value"] == -0.8

    insight = (
        "At Week 8, the maximum mean change was observed in Placebo with -0.1, "
        "while the lowest mean change was observed in Drug X with -0.8."
    )
    result = validate_insight(insight, SYNTHETIC_QUERY_RESULTS, evidence)
    assert result["valid"] is True
    assert result["ranking_issue"] is None


def test_4_ranking_claim_with_missing_or_mismatched_evidence():
    """4. A ranking claim with missing or mismatched evidence is caught."""
    evidence = build_insight_evidence(SYNTHETIC_QUERY_RESULTS)

    # Claiming an unauthorized category (e.g. Drug Y) has the highest value
    mismatched_insight = (
        "At Week 8, the highest change was observed in Drug Y with -0.1."
    )
    result = validate_insight(mismatched_insight, SYNTHETIC_QUERY_RESULTS, evidence)
    assert result["valid"] is False
    assert result["ranking_issue"] is not None
    assert "Highest-value claim does not match" in result["ranking_issue"]

    # Claiming highest without deterministic evidence available
    no_evidence_result = validate_insight(
        "The highest change was observed in Placebo with -0.1.",
        SYNTHETIC_QUERY_RESULTS,
        insight_evidence={},
    )
    assert no_evidence_result["valid"] is False
    assert "unavailable" in no_evidence_result["ranking_issue"]


def test_5_insight_regeneration_after_validation_failure(monkeypatch):
    """5. Insight regeneration receives actionable validation feedback."""
    evidence = build_insight_evidence(SYNTHETIC_QUERY_RESULTS)

    # Simulate an invalid insight in state
    state = {
        "user_question": "What is the laboratory change from baseline by treatment arm?",
        "insight": "Drug X changed by -99.9 g/dL.",
        "query_result": SYNTHETIC_QUERY_RESULTS,
        "insight_evidence": evidence,
        "insight_retry_count": 0,
    }

    # First validation step
    val_out = validate_insight_node(state)
    assert val_out["failed_node"] == "validate_insight"
    assert "validation_feedback" in val_out
    assert "-99.9" in val_out["validation_feedback"]

    # Check that router directs to regenerate_insight
    combined_state = {**state, **val_out}
    next_node = insight_validation_router(combined_state)
    assert next_node == "regenerate_insight"

    # Mock regeneration to verify it uses the actionable feedback
    received_feedback = []
    def mock_regenerate(user_question, query_results, validation_message, insight_evidence=None):
        received_feedback.append(validation_message)
        return (
            "At Week 8, mean change in Drug X was -0.80 (-5.96%) and Placebo was -0.10 (-0.75%)."
        )

    monkeypatch.setattr("app.workflow.graph.regenerate_insight", mock_regenerate)

    regen_out = regenerate_insight_node(combined_state)
    assert regen_out["insight_retry_count"] == 1
    assert len(received_feedback) == 1
    assert "-99.9" in received_feedback[0]


def test_6_exhaustion_of_allowed_retry_count():
    """6. Exhaustion of the allowed retry count results in controlled terminal routing."""
    evidence = build_insight_evidence(SYNTHETIC_QUERY_RESULTS)

    state = {
        "user_question": "What is the laboratory change from baseline by treatment arm?",
        "insight": "Drug X changed by -99.9 g/dL.",
        "query_result": SYNTHETIC_QUERY_RESULTS,
        "insight_evidence": evidence,
        "insight_retry_count": 2,  # Already at retry limit
    }

    val_out = validate_insight_node(state)
    assert val_out["failed_node"] == "validate_insight"
    assert "maximum regeneration attempts" in val_out["error"]

    combined_state = {**state, **val_out}
    next_node = insight_validation_router(combined_state)
    assert next_node == "stop"
