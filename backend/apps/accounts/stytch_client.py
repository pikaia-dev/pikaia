"""
Stytch B2B client wrapper.

Provides a singleton client instance configured from Django settings.
"""

from functools import lru_cache
from typing import Any

import requests  # type: ignore[import-untyped]
import stytch
from django.conf import settings
from stytch.core.http.client import SyncClient


class _TimeoutSession(requests.Session):
    """Session subclass that enforces a default timeout on every request.

    The Stytch SDK's SyncClient uses requests.Session without setting a
    timeout, which means requests can hang indefinitely. Passing this
    session forces a bounded timeout on all Stytch API calls.
    """

    def __init__(self, timeout: int) -> None:
        super().__init__()
        self.timeout = timeout

    def request(self, *args: Any, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return super().request(*args, **kwargs)


@lru_cache(maxsize=1)
def get_stytch_client() -> stytch.B2BClient:
    """
    Get configured Stytch B2B client (singleton).

    Uses lru_cache to ensure only one client instance is created.
    Injects a timeout-enforcing requests.Session into the sync HTTP client.
    """
    client = stytch.B2BClient(
        project_id=settings.STYTCH_PROJECT_ID,
        secret=settings.STYTCH_SECRET,
    )

    timeout_session = _TimeoutSession(timeout=settings.EXTERNAL_API_TIMEOUT_STYTCH)
    client.sync_client = SyncClient(
        project_id=settings.STYTCH_PROJECT_ID,
        secret=settings.STYTCH_SECRET,
        session=timeout_session,
    )

    return client
