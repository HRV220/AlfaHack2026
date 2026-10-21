"""Статические проверки Compose-профиля core (E02-02): теги, переменные режима по умолчанию."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy" / "compose" / "compose.yaml"
ENV_EXAMPLE = ROOT / ".env.example"


def compose_text() -> str:
    return COMPOSE.read_text(encoding="utf-8")


def test_no_latest_tags() -> None:
    images = re.findall(r"^\s*image:\s*(\S+)", compose_text(), flags=re.MULTILINE)
    assert images
    assert [i for i in images if i.endswith(":latest") or ":" not in i] == []


def test_env_example_describes_default_mode() -> None:
    names = {
        line.split("=", 1)[0]
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    assert {"LLM_PROVIDER", "LLM_MODEL", "ASSISTANT_ENABLED", "CHECKING_DELAY_SEC"} <= names


def test_env_example_has_no_secrets() -> None:
    """Значения переменных с паролем, ключом, токеном или секретом — только учебные (с «dev»)."""
    secret_name = re.compile(r"(PASSWORD|SECRET|KEY|TOKEN)", re.IGNORECASE)
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if secret_name.search(name) and value.strip():
            assert (
                "dev" in value.lower()
            ), f"{name}: в .env.example допустимы только учебные значения"


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker не установлен")
def test_compose_config_is_valid() -> None:
    cmd = ["docker", "compose", "--project-directory", str(ROOT), "-f", str(COMPOSE)]
    result = subprocess.run(  # noqa: S603
        [*cmd, "--profile", "core", "config", "-q"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


NGINX = ROOT / "deploy" / "compose" / "nginx" / "nginx.conf"


def test_edge_config_streams_sse_and_limits_requests() -> None:
    text = NGINX.read_text(encoding="utf-8")
    api = text[text.index("location /api/") : text.index("location / {")]
    assert "proxy_buffering off" in api
    assert re.search(r"proxy_read_timeout\s+\d+s", api)
    assert "limit_req zone=api" in api
    web = text[text.index("location / {") :]
    assert "limit_req zone=web" in web
    assert text.count("X-Forwarded-For $remote_addr") == 2  # не доверяем заголовку клиента
    assert "limit_req_zone" in text


def test_edge_config_tls_and_security_headers() -> None:
    text = NGINX.read_text(encoding="utf-8")
    assert "listen 443 ssl" in text
    for header in ("Strict-Transport-Security", "X-Content-Type-Options", "X-Frame-Options"):
        assert header in text
    assert "server_tokens off" in text


def compose_config() -> dict[str, dict[str, object]]:
    cmd = ["docker", "compose", "--project-directory", str(ROOT), "-f", str(COMPOSE)]
    out = subprocess.run(  # noqa: S603
        [*cmd, "--profile", "core", "config", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    services: dict[str, dict[str, object]] = json.loads(out.stdout)["services"]
    return services


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker не установлен")
def test_every_resident_service_has_healthcheck() -> None:
    services = compose_config()
    resident = {n: s for n, s in services.items() if s.get("restart") != "no"}
    assert resident
    missing = [
        n
        for n, s in resident.items()
        if not s.get("healthcheck") or s["healthcheck"].get("disable")  # type: ignore[attr-defined]
    ]
    assert missing == []


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker не установлен")
def test_dependencies_wait_for_healthy_or_completed() -> None:
    allowed = {"service_healthy", "service_completed_successfully"}
    for name, service in compose_config().items():
        for dep, spec in (service.get("depends_on") or {}).items():  # type: ignore[attr-defined]
            assert spec["condition"] in allowed, f"{name} -> {dep}: {spec['condition']}"
