"""
Passkey (WebAuthn) models.

Stores WebAuthn credentials linked to users for passwordless authentication.
"""

from django.db import models

from apps.core.models import TimestampedModel


class Passkey(TimestampedModel):
    """
    WebAuthn credential stored for a user.

    Each passkey represents a registered authenticator (device) that can be used
    for passwordless authentication. Credentials are bound to the relying party
    (domain) and cannot be used on other sites.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="passkeys",
        help_text="User who owns this passkey",
    )

    # WebAuthn credential fields
    credential_id = models.BinaryField(
        unique=True,
        help_text="Base64URL-decoded credential ID from authenticator",
    )
    public_key = models.BinaryField(
        help_text="COSE public key for signature verification",
    )
    sign_count = models.PositiveIntegerField(
        default=0,
        help_text="Signature counter for replay attack detection",
    )

    # Metadata
    name = models.CharField(
        max_length=100,
        help_text="User-friendly name (e.g., 'iPhone 15', 'YubiKey')",
    )
    aaguid = models.CharField(
        max_length=36,
        blank=True,
        default="",
        help_text="Authenticator Attestation GUID (identifies authenticator model)",
    )

    # Credential flags
    is_discoverable = models.BooleanField(
        default=True,
        help_text="Whether this is a discoverable (resident) credential",
    )
    backup_eligible = models.BooleanField(
        default=False,
        help_text="Whether the credential is eligible for backup (e.g., iCloud Keychain)",
    )
    backup_state = models.BooleanField(
        default=False,
        help_text="Whether the credential is currently backed up",
    )

    # Transports (for UX hints during authentication)
    transports = models.JSONField(
        default=list,
        blank=True,
        help_text="Supported transports: usb, nfc, ble, internal, hybrid",
    )

    # Usage tracking
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this passkey was used for authentication",
    )

    class Meta:
        verbose_name = "Passkey"
        verbose_name_plural = "Passkeys"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.user.email})"

    @property
    def credential_id_b64(self) -> str:
        """Return credential ID as base64url string."""
        import base64

        return base64.urlsafe_b64encode(self.credential_id).rstrip(b"=").decode("ascii")
