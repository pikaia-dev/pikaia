"""
Production settings.

Security-hardened settings for deployed environments.
All secrets are read from environment variables (injected via ECS Task Definition).

IMPORTANT: This module validates that all required secrets are present at startup.
Missing secrets will cause the application to crash immediately with a clear error
rather than failing silently at runtime.
"""

# =============================================================================
# Structured Logging Configuration
# =============================================================================
# Configure structlog for JSON output in production.
# This enables easy querying in CloudWatch Logs Insights, Datadog, and Elastic.
from apps.core.logging import configure_logging

from .base import *  # noqa: F403
from .base import parse_comma_list, settings

configure_logging(json_format=True, log_level="INFO")

# Django's LOGGING config - minimal since structlog handles most logging.
# This ensures Django's internal loggers (request errors, etc.) still work.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# =============================================================================
# Required Secrets Validation
# =============================================================================
# These secrets MUST be set in production. The app will refuse to start without them.

_REQUIRED_SECRETS = {
    "SECRET_KEY": settings.SECRET_KEY,
    "STYTCH_PROJECT_ID": settings.STYTCH_PROJECT_ID,
    "STYTCH_SECRET": settings.STYTCH_SECRET,
    "STRIPE_SECRET_KEY": settings.STRIPE_SECRET_KEY,
    "STRIPE_PRICE_ID": settings.STRIPE_PRICE_ID,
}

# Secrets that have obviously insecure defaults
_INSECURE_DEFAULTS = {
    "SECRET_KEY": "django-insecure-change-me-in-production",
}


def _validate_production_secrets() -> None:
    """Validate all required secrets are present and not using insecure defaults."""
    missing = []
    insecure = []

    for name, value in _REQUIRED_SECRETS.items():
        if not value or (isinstance(value, str) and not value.strip()):
            missing.append(name)
        elif name in _INSECURE_DEFAULTS and value == _INSECURE_DEFAULTS[name]:
            insecure.append(name)

    errors = []
    if missing:
        errors.append(f"Missing required environment variables: {', '.join(missing)}")
    if insecure:
        errors.append(f"Insecure default values detected: {', '.join(insecure)}")

    if errors:
        raise ValueError(
            "Production configuration error!\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\n\nSet these in your environment or ECS Task Definition."
        )


# Run validation at module load (app startup)
_validate_production_secrets()


# =============================================================================
# Production Settings
# =============================================================================

DEBUG = False
ALLOWED_HOSTS = parse_comma_list(settings.ALLOWED_HOSTS)

if not ALLOWED_HOSTS:
    raise ValueError(
        "Production configuration error!\n"
        "  - ALLOWED_HOSTS is empty. Set it to your domain(s), e.g. 'api.example.com'"
    )

# Security settings (non-negotiables from RULES.md)
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health$"]  # ALB health checks use HTTP
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_CLOUDFRONT_FORWARDED_PROTO", "https")

# Additional security headers (OWASP recommendations)
SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME-type sniffing
X_FRAME_OPTIONS = "DENY"  # Clickjacking protection (explicit, don't rely on default)
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"  # Control referrer leakage
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"  # Isolate browsing context

# Use the original host header from CloudFront, not the ALB's internal hostname
# This ensures redirects go to b2b.demo.tango.agency, not the ALB DNS name
USE_X_FORWARDED_HOST = True

# CORS - read from environment, required for frontend to work
CORS_ALLOWED_ORIGINS = parse_comma_list(settings.CORS_ALLOWED_ORIGINS or "")

if not CORS_ALLOWED_ORIGINS:
    from apps.core.logging import get_logger

    get_logger(__name__).warning("cors_allowed_origins_empty")

# Validate S3 storage configuration
if settings.USE_S3_STORAGE:
    _required_s3_settings = {
        "AWS_STORAGE_BUCKET_NAME": settings.AWS_STORAGE_BUCKET_NAME,
        "IMAGE_TRANSFORM_URL": settings.IMAGE_TRANSFORM_URL,
    }
    missing_s3 = [k for k, v in _required_s3_settings.items() if not v]
    if missing_s3:
        raise ValueError(
            "Production configuration error!\n"
            f"  - USE_S3_STORAGE is enabled but missing: {', '.join(missing_s3)}"
        )
