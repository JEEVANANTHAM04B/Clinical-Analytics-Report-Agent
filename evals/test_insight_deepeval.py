import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
os.environ["PYTHONIOENCODING"] = "utf-8"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from deepeval import evaluate
from deepeval.evaluate.configs import AsyncConfig
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.models import GeminiModel
from deepeval.test_case import LLMTestCase

from app.analytics.insight_evidence import build_insight_evidence
from app.ai.insight_generator import generate_insight

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "insight_deepeval_test_cases.json"


class RateLimitedGeminiModel(GeminiModel):
    """
    GeminiModel subclass with automatic rate-limit backoff.
    Protects DeepEval evaluation from transient 429 Resource Exhausted (15 RPM free tier) errors.
    """

    async def a_generate(self, prompt: str, schema=None):
        for attempt in range(6):
            try:
                return await super().a_generate(prompt, schema=schema)
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota exceeded" in err_str:
                    wait_time = 7.0
                    match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_str)
                    if match:
                        wait_time = float(match.group(1)) + 1.0
                    print(f"\n[DeepEval Rate Limit] 429 detected. Sleeping {wait_time:.1f}s for quota window to reset...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
        return await super().a_generate(prompt, schema=schema)

    def generate(self, prompt: str, schema=None):
        for attempt in range(6):
            try:
                return super().generate(prompt, schema=schema)
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "Quota exceeded" in err_str:
                    wait_time = 7.0
                    match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_str)
                    if match:
                        wait_time = float(match.group(1)) + 1.0
                    print(f"\n[DeepEval Rate Limit] 429 detected. Sleeping {wait_time:.1f}s for quota window to reset...")
                    time.sleep(wait_time)
                else:
                    raise
        return super().generate(prompt, schema=schema)


def load_test_cases():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_analysis_context(query_results: list[dict], evidence: dict) -> list[str]:
    """
    Format verified SQL results, deterministic evidence summary,
    for DeepEval Faithfulness evaluation.
    """
    contexts = []

    # 1. Verified SQL Results
    if query_results:
        rows = [
            ", ".join(f"{k}: {v}" for k, v in row.items())
            for row in query_results
        ]
        contexts.append("Verified SQL Results:\n" + "\n".join(f"- {r}" for r in rows))
    else:
        contexts.append(
            "Verified SQL Results: No matching records were returned (0 rows, empty result set). "
            "There are no encounters matching the filter."
        )

    # 2. Deterministic evidence summary
    if evidence:
        ev_summary = [f"Row count: {evidence.get('row_count', len(query_results))}."]
        if evidence.get("maximum"):
            max_info = evidence["maximum"]
            ev_summary.append(f"Maximum value is {max_info.get('value')} for {max_info.get('category')}.")
        if evidence.get("minimum"):
            min_info = evidence["minimum"]
            ev_summary.append(f"Minimum value is {min_info.get('value')}.")
        contexts.append("Deterministic Summary: " + " ".join(ev_summary))

    return contexts


