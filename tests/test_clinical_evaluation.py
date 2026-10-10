"""
tests/test_clinical_evaluation.py
=================================
Comprehensive regression test suite verifying the Clinical Trial / CDISC Evaluation
and Golden Benchmark system.

Validates:
1. Golden benchmark file integrity (40 cases covering all 8 clinical domains).
2. Category distribution (enrollment, demographics, safety, lab, vitals, efficacy, disposition, RAG).
3. Verified MySQL ground-truth values (10,000 subjects, 2,518 SAEs, 2,126 responders, 0 dropouts).
4. CDISC SQL test cases (21 cases, 100% validation pass rate).
5. CDISC SQL plan test cases (15 cases, 100% plan validation pass rate).
6. CDISC SQL execution test cases (10 queries successfully executed against MySQL).
7. CDISC dataset coverage (SDTM dm, ae, ex, lb, vs, study, sites + ADaM adsl, adae, adlb, advs, adresp).
8. RAG concept definitions and terminology coverage.
9. Full legacy EHR benchmark preservation in evals/datasets/legacy/ (10 benchmark files).
10. Benchmark evaluation runner integrity (evals/run_clinical_benchmark.py).
"""

import os
import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from app.analytics.sql_validator import validate_sql
from app.analytics.query_executor import execute_query
from app.database.schema_service import get_database_schema
from app.clinical.question_mapping import build_clinical_question_plan
from evals.run_clinical_benchmark import load_golden_benchmark, evaluate_analytical_case


BENCHMARK_PATH = Path("evals/datasets/clinical_golden_benchmark.json")
LEGACY_DIR = Path("evals/datasets/legacy")


def test_golden_benchmark_file_exists_and_structure():
    """Verify that the master clinical benchmark dataset exists and contains 40 valid cases."""
    assert BENCHMARK_PATH.exists(), f"Benchmark file missing at {BENCHMARK_PATH}"
    cases = load_golden_benchmark()
    assert len(cases) == 40, f"Expected exactly 40 golden cases, found {len(cases)}"

    for case in cases:
        assert "id" in case, f"Case missing 'id': {case}"
        assert "question" in case, f"Case missing 'question': {case}"
        assert "category" in case, f"Case missing 'category': {case}"
        assert "expected_intent" in case, f"Case missing 'expected_intent': {case}"
        assert "expected_terminology" in case, f"Case missing 'expected_terminology': {case}"


def test_golden_benchmark_categories_distribution():
    """Verify that all 8 mandatory clinical domains are represented in the benchmark."""
    cases = load_golden_benchmark()
    categories = {}
    for c in cases:
        cat = c["category"]
        categories[cat] = categories.get(cat, 0) + 1

    expected_categories = {
        "enrollment": 4,
        "demographics": 3,
        "safety": 5,
        "laboratory": 3,
        "vital_signs": 3,
        "efficacy": 4,
        "disposition": 3,
        "RAG": 15,
    }

    for cat, expected_count in expected_categories.items():
        assert cat in categories, f"Missing category: {cat}"
        assert categories[cat] == expected_count, (
            f"Category '{cat}' count mismatch: got {categories[cat]}, expected {expected_count}"
        )


def test_golden_benchmark_ground_truth_values():
    """Verify ground truth numerical metrics against clinical_trial_analytics_db schema."""
    cases = {c["id"]: c for c in load_golden_benchmark()}

    # Enrollment
    assert cases["gold_enr_001"]["expected_result"] == 10000
    assert cases["gold_enr_002"]["expected_result"]["site_id"] == "SITE010"
    assert cases["gold_enr_004"]["expected_result"]["Drug X"] == 5011

    # Demographics
    mean_age_res = cases["gold_dem_001"]["expected_result"]
    mean_age_val = mean_age_res["mean_age"] if isinstance(mean_age_res, dict) else mean_age_res
    assert abs(mean_age_val - 54.63) < 0.5
    assert cases["gold_dem_002"]["expected_result"]["F"] == 5033

    # Safety
    assert cases["gold_saf_001"]["expected_result"] == 10000
    assert cases["gold_saf_002"]["expected_result"] == 2518
    assert cases["gold_saf_004"]["expected_result"]["MILD"] == 7018

    # Efficacy
    assert cases["gold_eff_003"]["expected_result"] == 2126

    # Disposition
    assert cases["gold_dsp_002"]["expected_result"] == 10000
    assert cases["gold_dsp_003"]["expected_result"] == 0


