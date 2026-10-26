"""
tests/evaluation/test_clinical_analytics_e2e.py
===============================================
Full End-to-End Integration Evaluation of the Clinical Analytics Platform.
Exercises the real LangGraph pipeline from natural-language question
to validated SQL, MySQL execution, evidence extraction, and visualization.
"""

import pytest
from app.workflow.graph import clinical_analytics_graph
from app.database.schema_service import get_database_schema


def test_e2e_subject_distribution_workflow(pipeline_metric, sql_safety_metric):
    """
    E2E Test: Subject distribution across treatment arms.
    Pipeline: validate_table_selection -> load_schema -> analyze_question ->
              human_approval -> generate_sql -> validate_sql -> execute_sql ->
              validate_results -> generate_insight -> validate_insight -> generate_chart
    """
    question = "How many subjects are assigned to each treatment arm?"
    selected = ["adsl", "dm"]

    state_input = {
        "user_question": question,
        "selected_tables": selected,
        "approval_status": "approved",  # Approved to run complete execution
        "plan_version": 1,
    }

    final_state = clinical_analytics_graph.invoke(state_input)

    # 1. Pipeline completeness
    p_eval = pipeline_metric.evaluate_state(final_state, expected_outcome="authorized")
    assert p_eval["passed"] is True, f"Pipeline completeness failed: {p_eval['reason']}"

    # 2. SQL Safety & Boundary Containment
    sql = final_state.get("sql_query")
    assert sql, "Expected SQL query to be generated"
    s_eval = sql_safety_metric.evaluate_query(sql, selected_tables=selected)
    assert s_eval["passed"] is True, f"SQL safety failed: {s_eval['reason']}"

    # 3. Query Results Integrity
    results = final_state.get("results") or final_state.get("query_result")
    assert results and len(results) >= 2, f"Expected grouped treatment arm results, got: {results}"
    total_subjects = sum(int(r.get("cnt") or r.get("count") or r.get("subject_count") or list(r.values())[-1]) for r in results)
    assert total_subjects == 10000, f"Expected 10,000 subjects, got {total_subjects}"

    # 4. Chart Specification
    chart_spec = final_state.get("chart_spec")
    assert chart_spec is not None, "Expected chart spec to be generated"
    assert "chart_type" in chart_spec
    assert "x_column" in chart_spec


def test_e2e_adverse_event_rate_workflow(pipeline_metric, sql_safety_metric):
    """
    E2E Test: Adverse event incidence rate by treatment arm.
    Requires multi-table join across ADSL and ADAE.
    """
    question = "What is the adverse event incidence rate by treatment arm?"
    selected = ["adsl", "adae"]

    state_input = {
        "user_question": question,
        "selected_tables": selected,
        "approval_status": "approved",
        "plan_version": 1,
    }

    final_state = clinical_analytics_graph.invoke(state_input)

    # 1. Pipeline completeness
    p_eval = pipeline_metric.evaluate_state(final_state, expected_outcome="authorized")
    assert p_eval["passed"] is True, f"Pipeline completeness failed: {p_eval['reason']}"

    # 2. SQL generated must not reference unselected tables
    sql = final_state.get("sql_query")
    assert sql
    s_eval = sql_safety_metric.evaluate_query(sql, selected_tables=selected)
    assert s_eval["passed"] is True, f"SQL safety failed: {s_eval['violations']}"

    # 3. Results check
    results = final_state.get("results") or final_state.get("query_result")
    assert results and len(results) > 0


def test_e2e_missing_table_blocked_workflow(pipeline_metric):
    """
    E2E Test: Missing table early termination.
    Question requires ADAE, but only ADSL selected.
    Expected: Early termination at boundary guard; no SQL or results.
    """
    question = "What is the adverse event incidence rate by treatment arm?"
    selected = ["adsl"]

    state_input = {
        "user_question": question,
        "selected_tables": selected,
        "approval_status": "approved",
    }

    final_state = clinical_analytics_graph.invoke(state_input)

    # Must be safely blocked
    p_eval = pipeline_metric.evaluate_state(final_state, expected_outcome="blocked")
    assert p_eval["passed"] is True, f"Blocked evaluation failed: {p_eval['reason']}"
    assert final_state.get("validation_status") == "blocked"
    assert "adae" in final_state.get("missing_tables", [])
    assert final_state.get("sql_query") is None
    assert final_state.get("results") is None or len(final_state.get("results", [])) == 0


def test_synthetic_kpi_mathematical_invariants(synthetic_data, correctness_metric):
    """
    Phase 7: Evaluates KPI formulas against trusted synthetic fixtures
    with 4 subjects in ADSL and multi-event ADAE records.
    Verifies numerator, denominator, and incidence percentage.
    """
    adsl = synthetic_data["adsl"]
    adae = synthetic_data["adae"]
    ground_truth = synthetic_data["ground_truth"]["ae_incidence_rate"]

    # Calculate actual KPI values directly using clinical business logic
    calculated_results = []
    arms = sorted(list(set(s["TRT01A"] for s in adsl)))

    for arm in arms:
        # Denominator: subjects in safety population
        safety_subjects = set(s["USUBJID"] for s in adsl if s["TRT01A"] == arm and s["SAFFL"] == "Y")
        denom = len(safety_subjects)

        # Numerator: distinct subjects in safety pop with >=1 treatment-emergent AE
        ae_subjects = set(
            e["USUBJID"]
            for e in adae
            if e["TRT01A"] == arm and e["TRTEMFL"] == "Y" and e["USUBJID"] in safety_subjects
        )
        numer = len(ae_subjects)
        pct = round((numer / denom * 100.0), 2) if denom else 0.0

        calculated_results.append({
            "TRT01A": arm,
            "numerator": numer,
            "denominator": denom,
            "percentage": pct,
        })

    # Overall total
    all_safety = set(s["USUBJID"] for s in adsl if s["SAFFL"] == "Y")
    all_ae = set(e["USUBJID"] for e in adae if e["TRTEMFL"] == "Y" and e["USUBJID"] in all_safety)
    calculated_results.append({
        "TRT01A": "Overall",
        "numerator": len(all_ae),
        "denominator": len(all_safety),
        "percentage": round((len(all_ae) / len(all_safety) * 100.0), 2) if all_safety else 0.0,
    })

    # Evaluate using clinical correctness metric
    eval_res = correctness_metric.evaluate_grouped_percentages(
        actual_rows=calculated_results,
        expected_groups=ground_truth,
        group_col="TRT01A",
        pct_col="percentage",
    )
    assert eval_res["passed"] is True, f"Synthetic KPI calculation failed: {eval_res['reason']}"
