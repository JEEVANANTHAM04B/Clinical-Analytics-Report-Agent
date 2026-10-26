"""Persistent PDF history for the trusted, single-user development prototype."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models import ClinicalReport
from app.database.session import get_db
from app.reporting.validation import validate_pdf


router = APIRouter(prefix="/reports", tags=["Report History"])
LOCAL_OWNER = "local-prototype"
MAX_PDF_BYTES = 16 * 1024 * 1024  # Existing MEDIUMBLOB capacity.


def _summary(report: ClinicalReport) -> dict:
    return {
        "id": report.id,
        "title": report.title or report.question[:120],
        "question": report.question,
        "dataset_name": report.dataset_name,
        "analysis_run_id": report.analysis_run_id,
        "study": (report.analysis_metadata or {}).get("study"),
        "generated_at": report.created_at.isoformat() + "Z",
        "acknowledged_at": report.completed_at.isoformat() + "Z" if report.completed_at else None,
        "status": report.status,
        "filename": report.filename,
    }


@router.post("/acknowledge", status_code=201)
async def acknowledge_report(
    report_id: str = Form(...),
    question: str = Form(...),
    pdf: UploadFile = File(...),
    dataset_name: str | None = Form(None),
    analysis_run_id: str | None = Form(None),
    study_id: str | None = Form(None),
    generated_at: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """Store exactly the PDF reviewed by the human; retries with the same ID are safe."""
    try:
        report_id = str(UUID(report_id))
    except ValueError:
        raise HTTPException(422, "Invalid report ID.")
    question = question.strip()
    if not question or len(question) > 10000:
        raise HTTPException(422, "A valid analysis question is required.")

    try:
        data = await pdf.read(MAX_PDF_BYTES + 1)
        if len(data) > MAX_PDF_BYTES:
            raise HTTPException(413, "PDF exceeds the 16 MB report limit.")
        try:
            validate_pdf(data)
        except Exception as exc:
            # pypdf raises several parser-specific exceptions for malformed bytes.
            raise HTTPException(422, "The reviewed file is not a valid PDF.") from exc

        existing = db.get(ClinicalReport, report_id)
        if existing is not None:
            if (existing.user_id != LOCAL_OWNER or existing.status != "ACKNOWLEDGED"
                    or existing.question != question or existing.pdf_bytes != data):
                raise HTTPException(409, "This report ID is already in use for a different report.")
            return _summary(existing)

        try:
            created_at = datetime.fromisoformat(generated_at.replace("Z", "+00:00")) if generated_at else datetime.now(timezone.utc)
            created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            raise HTTPException(422, "Invalid report generation time.")

        report = ClinicalReport(
            id=report_id,
            user_id=LOCAL_OWNER,
            title=(question[:117] + "...") if len(question) > 120 else question,
            question=question,
            dataset_name=(dataset_name or None),
            analysis_run_id=(analysis_run_id or None),
            analysis_metadata={"study": {"studyid": study_id}} if study_id else None,
            status="ACKNOWLEDGED",
            filename=f"clinical-report-{report_id}.pdf",
            storage_reference=f"mysql:clinical_reports:{report_id}",
            results=[],
            selected_tables=[],
            pdf_bytes=data,
            created_at=created_at,
            completed_at=datetime.utcnow(),
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return _summary(report)
    except IntegrityError:
        db.rollback()
        existing = db.get(ClinicalReport, report_id)
        if (existing is not None and existing.user_id == LOCAL_OWNER and existing.status == "ACKNOWLEDGED"
                and existing.question == question and existing.pdf_bytes == data):
            return _summary(existing)
        raise HTTPException(409, "This report ID is already in use.")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "Could not save the acknowledged report. Retry when MySQL is available.") from exc
    finally:
        await pdf.close()


@router.get("")
def list_reports(db: Session = Depends(get_db)):
    try:
        reports = (db.query(ClinicalReport)
                   .filter(ClinicalReport.user_id == LOCAL_OWNER, ClinicalReport.status == "ACKNOWLEDGED")
                   .order_by(ClinicalReport.completed_at.desc()).all())
        return [_summary(report) for report in reports]
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Report history is unavailable. Check the MySQL connection.") from exc


@router.get("/{report_id}/pdf")
def get_report_pdf(report_id: str, download: bool = Query(False), db: Session = Depends(get_db)):
    try:
        UUID(report_id)
    except ValueError:
        raise HTTPException(404, "Report not found.")
    try:
        report = db.get(ClinicalReport, report_id)
        if (report is None or report.user_id != LOCAL_OWNER or report.status != "ACKNOWLEDGED"
                or not report.pdf_bytes):
            raise HTTPException(404, "Acknowledged report not found.")
        disposition = "attachment" if download else "inline"
        return Response(
            content=report.pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'{disposition}; filename="{report.filename}"',
                     "Cache-Control": "private, no-store"},
        )
    except SQLAlchemyError as exc:
        raise HTTPException(503, "The saved PDF is temporarily unavailable.") from exc
