"""
app/api/health.py
==================
Health Check API Endpoints

WHY HEALTH CHECKS?
    Every production API needs health check endpoints because:
      1. Load balancers use them to know if the server is ready
      2. Monitoring tools (like Uptime Robot, Grafana) ping them periodically
      3. During development, they're the first thing you test to confirm
         the server + database are both working

ENDPOINTS:
    GET /health      — Basic API liveness check (no DB required)
    GET /health/db   — Full health check including MySQL connectivity

DESIGN DECISION:
    We separate /health and /health/db intentionally.

    /health:
        Returns immediately — just confirms FastAPI is running.
        Even if MySQL is down, this should return 200 OK.
        Used by: load balancers, Kubernetes liveness probes.

    /health/db:
        Attempts a real MySQL query — confirms full stack is working.
        May return 503 if MySQL is unreachable.
        Used by: developers, monitoring dashboards, readiness probes.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.database import check_db_connection
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Create a router — FastAPI's way of grouping related endpoints
# The prefix "/health" means all routes here are under /health
router = APIRouter(
    prefix="/health",
    tags=["Health"],  # Groups endpoints in the /docs UI
)


# =============================================================================
# GET /health
# =============================================================================

@router.get(
    "",
    summary="API Liveness Check",
    description=(
        "Basic health check confirming the API server is running. "
        "Does not check database connectivity. Always returns 200 OK if the server is up."
    ),
    response_description="API health status",
)
def health_check():
    """
    Basic liveness check — confirms the FastAPI server is running.

    Returns:
        200 OK with application info and timestamp.

    Example response:
        {
            "status": "healthy",
            "app_name": "Clinical Analytics MVP",
            "version": "0.1.0",
            "environment": "development",
            "timestamp": "2024-01-15T10:30:45.123456+00:00"
        }
    """
    logger.debug("GET /health called")

    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# GET /health/db
# =============================================================================

@router.get(
    "/db",
    summary="Database Health Check",
    description=(
        "Full health check including MySQL database connectivity. "
        "Returns 200 if MySQL is reachable, 503 if not."
    ),
    response_description="API and database health status",
)
def database_health_check():
    """
    Full health check — confirms both API and MySQL are working.

    Attempts a real MySQL connection and runs SELECT 1.

    Returns:
        200 OK  — if MySQL connection succeeds
        503     — if MySQL connection fails (with error details)

    Example success response:
        {
            "status": "healthy",
            "api": "healthy",
            "database": {
                "status": "healthy",
                "message": "MySQL connection successful",
                "host": "localhost",
                "port": 3306,
                "database": "clinical_analytics_db"
            },
            "timestamp": "2024-01-15T10:30:45.123456+00:00"
        }
    """
    logger.info("GET /health/db called — checking MySQL connection")

    db_status = check_db_connection()

    # Determine HTTP status code based on DB health
    # 200 = everything OK, 503 = Service Unavailable (DB down)
    http_status = (
        status.HTTP_200_OK
        if db_status["status"] == "healthy"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    if db_status["status"] != "healthy":
        logger.warning(f"Database health check failed: {db_status['message']}")

    response_body = {
        "status": db_status["status"],
        "api": "healthy",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return JSONResponse(content=response_body, status_code=http_status)
