#!/usr/bin/env python
"""Regenerate compliance renders (stub orchestrator).

Does not delete existing PNGs. Invokes known smokes that write renders when
available; documents migration in ``docs/renders/README.md``.

Usage::

    PYTHONPATH=runtime python runtime/scripts/regenerate_compliance_renders.py
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(ROOT, ".."))

SMOKES = (
    "p72_world_atmosphere_smoke.py",
    "p75_koeppen_grid_smoke.py",
    "p80_koeppen_genesis_smoke.py",
)


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT
    print("[regenerate_compliance_renders] orchestrator — no PNG deletion")
    for name in SMOKES:
        path = os.path.join(HERE, name)
        if not os.path.isfile(path):
            print(f"  SKIP missing {name}")
            continue
        print(f"  RUN {name}")
        r = subprocess.run([sys.executable, path], cwd=ROOT, env=env)
        if r.returncode != 0:
            print(f"  WARN {name} exit {r.returncode}")
    print("[regenerate_compliance_renders] done — copy PNGs to docs/compliance/renders/ manually or via future render hooks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
