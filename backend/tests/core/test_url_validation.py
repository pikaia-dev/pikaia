"""
Tests for URL validation and SSRF protection.

Tests cover all SSRF attack vectors:
- Private IP ranges (10.x, 172.16-31.x, 192.168.x)
- Loopback addresses (127.0.0.1, localhost)
- AWS metadata endpoint (169.254.169.254)
- Non-HTTPS schemes
- Disallowed domains
"""

from unittest.mock import patch

import pytest

from apps.core.url_validation import (
    ALLOWED_AVATAR_DOMAINS,
    SSRFError,
    is_private_ip,
    validate_avatar_url,
)


class TestIsPrivateIP:
    """Tests for is_private_ip function."""

    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "127.0.0.2",
            "127.255.255.255",
        ],
    )
    def test_loopback_ipv4(self, ip: str) -> None:
        """Should detect IPv4 loopback addresses."""
        assert is_private_ip(ip) is True

    def test_loopback_ipv6(self) -> None:
        """Should detect IPv6 loopback address."""
        assert is_private_ip("::1") is True

    @pytest.mark.parametrize(
        "ip",
        [
            "10.0.0.1",
            "10.255.255.255",
            "10.0.0.0",
        ],
    )
    def test_class_a_private(self, ip: str) -> None:
        """Should detect Class A private range (10.x.x.x)."""
        assert is_private_ip(ip) is True

    @pytest.mark.parametrize(
        "ip",
        [
            "172.16.0.1",
            "172.16.255.255",
            "172.31.0.1",
            "172.31.255.255",
            "172.20.0.0",
        ],
    )
    def test_class_b_private(self, ip: str) -> None:
        """Should detect Class B private range (172.16-31.x.x)."""
        assert is_private_ip(ip) is True

    @pytest.mark.parametrize(
        "ip",
        [
            "192.168.0.1",
            "192.168.1.1",
            "192.168.255.255",
        ],
    )
    def test_class_c_private(self, ip: str) -> None:
        """Should detect Class C private range (192.168.x.x)."""
        assert is_private_ip(ip) is True

    def test_aws_metadata_endpoint(self) -> None:
        """Should detect AWS metadata endpoint IP."""
        assert is_private_ip("169.254.169.254") is True

    def test_link_local(self) -> None:
        """Should detect link-local addresses."""
        assert is_private_ip("169.254.0.1") is True
        assert is_private_ip("169.254.100.100") is True

    @pytest.mark.parametrize(
        "ip",
        [
            "8.8.8.8",
            "1.1.1.1",
            "142.250.190.46",
            "151.101.1.140",
        ],
    )
    def test_public_ipv4(self, ip: str) -> None:
        """Should allow public IPv4 addresses."""
        assert is_private_ip(ip) is False

    def test_public_ipv6(self) -> None:
        """Should allow public IPv6 addresses."""
        assert is_private_ip("2607:f8b0:4004:800::200e") is False

    def test_invalid_ip_format(self) -> None:
        """Should treat invalid IP format as private (fail-safe)."""
        assert is_private_ip("not-an-ip") is True
        assert is_private_ip("256.256.256.256") is True
        assert is_private_ip("") is True


