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
        "django.security.DisallowedHost": {
            "handlers": [],
            "propagate": False,
        },
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
    "STRIPE_WEBHOOK_SECRET": settings.STRIPE_WEBHOOK_SECRET,
    "STYTCH_WEBHOOK_SECRET": settings.STYTCH_WEBHOOK_SECRET,
    "FIELD_ENCRYPTION_KEY": settings.FIELD_ENCRYPTION_KEY,
    "CORS_ALLOWED_ORIGINS": settings.CORS_ALLOWED_ORIGINS,
}

# Secrets that have obviously insecure defaults
_INSECURE_DEFAULTS = {
    "SECRET_KEY": "django-insecure-change-me-in-production",  # nosec B105
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

    # FIELD_ENCRYPTION_KEY must differ from SECRET_KEY to limit blast radius
    if (
        settings.FIELD_ENCRYPTION_KEY
        and settings.SECRET_KEY
        and settings.FIELD_ENCRYPTION_KEY == settings.SECRET_KEY
    ):
        insecure.append("FIELD_ENCRYPTION_KEY (must not equal SECRET_KEY)")

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
# Convert header name to Django's HTTP_ prefixed format (e.g. X-Forwarded-Proto -> HTTP_X_FORWARDED_PROTO)
_ssl_header = settings.PROXY_SSL_HEADER.upper().replace("-", "_")
SECURE_PROXY_SSL_HEADER = (f"HTTP_{_ssl_header}", "https")

# Additional security headers (OWASP recommendations)
SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME-type sniffing
X_FRAME_OPTIONS = "DENY"  # Clickjacking protection (explicit, don't rely on default)
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"  # Control referrer leakage
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"  # Isolate browsing context

# Use the original host header from CloudFront, not the ALB's internal hostname
# This ensures redirects go to your domain, not the ALB DNS name
USE_X_FORWARDED_HOST = True

# CORS - read from environment, required for frontend to work
# (validated as a required setting above; empty value fails startup)
CORS_ALLOWED_ORIGINS = parse_comma_list(settings.CORS_ALLOWED_ORIGINS or "")

# Include both CORS origins and WebAuthn origin for CSRF protection
CSRF_TRUSTED_ORIGINS = list(
    {
        *CORS_ALLOWED_ORIGINS,
        *parse_comma_list(settings.WEBAUTHN_ORIGIN),
    }
)

# =============================================================================
# Sentry Error Tracking
# =============================================================================
if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    def _is_management_shell_error(event):
        """Check if the error originated from `manage.py shell -c ...`."""
        for entry in event.get("exception", {}).get("values", []):
            for frame in entry.get("stacktrace", {}).get("frames", []):
                if (
                    frame.get("module") == "django.core.management.commands.shell"
                    and frame.get("function") == "handle"
                ):
                    return True
        return False

    def _before_send(event, hint):
        """Filter out noisy errors before they reach Sentry.

        Drops:
        - DisallowedHost errors: bot/scanner noise hitting the ALB IP directly.
        - Management shell errors: ad-hoc `manage.py shell -c` commands that fail.
        """
        exc_info = hint.get("exc_info")
        if exc_info:
            exc_type = exc_info[0]
            if exc_type and exc_type.__name__ == "DisallowedHost":
                return None

        if _is_management_shell_error(event):
            return None

        return event

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        send_default_pii=False,
        environment="production",
        before_send=_before_send,
    )

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

# =============================================================================
# Database Timeout Protection
# =============================================================================
# Enforce a statement timeout in production to prevent runaway queries from
# holding locks and exhausting connections. Overrides the base.py default of 0
# (no timeout). The value comes from DB_STATEMENT_TIMEOUT_MS env var, falling
# back to 30 seconds if unset.
_statement_timeout_ms = settings.DB_STATEMENT_TIMEOUT_MS or 30_000
DATABASES["default"].setdefault("OPTIONS", {})  # noqa: F405
DATABASES["default"]["OPTIONS"]["options"] = (  # noqa: F405
    f"-c statement_timeout={_statement_timeout_ms}"
)

# Connection reuse — avoid per-request TCP+SSL handshake overhead.
# Threads keep persistent connections up to DB_CONN_MAX_AGE; health checks
# detect stale connections before reuse. Verify aggregate connection count
# across all tasks against your PostgreSQL max_connections setting.
DATABASES["default"]["CONN_MAX_AGE"] = settings.DB_CONN_MAX_AGE  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405
