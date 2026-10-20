"""Границы монорепозитория: сервисы не зависят друг от друга (архитектура, раздел 21.1)."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICES = {
    "core-api": "core_api",
    "ml-service": "ml_service",
    "doc-service": "doc_service",
    "bank-sim": "bank_sim",
}


def test_services_do_not_import_each_other() -> None:
    for svc, mod in SERVICES.items():
        others = [m for m in SERVICES.values() if m != mod] + ["cabinet_web"]
        for path in (ROOT / "services" / svc).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for other in others:
                assert not re.search(rf"^\s*(from|import)\s+{other}\b", text, re.M), path


def test_services_do_not_depend_on_each_other() -> None:
    names = set(SERVICES) | {"web"}
    for pyproject in [
        *(ROOT / "services").glob("*/pyproject.toml"),
        ROOT / "web" / "pyproject.toml",
    ]:
        deps = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["dependencies"]
        assert not names & {re.split(r"[<>=!~ \[]", d)[0] for d in deps}, pyproject


def test_python_version_pinned() -> None:
    assert (ROOT / ".python-version").read_text().strip() == "3.12"
    assert (ROOT / "uv.lock").exists()


def test_repository_tree() -> None:
    expected = [
        "services/core-api", "services/ml-service", "services/doc-service", "services/bank-sim",
        "web", "config", "ml/generators", "ml/training", "ml/eval/recommendation",
        "ml/eval/assistant", "ml/eval/models", "ml/model_cards", "kb", "fixtures/registry",
        "fixtures/news", "deploy/compose", "deploy/observability", "docs/api",
        "docs/data-model", "docs/tests", "docs/research", "docs/contracts",
        "libs/common", "libs/contracts", "libs/featurebuilder",
    ]  # fmt: skip
    missing = [p for p in expected if not (ROOT / p).is_dir()]
    assert not missing, missing
