"""
Core middleware.
"""

import time
from collections.abc import Callable
from uuid import UUID, uuid4

from django.http import HttpRequest, HttpResponse
from stytch.core.response_base import StytchError

from apps.core.auth import AuthContext
from apps.core.logging import bind_contextvars, clear_contextvars, get_logger
from apps.core.utils import get_client_ip
from apps.events.services import set_correlation_id

logger = get_logger(__name__)

# Truncate user-agent to avoid bloating event payloads
MAX_USER_AGENT_LENGTH = 512


class CorrelationIdMiddleware:
    """
    Generate or extract correlation ID for request tracing.

    If X-Correlation-ID header is present, uses that value.
    Otherwise generates a new UUID4.

    Binds structured logging context with Datadog-compatible field names:
    - trace_id: Correlation ID for distributed tracing
    - http.method: Request method
    - http.url_details.path: Request path
    - http.status_code: Response status code (added on response)
    - duration_ms: Request duration in milliseconds (added on response)
    """

    HEADER_NAME = "X-Correlation-ID"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Extract from header or generate new
        correlation_id_str = request.headers.get(self.HEADER_NAME)

        if correlation_id_str:
            try:
                correlation_id = UUID(correlation_id_str)
            except ValueError:
                correlation_id = uuid4()
        else:
            correlation_id = uuid4()

        # Store on request for access in views
        request.correlation_id = correlation_id  # type: ignore[attr-defined]

        # Set in event services context
        set_correlation_id(correlation_id)

        # Extract request context for audit logging
        client_ip = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:MAX_USER_AGENT_LENGTH]

        # Clear any stale context and bind request metadata for structured logging
        clear_contextvars()
        bind_contextvars(
            correlation_id=str(correlation_id),
            **{
                "http.method": request.method,
                "http.url_details.path": request.path,
                "request.ip_address": client_ip,
                "request.user_agent": user_agent,
            },
        )

        start_time = time.monotonic()

        try:
            response = self.get_response(request)

            # Bind response metadata
            duration_ms = (time.monotonic() - start_time) * 1000
            bind_contextvars(
                duration_ms=round(duration_ms, 2),
                **{"http.status_code": response.status_code},
            )

            # Add correlation ID to response headers for client debugging
            response[self.HEADER_NAME] = str(correlation_id)
            response["X-Request-ID"] = str(correlation_id)  # Alias for compatibility

            return response
        finally:
            # Clear context to prevent leakage between requests (especially in async workers)
            set_correlation_id(None)
            clear_contextvars()


class StytchAuthMiddleware:
    """
    Validates Stytch session JWT from Authorization header.

    Sets request.auth with user, member, and organization for authenticated
    requests. Allows unauthenticated requests to pass through (authorization
    enforced at endpoint level).

    The auth.failed flag distinguishes between:
    - No auth attempted (failed=False, user=None)
    - Auth attempted but failed (failed=True, user=None)

    After successful authentication, binds user/org context to structured logging:
    - usr.id: User identifier
    - usr.email: User email
    - organization.id: Organization Stytch ID
    """

    # Paths that don't require authentication
    PUBLIC_PATHS = {
        "/api/v1/health",
        "/api/v1/auth/magic-link/send",
        "/api/v1/auth/magic-link/authenticate",
        "/api/v1/auth/discovery/create-org",
        "/api/v1/auth/discovery/exchange",
        "/api/v1/auth/mobile/provision",
        "/admin/",
    }

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Initialize auth context
        request.auth = AuthContext()  # type: ignore[attr-defined]

        # Skip auth for public paths
        if self._is_public_path(request.path):
            return self.get_response(request)

        # Extract JWT from Authorization header or Cookies
        auth_header = request.headers.get("Authorization", "")
        session_jwt = None

        if auth_header.startswith("Bearer "):
            session_jwt = auth_header.replace("Bearer ", "")
        else:
            # Fallback to cookies (used after discovery/create-org)
            session_jwt = request.COOKIES.get("stytch_session_jwt")

        if session_jwt:
            self._authenticate_jwt(request, session_jwt)

        return self.get_response(request)

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        return any(path.startswith(public_path) for public_path in self.PUBLIC_PATHS)

    def _authenticate_jwt(self, request: HttpRequest, session_jwt: str) -> None:
        """
        Validate JWT and populate request.auth with user/member/org.

        Uses a two-tier strategy for performance:
        1. Local JWT verification (fast, no API call)
        2. Local DB lookup for member/user/org

        Falls back to full Stytch API call only when:
        - Member doesn't exist locally (first-time login)
        - Local JWT verification fails (triggers fresh API check)

        Role changes are synced via Stytch webhooks (handle_member_updated),
        so we don't need to call Stytch API on every request.
        """
        # Import here to avoid circular imports
        from apps.accounts.models import Member
        from apps.accounts.services import sync_session_to_local
        from apps.accounts.stytch_client import get_stytch_client

        client = get_stytch_client()
        auth: AuthContext = request.auth  # type: ignore[attr-defined]

        try:
            # Step 1: Local JWT verification (no API call)
            # max_token_age_seconds=None uses the session's expiration from JWT
            local_response = client.sessions.authenticate_jwt(
                session_jwt=session_jwt,
                max_token_age_seconds=None,
            )

            # Extract member_id from JWT claims
            stytch_member_id = local_response.member_session.member_id

            # Step 2: Look up member from local DB
            member = (
                Member.objects.select_related("user", "organization")
                .filter(stytch_member_id=stytch_member_id)
                .first()
            )

            if member:
                # Fast path: member exists locally, use cached data
                auth.user = member.user
                auth.member = member
                auth.organization = member.organization
            else:
                # Slow path: first-time login, sync from Stytch
                # Call the full API to get current data
                logger.info(
                    "Member %s not found locally, syncing from Stytch",
                    stytch_member_id,
                )
                full_response = client.sessions.authenticate(session_jwt=session_jwt)
                user, member, org = sync_session_to_local(
                    stytch_member=full_response.member,
                    stytch_organization=full_response.organization,
                )
                auth.user = user
                auth.member = member
                auth.organization = org

            # Bind user/org context to structured logging (Datadog-compatible field names)
            bind_contextvars(
                **{
                    "usr.id": str(member.user.id),
                    "usr.email": member.user.email,
                    "organization.id": member.organization.stytch_org_id
                    if member.organization
                    else None,
                }
            )

        except StytchError as e:
            # Invalid/expired JWT - mark as failed so endpoints can distinguish
            # "no auth attempted" from "auth attempted but failed"
            auth.failed = True
            logger.debug("jwt_auth_failed", error_message=e.details.error_message)
        except Exception:
            # Catch any other exception (network errors, timeouts, etc.)
            # Also mark as failed - potential security issue
            auth.failed = True
            logger.exception("jwt_auth_unexpected_error")
