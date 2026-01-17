"""
Local development settings.

Extends base settings with development-friendly defaults.
"""

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

# =============================================================================
# Structured Logging Configuration (Development)
# =============================================================================
# Configure structlog with pretty console output for local development.
# Colors and human-readable format make debugging easier.
from apps.core.logging import configure_logging

configure_logging(json_format=False, log_level="DEBUG")
