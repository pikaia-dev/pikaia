"""
Tests for Trusted Auth token generation.

Tests JWT creation, signing, and validation for Stytch session attestation.
"""

import time

import jwt
import pytest

from apps.passkeys.trusted_auth import TRUSTED_AUTH_TOKEN_EXPIRY_SECONDS, create_trusted_auth_token

# Test RSA private key (generated for testing only)
TEST_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCVyLhf1ZHrknFF
mBkLsYZ3KugyQNXVQOSKW/s9+wEOamKhtysC3ImNeJpxir4bCM6v0e32lJxWOjTu
/Hfr2qJZVjhWMmK3IGNm1042sQpLPIBE5KRbYE49kNgV6VY4oA6MWTjeHYsMT9fQ
LG9nxdtoAJVhTUFfiX/jM5n5kVDFZ5kdTJmECrBWCbgNjbEdsXHM0ZEFM47GXe6t
V2QEwdixaNUYN2GbxPNInSNWXL2Sh/zhPR5tEoIQSrupZxH+auy2pTyT0xKcaRqV
b9/KLaGK+uz+/3Ct4OBKHZgUBcNRTqtSKO/nZ883xQWHe6oIVw6PMlQvmqTnRu6Q
NtHdhDB1AgMBAAECggEAE0GiXoO9Bk2l7V4P/j5c/K4R+v/13bxBhX4szzuZV6qa
spKzX2NN9dem92jwZtZbiCQTlUtmy/kgvAbOPg62J4kbpg1FPqjVzq9oeUSKf8Cv
9ut0K+E2PdkExtBgSthc9nM0Ce4/ZZ5QLw2/ZtZ7jiPhEIjXmjo5rFKCfaDOgwpL
ugDswnKmom3rieiYkVdyhq3TWVn/aUO8ReP9aCCKn3jCxU65l7TLe2zP9jT136yj
H3Umkhfhx9qmKzFWfLzhAThID7TKjchiFWk69u3ti9IpLwpdgTTRPcPvHKqVSkCG
otUGvWTC/b0uOygh9/jXPi4gAXlSC04T5+I+nc6PYQKBgQDIuZwNVMYlpI1+rVe3
vaKI9pWO2ezPltH6VBQ/p5KFAKOCogININmCsw36pDO8XuEwx8rZ8SBRiI4ytN14
bLN98Ee5qG1fwpf+aSrAx5ePukuhRWHezFueadJu4/utaC4W51mTqwiLnd8Vrgxx
56tFizmL/sXjTzgBRxFH8vlLJQKBgQC/B/S0vGOEBYaOPlA95JezvK+eWjWC2bUj
h/g4rBAs/wNUEe0cQbmuKnJjiKxaIan2nm25aM475t7p6kxDr8kX9wQ4OI/Rbheq
aA5bmyW14Ya/jsmvnAXMWTdmXNmMbaMkm8yX2gEIH+LeeYQ187VlLFdFO59mxcRr
RiJRamh3EQKBgQCIn83YRRuaA6dL0jEin7FCCJVD5pGJut6xxQkDSswwO38QK7W5
ueJTVAzvzVRpoyskSNmJ/tZAqPIhEXqtvU9vKV2owTuxMoLCaFLxZOmEqwlPfCph
vDegW+cgE437Oi4k6NPP71qhrZNq7k0KOuYZL+q7n26SihlUxUq97mRBAQKBgAJe
qeV4FM/1dZbcJQivhkY/h/ox6koGQ13+eNDTKZw1SahIVKWuFwyXEDY14tV3Z3Fc
w8WyDCToF0nVkz6ftqHqeY3s/bO+ZuLBSbRPN2eLNa24qr3X9KZ1UN+fNT+tuIFi
wWX82VhtdNYHseEtdcmchDSiqbaPq4EdLJ3P8R3RAoGBALm5Zw2SXhxoE2fLBhHR
xumRVJIf+sm3hli9H0F9CpO6/+E0fRHuWk2jN0tYOErKwUBqPCfk5/Efy8Zy+e4r
b8jC/mQIlWNM1U+IGB6DHVoLIw4NR5pK8jcwR5ueNzPxr2EPPmZ6+zCk3C9Mjh7z
4KyGKoZ7tWAsxd0P/iVOEAfc
-----END PRIVATE KEY-----"""


class TestTrustedAuthToken:
    """Tests for create_trusted_auth_token function."""

    def test_creates_valid_jwt_with_correct_claims(self, settings):
        """Should create JWT with all required Stytch claims."""
        # Configure test settings
        settings.STYTCH_TRUSTED_AUTH_ISSUER = "test.example.com"
        settings.STYTCH_TRUSTED_AUTH_AUDIENCE = "project-test-123"
        settings.PASSKEY_JWT_PRIVATE_KEY = TEST_PRIVATE_KEY

        token = create_trusted_auth_token(
            email="test@example.com",
            member_id="member-test-123",
            organization_id="org-test-456",
            user_id=789,
        )

        # Decode without verification to inspect claims
        decoded = jwt.decode(token, options={"verify_signature": False})

        assert decoded["token_id"] == "789"
        assert decoded["email"] == "test@example.com"
        assert decoded["iss"] == "test.example.com"
        assert decoded["aud"] == "project-test-123"
        assert decoded["org_id"] == "org-test-456"
        assert decoded["member_id"] == "member-test-123"
        assert "iat" in decoded
        assert "exp" in decoded

    def test_token_expires_in_5_minutes(self, settings):
        """Should set expiration to 5 minutes (300 seconds)."""
        settings.STYTCH_TRUSTED_AUTH_ISSUER = "test.example.com"
        settings.STYTCH_TRUSTED_AUTH_AUDIENCE = "project-test-123"
        settings.PASSKEY_JWT_PRIVATE_KEY = TEST_PRIVATE_KEY

        now = int(time.time())
        token = create_trusted_auth_token(
            email="test@example.com",
            member_id="member-123",
            organization_id="org-456",
            user_id=1,
        )

        decoded = jwt.decode(token, options={"verify_signature": False})

        # Should be issued now-ish (within 2 seconds)
        assert abs(decoded["iat"] - now) <= 2

        # Should expire in exactly TRUSTED_AUTH_TOKEN_EXPIRY_SECONDS
        assert decoded["exp"] - decoded["iat"] == TRUSTED_AUTH_TOKEN_EXPIRY_SECONDS

    def test_handles_escaped_newlines_in_private_key(self, settings):
        """Should convert escaped newlines to actual newlines."""
        settings.STYTCH_TRUSTED_AUTH_ISSUER = "test.example.com"
        settings.STYTCH_TRUSTED_AUTH_AUDIENCE = "project-test-123"
        # Simulate environment variable with escaped newlines (first line of real key)
        settings.PASSKEY_JWT_PRIVATE_KEY = TEST_PRIVATE_KEY.replace("\n", "\\n")

        # Should not raise an error
        token = create_trusted_auth_token(
            email="test@example.com",
            member_id="member-123",
            organization_id="org-456",
            user_id=1,
        )

        assert isinstance(token, str)
        assert len(token) > 0

    def test_raises_error_when_private_key_missing(self, settings):
        """Should raise ValueError when PASSKEY_JWT_PRIVATE_KEY is not configured."""
        settings.PASSKEY_JWT_PRIVATE_KEY = None

        with pytest.raises(ValueError, match="PASSKEY_JWT_PRIVATE_KEY is not configured"):
            create_trusted_auth_token(
                email="test@example.com",
                member_id="member-123",
                organization_id="org-456",
                user_id=1,
            )

    def test_uses_rs256_algorithm(self, settings):
        """Should use RS256 algorithm for signing."""
        settings.STYTCH_TRUSTED_AUTH_ISSUER = "test.example.com"
        settings.STYTCH_TRUSTED_AUTH_AUDIENCE = "project-test-123"
        settings.PASSKEY_JWT_PRIVATE_KEY = TEST_PRIVATE_KEY

        token = create_trusted_auth_token(
            email="test@example.com",
            member_id="member-123",
            organization_id="org-456",
            user_id=1,
        )

        # Decode header to check algorithm
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "RS256"
        assert header["kid"] == "passkey-auth-key-1"
