"""
Production settings.

Security-hardened settings for deployed environments.
All secrets are read from environment variables (injected via ECS Task Definition).
"""

from .base import *  # noqa: F403
from .base import settings

DEBUG = False
ALLOWED_HOSTS = [h.strip() for h in settings.ALLOWED_HOSTS.split(",") if h.strip()]

# Security settings (non-negotiables from RULES.md)
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# CORS - requires full URLs (e.g. "https://app.example.com")
# TODO: Add CORS_ALLOWED_ORIGINS env var when deploying
CORS_ALLOWED_ORIGINS: list[str] = []
