import hashlib
from pathlib import Path

import pytest
from cabinet_common.config import ConfigError, ConfigModel, load_config


class Sample(ConfigModel):
    items: list[str]
    weight: float = 1.0


def write(tmp_path: Path, text: str) -> Path:
    file = tmp_path / "sample.yaml"
    file.write_bytes(text.encode())
    return file


def test_loads_version_hash_and_data(tmp_path: Path) -> None:
    text = "version: 1.0.0\nitems: [a, b]\n"
    loaded = load_config(write(tmp_path, text), Sample)
    assert loaded.version == "1.0.0"
    assert loaded.data.items == ["a", "b"]
    assert loaded.content_hash == hashlib.sha256(text.encode()).hexdigest()


def test_hash_changes_with_content(tmp_path: Path) -> None:
    first = load_config(write(tmp_path, "version: '1'\nitems: []\n"), Sample)
    second = load_config(write(tmp_path, "version: '1'\nitems: [x]\n"), Sample)
    assert first.content_hash != second.content_hash


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("items: [a]\n", "version"),
        ("version: ''\nitems: []\n", "version"),
        ("version: 1.0.0\n", "items"),
        ("version: 1.0.0\nitems: [a]\nextra: 1\n", "extra"),
        ("version: 1.0.0\nitems: [a]\nweight: heavy\n", "weight"),
        ("version: [unclosed\n", "некорректный YAML"),
        ("- just\n- a list\n", "словарь"),
        ("", "словарь"),
    ],
)
def test_invalid_config_raises_with_file_and_reason(
    tmp_path: Path, text: str, fragment: str
) -> None:
    file = write(tmp_path, text)
    with pytest.raises(ConfigError) as info:
        load_config(file, Sample)
    assert str(file) in str(info.value)
    assert fragment in str(info.value)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="не удалось прочитать"):
        load_config(tmp_path / "absent.yaml", Sample)


def test_numeric_version_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="version"):
        load_config(write(tmp_path, "version: 1.0\nitems: []\n"), Sample)
