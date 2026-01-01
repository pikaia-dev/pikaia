"""
SVG sanitization utilities.

Sanitizes user-uploaded SVG files to prevent XSS attacks by removing
potentially dangerous elements and attributes while preserving visual content.

SVG files can contain executable content like <script> tags, event handlers
(onclick, onload), and external resource references that pose security risks.
This module implements a strict whitelist-based approach.
"""

import re
from io import BytesIO

from defusedxml import ElementTree as DefusedET
from lxml import etree

# SVG namespace
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

# Whitelist of safe SVG elements (excluding script, foreignObject, etc.)
ALLOWED_ELEMENTS = frozenset([
    # Structure
    "svg", "g", "defs", "symbol", "use", "title", "desc", "metadata",
    # Shapes
    "circle", "ellipse", "line", "path", "polygon", "polyline", "rect",
    # Text
    "text", "tspan", "textPath",
    # Graphics
    "image", "clipPath", "mask", "pattern", "marker",
    # Filters
    "filter", "feBlend", "feColorMatrix", "feComponentTransfer",
    "feComposite", "feConvolveMatrix", "feDiffuseLighting",
    "feDisplacementMap", "feDropShadow", "feFlood", "feFuncA", "feFuncB",
    "feFuncG", "feFuncR", "feGaussianBlur", "feImage", "feMerge",
    "feMergeNode", "feMorphology", "feOffset", "feSpecularLighting",
    "feTile", "feTurbulence",
    # Gradients
    "linearGradient", "radialGradient", "stop",
    # Animation (safe subset - no script execution)
    "animate", "animateMotion", "animateTransform", "set", "mpath",
])

# Whitelist of safe attributes (excluding event handlers like onclick, onload)
ALLOWED_ATTRIBUTES = frozenset([
    # Core attributes
    "id", "class", "style", "lang", "tabindex",
    # Presentation attributes
    "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
    "stroke-dasharray", "stroke-dashoffset", "stroke-miterlimit",
    "stroke-opacity", "fill-opacity", "fill-rule", "opacity",
    "color", "display", "visibility", "overflow", "clip", "clip-path",
    "clip-rule", "mask", "filter", "flood-color", "flood-opacity",
    "lighting-color", "stop-color", "stop-opacity",
    "font-family", "font-size", "font-style", "font-weight", "font-variant",
    "text-anchor", "text-decoration", "dominant-baseline", "alignment-baseline",
    "baseline-shift", "letter-spacing", "word-spacing", "writing-mode",
    "direction", "unicode-bidi",
    # Geometry attributes
    "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
    "width", "height", "d", "points", "pathLength",
    "viewBox", "preserveAspectRatio", "transform", "transform-origin",
    # Reference attributes (safe subset)
    "href", "xlink:href", "gradientUnits", "gradientTransform",
    "spreadMethod", "patternUnits", "patternTransform",
    "markerUnits", "markerWidth", "markerHeight", "refX", "refY",
    "orient", "maskUnits", "maskContentUnits",
    "clipPathUnits", "filterUnits", "primitiveUnits",
    # Filter attributes
    "in", "in2", "result", "mode", "operator", "k1", "k2", "k3", "k4",
    "stdDeviation", "dx", "dy", "specularExponent", "specularConstant",
    "surfaceScale", "diffuseConstant", "azimuth", "elevation",
    "type", "values", "tableValues", "slope", "intercept",
    "amplitude", "exponent", "offset",
    # Animation attributes
    "attributeName", "attributeType", "begin", "dur", "end", "min", "max",
    "restart", "repeatCount", "repeatDur", "fill", "calcMode", "values",
    "keyTimes", "keySplines", "from", "to", "by", "additive", "accumulate",
    # Other safe attributes
    "version", "xmlns", "xmlns:xlink", "xml:space", "xml:lang",
    "baseProfile", "contentScriptType", "contentStyleType",
])

# Pre-computed lowercase versions for efficient case-insensitive matching
_ALLOWED_ELEMENTS_LOWER = frozenset(e.lower() for e in ALLOWED_ELEMENTS)
_ALLOWED_ATTRIBUTES_LOWER = frozenset(a.lower() for a in ALLOWED_ATTRIBUTES)

