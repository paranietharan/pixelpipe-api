"""Error definitions and helpers for consistent JSON error responses."""

import json

try:
    from workers import Response
except (ImportError, ModuleNotFoundError):
    class Response:
        """Fallback Response class for environments where workers/pyodide is not loaded."""
        def __init__(self, body=None, status=200, headers=None):
            self.body = body
            self.status = status
            self.headers = dict(headers or {})

        @classmethod
        def from_json(cls, data, status=200, headers=None):
            h = {"content-type": "application/json"}
            if headers:
                h.update(headers)
            return cls(json.dumps(data), status=status, headers=h)


class ApiException(Exception):
    """Base API exception."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class BadRequestError(ApiException):
    """400 Bad Request."""

    def __init__(self, code: str = "BAD_REQUEST", message: str = "Bad request"):
        super().__init__(code=code, message=message, status_code=400)


class NotFoundError(ApiException):
    """404 Not Found."""

    def __init__(self, code: str = "NOT_FOUND", message: str = "Not found"):
        super().__init__(code=code, message=message, status_code=404)


class MethodNotAllowedError(ApiException):
    """405 Method Not Allowed."""

    def __init__(self, code: str = "METHOD_NOT_ALLOWED", message: str = "Method not allowed"):
        super().__init__(code=code, message=message, status_code=405)


class InternalServerError(ApiException):
    """500 Internal Server Error."""

    def __init__(self, code: str = "INTERNAL_ERROR", message: str = "An unexpected error occurred"):
        super().__init__(code=code, message=message, status_code=500)


def format_error_payload(code: str, message: str) -> dict:
    """Return the standard error dictionary format."""
    return {
        "error": {
            "code": code,
            "message": message,
        }
    }


def error_response(code: str, message: str, status: int = 400, headers: dict | None = None) -> Response:
    """Build a standard JSON error Response."""
    payload = format_error_payload(code, message)
    resp_headers = {"content-type": "application/json"}
    if headers:
        resp_headers.update(headers)

    # Use Response.from_json if available, or construct standard Response
    if hasattr(Response, "from_json"):
        return Response.from_json(payload, status=status, headers=resp_headers)
    return Response(json.dumps(payload), status=status, headers=resp_headers)
