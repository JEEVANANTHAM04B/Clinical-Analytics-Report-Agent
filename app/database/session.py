"""
app/database/session.py
=======================
SQLAlchemy Database Session and Engine Management

WHY THIS MODULE EXISTS:
    Centralizes engine reuse, session creation, dependency injection for FastAPI,
    and metadata table initialization for Phase 5.

ARCHITECTURE:
    - Reuses the single global SQLAlchemy engine created in app.core.database.
    - Avoids creating a new engine for every request.
    - Provides get_db dependency for route handlers.
    - Provides init_db() to safely create metadata tables without affecting clinical tables.
"""

from typing import Generator
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.database import (
    engine,
    SessionLocal,
    Base,
    get_db_session,
    get_db_context,
    check_db_connection,
)
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# Dependency alias for FastAPI route injection
get_db = get_db_session


def init_db() -> dict:
    """
    Initializes metadata tables in MySQL.

    SAFETY GUARANTEES:
      - Uses Base.metadata.create_all() which runs 'CREATE TABLE IF NOT EXISTS'.
      - NEVER drops any existing tables.
      - NEVER creates clinical data tables automatically (those are created upon dataset loading).
      - Creates ONLY metadata tables:
          1. dataset_versions
          2. dataset_columns
          3. approved_relationships
          4. audit_logs

    Returns:
        dict with status, existing_tables, and metadata_tables
    """
    # Import models so they are registered with Base.metadata
    from app.database import models  # noqa: F401

    logger.info("Initializing MySQL metadata tables...")

    try:
        # Create all tables registered to Base (only metadata tables)
        Base.metadata.create_all(bind=engine)

        inspector = inspect(engine)
        all_tables = inspector.get_table_names()

        metadata_tables = [
            "dataset_versions",
            "dataset_columns",
            "approved_relationships",
            "audit_logs",
        ]

        verified = [t for t in metadata_tables if t in all_tables]

        logger.info(f"MySQL metadata tables verified: {verified}")
        return {
            "status": "success",
            "message": "Metadata tables verified successfully",
            "tables": verified,
            "all_tables": all_tables,
        }

    except Exception as e:
        logger.exception(f"Error during metadata table initialization: {e}")
        raise
