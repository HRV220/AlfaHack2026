import os

import pytest
from cabinet_common import entrypoint


def test_healthcheck_non_api_mode_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_MODE", "relay")
    assert entrypoint.main(["--healthcheck"]) == 0


def test_healthcheck_api_mode_fails_when_service_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_MODE", "api")
    monkeypatch.setenv("PORT", "1")
    assert entrypoint.main(["--healthcheck"]) == 1


def test_api_mode_execs_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv("SERVICE_MODE", "api")
    monkeypatch.setenv("APP_MODULE", "core_api.main:app")
    monkeypatch.setattr(os, "execvp", lambda _f, argv: calls.append(argv))
    entrypoint.main([])
    assert calls == [["uvicorn", "core_api.main:app", "--host", "0.0.0.0", "--port", "8000"]]


@pytest.mark.parametrize("mode", ["consumer", "relay"])
def test_worker_modes_run_idle_stub(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    seen: list[str] = []
    monkeypatch.setenv("SERVICE_MODE", mode)
    monkeypatch.setattr(entrypoint, "run_idle", lambda m: seen.append(m.value))
    assert entrypoint.main([]) == 0
    assert seen == [mode]
