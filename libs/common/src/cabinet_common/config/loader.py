"""Чтение YAML-конфига, проверка схемой Pydantic, версия и хэш содержимого для снимков."""

import hashlib
from collections.abc import Hashable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ConfigError(Exception):
    """Конфиг нельзя прочитать или он не соответствует схеме: сервис не должен стартовать."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """`SafeLoader`, отклоняющий повторяющиеся ключи: иначе побеждает последний, без сообщения."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: set[Hashable] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if isinstance(key, Hashable) and key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"повторяющийся ключ {key!r}", key_node.start_mark
                )
            if isinstance(key, Hashable):
                seen.add(key)
        return super().construct_mapping(node, deep)


def freeze(value: Any) -> Any:
    """Рекурсивно делает словари неизменяемыми (`MappingProxyType`), списки — кортежами."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(freeze(item) for item in value)
    return value


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
        parsed: Any = yaml.load(raw, Loader=_UniqueKeyLoader)  # noqa: S506  # SafeLoader
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
