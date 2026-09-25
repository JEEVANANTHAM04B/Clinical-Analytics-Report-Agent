"""
app/main.py
============
FastAPI Application Entry Point

WHY THIS FILE IS IMPORTANT:
    This is the file uvicorn loads when you run:
        uvicorn app.main:app --reload --port 8001

    'app.main' = the module (app/main.py)
    'app'      = the FastAPI() instance created in this file

WHAT HAPPENS AT STARTUP:
    1. Python imports this module
    2. Settings are loaded from .env via config.py
    3. Logging is configured via logging_config.py
    4. FastAPI app is created with metadata
    5. Routers (like health) are registered
    6. lifespan events run (startup/shutdown logic)
    7. uvicorn starts serving HTTP requests

WHAT IS lifespan?
    FastAPI's modern way to run code at startup and shutdown.
    We use it to:
      - Log that the server has started
      - (Future) Initialize DB connection pool, load ML models, etc.
      - (Future) Clean up resources on shutdown
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging_config import setup_logging, get_logger
from app.api import health as health_router
from app.api import ingestion as ingestion_router
from app.api.relationships import router as relationships_router
from app.api.database import router as database_router
from app.database.session import init_db
from app.core.database import check_db_connection

# =============================================================================
# Logging — Must be set up BEFORE anything else logs
# =============================================================================
# Called here so logging is ready before the app starts processing requests.
setup_logging()
logger = get_logger(__name__)


# =============================================================================
# Lifespan — Startup and Shutdown Events
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown events.

    WHY asynccontextmanager?
        FastAPI recommends this modern pattern over the older @app.on_event()
        decorators. Everything before 'yield' runs at startup, everything
        after 'yield' runs at shutdown.

    STARTUP:
        - Log that the server is live
        - (Future phases: init connection pools, load embeddings model, etc.)

    SHUTDOWN:
        - Log graceful shutdown
        - (Future phases: flush queues, close connections, etc.)
    """
    # ── STARTUP ────────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"[STARTUP] {settings.APP_NAME} v{settings.APP_VERSION} starting up")
    logger.info(f"   Environment   : {settings.ENVIRONMENT}")
    logger.info(f"   API Server    : http://{settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"   Docs UI       : http://{settings.API_HOST}:{settings.API_PORT}/docs")
    logger.info(f"   MySQL Host    : {settings.MYSQL_HOST}:{settings.MYSQL_PORT}")
    logger.info(f"   Database      : {settings.MYSQL_DATABASE}")
    logger.info(f"   Upload Dir    : {settings.UPLOAD_DIRECTORY}")
    logger.info(f"   Max Upload    : {settings.MAX_UPLOAD_SIZE_MB} MB")
    logger.info("=" * 60)

    # Phase 5: Verify MySQL connection and initialize metadata tables safely
    try:
        db_status = check_db_connection()
        if db_status.get("status") == "healthy":
            logger.info("MySQL connection verified successfully.")
            init_res = init_db()
            logger.info(f"Metadata tables verified: {init_res.get('tables', [])}")
        else:
            logger.warning(f"MySQL connection check returned: {db_status}")
    except Exception as e:
        logger.warning(f"Could not verify/initialize MySQL metadata tables at startup: {e}")

    yield  # ← Application is running here (serving requests)

    # ── SHUTDOWN ───────────────────────────────────────────────────────────────
    logger.info(f"[SHUTDOWN] {settings.APP_NAME} shutting down gracefully")


# =============================================================================
# FastAPI Application Instance
# =============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-Powered Healthcare Analytics and Reporting Platform. "
        "Provides clinical data analytics, LLM-assisted insights, "
        "and automated PDF report generation."
    ),
    docs_url="/docs",       # Swagger UI → http://localhost:8001/docs
    redoc_url="/redoc",     # ReDoc UI   → http://localhost:8001/redoc
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# =============================================================================
# CORS Middleware
# =============================================================================
# CORS = Cross-Origin Resource Sharing.
# This allows a frontend (running on a different port, like React on 3000)
# to make API calls to our FastAPI server on 8001.
# In development, we allow all origins. TIGHTEN THIS in production.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Register Routers
# =============================================================================
# Routers are FastAPI's way of organizing endpoints into separate files.
# Each router has a prefix (like "/health") that gets prepended to all
# routes inside it.

app.include_router(health_router.router)
app.include_router(ingestion_router.router)
app.include_router(relationships_router)
app.include_router(database_router)

# =============================================================================
# Root Endpoint
# =============================================================================

@app.get(
    "/",
    tags=["Root"],
    summary="API Root",
    description="Returns basic API information and links to documentation.",
)
def root():
    """
    Root endpoint — confirms the API is running and provides navigation links.

    This is what you see when you open http://localhost:8001/ in the browser.
    """
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "phase": "Phase 5 — MySQL Clinical Data Layer",
        "docs": f"http://{settings.API_HOST}:{settings.API_PORT}/docs",
        "endpoints": {
            "health": f"http://{settings.API_HOST}:{settings.API_PORT}/health",
            "health_db": f"http://{settings.API_HOST}:{settings.API_PORT}/health/db",
            "upload": f"http://{settings.API_HOST}:{settings.API_PORT}/ingestion/upload",
            "analyze": f"http://{settings.API_HOST}:{settings.API_PORT}/ingestion/analyze",
            "relationships_candidates": f"http://{settings.API_HOST}:{settings.API_PORT}/relationships/candidates",
            "relationships_review": f"http://{settings.API_HOST}:{settings.API_PORT}/relationships/review",
            "relationships_approved": f"http://{settings.API_HOST}:{settings.API_PORT}/relationships/approved",
            "relationships_rejected": f"http://{settings.API_HOST}:{settings.API_PORT}/relationships/rejected",
            "database_load": f"http://{settings.API_HOST}:{settings.API_PORT}/database/load",
            "database_versions": f"http://{settings.API_HOST}:{settings.API_PORT}/database/versions",
            "database_relationships": f"http://{settings.API_HOST}:{settings.API_PORT}/database/relationships",
            "database_audit_logs": f"http://{settings.API_HOST}:{settings.API_PORT}/database/audit-logs",
        },
    }
