"""Чтение YAML-конфига, проверка схемой Pydantic, версия и хэш содержимого для снимков."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ConfigError(Exception):
    """Конфиг нельзя прочитать или он не соответствует схеме: сервис не должен стартовать."""


class ConfigModel(BaseModel):
    """Базовая схема файла конфигурации: обязательное поле `version` (тип `Version` контракта)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(min_length=1, max_length=64)


@dataclass(frozen=True)
class LoadedConfig[T: ConfigModel]:
    path: Path
    version: str
    content_hash: str
    data: T


def load_config[T: ConfigModel](path: Path | str, model: type[T]) -> LoadedConfig[T]:
    """Читает `path`, проверяет схемой `model`; любая ошибка — `ConfigError` с именем файла."""
    file = Path(path)
    try:
        raw = file.read_bytes()
    except OSError as exc:
        raise ConfigError(f"{file}: не удалось прочитать файл ({exc.strerror or exc})") from exc

    try:
        parsed: Any = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{file}: некорректный YAML ({exc})") from exc
    if not isinstance(parsed, dict):
        raise ConfigError(f"{file}: ожидался словарь верхнего уровня")

    try:
        data = model.model_validate(parsed)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in err['loc']) or '<корень>'}: {err['msg']}"
            for err in exc.errors()
        )
        raise ConfigError(f"{file}: невалидный конфиг — {problems}") from exc

    return LoadedConfig(
        path=file,
        version=data.version,
        content_hash=hashlib.sha256(raw).hexdigest(),
        data=data,
    )
