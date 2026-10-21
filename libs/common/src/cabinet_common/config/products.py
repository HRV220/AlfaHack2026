"""Схема `config/products.yaml`: каталог из 6 продуктов (ТЗ 4.3, CAT-01; контракт `Product`)."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cabinet_common.config.loader import ConfigModel

PRODUCT_CODES = ("P1", "P2", "P3", "P4", "P5", "P6")


class SecurityKind(StrEnum):
    NONE = "none"
    GUARANTOR = "guarantor"
    COLLATERAL = "collateral"
    COLLATERAL_OR_GUARANTOR = "collateral_or_guarantor"


class CollateralKind(StrEnum):
    EQUIPMENT = "equipment"
    VEHICLE = "vehicle"
    REAL_ESTATE = "real_estate"


class Security(BaseModel):
    """Машинное правило обеспечения; клиентский текст — `collateral_rule` продукта."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    required: SecurityKind
    # Порог суммы: не больше одного из двух; без порога требование действует всегда.
    amount_over: float | None = Field(default=None, gt=0)  # «свыше N»: сумма > N
    amount_from: float | None = Field(default=None, gt=0)  # «от N»: сумма >= N
    collateral_kinds: tuple[CollateralKind, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.amount_over is not None and self.amount_from is not None:
            raise ValueError("amount_over и amount_from взаимоисключающие")
        if self.required is SecurityKind.NONE and (
            self.amount_over is not None or self.amount_from is not None
        ):
            raise ValueError("для required=none порог суммы не задаётся")
        has_collateral = self.required in (
            SecurityKind.COLLATERAL,
            SecurityKind.COLLATERAL_OR_GUARANTOR,
        )
        if has_collateral != bool(self.collateral_kinds):
            raise ValueError("collateral_kinds задаются тогда и только тогда, когда возможен залог")
        return self


class ProductConfig(BaseModel):
    """Поля `Product` контракта (без `catalog_version` — это `version` файла) и машинные правила."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    name: str = Field(min_length=1)
    amount_min: float = Field(gt=0)
    amount_max: float = Field(gt=0)
    amount_max_rule: str | None
    term_min_months: int = Field(ge=1)
    term_max_months: int = Field(ge=1)
    base_rate: float = Field(ge=0, le=1)
    grade_surcharge_applies: bool
    commission_pct: float = Field(ge=0, le=1)
    deferral_months: int = Field(ge=0)
    deferral_min_term_months: int = Field(ge=0)  # срок, с которого действует отсрочка; 0 — нет
    collateral_rule: str = Field(min_length=1)
    eligibility_rule: str = Field(min_length=1)
    fast: bool
    security: Security

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.code not in PRODUCT_CODES:
            raise ValueError(f"неизвестный код продукта {self.code}")
        if self.amount_min > self.amount_max:
            raise ValueError(f"{self.code}: amount_min больше amount_max")
        if self.term_min_months > self.term_max_months:
            raise ValueError(f"{self.code}: term_min_months больше term_max_months")
        if (self.deferral_months > 0) != (self.deferral_min_term_months > 0):
            raise ValueError(
                f"{self.code}: deferral_months и deferral_min_term_months задаются вместе"
            )
        return self


class ProductsConfig(ConfigModel):
    products: tuple[ProductConfig, ...]

    @model_validator(mode="after")
    def _all_six_once(self) -> Self:
        codes = tuple(product.code for product in self.products)
        if codes != PRODUCT_CODES:
            raise ValueError(f"ожидались продукты {PRODUCT_CODES} по порядку, получено {codes}")
        return self
