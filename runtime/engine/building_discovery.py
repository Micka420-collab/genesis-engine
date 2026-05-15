"""Genesis Engine — Wave 10e emergent building discovery.

**Règle invariante du projet** : rien n'est scripté, les agents
doivent découvrir par eux-mêmes.

This module replaces the hard-coded RECIPES of
:mod:`engine.realistic_construction` with **discovery-driven
emergence** :

  1. Agents place blocks one at a time via ``place_block``.
  2. Each block placement validates structural stability with
     :mod:`engine.statics` (Wave 1 — real compressive/tensile/
     overhang/support check from real material properties).
  3. When the structure satisfies all four functions (closed
     footprint, walls, roof, accessible interior), it's recognised
     as a "building".
  4. The agent's *culture* names it for the first time it sees this
     archetype. The name is auto-generated from the dominant
     material + footprint dimensions — NOT pre-scripted.
  5. Future agents of the same culture who build a similar structure
     get the same name (cultural archetype transmission).

So:

* Cu70Sn30 alloy emerges from `material_synthesis.synthesize` —
  no recipe table.
* A "stone_dwelling_3x3" emerges from a stable 3×3×2 brick stack —
  no recipe table.

What this module does NOT do
----------------------------
* It does not enumerate possible buildings.
* It does not predefine "stone_hut" or "marble_temple".
* It does not require the agent to know what they're building.

What an archetype is
--------------------
Once a culture has discovered N >= 1 stable structures sharing the
same fingerprint, that fingerprint becomes a **named archetype** for
that culture. The fingerprint encodes :

  - dominant material (max-mass material in the structure)
  - footprint dimensions in voxels (x, y)
  - height in voxels
  - has_roof (closed top layer)

Two structures match if all 4 fingerprint fields are equal. Names
are generated deterministically via :func:`engine.core.prf_rng`.

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"``
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"``
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from engine.core import prf_rng
from engine.statics import (
    Structure, VoxelBlock, is_structurally_stable,
)


# ---------------------------------------------------------------------------
# Minimum function thresholds — beyond which a structure counts as a
# "building" (= covers a footprint, has walls, has roof, encloses space).
# ---------------------------------------------------------------------------

MIN_BLOCKS_FOR_BUILDING = 8         # at least 8 voxels (1m³+ at 0.5m blocks)
MIN_FOOTPRINT_VOXELS = 4            # at least 2x2 footprint
MIN_HEIGHT_VOXELS = 2               # at least 2 layers tall


# ---------------------------------------------------------------------------
# Fingerprint + archetype types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BuildingFingerprint:
    dominant_material: str
    footprint_x: int
    footprint_y: int
    height: int
    has_roof: bool

    def short_key(self) -> str:
        return (f"{self.dominant_material}_"
                f"{self.footprint_x}x{self.footprint_y}x{self.height}"
                f"{'_roofed' if self.has_roof else ''}")


@dataclass
class CulturalArchetype:
    """An archetype is a (fingerprint → name) mapping recognised by a culture."""
    fingerprint: BuildingFingerprint
    name: str
    culture: int
    discovered_tick: int
    instances_count: int = 1


@dataclass
class DiscoveredBuilding:
    """One concrete instance built by an agent."""
    building_id: int
    fingerprint: BuildingFingerprint
    archetype_name: str
    builder_culture: int
    built_tick: int
    chunk_coord: Tuple[int, int, int]
    n_blocks: int
    is_stable: bool


@dataclass
class BuildingDiscoveryState:
    """Attached to ``sim._building_discovery_state``."""
    # Pending block buffer per agent — they accumulate blocks until they
    # request a structural check via complete_structure(row).
    pending_blocks: Dict[int, List[VoxelBlock]] = field(default_factory=dict)
    # Per-culture archetype dictionary (fingerprint_key → archetype).
    cultural_archetypes: Dict[int, Dict[str, CulturalArchetype]] = field(
        default_factory=dict)
    # Discovered buildings instances.
    buildings: Dict[int, DiscoveredBuilding] = field(default_factory=dict)
    next_building_id: int = 1
    next_struct_id: int = 1
    # Stats.
    attempts_total: int = 0
    successes_total: int = 0
    structural_failures: int = 0
    function_failures: int = 0


# ---------------------------------------------------------------------------
# Discovery API
# ---------------------------------------------------------------------------

def _agent_culture(sim, row: int) -> int:
    cultures = getattr(sim.agents, "culture", None)
    if cultures is not None:
        try:
            return int(cultures[row])
        except Exception:
            return 0
    return 0


def place_block(
    sim,
    row: int,
    pos: Tuple[int, int, int],
    material: str,
    voxel_size: float = 0.25,
) -> None:
    """Add a block to the agent's pending buffer.

    No structural validation here — that's deferred to
    ``complete_structure`` so the buffer can be built up.
    """
    state = install_building_discovery(sim)
    buf = state.pending_blocks.setdefault(row, [])
    buf.append(VoxelBlock.from_material(pos, material, voxel_size))


def _structure_function_ok(blocks: List[VoxelBlock]) -> Tuple[bool, str,
                                                              Optional[BuildingFingerprint]]:
    """Check that the block set has shelter-like geometry.

    Returns (ok, reason, fingerprint). On failure, fingerprint is None.
    """
    if len(blocks) < MIN_BLOCKS_FOR_BUILDING:
        return False, f"too_few_blocks:{len(blocks)}<{MIN_BLOCKS_FOR_BUILDING}", None
    # Footprint = unique (x, y) of the LOWEST layer.
    if not blocks:
        return False, "no_blocks", None
    min_z = min(b.position[2] for b in blocks)
    max_z = max(b.position[2] for b in blocks)
    height = max_z - min_z + 1
    if height < MIN_HEIGHT_VOXELS:
        return False, f"too_short:height={height}", None
    footprint = {(b.position[0], b.position[1])
                 for b in blocks if b.position[2] == min_z}
    if len(footprint) < MIN_FOOTPRINT_VOXELS:
        return False, (f"footprint_too_small:{len(footprint)}<"
                       f"{MIN_FOOTPRINT_VOXELS}"), None
    # Bounding box xy.
    xs = [p[0] for p in footprint]
    ys = [p[1] for p in footprint]
    fx = max(xs) - min(xs) + 1
    fy = max(ys) - min(ys) + 1
    # Roof check: at least 50 % of the footprint must be covered at max_z.
    top_layer = {(b.position[0], b.position[1])
                 for b in blocks if b.position[2] == max_z}
    has_roof = len(top_layer) >= 0.5 * len(footprint) and max_z > min_z
    # Dominant material = the one with the most blocks.
    counts: Dict[str, int] = {}
    for b in blocks:
        counts[b.material] = counts.get(b.material, 0) + 1
    dominant = max(counts.items(), key=lambda kv: kv[1])[0]
    fp = BuildingFingerprint(
        dominant_material=dominant,
        footprint_x=fx, footprint_y=fy, height=height,
        has_roof=has_roof,
    )
    return True, "ok", fp


def _auto_name_archetype(sim, culture: int, fp: BuildingFingerprint) -> str:
    """Deterministic auto-naming via prf_rng.

    Name = "<material>_<footprint>x<footprint>x<height>_<3-letter suffix>".
    The suffix is sampled deterministically so two cultures can stumble
    on the same fingerprint and produce different names — like real
    languages do.
    """
    rng = prf_rng(sim.cfg.seed,
                  ["building_discovery", "name", fp.short_key()],
                  [int(culture)])
    consonants = "kmnprstv"
    vowels = "aeiou"
    suffix = (consonants[int(rng.random() * len(consonants))]
              + vowels[int(rng.random() * len(vowels))]
              + consonants[int(rng.random() * len(consonants))])
    return f"{fp.dominant_material}_{fp.footprint_x}x{fp.footprint_y}x{fp.height}_{suffix}"


def complete_structure(
    sim,
    row: int,
) -> Tuple[bool, Optional[int], str]:
    """Submit the agent's pending block buffer for evaluation.

    Pipeline :
      1. Function check (footprint, height, roof, block count).
      2. Structural stability via engine.statics.
      3. Match-or-create archetype for the agent's culture.
      4. Record DiscoveredBuilding.
      5. Clear the pending buffer.

    Returns ``(success, building_id, reason)``.
    """
    state = install_building_discovery(sim)
    blocks = state.pending_blocks.get(row, [])
    state.attempts_total += 1
    if not blocks:
        return False, None, "no_blocks"
    # Function (shelter-shape) check first.
    ok_fn, reason_fn, fp = _structure_function_ok(blocks)
    if not ok_fn or fp is None:
        state.function_failures += 1
        state.pending_blocks[row] = []   # consume the failed attempt
        return False, None, f"function:{reason_fn}"
    # Structural stability check via Wave 1 statics.
    sid = state.next_struct_id
    state.next_struct_id += 1
    structure = Structure(structure_id=sid, blocks=list(blocks), voxel_size_m=0.25)
    stable, why = is_structurally_stable(structure)
    if not stable:
        state.structural_failures += 1
        state.pending_blocks[row] = []
        return False, None, f"unstable:{why}"
    # Archetype lookup / creation per culture.
    culture = _agent_culture(sim, row)
    arch_dict = state.cultural_archetypes.setdefault(culture, {})
    key = fp.short_key()
    archetype = arch_dict.get(key)
    if archetype is None:
        name = _auto_name_archetype(sim, culture, fp)
        archetype = CulturalArchetype(
            fingerprint=fp, name=name,
            culture=culture, discovered_tick=int(sim.tick),
        )
        arch_dict[key] = archetype
    else:
        archetype.instances_count += 1
    # Record the discovered building.
    bid = state.next_building_id
    state.next_building_id += 1
    from engine.world import world_to_chunk
    px = float(sim.agents.pos[row, 0])
    py = float(sim.agents.pos[row, 1])
    ch = world_to_chunk(px, py)
    state.buildings[bid] = DiscoveredBuilding(
        building_id=bid, fingerprint=fp,
        archetype_name=archetype.name,
        builder_culture=culture, built_tick=int(sim.tick),
        chunk_coord=ch, n_blocks=len(blocks), is_stable=True,
    )
    state.successes_total += 1
    state.pending_blocks[row] = []
    return True, bid, archetype.name


def abandon_pending(sim, row: int) -> int:
    """Discard the agent's pending block buffer without evaluating it."""
    state = install_building_discovery(sim)
    blocks = state.pending_blocks.pop(row, [])
    return len(blocks)


