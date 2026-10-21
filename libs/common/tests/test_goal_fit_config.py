import json
from pathlib import Path

import pytest
from cabinet_common.config import ConfigError, load_config
from cabinet_common.config.goal_fit import GOALS, REGULARITIES, GoalFitConfig

ROOT = Path(__file__).resolve().parents[3]
GOAL_FIT = ROOT / "config" / "goal_fit.yaml"
DEFS = json.loads((ROOT / "docs/contracts/schemas/domain.schema.json").read_text(encoding="utf-8"))[
    "$defs"
]


def test_goals_and_regularities_match_contract() -> None:
    assert list(GOALS) == DEFS["Goal"]["enum"]
    assert list(REGULARITIES) == DEFS["Regularity"]["enum"]


def test_matrix_values_from_tz_table() -> None:
    matrix = load_config(GOAL_FIT, GoalFitConfig).data.matrix
    assert matrix["CASH_GAP"]["P1"] == 1.0
    assert matrix["SEASONAL"]["P3"] == 1.0
    assert matrix["EQUIPMENT"] == {"P1": 0, "P2": 0.2, "P3": 0, "P4": 1.0, "P5": 0.9, "P6": 0.9}
    assert matrix["OTHER"]["P4"] == 0.5
    assert load_config(GOAL_FIT, GoalFitConfig).data.regularity_bonus == {"RECURRING": {"P3": 0.2}}


def _broken(tmp_path: Path, old: str, new: str) -> Path:
    text = GOAL_FIT.read_bytes().decode("utf-8")
    assert old in text
    file = tmp_path / "goal_fit.yaml"
    file.write_bytes(text.replace(old, new, 1).encode("utf-8"))
    return file


@pytest.mark.parametrize(
    ("old", "new", "fragment"),
    [
        (
            "  OTHER:      {P1: 0.3, P2: 0.6, P3: 0.5, P4: 0.5, P5: 0.8, P6: 0.4}\n",
            "",
            "ожидались цели",
        ),
        (
            "PURCHASE:   {P1: 0.4, P2: 1.0, P3: 0.8, P4: 0.0, P5: 0.6, P6: 0.6}",
            "PURCHASE:   {P1: 0.4}",
            "ожидались продукты",
        ),
        ("P1: 1.0, P2: 0.6", "P1: 1.5, P2: 0.6", "от 0 до 1"),
        ("RECURRING: {P3: 0.2}", "WEEKLY: {P3: 0.2}", "неизвестная регулярность"),
        ("RECURRING: {P3: 0.2}", "RECURRING: {P9: 0.2}", "неверный продукт"),
    ],
)
def test_broken_matrix_rejected(tmp_path: Path, old: str, new: str, fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        load_config(_broken(tmp_path, old, new), GoalFitConfig)
