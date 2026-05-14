"""Genesis Engine -- structural statics engine (Sprint B4, Pillar 3).

Today ``engine/construction.py`` exposes ``RECIPES`` (HEARTH, HUT, ...) as
fixed templates: an agent can "construct" a building without any check on
mass, support, or balance.  Tomorrow, the world will be voxel-based and
emergent structures must pass a *structural* check before being committed
to the world: do they actually stand under gravity?

This module provides a small, dependency-light statics solver.  It is not
a finite-element solver -- it relies on three engineering rules of thumb
that catch the vast majority of unstable voxel structures:

1. **Support** -- every voxel must rest on the ground (z == 0) or on at
   least one neighbouring voxel that itself rests on the ground.  This is
   resolved with a flood fill from the ground up.

2. **Compressive stress** -- for each "column" of stacked voxels, the
   bottom blocks carry the cumulated weight of everything sitting above.
   The local compressive stress (in MPa) must remain below the material's
   compressive strength divided by a safety factor.

3. **Overhang / cantilever** -- horizontal runs of unsupported blocks
   (corbels) cannot exceed a material-dependent limit.  Stone walls
   tolerate ~3 voxels of overhang before the unsupported moment exceeds
   the tensile strength at the root.

A global tip-over check is also exposed (centroid of mass above support
base), so a tall tower with too narrow a footprint fails before it would
fall over.

No external solver dependencies: only ``math`` and ``numpy``.  Determinism
is purely geometric (no RNG).  ``engine.physics`` is imported optionally
so the module is usable in isolation (e.g. unit tests, smoke scripts).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import math

import numpy as np


# ---------------------------------------------------------------------------
# Physics constants (with optional fallback to engine.physics).
# ---------------------------------------------------------------------------
try:  # pragma: no cover -- exercised when physics module is present.
    from engine.physics import G_EARTH as _G_EARTH_FROM_PHYS  # type: ignore
    G_EARTH: float = float(_G_EARTH_FROM_PHYS)
except Exception:  # pragma: no cover -- fallback when physics unavailable.
    G_EARTH = 9.81


# ---------------------------------------------------------------------------
# Material strength table (engineering rules of thumb in MPa, kg/m^3).
# ---------------------------------------------------------------------------
# Values are pragmatic, not laboratory-precise: they reflect the order of
# magnitude one would teach in a first-year statics class.  The compressive
# strengths for ductile metals are deliberately conservative because real
# voxel masonry is governed by buckling, not the bulk yield stress.
STRENGTH_TABLE: Dict[str, Dict[str, float]] = {
    "wood":     {"compressive": 40.0,  "tensile": 80.0,  "density": 600.0},
    "stone":    {"compressive": 100.0, "tensile": 5.0,   "density": 2400.0},
    "brick":    {"compressive": 30.0,  "tensile": 3.0,   "density": 1800.0},
    "mud":      {"compressive": 5.0,   "tensile": 0.5,   "density": 1600.0},
    "concrete": {"compressive": 30.0,  "tensile": 4.0,   "density": 2400.0},
    "iron":     {"compressive": 200.0, "tensile": 200.0, "density": 7800.0},
    "bronze":   {"compressive": 250.0, "tensile": 250.0, "density": 8700.0},
}


def material_properties(material: str) -> Dict[str, float]:
    """Look up a material in :data:`STRENGTH_TABLE`.

    Unknown materials fall back to a low-grade ``"mud"`` profile, with the
    name preserved so callers can detect the fallback.  This keeps the
    solver useful for *synthesized* materials invented by AI agents (they
    will simply look weak until the Inventor adds a proper entry).
    """
    if material in STRENGTH_TABLE:
        return STRENGTH_TABLE[material]
    # Synthesized / unknown material -> conservative fallback.
    return {"compressive": 5.0, "tensile": 0.5, "density": 1600.0,
            "_fallback": 1.0}


# ---------------------------------------------------------------------------
# Geometry helpers.
# ---------------------------------------------------------------------------
def voxel_volume_m3(voxel_size: float) -> float:
    """Volume of a single voxel cube (m^3)."""
    return float(voxel_size) ** 3


def voxel_area_m2(voxel_size: float) -> float:
    """Bearing area of a single voxel face (m^2)."""
    return float(voxel_size) ** 2


def block_mass(material: str, voxel_size: float) -> float:
    """Mass of a voxel block (kg) = density * voxel volume."""
    props = material_properties(material)
    return float(props["density"]) * voxel_volume_m3(voxel_size)


# ---------------------------------------------------------------------------
# Data classes.
# ---------------------------------------------------------------------------
@dataclass
class VoxelBlock:
    """A single cubic voxel placed in a structure."""

    position: Tuple[int, int, int]
    material: str
    mass_kg: float
    compressive_strength_MPa: float
    tensile_strength_MPa: float

    @classmethod
    def from_material(cls, position: Tuple[int, int, int], material: str,
                      voxel_size: float = 0.25) -> "VoxelBlock":
        """Build a block from a material name + voxel size.

        Useful in tests / smoke scripts where the caller does not want to
        hand-compute mass and strengths.
        """
        props = material_properties(material)
        return cls(
            position=(int(position[0]), int(position[1]), int(position[2])),
            material=material,
            mass_kg=block_mass(material, voxel_size),
            compressive_strength_MPa=float(props["compressive"]),
            tensile_strength_MPa=float(props["tensile"]),
        )


@dataclass
class Structure:
    """A collection of voxel blocks forming one connected construction."""

    structure_id: int
    blocks: List[VoxelBlock] = field(default_factory=list)
    voxel_size_m: float = 0.25

    # ----- convenience constructors -------------------------------------
    @classmethod
    def from_positions(cls, structure_id: int,
                       positions: Iterable[Tuple[int, int, int]],
                       material: str = "stone",
                       voxel_size: float = 0.25) -> "Structure":
        """Build a structure where every block has the same material."""
        blocks = [VoxelBlock.from_material(tuple(p), material, voxel_size)
                  for p in positions]
        return cls(structure_id=structure_id, blocks=blocks,
                   voxel_size_m=voxel_size)

    # ----- lookups ------------------------------------------------------
    def position_set(self) -> set:
        return {b.position for b in self.blocks}

    def index_by_position(self) -> Dict[Tuple[int, int, int], int]:
        return {b.position: i for i, b in enumerate(self.blocks)}


# ---------------------------------------------------------------------------
# Mass / centroid helpers.
# ---------------------------------------------------------------------------
def total_mass(structure: Structure) -> float:
    """Total mass of the structure in kg."""
    return float(sum(b.mass_kg for b in structure.blocks))


def centroid_of_mass(structure: Structure) -> Tuple[float, float, float]:
    """Centre of mass in **voxel** coordinates.

    Returns ``(0, 0, 0)`` for an empty structure (degenerate but harmless).
    """
    if not structure.blocks:
        return (0.0, 0.0, 0.0)
    m_total = total_mass(structure)
    if m_total <= 0.0:
        return (0.0, 0.0, 0.0)
    cx = sum(b.mass_kg * b.position[0] for b in structure.blocks) / m_total
    cy = sum(b.mass_kg * b.position[1] for b in structure.blocks) / m_total
    cz = sum(b.mass_kg * b.position[2] for b in structure.blocks) / m_total
    return (float(cx), float(cy), float(cz))


def _support_base_xy(structure: Structure) -> List[Tuple[int, int]]:
    """Set of (x, y) cells that touch the ground (z == 0)."""
    return sorted({(b.position[0], b.position[1])
                   for b in structure.blocks if b.position[2] == 0})


def centroid_over_support_base(structure: Structure,
                               tolerance: float = 0.5) -> bool:
    """Tip-over check: horizontal centroid lies above a ground voxel.

    The base is the convex projection of all blocks resting on z == 0.
    We approximate the base by its bounding box (inclusive), which is a
    conservative over-estimate -- but tightening the projection further
    requires a 2D convex hull and offers little benefit for voxel-aligned
    structures.

    ``tolerance`` (in voxels) lets the centroid sit slightly outside the
    integer footprint, since each ground voxel actually spans 1.0 voxel
    of horizontal extent around its centre.
    """
    base = _support_base_xy(structure)
    if not base:
        return False
    cx, cy, _ = centroid_of_mass(structure)
    xs = [p[0] for p in base]
    ys = [p[1] for p in base]
    x_min, x_max = min(xs) - tolerance, max(xs) + tolerance
    y_min, y_max = min(ys) - tolerance, max(ys) + tolerance
    return (x_min <= cx <= x_max) and (y_min <= cy <= y_max)


# ---------------------------------------------------------------------------
# Rule 1 -- support check (flood fill from the ground).
# ---------------------------------------------------------------------------
def check_support(structure: Structure
                  ) -> Tuple[bool, List[Tuple[int, int, int]]]:
    """Verify that every block is connected to the ground via supports.

    A block at ``z == 0`` is anchored to the ground.  Any other block is
    *supported* if it has a face-adjacent neighbour (below, above, or to
    any of the four sides) that is itself supported.  We resolve this
    transitively with a BFS rooted at the ground voxels.

    The "support" relation is purposefully forgiving: a horizontal block
    glued to a wall is treated as supported.  Rule 3 (overhang) is what
    eventually rejects long cantilevers.

    Returns ``(is_supported, unsupported_positions)``.
    """
    positions = structure.position_set()
    if not positions:
        return (True, [])

    # Seed: every ground voxel.
    queue: List[Tuple[int, int, int]] = [p for p in positions if p[2] == 0]
    supported: set = set(queue)

    # 6-connected neighbours (face-adjacent).
    neigh = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0),
             (0, 0, 1), (0, 0, -1)]
    while queue:
        x, y, z = queue.pop()
        for dx, dy, dz in neigh:
            np_ = (x + dx, y + dy, z + dz)
            if np_ in positions and np_ not in supported:
                supported.add(np_)
                queue.append(np_)

    unsupported = sorted(positions - supported)
    return (len(unsupported) == 0, unsupported)


# ---------------------------------------------------------------------------
# Rule 2 -- compressive stress per column.
# ---------------------------------------------------------------------------
def check_compressive_stress(structure: Structure,
                             g: float = G_EARTH,
                             safety_factor: float = 2.0,
                             ) -> Tuple[bool, Dict[Tuple[int, int, int], Dict[str, float]]]:
    """Per-block compressive-stress check.

    For each vertical column of blocks ``(x, y, *)``, we sort by z and
    accumulate the cumulative mass *strictly above* each block.  The
    weight that a block carries equals (cumulative_mass + self_mass) * g.

    The local compressive stress is the weight divided by the bearing
    area of one voxel face.  It must remain below
    ``compressive_strength / safety_factor``.

    The returned dict maps every block position to a small report:
    ``stress_MPa``, ``limit_MPa``, ``ok``.
    """
    if g <= 0:
        raise ValueError("g must be positive")
    if safety_factor <= 0:
        raise ValueError("safety_factor must be positive")

    area = voxel_area_m2(structure.voxel_size_m)
    # Group blocks by (x, y) column.
    columns: Dict[Tuple[int, int], List[VoxelBlock]] = {}
    for b in structure.blocks:
        columns.setdefault((b.position[0], b.position[1]), []).append(b)

    report: Dict[Tuple[int, int, int], Dict[str, float]] = {}
    overall_ok = True

    for (x, y), col in columns.items():
        col.sort(key=lambda b: b.position[2])
        # cumulative mass of blocks strictly above index i.
        masses = [b.mass_kg for b in col]
        n = len(col)
        cum_above = [0.0] * n
        running = 0.0
        for i in range(n - 1, -1, -1):
            cum_above[i] = running
            running += masses[i]
        for i, b in enumerate(col):
            # Self weight + everything above pressing down on this block's
            # *bottom* face.
            weight_N = (masses[i] + cum_above[i]) * g
            stress_Pa = weight_N / area
            stress_MPa = stress_Pa / 1.0e6
            limit_MPa = b.compressive_strength_MPa / safety_factor
            ok = stress_MPa <= limit_MPa
            report[b.position] = {
                "stress_MPa": round(stress_MPa, 6),
                "limit_MPa": round(limit_MPa, 6),
                "ok": bool(ok),
            }
            if not ok:
                overall_ok = False
    return (overall_ok, report)


# ---------------------------------------------------------------------------
# Rule 3 -- overhang / cantilever.
# ---------------------------------------------------------------------------
def _material_overhang_limit(material: str,
                             default: int = 3) -> int:
    """Translate the tensile/compressive ratio into a voxel overhang limit.

    Stone -> ~3 voxels (low tensile strength).
    Wood / iron / bronze -> longer cantilevers thanks to high tensile.
    Mud / brick -> shorter cantilevers.
    """
    props = material_properties(material)
    tensile = float(props["tensile"])
    compressive = float(props["compressive"])
    if compressive <= 0:
        return 1
    # A pragmatic rule: limit = 2 + round(2 * tensile / compressive).
    # stone   tensile/comp = 0.05 -> 2 voxels
    # brick                 0.10 -> 2
    # wood                  2.00 -> 6
    # iron                  1.00 -> 4
    # bronze                1.00 -> 4
    # We also cap to the user-provided default for non-metals.
    ratio = tensile / compressive
    limit = 2 + int(round(2.0 * ratio))
    if material in ("stone", "brick", "mud", "concrete"):
        # Brittle masonry -> obey the global default cap.
        limit = min(limit + 1, default)
    return max(1, limit)


def check_overhang(structure: Structure,
                   max_overhang_voxels: int = 3,
                   ) -> Tuple[bool, List[Tuple[Tuple[int, int, int], int]]]:
    """Cantilever check.

    For every block, we look horizontally (in the +/- x and +/- y
    directions) and count how many *consecutive* blocks at the same
    altitude are themselves unsupported from below until we either reach
    a block that *is* supported from below, or fall off the structure.
    That length is the local overhang.

    The block tolerates an overhang up to
    ``min(max_overhang_voxels, material_limit)``.

    Returns ``(passes, offending_list)`` where each offender is a
    ``(position, observed_overhang)`` pair.
    """
    positions = structure.position_set()
    idx = structure.index_by_position()
    offenders: List[Tuple[Tuple[int, int, int], int]] = []

    # For each block, compute "is supported from below" once.
    has_support_below = {p: ((p[0], p[1], p[2] - 1) in positions) or p[2] == 0
                         for p in positions}

    # Identify rows of consecutive overhanging blocks along x and y.
    for axis, (dx, dy) in enumerate(((1, 0), (0, 1))):
        for p in positions:
            if has_support_below[p]:
                continue
            # Walk both directions along this axis and find the nearest
            # supported neighbour at the same z.
            length_pos = 0
            q = p
            while True:
                q = (q[0] + dx, q[1] + dy, q[2])
                if q not in positions:
                    break
                length_pos += 1
                if has_support_below[q]:
                    break
            length_neg = 0
            q = p
            while True:
                q = (q[0] - dx, q[1] - dy, q[2])
                if q not in positions:
                    break
                length_neg += 1
                if has_support_below[q]:
                    break
            # The block sits in a run of length_neg + 1 + length_pos
            # unsupported voxels.  "Overhang" relative to the nearest
            # supported anchor = max(length_pos, length_neg) before that
            # anchor.
            # Distance from nearest anchor along this axis:
            dist = min(length_pos if length_pos > 0 else 10**9,
                       length_neg if length_neg > 0 else 10**9)
            # If both directions stay unsupported until they fall off the
            # structure, this block is a free-floating cantilever tip;
            # treat its overhang as its run length.
            if dist >= 10**8:
                run = max(length_pos, length_neg) + 1
            else:
                run = dist
            b = structure.blocks[idx[p]]
            mat_limit = _material_overhang_limit(b.material,
                                                 default=max_overhang_voxels)
            limit = min(max_overhang_voxels, mat_limit)
            if run > limit:
                offenders.append((p, run))

    passes = len(offenders) == 0
    return (passes, offenders)


# ---------------------------------------------------------------------------
# Top-level validator.
# ---------------------------------------------------------------------------
def is_structurally_stable(structure: Structure, *,
                           g: float = G_EARTH,
                           safety_factor: float = 2.0,
                           max_overhang_voxels: int = 3,
                           ) -> Tuple[bool, str]:
    """Combine all three checks plus the tip-over heuristic.

    Returns ``(is_stable, reason)``.  ``reason`` is ``"stable"`` on
    success, and a short human-readable diagnostic otherwise.
    """
    if not structure.blocks:
        return (False, "empty: structure has no blocks")

    ok_support, unsupported = check_support(structure)
    if not ok_support:
        sample = unsupported[:3]
        return (False, f"unsupported blocks: {len(unsupported)} (e.g. {sample})")

    ok_stress, _stress = check_compressive_stress(
        structure, g=g, safety_factor=safety_factor)
    if not ok_stress:
        # Find the worst offender for the message.
        worst = max(_stress.items(),
                    key=lambda kv: kv[1]["stress_MPa"] - kv[1]["limit_MPa"])
        return (False,
                f"compressive stress exceeded at {worst[0]}: "
                f"{worst[1]['stress_MPa']:.2f} MPa > "
                f"{worst[1]['limit_MPa']:.2f} MPa")

    ok_overhang, overhangs = check_overhang(
        structure, max_overhang_voxels=max_overhang_voxels)
    if not ok_overhang:
        worst = max(overhangs, key=lambda x: x[1])
        return (False,
                f"overhang too long at {worst[0]}: "
                f"{worst[1]} voxels (limit {max_overhang_voxels})")

    if not centroid_over_support_base(structure):
        cx, cy, cz = centroid_of_mass(structure)
        return (False,
                f"tip-over: centroid ({cx:.2f}, {cy:.2f}, {cz:.2f}) "
                "lies outside support base")

    return (True, "stable")


# ---------------------------------------------------------------------------
# Aggregate diagnostic (useful for journals).
# ---------------------------------------------------------------------------
def analyze(structure: Structure, *,
            g: float = G_EARTH,
            safety_factor: float = 2.0,
            max_overhang_voxels: int = 3) -> Dict[str, object]:
    """Run every check and return a structured report (no exceptions)."""
    ok_support, unsupported = check_support(structure)
    ok_stress, stress = check_compressive_stress(
        structure, g=g, safety_factor=safety_factor)
    ok_overhang, overhangs = check_overhang(
        structure, max_overhang_voxels=max_overhang_voxels)
    is_stable, reason = is_structurally_stable(
        structure, g=g, safety_factor=safety_factor,
        max_overhang_voxels=max_overhang_voxels)
    cx, cy, cz = centroid_of_mass(structure)
    return {
        "structure_id": structure.structure_id,
        "block_count": len(structure.blocks),
        "total_mass_kg": round(total_mass(structure), 4),
        "centroid_voxels": (round(cx, 4), round(cy, 4), round(cz, 4)),
        "centroid_over_base": centroid_over_support_base(structure),
        "support": {"ok": ok_support, "unsupported": unsupported[:8]},
        "compressive": {
            "ok": ok_stress,
            "worst_block": None if not stress else max(
                stress.items(),
                key=lambda kv: kv[1]["stress_MPa"])[0],
            "max_stress_MPa": 0.0 if not stress else round(max(
                v["stress_MPa"] for v in stress.values()), 6),
        },
        "overhang": {
            "ok": ok_overhang,
            "offenders": [(pos, run) for pos, run in overhangs[:8]],
        },
        "is_stable": is_stable,
        "reason": reason,
    }


__all__ = [
    "G_EARTH",
    "STRENGTH_TABLE",
    "VoxelBlock",
    "Structure",
    "material_properties",
    "voxel_volume_m3",
    "voxel_area_m2",
    "block_mass",
    "total_mass",
    "centroid_of_mass",
    "centroid_over_support_base",
    "check_support",
    "check_compressive_stress",
    "check_overhang",
    "is_structurally_stable",
    "analyze",
]
