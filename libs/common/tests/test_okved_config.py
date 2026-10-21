import json
from pathlib import Path

import pytest
from cabinet_common.config import ConfigError, load_config
from cabinet_common.config.eligibility import EligibilityConfig
from cabinet_common.config.okved import OKVED_PATTERN, OkvedGroupsConfig

ROOT = Path(__file__).resolve().parents[3]
OKVED = ROOT / "config" / "okved_groups.yaml"
DEFS = json.loads((ROOT / "docs/contracts/schemas/domain.schema.json").read_text(encoding="utf-8"))[
    "$defs"
]


def _cfg() -> OkvedGroupsConfig:
    return load_config(OKVED, OkvedGroupsConfig).data


def test_groups_match_contract() -> None:
    assert [g.group for g in _cfg().groups] == DEFS["IndustryGroup"]["enum"]


def test_okved_pattern_matches_contract() -> None:
    assert OKVED_PATTERN.pattern == DEFS["RegistryData"]["properties"]["okved"]["pattern"]


@pytest.mark.parametrize(
    ("okved", "group"),
    [
        ("47", "G01"), ("47.11", "G01"), ("45.20", "G02"), ("46", "G02"), ("55", "G03"),
        ("56.10.1", "G03"), ("10", "G04"), ("33", "G04"), ("41", "G05"), ("43.99", "G05"),
        ("49", "G06"), ("53", "G06"), ("01", "G07"), ("03", "G07"), ("58", "G08"),
        ("62.01", "G08"), ("63", "G08"), ("69", "G09"), ("75", "G09"), ("77", "G09"),
        ("82", "G09"), ("90", "G10"), ("96", "G10"), ("85", "G11"), ("88", "G11"),
        ("84", "G12"), ("76", "G12"), ("64", "G12"), ("04", "G12"), ("97", "G12"), ("35", "G12"),
    ],
)  # fmt: skip
def test_okved_to_group_from_tz_table(okved: str, group: str) -> None:
    assert _cfg().group_for_okved(okved) == group


def test_every_class_resolves_to_a_group() -> None:
    cfg = _cfg()
    assert {cfg.group_for_okved(f"{n:02d}") for n in range(1, 100)} == set(
        DEFS["IndustryGroup"]["enum"]
    )


def test_p6_program_groups_exist_in_catalog() -> None:
    p6 = load_config(ROOT / "config" / "eligibility.yaml", EligibilityConfig).data.products["P6"]
    assert set(p6.industry_groups or ()) <= {g.group for g in _cfg().groups}


@pytest.mark.parametrize("bad", ["4", "47.", "47.111", "ab", ""])
def test_bad_okved_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="формату"):
        _cfg().group_for_okved(bad)


def _broken(tmp_path: Path, old: str, new: str) -> Path:
    text = OKVED.read_bytes().decode("utf-8")
    assert old in text
    file = tmp_path / "okved_groups.yaml"
    file.write_bytes(text.replace(old, new, 1).encode("utf-8"))
    return file


@pytest.mark.parametrize(
    ("old", "new", "fragment"),
    [
        ('classes: ["47"]', 'classes: ["47", "10"]', "в группах"),
        ('classes: ["10-33"]', 'classes: ["33-10"]', "диапазон"),
        ('classes: ["01-03"]', 'classes: ["1-3"]', "ожидалось"),
        ('classes: ["01-03"]', 'classes: ["00-03"]', "диапазон"),
        ("group: G07", "group: G70", "ожидались группы"),
        ("default_group: G12", "default_group: G01", "default_group"),
        ('"Другие отрасли", classes: []', '"Другие отрасли", classes: ["99"]', "default_group"),
    ],
)
def test_broken_catalog_rejected(tmp_path: Path, old: str, new: str, fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        load_config(_broken(tmp_path, old, new), OkvedGroupsConfig)
