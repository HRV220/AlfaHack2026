"""Jinja2: общий рендер; страницы с токеном сессии не кэшируются."""

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def render(request: Request, name: str, context: dict[str, Any], status: int = 200) -> HTMLResponse:
    session = context.get("session")
    context = {**context, "csrf_token": session["csrf_token"] if session else ""}
    response = templates.TemplateResponse(request, name, context, status_code=status)
    response.headers["Cache-Control"] = "no-store"
    return response
