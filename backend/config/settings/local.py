"""
Local development settings.

Extends base settings with development-friendly defaults.
"""

from .base import *  # noqa: F403
from .base import settings

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True
