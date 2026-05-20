"""P73b — Python ↔ Rust world-engine smoke (pybindings optional)."""
from __future__ import annotations

import io
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(ROOT, ".."))
sys.path.insert(0, ROOT)
IMPROVEMENTS = os.path.join(REPO, "docs", "IMPROVEMENTS-SESSION.md")


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'SKIP'}] {label:62s} {detail}"


def _append_improvements(note: str) -> None:
    os.makedirs(os.path.dirname(IMPROVEMENTS), exist_ok=True)
    with open(IMPROVEMENTS, "a", encoding="utf-8") as f:
        f.write(note + "\n")


def main() -> int:
    print("=" * 78)
    print("P73b — Rust pybindings smoke")
    print("=" * 78)

    from engine.rust_bridge import create_py_world, try_import_genesis_world

    gw_mod, native = try_import_genesis_world()
    if not native:
        msg = (
            f"\n## Pont Rust — mock actif\n\n"
            f"`genesis_world` non importable ; smokes utilisent "
            f"`engine.rust_bridge.MockPyWorld`. Compiler pour le natif :\n\n"
            f"```bash\n"
            f"cd native/world-engine\n"
            f"maturin develop -m crates/pybindings/Cargo.toml\n"
            f"```\n"
        )
        _append_improvements(msg)
        print(_row("import genesis_world", False, "using MockPyWorld"))
    else:
        print(_row("import genesis_world", True, "native module"))

    failures = 0
    w = create_py_world(seed=42)
    obs = w.observe_chunk(0, 0)
    ok = isinstance(obs, dict) and "elevation" in obs
    print(_row("PyWorld.observe_chunk", ok, f"keys={list(obs.keys())[:5]}"))
    if not ok:
        failures += 1

    if hasattr(w, "biome_at"):
        b = w.biome_at(0, 0, 0)
        print(_row("biome_at", True, f"biome={b}"))
    else:
        print(_row("biome_at (optional)", True, "not exposed"))

    print("=" * 78)
    if failures:
        print(f"P73b FAIL — {failures}")
        return 1
    label = "native" if native else "mock"
    print(f"P73b PASS — Rust bridge OK ({label})")
    if native:
        _append_improvements(
            "\n## Pont Rust — OK\n\n`genesis_world` importable, observe_chunk OK.\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
