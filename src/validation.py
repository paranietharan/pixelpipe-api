"""Validation helpers for upload and transformation parameters."""

import os
import re
from urllib.parse import parse_qs, urlparse

from config import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_FITS,
    ALLOWED_FORMATS,
    CONTENT_TYPE_ALIASES,
    FORMAT_TO_MIME,
    MAX_DIMENSION,
    MAX_QUALITY,
    MIN_DIMENSION,
    MIN_QUALITY,
)
from errors import BadRequestError


def sanitize_filename(filename: str | None) -> str:
    """Sanitize original filename to prevent path traversal or unsafe characters."""
    if not filename:
        return "image"
    # Strip any directory path components
    basename = os.path.basename(filename.strip().replace("\\", "/"))
    # Keep only safe characters: alphanumeric, dots, underscores, dashes
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", basename)
    # Avoid empty string or hidden files like ".gitignore"
    cleaned = cleaned.lstrip(".")
    return cleaned if cleaned else "image"


def normalize_content_type(raw_type: str | None) -> str:
    """Normalize and validate image content type."""
    if not raw_type:
        return ""
    # Strip parameters like charset if present
    content_type = raw_type.split(";")[0].strip().lower()
    return CONTENT_TYPE_ALIASES.get(content_type, content_type)


def validate_image_file(file_obj) -> tuple[str, str, int]:
    """
    Validate that an uploaded file object exists and has an allowed image content type.
    Returns: (filename, normalized_content_type, size)
    """
    if file_obj is None:
        raise BadRequestError(
            code="FILE_MISSING",
            message="A file must be provided in the 'file' field",
        )

    # Some form implementations return a string if a text input was submitted instead of a file
    if isinstance(file_obj, str):
        raise BadRequestError(
            code="FILE_MISSING",
            message="The 'file' field must contain an image file, not plain text",
        )

    # Check content type
    raw_type = getattr(file_obj, "content_type", None) or getattr(file_obj, "type", None)
    normalized_type = normalize_content_type(raw_type)

    if not normalized_type or normalized_type not in ALLOWED_CONTENT_TYPES:
        allowed_list = ", ".join(sorted(["JPEG", "PNG", "WebP", "GIF", "AVIF"]))
        raise BadRequestError(
            code="INVALID_CONTENT_TYPE",
            message=f"Unsupported image type '{raw_type or 'unknown'}'. Allowed types: {allowed_list}",
        )

    filename = sanitize_filename(getattr(file_obj, "name", None))
    size = getattr(file_obj, "size", 0)

    return filename, normalized_type, size


def validate_transform_params(query_dict: dict[str, list[str] | str]) -> dict:
    """
    Validate and parse image transformation query parameters.
    Returns validated dict containing:
    {
        "width": int | None,
        "height": int | None,
        "fit": str | None,
        "format": str | None,
        "quality": int | None,
    }
    """
    # Helper to extract a single query parameter value
    def get_single(key: str) -> str | None:
        val = query_dict.get(key)
        if val is None:
            return None
        if isinstance(val, list):
            return val[0] if val else None
        return str(val)

    # Width validation
    raw_width = get_single("width")
    width = None
    if raw_width is not None:
        try:
            width = int(raw_width)
            if width < MIN_DIMENSION or width > MAX_DIMENSION:
                raise ValueError()
        except (ValueError, TypeError):
            raise BadRequestError(
                code="INVALID_PARAMETER",
                message=f"'width' must be an integer between {MIN_DIMENSION} and {MAX_DIMENSION}",
            )

    # Height validation
    raw_height = get_single("height")
    height = None
    if raw_height is not None:
        try:
            height = int(raw_height)
            if height < MIN_DIMENSION or height > MAX_DIMENSION:
                raise ValueError()
        except (ValueError, TypeError):
            raise BadRequestError(
                code="INVALID_PARAMETER",
                message=f"'height' must be an integer between {MIN_DIMENSION} and {MAX_DIMENSION}",
            )

    # At least one of width or height must be supplied
    if width is None and height is None:
        raise BadRequestError(
            code="INVALID_PARAMETER",
            message="At least one of 'width' or 'height' must be supplied",
        )

    # Fit validation
    raw_fit = get_single("fit")
    fit = None
    if raw_fit is not None:
        fit = raw_fit.strip().lower()
        if fit not in ALLOWED_FITS:
            allowed_fits = ", ".join(sorted(ALLOWED_FITS))
            raise BadRequestError(
                code="INVALID_PARAMETER",
                message=f"Invalid 'fit' value '{raw_fit}'. Allowed values: {allowed_fits}",
            )

    # Format validation
    raw_format = get_single("format")
    fmt = None
    if raw_format is not None:
        fmt = raw_format.strip().lower()
        if fmt not in ALLOWED_FORMATS:
            allowed_fmts = ", ".join(sorted(ALLOWED_FORMATS))
            raise BadRequestError(
                code="INVALID_PARAMETER",
                message=f"Invalid 'format' value '{raw_format}'. Allowed values: {allowed_fmts}",
            )

    # Quality validation
    raw_quality = get_single("quality")
    quality = None
    if raw_quality is not None:
        try:
            quality = int(raw_quality)
            if quality < MIN_QUALITY or quality > MAX_QUALITY:
                raise ValueError()
        except (ValueError, TypeError):
            raise BadRequestError(
                code="INVALID_PARAMETER",
                message=f"'quality' must be an integer between {MIN_QUALITY} and {MAX_QUALITY}",
            )

    return {
        "width": width,
        "height": height,
        "fit": fit,
        "format": fmt,
        "quality": quality,
    }


def parse_query_params(url_str: str) -> dict[str, str]:
    """Parse query parameters from URL string into a single-value dict."""
    parsed = urlparse(url_str)
    qs = parse_qs(parsed.query)
    return {k: v[0] for k, v in qs.items() if v}


def resolve_output_format(
    requested_format: str | None,
    accept_header: str | None,
    original_content_type: str | None = None,
) -> tuple[str, bool]:
    """
    Resolve target output MIME format from requested format and Accept header.
    Returns (target_mime_type, is_auto_negotiated).
    """
    if requested_format and requested_format != "auto":
        return FORMAT_TO_MIME[requested_format], False

    # auto-negotiation or default
    accept = (accept_header or "").lower()
    if "image/avif" in accept:
        return "image/avif", True
    if "image/webp" in accept:
        return "image/webp", True

    # Fallback to original content type if supported output format
    if original_content_type in FORMAT_TO_MIME.values():
        return original_content_type, True

    return "image/jpeg", True
