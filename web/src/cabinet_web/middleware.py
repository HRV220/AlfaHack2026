"""Middleware web: сквозной `correlation_id` и CSRF-защита изменяющих запросов (E02-11.5)."""

import hmac
import time
import uuid
from collections.abc import Awaitable, Callable

from cabinet_common.logging import correlation_id
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from cabinet_web.clients.core_api import (
    SESSION_COOKIE,
    CoreApiClient,
    CoreApiUnauthorizedError,
    CoreApiUnavailableError,
)
from cabinet_web.problem import problem_response

CORRELATION_HEADER = "X-Correlation-Id"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CACHE_LIMIT = 1024

Next = Callable[[Request], Awaitable[Response]]


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Next) -> Response:
        cid = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        token = correlation_id.set(cid)
        try:
            response = await call_next(request)
        finally:
            correlation_id.reset(token)
        response.headers[CORRELATION_HEADER] = cid
        return response


class CsrfMiddleware(BaseHTTPMiddleware):
    """Сверяет `X-CSRF-Token` с токеном, который core-api выдаёт в `GET /auth/me`."""

    def __init__(self, app: ASGIApp, client: CoreApiClient, ttl_sec: int) -> None:
        super().__init__(app)
        self._client = client
        self._ttl = ttl_sec
        self._cache: dict[str, tuple[str, float]] = {}

    async def _expected_token(self, session: str) -> str:
        cached = self._cache.get(session)
        if cached and cached[1] > time.monotonic():
            return cached[0]
        token = str((await self._client.get_session(session))["csrf_token"])
        if len(self._cache) >= CACHE_LIMIT:
            self._cache.clear()
        self._cache[session] = (token, time.monotonic() + self._ttl)
        return token

    async def dispatch(self, request: Request, call_next: Next) -> Response:
        if request.method in SAFE_METHODS:
            return await call_next(request)
        session = request.cookies.get(SESSION_COOKIE)
        supplied = request.headers.get(CSRF_HEADER)
        if not session:
            return problem_response(request, 401, "UNAUTHORIZED", "Нужен вход", "Нет сессии.")
        if not supplied:
            return problem_response(
                request, 403, "FORBIDDEN", "Запрос отклонён", "Нет заголовка X-CSRF-Token."
            )
        try:
            expected = await self._expected_token(session)
        except CoreApiUnauthorizedError:
            self._cache.pop(session, None)
            return problem_response(
                request, 401, "UNAUTHORIZED", "Нужен вход", "Сессия не действует."
            )
        except CoreApiUnavailableError:
            return problem_response(
                request, 503, "INTERNAL", "Сервис недоступен", "Не удалось проверить сессию."
            )
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            return problem_response(
                request, 403, "FORBIDDEN", "Запрос отклонён", "Неверный X-CSRF-Token."
            )
        return await call_next(request)
