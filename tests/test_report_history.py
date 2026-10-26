"""Report persistence, acknowledgement gate, retrieval, and failure behavior."""
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import analytics
from app.api.reports import LOCAL_OWNER
from app.database.models import ClinicalReport
from app.database.session import get_db
from app.main import app
from app.schemas.reports import PDFReportRequest


def sample_pdf(label="Fixture report"):
    output = BytesIO()
    canvas = Canvas(output, invariant=1)
    canvas.drawString(50, 700, label)
    canvas.save()
    return output.getvalue()


@pytest.fixture
def report_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    ClinicalReport.__table__.create(engine)
    sessions = sessionmaker(bind=engine)

    def session_override():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = session_override
    try:
        yield TestClient(app), sessions
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def acknowledge(client, report_id, pdf=None):
    return client.post("/reports/acknowledge", data={
        "report_id": report_id,
        "question": "Count subjects by treatment arm",
        "dataset_name": "Clinical Trial CDISC Dataset",
    }, files={"pdf": ("report.pdf", pdf or sample_pdf(), "application/pdf")})


def test_generation_does_not_persist_without_acknowledgement(monkeypatch, report_client):
    client, sessions = report_client
    pdf = sample_pdf()
    monkeypatch.setattr(analytics, "build_clinical_pdf_report", lambda request: pdf)
    monkeypatch.setattr("app.audit.service.record_audit_event", lambda **kwargs: None)
    response = analytics.generate_pdf_report(PDFReportRequest(question="Count subjects", results=[{"subjects": 12}]))
    assert response.body == pdf
    assert response.headers["x-report-id"]
    assert client.get("/reports").json() == []
    with sessions() as db:
        assert db.query(ClinicalReport).count() == 0
    with pytest.raises(HTTPException) as error:
        analytics.generate_pdf_report(PDFReportRequest(question="No results", results=[]))
    assert error.value.status_code == 422


def test_acknowledge_history_restart_download_and_duplicate(report_client):
    client, sessions = report_client
    report_id = str(uuid4())
    pdf = sample_pdf()
    assert client.get("/reports").json() == []
    first = acknowledge(client, report_id, pdf)
    assert first.status_code == 201
    assert first.json()["status"] == "ACKNOWLEDGED"
    assert first.json()["title"] == "Count subjects by treatment arm"
    assert first.json()["acknowledged_at"]
    assert acknowledge(client, report_id, pdf).status_code == 201
    assert acknowledge(client, report_id, sample_pdf("Different report")).status_code == 409
    # A new API client simulates a page refresh / process restart against the same DB.
    restarted_client = TestClient(app)
    history = restarted_client.get("/reports")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [report_id]
    viewed = restarted_client.get(f"/reports/{report_id}/pdf")
    downloaded = restarted_client.get(f"/reports/{report_id}/pdf?download=true")
    assert viewed.content == downloaded.content == pdf
    assert viewed.headers["content-disposition"].startswith("inline")
    assert downloaded.headers["content-disposition"].startswith("attachment")
    assert restarted_client.get(f"/reports/{uuid4()}/pdf").status_code == 404
    with sessions() as db:
        assert db.query(ClinicalReport).count() == 1


def test_legacy_unacknowledged_rows_are_hidden(report_client):
    client, sessions = report_client
    with sessions() as db:
        db.add(ClinicalReport(id=str(uuid4()), user_id=LOCAL_OWNER, question="Draft", status="COMPLETED",
                              filename="draft.pdf", storage_reference="mysql:test", results=[], selected_tables=[],
                              pdf_bytes=sample_pdf()))
        db.commit()
    assert client.get("/reports").json() == []


def test_invalid_pdf_and_database_failure(report_client):
    client, sessions = report_client
    assert acknowledge(client, str(uuid4()), b"invalid").status_code == 422
    with sessions() as db:
        assert db.query(ClinicalReport).count() == 0
    # Drop only the isolated test table to exercise a real SQL database error.
    with sessions() as db:
        db.execute(text("DROP TABLE clinical_reports"))
        db.commit()
    assert acknowledge(client, str(uuid4())).status_code == 503
    assert client.get("/reports").status_code == 503


def test_routes_are_registered():
    paths = app.openapi()["paths"]
    assert "/reports/acknowledge" in paths
    assert "/reports" in paths
    assert "/reports/{report_id}/pdf" in paths
