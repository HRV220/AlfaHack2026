"""Страницы-заглушки: главная, проверка SSE-потока (E02-11.4, E02-11.6)."""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from cabinet_web.clients.core_api import (
    SESSION_COOKIE,
    CoreApiUnauthorizedError,
    CoreApiUnavailableError,
)
from cabinet_web.templating import render

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    session: dict[str, Any] | None = None
    try:
        session = await request.app.state.core_api.get_session(request.cookies.get(SESSION_COOKIE))
    except CoreApiUnauthorizedError:
        pass
    except CoreApiUnavailableError:
        return render(
            request,
            "error.html",
            {
                "title": "Кабинет временно недоступен",
                "message": "Не удаётся связаться с сервисом. Обновите страницу через минуту.",
            },
            status=503,
        )
    return render(request, "home.html", {"session": session})


@router.get("/stream-check", response_class=HTMLResponse)
async def stream_check(request: Request) -> HTMLResponse:
    """Служебная страница: подключается к `/api/v1/events/stream` и показывает `ping`."""
    return render(request, "stream_check.html", {})
