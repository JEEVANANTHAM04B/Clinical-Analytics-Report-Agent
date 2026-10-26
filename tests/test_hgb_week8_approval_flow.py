"""
tests/test_hgb_week8_approval_flow.py
======================================
Regression test for the Clinical Analytics approval workflow failure:
Ensures that when an analyst approves an analysis plan querying ADLB (such as Hemoglobin at Week 8),
table authorization resolves correctly, SQL validation passes, real MySQL data executes,
and results, insights, and visualizations are produced without SQLValidationError.
"""

import pytest
from app.schemas.analytics import AnalyticsRequest
from app.api.analytics import run_analytics
from app.analytics.sql_validator import validate_sql, _extract_plan_datasets


def test_extract_plan_datasets_bullet_format():
    """Verify that _extract_plan_datasets parses '- Table: adlb' without treating prose words as tables."""
    plan = (
        "- Table: adlb\n"
        "- Columns: TRT01A, AVISIT, AVAL, BASE, CHG, PCHG, ANL01FL, PARAM/PARAMCD, USUBJID\n"
        "- No joins required\n"
        "- Mean baseline: AVG(BASE)\n"
        "- Mean Week 8 value: AVG(AVAL)\n"
        "- Mean change: AVG(CHG)\n"
        "- Mean percentage change: AVG(PCHG)\n"
        "- Distinct subject count: COUNT(DISTINCT USUBJID)\n"
        "- Group by TRT01A\n"
        "- Filter PARAMCD = 'HGB'\n"
        "- Filter ANL01FL = 'Y'\n"
        "- Filter AVISIT = 'WEEK 8'\n"
        "- Filter TRT01A IN ('Drug X', 'Placebo')"
    )

    datasets = _extract_plan_datasets(plan)
    assert datasets == ["adlb"]


def test_hgb_week8_approval_workflow_end_to_end():
    """Verify end-to-end approval request with the user's exact question and plan."""
    question = (
        "Compare the mean change from baseline in hemoglobin between Drug X and Placebo at Week 8. "
        "Use records where ANL01FL = 'Y', group the results by treatment arm, and calculate the mean baseline value, "
        "mean Week 8 value, mean change from baseline, mean percentage change, and distinct subject count. "
        "Use the actual visit label 'WEEK 8'. Do not filter for 'END OF TREATMENT'. "
        "Present the results in a comparison table and provide a concise clinical interpretation."
    )

    current_plan = (
        "- Table: adlb\n"
        "- Columns: TRT01A, AVISIT, AVAL, BASE, CHG, PCHG, ANL01FL, PARAM/PARAMCD, USUBJID\n"
        "- No joins required\n"
        "- Mean baseline: AVG(BASE)\n"
        "- Mean Week 8 value: AVG(AVAL)\n"
        "- Mean change: AVG(CHG)\n"
        "- Mean percentage change: AVG(PCHG)\n"
        "- Distinct subject count: COUNT(DISTINCT USUBJID)\n"
        "- Group by TRT01A\n"
        "- Filter PARAMCD = 'HGB'\n"
        "- Filter ANL01FL = 'Y'\n"
        "- Filter AVISIT = 'WEEK 8'\n"
        "- Filter TRT01A IN ('Drug X', 'Placebo')"
    )

    selected_tables = ["dm", "ae", "adsl", "adae", "adlb", "advs", "lb", "vs"]

    req = AnalyticsRequest(
        question=question,
        approval_status="approved",
        current_plan=current_plan,
        selected_tables=selected_tables,
        analysis_id=None,
        state_version=None,
    )

    response = run_analytics(req)

    assert response.status == "success"
    assert response.error is None
    assert response.sql_query is not None
    assert "adlb" in response.sql_query.lower()
    assert response.results is not None
    assert len(response.results) == 2

    # Verify real MySQL data values for Drug X and Placebo
    arms = {r["treatment_arm"]: r for r in response.results}
    assert "Drug X" in arms
    assert "Placebo" in arms
    assert arms["Drug X"]["distinct_subject_count"] == 2504
    assert arms["Placebo"]["distinct_subject_count"] == 2496
    assert abs(float(arms["Drug X"]["mean_baseline"]) - 13.54) < 0.1
    assert abs(float(arms["Placebo"]["mean_baseline"]) - 13.50) < 0.1

    assert response.insight is not None
    assert response.chart_spec is not None
    assert response.result_validation.get("valid") is True


def test_sql_validator_rejects_unauthorized_tables():
    """Verify that unauthorized tables are still strictly rejected by validate_sql."""
    sql = "SELECT * FROM passwords;"
    is_valid, msg = validate_sql(sql)
    assert not is_valid
    assert "Unauthorized" in msg or "not allowed" in msg
