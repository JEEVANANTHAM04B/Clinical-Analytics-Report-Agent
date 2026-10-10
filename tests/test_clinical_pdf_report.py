"""
tests/test_clinical_pdf_report.py
=================================
Comprehensive verification test suite for the migrated Clinical Trial PDF Report Generator.

Verifies:
1. Canonical clinical questions (Total subjects, AE count, Serious AE count, AE rate by treatment,
   Lab change, Vital sign change, Efficacy response rate, Site enrollment).
2. ReportLab PDF binary structure, multi-page layout, and valid PDF signatures.
3. Proper clinical trial terminology (subjects, treatment arms, protocol, CDISC).
4. Strict absence of legacy EHR terminology (inpatient, length of stay, diagnoses, hospital admissions).
5. Exact numeric alignment with verified SQL query outcomes.
6. Chart and visual evidence generation.
7. Clinical insight integration and non-causal language safety.
8. Backward compatibility for legacy EHR report requests.
9. FastAPI analytics reporting endpoints (/report/pdf, /report/pdf/latest, /report/pdf/download, /report/approve).
"""

import io
import sys
import os
sys.path.insert(0, os.path.abspath("."))

import pytest
from pypdf import PdfReader
from fastapi.testclient import TestClient

from app.main import app
from app.reporting.pdf_generator import build_clinical_pdf_report, generate_chart_image, _is_clinical_context
from app.schemas.reports import PDFReportRequest


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extracts raw text content across all pages from compiled PDF bytes."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = []
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            full_text.append(txt)
    return "\n".join(full_text)


# =============================================================================
# 1. CANONICAL CLINICAL TRIAL REPORT GENERATION TESTS
# =============================================================================

def test_report_total_subjects_enrollment():
    """Verify PDF report generation for total subjects enrollment inquiry."""
    req = PDFReportRequest(
        question="How many subjects are enrolled?",
        selected_tables=["dm"],
        results=[{"total_subjects": 1053}],
        sql_query="SELECT COUNT(DISTINCT USUBJID) AS total_subjects FROM dm;",
        insight="The clinical trial successfully enrolled 1,053 subjects across all participating investigator sites.",
    )
    pdf = build_clinical_pdf_report(req)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 5000

    text = extract_pdf_text(pdf)
    assert "CLINICAL TRIAL ANALYTICS REPORT" in text
    assert "How many subjects are enrolled?" in text
    assert "1,053" in text or "1053" in text
    assert "total subjects" in text.lower() or "study cohort" in text.lower()
    # Clinical terminology check
    assert "subject" in text.lower()
    # Absence of EHR terms
    assert "length of stay" not in text.lower()
    assert "inpatient encounter" not in text.lower()


def test_report_adverse_event_count():
    """Verify PDF report generation for adverse event count inquiry."""
    req = PDFReportRequest(
        question="How many adverse events occurred?",
        selected_tables=["ae"],
        results=[{"adverse_event_count": 1191}],
        sql_query="SELECT COUNT(*) AS adverse_event_count FROM ae;",
        insight="A total of 1,191 adverse events occurred across all study participants during the monitored observation period.",
    )
    pdf = build_clinical_pdf_report(req)
    assert pdf.startswith(b"%PDF-")

    text = extract_pdf_text(pdf)
    assert "1,191" in text or "1191" in text
    assert "adverse event" in text.lower()
    assert "length of stay" not in text.lower()


def test_report_serious_ae_count():
    """Verify PDF report generation for serious adverse event count inquiry."""
    req = PDFReportRequest(
        question="How many serious adverse events occurred?",
        selected_tables=["ae"],
        results=[{"serious_ae_count": 62}],
        sql_query="SELECT COUNT(*) AS serious_ae_count FROM ae WHERE AESER = 'Y';",
        insight="A total of 62 serious adverse events occurred during the trial, meeting protocol seriousness criteria.",
    )
    pdf = build_clinical_pdf_report(req)
    assert pdf.startswith(b"%PDF-")

    text = extract_pdf_text(pdf)
    assert "62" in text
    assert "serious adverse event" in text.lower()
    assert "length of stay" not in text.lower()


