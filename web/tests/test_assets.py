"""Вендоренная статика и отсутствие внешних URL в шаблонах (NFR-19, E02-11.2)."""

import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "cabinet_web"
ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = re.compile(r"(https?:)?//[a-z0-9.-]+\.[a-z]{2,}", re.IGNORECASE)


def test_vendored_libraries_present() -> None:
    vendor = PACKAGE / "static" / "vendor"
    for name in (
        "htmx.min.js",
        "htmx-ext-sse.js",
        "alpine.min.js",
        "chart.umd.js",
        "LICENSE-htmx.txt",
        "LICENSE-alpine.txt",
        "LICENSE-chartjs.txt",
    ):
        assert (vendor / name).stat().st_size > 500, name


def test_templates_and_own_assets_have_no_external_urls() -> None:
    files = [
        *(PACKAGE / "templates").rglob("*.html"),
        *(PACKAGE / "static" / "css").glob("*.css"),
        *(PACKAGE / "static" / "js").glob("*.js"),
    ]
    assert files
    offenders = {
        f.name: EXTERNAL.findall(f.read_text(encoding="utf-8"))
        for f in files
        if EXTERNAL.search(f.read_text(encoding="utf-8"))
    }
    assert offenders == {}


def test_base_layout_is_responsive() -> None:
    base = (PACKAGE / "templates" / "base.html").read_text(encoding="utf-8")
    assert 'name="viewport" content="width=device-width, initial-scale=1"' in base
    css = (PACKAGE / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert "min-width: 768px" in css and "min-width: 1280px" in css


def test_vendored_libraries_listed_in_third_party_notices() -> None:
    notices = (ROOT / "THIRD_PARTY_NOTICES").read_text(encoding="utf-8")
    for name in ("htmx", "htmx-ext-sse", "Alpine.js", "Chart.js"):
        assert name in notices
