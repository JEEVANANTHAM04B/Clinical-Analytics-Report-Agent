"""
tests/evaluation/test_insight_generation.py
===========================================
Evaluates generated clinical insights using:
1. Deterministic evidence quality metric (no hallucinations, valid numbers).
2. DeepEval AnswerRelevancyMetric and FaithfulnessMetric when LLM judge is enabled.
"""

import pytest
from app.ai.insight_generator import generate_insight
from app.analytics.insight_evidence import build_insight_evidence


def test_insight_factual_grounding_deterministic(evidence_metric):
    """
    Deterministic evaluation: Verifies that numbers cited in insight text
    originate strictly from verified query results and deterministic evidence summary.
    """
    results = [
        {"TRT01A": "Drug X", "cnt": 5011},
        {"TRT01A": "Placebo", "cnt": 4989},
    ]
    evidence = build_insight_evidence(results)

    insight = generate_insight(
        user_question="How many subjects are assigned to each treatment arm?",
        query_results=results,
        rag_context="Study protocol Phase III randomized controlled trial.",
        insight_evidence=evidence,
    )

    assert insight and len(insight.strip()) > 0

    grounding = evidence_metric.evaluate_grounding(
        insight_text=insight,
        query_results=results,
        deterministic_evidence=evidence,
        rag_context="Study protocol Phase III randomized controlled trial.",
    )
    assert grounding["passed"] is True, f"Insight grounding failed: {grounding['reason']}"


def test_insight_empty_result_handling(evidence_metric):
    """
    Deterministic evaluation: Verifies that an empty query result
    causes the insight generator to clearly report no matching records.
    """
    results = []
    evidence = build_insight_evidence(results)

    insight = generate_insight(
        user_question="Find all subjects with severe toxicity at baseline.",
        query_results=results,
        rag_context="",
        insight_evidence=evidence,
    )

    assert insight and len(insight.strip()) > 0
    grounding = evidence_metric.evaluate_grounding(
        insight_text=insight,
        query_results=results,
        deterministic_evidence=evidence,
    )
    assert grounding["passed"] is True


def test_deepeval_llm_judge_metrics(request, deepeval_gemini_judge):
    """
    DeepEval LLM-as-a-judge evaluation: AnswerRelevancy and Faithfulness.
    Executed when --run-deepeval-judge is passed and GEMINI_API_KEY is available.
    """
    if not request.config.getoption("--run-deepeval-judge"):
        pytest.skip("Pass --run-deepeval-judge to execute DeepEval LLM-as-a-judge evaluations.")

    from deepeval.test_case import LLMTestCase
    from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric

    question = "How many subjects are assigned to each treatment arm?"
    results = [
        {"TRT01A": "Drug X", "cnt": 5011},
        {"TRT01A": "Placebo", "cnt": 4989},
    ]
    evidence = build_insight_evidence(results)
    rag_context = "Phase III clinical trial assessing Drug X against Placebo."

    insight = generate_insight(
        user_question=question,
        query_results=results,
        rag_context=rag_context,
        insight_evidence=evidence,
    )

    test_case = LLMTestCase(
        input=question,
        actual_output=insight,
        retrieval_context=[
            f"Query Results: Drug X has 5011 subjects; Placebo has 4989 subjects. Total: 10000.",
            rag_context,
        ],
    )

    # 1. Answer Relevancy Metric
    relevancy_metric = AnswerRelevancyMetric(
        threshold=0.7,
        model=deepeval_gemini_judge,
        include_reason=True,
    )
    relevancy_metric.measure(test_case)
    assert relevancy_metric.is_successful(), f"AnswerRelevancy failed: {relevancy_metric.reason}"

    # 2. Faithfulness Metric
    faithfulness_metric = FaithfulnessMetric(
        threshold=0.7,
        model=deepeval_gemini_judge,
        include_reason=True,
    )
    faithfulness_metric.measure(test_case)
    assert faithfulness_metric.is_successful(), f"Faithfulness failed: {faithfulness_metric.reason}"
