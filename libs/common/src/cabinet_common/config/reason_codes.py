"""Схема `config/reason_codes.yaml`: коды причин с текстами для клиента (ТЗ 5.4, SC-06)."""

import re
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cabinet_common.config.eligibility import ELIGIBILITY_CODES, STOP_CODES
from cabinet_common.config.loader import ConfigModel

PD_FACTOR_CODES = (
    "LOW_TURNOVER",
    "VOLATILE_TURNOVER",
    "FALLING_TURNOVER",
    "HIGH_DEBT_LOAD",
    "PAST_OVERDUE",
    "LOW_CASH_RESERVE",
    "CUSTOMER_CONCENTRATION",
    "YOUNG_BUSINESS",
    "AMOUNT_HIGH_FOR_TURNOVER",
)
LIMIT_CODES = ("AMOUNT_ABOVE_LIMIT",)
DOCUMENT_CODES = ("STATEMENT_NOT_VERIFIED", "INN_MISMATCH")

# Группа по ТЗ 5.4 для каждого кода
GROUP_OF = {
    **dict.fromkeys(STOP_CODES, "STOP"),
    **dict.fromkeys(ELIGIBILITY_CODES, "ELIGIBILITY"),
    **dict.fromkeys(PD_FACTOR_CODES, "PD_FACTOR"),
    **dict.fromkeys(LIMIT_CODES, "LIMIT"),
    **dict.fromkeys(DOCUMENT_CODES, "DOCUMENT"),
}
STOP_FRAUD_TEXT = "Проверку не удалось завершить дистанционно"


class ReasonCodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    group: str
    client_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if GROUP_OF.get(self.code) != self.group:
            raise ValueError(f"{self.code}: группа {self.group} не соответствует ТЗ 5.4")
        if re.search(r"\d|%", self.client_text):
            raise ValueError(f"{self.code}: в тексте не должно быть чисел и процентов")
        if self.code == "STOP_FRAUD" and self.client_text != STOP_FRAUD_TEXT:
            raise ValueError(f"STOP_FRAUD: текст должен быть «{STOP_FRAUD_TEXT}»")
        return self


class ReasonCodesConfig(ConfigModel):
    reason_codes: tuple[ReasonCodeConfig, ...]

    @model_validator(mode="after")
    def _complete(self) -> Self:
        codes = [entry.code for entry in self.reason_codes]
        if codes != list(GROUP_OF):
            raise ValueError("reason_codes: набор и порядок кодов должны соответствовать ТЗ 5.4")
        return self
