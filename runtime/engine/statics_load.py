"""Load spreading and stability scoring (Gustave / StableLego inspired).

Complements :mod:`engine.statics` column-based compressive checks with
multi-support load distribution: when a block rests on several blocks
below, vertical load is split equally among lower neighbours (face-
adjacent at z-1). This catches realistic arch/vault behaviour that
single-column models over-penalize.

References:
- Gustave (vsaulue/Gustave): static equilibrium on voxel grids.
- StableLego (arXiv:2402.10711): stability via force balance on blocks.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from engine.statics import (
    G_EARTH,
    Structure,
    check_compressive_stress,
    is_structurally_stable,
    voxel_area_m2,
)


def _neighbours_below(position: Tuple[int, int, int],
                      positions: set) -> List[Tuple[int, int, int]]:
    x, y, z = position
    if z <= 0:
        return []
    below_z = z - 1
    out = []
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        p = (x + dx, y + dy, below_z)
        if p in positions:
            out.append(p)
    return out


def _neighbours_above(position: Tuple[int, int, int],
                      positions: set) -> List[Tuple[int, int, int]]:
    x, y, z = position
    out = []
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        p = (x + dx, y + dy, z + 1)
        if p in positions:
            out.append(p)
    return out


def distribute_vertical_loads(
    structure: Structure,
    *,
    g: float = G_EARTH,
) -> Dict[Tuple[int, int, int], float]:
    """Downward reaction force (N) on each block after equal load splitting.

    Each block's total weight (self + everything it carries) is split
    equally among face-adjacent blocks directly below (Gustave-style).
    """
    if not structure.blocks:
        return {}

    positions = structure.position_set()
    self_w = {b.position: b.mass_kg * g for b in structure.blocks}
    carried = dict(self_w)

    for b in sorted(structure.blocks, key=lambda x: -x.position[2]):
        p = b.position
        below = _neighbours_below(p, positions)
        if not below:
            continue
        share = carried[p] / len(below)
        for q in below:
            carried[q] += share

    return carried


def check_load_spreading(
    structure: Structure,
    *,
    g: float = G_EARTH,
    safety_factor: float = 2.0,
) -> Tuple[bool, Dict[Tuple[int, int, int], Dict[str, float]]]:
    """Compressive check using distributed loads (multi-support)."""
    loads = distribute_vertical_loads(structure, g=g)
    area = voxel_area_m2(structure.voxel_size_m)
    report: Dict[Tuple[int, int, int], Dict[str, float]] = {}
    ok_all = True
    idx = structure.index_by_position()
    for pos, force_n in loads.items():
        b = structure.blocks[idx[pos]]
        stress_mpa = (force_n / area) / 1.0e6
        limit = b.compressive_strength_MPa / safety_factor
        ok = stress_mpa <= limit
        report[pos] = {
            "stress_MPa": round(stress_mpa, 6),
            "limit_MPa": round(limit, 6),
            "load_N": round(force_n, 4),
            "ok": bool(ok),
        }
        if not ok:
            ok_all = False
    return ok_all, report


def compute_stability_score(
    structure: Structure,
    *,
    g: float = G_EARTH,
    safety_factor: float = 2.0,
) -> float:
    """Continuous stability margin in [0, 1] (1 = ample reserve)."""
    ok_spread, spread = check_load_spreading(
        structure, g=g, safety_factor=safety_factor)
    if not spread:
        return 1.0 if ok_spread else 0.0
    margins = []
    for r in spread.values():
        lim = r["limit_MPa"]
        if lim <= 0:
            margins.append(0.0)
            continue
        margins.append(max(0.0, min(1.0, 1.0 - r["stress_MPa"] / lim)))
    base = float(np.mean(margins))
    if not ok_spread:
        base *= 0.5
    ok_col, col = check_compressive_stress(structure, g=g, safety_factor=safety_factor)
    if col:
        col_margins = [
            max(0.0, min(1.0, 1.0 - v["stress_MPa"] / max(v["limit_MPa"], 1e-9)))
            for v in col.values()
        ]
        base = 0.6 * base + 0.4 * float(np.mean(col_margins))
    if not ok_col:
        base *= 0.7
    return round(max(0.0, min(1.0, base)), 4)


def is_structurally_stable_spread(
    structure: Structure,
    *,
    min_score: float = 0.15,
    **kwargs,
) -> Tuple[bool, str]:
    """Combine classic statics + load-spreading score floor."""
    ok, reason = is_structurally_stable(structure, **kwargs)
    if not ok:
        return False, reason
    score = compute_stability_score(structure)
    if score < min_score:
        return False, f"load_spread_margin_low:score={score:.3f}"
    ok_spread, spread = check_load_spreading(structure)
    if not ok_spread:
        worst = max(
            spread.items(),
            key=lambda kv: kv[1]["stress_MPa"] - kv[1]["limit_MPa"],
        )
        return (
            False,
            f"load_spread_stress at {worst[0]}: "
            f"{worst[1]['stress_MPa']:.2f} > {worst[1]['limit_MPa']:.2f} MPa",
        )
    return True, "stable"


__all__ = [
    "distribute_vertical_loads",
    "check_load_spreading",
    "compute_stability_score",
    "is_structurally_stable_spread",
]