# Dangerous patterns in attribute values
DANGEROUS_PATTERNS = [
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"data:text/html", re.IGNORECASE),
    re.compile(r"data:application", re.IGNORECASE),
    re.compile(r"vbscript:", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),  # CSS expression()
]


class SVGSanitizationError(Exception):
    """Raised when SVG cannot be safely sanitized."""

    pass


def sanitize_svg(svg_content: bytes) -> bytes:
    """
    Sanitize SVG content by removing dangerous elements and attributes.

    Args:
        svg_content: Raw SVG file content as bytes

    Returns:
        Sanitized SVG content as bytes

    Raises:
        SVGSanitizationError: If SVG is malformed or cannot be sanitized
    """
    try:
        # Parse with defusedxml first to catch XXE attacks
        DefusedET.fromstring(svg_content)
    except Exception as e:
        raise SVGSanitizationError(f"Malformed or dangerous XML structure: {e}") from e

    try:
        # Parse with lxml for manipulation
        parser = etree.XMLParser(
            remove_comments=True,
            remove_pis=True,  # Remove processing instructions
            strip_cdata=True,
            resolve_entities=False,
            no_network=True,
        )
        tree = etree.parse(BytesIO(svg_content), parser)
        root = tree.getroot()
    except Exception as e:
        raise SVGSanitizationError(f"Failed to parse SVG: {e}") from e

    # Recursively sanitize elements
    _sanitize_element(root)

    # Serialize back to bytes
    return etree.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True,
    )


def _sanitize_element(element: etree._Element) -> bool:
    """
    Recursively sanitize an element and its children.

    Returns True if element should be kept, False if it should be removed.
    """
    # Get local name without namespace
    local_name = etree.QName(element.tag).localname if element.tag else ""

    # Remove elements not in whitelist
    if local_name.lower() not in _ALLOWED_ELEMENTS_LOWER:
        return False

    # Sanitize attributes
    attrs_to_remove = []
    for attr_name, attr_value in element.attrib.items():
        # Get local attribute name
        local_attr = etree.QName(attr_name).localname if "{" in attr_name else attr_name

        # Remove event handlers (on*)
        if local_attr.lower().startswith("on"):
            attrs_to_remove.append(attr_name)
            continue

        # Remove attributes not in whitelist
        if local_attr.lower() not in _ALLOWED_ATTRIBUTES_LOWER:
            attrs_to_remove.append(attr_name)
            continue

        # Check for dangerous patterns in attribute values
        if _has_dangerous_value(attr_value):
            attrs_to_remove.append(attr_name)
            continue

    for attr in attrs_to_remove:
        del element.attrib[attr]

    # Sanitize style attribute specifically
    if "style" in element.attrib:
        element.attrib["style"] = _sanitize_style(element.attrib["style"])

    # Recursively process children
    children_to_remove = []
    for child in element:
        if not _sanitize_element(child):
            children_to_remove.append(child)

    for child in children_to_remove:
        element.remove(child)

    return True


def _has_dangerous_value(value: str) -> bool:
    """Check if attribute value contains dangerous patterns."""
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(value):
            return True
    return False


def _sanitize_style(style: str) -> str:
    """
    Sanitize CSS style attribute.

    Removes url() references and dangerous patterns.
    """
    # Remove url() which could reference external resources or data URIs
    style = re.sub(r"url\s*\([^)]*\)", "", style, flags=re.IGNORECASE)

    # Remove expression() (IE-specific XSS vector)
    style = re.sub(r"expression\s*\([^)]*\)", "", style, flags=re.IGNORECASE)

    # Remove -moz-binding (Firefox XSS vector)
    style = re.sub(r"-moz-binding\s*:[^;]*", "", style, flags=re.IGNORECASE)

    # Remove behavior (IE XSS vector)
    style = re.sub(r"behavior\s*:[^;]*", "", style, flags=re.IGNORECASE)

    return style.strip()


def is_svg_content(content: bytes) -> bool:
    """Check if content appears to be SVG."""
    # Check for SVG signature in first 1KB
    header = content[:1024].lower()
    return b"<svg" in header or b"<!doctype svg" in header
