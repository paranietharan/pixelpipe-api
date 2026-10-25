"""CORS handling and header helpers for local frontend development."""

from config import ALLOWED_ORIGINS
from errors import Response


def get_cors_origin(request_origin: str | None) -> str | None:
    """Check if the requested origin is allowed and return the header value."""
    if not request_origin:
        return "*" if "*" in ALLOWED_ORIGINS else None

    if "*" in ALLOWED_ORIGINS:
        return "*"

    if request_origin in ALLOWED_ORIGINS:
        return request_origin

    return None


def get_request_header(request, name: str) -> str | None:
    """Helper to safely get a header from Request object."""
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    # Support both dict and HTTPMessage/Headers interface
    if hasattr(headers, "get"):
        return headers.get(name)
    return None


def build_cors_headers(request) -> dict[str, str]:
    """Generate CORS headers for a request."""
    origin = get_request_header(request, "origin")
    allowed_origin = get_cors_origin(origin)

    if not allowed_origin:
        return {}

    headers = {
        "Access-Control-Allow-Origin": allowed_origin,
        "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept",
        "Access-Control-Max-Age": "86400",
    }
    if allowed_origin != "*":
        headers["Vary"] = "Origin"
    return headers


def handle_preflight(request) -> Response:
    """Handle HTTP OPTIONS preflight requests."""
    cors_headers = build_cors_headers(request)
    return Response(None, status=204, headers=cors_headers)


def apply_cors_to_headers(target_headers: dict, request) -> dict:
    """Add CORS headers to a headers dictionary."""
    cors_headers = build_cors_headers(request)
    for k, v in cors_headers.items():
        if k not in target_headers:
            target_headers[k] = v
        elif k.lower() == "vary" and "origin" not in target_headers[k].lower():
            target_headers[k] = f"{target_headers[k]}, Origin"
    return target_headers
