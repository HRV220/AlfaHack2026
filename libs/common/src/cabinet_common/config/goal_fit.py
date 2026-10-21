"""Схема `config/goal_fit.yaml`: матрица «цель × продукт» (ТЗ 4.3, CAT-02)."""

from collections.abc import Mapping
from typing import Any, Self

from pydantic import Field, field_validator, model_validator

from cabinet_common.config.loader import ConfigModel, freeze
from cabinet_common.config.products import PRODUCT_CODES

GOALS = ("CASH_GAP", "PURCHASE", "SEASONAL", "EQUIPMENT", "RENOVATION", "CONTRACT", "OTHER")
REGULARITIES = ("ONE_TIME", "RECURRING")


class GoalFitConfig(ConfigModel):
    matrix: Mapping[str, Mapping[str, float]]
    regularity_bonus: Mapping[str, Mapping[str, float]] = Field(
        default_factory=dict, validate_default=True
    )

    @field_validator("matrix", "regularity_bonus", mode="after")
    @classmethod
    def _frozen(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return freeze(value)  # type: ignore[no-any-return]

    @model_validator(mode="after")
    def _complete(self) -> Self:
        if set(self.matrix) != set(GOALS):
            raise ValueError(f"matrix: ожидались цели {GOALS}, получено {tuple(self.matrix)}")
        for goal, row in self.matrix.items():
            if set(row) != set(PRODUCT_CODES):
                raise ValueError(f"matrix.{goal}: ожидались продукты {PRODUCT_CODES}")
            if any(not 0 <= value <= 1 for value in row.values()):
                raise ValueError(f"matrix.{goal}: значения должны быть от 0 до 1")
        for regularity, bonuses in self.regularity_bonus.items():
            if regularity not in REGULARITIES:
                raise ValueError(f"regularity_bonus: неизвестная регулярность {regularity}")
            if not set(bonuses) <= set(PRODUCT_CODES) or any(
                not 0 <= b <= 1 for b in bonuses.values()
            ):
                raise ValueError(f"regularity_bonus.{regularity}: неверный продукт или прибавка")
        return self
