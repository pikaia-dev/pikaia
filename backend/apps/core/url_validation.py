"""
URL validation utilities for SSRF protection.

Provides functions to validate URLs before making server-side requests,
preventing Server-Side Request Forgery (SSRF) attacks.
"""

import ipaddress
import socket
from urllib.parse import urlparse

# Allowlisted domains for avatar proxying
# These are known Google domains that serve profile images
# Note: Only specific subdomains are allowed, not the root googleusercontent.com
ALLOWED_AVATAR_DOMAINS = frozenset(
    {
        "lh3.googleusercontent.com",
        "lh4.googleusercontent.com",
        "lh5.googleusercontent.com",
        "lh6.googleusercontent.com",
        # Google Photos domains
        "photos.google.com",
    }
)


class SSRFError(Exception):
    """Raised when a URL fails SSRF validation."""

    pass


def is_private_ip(ip_str: str) -> bool:
    """
    Check if an IP address is private, loopback, or otherwise internal.

    Args:
        ip_str: IP address string (IPv4 or IPv6)

    Returns:
        True if the IP is private/internal, False if public
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
            # AWS metadata endpoint
            or ip_str == "169.254.169.254"
            # Common internal ranges that might not be caught
            or ip_str.startswith("10.")
            or ip_str.startswith("172.16.")
            or ip_str.startswith("172.17.")
            or ip_str.startswith("172.18.")
            or ip_str.startswith("172.19.")
            or ip_str.startswith("172.20.")
            or ip_str.startswith("172.21.")
            or ip_str.startswith("172.22.")
            or ip_str.startswith("172.23.")
            or ip_str.startswith("172.24.")
            or ip_str.startswith("172.25.")
            or ip_str.startswith("172.26.")
            or ip_str.startswith("172.27.")
            or ip_str.startswith("172.28.")
            or ip_str.startswith("172.29.")
            or ip_str.startswith("172.30.")
            or ip_str.startswith("172.31.")
            or ip_str.startswith("192.168.")
        )
    except ValueError:
        # Invalid IP address format
        return True


def validate_avatar_url(url: str, resolve_dns: bool = True) -> str:
    """
    Validate a URL for safe avatar fetching.

    Checks:
    1. URL uses HTTPS scheme
    2. Domain is in the allowlist
    3. Resolved IP is not private/internal (optional, for defense-in-depth)

    Args:
        url: The URL to validate
        resolve_dns: Whether to resolve DNS and check for private IPs
                    (set to False in tests to avoid network calls)

    Returns:
        The validated URL (unchanged if valid)

    Raises:
        SSRFError: If the URL fails any validation check
    """
    if not url:
        raise SSRFError("Empty URL")

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFError(f"Invalid URL format: {e}") from e

    # Require HTTPS
    if parsed.scheme != "https":
        raise SSRFError(f"URL must use HTTPS, got: {parsed.scheme}")

    # Extract hostname
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL has no hostname")

    # Normalize hostname (lowercase)
    hostname = hostname.lower()

    # Check against allowlist
    # Allow exact match or subdomain match
    domain_allowed = False
    for allowed_domain in ALLOWED_AVATAR_DOMAINS:
        if hostname == allowed_domain or hostname.endswith(f".{allowed_domain}"):
            domain_allowed = True
            break

    if not domain_allowed:
        raise SSRFError(f"Domain not allowed: {hostname}")

    # DNS resolution check (defense-in-depth against DNS rebinding)
    if resolve_dns:
        try:
            # Get all IP addresses for the hostname
            addr_info = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
            for _family, _type, _proto, _canonname, sockaddr in addr_info:
                ip = sockaddr[0]
                if is_private_ip(ip):
                    raise SSRFError(f"URL resolves to private IP: {ip}")
        except socket.gaierror as e:
            raise SSRFError(f"DNS resolution failed: {e}") from e

    return url
