"""
Encrypted model fields using Fernet symmetric encryption.

Provides application-level encryption at rest for sensitive data stored
in the database. Values are encrypted before writing and decrypted after
reading, so the database only ever stores ciphertext.

Uses the ``cryptography`` library with Fernet, which provides
AES-128-CBC + HMAC-SHA256.

Key management:
    - Derives a Fernet key from ``settings.FIELD_ENCRYPTION_KEY`` using
      PBKDF2-HMAC-SHA256 (100_000 iterations).
    - ``FIELD_ENCRYPTION_KEY`` must be a dedicated secret, separate from
      ``SECRET_KEY``, to limit blast radius if either key is compromised.
    - Falls back to ``settings.SECRET_KEY`` only in local development
      (production enforces a dedicated key via startup validation).
"""

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


def _derive_fernet_key(key_material: str) -> bytes:
    """Derive a 32-byte Fernet key from arbitrary key material via PBKDF2."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        key_material.encode("utf-8"),
        b"pikaia-field-encryption-salt",
        iterations=100_000,
        dklen=32,
    )
    return base64.urlsafe_b64encode(dk)


def get_fernet() -> Fernet:
    """
    Return a Fernet instance using the configured encryption key.

    In non-DEBUG mode, ``FIELD_ENCRYPTION_KEY`` must be set to a dedicated
    value (not the Django ``SECRET_KEY``). This prevents a single key
    compromise from exposing both session data and encrypted fields.
    """
    encryption_key = getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    if encryption_key:
        key_material = encryption_key
    elif getattr(settings, "DEBUG", False):
        key_material = settings.SECRET_KEY
    else:
        raise ValueError(
            "FIELD_ENCRYPTION_KEY is required when DEBUG=False. "
            "Set a dedicated encryption key separate from SECRET_KEY."
        )
    return Fernet(_derive_fernet_key(key_material))


class EncryptedTextField(models.TextField):
    """
    A TextField that transparently encrypts values before storing
    and decrypts after reading.

    Database column stores Fernet ciphertext (base64-encoded, ~200 chars
    for typical webhook secrets). Empty/blank values are stored as-is.
    """

    def get_prep_value(self, value: str | None) -> str | None:
        """Encrypt the value before saving to the database."""
        if value is None or value == "":
            return value
        fernet = get_fernet()
        return fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def from_db_value(
        self, value: str | None, expression: object, connection: object
    ) -> str | None:
        """Decrypt the value after reading from the database."""
        if value is None or value == "":
            return value
        fernet = get_fernet()
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")

    def deconstruct(self) -> tuple:
        """Return enough information to recreate the field in migrations."""
        name, path, args, kwargs = super().deconstruct()
        return name, "apps.core.fields.EncryptedTextField", args, kwargs
