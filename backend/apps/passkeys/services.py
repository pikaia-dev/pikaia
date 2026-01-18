"""
Passkey (WebAuthn) service layer.

Handles passkey registration and authentication using the webauthn library.
Integrates with Stytch for session management after successful authentication.
"""

import logging
import secrets
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from apps.accounts.models import Member, User
from apps.passkeys.models import Passkey

logger = logging.getLogger(__name__)

# Cache key prefixes for challenges
REGISTRATION_CHALLENGE_PREFIX = "passkey:reg:"
AUTHENTICATION_CHALLENGE_PREFIX = "passkey:auth:"
CHALLENGE_TTL_SECONDS = 300  # 5 minutes


@dataclass
class RegistrationOptions:
    """Options returned to client for passkey registration."""

    options_json: dict
    challenge_id: str


@dataclass
class AuthenticationOptions:
    """Options returned to client for passkey authentication."""

    options_json: dict
    challenge_id: str


@dataclass
class AuthenticationResult:
    """Result of successful passkey authentication."""

    user: User
    member: Member
    passkey: Passkey


class PasskeyService:
    """
    Service for WebAuthn passkey operations.

    Handles registration and authentication ceremonies, credential storage,
    and integration with Stytch sessions.
    """

    def __init__(self) -> None:
        self.rp_id = getattr(settings, "WEBAUTHN_RP_ID", "localhost")
        self.rp_name = getattr(settings, "WEBAUTHN_RP_NAME", "Tango B2B")
        self.origin = getattr(settings, "WEBAUTHN_ORIGIN", "http://localhost:5173")

    # --- Registration ---

    def generate_registration_options(
        self,
        user: User,
        member: Member,
    ) -> RegistrationOptions:
        """
        Generate options for passkey registration.

        Args:
            user: The user registering a passkey
            member: The member context for the registration

        Returns:
            Registration options to send to the client
        """
        # Get existing credentials to exclude (prevent re-registration)
        existing_credentials = [
            PublicKeyCredentialDescriptor(
                id=passkey.credential_id,
                transports=[AuthenticatorTransport(t) for t in passkey.transports]
                if passkey.transports
                else None,
            )
            for passkey in user.passkeys.all()
        ]

        options = generate_registration_options(
            rp_id=self.rp_id,
            rp_name=self.rp_name,
            user_id=str(user.id).encode(),
            user_name=user.email,
            user_display_name=user.name or user.email,
            exclude_credentials=existing_credentials,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
        )

        # Store challenge in cache for verification
        challenge_id = secrets.token_urlsafe(32)
        cache_key = f"{REGISTRATION_CHALLENGE_PREFIX}{challenge_id}"
        cache.set(
            cache_key,
            {
                "challenge": bytes_to_base64url(options.challenge),
                "user_id": user.id,
                "member_id": member.id,
            },
            timeout=CHALLENGE_TTL_SECONDS,
        )

        return RegistrationOptions(
            options_json=options_to_json(options),
            challenge_id=challenge_id,
        )

    def verify_registration(
        self,
        user: User,
        challenge_id: str,
        credential_json: dict,
        passkey_name: str,
    ) -> Passkey:
        """
        Verify registration response and store the new passkey.

        Args:
            user: The user registering the passkey
            challenge_id: ID of the registration challenge
            credential_json: The credential response from the browser
            passkey_name: User-friendly name for the passkey

        Returns:
            The created Passkey instance

        Raises:
            ValueError: If verification fails
        """
        # Retrieve and validate challenge
        cache_key = f"{REGISTRATION_CHALLENGE_PREFIX}{challenge_id}"
        challenge_data = cache.get(cache_key)

        if not challenge_data:
            raise ValueError("Registration challenge expired or invalid")

        if challenge_data["user_id"] != user.id:
            raise ValueError("Challenge does not match user")

        # Delete challenge to prevent reuse
        cache.delete(cache_key)

        try:
            verification = verify_registration_response(
                credential=credential_json,
                expected_challenge=base64url_to_bytes(challenge_data["challenge"]),
                expected_rp_id=self.rp_id,
                expected_origin=self.origin,
                require_user_verification=True,
            )
        except Exception as e:
            logger.warning("Passkey registration verification failed: %s", e)
            raise ValueError(f"Registration verification failed: {e}") from e

        # Check if credential already exists
        existing_passkey = (
            Passkey.objects.filter(credential_id=verification.credential_id)
            .select_related("user")
            .first()
        )

        if existing_passkey:
            if existing_passkey.user_id == user.id:
                # Same user, same credential - update name and return existing
                logger.info(
                    "Passkey already exists for user %s, updating name to '%s'",
                    user.email,
                    passkey_name,
                )
                existing_passkey.name = passkey_name
                existing_passkey.save(update_fields=["name", "updated_at"])
                return existing_passkey

            # Check if the existing passkey's user has any active memberships
            has_active_membership = existing_passkey.user.memberships.filter(
                deleted_at__isnull=True
            ).exists()

            if not has_active_membership:
                # User has no active memberships (orphaned) - delete old passkey
                logger.info(
                    "Deleting orphaned passkey for user %s (no active memberships)",
                    existing_passkey.user.email,
                )
                existing_passkey.delete()
            else:
                raise ValueError("This passkey is already registered to another account")

        # Extract transports from the response if available
        transports = []
        if (
            hasattr(credential_json, "response")
            and hasattr(credential_json["response"], "transports")
            or isinstance(credential_json, dict)
            and "response" in credential_json
        ):
            transports = credential_json["response"].get("transports", [])

        # Create passkey record
        passkey = Passkey.objects.create(
            user=user,
            credential_id=verification.credential_id,
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
            name=passkey_name,
            aaguid=str(verification.aaguid) if verification.aaguid else "",
            is_discoverable=True,  # We require resident keys
            backup_eligible=verification.credential_backed_up is not None,
            backup_state=verification.credential_backed_up
            if verification.credential_backed_up is not None
            else False,
            transports=transports,
        )

        logger.info("Passkey registered for user %s: %s", user.email, passkey_name)
        return passkey

    # --- Authentication ---

    def generate_authentication_options(
        self,
        email: str | None = None,
    ) -> AuthenticationOptions:
        """
        Generate options for passkey authentication.

        Args:
            email: Optional email to filter allowed credentials

        Returns:
            Authentication options to send to the client
        """
        allowed_credentials = []

        if email:
            # Get credentials for specific user
            try:
                user = User.objects.get(email=email)
                allowed_credentials = [
                    PublicKeyCredentialDescriptor(
                        id=passkey.credential_id,
                        transports=[AuthenticatorTransport(t) for t in passkey.transports]
                        if passkey.transports
                        else None,
                    )
                    for passkey in user.passkeys.all()
                ]
            except User.DoesNotExist:
                # Return empty options to not leak user existence
                pass

        options = generate_authentication_options(
            rp_id=self.rp_id,
            allow_credentials=allowed_credentials if allowed_credentials else None,
            user_verification=UserVerificationRequirement.REQUIRED,
        )

        # Store challenge in cache
        challenge_id = secrets.token_urlsafe(32)
        cache_key = f"{AUTHENTICATION_CHALLENGE_PREFIX}{challenge_id}"
        cache.set(
            cache_key,
            {
                "challenge": bytes_to_base64url(options.challenge),
                "email": email,
            },
            timeout=CHALLENGE_TTL_SECONDS,
        )

        return AuthenticationOptions(
            options_json=options_to_json(options),
            challenge_id=challenge_id,
        )

    def verify_authentication(
        self,
        challenge_id: str,
        credential_json: dict,
        organization_id: str | None = None,
    ) -> AuthenticationResult:
        """
        Verify authentication response and return the authenticated user.

        Args:
            challenge_id: ID of the authentication challenge
            credential_json: The credential response from the browser
            organization_id: Optional organization ID to validate membership

        Returns:
            AuthenticationResult with user, member, and passkey

        Raises:
            ValueError: If verification fails
        """
        # Retrieve and validate challenge
        cache_key = f"{AUTHENTICATION_CHALLENGE_PREFIX}{challenge_id}"
        challenge_data = cache.get(cache_key)

        if not challenge_data:
            raise ValueError("Authentication challenge expired or invalid")

        # Delete challenge to prevent reuse
        cache.delete(cache_key)

        # Find the passkey by credential ID
        raw_id = credential_json.get("rawId") or credential_json.get("id")
        if not raw_id:
            raise ValueError("Missing credential ID in response")

        credential_id = base64url_to_bytes(raw_id)

        try:
            passkey = Passkey.objects.select_related("user").get(credential_id=credential_id)
        except Passkey.DoesNotExist as e:
            raise ValueError("Passkey not found") from e

        try:
            verification = verify_authentication_response(
                credential=credential_json,
                expected_challenge=base64url_to_bytes(challenge_data["challenge"]),
                expected_rp_id=self.rp_id,
                expected_origin=self.origin,
                credential_public_key=passkey.public_key,
                credential_current_sign_count=passkey.sign_count,
                require_user_verification=True,
            )
        except Exception as e:
            logger.warning("Passkey authentication verification failed: %s", e)
            raise ValueError(f"Authentication verification failed: {e}") from e

        # Update sign count to prevent replay attacks
        passkey.sign_count = verification.new_sign_count
        passkey.last_used_at = timezone.now()
        passkey.save(update_fields=["sign_count", "last_used_at", "updated_at"])

        # Get member for the user
        user = passkey.user
        member_qs = user.memberships.select_related("organization")

        if organization_id:
            member = member_qs.filter(organization__stytch_org_id=organization_id).first()
            if not member:
                raise ValueError("User is not a member of the specified organization")
        else:
            # Get the most recently used membership
            member = member_qs.order_by("-updated_at").first()
            if not member:
                raise ValueError("User has no organization memberships")

        logger.info("Passkey authentication successful for user %s", user.email)

        return AuthenticationResult(
            user=user,
            member=member,
            passkey=passkey,
        )


def get_passkey_service() -> PasskeyService:
    """Get a PasskeyService instance."""
    return PasskeyService()
