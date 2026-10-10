from typing import Optional, Any
from app.rag.retriever.langchain_retriever import create_retriever


def get_insight_context(
    user_question: str,
    analysis_plan: Optional[str] = None,
    clinical_plan: Optional[Any] = None,
    k: int = 2,
) -> str:
    retriever = create_retriever(k=k)

    # Ensure search_kwargs has the requested k
    retriever.search_kwargs["k"] = k

    query_parts = [user_question]

    # Clinical plan context enrichment
    if clinical_plan:
        if isinstance(clinical_plan, dict):
            q_type = clinical_plan.get("question_type")
            dataset = clinical_plan.get("primary_dataset")
            metric = clinical_plan.get("metric")
            explanation = clinical_plan.get("explanation")
        else:
            q_type = getattr(clinical_plan, "question_type", None)
            dataset = getattr(clinical_plan, "primary_dataset", None)
            metric = getattr(clinical_plan, "metric", None)
            explanation = getattr(clinical_plan, "explanation", None)

        clinical_hints = []
        if q_type and q_type != "unknown":
            clinical_hints.append(f"Domain: {q_type}")
        if dataset:
            clinical_hints.append(f"Dataset: {dataset.upper()}")
        if metric and metric != "none":
            clinical_hints.append(f"Metric: {metric}")
        if explanation:
            clinical_hints.append(str(explanation)[:200])

        if clinical_hints:
            query_parts.append(" | ".join(clinical_hints))

    if analysis_plan:
        # Augment with key plan requirements so relevant clinical context is retrieved
        query_parts.append(str(analysis_plan)[:400])

    query = "\n".join(query_parts)

    documents = retriever.invoke(query)

    if not documents:
        return "No relevant reference context was found."

    return "\n\n".join(
        document.page_content
        for document in documents
    )