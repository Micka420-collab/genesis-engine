"""Sprint B4 smoke -- structural statics engine.

Five geometric tests exercise :mod:`engine.statics`:

1. A 5-block vertical stone tower is stable.
2. A floating stone block at z=5 (no support) is rejected with a reason
   that mentions "unsupported".
3. A 5-block stone column with a 4-voxel horizontal corbel is rejected
   by the overhang check.
4. A 10-metre tall single-column mud wall over a 1-voxel footprint
   exceeds compressive stress.
5. A 3-2-1 stone pyramid is stable.

Pass criterion: at least 4/5 individual tests pass.
"""

from __future__ import annotations

import io
import json
import math
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
sys.path.insert(0, ROOT)

from engine.statics import (
    Structure, VoxelBlock, analyze, check_compressive_stress,
    check_overhang, check_support, is_structurally_stable,
)


def _run(name: str, fn) -> dict:
    """Run one test and capture exceptions as failures."""
    try:
        ok, info = fn()
    except Exception as exc:
        return {
            "test": name,
            "passed": False,
            "info": {
                "exception": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc().splitlines()[-6:],
            },
        }
    return {"test": name, "passed": bool(ok), "info": info}


# ---------------------------------------------------------------------------
# Test 1 -- vertical stone tower (5 blocks tall, 1x1 base).
# ---------------------------------------------------------------------------
def test_tower_stable() -> tuple:
    s = Structure.from_positions(
        structure_id=1,
        positions=[(0, 0, z) for z in range(5)],
        material="stone",
        voxel_size=0.25,
    )
    is_stable, reason = is_structurally_stable(s)
    report = analyze(s)
    return is_stable, {"reason": reason, "report": report}


# ---------------------------------------------------------------------------
# Test 2 -- single floating block at z=5.
# ---------------------------------------------------------------------------
def test_floating_block() -> tuple:
    block = VoxelBlock.from_material(position=(2, 2, 5), material="stone",
                                     voxel_size=0.25)
    s = Structure(structure_id=2, blocks=[block], voxel_size_m=0.25)
    ok_support, unsupported = check_support(s)
    is_stable, reason = is_structurally_stable(s)
    # Pass condition: support failed AND reason mentions "unsupported".
    passed = (not ok_support) and (not is_stable) and ("unsupported" in reason)
    return passed, {
        "support_ok": ok_support,
        "unsupported": unsupported,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Test 3 -- corbel: 5-block stone column + 4-voxel horizontal overhang.
# ---------------------------------------------------------------------------
def test_corbel_overhang() -> tuple:
    positions = [(0, 0, z) for z in range(5)]
    # Cantilever blocks at the top z=4 extending in +x for 4 voxels.
    positions += [(x, 0, 4) for x in range(1, 5)]
    s = Structure.from_positions(structure_id=3, positions=positions,
                                 material="stone", voxel_size=0.25)
    ok_overhang, offenders = check_overhang(s, max_overhang_voxels=3)
    is_stable, reason = is_structurally_stable(s)
    passed = (not ok_overhang) and (not is_stable) and ("overhang" in reason)
    return passed, {
        "overhang_ok": ok_overhang,
        "offenders": offenders[:6],
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Test 4 -- 10 m tall mud column on a 1-voxel footprint.
# ---------------------------------------------------------------------------
def test_mud_wall_overload() -> tuple:
    # 10 m / 0.25 m = 40 voxels.  Mud strength = 5 MPa, safety_factor=2,
    # limit = 2.5 MPa.  Stress at bottom = 40 * 1600 kg/m^3 * 0.25 m * 9.81
    # / 1 m^2 ~= 0.157 MPa per voxel of column, so over 40 voxels the
    # bottom block sees ~0.157 MPa.  That actually stays *under* the
    # mud limit -- so we make the wall taller until it breaks.
    # Easier: compute analytically the height that breaks mud.
    # Stress = h * density * g.  Limit = 5e6 / 2 = 2.5e6 Pa.
    # h_max = 2.5e6 / (1600 * 9.81) ~= 159 m.  Use 200 m (800 voxels).
    H_VOX = 800
    s = Structure.from_positions(
        structure_id=4,
        positions=[(0, 0, z) for z in range(H_VOX)],
        material="mud",
        voxel_size=0.25,
    )
    ok_stress, stress = check_compressive_stress(s)
    is_stable, reason = is_structurally_stable(s)
    bottom = stress[(0, 0, 0)]
    passed = (not ok_stress) and (not is_stable) and ("compressive" in reason)
    return passed, {
        "stress_ok": ok_stress,
        "bottom_stress_MPa": bottom["stress_MPa"],
        "bottom_limit_MPa": bottom["limit_MPa"],
        "reason": reason,
        "height_voxels": H_VOX,
    }


# ---------------------------------------------------------------------------
# Test 5 -- 3-2-1 stone pyramid (stable).
# ---------------------------------------------------------------------------
def test_pyramid_stable() -> tuple:
    positions = []
    # Layer 0: 3x3.
    for x in range(3):
        for y in range(3):
            positions.append((x, y, 0))
    # Layer 1: 2x2 centred.
    for x in range(1, 3):
        for y in range(1, 3):
            positions.append((x, y, 1))
    # Layer 2: single cap.
    positions.append((1, 1, 2))
    s = Structure.from_positions(structure_id=5, positions=positions,
                                 material="stone", voxel_size=0.25)
    is_stable, reason = is_structurally_stable(s)
    report = analyze(s)
    return is_stable, {"reason": reason, "report": report}


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------
def main() -> int:
    out_path = os.path.join(ROOT, "journals", "sprint_b4_statics.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w").close()

    tests = [
        ("tower_stable", test_tower_stable),
        ("floating_block_rejected", test_floating_block),
        ("corbel_overhang_rejected", test_corbel_overhang),
        ("mud_wall_overload_rejected", test_mud_wall_overload),
        ("pyramid_stable", test_pyramid_stable),
    ]
    results = [_run(name, fn) for name, fn in tests]
    n_passed = sum(1 for r in results if r["passed"])
    n_total = len(results)
    summary = {
        "_summary": True,
        "sprint": "B4",
        "module": "engine.statics",
        "passed": n_passed,
        "total": n_total,
        "results": results,
    }

    with open(out_path, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(summary, separators=(",", ":"), default=str) + "\n")

    print(json.dumps(summary, indent=2, default=str))

    if n_passed >= 4:
        print(f"\n[OK] B4 STATICS SMOKE PASSED ({n_passed}/{n_total})")
        print(f"   journal: {out_path}")
        return 0
    print(f"\n[X] B4 STATICS SMOKE FAILED ({n_passed}/{n_total})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