def run_insight_deepeval():
    test_cases = load_test_cases()
    total_cases = len(test_cases)

    print("=" * 80)
    print("DEEPEVAL INSIGHT GENERATION EVALUATION RUNNER")
    print(f"Dataset: {DATASET_PATH.name} ({total_cases} test cases)")
    print("Judge Model: gemini-3.5-flash-lite | Metrics: Faithfulness, Answer Relevancy")
    print("=" * 80)

    evaluator_model = RateLimitedGeminiModel(
        model="gemini-3.5-flash-lite",
    )

    faithfulness_metric = FaithfulnessMetric(
        threshold=0.7,
        include_reason=True,
        model=evaluator_model,
    )

    relevancy_metric = AnswerRelevancyMetric(
        threshold=0.7,
        include_reason=True,
        model=evaluator_model,
    )

    deepeval_test_cases = []
    case_metadata = []

    # Step 1: Generate insights using production logic
    print("\n--- STEP 1: GENERATING INSIGHTS VIA REAL PRODUCTION LOGIC ---")
    for idx, case in enumerate(test_cases, 1):
        case_id = case["id"]
        question = case["question"]
        query_results = case.get("query_results", [])
        expected_answer = case.get("expected_answer", "")
        # Deterministic evidence calculation
        evidence = build_insight_evidence(query_results)

        # Real production insight generation
        print(f"\nGenerating insight for [{idx}/{total_cases}] {case_id}: \"{question}\"")
        insight = generate_insight(
            user_question=question,
            query_results=query_results,
            insight_evidence=evidence,
        )

        analysis_context = build_analysis_context(query_results, evidence)

        llm_test_case = LLMTestCase(
            input=question,
            actual_output=insight,
            expected_output=expected_answer,
            retrieval_context=analysis_context,
        )

        deepeval_test_cases.append(llm_test_case)
        case_metadata.append({
            "id": case_id,
            "category": case.get("category", ""),
            "question": question,
            "insight": insight,
            "expected_answer": expected_answer,
        })
        # Pacing between insight generations to conserve API quota
        time.sleep(2)

    # Step 2: Evaluate using DeepEval
    print("\n" + "=" * 80)
    print("--- STEP 2: RUNNING DEEPEVAL EVALUATION (Faithfulness & Answer Relevancy) ---")
    print("=" * 80)

    eval_result = evaluate(
        test_cases=deepeval_test_cases,
        metrics=[faithfulness_metric, relevancy_metric],
        async_config=AsyncConfig(
            run_async=True,
            throttle_value=1,
            max_concurrent=1,
        ),
    )

    # Step 3: Print detailed per-test reporting
    print("\n" + "=" * 80)
    print("PER-TEST DEEPEVAL RESULTS")
    print("=" * 80)

    faith_scores = []
    faith_passes = 0
    rel_scores = []
    rel_passes = 0
    overall_passes = 0

    for idx, (meta, t_res) in enumerate(zip(case_metadata, eval_result.test_results), 1):
        case_id = meta["id"]
        question = meta["question"]
        insight = meta["insight"]

        # Extract metric results
        case_faith_score = None
        case_faith_pass = False
        case_faith_reason = ""
        case_rel_score = None
        case_rel_pass = False
        case_rel_reason = ""

        for m_data in t_res.metrics_data:
            m_name_lower = m_data.name.lower()
            if "faithfulness" in m_name_lower:
                case_faith_score = m_data.score if m_data.score is not None else 0.0
                case_faith_pass = bool(m_data.success)
                case_faith_reason = m_data.reason or ""
            elif "relevancy" in m_name_lower or "relevance" in m_name_lower:
                case_rel_score = m_data.score if m_data.score is not None else 0.0
                case_rel_pass = bool(m_data.success)
                case_rel_reason = m_data.reason or ""

        if case_faith_score is not None:
            faith_scores.append(case_faith_score)
            if case_faith_pass:
                faith_passes += 1

        if case_rel_score is not None:
            rel_scores.append(case_rel_score)
            if case_rel_pass:
                rel_passes += 1

        case_all_passed = case_faith_pass and case_rel_pass
        if case_all_passed:
            overall_passes += 1

        print(f"\n--- [{idx}/{total_cases}] Test ID: {case_id} ({meta['category']}) ---")
        print(f"Question           : \"{question}\"")
        print(f"Generated Insight  : {insight}")
        print(f"Faithfulness score : {case_faith_score:.2f} | {'PASS' if case_faith_pass else 'FAIL'}")
        if case_faith_reason:
            print(f"  Reason           : {case_faith_reason}")
        print(f"Answer Relevancy   : {case_rel_score:.2f} | {'PASS' if case_rel_pass else 'FAIL'}")
        if case_rel_reason:
            print(f"  Reason           : {case_rel_reason}")
        print(f"Overall Test Result: {'PASS' if case_all_passed else 'FAIL'}")

    # Summary calculations
    avg_faith = sum(faith_scores) / len(faith_scores) if faith_scores else 0.0
    avg_rel = sum(rel_scores) / len(rel_scores) if rel_scores else 0.0
    pass_rate = (overall_passes / total_cases * 100) if total_cases > 0 else 0.0

    print("\n" + "=" * 50)
    print("FINAL INSIGHT DEEPEVAL SUMMARY")
    print("=" * 50)
    print(f"Total Test Cases        : {total_cases}")
    print(f"Faithfulness Passed     : {faith_passes}/{total_cases}")
    print(f"Faithfulness Average    : {avg_faith:.2f}")
    print(f"Answer Relevancy Passed : {rel_passes}/{total_cases}")
    print(f"Answer Relevancy Average: {avg_rel:.2f}")
    print(f"Overall Passed          : {overall_passes}/{total_cases}")
    print(f"Overall Pass Rate       : {pass_rate:.1f}%")
    print("=" * 50)

    # Return exit code 0 only if every test passes both metrics
    if overall_passes == total_cases:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    run_insight_deepeval()
