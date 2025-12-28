"""
Stytch B2B client wrapper.

Provides a singleton client instance configured from Django settings.
"""

from functools import lru_cache

import stytch
from django.conf import settings


@lru_cache(maxsize=1)
def get_stytch_client() -> stytch.B2BClient:
    """
    Get configured Stytch B2B client (singleton).

    Uses lru_cache to ensure only one client instance is created.
    """
    return stytch.B2BClient(
        project_id=settings.STYTCH_PROJECT_ID,
        secret=settings.STYTCH_SECRET,
    )
