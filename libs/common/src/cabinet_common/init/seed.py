"""Seed синтетического реестра: карточки `fixtures/registry/*.json` → `core.registry_snapshot`.

Каждая карточка проверяется схемой `RegistryData` контракта и контрольной суммой ИНН; загрузка —
upsert по ИНН (повторный запуск не плодит строки, изменённая карточка обновляется).
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from cabinet_common.events.topics import find_contracts_dir
from cabinet_common.events.validation import load_schema_registry
from cabinet_common.inn import is_valid_inn

FIXTURES_DIR_ENV = "FIXTURES_DIR"
DOMAIN_SCHEMA_ID = "https://contracts.smart-credit.local/schemas/domain.schema.json"

UPSERT = text(
    """
    INSERT INTO registry_snapshot (
        inn, kpp, ogrn, name, opf, manager_name, address, okved, industry_group,
        registry_status, registered_at, liquidated_at, origin, fetched_at
    ) VALUES (
        :inn, :kpp, :ogrn, :name, :opf, :manager_name, :address, :okved, :industry_group,
        :registry_status, CAST(:registered_at AS date), CAST(:liquidated_at AS date),
        :origin, CAST(:fetched_at AS timestamptz)
    )
    ON CONFLICT (inn) DO UPDATE SET
        kpp = EXCLUDED.kpp, ogrn = EXCLUDED.ogrn, name = EXCLUDED.name, opf = EXCLUDED.opf,
        manager_name = EXCLUDED.manager_name, address = EXCLUDED.address,
        okved = EXCLUDED.okved, industry_group = EXCLUDED.industry_group,
        registry_status = EXCLUDED.registry_status, registered_at = EXCLUDED.registered_at,
        liquidated_at = EXCLUDED.liquidated_at, origin = EXCLUDED.origin,
        fetched_at = EXCLUDED.fetched_at
    RETURNING (xmax = 0) AS inserted
    """
)


class SeedError(Exception):
    """Фикстуры реестра не прошли проверку: init не должен загружать часть данных."""


@dataclass(frozen=True)
class SeedResult:
    inserted: int
    updated: int

    def describe(self) -> str:
        total = self.inserted + self.updated
        return f"карточек реестра: {total} (новых {self.inserted}, обновлено {self.updated})"


def find_registry_dir() -> Path:
    """`FIXTURES_DIR/registry` из окружения или `fixtures/registry` в корне репозитория."""
    override = os.environ.get(FIXTURES_DIR_ENV)
    if override:
        return Path(override) / "registry"
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "fixtures" / "registry"
        if candidate.is_dir():
            return candidate
    raise SeedError(f"каталог фикстур не найден: задайте {FIXTURES_DIR_ENV}")


def load_cards(
    registry_dir: Path | None = None, contracts_dir: Path | None = None
) -> list[dict[str, Any]]:
    """Читает и проверяет все карточки каталога; любая ошибка — `SeedError` с именем файла."""
    directory = registry_dir or find_registry_dir()
    registry = load_schema_registry(contracts_dir or find_contracts_dir())
    validator = Draft202012Validator(
        {"$ref": f"{DOMAIN_SCHEMA_ID}#/$defs/RegistryData"}, registry=registry
    )

    cards: list[dict[str, Any]] = []
    seen: dict[str, Path] = {}
    for file in sorted(directory.glob("*.json")):
        try:
            card = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SeedError(f"{file.name}: не удалось прочитать карточку ({exc})") from exc
        problems = [
            f"{'.'.join(str(p) for p in err.absolute_path) or '<корень>'}: {err.message}"
            for err in validator.iter_errors(card)
        ]
        problems += _check_consistency(card) if not problems else []
        if problems:
            raise SeedError(f"{file.name}: " + "; ".join(problems))
        if card["inn"] in seen:
            raise SeedError(f"{file.name}: ИНН {card['inn']} уже есть в {seen[card['inn']].name}")
        seen[card["inn"]] = file
        cards.append(card)
    return cards


def _check_consistency(card: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    inn = card["inn"]
    if not is_valid_inn(inn):
        problems.append(f"inn: неверная контрольная сумма {inn}")
    expected_len = 12 if card["opf"] == "IP" else 10
    if len(inn) != expected_len:
        problems.append(f"inn: для ОПФ {card['opf']} нужно {expected_len} цифр")
    liquidated = card["registry_status"] == "LIQUIDATED"
    if liquidated != (card["liquidated_at"] is not None):
        problems.append("liquidated_at: задаётся тогда и только тогда, когда статус LIQUIDATED")
    return problems


async def upsert_cards(engine: AsyncEngine, cards: list[dict[str, Any]]) -> SeedResult:
    """Загружает карточки одной транзакцией; возвращает число новых и обновлённых строк."""
    inserted = 0
    async with engine.begin() as conn:
        for card in cards:
            if (await conn.execute(UPSERT, card)).scalar_one():
                inserted += 1
    return SeedResult(inserted=inserted, updated=len(cards) - inserted)
