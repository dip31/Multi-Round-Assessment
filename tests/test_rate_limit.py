import asyncio

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response

from app.middleware import rate_limit
from app.middleware.rate_limit import RateLimitMiddleware


def _request(method: str, token: str, ip: str = "127.0.0.1") -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": "/test",
        "raw_path": b"/test",
        "query_string": b"",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
        "client": (ip, 12345),
        "server": ("testserver", 80),
    })


def test_read_rate_limit_is_separate_per_authenticated_user_and_write_bucket(monkeypatch):
    monkeypatch.setattr(rate_limit, "decode_access_token", lambda token: {"sub": token})
    monkeypatch.setattr(rate_limit.time, "time", lambda: 1000.0)
    middleware = RateLimitMiddleware(Starlette(), max_requests=2, read_max_requests=3)

    async def next_response(_request):
        return Response(status_code=200)

    async def send(method, token):
        return await middleware.dispatch(_request(method, token), next_response)

    assert [asyncio.run(send("GET", "faculty-1")).status_code for _ in range(3)] == [200, 200, 200]
    assert asyncio.run(send("GET", "faculty-1")).status_code == 429
    assert asyncio.run(send("GET", "faculty-2")).status_code == 200

    assert asyncio.run(send("POST", "faculty-1")).status_code == 200
    assert asyncio.run(send("POST", "faculty-1")).status_code == 200
    assert asyncio.run(send("POST", "faculty-1")).status_code == 429


def test_invalid_or_missing_bearer_token_uses_ip_bucket(monkeypatch):
    monkeypatch.setattr(rate_limit, "decode_access_token", lambda _token: None)
    first = _request("GET", "invalid-a", ip="192.0.2.5")
    second = _request("GET", "invalid-b", ip="192.0.2.5")
    other = _request("GET", "invalid-c", ip="192.0.2.6")

    assert RateLimitMiddleware._client_key(first) == "ip:192.0.2.5"
    assert RateLimitMiddleware._client_key(second) == "ip:192.0.2.5"
    assert RateLimitMiddleware._client_key(other) == "ip:192.0.2.6"
