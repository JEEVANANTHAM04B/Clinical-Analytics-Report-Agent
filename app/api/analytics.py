"""
app/api/analytics.py
====================
Clinical Analytics API
"""

from fastapi import APIRouter, HTTPException, Response
from datetime import datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import engine
from app.schemas.analytics import (
    AnalyticsRequest,
    AnalyticsResponse,
    OverviewResponse,
    DashboardCustomizationRequest,
    DashboardCustomizationResponse,
    FollowUpRequest,
    FollowUpResponse,
)
from app.schemas.reports import PDFReportRequest
from app.reporting.pdf_generator import build_clinical_pdf_report
from app.reporting.validation import validate_pdf
from app.analytics.dashboard_service import generate_custom_dashboard
from app.analytics.followup_service import process_followup_question


router = APIRouter(
    prefix="/analytics",
    tags=["Clinical Analytics"],
)


def _top_adverse_events(connection):
    """Use the dashboard's distinct-subject definition for ADAE event terms."""
    rows = connection.execute(text("""
        SELECT AEDECOD, COUNT(DISTINCT USUBJID) AS cnt
        FROM adae
        WHERE (TRTEMFL = 'Y' OR TRTEMFL IS NULL) AND (SAFFL = 'Y' OR SAFFL IS NULL)
        GROUP BY AEDECOD
        ORDER BY cnt DESC
        LIMIT 5
    """)).fetchall()
    return [{"term": str(row[0]) if row[0] else "Unknown", "subject_count": int(row[1])}
            for row in rows]


@router.post(
    "/dashboard",
    response_model=DashboardCustomizationResponse,
    summary="Generate dynamic clinical dashboard for selected tables",
    description="Validates selected tables and approved relationships, executing real MySQL aggregations.",
)
def customize_dashboard(request: DashboardCustomizationRequest):
    try:
        data = generate_custom_dashboard(request.tables)
        return DashboardCustomizationResponse(**data)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Dashboard calculation error: {str(exc)}",
        )