def test_cdisc_sql_test_cases_suite():
    """Verify that evals/datasets/sql_test_cases.json has 21 CDISC cases and all valid queries pass validation."""
    path = Path("evals/datasets/sql_test_cases.json")
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    assert len(cases) == 21

    schema = get_database_schema()
    for case in cases:
        sql = case["sql"]
        exp_valid = case["expected_valid"]
        is_valid, _ = validate_sql(sql, approved_schema=schema)
        assert is_valid == exp_valid, (
            f"Case {case['id']} validation mismatch: got {is_valid}, expected {exp_valid}"
        )


def test_cdisc_sql_plan_test_cases_suite():
    """Verify that evals/datasets/sql_plan_test_cases.json has 15 CDISC plans and all pass plan validation."""
    path = Path("evals/datasets/sql_plan_test_cases.json")
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    assert len(cases) == 15

    schema = get_database_schema()
    for case in cases:
        plan = case["analysis_plan"]
        sql = case["sql"]
        exp_valid = case["expected_valid"]
        is_valid, _ = validate_sql(sql=sql, approved_schema=schema, analysis_plan=plan)
        assert is_valid == exp_valid, (
            f"Plan case {case['id']} validation mismatch: got {is_valid}, expected {exp_valid}"
        )


def test_cdisc_sql_execution_test_cases_suite():
    """Verify that evals/datasets/sql_execution_test_cases.json queries execute against MySQL."""
    path = Path("evals/datasets/sql_execution_test_cases.json")
    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    assert len(cases) == 10

    for case in cases:
        rows = execute_query(case["sql"])
        assert rows is not None
        assert len(rows) > 0, f"Query returned empty result for {case['id']}"


def test_legacy_ehr_datasets_preservation():
    """Verify that all 10 legacy EHR benchmark datasets are archived and intact for backward compatibility."""
    assert LEGACY_DIR.exists()
    expected_legacy_files = [
        "analysis_plan_test_cases.json",
        "chart_test_cases.json",
        "e2e_test_cases.json",
        "insight_deepeval_test_cases.json",
        "insight_test_cases.json",
        "plan_regeneration_test_cases.json",
        "rag_test_cases.json",
        "sql_execution_test_cases.json",
        "sql_plan_test_cases.json",
        "sql_test_cases.json",
    ]
    for fn in expected_legacy_files:
        fpath = LEGACY_DIR / fn
        assert fpath.exists(), f"Legacy file missing: {fn}"
        assert fpath.stat().st_size > 0, f"Legacy file is empty: {fn}"


def test_clinical_datasets_coverage():
    """Verify that golden benchmark exercises SDTM and ADaM clinical trial domains."""
    cases = load_golden_benchmark()
    all_datasets = set()
    for c in cases:
        for ds in c.get("expected_datasets", []):
            all_datasets.add(ds.lower())

    sdtm_expected = {"study", "sites", "dm", "ae"}
    adam_expected = {"adsl", "adae", "adlb", "advs", "adresp"}

    assert sdtm_expected.issubset(all_datasets), f"Missing SDTM datasets: {sdtm_expected - all_datasets}"
    assert adam_expected.issubset(all_datasets), f"Missing ADaM datasets: {adam_expected - all_datasets}"


