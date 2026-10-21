import json
from pathlib import Path
from typing import Any

import pytest
from cabinet_common.init.seed import SeedError, find_registry_dir, load_cards

REGISTRY = find_registry_dir()


def write_card(directory: Path, name: str, **changes: Any) -> Path:
    card = json.loads((REGISTRY / "7707083893.json").read_text("utf-8"))
    card.update(changes)
    file = directory / f"{name}.json"
    file.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    return file


def test_repository_fixtures_cover_llc_ip_and_liquidated() -> None:
    cards = {card["inn"]: card for card in load_cards(REGISTRY)}
    assert len(cards) == 3
    assert {card["opf"] for card in cards.values()} == {"LLC", "IP"}
    assert {card["registry_status"] for card in cards.values()} == {"ACTIVE", "LIQUIDATED"}
    assert cards["7707083893"]["origin"] == "SYNTHETIC_REGISTRY"


def test_ip_card_has_twelve_digit_inn_and_no_kpp() -> None:
    ip = next(card for card in load_cards(REGISTRY) if card["opf"] == "IP")
    assert len(ip["inn"]) == 12
    assert ip["kpp"] is None


def test_wrong_checksum_is_rejected(tmp_path: Path) -> None:
    write_card(tmp_path, "bad", inn="7707083892")
    with pytest.raises(SeedError, match="контрольная сумма"):
        load_cards(tmp_path)


def test_card_not_matching_schema_is_rejected_with_file_name(tmp_path: Path) -> None:
    write_card(tmp_path, "bad", okved="not-an-okved")
    with pytest.raises(SeedError, match=r"bad\.json.*okved"):
        load_cards(tmp_path)


def test_unknown_field_is_rejected(tmp_path: Path) -> None:
    write_card(tmp_path, "bad", extra="x")
    with pytest.raises(SeedError, match="bad.json"):
        load_cards(tmp_path)


def test_inn_length_must_match_opf(tmp_path: Path) -> None:
    write_card(tmp_path, "bad", opf="IP")
    with pytest.raises(SeedError, match="ОПФ IP"):
        load_cards(tmp_path)


def test_liquidated_status_needs_liquidation_date(tmp_path: Path) -> None:
    write_card(tmp_path, "bad", registry_status="LIQUIDATED")
    with pytest.raises(SeedError, match="liquidated_at"):
        load_cards(tmp_path)
    write_card(tmp_path, "bad", liquidated_at="2025-01-01")
    with pytest.raises(SeedError, match="liquidated_at"):
        load_cards(tmp_path)


def test_duplicate_inn_is_rejected(tmp_path: Path) -> None:
    write_card(tmp_path, "a")
    write_card(tmp_path, "b")
    with pytest.raises(SeedError, match="уже есть в a.json"):
        load_cards(tmp_path)


def test_broken_json_is_reported(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(SeedError, match="broken.json"):
        load_cards(tmp_path)


def test_empty_directory_gives_no_cards(tmp_path: Path) -> None:
    assert load_cards(tmp_path) == []