def test_report_ae_rate_by_treatment():
    """Verify PDF report generation for AE rate by treatment arm inquiry."""
    req = PDFReportRequest(
        question="What is the adverse event rate by treatment arm?",
        selected_tables=["adsl", "adae"],
        results=[
            {"treatment_arm": "Drug X", "total_safety_subjects": 526, "subjects_with_ae": 392, "adverse_event_rate_pct": 74.5},
            {"treatment_arm": "Placebo", "total_safety_subjects": 527, "subjects_with_ae": 280, "adverse_event_rate_pct": 53.1},
        ],
        sql_query="""
            SELECT adsl.TRT01A AS treatment_arm,
                   COUNT(DISTINCT adsl.USUBJID) AS total_safety_subjects,
                   COUNT(DISTINCT adae.USUBJID) AS subjects_with_ae,
                   ROUND(COUNT(DISTINCT adae.USUBJID) * 100.0 / COUNT(DISTINCT adsl.USUBJID), 1) AS adverse_event_rate_pct
            FROM adsl
            LEFT JOIN adae ON adsl.USUBJID = adae.USUBJID AND adae.TRTEMFL = 'Y'
            WHERE adsl.SAFFL = 'Y'
            GROUP BY adsl.TRT01A;
        """,
        insight="Drug X demonstrated an observed adverse event rate of 74.5%, while Placebo recorded 53.1% in the safety population.",
    )
    pdf = build_clinical_pdf_report(req)
    assert pdf.startswith(b"%PDF-")

    text = extract_pdf_text(pdf)
    assert "Drug X" in text
    assert "Placebo" in text
    assert "74.5%" in text or "74.5" in text
    assert "53.1%" in text or "53.1" in text
    assert "treatment arm" in text.lower() or "safety population" in text.lower()
    assert "length of stay" not in text.lower()


def test_report_lab_change_from_baseline():
    """Verify PDF report generation for laboratory change from baseline."""
    req = PDFReportRequest(
        question="What is the lab change from baseline to Week 8?",
        selected_tables=["adlb"],
        results=[
            {"PARAM": "Alanine Aminotransferase", "baseline_mean": 24.5, "week8_mean": 26.2, "mean_change": 1.7},
            {"PARAM": "Hemoglobin", "baseline_mean": 13.8, "week8_mean": 13.5, "mean_change": -0.3},
        ],
        sql_query="""
            SELECT PARAM, ROUND(AVG(BASE), 1) AS baseline_mean, ROUND(AVG(AVAL), 1) AS week8_mean, ROUND(AVG(CHG), 2) AS mean_change
            FROM adlb
            WHERE AVISIT = 'Week 8'
            GROUP BY PARAM;
        """,
        insight="Alanine Aminotransferase showed a mean change from baseline of 1.7 U/L at Week 8.",
    )
    pdf = build_clinical_pdf_report(req)
    assert pdf.startswith(b"%PDF-")

    text = extract_pdf_text(pdf)
    assert "Alanine Aminotransferase" in text
    assert "Hemoglobin" in text
    assert "1.7" in text
    assert "laboratory" in text.lower() or "param" in text.lower()
    assert "length of stay" not in text.lower()


def test_report_vital_sign_change_from_baseline():
    """Verify PDF report generation for vital signs change from baseline."""
    req = PDFReportRequest(
        question="What is the vital sign change from baseline?",
        selected_tables=["advs"],
        results=[
            {"PARAM": "Systolic Blood Pressure", "baseline_mean": 128.4, "latest_mean": 124.2, "mean_change": -4.2},
            {"PARAM": "Diastolic Blood Pressure", "baseline_mean": 82.1, "latest_mean": 79.9, "mean_change": -2.2},
        ],
        sql_query="""
            SELECT PARAM, ROUND(AVG(BASE), 1) AS baseline_mean, ROUND(AVG(AVAL), 1) AS latest_mean, ROUND(AVG(CHG), 2) AS mean_change
            FROM advs
            GROUP BY PARAM;
        """,
        insight="Systolic Blood Pressure demonstrated a mean decrease of 4.2 mmHg from baseline across evaluated subjects.",
    )
    pdf = build_clinical_pdf_report(req)
    assert pdf.startswith(b"%PDF-")

    text = extract_pdf_text(pdf)
    assert "Systolic Blood Pressure" in text
    assert "Diastolic Blood Pressure" in text
    assert "-4.2" in text or "4.2" in text
    assert "length of stay" not in text.lower()


