"""
Tests for core encrypted fields.
"""

from unittest.mock import patch

import pytest
from django.db import connection

from apps.core.fields import EncryptedTextField, _derive_fernet_key, get_fernet
from apps.webhooks.models import WebhookEndpoint
from tests.webhooks.factories import WebhookEndpointFactory


class TestDeriveFernetKey:
    """Tests for Fernet key derivation."""

    def test_produces_valid_fernet_key(self) -> None:
        """Derived key should be 44 bytes (base64-encoded 32-byte key)."""
        key = _derive_fernet_key("test-secret")

        assert len(key) == 44

    def test_deterministic(self) -> None:
        """Same input should produce same key."""
        key1 = _derive_fernet_key("my-secret")
        key2 = _derive_fernet_key("my-secret")

        assert key1 == key2

    def test_different_inputs_different_keys(self) -> None:
        """Different inputs should produce different keys."""
        key1 = _derive_fernet_key("secret-a")
        key2 = _derive_fernet_key("secret-b")

        assert key1 != key2


class TestGetFernet:
    """Tests for get_fernet helper."""

    def test_returns_fernet_instance(self) -> None:
        """Should return a valid Fernet instance."""
        from cryptography.fernet import Fernet

        fernet = get_fernet()

        assert isinstance(fernet, Fernet)

    def test_uses_field_encryption_key_when_set(self) -> None:
        """Should prefer FIELD_ENCRYPTION_KEY over SECRET_KEY."""
        with patch("apps.core.fields.settings") as mock_settings:
            mock_settings.FIELD_ENCRYPTION_KEY = "dedicated-encryption-key"
            mock_settings.SECRET_KEY = "django-secret-key"

            fernet1 = get_fernet()

        with patch("apps.core.fields.settings") as mock_settings:
            mock_settings.FIELD_ENCRYPTION_KEY = ""
            mock_settings.DEBUG = True
            mock_settings.SECRET_KEY = "dedicated-encryption-key"

            fernet2 = get_fernet()

        # Both use the same raw key material ("dedicated-encryption-key"),
        # so PBKDF2 produces the same derived key and cross-decryption works.
        test_data = b"test-plaintext"
        token1 = fernet1.encrypt(test_data)
        assert fernet2.decrypt(token1) == test_data

    def test_falls_back_to_secret_key_in_debug_mode(self) -> None:
        """Should fall back to SECRET_KEY when FIELD_ENCRYPTION_KEY is empty and DEBUG=True."""
        with patch("apps.core.fields.settings") as mock_settings:
            mock_settings.FIELD_ENCRYPTION_KEY = ""
            mock_settings.DEBUG = True
            mock_settings.SECRET_KEY = "fallback-key"

            fernet = get_fernet()

        assert fernet.encrypt(b"data") is not None

    def test_raises_when_missing_and_not_debug(self) -> None:
        """Should raise ValueError when FIELD_ENCRYPTION_KEY is empty and DEBUG=False."""
        with patch("apps.core.fields.settings") as mock_settings:
            mock_settings.FIELD_ENCRYPTION_KEY = ""
            mock_settings.DEBUG = False

            with pytest.raises(ValueError, match="FIELD_ENCRYPTION_KEY is required"):
                get_fernet()


class TestEncryptedTextField:
    """Tests for EncryptedTextField."""

    def test_get_prep_value_encrypts(self) -> None:
        """Should encrypt non-empty values."""
        field = EncryptedTextField()

        encrypted = field.get_prep_value("whsec_abc123")

        assert encrypted is not None
        assert encrypted != "whsec_abc123"
        assert encrypted.startswith("gAAAAA")

    def test_from_db_value_decrypts(self) -> None:
        """Should decrypt ciphertext back to original value."""
        field = EncryptedTextField()
        original = "whsec_test_secret_value"

        encrypted = field.get_prep_value(original)
        decrypted = field.from_db_value(encrypted, None, None)

        assert decrypted == original

    def test_none_passthrough(self) -> None:
        """Should pass None through without encryption."""
        field = EncryptedTextField()

        assert field.get_prep_value(None) is None
        assert field.from_db_value(None, None, None) is None

    def test_empty_string_passthrough(self) -> None:
        """Should pass empty string through without encryption."""
        field = EncryptedTextField()

        assert field.get_prep_value("") == ""
        assert field.from_db_value("", None, None) == ""

    def test_roundtrip_various_values(self) -> None:
        """Should roundtrip various secret formats."""
        field = EncryptedTextField()

        test_values = [
            "whsec_abcdef1234567890",
            "simple-secret",
            "a" * 200,
            "special-chars-!@#$%^&*()",
            "unicode-\u00e9\u00e0\u00fc",
        ]

        for original in test_values:
            encrypted = field.get_prep_value(original)
            decrypted = field.from_db_value(encrypted, None, None)
            assert decrypted == original, f"Roundtrip failed for: {original}"

    def test_deconstruct_returns_custom_path(self) -> None:
        """Deconstruct should return the custom field path for migrations."""
        field = EncryptedTextField()
        field.name = "secret"

        _name, path, _args, _kwargs = field.deconstruct()

        assert path == "apps.core.fields.EncryptedTextField"


@pytest.mark.django_db
class TestEncryptedFieldIntegration:
    """Integration tests: encrypted field with real database reads/writes."""

    def test_secret_stored_encrypted_in_database(self) -> None:
        """The database column should contain ciphertext, not plaintext."""
        endpoint = WebhookEndpointFactory.create()
        original_secret = endpoint.secret

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT secret FROM webhooks_webhookendpoint WHERE id = %s",
                [endpoint.id],
            )
            raw_value = cursor.fetchone()[0]

        assert raw_value.startswith("gAAAAA")
        assert raw_value != original_secret

    def test_secret_decrypted_on_read(self) -> None:
        """Reading through the ORM should return the decrypted plaintext."""
        endpoint = WebhookEndpointFactory.create()
        original_secret = endpoint.secret

        fetched = WebhookEndpoint.objects.get(id=endpoint.id)

        assert fetched.secret == original_secret
        assert fetched.secret.startswith("whsec_")

    def test_regenerate_secret_encrypts_new_value(self) -> None:
        """Regenerated secrets should also be encrypted at rest."""
        endpoint = WebhookEndpointFactory.create()

        new_secret = endpoint.regenerate_secret()

        fetched = WebhookEndpoint.objects.get(id=endpoint.id)
        assert fetched.secret == new_secret
        assert fetched.secret.startswith("whsec_")

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT secret FROM webhooks_webhookendpoint WHERE id = %s",
                [endpoint.id],
            )
            raw_value = cursor.fetchone()[0]

        assert raw_value.startswith("gAAAAA")
        assert raw_value != new_secret

    def test_update_fields_preserves_encryption(self) -> None:
        """Saving with update_fields should still encrypt."""
        endpoint = WebhookEndpointFactory.create()
        endpoint.secret = "whsec_new_test_value"
        endpoint.save(update_fields=["secret", "updated_at"])

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT secret FROM webhooks_webhookendpoint WHERE id = %s",
                [endpoint.id],
            )
            raw_value = cursor.fetchone()[0]

        assert raw_value.startswith("gAAAAA")

        fetched = WebhookEndpoint.objects.get(id=endpoint.id)
        assert fetched.secret == "whsec_new_test_value"
