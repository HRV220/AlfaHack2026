"""Общий каркас FastAPI-приложения с `GET /health` (проверку зависимостей добавляет E02-02.9)."""

from fastapi import FastAPI


def create_app(service_name: str) -> FastAPI:
    app = FastAPI(title=service_name)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": service_name}

    return app
