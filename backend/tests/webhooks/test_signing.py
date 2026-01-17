"""
Tests for webhook signature generation and verification.
"""

import time

from apps.webhooks.signing import (
    CLOCK_SKEW_TOLERANCE,
    generate_headers,
    generate_signature,
    verify_signature,
)


class TestGenerateSignature:
    """Tests for generate_signature function."""

    def test_generates_signature_with_version_prefix(self) -> None:
        """Should generate signature with v1= prefix."""
        signature, timestamp = generate_signature('{"test": true}', "secret123")

        assert signature.startswith("v1=")
        assert len(signature) > 3  # More than just the prefix

    def test_signature_is_deterministic_for_same_inputs(self) -> None:
        """Same payload, secret, and timestamp should produce same signature."""
        fixed_timestamp = 1700000000

        sig1, _ = generate_signature('{"test": true}', "secret123", fixed_timestamp)
        sig2, _ = generate_signature('{"test": true}', "secret123", fixed_timestamp)

        assert sig1 == sig2

    def test_different_payloads_produce_different_signatures(self) -> None:
        """Different payloads should produce different signatures."""
        fixed_timestamp = 1700000000

        sig1, _ = generate_signature('{"test": true}', "secret123", fixed_timestamp)
        sig2, _ = generate_signature('{"test": false}', "secret123", fixed_timestamp)

        assert sig1 != sig2

    def test_different_secrets_produce_different_signatures(self) -> None:
        """Different secrets should produce different signatures."""
        fixed_timestamp = 1700000000

        sig1, _ = generate_signature('{"test": true}', "secret1", fixed_timestamp)
        sig2, _ = generate_signature('{"test": true}', "secret2", fixed_timestamp)

        assert sig1 != sig2

    def test_different_timestamps_produce_different_signatures(self) -> None:
        """Different timestamps should produce different signatures."""
        sig1, _ = generate_signature('{"test": true}', "secret123", 1700000000)
        sig2, _ = generate_signature('{"test": true}', "secret123", 1700000001)

        assert sig1 != sig2

    def test_returns_current_timestamp_when_not_provided(self) -> None:
        """Should use current time when timestamp not provided."""
        before = int(time.time())
        _, timestamp = generate_signature('{"test": true}', "secret123")
        after = int(time.time())

        assert before <= timestamp <= after


class TestVerifySignature:
    """Tests for verify_signature function."""

    def test_accepts_valid_signature(self) -> None:
        """Should accept a valid signature within time tolerance."""
        payload = '{"test": true}'
        secret = "secret123"
        timestamp = int(time.time())

        signature, _ = generate_signature(payload, secret, timestamp)

        assert verify_signature(payload, secret, signature, timestamp) is True

    def test_rejects_wrong_signature(self) -> None:
        """Should reject an incorrect signature."""
        payload = '{"test": true}'
        secret = "secret123"
        timestamp = int(time.time())

        assert verify_signature(payload, secret, "v1=wrong", timestamp) is False

    def test_rejects_wrong_secret(self) -> None:
        """Should reject signature made with different secret."""
        payload = '{"test": true}'
        timestamp = int(time.time())

        signature, _ = generate_signature(payload, "secret123", timestamp)

        assert verify_signature(payload, "different_secret", signature, timestamp) is False

    def test_rejects_modified_payload(self) -> None:
        """Should reject signature when payload was modified."""
        original_payload = '{"test": true}'
        modified_payload = '{"test": false}'
        secret = "secret123"
        timestamp = int(time.time())

        signature, _ = generate_signature(original_payload, secret, timestamp)

        assert verify_signature(modified_payload, secret, signature, timestamp) is False

    def test_rejects_old_timestamp(self) -> None:
        """Should reject signatures with timestamps outside tolerance."""
        payload = '{"test": true}'
        secret = "secret123"
        old_timestamp = int(time.time()) - CLOCK_SKEW_TOLERANCE - 60  # Beyond tolerance

        signature, _ = generate_signature(payload, secret, old_timestamp)

        assert verify_signature(payload, secret, signature, old_timestamp) is False

    def test_rejects_future_timestamp(self) -> None:
        """Should reject signatures with future timestamps outside tolerance."""
        payload = '{"test": true}'
        secret = "secret123"
        future_timestamp = int(time.time()) + CLOCK_SKEW_TOLERANCE + 60  # Beyond tolerance

        signature, _ = generate_signature(payload, secret, future_timestamp)

        assert verify_signature(payload, secret, signature, future_timestamp) is False

    def test_accepts_timestamp_within_tolerance(self) -> None:
        """Should accept signatures within clock skew tolerance."""
        payload = '{"test": true}'
        secret = "secret123"
        slightly_old = int(time.time()) - (CLOCK_SKEW_TOLERANCE - 10)  # Within tolerance

        signature, _ = generate_signature(payload, secret, slightly_old)

        assert verify_signature(payload, secret, signature, slightly_old) is True


class TestGenerateHeaders:
    """Tests for generate_headers function."""

    def test_includes_all_required_headers(self) -> None:
        """Should include all webhook headers."""
        headers = generate_headers('{"test": true}', "secret123", "evt_123")

        assert "Content-Type" in headers
        assert "X-Webhook-ID" in headers
        assert "X-Webhook-Timestamp" in headers
        assert "X-Webhook-Signature" in headers
        assert "User-Agent" in headers

    def test_content_type_is_json(self) -> None:
        """Should set Content-Type to application/json."""
        headers = generate_headers('{"test": true}', "secret123", "evt_123")

        assert headers["Content-Type"] == "application/json"

    def test_webhook_id_matches_event_id(self) -> None:
        """Should set X-Webhook-ID to the event ID."""
        headers = generate_headers('{"test": true}', "secret123", "evt_12345")

        assert headers["X-Webhook-ID"] == "evt_12345"

    def test_timestamp_is_numeric_string(self) -> None:
        """Should set X-Webhook-Timestamp to numeric string."""
        headers = generate_headers('{"test": true}', "secret123", "evt_123")

        assert headers["X-Webhook-Timestamp"].isdigit()

    def test_signature_is_valid(self) -> None:
        """Generated signature should be verifiable."""
        payload = '{"test": true}'
        secret = "secret123"

        headers = generate_headers(payload, secret, "evt_123")

        timestamp = int(headers["X-Webhook-Timestamp"])
        signature = headers["X-Webhook-Signature"]

        assert verify_signature(payload, secret, signature, timestamp) is True
