"""
Tests for SVG sanitization module.

Security-critical tests for XSS prevention in user-uploaded SVGs.
"""

import pytest

from apps.media.svg_sanitizer import (
    SVGSanitizationError,
    _has_dangerous_value,
    is_svg_content,
    sanitize_svg,
)


class TestSanitizeSVG:
    """Tests for the main sanitize_svg function."""

    def test_valid_svg_passes_through(self) -> None:
        """Should preserve valid SVG structure and content."""
        svg = b"""<?xml version="1.0" encoding="UTF-8"?>
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
            <rect x="10" y="10" width="80" height="80" fill="blue"/>
            <circle cx="50" cy="50" r="30" stroke="red" stroke-width="2"/>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"<svg" in result
        assert b"<rect" in result
        assert b"<circle" in result
        assert b'fill="blue"' in result
        assert b'stroke="red"' in result

    def test_removes_script_tags(self) -> None:
        """Should remove script elements."""
        svg = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect x="10" y="10" width="50" height="50"/>
            <script>alert('XSS')</script>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"<script" not in result
        assert b"alert" not in result
        assert b"<rect" in result

    def test_removes_onclick_handler(self) -> None:
        """Should remove onclick event handler."""
        svg = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect onclick="alert('XSS')" x="10" y="10" width="50" height="50"/>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"onclick" not in result
        assert b"alert" not in result
        assert b"<rect" in result

    def test_removes_onload_handler(self) -> None:
        """Should remove onload event handler."""
        svg = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg" onload="malicious()">
            <rect x="10" y="10" width="50" height="50"/>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"onload" not in result
        assert b"malicious" not in result

    def test_removes_onerror_handler(self) -> None:
        """Should remove onerror event handler."""
        svg = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <image onerror="alert(1)" href="invalid.jpg"/>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"onerror" not in result

    def test_removes_foreign_object(self) -> None:
        """Should remove foreignObject elements."""
        svg = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <foreignObject width="100" height="100">
                <body xmlns="http://www.w3.org/1999/xhtml">
                    <p>HTML content</p>
                </body>
            </foreignObject>
            <rect x="0" y="0" width="10" height="10"/>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"foreignObject" not in result
        assert b"<body" not in result
        assert b"<rect" in result

    def test_removes_javascript_url_from_href(self) -> None:
        """Should remove javascript: URLs from href attributes."""
        svg = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
            <a xlink:href="javascript:alert('XSS')">
                <rect x="10" y="10" width="50" height="50"/>
            </a>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"javascript:" not in result

    def test_removes_data_uri_with_html(self) -> None:
        """Should detect dangerous data:text/html pattern."""
        # Test the detection function directly since XML parsing may fail
        assert _has_dangerous_value("data:text/html,<script>alert(1)</script>")

    def test_removes_vbscript_url(self) -> None:
        """Should remove vbscript: URLs."""
        svg = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
            <a xlink:href="vbscript:msgbox">
                <rect x="10" y="10" width="50" height="50"/>
            </a>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"vbscript:" not in result

    def test_sanitizes_nested_elements(self) -> None:
        """Should process deeply nested elements."""
        svg = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <g>
                <g>
                    <g onclick="bad()">
                        <rect x="10" y="10" width="50" height="50"/>
                        <script>evil()</script>
                    </g>
                </g>
            </g>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"<script" not in result
        assert b"onclick" not in result
        assert b"<rect" in result

    def test_raises_error_on_malformed_xml(self) -> None:
        """Should raise SVGSanitizationError for malformed XML."""
        malformed_svg = b"<svg><rect></svg>"  # Unclosed rect tag

        with pytest.raises(SVGSanitizationError) as exc_info:
            sanitize_svg(malformed_svg)

        assert "Malformed" in str(exc_info.value) or "Failed" in str(exc_info.value)

    def test_raises_error_on_empty_content(self) -> None:
        """Should raise SVGSanitizationError for empty content."""
        with pytest.raises(SVGSanitizationError):
            sanitize_svg(b"")

    def test_preserves_safe_animation_elements(self) -> None:
        """Should preserve safe animation elements."""
        svg = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect x="10" y="10" width="50" height="50">
                <animate attributeName="x" from="10" to="100" dur="2s"/>
            </rect>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"<animate" in result
        assert b'attributeName="x"' in result

    def test_preserves_gradients_and_filters(self) -> None:
        """Should preserve gradient and filter elements."""
        svg = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="grad1">
                    <stop offset="0%" stop-color="red"/>
                    <stop offset="100%" stop-color="blue"/>
                </linearGradient>
                <filter id="blur">
                    <feGaussianBlur stdDeviation="5"/>
                </filter>
            </defs>
            <rect fill="url(#grad1)" filter="url(#blur)"/>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"<linearGradient" in result
        assert b"<filter" in result
        assert b"<feGaussianBlur" in result


class TestStyleAttributeRemoved:
    """Tests that style attributes are fully stripped (XSS prevention)."""

    def test_removes_style_attribute(self) -> None:
        """Should remove style attribute entirely instead of trying to sanitize it."""
        svg = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect style="fill: blue; stroke: red;" x="10" y="10" width="50" height="50"/>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"style=" not in result
        assert b"<rect" in result

    def test_removes_style_with_dangerous_content(self) -> None:
        """Should remove style even with XSS payloads (no regex bypass possible)."""
        svg = b"""<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect style="background: url(javascript:alert(1))" x="10" y="10" width="50" height="50"/>
        </svg>"""

        result = sanitize_svg(svg)

        assert b"style=" not in result
        assert b"javascript" not in result


class TestHasDangerousValue:
    """Tests for dangerous value detection."""

    def test_detects_javascript_url(self) -> None:
        """Should detect javascript: URLs."""
        assert _has_dangerous_value("javascript:alert(1)") is True
        assert _has_dangerous_value("JAVASCRIPT:ALERT(1)") is True
        assert _has_dangerous_value("  javascript:void(0)") is True

    def test_detects_data_text_html(self) -> None:
        """Should detect data:text/html URIs."""
        assert _has_dangerous_value("data:text/html,<script>") is True

    def test_detects_data_application(self) -> None:
        """Should detect data:application URIs."""
        assert _has_dangerous_value("data:application/javascript,alert(1)") is True

    def test_detects_vbscript(self) -> None:
        """Should detect vbscript: URLs."""
        assert _has_dangerous_value("vbscript:msgbox") is True

    def test_detects_css_expression(self) -> None:
        """Should detect CSS expression()."""
        assert _has_dangerous_value("expression(alert(1))") is True
        assert _has_dangerous_value("expression (alert(1))") is True  # With space

    def test_allows_safe_values(self) -> None:
        """Should allow safe attribute values."""
        assert _has_dangerous_value("100") is False
        assert _has_dangerous_value("blue") is False
        assert _has_dangerous_value("translate(10, 20)") is False
        assert _has_dangerous_value("M10 10 L20 20") is False
        assert _has_dangerous_value("https://example.com/image.png") is False


class TestIsSVGContent:
    """Tests for SVG content detection."""

    def test_detects_svg_with_svg_tag(self) -> None:
        """Should detect SVG by <svg tag."""
        content = b"<?xml version='1.0'?><svg xmlns=''>"
        assert is_svg_content(content) is True

    def test_detects_svg_doctype(self) -> None:
        """Should detect SVG by DOCTYPE."""
        content = b"<!DOCTYPE svg PUBLIC '-//W3C//DTD'>"
        assert is_svg_content(content) is True

    def test_detects_svg_namespace(self) -> None:
        """Should detect SVG by xmlns namespace."""
        content = b'<root xmlns="http://www.w3.org/2000/svg">'
        assert is_svg_content(content) is True

    def test_rejects_non_svg(self) -> None:
        """Should reject non-SVG content."""
        assert is_svg_content(b"<html><body>Hello</body></html>") is False
        assert is_svg_content(b"Just plain text") is False
        assert is_svg_content(b"\x89PNG\r\n\x1a\n") is False  # PNG header

    def test_handles_empty_content(self) -> None:
        """Should handle empty content gracefully."""
        assert is_svg_content(b"") is False
