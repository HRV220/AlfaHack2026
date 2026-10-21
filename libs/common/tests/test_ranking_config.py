import json
from pathlib import Path

import pytest
from cabinet_common.config import ConfigError, load_config
from cabinet_common.config.ranking import (
    CHANCES,
    FACTORS,
    GRADES,
    PRIORITIES,
    RankingWeightsConfig,
    ThresholdsConfig,
)

ROOT = Path(__file__).resolve().parents[3]
WEIGHTS = ROOT / "config" / "ranking_weights.yaml"
THRESHOLDS = ROOT / "config" / "thresholds.yaml"
DEFS = json.loads((ROOT / "docs/contracts/schemas/domain.schema.json").read_text(encoding="utf-8"))[
    "$defs"
]


def _broken(src: Path, tmp_path: Path, old: str, new: str) -> Path:
    text = src.read_bytes().decode("utf-8")
    assert old in text
    file = tmp_path / src.name
    file.write_bytes(text.replace(old, new, 1).encode("utf-8"))
    return file


def test_constants_match_contract() -> None:
    assert list(PRIORITIES) == DEFS["Priority"]["enum"]
    assert list(FACTORS) == DEFS["Factor"]["enum"]
    assert list(GRADES) == DEFS["Grade"]["enum"]
    assert list(CHANCES) == DEFS["Chance"]["enum"]


def test_weights_from_tz_table_sum_to_one() -> None:
    weights = load_config(WEIGHTS, RankingWeightsConfig).data.weights
    assert weights["NONE"] == {
        "F1": 0.30,
        "F2": 0.20,
        "F3": 0.15,
        "F4": 0.10,
        "F5": 0.20,
        "F6": 0.05,
    }
    assert weights["MIN_PAYMENT"]["F3"] == 0.30
    assert weights["MIN_OVERPAYMENT"]["F4"] == 0.25
    assert weights["SPEED"]["F6"] == 0.25
    assert weights["NO_COLLATERAL"]["F6"] == 0.20
    assert all(abs(sum(row.values()) - 1) < 1e-9 for row in weights.values())


@pytest.mark.parametrize(
    ("old", "new", "fragment"),
    [
        ("F1: 0.30, F2: 0.20, F3: 0.15", "F1: 0.35, F2: 0.20, F3: 0.15", "сумма весов"),
        ("  SPEED:", "  FAST:", "ожидались приоритеты"),
        ("F5: 0.20, F6: 0.05}\n  MIN_PAYMENT", "F6: 0.05}\n  MIN_PAYMENT", "ожидались факторы"),
        ("F1: 0.30,", "F1: -0.30,", "от 0 до 1"),
    ],
)
def test_broken_weights_rejected(tmp_path: Path, old: str, new: str, fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        load_config(_broken(WEIGHTS, tmp_path, old, new), RankingWeightsConfig)


def test_thresholds_from_tz() -> None:
    cfg = load_config(THRESHOLDS, ThresholdsConfig).data
    assert [(g.grade, g.pd_lt, g.rate_surcharge) for g in cfg.grades] == [
        ("A", 0.02, 0.0),
        ("B", 0.05, 0.02),
        ("C", 0.12, 0.04),
        ("D", None, None),
    ]
    assert (cfg.approval_chance.pd_medium_from, cfg.approval_chance.pd_low_from) == (0.05, 0.12)
    assert cfg.approval_chance.factor_scores == {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.2}
    assert cfg.explanation.shap_top_n == 3
    assert (cfg.alternatives.max_count, cfg.alternatives.min_score_ratio) == (2, 0.7)


@pytest.mark.parametrize(
    ("old", "new", "fragment"),
    [
        ("pd_lt: 0.05,", "pd_lt: 0.01,", "строго возрастать"),
        ("pd_medium_from: 0.05", "pd_medium_from: 0.06", "совпадать с границами"),
        (
            "{grade: D, pd_lt: null, rate_surcharge: null}",
            "{grade: D, pd_lt: 0.5, rate_surcharge: null}",
            "последнего",
        ),
        (
            "{grade: D, pd_lt: null, rate_surcharge: null}",
            "{grade: D, pd_lt: null, rate_surcharge: 0.06}",
            "отказ",
        ),
        ("grade: B,", "grade: X,", "ожидались грейды"),
        ("MEDIUM: 0.6", "MEDIUM: 1.5", "по убыванию"),
        ("shap_top_n: 3", "shap_top_n: 0", "shap_top_n"),
        ("min_score_ratio: 0.7", "min_score_ratio: 7", "min_score_ratio"),
    ],
)
def test_broken_thresholds_rejected(tmp_path: Path, old: str, new: str, fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        load_config(_broken(THRESHOLDS, tmp_path, old, new), ThresholdsConfig)