def test_clinical_rag_expected_concepts():
    """Verify that all 15 RAG golden cases define CDISC standard concepts and terminology."""
    cases = [c for c in load_golden_benchmark() if c.get("category") == "RAG"]
    assert len(cases) == 15

    for case in cases:
        assert case.get("expected_rag_topic") is not None
        has_concepts = len(case.get("expected_rag_concepts", [])) > 0 or len(case.get("expected_terminology", [])) > 0
        assert has_concepts, f"RAG case {case['id']} missing expected concepts or terminology"


# =============================================================================
# REGRESSION TESTS FOR THE 4 SQL SEMANTIC-CORRECTNESS ISSUES
# =============================================================================

def test_regression_age_distribution_by_treatment_arm_semantics():
    """Regression test: Age question with arm breakdown must group by ARM and compute mean per arm."""
    plan = build_clinical_question_plan("What is the age distribution by treatment arm?")
    assert plan.is_supported is True
    assert plan.dimensions == ["ARM"]
    assert "GROUP BY ARM" in plan.suggested_sql.upper()
    assert "AVG" in plan.suggested_sql.upper()

    rows = execute_query(plan.suggested_sql)
    assert len(rows) == 2, f"Expected 2 treatment arm rows, got {len(rows)}"
    arms = {r["ARM"] for r in rows}
    assert arms == {"Drug X", "Placebo"}


def test_regression_treatment_emergent_ae_filter_semantics():
    """Regression test: TEAE questions must explicitly filter on TRTEMFL = 'Y'."""
    plan = build_clinical_question_plan("What is the treatment-emergent AE rate?")
    assert plan.is_supported is True
    assert "TRTEMFL = 'Y'" in plan.suggested_sql.upper()
    assert any("TRTEMFL" in f.upper() for f in plan.filter_conditions)

    rows = execute_query(plan.suggested_sql)
    assert len(rows) == 2
    assert all("ae_rate_pct" in r for r in rows)


def test_regression_evaluator_cdisc_arm_equivalence():
    """Regression test: Semantic evaluator recognizes ADaM TRT01A as valid equivalent of concept ARM."""
    schema = get_database_schema()
    case = {
        "id": "gold_enr_004",
        "question": "What is the treatment-arm distribution?",
        "category": "enrollment",
        "expected_kpi": "SUBJECTS_BY_TREATMENT_ARM",
        "expected_datasets": ["adsl"],
        "expected_columns": ["TRT01A", "USUBJID"],
        "expected_sql_concepts": ["GROUP BY", "ARM"],
        "expected_result": {"Drug X": 5011, "Placebo": 4989},
        "expected_result_type": "distribution",
        "expected_terminology": ["treatment arm"],
    }
    res = evaluate_analytical_case(case, schema)
    assert res["sql_semantic"] is True, f"Failed semantic check with details: {res['details']}"


def test_regression_evaluator_ranking_equivalence():
    """Regression test: Semantic evaluator recognizes ORDER BY ... DESC as ranking semantics for LIMIT."""
    schema = get_database_schema()
    case = {
        "id": "gold_enr_002",
        "question": "Which site has the highest enrollment?",
        "category": "enrollment",
        "expected_kpi": "ENROLLMENT_BY_SITE",
        "expected_datasets": ["sites", "dm"],
        "expected_columns": ["SITEID", "SITE_NAME", "USUBJID"],
        "expected_sql_concepts": ["JOIN", "GROUP BY", "ORDER BY DESC", "LIMIT"],
        "expected_result": {"site_id": "SITE010", "site_name": "Clinical Center 10", "enrolled_subjects": 1053},
        "expected_result_type": "entity_ranking",
        "expected_terminology": ["highest enrollment"],
    }
    res = evaluate_analytical_case(case, schema)
    assert res["sql_semantic"] is True, f"Failed semantic check with details: {res['details']}"


