from typing import Any

from app.ai.llm import generate_response


def _deterministic_insight_fallback(
    user_question: str,
    query_results: list[dict[str, Any]],
    insight_evidence: dict[str, Any],
) -> str | None:
    """
    Generate an insight directly from verified query results and
    deterministic evidence when the LLM is temporarily unavailable.
    """

    question = user_question.lower()

    if (
        "average length of stay" not in question
        or "diagnosis" not in question
    ):
        return None

    if not query_results:
        return "No verified results were returned for the requested analysis."

    maximum = insight_evidence.get("maximum")
    minimum = insight_evidence.get("minimum")

    if not maximum or not minimum:
        return None

    row_count = insight_evidence.get(
        "row_count",
        len(query_results),
    )

    max_category = maximum.get("category")
    max_value = maximum.get("value")

    min_value = minimum.get("value")
    min_categories = minimum.get("categories", [])

    dimension = "encounter classes" if any("encounter" in k.lower() for k in query_results[0].keys()) else "categories"

    insight = (
        f"Based on the clinical dataset covering {row_count} {dimension}, "
        f"the highest average length of stay was "
        f"{max_category} at {max_value:.4f} days. "
    )

    if len(min_categories) == 1:
        insight += (
            f"The lowest average length of stay was "
            f"{min_value:.4f} days for {min_categories[0]}."
        )
    else:
        insight += (
            f"The lowest average length of stay was "
            f"{min_value:.4f} days across multiple {dimension}."
        )

    return insight


def generate_insight(
    user_question: str,
    query_results: list[dict[str, Any]],
    rag_context: str = "",
    insight_evidence: dict[str, Any] | None = None,
) -> str:
    """
    Generate a clinical analytics insight using:

    1. Verified SQL results
    2. RAG reference context
    3. Deterministically calculated evidence

    The LLM is responsible for explaining the evidence,
    not independently calculating rankings.

    If the LLM is temporarily unavailable, a deterministic
    fallback is used for supported analytics patterns.
    """

    if insight_evidence is None:
        insight_evidence = {}

    prompt = f"""
You are a clinical analytics insight assistant.

Answer the user's question using ONLY:
1. The verified SQL results.
2. The provided reference context.
3. The deterministic insight evidence.

User question:
{user_question}

Verified SQL results:
{query_results}

Deterministic insight evidence:
{insight_evidence}

Reference context:
{rag_context}

Rules:
- Do not invent statistics or values.
- Do not invent categories.
- Do not calculate rankings yourself.
- For highest/maximum claims, use the deterministic insight evidence.
- For lowest/minimum claims, use the deterministic insight evidence.
- Use only verified SQL results for numerical claims.
- Use the deterministic evidence when stating maximum or minimum values.
- Use the reference context only for definitions or supporting knowledge.
- Clearly mention important patterns supported by the verified results.
- If the results contain NULL or missing categories, mention this when relevant.
- Do not provide medical diagnosis or treatment recommendations.
- Do not make claims that are not supported by the supplied evidence.
- Keep the answer concise and suitable for a clinical data analyst.
- Return only the final insight text.
"""

    try:
        return generate_response(prompt)

    except RuntimeError as error:
        print(
            "LLM insight generation unavailable. "
            "Checking deterministic insight fallback..."
        )

        fallback_insight = _deterministic_insight_fallback(
            user_question=user_question,
            query_results=query_results,
            insight_evidence=insight_evidence,
        )

        if fallback_insight is not None:
            print("Using deterministic insight fallback.")
            return fallback_insight

        raise error