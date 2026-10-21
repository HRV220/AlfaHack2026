"""Приложение web: серверный рендеринг (FastAPI + Jinja2 + HTMX), ADR 17."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from cabinet_common.health import create_app as create_base_app
from cabinet_common.logging import configure_logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from cabinet_web.clients.core_api import CoreApiClient
from cabinet_web.middleware import CorrelationMiddleware, CsrfMiddleware
from cabinet_web.routes import pages
from cabinet_web.settings import WebSettings
from cabinet_web.templating import BASE_DIR, render


def create_app(core_api: CoreApiClient | None = None) -> FastAPI:
    settings = WebSettings()
    configure_logging(settings.log_level)
    client = core_api or CoreApiClient(settings.core_api_url, settings.core_api_timeout_sec)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await client.aclose()

    app = create_base_app(settings.service_name)
    app.router.lifespan_context = lifespan
    app.state.core_api = client
    # Последний добавленный выполняется первым: correlation_id нужен и в CSRF-проверке.
    app.add_middleware(CsrfMiddleware, client=client, ttl_sec=settings.csrf_cache_ttl_sec)
    app.add_middleware(CorrelationMiddleware)
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    app.include_router(pages.router)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 404:
            return render(
                request,
                "error.html",
                {
                    "title": "Страница не найдена",
                    "message": "Проверьте адрес или вернитесь на главную.",
                },
                status=404,
            )
        return HTMLResponse(str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def server_error(request: Request, _: Exception) -> Response:
        return render(
            request,
            "error.html",
            {"title": "Что-то пошло не так", "message": "Попробуйте позже."},
            status=500,
        )

    return app


app = create_app()
