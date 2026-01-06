"""
Local development settings.

Extends base settings with development-friendly defaults.
"""

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# CORS settings for local development
# Cannot use CORS_ALLOW_ALL_ORIGINS with credentials: 'include'
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True
