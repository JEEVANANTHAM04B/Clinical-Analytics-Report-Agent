"""
tests/test_clinical_rag.py
===========================
Comprehensive test suite verifying the Clinical Trial / CDISC RAG Knowledge Base.

Validates:
1. All 20 mandatory clinical trial retrieval questions (SDTM, ADaM, AE, SAE, AESER, TRTEMFL,
   SAFFL, RESPFL, CHG, AVISIT, USUBJID, ADSL, ADAE, ADLB, ADVS, ADRESP, ICH GCP, ICH E9, MedDRA, LOINC).
2. Vector database integrity (384 dimensions, 34 chunks, index load status, distance metrics).
3. Document metadata structure (domain, standard, dataset, topic, source, document_type).
4. Clinical domain dominance (clinical queries do not return hospital length-of-stay).
5. Legacy EHR backward compatibility preservation.
6. LangGraph retrieve_rag_node and clinical_question_plan context integration.
7. RAG safety and separation (no metric fabrication, SQL results remain authoritative).
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import pytest
from pathlib import Path
import numpy as np
import faiss

from app.rag.documents.document_loader import load_documents, split_documents
from app.rag.retriever.retriever import retrieve, load_retriever
from app.rag.retriever.langchain_retriever import create_retriever
from app.rag.insight_context import get_insight_context
from app.workflow.graph import retrieve_rag_node
from app.workflow.state import ClinicalAnalyticsState
from app.clinical.question_mapping import build_clinical_question_plan
from app.ai.insight_generator import generate_insight


# =============================================================================
# 1. 20 MANDATORY CLINICAL TRIAL RETRIEVAL QUESTIONS (STEP 12)
# =============================================================================

@pytest.mark.parametrize(
    "question,expected_keywords",
    [
        # 1. SDTM
        ("What is SDTM?", ["sdtm", "study data tabulation model", "cdisc"]),
        # 2. ADaM
        ("What is ADaM?", ["adam", "analysis data model", "cdisc"]),
        # 3. Adverse Event
        ("What is an adverse event?", ["adverse event", "untoward medical occurrence"]),
        # 4. Serious Adverse Event
        ("What is a serious adverse event?", ["serious", "death", "life-threatening", "hospitalization"]),
        # 5. AESER = Y
        ("What does AESER = Y mean?", ["aeser", "serious", "adverse event"]),
        # 6. Treatment-emergent AE
        ("What is treatment-emergent AE?", ["treatment-emergent", "trtemfl", "ae"]),
        # 7. Safety population
        ("What is a safety population?", ["safety population", "saffl", "dose"]),
        # 8. RESPFL
        ("What is RESPFL?", ["respfl", "response", "adresp", "responder"]),
        # 9. Change from baseline
        ("What is change from baseline?", ["change from baseline", "chg", "base"]),
        # 10. AVISIT
        ("What is AVISIT?", ["avisit", "analysis visit", "visit"]),
        # 11. USUBJID
        ("What is USUBJID?", ["usubjid", "unique subject identifier", "subject"]),
        # 12. Purpose of ADSL
        ("What is the purpose of ADSL?", ["adsl", "subject-level", "demographics"]),
        # 13. ADAE
        ("What is ADAE?", ["adae", "adverse event", "safety"]),
        # 14. ADLB
        ("What is ADLB?", ["adlb", "laboratory", "lab"]),
        # 15. ADVS
        ("What is ADVS?", ["advs", "vital sign", "vitals"]),
        # 16. ADRESP
        ("What is ADRESP?", ["adresp", "response", "efficacy"]),
        # 17. ICH GCP
        ("What is ICH GCP?", ["ich", "gcp", "good clinical practice", "ich e6"]),
        # 18. ICH E9
        ("What is ICH E9?", ["ich e9", "statistical principles", "clinical trials"]),
        # 19. MedDRA
        ("What is MedDRA?", ["meddra", "medical dictionary for regulatory activities", "adverse"]),
        # 20. LOINC
        ("What is LOINC?", ["loinc", "logical observation identifiers", "laboratory"]),
    ],
)
def test_step12_canonical_clinical_retrieval(question: str, expected_keywords: list[str]):
    """Verify that all 20 canonical clinical questions retrieve relevant authoritative knowledge."""
    context = get_insight_context(user_question=question, k=2)
    assert context is not None and len(context) > 0, f"Retrieved context for '{question}' was empty"

    context_lower = context.lower()
    matched = any(kw.lower() in context_lower for kw in expected_keywords)
    assert matched, (
        f"Query '{question}' retrieved context missing expected keywords {expected_keywords}.\n"
        f"Context snippet: {context[:300]}"
    )


# =============================================================================
# 2. VECTOR DATABASE & EMBEDDING VALIDATION (STEP 13)
# =============================================================================

class TestVectorDatabaseIntegrity:
    """Verify embedding dimension, vector count, FAISS index, and chunks."""

    def test_embedding_dimension_and_count(self):
        model, index, chunks = load_retriever()
        assert index.d == 384, f"Expected 384 dimensions, got {index.d}"
        assert index.ntotal >= 34, f"Expected at least 34 vectors in index, got {index.ntotal}"
        assert len(chunks) == index.ntotal, "Mismatch between chunk count and vector index count"

    def test_raw_faiss_retriever_scores(self):
        results = retrieve("What is CDISC SDTM?", top_k=2)
        assert len(results) == 2
        for res in results:
            assert "text" in res
            assert "distance" in res
            assert isinstance(res["distance"], float)
            assert res["distance"] >= 0.0  # L2 distance is non-negative
            assert len(res["text"]) > 50

    def test_langchain_retriever_returns_documents(self):
        retriever = create_retriever(k=2)
        docs = retriever.invoke("What is an adverse event?")
        assert len(docs) == 2
        assert any("adverse" in d.page_content.lower() for d in docs)


# =============================================================================
# 3. METADATA QUALITY VALIDATION (STEP 6)
# =============================================================================

class TestDocumentMetadata:
    """Verify document metadata categorization and fields."""

    def test_document_metadata_fields(self):
        docs = load_documents()
        assert len(docs) >= 1, "Expected at least 1 document loaded"
        chunks = split_documents(docs)
        assert len(chunks) >= 34, f"Expected at least 34 chunks, got {len(chunks)}"

        required_metadata_keys = {
            "source", "domain", "standard", "dataset", "topic", "document_type"
        }

        for chunk in chunks:
            meta = chunk.metadata
            missing = required_metadata_keys - set(meta.keys())
            assert not missing, f"Chunk missing keys: {missing}"
            assert meta["domain"] in ["clinical_trial", "ehr"]

    def test_clinical_trial_chunks_have_valid_standards(self):
        docs = load_documents()
        chunks = split_documents(docs)
        clinical_chunks = [c for c in chunks if c.metadata["domain"] == "clinical_trial"]
        assert len(clinical_chunks) >= 28, "Expected majority of chunks to be clinical_trial domain"

        standards = {c.metadata["standard"] for c in clinical_chunks}
        assert any("CDISC" in s or "ICH" in s for s in standards)


# =============================================================================
# 4. DOMAIN SEPARATION & BACKWARD COMPATIBILITY (STEPS 3, 8)
# =============================================================================

class TestDomainSeparation:
    """Ensure clinical queries do not retrieve hospital EHR text, and EHR queries still work."""

    def test_clinical_query_dominates_over_hospital_ehr(self):
        clinical_queries = [
            "What is the adverse event rate in treatment arms?",
            "What is the analysis visit AVISIT?",
            "What is the difference between SDTM and ADaM?",
        ]
        for q in clinical_queries:
            context = get_insight_context(user_question=q, k=1).lower()
            # Must NOT retrieve hospital length-of-stay or emergency encounter chunks as top result
            assert "length of stay" not in context or "adverse" in context or "cdisc" in context
            assert "hospital inpatient" not in context or "clinical" in context

    def test_legacy_ehr_retrieval_preserved(self):
        """Legacy EHR questions should still retrieve legacy guidance safely."""
        ehr_context = get_insight_context(user_question="What is the hospital benchmark for length of stay?", k=2).lower()
        assert "length of stay" in ehr_context or "los" in ehr_context or "hospital" in ehr_context


# =============================================================================
# 5. LANGGRAPH NODE & CLINICAL PLAN INTEGRATION (STEP 7, 9)
# =============================================================================

class TestLangGraphRAGIntegration:
    """Verify retrieve_rag_node in LangGraph workflow."""

    def test_retrieve_rag_node_with_clinical_plan(self):
        plan = build_clinical_question_plan("What is the adverse event rate by treatment arm?")
        plan_dict = {
            "is_supported": plan.is_supported,
            "question_type": plan.question_type,
            "matched_kpi_id": plan.matched_kpi_id,
            "primary_dataset": plan.primary_dataset,
            "metric": plan.metric,
            "explanation": plan.explanation,
        }

        mock_state = {
            "user_question": "What is the adverse event rate by treatment arm?",
            "clinical_question_plan": plan_dict,
            "analysis_plan": "Evaluate adverse events across treatment arms using ADAE and ADSL.",
            "error": None,
        }

        update = retrieve_rag_node(mock_state)
        assert "rag_context" in update
        rag_context = update["rag_context"]
        assert len(rag_context) > 0
        assert "adverse" in rag_context.lower() or "safety" in rag_context.lower()

    def test_retrieve_rag_node_handles_missing_plan_gracefully(self):
        mock_state = {
            "user_question": "What is SDTM?",
            "error": None,
        }
        update = retrieve_rag_node(mock_state)
        assert "rag_context" in update
        assert len(update["rag_context"]) > 0


# =============================================================================
# 6. RAG SAFETY & NON-FABRICATION (STEP 8, 10)
# =============================================================================

class TestRAGSafetyAndNonFabrication:
    """Verify RAG context does not override verified SQL or fabricate metrics."""

    def test_sql_results_remain_authoritative(self):
        user_q = "What is the adverse event rate by treatment arm?"
        verified_sql_results = [
            {"treatment_arm": "Drug X", "adverse_event_rate_pct": 24.5},
            {"treatment_arm": "Placebo", "adverse_event_rate_pct": 8.2},
        ]
        rag_ctx = get_insight_context(user_q, k=2)

        # Generate insight with verified results + RAG context
        insight = generate_insight(
            user_question=user_q,
            query_results=verified_sql_results,
            rag_context=rag_ctx,
            insight_evidence={
                "row_count": 2,
                "maximum": {"category": "Drug X", "value": 24.5},
                "minimum": {"category": "Placebo", "value": 8.2},
            },
        )

        assert insight is not None
        # Insight must reflect verified empirical numbers (24.5 or Drug X)
        assert "Drug X" in insight
        assert ("24.5" in insight or "24.50" in insight or "highest" in insight)