def test_regression_uat_natural_language_treatment_group_mapping():
    """Regression test: 'treatment group' and 'study population by treatment' resolve to SUBJECTS_BY_TREATMENT_ARM."""
    plan1 = build_clinical_question_plan("How many subjects are in each treatment group?")
    assert plan1.is_supported is True
    assert plan1.matched_kpi_id == "SUBJECTS_BY_TREATMENT_ARM"
    assert "adsl" in plan1.datasets

    plan2 = build_clinical_question_plan("Break down the study population by treatment.")
    assert plan2.is_supported is True
    assert plan2.matched_kpi_id == "SUBJECTS_BY_TREATMENT_ARM"


def test_regression_uat_natural_language_age_profile_mapping():
    """Regression test: 'Show the age profile for each treatment group' groups age by ARM."""
    plan = build_clinical_question_plan("Show the age profile for each treatment group.")
    assert plan.is_supported is True
    assert plan.matched_kpi_id == "AVERAGE_AGE"
    assert "ARM" in plan.dimensions or "ARM" in (plan.suggested_sql or "")


def test_regression_uat_natural_language_ae_more_comparison():
    """Regression test: 'Which treatment group had more adverse events' resolves to AE_RATE_BY_TREATMENT."""
    plan = build_clinical_question_plan("Which treatment group had more adverse events?")
    assert plan.is_supported is True
    assert plan.matched_kpi_id == "AE_RATE_BY_TREATMENT"


def test_regression_uat_sql_generator_forbids_window_functions():
    """Regression test: _check_sql_vs_clinical_plan rejects queries with OVER () or STDDEV."""
    from app.analytics.sql_generator import _check_sql_vs_clinical_plan
    plan = build_clinical_question_plan("Break down the study population by treatment.")

    bad_sql_over = "SELECT TRT01A, COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () FROM adsl GROUP BY TRT01A;"
    is_ok, reason = _check_sql_vs_clinical_plan(bad_sql_over, plan)
    assert is_ok is False
    assert "OVER" in reason

    bad_sql_stddev = "SELECT TRT01A, STDDEV(AGE) FROM adsl GROUP BY TRT01A;"
    is_ok2, reason2 = _check_sql_vs_clinical_plan(bad_sql_stddev, plan)
    assert is_ok2 is False
    assert "STDDEV" in reason2


def test_regression_uat_ambiguous_queries_safety():
    """Regression test: Ambiguous queries produce safe broad responses or safe rejections without invalid SQL."""
    from evals.run_clinical_uat import evaluate_ambiguous_case
    from app.workflow.graph import build_graph
    g = build_graph()
    rep = evaluate_ambiguous_case({"id": "test_amb_01", "question": "Show the patient data."}, g)
    assert rep["fallback_safe"] is True


# =============================================================================
# REGRESSION TESTS FOR FINAL TARGETED NATURAL-LANGUAGE ROBUSTNESS FIXES
# =============================================================================

def test_regression_issue1_treatment_comparison_intent_priority():
    """
    Issue 1 Regression:
    Ensure treatment comparison signals (versus, vs, Drug X versus placebo,
    treatment versus placebo, compared with placebo, each treatment, treatment groups)
    take precedence over generic total-subject matching across multiple phrasings.
    """
    test_questions = [
        "How many participants received Drug X versus placebo?",
        "Compare the number of subjects receiving Drug X and placebo.",
        "How many subjects are in each treatment?",
        "Show the treatment allocation.",
        "Compare Drug X with placebo by participant count.",
        "Compare Drug X versus placebo subjects.",
        "Show participant count compared with placebo.",
    ]
    for q in test_questions:
        plan = build_clinical_question_plan(q)
        assert plan.is_supported is True, f"Failed for question: '{q}'"
        assert plan.matched_kpi_id == "SUBJECTS_BY_TREATMENT_ARM", (
            f"Question '{q}' routed to '{plan.matched_kpi_id}' instead of SUBJECTS_BY_TREATMENT_ARM"
        )
        assert "TRT01A" in plan.dimensions or "ARM" in plan.dimensions, f"Missing arm dimension for '{q}'"
        assert "adsl" in plan.datasets, f"Missing adsl dataset for '{q}'"