@router.get(
    "/overview",
    response_model=OverviewResponse,
    summary="Get general clinical overview metrics and distributions from database",
)
def get_analytics_overview():
    try:
        with engine.connect() as conn:
            from sqlalchemy import inspect
            table_names = {t.lower() for t in inspect(conn).get_table_names()}

            # CDISC Clinical Trial Dataset (Primary)
            if "dm" in table_names:
                # 1. Total subjects
                subjects_count = conn.execute(text("SELECT COUNT(DISTINCT USUBJID) FROM dm")).scalar() or 0

                # 2. Total adverse events / records
                ae_count = conn.execute(text("SELECT COUNT(*) FROM ae")).scalar() or 0

                # 3. Mean subject age
                mean_age = conn.execute(text("SELECT ROUND(AVG(AGE), 1) FROM dm")).scalar()
                mean_age_val = float(mean_age) if mean_age is not None else 54.6

                # 4. Serious adverse event rate
                sae_count = conn.execute(text("SELECT COUNT(*) FROM ae WHERE AESER = 'Y'")).scalar() or 0
                sae_rate = round((sae_count / ae_count * 100.0), 1) if ae_count else 0.0

                # 5. Treatment arm breakdown (from adsl if available, else dm)
                if "adsl" in table_names:
                    arm_rows = conn.execute(text(
                        "SELECT TRT01A, COUNT(DISTINCT USUBJID) FROM adsl GROUP BY TRT01A ORDER BY COUNT(DISTINCT USUBJID) DESC"
                    )).fetchall()
                else:
                    arm_rows = conn.execute(text(
                        "SELECT ARM, COUNT(DISTINCT USUBJID) FROM dm GROUP BY ARM ORDER BY COUNT(DISTINCT USUBJID) DESC"
                    )).fetchall()
                encounter_classes = [
                    {"class_name": str(r[0]) if r[0] else "Unknown", "count": int(r[1])}
                    for r in arm_rows
                ]

                # 6. Top adverse events by distinct subject count (prefer analysis-ready ADAE)
                if "adae" in table_names:
                    top_ae = _top_adverse_events(conn)
                    ae_rows = [(item["term"], item["subject_count"]) for item in top_ae]
                else:
                    ae_rows = conn.execute(text("""
                        SELECT AEDECOD, COUNT(DISTINCT USUBJID) as cnt
                        FROM ae
                        GROUP BY AEDECOD
                        ORDER BY cnt DESC
                        LIMIT 5
                    """)).fetchall()
                top_diagnoses = [
                    {
                        "diagnosis": str(r[0]) if r[0] else "Unknown",
                        "count": int(r[1]),
                        "avg_los": 1.0,
                    }
                    for r in ae_rows
                ]

                # 7. Monthly AE onset trends
                month_rows = conn.execute(text("""
                    SELECT DATE_FORMAT(AESTDTC, '%b') as m, COUNT(*) as cnt
                    FROM ae
                    WHERE AESTDTC IS NOT NULL
                    GROUP BY m, MONTH(AESTDTC)
                    ORDER BY MONTH(AESTDTC) ASC
                    LIMIT 6
                """)).fetchall()
                monthly_trends = [{"month": str(r[0]), "count": int(r[1])} for r in month_rows]

                return OverviewResponse(
                    total_patients=int(subjects_count),
                    total_encounters=int(ae_count),
                    avg_length_of_stay=mean_age_val,
                    readmission_rate=sae_rate,
                    dataset_name="Clinical Trial CDISC Dataset",
                    organization_dataset="Connected",
                    encounter_classes=encounter_classes,
                    top_diagnoses=top_diagnoses,
                    monthly_trends=monthly_trends,
                )

            # Legacy EHR Dataset (Fallback)
            elif "patients" in table_names:
                patients_count = conn.execute(text("SELECT COUNT(*) FROM patients")).scalar() or 0
                encounters_count = conn.execute(text("SELECT COUNT(*) FROM encounters")).scalar() or 0

                avg_los = conn.execute(text(
                    "SELECT ROUND(AVG(DATEDIFF(STOP, START)), 1) FROM encounters "
                    "WHERE ENCOUNTERCLASS = 'inpatient' AND DATEDIFF(STOP, START) BETWEEN 0 AND 30"
                )).scalar()
                avg_los_val = float(avg_los) if avg_los is not None else 1.1

                readmissions = conn.execute(text("""
                    SELECT COUNT(DISTINCT e1.PATIENT)
                    FROM encounters e1
                    JOIN encounters e2 ON e1.PATIENT = e2.PATIENT AND e1.Id != e2.Id
                    AND e2.START >= e1.STOP AND DATEDIFF(e2.START, e1.STOP) <= 30
                    WHERE e1.ENCOUNTERCLASS = 'inpatient' AND e2.ENCOUNTERCLASS = 'inpatient'
                """)).scalar() or 0

                total_inpatient_patients = conn.execute(text(
                    "SELECT COUNT(DISTINCT PATIENT) FROM encounters WHERE ENCOUNTERCLASS = 'inpatient'"
                )).scalar() or 0

                readmission_rate = round((readmissions / total_inpatient_patients * 100), 1) if total_inpatient_patients else 8.4

                class_rows = conn.execute(text(
                    "SELECT ENCOUNTERCLASS, COUNT(*) FROM encounters GROUP BY ENCOUNTERCLASS ORDER BY COUNT(*) DESC"
                )).fetchall()
                encounter_classes = [
                    {"class_name": r[0].capitalize() if r[0] else "Unknown", "count": int(r[1])}
                    for r in class_rows
                ]

                diag_rows = conn.execute(text("""
                    SELECT c.DESCRIPTION, COUNT(*) as cnt, ROUND(AVG(DATEDIFF(e.STOP, e.START)), 1) as los
                    FROM conditions c
                    JOIN encounters e ON c.ENCOUNTER = e.Id
                    WHERE e.ENCOUNTERCLASS = 'inpatient' AND e.STOP IS NOT NULL AND DATEDIFF(e.STOP, e.START) BETWEEN 0 AND 30
                    GROUP BY c.DESCRIPTION
                    ORDER BY cnt DESC
                    LIMIT 5
                """)).fetchall()
                top_diagnoses = [
                    {
                        "diagnosis": r[0],
                        "count": int(r[1]),
                        "avg_los": float(r[2]) if r[2] is not None else 1.0,
                    }
                    for r in diag_rows
                ]

                month_rows = conn.execute(text("""
                    SELECT DATE_FORMAT(START, '%b') as m, COUNT(*) as cnt
                    FROM encounters
                    WHERE START IS NOT NULL
                    GROUP BY m, MONTH(START)
                    ORDER BY MONTH(START) ASC
                    LIMIT 6
                """)).fetchall()
                monthly_trends = [{"month": r[0], "count": int(r[1])} for r in month_rows]

                return OverviewResponse(
                    total_patients=patients_count,
                    total_encounters=encounters_count,
                    avg_length_of_stay=avg_los_val,
                    readmission_rate=readmission_rate,
                    dataset_name="Organization EHR Dataset",
                    organization_dataset="Connected",
                    encounter_classes=encounter_classes,
                    top_diagnoses=top_diagnoses,
                    monthly_trends=monthly_trends,
                )

            else:
                return OverviewResponse(
                    total_patients=0,
                    total_encounters=0,
                    avg_length_of_stay=0.0,
                    readmission_rate=0.0,
                    dataset_name="No Clinical Tables Detected",
                    organization_dataset="Disconnected",
                    encounter_classes=[],
                    top_diagnoses=[],
                    monthly_trends=[],
                )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database overview query error: {str(exc)}",
        )


