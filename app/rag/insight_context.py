from typing import Optional
from app.rag.retriever.langchain_retriever import create_retriever


def get_insight_context(
    user_question: str,
    analysis_plan: Optional[str] = None,
    k: int = 2,
) -> str:
    retriever = create_retriever()

    # Override the default k=1 used by the existing retriever.
    retriever.search_kwargs["k"] = k

    query = user_question
    if analysis_plan:
        # Augment with key plan requirements so relevant clinical context is retrieved
        # even if human feedback updated the analysis scope (e.g. encounter class vs diagnosis)
        query = f"{user_question}\n{analysis_plan[:400]}"

    documents = retriever.invoke(query)

    if not documents:
        return "No relevant reference context was found."

    return "\n\n".join(
        document.page_content
        for document in documents
    )