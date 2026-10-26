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
9. PDF endpoint behavior and retired history routes.
"""

import io
import sys
import os
sys.path.insert(0, os.path.abspath("."))

import pytest
from pypdf import PdfReader
from fastapi import HTTPException
from sqlalchemy import create_engine, text

from app.main import app
from app.api.analytics import _top_adverse_events
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
    assert len(pdf) > 2000

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
    assert "SQL was not stored" not in text
    assert "SELECT COUNT(DISTINCT USUBJID)" not in text
    assert "End of report." not in text
    assert req.sql_query == "SELECT COUNT(DISTINCT USUBJID) AS total_subjects FROM dm;"
    assert "100%" not in text
    assert "CERTIFIED BY" not in text


def test_report_without_sql_does_not_invent_query_or_certification():
    req = PDFReportRequest(question="How many subjects are enrolled?", selected_tables=["dm"],
                           results=[{"total_subjects": 1053}])
    text = extract_pdf_text(build_clinical_pdf_report(req))
    assert "SQL was not stored with this report" not in text
    assert "End of report." not in text
    assert "source execution not established" in text.lower()
    assert "CERTIFIED" not in text


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


def test_report_plan_formula_multiplication_does_not_break_pdf_markup():
    """Inline SQL-style formulas must not be interpreted as Markdown italics."""
    plan = (
        "#### 3. Derived Calculations\n"
        "* **Adverse Event Incidence Rate (%)**:\n"
        "  `COUNT(DISTINCT adae.USUBJID) / COUNT(DISTINCT adsl.USUBJID) * 100`"
    )
    req = PDFReportRequest(
        question="Compare adverse event rates between treatment groups",
        analysis_plan=plan,
        selected_tables=["adsl", "adae"],
        results=[
            {"treatment_arm": "Drug X", "subjects": 20, "adverse_event_rate_pct": 25.0},
            {"treatment_arm": "Placebo", "subjects": 20, "adverse_event_rate_pct": 15.0},
        ],
        insight="The submitted rates were 25.0% and 15.0%.",
    )

    pdf = build_clinical_pdf_report(req)
    text = extract_pdf_text(pdf)
    assert "Population and Analysis Rules" in text
    assert "Participant percentage" in text
    assert "COUNT(DISTINCT adae.USUBJID)" not in text.split("4. Submitted Results")[0]


def test_report_cover_study_facts_plain_language_rules_and_second_chart():
    req = PDFReportRequest(
        question="What is the adverse event rate by treatment arm?",
        dataset_name="Clinical Trial CDISC Dataset",
        selected_tables=["study", "adsl", "adae"],
        analysis_plan=("Join adsl.USUBJID = adae.USUBJID without STUDYID. "
                       "Group by adsl.TRT01A; use COUNT(DISTINCT adae.USUBJID) / "
                       "COUNT(DISTINCT adsl.USUBJID) * 100. "
                       "SAFFL = 'Y' if applicable; TRTEMFL = 'Y' if applicable."),
        results=[
            {"treatment_arm": "Drug X", "total_subjects": 5011, "ae_subjects": 5011,
             "adverse_event_rate_pct": 100.0},
            {"treatment_arm": "Placebo", "total_subjects": 4989, "ae_subjects": 4989,
             "adverse_event_rate_pct": 100.0},
        ],
        insight="Both groups had a reported adverse event rate of 100%.",
        analysis_metadata={"result_validation": {"valid": True}, "study": {
            "studyid": "STDY001", "phase": "Phase 3",
            "study_title": "Phase 3 Study of Drug X", "indication": "Rheumatoid Arthritis",
            "start_date": "2025-01-15", "end_date": "2026-06-30",
        }},
    )
    pages = PdfReader(io.BytesIO(build_clinical_pdf_report(req))).pages
    cover = pages[0].extract_text()
    text = "\n".join(page.extract_text() for page in pages)
    assert "Study ID: STDY001" in cover
    assert "Phase: Phase 3" in cover
    assert "Study dates: 2025-01-15 to 2026-06-30" in cover
    assert "Figure 2. Participant counts by treatment group" in text
    assert "Verified Results" in text
    assert "Clinical Insights and Follow-up" in text
    assert "optional restriction" in text
    assert "COUNT(DISTINCT" not in text
    assert "End of report." not in text


def test_pdf_adds_top_adae_events_as_separate_dataset_context():
    req = PDFReportRequest(
        question="What is the adverse event rate by treatment arm?",
        dataset_name="Clinical Trial CDISC Dataset",
        selected_tables=["adsl", "adae"],
        results=[
            {"treatment_arm": "Drug X", "adverse_event_rate_pct": 62.0},
            {"treatment_arm": "Placebo", "adverse_event_rate_pct": 48.0},
        ],
        analysis_metadata={"result_validation": {"valid": True}, "top_adverse_events": [
            {"term": "Headache", "subject_count": 2571},
            {"term": "Nausea", "subject_count": 1984},
        ]},
    )
    pdf = build_clinical_pdf_report(req)
    text_content = extract_pdf_text(pdf)
    assert "Top Adverse Events by Frequency" in text_content
    assert "Supplemental ADAE dataset view" in text_content
    assert "Distinct participants with each adverse-event term" in text_content
    assert "Headache" in text_content and "2,571" in text_content
    assert "Nausea" in text_content and "1,984" in text_content
    assert "counts must not be added together" in text_content
    assert any(
        "Top Adverse Events by Frequency" in (page.extract_text() or "")
        and "Figure 3. Distinct participants" in (page.extract_text() or "")
        for page in PdfReader(io.BytesIO(pdf)).pages
    )
    assert any(
        "5. Clinical Insights and Follow-up" in (page.extract_text() or "")
        and "What cannot be concluded" in (page.extract_text() or "")
        for page in PdfReader(io.BytesIO(pdf)).pages
    )


def test_long_pdf_keeps_result_rows_and_insights_without_sql_appendix():
    req = PDFReportRequest(
        question="How do clinical outcomes vary across categories?",
        selected_tables=["adsl"],
        results=[{"category": f"Category {index:03d}", "subject_count": index * 10,
                  "rate_pct": index / 2} for index in range(1, 81)],
        insight="\n".join(f"Finding {index}: Review this descriptive outcome with the study plan."
                          for index in range(1, 16)),
        follow_up_answers=[{"question": f"Follow-up {index}?", "answer": "Clinical review is required."}
                           for index in range(1, 11)],
        sql_query="SELECT INTERNAL_QUERY_SENTINEL FROM adsl;",
    )
    pages = PdfReader(io.BytesIO(build_clinical_pdf_report(req))).pages
    text = "\n".join(page.extract_text() or "" for page in pages)

    assert len(pages) > 3
    assert "Category 001" in text and "Category 080" in text
    assert "Finding 1:" in text and "Finding 15:" in text
    assert "Follow-up 1?" in text and "Follow-up 10?" in text
    assert "INTERNAL_QUERY_SENTINEL" not in text
    assert "End of report." not in text


def test_pdf_does_not_infer_top_events_from_other_results():
    req = PDFReportRequest(
        question="What is the mean age in each treatment group?",
        selected_tables=["adsl", "dm"],
        results=[{"treatment_arm": "Drug X", "mean_age": 54.2}],
    )
    assert "Top Adverse Events by Frequency" not in extract_pdf_text(build_clinical_pdf_report(req))


def test_top_adverse_events_match_dashboard_distinct_subject_definition():
    test_engine = create_engine("sqlite+pysqlite:///:memory:")
    with test_engine.begin() as connection:
        connection.execute(text("CREATE TABLE adae (AEDECOD TEXT, USUBJID TEXT, TRTEMFL TEXT, SAFFL TEXT)"))
        connection.execute(text("INSERT INTO adae VALUES (:term, :subject, :emergent, :safety)"), [
            {"term": "Headache", "subject": "01", "emergent": "Y", "safety": "Y"},
            {"term": "Headache", "subject": "01", "emergent": "Y", "safety": "Y"},
            {"term": "Headache", "subject": "02", "emergent": None, "safety": "Y"},
            {"term": "Nausea", "subject": "01", "emergent": "Y", "safety": None},
            {"term": "Headache", "subject": "03", "emergent": "N", "safety": "Y"},
        ])
        items = _top_adverse_events(connection)
    assert items == [
        {"term": "Headache", "subject_count": 2},
        {"term": "Nausea", "subject_count": 1},
    ]


def test_safety_template_has_three_sections_pages_without_sample_study_facts():
    req = PDFReportRequest(
        question="Compare serious adverse events between Drug A and Placebo",
        dataset_name="Current clinical dataset",
        selected_tables=["adsl", "adae"],
        results=[
            {"treatment_arm": "Drug A", "safety_population": 40, "serious_ae_rate_pct": 2.5},
            {"treatment_arm": "Placebo", "safety_population": 42, "serious_ae_rate_pct": 0.0},
        ],
        insight="Observed serious adverse event rates were 2.5% and 0.0%, respectively.",
        analysis_plan="Compare the supplied treatment groups using the selected datasets.",
    )

    pdf = build_clinical_pdf_report(req)
    pages = PdfReader(io.BytesIO(pdf)).pages
    text = extract_pdf_text(pdf)
    assert len(pages) >= 3
    for heading in ("1. Executive Summary", "2. Results Visualization",
                    "3. Population and Analysis Rules", "4. Submitted Results",
                    "5. Clinical Insights and Follow-up", "6. Data Quality, Limitations, and Traceability",
                    "7. Agent Execution Record"):
        assert heading in text
    assert "Drug A" in text and "2.5%" in text and "0.0%" in text
    assert "STDY001" not in text


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

def test_api_generate_pdf_endpoint():
    """Report generation is open, but still requires validated result rows."""
    from app.api.analytics import generate_pdf_report
    with pytest.raises(HTTPException) as error:
        generate_pdf_report(PDFReportRequest(question="How many subjects are enrolled?"))
    assert error.value.status_code == 422


def test_api_download_latest_pdf():
    """The unsafe process-global latest PDF endpoint is retired."""
    from app.api.analytics import download_latest_pdf_report
    with pytest.raises(HTTPException) as error:
        download_latest_pdf_report()
    assert error.value.status_code == 410


def test_api_download_pdf_get():
    """Downloads cannot generate a new report."""
    from app.api.analytics import download_pdf_report_get
    with pytest.raises(HTTPException) as error:
        download_pdf_report_get()
    assert error.value.status_code == 410


def test_api_approve_pdf_report():
    """Persistent report review acknowledgement is not an active API feature."""
    assert "/analytics/report/approve" not in app.openapi()["paths"]
