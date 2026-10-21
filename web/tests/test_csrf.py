from collections.abc import Callable

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from .conftest import ok_handler


def _client_with_post(make_client: Callable[..., tuple[FastAPI, TestClient]], handler=ok_handler):  # type: ignore[no-untyped-def]
    app, client = make_client(handler)

    @app.post("/echo")
    async def echo() -> dict[str, bool]:
        return {"done": True}

    return client


def test_post_without_token_is_forbidden(make_client) -> None:  # type: ignore[no-untyped-def]
    client = _client_with_post(make_client)
    client.cookies.set("session", "s1")
    response = client.post("/echo")
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "FORBIDDEN"
    assert body["status"] == 403
    assert body["correlation_id"]


def test_post_with_wrong_token_is_forbidden(make_client) -> None:  # type: ignore[no-untyped-def]
    client = _client_with_post(make_client)
    client.cookies.set("session", "s1")
    response = client.post("/echo", headers={"X-CSRF-Token": "other"})
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_post_with_valid_token_passes(make_client) -> None:  # type: ignore[no-untyped-def]
    client = _client_with_post(make_client)
    client.cookies.set("session", "s1")
    response = client.post("/echo", headers={"X-CSRF-Token": "tok-123"})
    assert response.status_code == 200
    assert response.json() == {"done": True}


def test_post_without_session_is_unauthorized(make_client) -> None:  # type: ignore[no-untyped-def]
    client = _client_with_post(make_client)
    response = client.post("/echo", headers={"X-CSRF-Token": "tok-123"})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_post_with_expired_session_is_unauthorized(make_client) -> None:  # type: ignore[no-untyped-def]
    client = _client_with_post(make_client)
    client.cookies.set("session", "stale")
    response = client.post("/echo", headers={"X-CSRF-Token": "tok-123"})
    assert response.status_code == 401


def test_post_when_core_api_is_down_fails_closed(make_client) -> None:  # type: ignore[no-untyped-def]
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = _client_with_post(make_client, down)
    client.cookies.set("session", "s1")
    response = client.post("/echo", headers={"X-CSRF-Token": "tok-123"})
    assert response.status_code == 503


def test_expected_token_is_cached_per_session(make_client) -> None:  # type: ignore[no-untyped-def]
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return ok_handler(request)

    client = _client_with_post(make_client, handler)
    client.cookies.set("session", "s1")
    for _ in range(3):
        assert client.post("/echo", headers={"X-CSRF-Token": "tok-123"}).status_code == 200
    assert len(calls) == 1


def test_safe_methods_skip_csrf(make_client) -> None:  # type: ignore[no-untyped-def]
    client = _client_with_post(make_client)
    assert client.get("/health").status_code == 200
    assert client.head("/health").status_code in (200, 405)
