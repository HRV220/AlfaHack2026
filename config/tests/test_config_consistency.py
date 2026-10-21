"""Согласованность конфигов с контрактом и версиями снимка (ТЗ CAT-01–CAT-03, REC-08)."""

import json
import shutil
from pathlib import Path

import pytest
from cabinet_common.config import ConfigError
from cabinet_common.config.registry import CONFIG_FILES, LoadedConfigs, load_all_configs

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DEFS = json.loads((ROOT / "docs/contracts/schemas/domain.schema.json").read_text(encoding="utf-8"))[
    "$defs"
]


def enum(name: str) -> set[str]:
    return set(DEFS[name]["enum"])


def test_every_yaml_is_registered() -> None:
    on_disk = {path.name for path in CONFIG_DIR.glob("*.yaml")}
    assert on_disk == {file.name for file in CONFIG_FILES}


def test_all_configs_load() -> None:
    configs = load_all_configs(CONFIG_DIR)
    assert all(loaded.version for loaded in vars(configs).values())


def test_enumerations_are_within_contract() -> None:
    c = load_all_configs(CONFIG_DIR)
    assert {p.code for p in c.products.data.products} == enum("ProductCode")
    assert set(c.goal_fit.data.matrix) == enum("Goal")
    assert {code for row in c.goal_fit.data.matrix.values() for code in row} == enum("ProductCode")
    assert set(c.goal_fit.data.regularity_bonus) <= enum("Regularity")
    assert set(c.eligibility.data.opf) == enum("Opf")
    assert set(c.eligibility.data.stop_factors.registry.allowed_statuses) <= enum("RegistryStatus")
    assert set(c.eligibility.data.products) == enum("ProductCode")
    groups = {g for p in c.eligibility.data.products.values() for g in p.industry_groups or ()}
    assert groups <= enum("IndustryGroup")
    assert set(c.ranking_weights.data.weights) == enum("Priority")
    assert {f for row in c.ranking_weights.data.weights.values() for f in row} == enum("Factor")
    assert {g.grade for g in c.thresholds.data.grades} == enum("Grade")
    assert set(c.thresholds.data.approval_chance.factor_scores) == enum("Chance")
    assert {e.code for e in c.reason_codes.data.reason_codes} == enum("ReasonCode")
    assert {e.group for e in c.reason_codes.data.reason_codes} <= enum("ReasonGroup")
    assert {g.group for g in c.okved_groups.data.groups} == enum("IndustryGroup")


def test_versions_fill_config_versions_fields() -> None:
    versions = load_all_configs(CONFIG_DIR).versions()
    contract_fields = set(DEFS["ConfigVersions"]["properties"])
    assert set(versions) == {"catalog", "goal_fit", "grades", "weights", "reason_codes"}
    assert set(versions) <= contract_fields
    for version in versions.values():
        assert 1 <= len(version) <= DEFS["Version"]["maxLength"]


def test_changing_config_version_changes_snapshot_version(tmp_path: Path) -> None:
    shutil.copytree(CONFIG_DIR, tmp_path / "config", ignore=shutil.ignore_patterns("tests"))
    work = tmp_path / "config"
    before = load_all_configs(work).versions()
    file = work / "products.yaml"
    file.write_bytes(file.read_bytes().replace(b'version: "1.0.0"', b'version: "1.1.0"', 1))
    after = load_all_configs(work).versions()
    assert after["catalog"] == "1.1.0"
    assert {k: v for k, v in after.items() if k != "catalog"} == {
        k: v for k, v in before.items() if k != "catalog"
    }


def test_content_hash_changes_with_content(tmp_path: Path) -> None:
    shutil.copytree(CONFIG_DIR, tmp_path / "config", ignore=shutil.ignore_patterns("tests"))
    work = tmp_path / "config"
    before = load_all_configs(work).thresholds.content_hash
    file = work / "thresholds.yaml"
    file.write_bytes(file.read_bytes() + "\n# правка\n".encode())
    assert load_all_configs(work).thresholds.content_hash != before


def test_broken_file_stops_loading_with_its_name(tmp_path: Path) -> None:
    shutil.copytree(CONFIG_DIR, tmp_path / "config", ignore=shutil.ignore_patterns("tests"))
    (tmp_path / "config" / "thresholds.yaml").write_bytes(b"version: ''" + bytes([10]))
    with pytest.raises(ConfigError, match="thresholds.yaml"):
        load_all_configs(tmp_path / "config")


def test_missing_file_stops_loading(tmp_path: Path) -> None:
    shutil.copytree(CONFIG_DIR, tmp_path / "config", ignore=shutil.ignore_patterns("tests"))
    (tmp_path / "config" / "okved_groups.yaml").unlink()
    with pytest.raises(ConfigError, match="okved_groups.yaml"):
        load_all_configs(tmp_path / "config")


def test_registry_matches_loaded_configs_fields() -> None:
    fields = set(LoadedConfigs.__dataclass_fields__)
    assert {file.name.removesuffix(".yaml") for file in CONFIG_FILES} == fields
    keys = {file.versions_key for file in CONFIG_FILES if file.versions_key}
    assert keys == set(load_all_configs(CONFIG_DIR).versions())


def test_loaded_values_are_immutable() -> None:
    c = load_all_configs(CONFIG_DIR)
    with pytest.raises(TypeError):
        c.goal_fit.data.matrix["CASH_GAP"]["P4"] = 1.0  # type: ignore[index]
    with pytest.raises(TypeError):
        c.ranking_weights.data.weights["NONE"] = {}  # type: ignore[index]
    with pytest.raises(TypeError):
        c.eligibility.data.products["P1"] = None  # type: ignore[index]
    with pytest.raises(TypeError):
        c.thresholds.data.approval_chance.factor_scores["HIGH"] = 0.0  # type: ignore[index]