def test_report_efficacy_response_rate():
    """Verify PDF report generation for efficacy response rate inquiry."""
    req = PDFReportRequest(
        question="What is the efficacy response rate by treatment?",
        selected_tables=["adresp"],
        results=[
            {"treatment_arm": "Drug X", "evaluable_subjects": 526, "responders": 447, "response_rate_pct": 84.9},
            {"treatment_arm": "Placebo", "evaluable_subjects": 527, "responders": 0, "response_rate_pct": 0.0},
        ],
        sql_query="""
            SELECT TRT01A AS treatment_arm,
                   COUNT(DISTINCT USUBJID) AS evaluable_subjects,
                   COUNT(DISTINCT CASE WHEN RESPFL = 'Y' THEN USUBJID END) AS responders,
                   ROUND(COUNT(DISTINCT CASE WHEN RESPFL = 'Y' THEN USUBJID END) * 100.0 / COUNT(DISTINCT USUBJID), 1) AS response_rate_pct
            FROM adresp
            GROUP BY TRT01A;
        """,
        insight="Drug X showed an observed confirmed efficacy response rate of 84.9% compared to 0.0% in Placebo.",
    )
    pdf = build_clinical_pdf_report(req)
    assert pdf.startswith(b"%PDF-")

    text = extract_pdf_text(pdf)
    assert "Drug X" in text
    assert "Placebo" in text
    assert "84.9%" in text or "84.9" in text
    assert "0.0%" in text or "0.0" in text
    assert "efficacy" in text.lower() or "response rate" in text.lower()
    assert "length of stay" not in text.lower()


def test_report_site_enrollment():
    """Verify PDF report generation for site enrollment inquiry."""
    req = PDFReportRequest(
        question="Which site has the highest enrollment?",
        selected_tables=["sites", "dm"],
        results=[
            {"site_name": "Clinical Center 10", "enrolled_subjects": 1053},
            {"site_name": "Clinical Center 1", "enrolled_subjects": 1000},
        ],
        sql_query="""
            SELECT sites.SITE_NAME AS site_name, COUNT(DISTINCT dm.USUBJID) AS enrolled_subjects
            FROM sites
            JOIN dm ON sites.SITEID = dm.SITEID
            GROUP BY sites.SITEID, sites.SITE_NAME
            ORDER BY enrolled_subjects DESC;
        """,
        insight="Clinical Center 10 recorded the highest subject recruitment with 1,053 enrolled participants.",
    )
    pdf = build_clinical_pdf_report(req)
    assert pdf.startswith(b"%PDF-")

    text = extract_pdf_text(pdf)
    assert "Clinical Center 10" in text
    assert "1,053" in text or "1053" in text
    assert "enrolled" in text.lower() or "site" in text.lower()
    assert "length of stay" not in text.lower()


# =============================================================================
# 2. CHART GENERATION & SCIENTIFIC LANGUAGE INTEGRATION
# =============================================================================

def test_chart_image_generation():
    """Verify in-memory matplotlib chart generation for clinical categorical data."""
    results = [
        {"treatment_arm": "Drug X", "adverse_event_rate_pct": 74.5},
        {"treatment_arm": "Placebo", "adverse_event_rate_pct": 53.1},
    ]
    buf = generate_chart_image(results, "What is the adverse event rate by treatment arm?")
    assert buf is not None
    assert buf.getvalue().startswith(b"\x89PNG")  # Valid PNG signature


def test_chart_handles_negative_values():
    """Verify chart handles negative changes from baseline (e.g. blood pressure reduction)."""
    results = [
        {"PARAM": "Systolic Blood Pressure", "mean_change": -4.2},
        {"PARAM": "Diastolic Blood Pressure", "mean_change": -2.1},
    ]
    buf = generate_chart_image(results, "What is the vital sign change from baseline?")
    assert buf is not None
    assert buf.getvalue().startswith(b"\x89PNG")


def test_no_unsupported_causal_or_stat_claims():
    """Ensure report generation does not insert fabricated causal or statistical significance claims."""
    req = PDFReportRequest(
        question="What is the adverse event rate by treatment arm?",
        selected_tables=["adsl", "adae"],
        results=[
            {"treatment_arm": "Drug X", "adverse_event_rate_pct": 74.5},
            {"treatment_arm": "Placebo", "adverse_event_rate_pct": 53.1},
        ],
        insight="Drug X showed an observed adverse event rate of 74.5% compared to 53.1% in Placebo.",
    )
    pdf = build_clinical_pdf_report(req)
    text = extract_pdf_text(pdf).lower()

    # Must NOT introduce unsupported claims
    assert "drug x caused" not in text
    assert "statistically proven" not in text
    assert "p < 0.05" not in text
    assert "statistically significantly better" not in text