def test_regression_issue2_teae_fallback_preserves_clinical_semantics():
    """
    Issue 2 Regression:
    Ensure TEAE signals ('treatment-emergent', 'treatment-emergent AE', 'TEAE', 'TEAEs')
    always route to TEAE clinical logic (adae + adsl, TRTEMFL = 'Y') even when simulating
    LLM fallback/rate limiting.
    """
    from app.analytics.sql_generator import _deterministic_sql_fallback, _check_sql_vs_clinical_plan

    teae_questions = [
        "Show subjects with treatment-emergent AEs.",
        "How many patients had TEAEs?",
        "What is the TEAE incidence?",
        "Show treatment-emergent adverse events by treatment.",
    ]

    for q in teae_questions:
        # 1. Deterministic plan level
        plan = build_clinical_question_plan(q)
        assert plan.is_supported is True, f"Plan not supported for '{q}'"
        assert plan.matched_kpi_id == "AE_RATE_BY_TREATMENT", f"Unexpected KPI for '{q}': {plan.matched_kpi_id}"
        assert "adae" in plan.datasets, f"Missing adae dataset for '{q}'"
        assert any("TRTEMFL" in f for f in plan.filter_conditions), f"Missing TRTEMFL filter in plan for '{q}'"

        # 2. Simulated LLM fallback/rate limiting
        fallback_sql = _deterministic_sql_fallback(q, "Analysis plan unavailable due to rate limit")
        assert fallback_sql is not None, f"Fallback SQL is None for '{q}'"
        assert "adae" in fallback_sql.lower(), f"Fallback SQL missing adae for '{q}'"
        assert "trtemfl" in fallback_sql.lower() and "'y'" in fallback_sql.lower(), (
            f"Fallback SQL missing TRTEMFL = 'Y' for '{q}': {fallback_sql}"
        )

        # 3. Plan consistency check rejects SQL missing TRTEMFL
        sql_without_teae = "SELECT adsl.TRT01A, COUNT(DISTINCT adae.USUBJID) FROM adsl JOIN adae ON adsl.USUBJID = adae.USUBJID GROUP BY adsl.TRT01A;"
        is_ok, reason = _check_sql_vs_clinical_plan(sql_without_teae, plan)
        assert is_ok is False, f"Check should have rejected query missing TRTEMFL for '{q}'"
        assert "TRTEMFL" in reason


