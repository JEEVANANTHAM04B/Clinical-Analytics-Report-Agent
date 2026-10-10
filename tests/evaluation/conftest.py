"""
tests/evaluation/conftest.py
============================
Pytest configuration, shared fixtures, and DeepEval setup for the
Clinical Analytics Platform evaluation suite.
"""

import os
import sys
import json
import pytest
from pathlib import Path
from typing import Dict, Any, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.evaluation.metrics import (
    ClinicalCorrectnessMetric,
    SQLSafetyMetric,
    PipelineCompletenessMetric,
    EvidenceQualityMetric,
)
from tests.evaluation.fixtures.clinical_test_data import (
    SYNTHETIC_ADSL,
    SYNTHETIC_ADAE,
    SYNTHETIC_ADLB,
    SYNTHETIC_ADRESP,
    GROUND_TRUTH_KPIS,
)

EVAL_DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "clinical_eval_cases.json"


def pytest_addoption(parser):
    """Adds optional command-line flag to run LLM-as-a-judge DeepEval tests."""
    parser.addoption(
        "--run-deepeval-judge",
        action="store_true",
        default=False,
        help="Run DeepEval LLM-as-a-judge evaluation tests (requires GEMINI_API_KEY).",
    )


@pytest.fixture(scope="session")
def eval_dataset() -> List[Dict[str, Any]]:
    """Loads the master clinical evaluation dataset."""
    assert EVAL_DATASET_PATH.exists(), f"Evaluation dataset not found at {EVAL_DATASET_PATH}"
    with open(EVAL_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def synthetic_data() -> Dict[str, Any]:
    """Provides synthetic clinical datasets and ground truth KPIs."""
    return {
        "adsl": SYNTHETIC_ADSL,
        "adae": SYNTHETIC_ADAE,
        "adlb": SYNTHETIC_ADLB,
        "adresp": SYNTHETIC_ADRESP,
        "ground_truth": GROUND_TRUTH_KPIS,
    }


@pytest.fixture(scope="session")
def correctness_metric() -> ClinicalCorrectnessMetric:
    return ClinicalCorrectnessMetric(tolerance=0.05)


@pytest.fixture(scope="session")
def sql_safety_metric() -> SQLSafetyMetric:
    return SQLSafetyMetric()


@pytest.fixture(scope="session")
def pipeline_metric() -> PipelineCompletenessMetric:
    return PipelineCompletenessMetric()


@pytest.fixture(scope="session")
def evidence_metric() -> EvidenceQualityMetric:
    return EvidenceQualityMetric()


@pytest.fixture(scope="session")
def deepeval_gemini_judge():
    """
    Returns a rate-limited Gemini model for DeepEval evaluation.
    Skips if GEMINI_API_KEY is not available.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY / GOOGLE_API_KEY not configured. Skipping LLM-judge tests.")

    from deepeval.models import GeminiModel
    try:
        # Use active gemini-3.1-flash-lite as judge
        model_name = os.getenv("DEEPEVAL_JUDGE_MODEL", "gemini-3.1-flash-lite")
        return GeminiModel(model=model_name, api_key=api_key)
    except Exception as e:
        pytest.skip(f"Failed to initialize GeminiModel judge: {e}")
