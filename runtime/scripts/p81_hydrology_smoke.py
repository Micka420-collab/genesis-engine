"""P81 — cross-chunk hydrology (Saint-Venant 1D + LBM D2Q9) smoke."""
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

import numpy as np  # noqa: E402

from engine.world import TerrainParams, generate_chunk  # noqa: E402
from engine.chunk_hydrology import (  # noqa: E402
    cross_chunk_flow_stub,
    cross_chunk_saint_venant_1d,
    cross_chunk_lbm_d2q9_step,
)

_SEED = 0xC081_0001
_PARAMS = TerrainParams()


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _pair_chunks():
    a = generate_chunk(_SEED, (0, 0, 0), _PARAMS)
    b = generate_chunk(_SEED, (1, 0, 0), _PARAMS)
    a.water[:, -1] = 2.0
    b.water[:, 0] = 0.2
    return a, b


def main() -> int:
    print("=" * 78)
    print("P81 — cross-chunk hydrology smoke")
    print("=" * 78)
    failures = 0
    a, b = _pair_chunks()
    q1 = cross_chunk_flow_stub(a, b, "east")
    a2, b2 = _pair_chunks()
    q2 = cross_chunk_saint_venant_1d(a2, b2, "east")
    ok = q1 >= 0.0 and q2 >= 0.0
    print(_row("Manning stub + Saint-Venant", ok, f"q_stub={q1:.4f} q_sv={q2:.4f}"))
    if not ok:
        failures += 1
    a3, b3 = _pair_chunks()
    d1 = cross_chunk_lbm_d2q9_step(a3, b3, "east", prf_seed=42)
    a4, b4 = _pair_chunks()
    d2 = cross_chunk_lbm_d2q9_step(a4, b4, "east", prf_seed=42)
    ok = d1 == d2 and d1 > 0.0
    print(_row("LBM D2Q9 deterministic", ok, f"flux={d1:.4f}"))
    if not ok:
        failures += 1
    ok = not np.array_equal(a3.water, _pair_chunks()[0].water)
    print(_row("LBM mutates boundary water", ok))
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