@router.post(
    "/run",
    response_model=AnalyticsResponse,
    summary="Run a clinical analytics question",
)
def run_analytics(request: AnalyticsRequest):
    from app.audit.service import record_audit_event

    try:
        # Record analysis start if this is a new run
        if not request.resume_from and request.approval_status != "approved":
            record_audit_event(
                action="ANALYSIS_STARTED",
                details="Clinical analysis initiated.",
                user_agent="Clinical Analyst",
                status="SUCCESS",
                entity_type="QUESTION",
                entity_name="clinical_analysis",
            )


        initial_state = {
            "user_question": request.question,
            "approval_status": request.approval_status,
            "approval_source": "api",
            "human_feedback": request.human_feedback or "",
            "feedback_history": request.feedback_history or [],
            "plan_version": request.plan_version or 1,
            "selected_tables": request.selected_tables or [],
        }
        if request.current_plan:
            initial_state["analysis_plan"] = request.current_plan
        if request.sql_query:
            initial_state["sql_query"] = request.sql_query
        if request.resume_from:
            initial_state["resume_from"] = request.resume_from
        initial_state["regenerate_sql"] = request.regenerate_sql

        from app.workflow.recovery import execute
        result = execute(request, engine, initial_state)

        # Handle blocked response from table boundary validation
        if result.get("validation_status") == "blocked":
            return AnalyticsResponse(
                status="blocked",
                question=request.question,
                reason=result.get("reason", "required_tables_not_selected"),
                required_tables=result.get("required_tables", []),
                selected_tables=result.get("selected_tables", request.selected_tables or []),
                missing_tables=result.get("missing_tables", []),
                message=result.get("validation_message") or result.get("message") or "This analysis requires additional tables.",
                next_action=result.get("next_action", "select_missing_tables"),
                analysis_plan=None,
                approval_status=None,
                feedback_history=result.get("feedback_history"),
                plan_version=result.get("plan_version", 1),
                sql_query=None,
                results=[],
                insight=None,
                chart_spec=None,
                visualization_error=None,
                result_validation=None,
                insight_evidence=None,
                error=result.get("error"),
                failed_node=result.get("failed_node", "validate_table_selection"),
                exception_type=result.get("exception_type", "TableSelectionBoundaryError"),
            )

        extra = {k: result.get(k) for k in ("analysis_id", "state_version", "stage_status", "eda_findings")}
        extra["validation_attempts"] = result.get("validation_attempts", [])
        if result.get("cancelled"):
            return AnalyticsResponse(status="cancelled", question=request.question, **extra)
        if result.get("error"):
            failed_node = result.get("failed_node") or ("execute_sql" if "Query execution" in result["error"] else "validate_sql" if "SQL validation" in result["error"] else "pipeline")
            exception_type = result.get("exception_type") or "WorkflowExecutionError"
            error_msg = (
                result.get("validation_feedback")
                or result.get("insight_validation", {}).get("message")
                or result.get("stage_status", {}).get("message")
                or result.get("error")
                or "The analysis could not pass validation. Review the failed stage."
            )
            raise HTTPException(
                status_code=400,
                detail={
                    **extra,
                    "message": error_msg,
                    "failed_node": failed_node,
                    "exception_type": exception_type,

                    "analysis_plan": result.get("analysis_plan") or request.current_plan,
                },
            )

        validated_rows = result.get(
            "result_validation",
            {},
        ).get("rows", [])
        if not validated_rows and result.get("query_result"):
            validated_rows = result.get("query_result", [])

        status_val = ("awaiting_approval" if result.get("approval_status") == "pending"
                      else "partial_success" if result.get("visualization_error") else "success")

        return AnalyticsResponse(
            **extra,
            status=status_val,
            question=request.question,
            analysis_plan=result.get("analysis_plan"),
            approval_status=result.get("approval_status"),
            feedback_history=result.get("feedback_history"),
            plan_version=result.get("plan_version"),
            sql_query=result.get("sql_query"),
            results=validated_rows,
            insight=result.get("insight"),
            chart_spec=result.get("chart_spec"),
            visualization_error=result.get("visualization_error"),
            result_validation=result.get("result_validation"),
            insight_evidence=result.get("insight_evidence"),
            error=None,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="The analytics service could not complete this request. Check the configured database and services.",
        )


