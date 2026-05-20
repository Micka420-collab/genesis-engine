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
    assert "globeCanvas" in text
    assert "mode=iso" in text or "viewMode" in text
    assert "/api/journal/events" in text
    assert "btnReplayMode" in text
    assert "artifactFile" in text
    assert "btnSse" in text
    assert "meteorology_state" in text or "hdrTemp" in text
    assert "agentDetail" in text
    assert "lite2d" in text
    assert "data-view-mode=\"lite2d\"" in text
    assert "/api/agents?lite=1" in text
    assert "zoomPresets" in text
    assert "liteTerrain" in text
    assert "/api/lite_field" in text
    assert "/api/earth_laws" in text
    assert "lawLapse" in text
    assert "wind_field" in text or "/api/circulation_state" in text
    assert "decodePackedAgents" in text
    assert "earth_console_webgpu.js" in text
    assert "agentGpuLayer" in text
    assert "EarthConsoleWebGPU" in text or "initAgentWebGPU" in text
    assert "earth_console_observer.js" in text
    assert "EarthConsoleObserver" in text
    assert "data-view-mode=\"sky\"" in text
    assert "/api/observer_feed" in text
    assert "observerLayer" in text
    assert "earth_console_speech.js" in text
    assert "earth_console_phoneme_audio.js" in text
    assert "speechFocus" in text
    assert "selVoiceMode" in text
    assert "btnListen" in text
    assert "KeyE" in text or "toggleListen" in text
    assert "/api/sun_state" in text or "loadSunState" in text


def test_run_earth_console_script_exists():
    script = RUNTIME / "scripts" / "run_earth_console.py"
    assert script.is_file()
    src = script.read_text(encoding="utf-8")
    assert "bootstrap_genesis_sim" in src
    assert "wire_emergence_v2" in src
    assert "earth_console" in src.lower() or "Earth Console" in src
