from pathlib import Path
from typing import Any

import httpx
import pytest
from cabinet_common.init.runner import Step, StepWarning, run_steps
from cabinet_common.init.steps import (
    InitSettings,
    default_steps,
    llm_step,
    mlflow_step,
    parse_broker,
    wait_tcp,
)


class FakeResponse:
    def __init__(self, payload: dict[str, Any] | None = None, status: int = 200) -> None:
        self._payload = payload or {}
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "ошибка",
                request=httpx.Request("GET", "http://x"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict[str, Any]:
        return self._payload


def patch_get(monkeypatch: pytest.MonkeyPatch, response: FakeResponse | Exception) -> None:
    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(httpx, "get", fake_get)


def test_step_order_and_optional_flags() -> None:
    plan = default_steps(InitSettings())
    assert [step.name for step in plan] == [
        "wait",
        "bootstrap",
        "migrations",
        "topics",
        "schemas",
        "seed",
        "mlflow",
        "llm",
    ]
    assert {step.name for step in plan if not step.required} == {"mlflow", "llm"}


def test_llm_ready_when_model_is_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_get(monkeypatch, FakeResponse({"models": [{"name": "qwen2.5:7b-instruct-q4_K_M"}]}))
    assert "LLM готова" in llm_step(InitSettings())


def test_llm_model_missing_is_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_get(monkeypatch, FakeResponse({"models": [{"name": "other:1b"}]}))
    with pytest.raises(StepWarning, match="не загружена"):
        llm_step(InitSettings())


def test_llm_unreachable_is_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_get(monkeypatch, httpx.ConnectError("отказ в соединении"))
    with pytest.raises(StepWarning, match="Ollama недоступна"):
        llm_step(InitSettings())


def test_llm_check_skipped_when_assistant_is_disabled() -> None:
    assert "пропущена" in llm_step(InitSettings(assistant_enabled=False))


def test_mlflow_unreachable_is_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_get(monkeypatch, httpx.ConnectError("отказ в соединении"))
    with pytest.raises(StepWarning, match="MLflow недоступен"):
        mlflow_step(InitSettings())


def test_mlflow_without_model_artifacts_is_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_get(monkeypatch, FakeResponse())
    with pytest.raises(StepWarning, match="артефактов моделей нет"):
        mlflow_step(InitSettings())


def test_mlflow_with_model_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "pd").mkdir()
    (tmp_path / "pd" / "MLmodel").write_text("flavors: {}", encoding="utf-8")
    patch_get(monkeypatch, FakeResponse())
    assert "найдено артефактов моделей: 1" in mlflow_step(InitSettings(models_dir=tmp_path))


def test_wait_tcp_gives_up_after_timeout() -> None:
    with pytest.raises(TimeoutError, match="недоступен"):
        wait_tcp("127.0.0.1", 1, timeout=0)


def test_warning_does_not_fail_init() -> None:
    def warn() -> str:
        raise StepWarning("модель ещё не загружена")

    assert run_steps([Step("llm", warn, required=False)]) == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("redpanda:9092", ("redpanda", 9092)),
        ("redpanda", ("redpanda", 9092)),
        ("a:9092,b:9093", ("a", 9092)),
        ("PLAINTEXT://broker:19092", ("broker", 19092)),
        (" localhost:55092 ", ("localhost", 55092)),
    ],
)
def test_parse_broker(value: str, expected: tuple[str, int]) -> None:
    assert parse_broker(value) == expected


@pytest.mark.parametrize("value", [":9092", "host:abc"])
def test_parse_broker_rejects_garbage(value: str) -> None:
    with pytest.raises(ValueError, match="адрес брокера"):
        parse_broker(value)
