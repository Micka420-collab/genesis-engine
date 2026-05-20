"""Earth Console static assets and launcher smoke."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "runtime"


def test_earth_console_html_exists():
    html = RUNTIME / "engine" / "earth_console.html"
    assert html.is_file()
    text = html.read_text(encoding="utf-8")
    assert "earth_console" in text or "Terre" in text
    assert "/api/render" in text
    assert "/api/macro" in text


def test_run_earth_console_script_exists():
    script = RUNTIME / "scripts" / "run_earth_console.py"
    assert script.is_file()
    src = script.read_text(encoding="utf-8")
    assert "bootstrap_genesis_sim" in src
    assert "earth_console" in src.lower() or "Earth Console" in src
