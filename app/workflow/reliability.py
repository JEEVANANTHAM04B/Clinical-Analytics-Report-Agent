"""Common stage contracts and sanitized failure classification."""
import os
from datetime import datetime, timezone
from sqlalchemy.exc import OperationalError


def retry_limit(name="WORKFLOW_MAX_RETRIES"):
    return max(0, min(int(os.getenv(name, "2")), 5))


def transient(exc):
    if isinstance(exc, ConnectionError): return True
    if isinstance(exc, OperationalError):
        args = getattr(exc.orig, "args", ())
        return bool(args and args[0] in {1205, 1213, 2003, 2006, 2013})
    return False


def failure(stage, code="VALIDATION_FAILED", recoverable=False, attempt=0):
    message = {
        "load_schema": "Dataset information could not be loaded. Check the database connection.",
        "analyze_question": "An analysis plan could not be prepared. Review your question and selected datasets.",
        "validate_results": "The query results failed validation. Counts or measurements may be unreliable. Review the data or revise the plan.",
        "execute_sql": "The database query could not complete. No results have been accepted.",
        "validate_sql": "The query did not pass safety or schema checks and was not executed.",
        "validate_insight": "The clinical insight could not be verified against the deterministic query results.",
        "generate_chart": "A chart could not be validated against the results.",
    }.get(stage, "This analysis stage could not complete. No unverified output will be used.")
    return {"stage": stage, "status": "RECOVERABLE_FAILURE" if recoverable else "TERMINAL_FAILURE",
        "code": code, "message": message, "recoverable": recoverable,
        "allowed_actions": ["retry", "stop"] if recoverable else ["review", "stop"],
        "retry_count": attempt, "max_retries": retry_limit(), "user_intervention_required": True,
        "next_destination": stage if recoverable else "stop", "timestamp": datetime.now(timezone.utc).isoformat()}