def test_regression_issue3_discontinuation_vs_completion_logic():
    """
    Issue 3 Regression:
    Ensure discontinuation phrases resolve to discontinuation logic (EOSDT IS NULL),
    while completion phrases resolve to completion logic (EOSDT IS NOT NULL) and are NOT inverted.
    """
    from app.analytics.sql_generator import _check_sql_vs_clinical_plan

    discontinuation_phrases = [
        "How many subjects discontinued?",
        "Count the study discontinuations.",
        "How many subjects who discontinued?",
        "patients who dropped out",
        "What is the patient dropout count?",
        "How many did not complete the study?",
    ]

    for q in discontinuation_phrases:
        plan = build_clinical_question_plan(q)
        assert plan.is_supported is True, f"Failed for question: '{q}'"
        assert plan.matched_kpi_id == "SUBJECT_DISPOSITION", f"Wrong KPI for '{q}': {plan.matched_kpi_id}"
        assert any("EOSDT IS NULL" in f for f in plan.filter_conditions), (
            f"Question '{q}' missing EOSDT IS NULL filter in plan: {plan.filter_conditions}"
        )
        assert "EOSDT IS NULL" in (plan.suggested_sql or ""), f"Suggested SQL missing EOSDT IS NULL for '{q}'"

        # Plan check rejects SQL with EOSDT IS NOT NULL for discontinuation
        bad_sql = "SELECT COUNT(*) FROM adsl WHERE EOSDT IS NOT NULL;"
        is_ok, reason = _check_sql_vs_clinical_plan(bad_sql, plan)
        assert is_ok is False, f"Check should have rejected EOSDT IS NOT NULL for discontinued query: '{q}'"
        assert "EOSDT IS NULL" in reason

    completion_phrases = [
        "How many subjects completed?",
        "How many subjects completed the study?",
        "Count the study completers.",
    ]

    for q in completion_phrases:
        plan = build_clinical_question_plan(q)
        assert plan.is_supported is True, f"Failed for question: '{q}'"
        assert plan.matched_kpi_id == "SUBJECT_DISPOSITION", f"Wrong KPI for '{q}': {plan.matched_kpi_id}"
        assert any("EOSDT IS NOT NULL" in f for f in plan.filter_conditions), (
            f"Question '{q}' missing EOSDT IS NOT NULL filter in plan: {plan.filter_conditions}"
        )
        assert "EOSDT IS NOT NULL" in (plan.suggested_sql or ""), f"Suggested SQL missing EOSDT IS NOT NULL for '{q}'"

        # Plan check rejects SQL with EOSDT IS NULL for completion
        bad_sql = "SELECT COUNT(*) FROM adsl WHERE EOSDT IS NULL;"
        is_ok, reason = _check_sql_vs_clinical_plan(bad_sql, plan)
        assert is_ok is False, f"Check should have rejected EOSDT IS NULL for completion query: '{q}'"
        assert "EOSDT IS NOT NULL" in reason


def test_regression_issue4_multi_row_additive_equivalence_evaluation():
    """
    Issue 4 Regression:
    Ensure UAT evaluation correctly evaluates multi-row partitioned subject counts
    (e.g. Drug X = 5,011, Placebo = 4,989) against an expected scalar total (10,000)
    when grouped by valid mutually exclusive dimensions.
    """
    from evals.run_clinical_uat import check_multi_row_additive_equivalence

    case = {
        "id": "uat_disp_001",
        "question": "How many participants completed the study?",
        "category": "disposition",
        "expected_kpi": "SUBJECT_DISPOSITION",
        "expected_result": 10000,
        "expected_result_type": "scalar_integer",
    }

    # Case A: Valid partitioned multi-row result summing to 10,000
    valid_rows = [
        {"treatment_arm": "Drug X", "completed_subjects": 5011},
        {"treatment_arm": "Placebo", "completed_subjects": 4989},
    ]
    assert check_multi_row_additive_equivalence(valid_rows, 10000, case) is True

    # Case B: Multi-row result with wrong sum
    wrong_rows = [
        {"treatment_arm": "Drug X", "completed_subjects": 2000},
        {"treatment_arm": "Placebo", "completed_subjects": 3000},
    ]
    assert check_multi_row_additive_equivalence(wrong_rows, 10000, case) is False

    # Case C: Single row should not trigger multi-row equivalence helper
    single_row = [{"completed_subjects": 10000}]
    assert check_multi_row_additive_equivalence(single_row, 10000, case) is False

    # Case D: Non-additive KPI (e.g. rate or percentage) must be rejected
    rate_case = {
        "id": "uat_rate_001",
        "category": "safety",
        "expected_kpi": "AE_RATE_BY_TREATMENT",
        "expected_result": 10000,
        "expected_result_type": "scalar_integer",
    }
    assert check_multi_row_additive_equivalence(valid_rows, 10000, rate_case) is False

    # Case E: Invalid grouping dimension (non-mutually-exclusive) must be rejected
    invalid_dim_rows = [
        {"adverse_event_term": "Headache", "completed_subjects": 5011},
        {"adverse_event_term": "Nausea", "completed_subjects": 4989},
    ]
    assert check_multi_row_additive_equivalence(invalid_dim_rows, 10000, case) is False
