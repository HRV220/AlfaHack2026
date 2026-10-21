"""Схема `config/okved_groups.yaml`: ОКВЭД 2 → отраслевая группа (ТЗ PRF-02, раздел 6)."""

import re
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cabinet_common.config.eligibility import INDUSTRY_GROUPS
from cabinet_common.config.loader import ConfigModel

OKVED_PATTERN = re.compile(r"^[0-9]{2}(\.[0-9]{1,2}){0,2}$")  # RegistryData.okved в контракте
_CLASSES = re.compile(r"^(\d{2})(?:-(\d{2}))?$")


def _parse_classes(classes: tuple[str, ...]) -> list[tuple[int, int]]:
    ranges = []
    for item in classes:
        match = _CLASSES.match(item)
        if match is None:
            raise ValueError(f"класс ОКВЭД «{item}»: ожидалось «47» или «10-33»")
        low = int(match.group(1))
        high = int(match.group(2) or low)
        if not 1 <= low <= high <= 99:
            raise ValueError(f"класс ОКВЭД «{item}»: диапазон должен быть в пределах 01–99")
        ranges.append((low, high))
    return ranges


class OkvedGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    group: str
    name: str = Field(min_length=1)
    classes: tuple[str, ...]

    @model_validator(mode="after")
    def _check(self) -> Self:
        _parse_classes(self.classes)
        return self


class OkvedGroupsConfig(ConfigModel):
    default_group: str
    groups: tuple[OkvedGroup, ...]

    @model_validator(mode="after")
    def _check(self) -> Self:
        if tuple(g.group for g in self.groups) != INDUSTRY_GROUPS:
            raise ValueError(f"groups: ожидались группы {INDUSTRY_GROUPS} по порядку")
        by_group = {g.group: g for g in self.groups}
        if self.default_group not in by_group or by_group[self.default_group].classes:
            raise ValueError("default_group: группа должна существовать и не иметь своих классов")
        seen: dict[int, str] = {}
        for item in self.groups:
            for low, high in _parse_classes(item.classes):
                for number in range(low, high + 1):
                    if number in seen:
                        raise ValueError(
                            f"класс {number:02d} в группах {seen[number]} и {item.group}"
                        )
                    seen[number] = item.group
        return self

    def group_for_okved(self, okved: str) -> str:
        """Группа по основному ОКВЭД; класс вне таблицы — `default_group`."""
        if OKVED_PATTERN.match(okved) is None:
            raise ValueError(f"ОКВЭД «{okved}» не соответствует формату контракта")
        number = int(okved[:2])
        for item in self.groups:
            if any(low <= number <= high for low, high in _parse_classes(item.classes)):
                return item.group
        return self.default_group