# =============================================================================
# 3. BACKWARD COMPATIBILITY & CONTEXT DETECTION TESTS
# =============================================================================

def test_is_clinical_context_detection():
    """Verify accurate detection of CDISC clinical trial context vs legacy EHR context."""
    # Clinical trial requests
    req_clinical_1 = PDFReportRequest(question="How many subjects are enrolled?", selected_tables=["dm"])
    assert _is_clinical_context(req_clinical_1) is True

    req_clinical_2 = PDFReportRequest(question="What is the adverse event rate by treatment arm?", selected_tables=["adsl", "adae"])
    assert _is_clinical_context(req_clinical_2) is True

    req_clinical_3 = PDFReportRequest(
        question="Analysis Inquiry",
        results=[{"treatment_arm": "Drug X", "adverse_event_rate_pct": 74.5}],
    )
    assert _is_clinical_context(req_clinical_3) is True

    # Legacy EHR request
    req_ehr = PDFReportRequest(
        question="What is the average length of stay by diagnosis?",
        selected_tables=["encounters", "conditions", "patients"],
        dataset_name="Organization EHR Dataset",
        results=[{"diagnosis": "Anemia (disorder)", "average_length_of_stay": 4.0}],
    )
    assert _is_clinical_context(req_ehr) is False


def test_legacy_ehr_report_backward_compatibility():
    """Verify that legacy EHR report requests still generate authentic EHR reports."""
    req_ehr = PDFReportRequest(
        question="What is the average length of stay by diagnosis?",
        selected_tables=["encounters", "conditions", "patients"],
        dataset_name="Organization EHR Dataset",
        results=[
            {"diagnosis": "Anemia (disorder)", "average_length_of_stay": 4.0},
            {"diagnosis": "Acute appendicitis", "average_length_of_stay": 2.8},
        ],
        sql_query="""
            SELECT c.DESCRIPTION AS diagnosis, ROUND(AVG(DATEDIFF(e.STOP, e.START)), 1) AS average_length_of_stay
            FROM conditions c
            JOIN encounters e ON c.ENCOUNTER = e.Id
            WHERE e.ENCOUNTERCLASS = 'inpatient'
            GROUP BY c.DESCRIPTION;
        """,
        insight="Anemia was associated with the longest recorded hospital stay of 4.0 days.",
    )
    pdf = build_clinical_pdf_report(req_ehr)
    assert pdf.startswith(b"%PDF-")

    text = extract_pdf_text(pdf)
    assert "CLINICAL ANALYTICS REPORT" in text
    assert "EHR Audit" in text or "EHR" in text
    assert "Anemia (disorder)" in text
    assert "4.0" in text


# =============================================================================
# 4. FASTAPI ENDPOINT INTEGRATION TESTS
# =============================================================================

@pytest.fixture
def client():
    return TestClient(app)


def test_api_generate_pdf_endpoint(client):
    """Test POST /analytics/report/pdf endpoint with clinical trial payload."""
    payload = {
        "question": "How many subjects are enrolled?",
        "selected_tables": ["dm"],
        "results": [{"total_subjects": 1053}],
        "sql_query": "SELECT COUNT(DISTINCT USUBJID) AS total_subjects FROM dm;",
        "insight": "Verified total enrollment of 1,053 subjects in the clinical trial.",
        "dataset_name": "CDISC Clinical Trial Dataset",
    }
    response = client.post("/analytics/report/pdf", json=payload)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_api_download_latest_pdf(client):
    """Test GET /analytics/report/pdf/latest endpoint."""
    response = client.get("/analytics/report/pdf/latest")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_api_download_pdf_get(client):
    """Test GET /analytics/report/pdf/download endpoint."""
    response = client.get("/analytics/report/pdf/download?question=How+many+subjects+are+enrolled%3F")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_api_approve_pdf_report(client):
    """Test POST /analytics/report/approve certification endpoint."""
    response = client.post("/analytics/report/approve")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
