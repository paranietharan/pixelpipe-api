"""Request router and dispatch system with middleware support."""

import re
import traceback
from typing import Awaitable, Callable
from urllib.parse import urlparse

from cors import build_cors_headers, handle_preflight
from errors import ApiException, error_response
from handlers import (
    delete_image_handler,
    get_image_handler,
    health_handler,
    upload_image_handler,
    transform_image_handler,
    variants_handler,
)

Middleware = Callable[[any, any], Awaitable[any]]


class Router:
    """HTTP router supporting parameter matching, middleware, and CORS."""

    def __init__(self):
        # Middlewares executed in sequence before route handlers
        self.middlewares: list[Middleware] = []

    def use(self, middleware: Middleware):
        """
        Register a middleware function.
        Signature: async def middleware(request, env) -> Response | None
        If the middleware returns a Response, dispatch stops and returns that Response.
        Use this for future authentication, rate limiting, logging, etc.
        """
        self.middlewares.append(middleware)

    async def dispatch(self, request, env):
        """Route and execute incoming request."""
        # 1. Normalize method and path
        method = getattr(request, "method", "GET")
        if hasattr(method, "name"):
            method = method.name
        method = str(method).upper()

        url_str = getattr(request, "url", "")
        parsed_url = urlparse(url_str)
        path = parsed_url.path or "/"

        # 2. Handle CORS preflight (OPTIONS)
        if method == "OPTIONS":
            return handle_preflight(request)

        try:
            # 3. Execute middleware chain (e.g. for future auth)
            for middleware in self.middlewares:
                middleware_res = await middleware(request, env)
                if middleware_res is not None:
                    return self._wrap_response_with_cors(middleware_res, request)

            # 4. Route matching
            response = await self._route_request(method, path, request, env)
            return self._wrap_response_with_cors(response, request)

        except ApiException as exc:
            err_resp = error_response(code=exc.code, message=exc.message, status=exc.status_code)
            return self._wrap_response_with_cors(err_resp, request)

        except Exception as exc:
            # Log internal traceback without exposing details to client
            print(f"[PixelPipe Error] Unhandled exception on {method} {path}: {exc}")
            traceback.print_exc()
            err_resp = error_response(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred",
                status=500,
            )
            return self._wrap_response_with_cors(err_resp, request)

    async def _route_request(self, method: str, path: str, request, env):
        """Match path and method to corresponding handler."""
        # GET /health
        if path == "/health":
            if method != "GET":
                return error_response(
                    "METHOD_NOT_ALLOWED",
                    f"Method {method} not allowed for /health",
                    status=405,
                )
            return await health_handler(request, env)

        # POST /v1/images
        if path == "/v1/images":
            if method != "POST":
                return error_response(
                    "METHOD_NOT_ALLOWED",
                    f"Method {method} not allowed for /v1/images",
                    status=405,
                )
            return await upload_image_handler(request, env)

        # Pattern: /v1/images/:imageId/transform
        m_transform = re.match(r"^/v1/images/([^/]+)/transform/?$", path)
        if m_transform:
            image_id = m_transform.group(1)
            if method != "GET":
                return error_response(
                    "METHOD_NOT_ALLOWED",
                    f"Method {method} not allowed for transformation",
                    status=405,
                )
            return await transform_image_handler(request, env, image_id)

        # Pattern: /v1/images/:imageId/variants
        m_variants = re.match(r"^/v1/images/([^/]+)/variants/?$", path)
        if m_variants:
            image_id = m_variants.group(1)
            if method != "GET":
                return error_response(
                    "METHOD_NOT_ALLOWED",
                    f"Method {method} not allowed for variants",
                    status=405,
                )
            return await variants_handler(request, env, image_id)

        # Pattern: /v1/images/:imageId
        m_image = re.match(r"^/v1/images/([^/]+)/?$", path)
        if m_image:
            image_id = m_image.group(1)
            if method == "GET":
                return await get_image_handler(request, env, image_id)
            elif method == "DELETE":
                return await delete_image_handler(request, env, image_id)
            else:
                return error_response(
                    "METHOD_NOT_ALLOWED",
                    f"Method {method} not allowed for image metadata",
                    status=405,
                )

        # 404 Route Not Found
        return error_response(
            code="NOT_FOUND",
            message=f"Endpoint '{method} {path}' not found",
            status=404,
        )

    def _wrap_response_with_cors(self, response, request):
        """Attach CORS headers to outgoing response if not already present."""
        cors_headers = build_cors_headers(request)
        if not cors_headers or not hasattr(response, "headers"):
            return response

        # If headers is a JS Headers or HTTPMessage instance
        headers = response.headers
        for k, v in cors_headers.items():
            if hasattr(headers, "set") and hasattr(headers, "has"):
                if not headers.has(k):
                    headers.set(k, v)
            elif hasattr(headers, "__setitem__") and hasattr(headers, "__contains__"):
                if k not in headers:
                    headers[k] = v

        return response


# Global router instance ready to register middleware or dispatch requests
router = Router()
