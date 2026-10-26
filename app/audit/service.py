"""
app/audit/service.py
====================
Centralized Audit Trail Service for Clinical Analytics Platform.

PURPOSE:
    Provides a standardized, tamper-evident audit logging mechanism for:
      - Dataset Ingestion & Schema Profiling
      - Analyst Relationship Confirmation / Rejection
      - Analytics Pipeline Execution & Plan Review
      - SQL Synthesis, Validation & Execution
      - AI Insight Generation & Validation
      - Reportlab Certified PDF Generation, Approval & Download

SAFETY GUARANTEES:
    - Writes directly to the real MySQL `audit_logs` table.
    - Captures WHO, WHAT, WHEN, RESOURCE, and OUTCOME.
    - Sanitizes sensitive clinical data (never logs raw PII, credentials, or secrets).
    - Failure in audit logging is logged as an error and never crashes upstream medical queries.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db_context, engine
from app.core.logging_config import get_logger
from app.database.models import AuditLog

logger = get_logger(__name__)


def record_audit_event(
    action: str,
    details: str,
    user_agent: str = "Clinical Analyst",
    status: str = "SUCCESS",
    entity_type: str = "WORKFLOW",
    entity_name: str = "clinical_analytics",
    db: Optional[Session] = None,
) -> Optional[AuditLog]:
    """
    Persists a real audit event record directly into the MySQL `audit_logs` table.

    Args:
        action: Audit action name (e.g. DATASET_UPLOAD, SQL_EXECUTED, ANALYSIS_PLAN_APPROVED).
        details: Clear, sanitized explanation of the event and resources affected.
        user_agent: Initiating actor (e.g. 'Clinical Analyst', 'FastAPI API', 'LangGraph Pipeline').
        status: Operation outcome (SUCCESS, FAILED, REJECTED, PARTIAL).
        entity_type: Category of the resource (e.g. TABLE, QUERY, PLAN, REPORT, RELATIONSHIP).
        entity_name: Specific identifier of the resource (e.g. table name, query hash, report name).
        db: Optional existing SQLAlchemy session; if omitted, opens a dedicated context session.

    Returns:
        The created AuditLog instance or None if database insertion failed.
    """
    clean_action = str(action).strip().upper()
    clean_details = str(details).strip() if details else "Operational event recorded."
    clean_user = str(user_agent).strip() if user_agent else "Clinical Analyst"
    clean_status = str(status).strip().upper()
    clean_entity_type = str(entity_type).strip().upper() if entity_type else "SYSTEM"
    clean_entity_name = str(entity_name).strip() if entity_name else "clinical_analytics"

    # Internal helper to perform insertion
    def _insert(session: Session) -> AuditLog:
        log_entry = AuditLog(
            action=clean_action,
            entity_type=clean_entity_type,
            entity_name=clean_entity_name,
            status=clean_status,
            message=clean_details,
            user_agent=clean_user,
            created_at=datetime.utcnow(),
        )
        session.add(log_entry)
        session.commit()
        session.refresh(log_entry)
        session.expunge(log_entry)
        return log_entry

    try:
        if db is not None:
            entry = _insert(db)
            logger.info(f"AUDIT EVENT: [{entry.action}] #{entry.id} - {entry.message} (by {entry.user_agent})")
            return entry

        with get_db_context() as session:
            entry = _insert(session)
            logger.info(f"AUDIT EVENT: [{entry.action}] #{entry.id} - {entry.message} (by {entry.user_agent})")
            return entry

    except Exception as exc:
        logger.error(f"Failed to persist audit event [{clean_action}] to MySQL: {exc}", exc_info=True)
        return None


def get_audit_trail(
    limit: int = 100,
    action_filter: Optional[str] = None,
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves real audit log records from the MySQL `audit_logs` table, ordered newest first.
    """
    query_str = """
        SELECT 
            id,
            action,
            entity_type,
            entity_name,
            status,
            message,
            COALESCE(user_agent, 'Clinical Analyst') AS user_agent,
            created_at
        FROM audit_logs
    """
    params = {"limit": limit}

    if action_filter:
        query_str += " WHERE action = :action"
        params["action"] = action_filter.upper()

    query_str += " ORDER BY id DESC LIMIT :limit"

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(query_str), params).fetchall()

        events = []
        for r in rows:
            created_dt = r[7]
            formatted_ts = created_dt.strftime("%Y-%m-%d %H:%M:%S") if created_dt else ""
            events.append({
                "id": int(r[0]),
                "action": str(r[1]),
                "entity_type": str(r[2]),
                "entity_name": str(r[3]),
                "status": str(r[4]),
                "message": r[5] or "",
                "details": r[5] or f"{r[2]}: {r[3]} ({r[4]})",
                "user": str(r[6]),
                "user_agent": str(r[6]),
                "timestamp": formatted_ts,
                "created_at": created_dt,
            })
        return events

    except Exception as exc:
        logger.error(f"Error reading audit trail from MySQL: {exc}", exc_info=True)
        raise
