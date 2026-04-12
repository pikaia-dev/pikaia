"""
Data migration: encrypt all existing plaintext webhook signing secrets.

After 0004 changed the column from CharField to EncryptedTextField, old rows
still contain plaintext values. This migration reads each secret via raw SQL
(bypassing the field's from_db_value decryption), encrypts it, and writes
the ciphertext back.

The migration is idempotent: Fernet tokens always start with "gAAAAA", so
already-encrypted values are detected and skipped.
"""

import logging

from cryptography.fernet import InvalidToken
from django.db import migrations

logger = logging.getLogger(__name__)

# Fernet tokens are base64url-encoded and always begin with the version
# byte 0x80 encoded as "gA". Checking for this prefix lets us distinguish
# ciphertext from plaintext without attempting (and failing) decryption.
_FERNET_PREFIX = "gAAAAA"


def encrypt_existing_secrets(apps, schema_editor):
    """Encrypt plaintext secrets in-place."""
    # Use raw SQL to bypass EncryptedTextField.from_db_value, which would
    # try to decrypt the still-plaintext values and fail.
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, secret FROM webhooks_webhookendpoint")
        rows = cursor.fetchall()

    if not rows:
        return

    from apps.core.fields import get_fernet

    fernet = get_fernet()

    for endpoint_id, plaintext_secret in rows:
        if not plaintext_secret or plaintext_secret.startswith(_FERNET_PREFIX):
            continue

        try:
            ciphertext = fernet.encrypt(plaintext_secret.encode("utf-8")).decode("utf-8")
        except Exception:
            logger.exception("Failed to encrypt webhook secret for endpoint %s", endpoint_id)
            raise

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE webhooks_webhookendpoint SET secret = %s WHERE id = %s",
                [ciphertext, endpoint_id],
            )


def decrypt_existing_secrets(apps, schema_editor):
    """Reverse migration: decrypt secrets back to plaintext."""
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, secret FROM webhooks_webhookendpoint")
        rows = cursor.fetchall()

    if not rows:
        return

    from apps.core.fields import get_fernet

    fernet = get_fernet()

    for endpoint_id, ciphertext_secret in rows:
        if not ciphertext_secret or not ciphertext_secret.startswith(_FERNET_PREFIX):
            continue

        try:
            plaintext = fernet.decrypt(ciphertext_secret.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            logger.error(
                "Failed to decrypt webhook secret for endpoint %s — "
                "encryption key may have changed since the forward migration",
                endpoint_id,
            )
            raise
        except Exception:
            logger.exception(
                "Unexpected error decrypting webhook secret for endpoint %s",
                endpoint_id,
            )
            raise

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE webhooks_webhookendpoint SET secret = %s WHERE id = %s",
                [plaintext, endpoint_id],
            )


class Migration(migrations.Migration):
    dependencies = [
        ("webhooks", "0004_encrypt_webhook_secret"),
    ]

    operations = [
        migrations.RunPython(
            encrypt_existing_secrets,
            reverse_code=decrypt_existing_secrets,
        ),
    ]
