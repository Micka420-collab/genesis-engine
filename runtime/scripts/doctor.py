"""Local environment doctor for Genesis Engine.

This script is intentionally lightweight: it does not import the whole
simulation unless required dependencies are present. It helps contributors
distinguish "project is broken" from "local toolchain is missing".
"""
from __future__ import annotations

import importlib.util
import platform
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _status(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def _module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    # pyproject.toml declares `requires-python = ">=3.11,<3.14"` so we align
    # the doctor with the published constraint. The CI matrix tests 3.11–3.13.
    checks.append(("python>=3.11", sys.version_info >= (3, 11), platform.python_version()))
    checks.append(("numpy", _module("numpy"), "required for runtime/engine"))
    checks.append(("pytest", _module("pytest"), "required for make test-python"))
    checks.append(("rasterio", _module("rasterio"), "optional: Earth-anchored mode"))
    checks.append(("pyproj", _module("pyproj"), "optional: Earth-anchored mode"))
    checks.append(("cargo", shutil.which("cargo") is not None, "required for scaffolding/"))

    print("Genesis Engine doctor")
    print(f"root: {ROOT.parent}")
    print()
    for name, ok, detail in checks:
        print(f"{_status(ok):7} {name:14} {detail}")

    required_ok = all(ok for name, ok, _ in checks if name in {"python>=3.11", "numpy"})
    if not required_ok:
        print()
        print("Install the runtime with:")
        print("  python -m pip install -e .")
        print("or, without editable install:")
        print("  python -m pip install -r requirements.txt")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

