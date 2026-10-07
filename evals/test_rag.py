
import json
from pathlib import Path

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    
from deepeval import evaluate
from deepeval.evaluate.configs import AsyncConfig
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase
from deepeval.models import GeminiModel

from app.rag.retriever.retriever import retrieve
from app.ai.llm import generate_response


BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "datasets" / "rag_test_cases.json"


def load_test_cases():
    with open(DATASET_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def build_answer(question: str, retrieved_context: str) -> str:
    prompt = f"""
You are a clinical analytics knowledge assistant.

Answer the user's question using only the provided reference context.

Question:
{question}

Reference context:
{retrieved_context}

Rules:
- Do not invent information.
- Do not provide medical diagnosis or treatment.
- Use only the supplied reference context.
- Keep the answer concise.
"""

    return generate_response(prompt)


def test_rag_evaluation():

    test_cases = load_test_cases()
    deepeval_cases = []

    for case in test_cases:

        question = case["question"]

        retrieved = retrieve(
            question,
            top_k=1,
        )

        retrieved_context = [
            item["text"]
            for item in retrieved
        ]

        context_text = "\n\n".join(
            retrieved_context
        )

        actual_answer = build_answer(
            question,
            context_text,
        )

        test_case = LLMTestCase(
            input=question,
            actual_output=actual_answer,
            retrieval_context=retrieved_context,
        )

        deepeval_cases.append(test_case)

        print("\n" + "=" * 70)
        print("QUESTION:")
        print(question)

        print("\nRETRIEVED CONTEXT:")
        print(context_text)

        print("\nACTUAL ANSWER:")
        print(actual_answer)

        print("=" * 70)

    evaluator_model = GeminiModel(
        model="gemini-3.5-flash-lite",
    )

    evaluate(
        test_cases=deepeval_cases,
        metrics=[
            AnswerRelevancyMetric(
                threshold=0.7,
                include_reason=True,
                model=evaluator_model,
            )
        ],
        async_config=AsyncConfig(
            run_async=True,
            throttle_value=1,
            max_concurrent=1,
        ),
    )


if __name__ == "__main__":
    test_rag_evaluation()