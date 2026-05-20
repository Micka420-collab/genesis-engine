"""P74 — Köppen–Geiger harness smoke (Python mirror of Rust thresholds)."""
from __future__ import annotations

import io
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.koeppen_grid import REFERENCE_CLIMATES, classify_koeppen as classify


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P74 — Köppen harness smoke (Python)")
    print("=" * 78)
    failures = 0
    ok_count = 0
    for name, ta, tc, p, expected in REFERENCE_CLIMATES:
        got = classify(ta, tc, p)
        ok = got == expected
        if ok:
            ok_count += 1
        else:
            failures += 1
        print(_row(name, ok, f"expected={expected} got={got}"))
    rate = ok_count / max(len(REFERENCE_CLIMATES), 1)
    ok = rate >= 0.5
    print(_row(f"harness pass rate >= 50%", ok, f"{rate*100:.0f}%"))
    if not ok:
        failures += 1
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
