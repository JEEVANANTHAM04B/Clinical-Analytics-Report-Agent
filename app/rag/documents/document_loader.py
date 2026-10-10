"""
app/rag/documents/document_loader.py
====================================
Loads clinical knowledge documents and splits them into semantically rich,
metadata-annotated chunks for vector indexing and context retrieval.
"""

from pathlib import Path
from typing import List, Dict, Any

from langchain_core.documents import Document


DOCUMENTS_DIR = Path(__file__).resolve().parent
PRIMARY_DOCUMENT_PATH = DOCUMENTS_DIR / "cdisc_clinical_trial_reference.txt"
FALLBACK_DOCUMENT_PATH = DOCUMENTS_DIR / "clinical_reference.txt"


def classify_chunk_metadata(paragraph: str, source_name: str) -> Dict[str, Any]:
    """
    Classifies a knowledge paragraph into structured clinical trial metadata.
    """
    p_lower = paragraph.lower()

    domain = "clinical_trial"
    standard = "CDISC"
    dataset = "General"
    topic = "Clinical Trial Fundamentals"

    if any(k in p_lower for k in ["serious adverse event", "aeser"]):
        topic = "Serious Adverse Events"
        dataset = "AE / ADAE"
        standard = "ICH / CDISC"
    elif any(k in p_lower for k in ["treatment-emergent", "trtemfl"]):
        topic = "Treatment-Emergent Adverse Events"
        dataset = "ADAE"
        standard = "CDISC"
    elif any(k in p_lower for k in ["adverse event rate", "incidence rate"]):
        topic = "Adverse Event Rate"
        dataset = "ADAE / ADSL"
        standard = "CDISC"
    elif any(k in p_lower for k in ["adverse event", "aedecod", "aebodsys", "aesev", "aerel"]):
        topic = "Adverse Events & Safety"
        dataset = "AE / ADAE"
        standard = "CDISC"
    elif "meddra" in p_lower:
        topic = "Medical Dictionary (MedDRA)"
        dataset = "AE / ADAE"
        standard = "MedDRA / ICH"
    elif any(k in p_lower for k in ["safety analysis population", "saffl"]):
        topic = "Safety Population"
        dataset = "ADSL"
        standard = "ICH E9 / CDISC"
    elif any(k in p_lower for k in ["intent-to-treat", "ittfl", "full analysis set"]):
        topic = "Analysis Populations"
        dataset = "ADSL"
        standard = "ICH E9 / CDISC"
    elif any(k in p_lower for k in ["subject-level analysis dataset", "adsl"]):
        topic = "Subject-Level Dataset (ADSL)"
        dataset = "ADSL"
        standard = "CDISC ADaM"
    elif any(k in p_lower for k in ["demographics", "dm domain"]):
        topic = "Demographics"
        dataset = "DM"
        standard = "CDISC SDTM"
    elif any(k in p_lower for k in ["unique subject identifier", "usubjid"]):
        topic = "Subject Identifier (USUBJID)"
        dataset = "All Domains"
        standard = "CDISC"
    elif any(k in p_lower for k in ["laboratory analysis dataset", "adlb"]):
        topic = "Laboratory Analysis (ADLB)"
        dataset = "ADLB"
        standard = "CDISC ADaM"
    elif any(k in p_lower for k in ["change from baseline", "baseline value", "chg", "base"]):
        topic = "Change from Baseline"
        dataset = "ADLB / ADVS"
        standard = "CDISC ADaM"
    elif any(k in p_lower for k in ["clinical laboratory", "lb domain", "loinc"]):
        topic = "Laboratory Assessments"
        dataset = "LB"
        standard = "CDISC SDTM / LOINC"
    elif any(k in p_lower for k in ["vital signs", "advs", "vs domain"]):
        topic = "Vital Signs"
        dataset = "VS / ADVS"
        standard = "CDISC"
    elif any(k in p_lower for k in ["responder flag", "respfl", "efficacy response rate"]):
        topic = "Efficacy Responder Analysis"
        dataset = "ADRESP"
        standard = "CDISC ADaM"
    elif any(k in p_lower for k in ["efficacy response analysis dataset", "adresp"]):
        topic = "Efficacy Endpoints (ADRESP)"
        dataset = "ADRESP"
        standard = "CDISC ADaM"
    elif any(k in p_lower for k in ["analysis visits", "avisit", "visit"]):
        topic = "Visit Structure (AVISIT)"
        dataset = "All Longitudinal"
        standard = "CDISC"
    elif any(k in p_lower for k in ["treatment arms & randomization", "trt01a", "arm"]):
        topic = "Treatment Arms & Randomization"
        dataset = "DM / ADSL"
        standard = "CDISC"
    elif any(k in p_lower for k in ["investigator sites", "siteid", "sites"]):
        topic = "Investigator Sites & Enrollment"
        dataset = "SITES"
        standard = "ICH GCP / CDISC"
    elif any(k in p_lower for k in ["protocol & study management", "study table", "studyid"]):
        topic = "Study Protocol & Objectives"
        dataset = "STUDY"
        standard = "CDISC"
    elif any(k in p_lower for k in ["sdtm vs adam", "sdtm", "adam"]):
        topic = "CDISC Standards Architecture"
        dataset = "SDTM / ADaM"
        standard = "CDISC"
    elif any(k in p_lower for k in ["ich e6", "good clinical practice", "gcp"]):
        topic = "Good Clinical Practice (GCP)"
        dataset = "Governance"
        standard = "ICH E6(R2)"
    elif any(k in p_lower for k in ["ich e9", "statistical principles"]):
        topic = "Statistical Principles"
        dataset = "Biostatistics"
        standard = "ICH E9"
    elif any(k in p_lower for k in ["21 cfr part 11", "fda"]):
        topic = "Electronic Records & Compliance"
        dataset = "Regulatory"
        standard = "FDA 21 CFR 11"
    elif any(k in p_lower for k in ["length of stay", "inpatient encounter", "readmission"]):
        domain = "ehr"
        standard = "Hospital EHR"
        dataset = "Encounters"
        topic = "Hospital Inpatient Operations"

    return {
        "source": source_name,
        "document_type": "clinical_reference",
        "domain": domain,
        "standard": standard,
        "dataset": dataset,
        "topic": topic,
    }


