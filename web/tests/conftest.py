from collections.abc import Callable

import httpx
import pytest
from cabinet_web.clients.core_api import CoreApiClient
from cabinet_web.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient

Handler = Callable[[httpx.Request], httpx.Response]

SESSION = {
    "role": "CLIENT",
    "csrf_token": "tok-123",
    "expires_at": "2026-10-21T20:00:00+03:00",
    "company": {"inn": "7707083893", "name": "ООО Ромашка"},
    "applicant_role": None,
}


def ok_handler(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/api/v1/auth/me"
    if "session=s1" not in request.headers.get("cookie", ""):
        return httpx.Response(401, json={"code": "UNAUTHORIZED"})
    return httpx.Response(200, json=SESSION)


@pytest.fixture
def make_client() -> Callable[..., tuple[FastAPI, TestClient]]:
    def factory(handler: Handler = ok_handler) -> tuple[FastAPI, TestClient]:
        core = CoreApiClient("http://core", 1.0, transport=httpx.MockTransport(handler))
        app = create_app(core)
        return app, TestClient(app, raise_server_exceptions=False)

    return factory
