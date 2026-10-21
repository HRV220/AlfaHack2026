import json
from pathlib import Path

import pytest
from cabinet_common.config import ConfigError, load_config
from cabinet_common.config.eligibility import (
    ELIGIBILITY_CODES,
    INDUSTRY_GROUPS,
    OPFS,
    REGISTRY_STATUSES,
    STOP_CODES,
    EligibilityConfig,
)

ROOT = Path(__file__).resolve().parents[3]
ELIGIBILITY = ROOT / "config" / "eligibility.yaml"
DEFS = json.loads((ROOT / "docs/contracts/schemas/domain.schema.json").read_text(encoding="utf-8"))[
    "$defs"
]


def _rule_codes(cfg: EligibilityConfig) -> set[str]:
    stops = {s.reason_code for s in vars(cfg.stop_factors).values()}
    rules = {r.reason_code for r in vars(cfg.rules).values()}
    return stops | rules


def test_constants_match_contract() -> None:
    assert list(OPFS) == DEFS["Opf"]["enum"]
    assert list(INDUSTRY_GROUPS) == DEFS["IndustryGroup"]["enum"]
    assert list(REGISTRY_STATUSES) == DEFS["RegistryStatus"]["enum"]
    assert set(STOP_CODES) | set(ELIGIBILITY_CODES) <= set(DEFS["ReasonCode"]["enum"])


def test_every_rule_references_existing_code_and_all_codes_covered() -> None:
    cfg = load_config(ELIGIBILITY, EligibilityConfig).data
    codes = _rule_codes(cfg)
    assert codes <= set(DEFS["ReasonCode"]["enum"])
    assert codes == set(STOP_CODES) | set(ELIGIBILITY_CODES)


def test_values_from_tz() -> None:
    cfg = load_config(ELIGIBILITY, EligibilityConfig).data
    assert cfg.stop_factors.overdue.over_days == 60
    assert cfg.stop_factors.overdue.window_months == 12
    assert cfg.stop_factors.young.below_months == 6
    assert cfg.stop_factors.registry.allowed_statuses == ("ACTIVE",)
    assert cfg.capacity.payment_share_of_sdp == 0.5
    p = cfg.products
    assert p["P1"].inflow_each_of_last_months == 6
    assert p["P2"].min_business_age_months == 6
    assert (p["P3"].min_business_age_months, p["P3"].min_avg_inflow_6m) == (12, 1_000_000)
    assert p["P4"].min_business_age_months == 12
    assert p["P5"].collateral_value_required
    assert p["P6"].industry_groups == ("G04", "G07", "G08", "G11")


def _broken(tmp_path: Path, old: str, new: str) -> Path:
    text = ELIGIBILITY.read_bytes().decode("utf-8")
    assert old in text
    file = tmp_path / "eligibility.yaml"
    file.write_bytes(text.replace(old, new, 1).encode("utf-8"))
    return file


@pytest.mark.parametrize(
    ("old", "new", "fragment"),
    [
        ("reason_code: STOP_FRAUD", "reason_code: STOP_BOGUS", "ожидался reason_code STOP_FRAUD"),
        ("reason_code: GOAL_MISMATCH", "reason_code: AGE_BELOW_MIN", "rules.goal"),
        ("allowed_statuses: [ACTIVE]", "allowed_statuses: [OPEN]", "статус реестра"),
        ("opf: [IP, LLC]", "opf: [IP]", "CAT-05"),
        ("industry_groups: [G04, G07, G08, G11]", "industry_groups: [G99]", "отраслевая группа"),
        ("payment_share_of_sdp: 0.5 ", "payment_share_of_sdp: 1.5 ", "payment_share_of_sdp"),
        ("  P6: {", "  P7: {", "ожидались"),
        ("P2: {min_business_age_months: 6}", "P2: {min_age: 6}", "min_age"),
    ],
)
def test_broken_config_rejected(tmp_path: Path, old: str, new: str, fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        load_config(_broken(tmp_path, old, new), EligibilityConfig)