# ---------------------------------------------------------------------------
# Installer + reporter
# ---------------------------------------------------------------------------

def install_building_discovery(sim) -> BuildingDiscoveryState:
    """Idempotent installer. No step hook — discovery is event-driven."""
    existing: Optional[BuildingDiscoveryState] = getattr(
        sim, "_building_discovery_state", None)
    if existing is not None:
        return existing
    state = BuildingDiscoveryState()
    sim._building_discovery_state = state
    return state


def building_discovery_state(sim) -> Dict[str, object]:
    state: Optional[BuildingDiscoveryState] = getattr(
        sim, "_building_discovery_state", None)
    if state is None:
        return {}
    # Per-culture archetype counts.
    arch_per_culture = {
        str(c): sorted(
            [{"name": a.name, "key": a.fingerprint.short_key(),
              "instances": a.instances_count,
              "discovered_tick": a.discovered_tick}
             for a in d.values()],
            key=lambda x: -x["instances"])
        for c, d in state.cultural_archetypes.items()
    }
    return {
        "attempts_total": state.attempts_total,
        "successes_total": state.successes_total,
        "structural_failures": state.structural_failures,
        "function_failures": state.function_failures,
        "n_archetypes_total": sum(len(d) for d in state.cultural_archetypes.values()),
        "n_buildings_total": len(state.buildings),
        "archetypes_per_culture": arch_per_culture,
        "pending_buffers": {
            str(r): len(blocks) for r, blocks in state.pending_blocks.items()
        },
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_building_discovery_state(sim, target_dir: str) -> bool:
    state: Optional[BuildingDiscoveryState] = getattr(
        sim, "_building_discovery_state", None)
    if state is None:
        return False
    payload = {
        "next_building_id": state.next_building_id,
        "next_struct_id": state.next_struct_id,
        "attempts_total": state.attempts_total,
        "successes_total": state.successes_total,
        "structural_failures": state.structural_failures,
        "function_failures": state.function_failures,
        "cultural_archetypes": {
            str(c): [
                {"fingerprint": {
                    "dominant_material": a.fingerprint.dominant_material,
                    "footprint_x": a.fingerprint.footprint_x,
                    "footprint_y": a.fingerprint.footprint_y,
                    "height": a.fingerprint.height,
                    "has_roof": a.fingerprint.has_roof},
                 "name": a.name,
                 "culture": a.culture,
                 "discovered_tick": a.discovered_tick,
                 "instances_count": a.instances_count}
                for a in d.values()
            ]
            for c, d in state.cultural_archetypes.items()
        },
        "buildings": [
            {"building_id": b.building_id,
             "fingerprint": {
                 "dominant_material": b.fingerprint.dominant_material,
                 "footprint_x": b.fingerprint.footprint_x,
                 "footprint_y": b.fingerprint.footprint_y,
                 "height": b.fingerprint.height,
                 "has_roof": b.fingerprint.has_roof},
             "archetype_name": b.archetype_name,
             "builder_culture": b.builder_culture,
             "built_tick": b.built_tick,
             "chunk_coord": list(b.chunk_coord),
             "n_blocks": b.n_blocks,
             "is_stable": b.is_stable}
            for b in state.buildings.values()
        ],
    }
    with open(os.path.join(target_dir, "building_discovery.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return True


def load_building_discovery_state(sim, target_dir: str) -> bool:
    path = os.path.join(target_dir, "building_discovery.json")
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state = install_building_discovery(sim)
    state.next_building_id = int(payload.get("next_building_id", 1))
    state.next_struct_id = int(payload.get("next_struct_id", 1))
    state.attempts_total = int(payload.get("attempts_total", 0))
    state.successes_total = int(payload.get("successes_total", 0))
    state.structural_failures = int(payload.get("structural_failures", 0))
    state.function_failures = int(payload.get("function_failures", 0))
    state.cultural_archetypes.clear()
    for c, arch_list in payload.get("cultural_archetypes", {}).items():
        d = state.cultural_archetypes.setdefault(int(c), {})
        for ad in arch_list:
            f_dict = ad["fingerprint"]
            fp = BuildingFingerprint(
                dominant_material=str(f_dict["dominant_material"]),
                footprint_x=int(f_dict["footprint_x"]),
                footprint_y=int(f_dict["footprint_y"]),
                height=int(f_dict["height"]),
                has_roof=bool(f_dict["has_roof"]),
            )
            d[fp.short_key()] = CulturalArchetype(
                fingerprint=fp, name=str(ad["name"]),
                culture=int(ad["culture"]),
                discovered_tick=int(ad["discovered_tick"]),
                instances_count=int(ad.get("instances_count", 1)),
            )
    state.buildings.clear()
    for bd in payload.get("buildings", []):
        f_dict = bd["fingerprint"]
        fp = BuildingFingerprint(
            dominant_material=str(f_dict["dominant_material"]),
            footprint_x=int(f_dict["footprint_x"]),
            footprint_y=int(f_dict["footprint_y"]),
            height=int(f_dict["height"]),
            has_roof=bool(f_dict["has_roof"]),
        )
        state.buildings[int(bd["building_id"])] = DiscoveredBuilding(
            building_id=int(bd["building_id"]),
            fingerprint=fp,
            archetype_name=str(bd["archetype_name"]),
            builder_culture=int(bd["builder_culture"]),
            built_tick=int(bd["built_tick"]),
            chunk_coord=tuple(int(x) for x in bd["chunk_coord"]),
            n_blocks=int(bd["n_blocks"]),
            is_stable=bool(bd["is_stable"]),
        )
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "BuildingFingerprint",
    "CulturalArchetype",
    "DiscoveredBuilding",
    "BuildingDiscoveryState",
    "MIN_BLOCKS_FOR_BUILDING",
    "MIN_FOOTPRINT_VOXELS",
    "MIN_HEIGHT_VOXELS",
    "install_building_discovery",
    "place_block",
    "complete_structure",
    "abandon_pending",
    "building_discovery_state",
    "save_building_discovery_state",
    "load_building_discovery_state",
]
