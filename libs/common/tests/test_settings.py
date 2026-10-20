import pytest
from cabinet_common.settings import BaseServiceSettings, ServiceMode


def test_defaults() -> None:
    assert BaseServiceSettings().service_mode is ServiceMode.API


def test_mode_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_MODE", "relay")
    assert BaseServiceSettings().service_mode is ServiceMode.RELAY


def test_invalid_mode_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_MODE", "bogus")
    with pytest.raises(ValueError):
        BaseServiceSettings()