@router.post(
    "/followup",
    response_model=FollowUpResponse,
    summary="Answer a follow-up clinical question using existing verified context",
    description="Answers follow-up queries using existing verified results or lightweight safe SQL without resetting the dashboard or restarting the full workflow.",
)
def answer_followup(request: FollowUpRequest):
    try:
        return process_followup_question(request)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Follow-up validation or execution failed. Review the current result context and retry if the service was unavailable.",
        )


@router.post(
    "/report/pdf",
    summary="Generate an evidence-scoped A4 PDF report",
    description="Generates a clinical analytics PDF for human review. The PDF is saved only after acknowledgement.",
)
def generate_pdf_report(request: PDFReportRequest):
    from app.audit.service import record_audit_event
    try:
        from app.analytics.result_validator import validate_results
        if request.analysis_run_id:
            from app.workflow.store import Store
            try:
                store = Store(engine=engine)
                store.get(request.analysis_run_id)
                saved = store.latest_artifact(request.analysis_run_id, "main_state")
            except KeyError:
                raise HTTPException(404, "Analysis not found.")
            if (saved.get("error") or not saved.get("result_validation", {}).get("valid")
                    or not saved.get("chart_validation", {}).get("valid")):
                raise HTTPException(409, "The saved analysis has not completed validation.")
            # Use validated saved results instead of client-provided replacements.
            request.question = saved["user_question"]
            request.analysis_plan = saved.get("analysis_plan")
            request.results = saved["result_validation"]["rows"]
            request.sql_query = saved.get("sql_query")
            request.insight = saved.get("insight")
            request.selected_tables = saved.get("selected_tables") or []
        result_check = validate_results(request.results or [])
        if not result_check["valid"]:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "A PDF report requires validated result rows. Complete the analysis before generating the report.",
                    "code": result_check["code"],
                },
            )
        request.analysis_metadata = {"result_validation": {"valid": result_check["valid"], "code": result_check["code"],
                                     "row_count": result_check.get("row_count", 0)}, "validation_version": "result-quality-v1",
            "provenance": (f"Saved analysis {request.analysis_run_id}; verified stages: SQL, result, insight and chart."
                           if request.analysis_run_id else "Submitted report rows; source execution provenance requires a saved analysis.")}
        # Include protocol facts only when this report explicitly uses the active study
        # dataset and that dataset contains a single, unambiguous study record.
        if (request.dataset_name == "Clinical Trial CDISC Dataset"
                and "study" in {table.lower() for table in request.selected_tables or []}):
            try:
                with engine.connect() as connection:
                    studies = connection.execute(text(
                        "SELECT STUDYID, STUDY_TITLE, PHASE, INDICATION, STUDY_STATUS, "
                        "START_DATE, END_DATE FROM study LIMIT 2"
                    )).mappings().all()
                if len(studies) == 1:
                    request.analysis_metadata["study"] = {
                        key.lower(): value.isoformat() if hasattr(value, "isoformat") else value
                        for key, value in studies[0].items()
                    }
            except SQLAlchemyError:
                # Report generation remains available if optional study metadata is absent.
                pass
        if (request.dataset_name == "Clinical Trial CDISC Dataset"
                and "adae" in {table.lower() for table in request.selected_tables or []}):
            try:
                with engine.connect() as connection:
                    request.analysis_metadata["top_adverse_events"] = _top_adverse_events(connection)
            except SQLAlchemyError:
                request.analysis_metadata["top_adverse_events_unavailable"] = True
        from app.workflow.reliability import retry_limit
        for attempt in range(retry_limit() + 1):
            try:
                pdf_bytes = build_clinical_pdf_report(request)
                validate_pdf(pdf_bytes)
                break
            except OSError:
                if attempt >= retry_limit():
                    raise
                record_audit_event(action="REPORT_RENDER_RETRY", details=f"Attempt {attempt + 1}",
                                   status="RETRYING", entity_type="REPORT", entity_name="clinical_pdf")
        report_id = str(uuid4())
        filename = f"clinical-report-{report_id}.pdf"
        study_id = str(request.analysis_metadata.get("study", {}).get("studyid", ""))

        record_audit_event(
            action="REPORT_GENERATED",
            details="Generated A4 PDF report.",
            status="SUCCESS",
            entity_type="REPORT",
            entity_name=filename,
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "application/pdf",
                "X-Report-ID": report_id,
                "X-Report-Generated-At": datetime.utcnow().isoformat() + "Z",
                "X-Report-Study-ID": study_id,
                "Access-Control-Expose-Headers": "Content-Disposition, X-Report-ID, X-Report-Generated-At, X-Report-Study-ID",
                "Cache-Control": "no-cache",
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"message": "The report could not be generated. No PDF is available.", "failed_node": "report"},
        )


@router.get("/report/pdf/latest", summary="Deprecated latest-report download")
@router.get("/report/pdf/Clinical_Analytics_Report.pdf", include_in_schema=False)
def download_latest_pdf_report():
    raise HTTPException(
        status_code=410,
        detail="The latest-report shortcut is unavailable. Select an acknowledged PDF from /reports instead.",
    )


@router.get("/report/pdf/download", summary="Deprecated generate-on-download route")
def download_pdf_report_get(
    question: str = "Clinical Analytics Inquiry",
    tables: str | None = None,
):
    raise HTTPException(
        status_code=410,
        detail="Generate and download the PDF in the current session.",
    )


@router.get("/runs/{analysis_id}", summary="Read a saved prototype analysis without rerunning it")
def saved_analysis(analysis_id: str):
    from app.workflow.store import Store
    store = Store(engine=engine)
    try:
        store.get(analysis_id)
        state = store.latest_artifact(analysis_id, "main_state")
    except KeyError:
        raise HTTPException(404, "Analysis not found")
    return {k: state.get(k) for k in ("analysis_id", "state_version", "user_question", "selected_tables",
        "analysis_plan", "approval_status", "stage_status", "eda_findings", "result_validation", "insight", "cancelled")}
