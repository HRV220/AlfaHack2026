import json
import os
from pathlib import Path

import pytest
from cabinet_common.config import ConfigError, load_config
from cabinet_common.config.eligibility import EligibilityConfig
from cabinet_common.config.reason_codes import GROUP_OF, STOP_FRAUD_TEXT, ReasonCodesConfig

ROOT = Path(__file__).resolve().parents[3]
REASON_CODES = ROOT / "config" / "reason_codes.yaml"
DEFS = json.loads((ROOT / "docs/contracts/schemas/domain.schema.json").read_text(encoding="utf-8"))[
    "$defs"
]


def test_codes_and_groups_match_contract() -> None:
    entries = load_config(REASON_CODES, ReasonCodesConfig).data.reason_codes
    assert {e.code for e in entries} == set(DEFS["ReasonCode"]["enum"])
    assert {e.group for e in entries} <= set(DEFS["ReasonGroup"]["enum"])
    assert len(entries) == len(DEFS["ReasonCode"]["enum"]) == 24


def test_entry_fields_match_contract_entry() -> None:
    contract = set(DEFS["ReasonCodeEntry"]["properties"]) - {"version"}
    entry = load_config(REASON_CODES, ReasonCodesConfig).data.reason_codes[0]
    assert set(entry.model_dump()) == contract


def test_every_code_has_text_and_fraud_text_is_fixed() -> None:
    entries = load_config(REASON_CODES, ReasonCodesConfig).data.reason_codes
    assert all(e.client_text.strip() for e in entries)
    assert next(e for e in entries if e.code == "STOP_FRAUD").client_text == STOP_FRAUD_TEXT


def test_eligibility_rules_reference_codes_with_texts() -> None:
    cfg = load_config(ROOT / "config" / "eligibility.yaml", EligibilityConfig).data
    rule_codes = {s.reason_code for s in vars(cfg.stop_factors).values()}
    rule_codes |= {r.reason_code for r in vars(cfg.rules).values()}
    texted = {e.code for e in load_config(REASON_CODES, ReasonCodesConfig).data.reason_codes}
    assert rule_codes <= texted


def _broken(tmp_path: Path, old: str, new: str) -> Path:
    text = REASON_CODES.read_bytes().decode("utf-8")
    assert old in text
    file = tmp_path / "reason_codes.yaml"
    file.write_bytes(text.replace(old, new, 1).encode("utf-8"))
    return file


@pytest.mark.parametrize(
    ("old", "new", "fragment"),
    [
        (
            'group: STOP, client_text: "Бизнес работает слишком',
            'group: LIMIT, client_text: "Бизнес работает слишком',
            "не соответствует",
        ),
        ('"Поступления на счёт снижаются"', '""', "client_text"),
        ('"Поступления на счёт снижаются"', '"Поступления упали на 20%"', "чисел"),
        (
            '"Проверку не удалось завершить дистанционно"',
            '"Подозрение на мошенничество"',
            "STOP_FRAUD",
        ),
        ("code: INN_MISMATCH", "code: SOMETHING_ELSE", "не соответствует"),
    ],
)
def test_broken_reason_codes_rejected(tmp_path: Path, old: str, new: str, fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        load_config(_broken(tmp_path, old, new), ReasonCodesConfig)


def test_group_map_covers_all_codes() -> None:
    assert set(GROUP_OF) == set(DEFS["ReasonCode"]["enum"])


def test_missing_code_rejected(tmp_path: Path) -> None:
    lines = REASON_CODES.read_bytes().decode("utf-8").splitlines()
    file = tmp_path / "reason_codes.yaml"
    kept = [x for x in lines if "code: INN_MISMATCH" not in x]
    file.write_bytes(os.linesep.join(kept).encode("utf-8"))
    with pytest.raises(ConfigError, match="набор и порядок"):
        load_config(file, ReasonCodesConfig)
