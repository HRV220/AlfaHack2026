import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
GIB = 1024**3


def load_module() -> ModuleType:
    path = ROOT / "deploy" / "compose" / "check_limits.py"
    spec = importlib.util.spec_from_file_location("check_limits", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_limits"] = module
    spec.loader.exec_module(module)
    return module


def config(**services: dict[str, object]) -> dict[str, object]:
    return {"services": services}


def test_within_budget_passes() -> None:
    cfg = config(a={"mem_limit": str(2 * GIB)}, b={"mem_limit": str(3 * GIB)})
    assert load_module().check(cfg, 14 * GIB) == []


def test_over_budget_fails() -> None:
    cfg = config(a={"mem_limit": str(8 * GIB)}, b={"mem_limit": str(7 * GIB)})
    problems = load_module().check(cfg, 14 * GIB)
    assert len(problems) == 1 and "больше бюджета" in problems[0]


def test_missing_limit_is_reported() -> None:
    cfg = config(a={"mem_limit": str(GIB)}, b={})
    assert load_module().check(cfg, 14 * GIB) == ["нет mem_limit: b"]


def test_one_shot_containers_are_not_counted() -> None:
    cfg = config(
        a={"mem_limit": str(10 * GIB)},
        init={"mem_limit": str(10 * GIB), "restart": "no"},
    )
    assert load_module().check(cfg, 14 * GIB) == []


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker не установлен")
def test_real_compose_fits_into_budget() -> None:
    module = load_module()
    assert module.check(module.load_config(), 14 * GIB) == []
