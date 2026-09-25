"""
app/core/database.py
=====================
MySQL Database Connection Layer

WHY SQLAlchemy?
    SQLAlchemy is Python's most powerful database toolkit. It gives us:
      1. Connection pooling   — reuses connections efficiently (no overhead per request)
      2. Abstraction          — same Python code works with MySQL, PostgreSQL, SQLite
      3. Safety               — parameterized queries prevent SQL injection
      4. Session management   — clean open/close lifecycle for every request

HOW CONNECTION POOLING WORKS:
    Instead of opening a new MySQL connection for every API request
    (which is slow), SQLAlchemy maintains a POOL of open connections.
    When a request comes in, it borrows a connection from the pool.
    When done, it returns it. Much faster.

    Pool settings here are tuned for development. Production will need
    larger pool sizes.

ARCHITECTURE NOTE:
    In Phase 1, we ONLY verify connectivity.
    We do NOT define any clinical database tables yet — that's Phase 2.

USAGE in other modules:
    from app.core.database import get_db_session, check_db_connection

    # In a FastAPI route (dependency injection):
    def my_route(db: Session = Depends(get_db_session)):
        result = db.execute(text("SELECT ..."))
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# SQLAlchemy Engine
# =============================================================================
# The engine is the core connection manager. Create it ONCE at module load.
# All sessions are created FROM this engine.
#
# Pool settings explained:
#   pool_pre_ping=True   — Before using a connection, test it's still alive.
#                          Prevents "MySQL server has gone away" errors.
#   pool_size=5          — Keep 5 connections open in the pool.
#   max_overflow=10      — Allow up to 10 extra connections during bursts.
#   pool_recycle=3600    — Recycle connections every 1 hour (MySQL timeout safety).
# =============================================================================

engine = create_engine(
    settings.mysql_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    echo=False,  # Set to True temporarily to see every SQL query (useful for debugging)
)

# Session factory — creates new Session objects bound to our engine
SessionLocal = sessionmaker(
    autocommit=False,  # We manage commits manually (safer, gives us rollback control)
    autoflush=False,   # Don't auto-flush before queries (we control this)
    bind=engine,
)


# =============================================================================
# Declarative Base
# =============================================================================
# All SQLAlchemy ORM models (database table definitions) will inherit from
# this Base class. Not used in Phase 1, but defined here so future phases
# (table definitions, migrations) can import it from one place.
# =============================================================================

class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    Future usage (Phase 2+):
        from app.core.database import Base

        class Patient(Base):
            __tablename__ = "patients"
            id = Column(Integer, primary_key=True)
            ...
    """
    pass


# =============================================================================
# Session Dependency — For FastAPI Dependency Injection
# =============================================================================

def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.

    HOW IT WORKS:
        FastAPI calls this function for every request that needs a DB session.
        The 'yield' creates a session, gives it to the route handler,
        then the 'finally' block closes it when the request is done —
        even if an error occurred.

    USAGE in routes:
        from sqlalchemy.orm import Session
        from fastapi import Depends
        from app.core.database import get_db_session

        @router.get("/patients")
        def get_patients(db: Session = Depends(get_db_session)):
            result = db.execute(text("SELECT * FROM patients"))
            return result.fetchall()
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database session error, rolling back: {e}")
        raise
    finally:
        db.close()


# =============================================================================
# Context Manager — For Non-FastAPI Use (scripts, CLI, background tasks)
# =============================================================================

@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions outside of FastAPI routes.

    USAGE in scripts or background tasks:
        from app.core.database import get_db_context

        with get_db_context() as db:
            result = db.execute(text("SELECT 1"))
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database context error, rolling back: {e}")
        raise
    finally:
        db.close()


# =============================================================================
# Health Check Function
# =============================================================================

def check_db_connection() -> dict:
    """
    Tests the MySQL database connection.

    Executes a minimal SQL query (SELECT 1) to verify:
      1. The engine can connect to MySQL
      2. Authentication credentials are correct
      3. The database exists and is accessible

    Returns:
        dict with keys: status, message, host, port, database

    Called by the /health/db endpoint.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 AS connection_test"))
            row = result.fetchone()

            if row and row[0] == 1:
                logger.info(
                    f"MySQL connection check: OK | "
                    f"host={settings.MYSQL_HOST}:{settings.MYSQL_PORT} | "
                    f"database={settings.MYSQL_DATABASE}"
                )
                return {
                    "status": "healthy",
                    "message": "MySQL connection successful",
                    "host": settings.MYSQL_HOST,
                    "port": settings.MYSQL_PORT,
                    "database": settings.MYSQL_DATABASE,
                }

    except OperationalError as e:
        # OperationalError covers: host not reachable, access denied, DB not found
        error_msg = str(e.orig) if e.orig else str(e)
        logger.error(f"MySQL connection failed (OperationalError): {error_msg}")
        return {
            "status": "unhealthy",
            "message": f"MySQL connection failed: {error_msg}",
            "host": settings.MYSQL_HOST,
            "port": settings.MYSQL_PORT,
            "database": settings.MYSQL_DATABASE,
        }

    except SQLAlchemyError as e:
        logger.error(f"MySQL connection failed (SQLAlchemyError): {e}")
        return {
            "status": "unhealthy",
            "message": f"Database error: {str(e)}",
            "host": settings.MYSQL_HOST,
            "port": settings.MYSQL_PORT,
            "database": settings.MYSQL_DATABASE,
        }
