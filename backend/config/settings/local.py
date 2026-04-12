"""
Local development settings.

Extends base settings with development-friendly defaults.
"""

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# Field-level encryption key for local dev and tests. Must be set explicitly
# here (not only in base.py) because Django's test runner forces DEBUG=False,
# disabling the SECRET_KEY fallback in `get_fernet()`.
_LOCAL_FIELD_ENCRYPTION_KEY_FALLBACK = "local-dev-field-encryption-key-not-for-production"  # noqa: S105
FIELD_ENCRYPTION_KEY = FIELD_ENCRYPTION_KEY or _LOCAL_FIELD_ENCRYPTION_KEY_FALLBACK  # noqa: F405

# Disable subscription gating for local development
SUBSCRIPTION_GATING_ENABLED = False

# CORS settings for local development
# Cannot use CORS_ALLOW_ALL_ORIGINS with credentials: 'include'
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True

# Include both CORS origins and WebAuthn origin for CSRF protection
CSRF_TRUSTED_ORIGINS = list({*CORS_ALLOWED_ORIGINS, WEBAUTHN_ORIGIN})  # noqa: F405

# =============================================================================
# Structured Logging Configuration (Development)
# =============================================================================
# Configure structlog with pretty console output for local development.
# Colors and human-readable format make debugging easier.
from apps.core.logging import configure_logging  # noqa: E402

configure_logging(json_format=False, log_level="DEBUG")
