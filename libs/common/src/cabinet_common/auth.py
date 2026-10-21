"""Контракт JWT-сессии (арх. 14): company_id только из токена. Реализация — E04."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict

SESSION_TTL_HOURS = 8


class TokenRole(StrEnum):
    APPLICANT = "applicant"
    UNDERWRITER = "underwriter"


class TokenClaims(BaseModel):
    model_config = ConfigDict(frozen=True)

    sub: str
    company_id: str
    role: TokenRole
    iat: datetime
    exp: datetime


class TokenService(Protocol):
    def issue(self, sub: str, company_id: str, role: TokenRole) -> str: ...

    def verify(self, token: str) -> TokenClaims:
        """Возвращает claims или бросает исключение при неверной подписи и истёкшем сроке."""
        ...