def load_documents() -> List[Document]:
    """
    Loads clinical documents from the documents directory.
    Prioritizes CDISC clinical trial reference and loads available knowledge texts.
    """
    documents: List[Document] = []
    seen_files = set()

    # Load primary CDISC clinical trial reference
    target_files = [PRIMARY_DOCUMENT_PATH, FALLBACK_DOCUMENT_PATH]

    for p in target_files:
        if p.exists() and p.name not in seen_files:
            text = p.read_text(encoding="utf-8")
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": p.name,
                        "document_type": "clinical_reference",
                    },
                )
            )
            seen_files.add(p.name)

    # Fallback to any .txt file in the directory
    if not documents:
        for p in DOCUMENTS_DIR.glob("*.txt"):
            if not p.name.endswith(".bak"):
                text = p.read_text(encoding="utf-8")
                documents.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": p.name,
                            "document_type": "clinical_reference",
                        },
                    )
                )

    return documents


def split_documents(documents: List[Document]) -> List[Document]:
    """
    Splits multi-paragraph clinical documents into discrete, semantically
    coherent paragraphs annotated with rich domain and topic metadata.
    """
    chunks: List[Document] = []
    seen_content = set()

    for doc in documents:
        source_name = doc.metadata.get("source", "clinical_reference.txt")
        raw_paragraphs = doc.page_content.split("\n\n")

        for paragraph in raw_paragraphs:
            cleaned = paragraph.strip()
            if not cleaned or len(cleaned) < 20:
                continue

            # Deduplicate identical paragraphs if multiple source files share chunks
            if cleaned in seen_content:
                continue
            seen_content.add(cleaned)

            meta = classify_chunk_metadata(cleaned, source_name)
            chunks.append(Document(page_content=cleaned, metadata=meta))

    return chunks


if __name__ == "__main__":
    docs = load_documents()
    chk = split_documents(docs)
    print(f"Loaded {len(docs)} documents, produced {len(chk)} unique chunks.")
    for i, c in enumerate(chk[:3], 1):
        print(f"\nChunk {i}: {c.page_content[:80]}...")
        print(f"Metadata: {c.metadata}")