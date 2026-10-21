"""Схема `config/eligibility.yaml`: стоп-факторы и условия допуска (ТЗ SC-01, REC-01, 4.3)."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cabinet_common.config.loader import ConfigModel
from cabinet_common.config.products import PRODUCT_CODES

OPFS = ("IP", "LLC")
INDUSTRY_GROUPS = tuple(f"G{n:02d}" for n in range(1, 13))
REGISTRY_STATUSES = ("ACTIVE", "LIQUIDATING", "LIQUIDATED", "BANKRUPT", "REORGANIZING")

# Группы STOP и ELIGIBILITY справочника reason codes (ТЗ 5.4): коды, на которые ссылаются правила.
STOP_CODES = ("STOP_REGISTRY", "STOP_FRAUD", "STOP_OVERDUE", "STOP_YOUNG")
ELIGIBILITY_CODES = (
    "GOAL_MISMATCH",
    "AGE_BELOW_MIN",
    "INFLOW_BELOW_MIN",
    "INFLOW_HISTORY_SHORT",
    "INDUSTRY_NOT_IN_PROGRAM",
    "COLLATERAL_REQUIRED",
    "AMOUNT_BELOW_MIN",
    "CAPACITY_BELOW_MIN",
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _expect(actual: str, expected: str) -> None:
    if actual != expected:
        raise ValueError(f"ожидался reason_code {expected}, указан {actual}")


class RegistryStop(_Model):
    reason_code: str
    allowed_statuses: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        _expect(self.reason_code, "STOP_REGISTRY")
        if not set(self.allowed_statuses) <= set(REGISTRY_STATUSES):
            raise ValueError("allowed_statuses: неизвестный статус реестра")
        return self


class FraudStop(_Model):
    reason_code: str

    @model_validator(mode="after")
    def _check(self) -> Self:
        _expect(self.reason_code, "STOP_FRAUD")
        return self


class OverdueStop(_Model):
    reason_code: str
    over_days: int = Field(ge=0)
    window_months: int = Field(ge=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        _expect(self.reason_code, "STOP_OVERDUE")
        return self


class YoungStop(_Model):
    reason_code: str
    below_months: int = Field(ge=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        _expect(self.reason_code, "STOP_YOUNG")
        return self


class StopFactors(_Model):
    registry: RegistryStop
    fraud: FraudStop
    overdue: OverdueStop
    young: YoungStop


class Rule(_Model):
    reason_code: str


class Rules(_Model):
    goal: Rule
    amount_min: Rule
    collateral: Rule
    age: Rule
    inflow: Rule
    inflow_history: Rule
    industry: Rule
    capacity: Rule

    @model_validator(mode="after")
    def _codes(self) -> Self:
        expected = {
            "goal": "GOAL_MISMATCH",
            "amount_min": "AMOUNT_BELOW_MIN",
            "collateral": "COLLATERAL_REQUIRED",
            "age": "AGE_BELOW_MIN",
            "inflow": "INFLOW_BELOW_MIN",
            "inflow_history": "INFLOW_HISTORY_SHORT",
            "industry": "INDUSTRY_NOT_IN_PROGRAM",
            "capacity": "CAPACITY_BELOW_MIN",
        }
        for name, code in expected.items():
            try:
                _expect(getattr(self, name).reason_code, code)
            except ValueError as exc:
                raise ValueError(f"rules.{name}: {exc}") from exc
        return self


class Capacity(_Model):
    payment_share_of_sdp: float = Field(gt=0, le=1)
    overdraft_share_of_inflow: float = Field(gt=0, le=1)


class ProductConditions(_Model):
    min_business_age_months: int | None = Field(default=None, ge=1)
    min_avg_inflow_6m: float | None = Field(default=None, gt=0)
    inflow_each_of_last_months: int | None = Field(default=None, ge=1, le=6)
    industry_groups: tuple[str, ...] | None = None
    collateral_value_required: bool = False

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.industry_groups is not None and (
            not self.industry_groups or not set(self.industry_groups) <= set(INDUSTRY_GROUPS)
        ):
            raise ValueError("industry_groups: пусто или неизвестная отраслевая группа")
        return self


class EligibilityConfig(ConfigModel):
    opf: tuple[str, ...]
    stop_factors: StopFactors
    rules: Rules
    capacity: Capacity
    products: dict[str, ProductConditions]

    @model_validator(mode="after")
    def _check(self) -> Self:
        if set(self.opf) != set(OPFS):
            raise ValueError(f"opf: CAT-05 требует {OPFS}, получено {self.opf}")
        if tuple(self.products) != PRODUCT_CODES:
            raise ValueError(f"products: ожидались {PRODUCT_CODES} по порядку")
        return self
