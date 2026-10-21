"""Ответ об ошибке по RFC 9457 в форме контракта (`Problem`)."""

from cabinet_common.logging import correlation_id
from fastapi import Request
from fastapi.responses import JSONResponse


def problem_response(
    request: Request, status: int, code: str, title: str, detail: str
) -> JSONResponse:
    body = {
        "type": f"about:blank#{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "correlation_id": correlation_id.get(),
    }
    return JSONResponse(body, status_code=status, media_type="application/problem+json")
