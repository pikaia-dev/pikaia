"""
Production settings.

Security-hardened settings for deployed environments.
All secrets are read from environment variables (injected via ECS Task Definition).

IMPORTANT: This module validates that all required secrets are present at startup.
Missing secrets will cause the application to crash immediately with a clear error
rather than failing silently at runtime.
"""

import logging

from .base import *  # noqa: F403
from .base import parse_comma_list, settings

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

# CORS - read from environment, required for frontend to work
CORS_ALLOWED_ORIGINS = parse_comma_list(settings.CORS_ALLOWED_ORIGINS or "")

if not CORS_ALLOWED_ORIGINS:
    logging.getLogger(__name__).warning(
        "CORS_ALLOWED_ORIGINS is empty. Frontend API calls may be blocked."
    )
