"""
app/config.py
=============
Centralized Configuration Management

Phase 2 additions:
    MAX_UPLOAD_SIZE_MB  — Maximum allowed file upload size in megabytes
    UPLOAD_DIRECTORY    — Local directory where uploaded files are stored

WHY THIS EXISTS:
    Instead of calling os.getenv("MYSQL_HOST") scattered across 20 files,
    we load ALL environment variables ONCE here using Pydantic Settings.

    Every other module imports 'settings' from this file.
    This means:
      - One place to see all configuration
      - Type validation (e.g., MYSQL_PORT is always an int)
      - Automatic .env file loading
      - Easy to test (swap settings for test config)

HOW IT WORKS:
    Pydantic Settings automatically:
      1. Reads your .env file
      2. Reads actual environment variables
      3. Validates types (str, int, bool, etc.)
      4. Makes everything available as settings.VARIABLE_NAME
"""

from urllib.parse import quote_plus
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings loaded from .env file.

    All variables here correspond to keys in your .env file.
    Pydantic validates types automatically — MYSQL_PORT will always
    be an integer even though .env stores it as a string.
    """

    # ─── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "Clinical Analytics MVP"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # ─── API Server ───────────────────────────────────────────────────────────
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8001

    # ─── MySQL Database ───────────────────────────────────────────────────────
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "clinical_analytics_db"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""

    # ─── Logging ──────────────────────────────────────────────────────────────
    LOG_LEVEL: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"

    LOG_FORMAT: Literal["json", "text"] = "text"

    # ─── Phase 2: File Upload Settings ───────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50           # Maximum upload size in MB (50 MB default)
    UPLOAD_DIRECTORY: str = "data/uploads" # Local path for uploaded datasets

    # ─── Pydantic Settings Configuration ─────────────────────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ─── Derived Properties ───────────────────────────────────────────────────
    @property
    def mysql_url(self) -> str:
        """
        Constructs the SQLAlchemy MySQL connection URL.

        Special characters in the username/password are URL-encoded
        before constructing the connection string.

        This is important because characters such as:
            #  @  :  /  ?  %
        have special meanings inside URLs.

        Format:
            mysql+pymysql://user:password@host:port/database

        WHY pymysql?
            PyMySQL is a pure-Python MySQL driver. It doesn't require
            separate C library installation, making it easier to set up
            on Windows. SQLAlchemy uses PyMySQL as the MySQL adapter.
        """

        encoded_user = quote_plus(self.MYSQL_USER)
        encoded_password = quote_plus(self.MYSQL_PASSWORD)

        return (
            f"mysql+pymysql://"
            f"{encoded_user}:{encoded_password}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}"
            f"/{self.MYSQL_DATABASE}"
        )

    @property
    def is_development(self) -> bool:
        """Returns True if running in development mode."""
        return self.ENVIRONMENT == "development"


# =============================================================================
# Singleton settings instance
# =============================================================================
# This is the ONE instance used everywhere in the app.
#
# Import like:
#     from app.config import settings
#
# Then use:
#     settings.MYSQL_HOST
#     settings.mysql_url
# =============================================================================

settings = Settings()