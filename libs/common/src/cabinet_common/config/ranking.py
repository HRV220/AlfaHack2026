"""Схемы `config/ranking_weights.yaml` и `config/thresholds.yaml` (ТЗ REC-06, CAT-03, SC-04)."""

import math
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cabinet_common.config.loader import ConfigModel

PRIORITIES = ("NONE", "MIN_PAYMENT", "MIN_OVERPAYMENT", "SPEED", "NO_COLLATERAL")
FACTORS = ("F1", "F2", "F3", "F4", "F5", "F6")
GRADES = ("A", "B", "C", "D")
CHANCES = ("HIGH", "MEDIUM", "LOW")


class RankingWeightsConfig(ConfigModel):
    weights: dict[str, dict[str, float]]

    @model_validator(mode="after")
    def _check(self) -> Self:
        if tuple(self.weights) != PRIORITIES:
            raise ValueError(f"weights: ожидались приоритеты {PRIORITIES} по порядку")
        for priority, row in self.weights.items():
            if tuple(row) != FACTORS:
                raise ValueError(f"weights.{priority}: ожидались факторы {FACTORS} по порядку")
            if any(not 0 <= w <= 1 for w in row.values()):
                raise ValueError(f"weights.{priority}: вес должен быть от 0 до 1")
            if not math.isclose(sum(row.values()), 1.0, abs_tol=1e-9):
                raise ValueError(f"weights.{priority}: сумма весов {sum(row.values())}, нужна 1")
        return self


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GradeRule(_Model):
    grade: str
    pd_lt: float | None = Field(gt=0, lt=1)
    rate_surcharge: float | None = Field(ge=0, le=1)


class ApprovalChance(_Model):
    pd_medium_from: float = Field(gt=0, lt=1)
    pd_low_from: float = Field(gt=0, lt=1)
    factor_scores: dict[str, float]


class Explanation(_Model):
    shap_top_n: int = Field(ge=1)


class Alternatives(_Model):
    max_count: int = Field(ge=0)
    min_score_ratio: float = Field(gt=0, le=1)


class ThresholdsConfig(ConfigModel):
    grades: tuple[GradeRule, ...]
    approval_chance: ApprovalChance
    explanation: Explanation
    alternatives: Alternatives

    @model_validator(mode="after")
    def _check(self) -> Self:
        if tuple(g.grade for g in self.grades) != GRADES:
            raise ValueError(f"grades: ожидались грейды {GRADES} по порядку")
        *bounded, last = self.grades
        bounds = [g.pd_lt for g in bounded]
        if any(b is None for b in bounds) or last.pd_lt is not None:
            raise ValueError("grades: границу pd_lt имеют все грейды, кроме последнего")
        floats = [b for b in bounds if b is not None]
        if floats != sorted(set(floats)):
            raise ValueError("grades: границы pd_lt должны строго возрастать")
        if last.rate_surcharge is not None:
            raise ValueError("grades: у последнего грейда (отказ) rate_surcharge должен быть null")
        if any(g.rate_surcharge is None for g in bounded):
            raise ValueError("grades: надбавка нужна всем грейдам, кроме последнего")
        chance = self.approval_chance
        if (chance.pd_medium_from, chance.pd_low_from) != (floats[1], floats[2]):
            raise ValueError(
                "approval_chance: границы PD должны совпадать с границами грейдов B и C"
            )
        if tuple(chance.factor_scores) != CHANCES:
            raise ValueError(f"approval_chance.factor_scores: ожидались ключи {CHANCES}")
        scores = list(chance.factor_scores.values())
        if any(not 0 <= s <= 1 for s in scores) or scores != sorted(scores, reverse=True):
            raise ValueError("approval_chance.factor_scores: значения 0–1, по убыванию HIGH→LOW")
        return self
