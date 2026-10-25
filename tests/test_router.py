"""Unit tests for the Router, Health route, and error formats."""

import json
import pytest
from router import Router


class DummyRequest:
    def __init__(self, method="GET", url="https://example.com/health", headers=None):
        self.method = method
        self.url = url
        self.headers = headers or {}


class DummyEnv:
    pass


@pytest.mark.asyncio
async def test_health_route():
    router = Router()
    req = DummyRequest(method="GET", url="https://example.com/health")
    resp = await router.dispatch(req, DummyEnv())

    assert resp.status == 200
    body = json.loads(resp.body)
    assert body == {
        "status": "ok",
        "service": "pixelpipe-api",
    }


@pytest.mark.asyncio
async def test_cors_preflight():
    router = Router()
    req = DummyRequest(
        method="OPTIONS",
        url="https://example.com/v1/images",
        headers={"origin": "http://localhost:3000"},
    )
    resp = await router.dispatch(req, DummyEnv())
    assert resp.status == 204
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"


@pytest.mark.asyncio
async def test_not_found_route():
    router = Router()
    req = DummyRequest(method="GET", url="https://example.com/v1/nonexistent")
    resp = await router.dispatch(req, DummyEnv())
    assert resp.status == 404
    body = json.loads(resp.body)
    assert body["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_method_not_allowed():
    router = Router()
    req = DummyRequest(method="POST", url="https://example.com/health")
    resp = await router.dispatch(req, DummyEnv())
    assert resp.status == 405
    body = json.loads(resp.body)
    assert body["error"]["code"] == "METHOD_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_middleware_interception():
    router = Router()

    # Define an auth middleware that rejects requests without Authorization header
    async def auth_middleware(request, env):
        if request.url.endswith("/health"):
            return None
        auth = request.headers.get("authorization")
        if not auth:
            from errors import error_response
            return error_response("UNAUTHORIZED", "Missing authorization header", status=401)
        return None

    router.use(auth_middleware)

    # Health route should pass through
    req_health = DummyRequest(method="GET", url="https://example.com/health")
    resp_health = await router.dispatch(req_health, DummyEnv())
    assert resp_health.status == 200

    # Protected route without auth header should be intercepted
    req_images = DummyRequest(method="POST", url="https://example.com/v1/images")
    resp_images = await router.dispatch(req_images, DummyEnv())
    assert resp_images.status == 401
    body = json.loads(resp_images.body)
    assert body["error"]["code"] == "UNAUTHORIZED"
