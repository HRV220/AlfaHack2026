"""Клиент core-api на httpx (async): пересылает cookie сессии и общий `correlation_id`."""

from typing import Any

import httpx
from cabinet_common.logging import correlation_id

API_PREFIX = "/api/v1"
SESSION_COOKIE = "session"


class CoreApiUnavailableError(Exception):
    """core-api не отвечает (сеть, таймаут, 5xx)."""


class CoreApiUnauthorizedError(Exception):
    """Нет сессии или она истекла (401)."""


class CoreApiClient:
    def __init__(
        self,
        base_url: str,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + API_PREFIX, timeout=timeout, transport=transport
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_session(self, session_cookie: str | None) -> dict[str, Any]:
        """`GET /auth/me`: сессия, компания и CSRF-токен. Без cookie — сразу 401."""
        if not session_cookie:
            raise CoreApiUnauthorizedError
        headers = {}
        cid = correlation_id.get()
        if cid:
            headers["X-Correlation-Id"] = cid
        try:
            headers["Cookie"] = f"{SESSION_COOKIE}={session_cookie}"
            response = await self._http.get("/auth/me", headers=headers)
        except httpx.HTTPError as exc:
            raise CoreApiUnavailableError(str(exc)) from exc
        if response.status_code == 401:
            raise CoreApiUnauthorizedError
        if response.status_code >= 500:
            raise CoreApiUnavailableError(f"core-api status {response.status_code}")
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data
