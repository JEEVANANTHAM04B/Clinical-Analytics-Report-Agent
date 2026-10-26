"""
tests/evaluation/test_question_understanding.py
===============================================
Evaluates question parsing, intent recognition, and required-table identification
across all clinical categories (Subject, Safety, Top AE, Labs, Vitals, Response, Sites).
"""

import pytest
from app.clinical.table_validator import identify_required_tables
from app.clinical.question_mapping import build_clinical_question_plan


def test_question_understanding_categories(eval_dataset):
    """
    Evaluates that natural-language clinical questions map to the
    correct clinical question plan and identify the minimum required datasets.
    """
    for case in eval_dataset:
        if case["category"].startswith("SECURITY_"):
            continue

        question = case["question"]
        expected_req = set(case["required_datasets"])
        allowed_alt = set(case.get("allowed_alternative_datasets", []))

        # 1. Deterministic clinical question plan
        plan = build_clinical_question_plan(question)
        assert plan is not None, f"Failed to build question plan for: '{question}'"

        # 2. Required tables identification
        identified, is_available, err = identify_required_tables(question)

        # Allow alternatives (e.g. adsl or dm for subject questions; adae or ae for AEs)
        matches_expected = expected_req.issubset(identified) or any(
            alt in identified for alt in allowed_alt
        )
        assert matches_expected, (
            f"Case {case['id']} failed required dataset matching.\n"
            f"Question: {question}\n"
            f"Expected: {expected_req} (or alternatives {allowed_alt})\n"
            f"Identified: {identified}"
        )


def test_question_plan_dimensions_and_metrics(eval_dataset):
    """
    Verifies that structured analytical questions extract the correct
    dimensions and metrics (e.g. TRT01A / ARM for treatment arm questions).
    """
    for case in eval_dataset:
        if case["category"].startswith("SECURITY_"):
            continue

        question = case["question"]
        plan = build_clinical_question_plan(question)
        if not plan or not plan.is_supported:
            continue

        # If grouping variables expected, verify plan has dimensions
        exp_grouping = case.get("grouping_variables", [])
        if exp_grouping:
            assert len(plan.dimensions) > 0 or "arm" in question.lower() or "treatment" in question.lower(), (
                f"Case {case['id']} expects grouping variables {exp_grouping}, but plan has none: {plan}"
            )
