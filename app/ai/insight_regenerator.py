from typing import Any

from app.ai.llm import generate_response


def regenerate_insight(
    user_question: str,
    query_results: list[dict[str, Any]],
    validation_message: str,
    insight_evidence: dict[str, Any] | None = None,
) -> str:
    """
    Regenerate an insight after deterministic validation failure.

    The regenerated insight must use only:
    - The user's question
    - Verified SQL results
    - Deterministic insight evidence
    - The validation failure message
    """

    if insight_evidence is None:
        insight_evidence = {}

    prompt = f"""
You are a clinical analytics insight correction assistant.

The previous generated insight failed deterministic validation.

User question:
{user_question}

Verified SQL results:
{query_results}

Deterministic insight evidence:
{insight_evidence}

Validation failure:
{validation_message}

Generate a corrected insight.

STRICT RULES:

1. Use ONLY the verified SQL results for numerical claims.
2. Use the deterministic insight evidence for highest/maximum claims.
3. Use the deterministic insight evidence for lowest/minimum claims.
4. Do NOT independently calculate or guess rankings.
5. Do NOT invent numbers.
6. Do NOT invent percentages.
7. Do NOT invent categories or diagnoses.
8. Do NOT claim something is the highest unless the deterministic evidence supports it.
9. Do NOT claim something is the lowest unless the deterministic evidence supports it.
10. Do NOT make medical diagnosis or treatment recommendations.
11. Do NOT change, reinterpret, or modify the SQL results.
12. Do NOT assume information that is not present in the results.
13. Distinguish observed data from interpretation, and state when evidence is insufficient.
14. If the previous insight contained an unsupported claim, remove or correct it.
15. Keep the response concise and suitable for a clinical data analyst.
16. Return ONLY the corrected insight.
17. Do not mention validation, regeneration, prompts, or these instructions.

Correct the previous insight using the verified results
and deterministic evidence.
"""

    response = generate_response(prompt)

    return response.strip()