class TestValidateAvatarUrl:
    """Tests for validate_avatar_url function."""

    # --- Valid URLs ---

    def test_valid_google_user_content_url(self) -> None:
        """Should accept valid Google user content URLs."""
        url = "https://lh3.googleusercontent.com/a/ACg8ocK-abc123"
        result = validate_avatar_url(url, resolve_dns=False)
        assert result == url

    def test_valid_lh4_subdomain(self) -> None:
        """Should accept lh4.googleusercontent.com."""
        url = "https://lh4.googleusercontent.com/user/photo"
        result = validate_avatar_url(url, resolve_dns=False)
        assert result == url

    def test_valid_lh5_subdomain(self) -> None:
        """Should accept lh5.googleusercontent.com."""
        url = "https://lh5.googleusercontent.com/user/photo"
        result = validate_avatar_url(url, resolve_dns=False)
        assert result == url

    def test_valid_lh6_subdomain(self) -> None:
        """Should accept lh6.googleusercontent.com."""
        url = "https://lh6.googleusercontent.com/user/photo"
        result = validate_avatar_url(url, resolve_dns=False)
        assert result == url

    def test_case_insensitive_domain(self) -> None:
        """Should handle domain case-insensitively."""
        url = "https://LH3.GOOGLEUSERCONTENT.COM/a/photo"
        result = validate_avatar_url(url, resolve_dns=False)
        assert result == url

    # --- Empty/Invalid URL ---

    def test_empty_url(self) -> None:
        """Should reject empty URL."""
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("", resolve_dns=False)
        assert "Empty URL" in str(exc_info.value)

    def test_none_url(self) -> None:
        """Should reject None URL."""
        with pytest.raises(SSRFError):
            validate_avatar_url(None, resolve_dns=False)  # type: ignore[arg-type]

    # --- Scheme Validation ---

    def test_rejects_http_scheme(self) -> None:
        """Should reject HTTP (non-HTTPS) URLs."""
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("http://lh3.googleusercontent.com/photo", resolve_dns=False)
        assert "HTTPS" in str(exc_info.value)

    def test_rejects_ftp_scheme(self) -> None:
        """Should reject FTP scheme."""
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("ftp://lh3.googleusercontent.com/photo", resolve_dns=False)
        assert "HTTPS" in str(exc_info.value)

    def test_rejects_file_scheme(self) -> None:
        """Should reject file:// scheme (local file access)."""
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("file:///etc/passwd", resolve_dns=False)
        assert "HTTPS" in str(exc_info.value)

    def test_rejects_data_scheme(self) -> None:
        """Should reject data: scheme."""
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("data:image/png;base64,abc123", resolve_dns=False)
        assert "HTTPS" in str(exc_info.value)

    def test_rejects_javascript_scheme(self) -> None:
        """Should reject javascript: scheme."""
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("javascript:alert(1)", resolve_dns=False)
        assert "HTTPS" in str(exc_info.value)

    # --- Domain Allowlist ---

    def test_rejects_arbitrary_domain(self) -> None:
        """Should reject domains not in allowlist."""
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("https://evil.com/photo.jpg", resolve_dns=False)
        assert "not allowed" in str(exc_info.value)

    def test_rejects_localhost(self) -> None:
        """Should reject localhost."""
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("https://localhost/photo", resolve_dns=False)
        assert "not allowed" in str(exc_info.value)

    def test_rejects_127_0_0_1(self) -> None:
        """Should reject 127.0.0.1."""
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("https://127.0.0.1/photo", resolve_dns=False)
        assert "not allowed" in str(exc_info.value)

    def test_rejects_internal_ip_in_url(self) -> None:
        """Should reject internal IP addresses in URL."""
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("https://10.0.0.1/photo", resolve_dns=False)
        assert "not allowed" in str(exc_info.value)

    def test_rejects_aws_metadata_in_url(self) -> None:
        """Should reject AWS metadata endpoint."""
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("https://169.254.169.254/latest/meta-data/", resolve_dns=False)
        assert "not allowed" in str(exc_info.value)

    def test_rejects_domain_with_allowed_suffix(self) -> None:
        """Should reject domains that merely contain allowed domain as suffix."""
        # evil-lh3.googleusercontent.com is NOT a subdomain of lh3.googleusercontent.com
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("https://evil-lh3.googleusercontent.com/photo", resolve_dns=False)
        assert "not allowed" in str(exc_info.value)

    def test_rejects_similar_looking_domain(self) -> None:
        """Should reject domains that look similar but aren't allowed."""
        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url(
                "https://lh3.googleusercontent.com.evil.com/photo", resolve_dns=False
            )
        assert "not allowed" in str(exc_info.value)

    # --- DNS Resolution Protection ---

    @patch("apps.core.url_validation.socket.getaddrinfo")
    def test_rejects_url_resolving_to_private_ip(self, mock_getaddrinfo) -> None:
        """Should reject URL that resolves to private IP (DNS rebinding protection)."""
        # Simulate DNS returning a private IP
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("10.0.0.1", 443)),
        ]

        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("https://lh3.googleusercontent.com/photo", resolve_dns=True)
        assert "private IP" in str(exc_info.value)

    @patch("apps.core.url_validation.socket.getaddrinfo")
    def test_rejects_url_resolving_to_loopback(self, mock_getaddrinfo) -> None:
        """Should reject URL that resolves to loopback."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ]

        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("https://lh3.googleusercontent.com/photo", resolve_dns=True)
        assert "private IP" in str(exc_info.value)

    @patch("apps.core.url_validation.socket.getaddrinfo")
    def test_rejects_url_resolving_to_aws_metadata(self, mock_getaddrinfo) -> None:
        """Should reject URL that resolves to AWS metadata IP."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("169.254.169.254", 443)),
        ]

        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("https://lh3.googleusercontent.com/photo", resolve_dns=True)
        assert "private IP" in str(exc_info.value)

    @patch("apps.core.url_validation.socket.getaddrinfo")
    def test_accepts_url_resolving_to_public_ip(self, mock_getaddrinfo) -> None:
        """Should accept URL that resolves to public IP."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("142.250.190.46", 443)),  # Google IP
        ]

        url = "https://lh3.googleusercontent.com/photo"
        result = validate_avatar_url(url, resolve_dns=True)
        assert result == url

    @patch("apps.core.url_validation.socket.getaddrinfo")
    def test_dns_resolution_failure(self, mock_getaddrinfo) -> None:
        """Should reject URL when DNS resolution fails."""
        import socket

        mock_getaddrinfo.side_effect = socket.gaierror("DNS failed")

        with pytest.raises(SSRFError) as exc_info:
            validate_avatar_url("https://lh3.googleusercontent.com/photo", resolve_dns=True)
        assert "DNS resolution failed" in str(exc_info.value)


class TestAllowedDomains:
    """Tests to verify the allowlist is configured correctly."""

    def test_allowlist_contains_google_domains(self) -> None:
        """Verify expected domains are in allowlist."""
        expected_domains = [
            "lh3.googleusercontent.com",
            "lh4.googleusercontent.com",
            "lh5.googleusercontent.com",
            "lh6.googleusercontent.com",
        ]
        for domain in expected_domains:
            assert domain in ALLOWED_AVATAR_DOMAINS

    def test_allowlist_is_frozen(self) -> None:
        """Verify allowlist cannot be modified at runtime."""
        assert isinstance(ALLOWED_AVATAR_DOMAINS, frozenset)
