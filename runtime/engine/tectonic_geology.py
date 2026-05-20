"""Genesis Engine — Wave 17 tectonic-aware geology.

Reads the continental macro map (``engine.world_genesis.GenesisAnchor``)
and biases per-chunk ore deposits to match real-world mineralisation
provinces:

  - **Andean-type subduction** (oceanic ↔ continental convergent)
    → porphyry copper, hydrothermal gold, cassiterite, pyrite.
  - **Continental collision** (continental-continental convergent)
    → high-grade metamorphic graphite, pyrite, quartz vein systems.
  - **Island arc** (oceanic-oceanic convergent)
    → moderate hydrothermal Cu + Au.
  - **Mid-ocean ridge** (oceanic divergent)
    → Volcanogenic Massive Sulfides (VMS): chalcopyrite, sphalerite, galena.
  - **Continental rift** (continental divergent)
    → restricted basin evaporites: halite, sylvite, gypsum.
  - **Transform fault** → minor quartz vein.

The module is a **post-pass overlay** : ``engine.geology.generate_chunk_geology``
runs first to produce the base stratigraphic column (biome + elevation
driven), then ``apply_overlay_to_chunk`` injects extra mineral fractions
into the deep layers (≥ 5 m, where hydrothermal fluids would actually
deposit).

Read-only contract :
    - Does not modify any module outside its own state.
    - GenesisWorld arrays are sampled, never mutated.
    - All randomness via :func:`engine.core.prf_rng`.

Determinism : the boost magnitude per layer is a deterministic function
of ``(world_seed, chunk_coord, mineral_name)``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.geology import (
    ChunkGeology, GeologyState, StrataLayer,
    chunk_geology as _base_chunk_geology,
    install_geology, generate_chunk_geology,
)
from engine.world import CHUNK_SIDE_M, world_to_chunk
from engine.world_genesis import (
    GenesisAnchor, GenesisWorld,
    BOUND_NONE, BOUND_DIVERGENT, BOUND_CONVERGENT, BOUND_TRANSFORM,
    OCEANIC, CONTINENTAL,
)


# ADR-0005 tags
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# Per-chunk fraction cap (consistent with engine.geology._select_ore_mix).
_PER_LAYER_FRAC_CAP = 0.30
_PER_MINERAL_FRAC_CAP = 0.20


# ---------------------------------------------------------------------------
# Tectonic context per chunk
# ---------------------------------------------------------------------------

@dataclass
class TectonicContext:
    """Macro tectonic state at one chunk location.

    Sampled once per chunk via :func:`sample_tectonic_context`. Used by
    the overlay to choose which minerals to inject.
    """
    plate_id: int
    plate_kind: int                 # OCEANIC / CONTINENTAL
    boundary_kind: int              # BOUND_NONE / DIVERGENT / CONVERGENT / TRANSFORM
    uplift_rate: float              # m / Myr at this cell
    neighbour_plate_kind: int = -1  # plate kind on the OTHER side, -1 if no boundary
    macro_elevation_m: float = 0.0
    distance_to_coast_km: float = 0.0


def sample_tectonic_context(anchor: GenesisAnchor,
                             x_m: float, y_m: float) -> TectonicContext:
    """Look up macro tectonic data at sim world coordinate ``(x_m, y_m)``.

    Converts sim metres → macro km using ``anchor.sim_origin_macro_km``,
    then snaps to the nearest macro cell. For boundary cells, scans
    4-neighbours to determine the OTHER plate's kind (used to distinguish
    Andean subduction vs Himalayan collision).
    """
    world = anchor.world
    p = world.params
    R = p.resolution
    cell_km = p.map_size_km / R
    x_km = x_m / 1000.0 + anchor.sim_origin_macro_km[0]
    y_km = y_m / 1000.0 + anchor.sim_origin_macro_km[1]
    ix = int(np.clip(np.floor(x_km / cell_km), 0, R - 1))
    iy = int(np.clip(np.floor(y_km / cell_km), 0, R - 1))

    plate_id = int(world.plate_id[iy, ix])
    plate_kind = int(world.plate_kind[plate_id])
    boundary_kind = int(world.boundary_kind[iy, ix])
    uplift_rate = float(world.uplift_rate[iy, ix])

    neighbour_plate_kind = -1
    if boundary_kind in (BOUND_CONVERGENT, BOUND_DIVERGENT, BOUND_TRANSFORM):
        # Scan 4-neighbours, find the first differing plate, record its kind.
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx = ix + dx; ny = iy + dy
            if 0 <= nx < R and 0 <= ny < R:
                npid = int(world.plate_id[ny, nx])
                if npid != plate_id:
                    neighbour_plate_kind = int(world.plate_kind[npid])
                    break

    return TectonicContext(
        plate_id=plate_id,
        plate_kind=plate_kind,
        boundary_kind=boundary_kind,
        uplift_rate=uplift_rate,
        neighbour_plate_kind=neighbour_plate_kind,
        macro_elevation_m=float(world.elevation_m[iy, ix]),
        distance_to_coast_km=float(world.distance_to_coast_km[iy, ix]),
    )


# ---------------------------------------------------------------------------
# Boost tables
# ---------------------------------------------------------------------------

# Province → mineral → additive mass fraction injected into deep layers.
# Values chosen so a single layer's mix can change from "barren / generic"
# to "clearly hydrothermal" without overflowing the 0.30 cap.
_BOOST_ANDEAN_SUBDUCTION: Dict[str, float] = {
    "chalcopyrite": 0.06,    # porphyry copper sulfide
    "native_gold":  0.012,   # epithermal Au
    "cassiterite":  0.025,   # tin granitoids
    "pyrite":       0.04,    # iron sulfide gangue
    "magnetite":    0.02,    # contact metamorphism
}

_BOOST_HIMALAYAN_COLLISION: Dict[str, float] = {
    "graphite":     0.025,   # carbon metamorphism
    "pyrite":       0.025,
    "quartz":       0.05,    # silicic vein systems
    "mica":         0.04,    # garnet-mica schist proxy
}

_BOOST_ISLAND_ARC: Dict[str, float] = {
    "chalcopyrite": 0.03,
    "native_gold":  0.006,
    "pyrite":       0.02,
}

_BOOST_MID_OCEAN_RIDGE: Dict[str, float] = {
    "chalcopyrite": 0.04,    # VMS Cu
    "sphalerite":   0.03,    # VMS Zn
    "galena":       0.025,   # VMS Pb
    "pyrite":       0.04,    # VMS gangue
}

_BOOST_CONTINENTAL_RIFT: Dict[str, float] = {
    "halite":       0.07,    # evaporite NaCl
    "sylvite":      0.025,   # KCl
    "gypsum":       0.045,   # CaSO4·2H2O
}

_BOOST_TRANSFORM_FAULT: Dict[str, float] = {
    "quartz":       0.02,    # fault-zone silicification
}


def _tectonic_boost_table(ctx: TectonicContext) -> Tuple[str, Dict[str, float]]:
    """Pick the right boost table for the tectonic context.

    Returns ``(province_label, {mineral_name → additive_frac})``.
    ``province_label`` is a short string for diagnostics ("andean",
    "himalayan", "island_arc", "mid_ocean_ridge", "continental_rift",
    "transform_fault", "passive").
    """
    bk = ctx.boundary_kind
    pk = ctx.plate_kind
    npk = ctx.neighbour_plate_kind
    if bk == BOUND_CONVERGENT:
        if (pk == CONTINENTAL and npk == OCEANIC) or (pk == OCEANIC and npk == CONTINENTAL):
            return "andean", _BOOST_ANDEAN_SUBDUCTION
        if pk == CONTINENTAL and npk == CONTINENTAL:
            return "himalayan", _BOOST_HIMALAYAN_COLLISION
        # Default to island arc for any other convergent (oc/oc, unknown).
        return "island_arc", _BOOST_ISLAND_ARC
    if bk == BOUND_DIVERGENT:
        if pk == OCEANIC:
            return "mid_ocean_ridge", _BOOST_MID_OCEAN_RIDGE
        if pk == CONTINENTAL:
            return "continental_rift", _BOOST_CONTINENTAL_RIFT
    if bk == BOUND_TRANSFORM:
        return "transform_fault", _BOOST_TRANSFORM_FAULT
    return "passive", {}


# ---------------------------------------------------------------------------
# Overlay application
# ---------------------------------------------------------------------------

def apply_overlay_to_chunk(geology: ChunkGeology, ctx: TectonicContext,
                            world_seed: int) -> Tuple[int, str]:
    """Inject tectonic mineral boosts into the geology's deep layers.

    Modifies ``geology.layers[*].ore_mix`` in place. Topsoil + regolith
    (depth < 5 m) are not affected since hydrothermal fluids deposit
    below the weathering front.

    Returns ``(n_layers_modified, province_label)``.
    """
    province, boost = _tectonic_boost_table(ctx)
    if not boost:
        return 0, province

    # Deterministic per-chunk + per-mineral jitter.
    cx, cy, cz = geology.coord
    rng = prf_rng(world_seed, ["tectonic_geo", "boost"],
                  [int(cx), int(cy), int(cz)])

    n_modified = 0
    # Depth attenuation: shallow deposits get smaller boosts; deep ones full.
    for layer in geology.layers:
        if layer.depth_top_m < 5.0:
            continue
        # Attenuation factor: 0.3 at 5-30 m, 0.7 at 30-200 m, 1.0 deeper.
        if layer.depth_top_m < 30.0:
            depth_atten = 0.3
        elif layer.depth_top_m < 200.0:
            depth_atten = 0.7
        else:
            depth_atten = 1.0

        # Uplift attenuation: stronger uplift = more vigorous hydrothermal.
        # 0..300 m/Myr -> 0.5..1.5 multiplier.
        uplift_atten = 0.5 + min(ctx.uplift_rate / 300.0, 1.0)

        for mineral_name, frac in boost.items():
            # Per-mineral jitter (deterministic), 0.5..1.5.
            jitter = 0.5 + rng.random()
            inject = frac * depth_atten * uplift_atten * jitter
            current = layer.ore_mix.get(mineral_name, 0.0)
            new_val = min(_PER_MINERAL_FRAC_CAP, current + inject)
            layer.ore_mix[mineral_name] = float(new_val)

        # Renormalise so total ore content stays ≤ 0.30.
        total = sum(layer.ore_mix.values())
        if total > _PER_LAYER_FRAC_CAP:
            scale = _PER_LAYER_FRAC_CAP / total
            layer.ore_mix = {k: float(v * scale)
                              for k, v in layer.ore_mix.items()}
        n_modified += 1

    return n_modified, province


# ---------------------------------------------------------------------------
# Sim integration
# ---------------------------------------------------------------------------

# Per-sim state for tectonic overlay.
@dataclass
class TectonicGeoState:
    anchor: GenesisAnchor
    province_by_chunk: Dict[Tuple[int, int, int], str] = field(default_factory=dict)
    layers_modified: int = 0
    chunks_overlaid: int = 0


def install_tectonic_overlay(sim, anchor: GenesisAnchor) -> TectonicGeoState:
    """Idempotent installer that wires tectonic-aware ore mixes into ``sim``.

    After install, every call to ``engine.geology.chunk_geology(sim, coord)``
    transparently applies the tectonic overlay. Already-cached geology is
    NOT re-overlaid retroactively — call :func:`apply_to_existing` to
    process them.

    Mutates :mod:`engine.geology` once: replaces ``chunk_geology`` with a
    wrapper. Subsequent installs are no-ops.
    """
    install_geology(sim)
    existing = getattr(sim, "_tectonic_geo_state", None)
    if existing is not None:
        existing.anchor = anchor
        return existing

    state = TectonicGeoState(anchor=anchor)
    sim._tectonic_geo_state = state

    import engine.geology as _geo
    if getattr(_geo, "_tectonic_inner_chunk_geology", None) is None:
        _geo._tectonic_inner_chunk_geology = _geo.chunk_geology

        def _wrapper(sim_inner, coord):
            base = _geo._tectonic_inner_chunk_geology(sim_inner, coord)
            if base is None:
                return None
            st: Optional[TectonicGeoState] = getattr(
                sim_inner, "_tectonic_geo_state", None)
            if st is None:
                return base
            # Only run overlay once per chunk.
            if coord in st.province_by_chunk:
                return base
            # Sample tectonic context at chunk centre (world metres).
            cx, cy, cz = coord
            x_m = (cx + 0.5) * CHUNK_SIDE_M
            y_m = (cy + 0.5) * CHUNK_SIDE_M
            ctx = sample_tectonic_context(st.anchor, x_m, y_m)
            n_layers, province = apply_overlay_to_chunk(
                base, ctx, int(sim_inner.cfg.seed))
            st.province_by_chunk[coord] = province
            st.layers_modified += n_layers
            st.chunks_overlaid += 1
            return base

        _geo.chunk_geology = _wrapper

    return state


def apply_to_existing(sim) -> int:
    """Re-overlay any cached chunks that pre-date the install.

    Returns the count of chunks freshly overlaid.
    """
    state: Optional[TectonicGeoState] = getattr(sim, "_tectonic_geo_state", None)
    if state is None:
        return 0
    geo_state: GeologyState = sim._geology_state
    n_new = 0
    for coord, geology in list(geo_state.chunks.items()):
        if coord in state.province_by_chunk:
            continue
        cx, cy, cz = coord
        x_m = (cx + 0.5) * CHUNK_SIDE_M
        y_m = (cy + 0.5) * CHUNK_SIDE_M
        ctx = sample_tectonic_context(state.anchor, x_m, y_m)
        n_layers, province = apply_overlay_to_chunk(
            geology, ctx, int(sim.cfg.seed))
        state.province_by_chunk[coord] = province
        state.layers_modified += n_layers
        state.chunks_overlaid += 1
        n_new += 1
    return n_new


def tectonic_state(sim) -> Dict[str, object]:
    """Reporter: province counts, chunks overlaid, etc."""
    state: Optional[TectonicGeoState] = getattr(sim, "_tectonic_geo_state", None)
    if state is None:
        return {"installed": False}
    province_counts: Dict[str, int] = {}
    for province in state.province_by_chunk.values():
        province_counts[province] = province_counts.get(province, 0) + 1
    return {
        "installed": True,
        "chunks_overlaid": state.chunks_overlaid,
        "layers_modified": state.layers_modified,
        "provinces": province_counts,
    }


def uninstall_tectonic_overlay(sim) -> bool:
    """Detach the overlay and restore the original :func:`chunk_geology`.

    Returns ``True`` if anything was uninstalled. Primarily useful for
    tests and for hot-swapping anchors.
    """
    import engine.geology as _geo
    state = getattr(sim, "_tectonic_geo_state", None)
    if state is None:
        return False
    inner = getattr(_geo, "_tectonic_inner_chunk_geology", None)
    if inner is not None:
        _geo.chunk_geology = inner
        _geo._tectonic_inner_chunk_geology = None
    del sim._tectonic_geo_state
    return True


def stratigraphy_layer_index(depth_m: float, *,
                              layer_thickness_m: float = 50.0,
                              n_layers: int = 8) -> int:
    """Light stratigraphy: map depth below surface to layer index [0, n_layers)."""
    d = max(0.0, float(depth_m))
    idx = int(d / max(layer_thickness_m, 1.0))
    return min(idx, n_layers - 1)
