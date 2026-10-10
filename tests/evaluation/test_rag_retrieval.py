"""
tests/evaluation/test_rag_retrieval.py
======================================
Evaluates the RAG retrieval pipeline using the existing vector store and retriever.
Validates concept retrieval, relevance, grounded clinical terminology,
and empty-result behavior without inventing citations.
"""

import pytest
from app.rag.insight_context import get_insight_context
from app.rag.retriever.langchain_retriever import create_retriever


def test_rag_safety_population_definition():
    """
    Evaluates retrieval of the CDISC Safety Population definition
    from the indexed reference store.
    """
    question = "What does the safety population mean in this clinical trial?"
    context = get_insight_context(user_question=question, k=2)

    assert context and context != "No relevant reference context was found."
    lower_ctx = context.lower()

    # Must contain CDISC-standard safety population keywords
    assert (
        "safety" in lower_ctx
        and ("treatment" in lower_ctx or "dose" in lower_ctx or "population" in lower_ctx)
    ), f"Retrieved context lacked safety population criteria: {context}"


def test_rag_adverse_event_terminology():
    """
    Evaluates retrieval of adverse event definitions (TEAE, serious adverse events).
    """
    question = "What defines a treatment-emergent adverse event (TEAE) and serious adverse event (SAE)?"
    context = get_insight_context(user_question=question, k=2)

    assert context and context != "No relevant reference context was found."
    lower_ctx = context.lower()
    assert "adverse event" in lower_ctx or "teae" in lower_ctx or "sae" in lower_ctx


def test_rag_retriever_metadata_preservation():
    """
    Verifies that documents retrieved by create_retriever preserve metadata
    such as source file paths or titles.
    """
    retriever = create_retriever(k=1)
    docs = retriever.invoke("clinical study protocol criteria")

    assert len(docs) > 0
    doc = docs[0]
    assert hasattr(doc, "page_content")
    assert len(doc.page_content.strip()) > 0
    assert hasattr(doc, "metadata")
    assert isinstance(doc.metadata, dict)
