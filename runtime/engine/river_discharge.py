"""Genesis Engine — Wave 64 live river-discharge coupling.

Closes the **hydrology half of D11** (AUDIT-DELTA-2026-06-23): the substrate
is frozen on the agent-visible *chunk* path. Two pieces already exist but
never meet —

  * :mod:`engine.chunk_hydrology` paints a macro-aligned river stripe into
    each river chunk, but with a **hard-coded** ``RIVER_WATER_LITRES = 800``
    depth: the painted river is blind to how much water its basin actually
    carries, and it never changes once painted ("rivers peintes").
  * :mod:`engine.discharge_observer` computes the **real** emergent discharge
    field ``Q`` — the mass-conserving LTI routing of a climate-driven runoff
    balance down the D8 network (Hascoet et al. 2026, *Differentiable River
    Routing*, JGR-ML) — but it is a pure **observer**: nothing on the chunk
    path ever consumes it ("observer treadmill").

This module is the missing wire. It is the exact hydrological partner of the
orographic temperature coupling in :mod:`engine.climate_biome`: where that one
re-reads the live macro ``elevation_m`` and turns its drift into a per-chunk
*temperature* anomaly, this one re-reads the same live ``elevation_m`` and
turns its drift into a per-chunk *river discharge* response.

Physical channel
----------------

Uplift cools a basin at the environmental lapse rate (``earth_laws.
LAPSE_K_PER_M`` = 6.5 K/km — the same SSOT orographic coupling uses). Colder
basins lose less water to evapotranspiration, so **runoff rises and the river
swells** ("water-tower" effect). Erosion / subsidence warms, ET climbs, runoff
falls and the river **shrinks** — and if warming drives the actual-ET demand up
to the precipitation ceiling, runoff collapses to zero and the channel runs
**dry** (an emergent wadi). The runoff balance and the routing are reused
*verbatim* from :mod:`engine.discharge_observer` (SSOT ``runoff_field_m3s`` +
``route_runoff``): ``runoff = max(P − ET, 0)`` with a temperature-limited
``ET = min(P, k·max(T, 0))``, routed exactly down the static D8 graph.

Only the **temperature / ET channel** of the orographic discharge response is
modelled here: precipitation is held at its install-time baseline (the
windward/leeward orographic *precip* enhancement remains backlog). The D8 flow
network is held fixed too — uplift does not re-route the basin, it only
re-weights the runoff each cell contributes. Both simplifications mirror the
orographic temperature coupling, which likewise reads — never re-derives — the
macro graph.

Live driver, and why it is safe to install by default
-----------------------------------------------------

The sole live driver is ``anchor.world.elevation_m`` — mutated by
``plate_tectonics_live`` / ``novel_operators`` inside the disjoint
``autonomous_world`` loop, never inside a plain ``sim.step``. So on any
simulation that does not deform the terrain (every unit / full-stack smoke),
this coupling is a **strict no-op**: it early-returns before touching a single
chunk, writes nothing, and leaves prior behaviour bit-identical. It only comes
alive on the runtime ``terre`` path where the world actually moves. Set
``enabled=False`` to opt out entirely.

Contracts
---------

* **Read-only macro** — the :class:`GenesisWorld` arrays are never written;
  the effective temperature is a local array derived from a read of live
  elevation.
* **Deterministic** — no RNG; pure arithmetic + the deterministic Kahn sweep
  in :func:`engine.discharge_observer.route_runoff`.
* **Mass-aware** — the *macro* discharge that drives the scaling is exactly
  mass-conserving (``Σ Q[sinks] == Σ runoff``); the chunk river depth is a
  faithful downscaled proxy of it, not a second water budget.
* **Reversible** — a chunk's river cells are scaled from a frozen baseline
  snapshot, so the river returns exactly to its painted state if the elevation
  returns to baseline (never compounding).

No new cross-language tell (``PY_TO_RUST`` unchanged — this is substrate
physics, not an agent capability), no new RNG, no mutation of the macro world.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np

from engine.chunk_hydrology import RIVER_WATER_LITRES
from engine.discharge_observer import (DischargeConfig, route_runoff,
                                       runoff_field_m3s)
from engine.earth_laws import LAPSE_K_PER_M
from engine.world import CHUNK_SIDE_M, invalidate_resource_masks
from engine.world_genesis import GenesisAnchor


# ADR-0005 pipeline tags (mirrors chunk_hydrology / climate_biome).
PIPELINE_LAYER = "Genesis-L1 Earth-Seed"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# A chunk cell counts as "river" (and thus discharge-coupled) when its painted
# water is at least half the canonical river depth — chunk_hydrology paints at
# exactly RIVER_WATER_LITRES, so this comfortably catches the stripe while
# ignoring incidental ambient water.
_RIVER_CELL_THRESHOLD = RIVER_WATER_LITRES * 0.5

# Discharge below this (m³/s) at a cell is treated as "no measurable river" —
# the baseline ratio is undefined, so the chunk is left at its painted value.
_MIN_BASELINE_DISCHARGE = 1e-9


# ---------------------------------------------------------------------------
# Sim state
# ---------------------------------------------------------------------------

@dataclass
class RiverDischargeState:
    """Per-sim state of the live river-discharge coupling."""
    anchor: GenesisAnchor
    enabled: bool = True
    # Ratio clamps: a basin can dry to nothing (0) but a single uplift cannot
    # swell a river beyond ``max_ratio`` × its painted depth.
    min_ratio: float = 0.0
    max_ratio: float = 4.0
    runoff_cfg: DischargeConfig = field(default_factory=DischargeConfig)

    # Install-time macro snapshots (read-only baselines).
    cell_km: float = 0.0
    base_elev_m: Optional[np.ndarray] = None
    base_precip_mm: Optional[np.ndarray] = None
    base_temp_c: Optional[np.ndarray] = None
    base_discharge: Optional[np.ndarray] = None   # Q0 (m³/s) per macro cell

    # Per-chunk frozen river snapshot: coord -> (boolean mask, baseline water).
    chunk_river: Dict[Tuple[int, int, int],
                      Tuple[np.ndarray, np.ndarray]] = field(
        default_factory=dict)
    # Coords whose river is currently scaled away from baseline (need restore
    # if the elevation returns to baseline).
    scaled_coords: set = field(default_factory=set)

    # Diagnostics.
    last_apply_tick: int = -1
    last_changed: bool = False
    chunks_coupled: int = 0
    min_ratio_seen: float = 1.0
    max_ratio_seen: float = 1.0


# ---------------------------------------------------------------------------
# Macro helpers
# ---------------------------------------------------------------------------

def _clamped(elev: np.ndarray) -> np.ndarray:
    """Elevation clamped at sea level — the lapse term only applies on land,
    consistent with the macro baseline temperature in ``world_genesis``."""
    return np.maximum(np.asarray(elev, dtype=np.float64), 0.0)


def _macro_cell_index(anchor: GenesisAnchor,
                      coord: Tuple[int, int, int],
                      R: int, cell_km: float) -> Tuple[int, int]:
    """Floor macro-cell index at a chunk centre (matches chunk_hydrology)."""
    cx, cy, _cz = coord
    x_km = (cx + 0.5) * CHUNK_SIDE_M / 1000.0 + anchor.sim_origin_macro_km[0]
    y_km = (cy + 0.5) * CHUNK_SIDE_M / 1000.0 + anchor.sim_origin_macro_km[1]
    ix = int(np.clip(np.floor(x_km / cell_km), 0, R - 1))
    iy = int(np.clip(np.floor(y_km / cell_km), 0, R - 1))
    return ix, iy


def _discharge_field(state: RiverDischargeState,
                     elev_m: np.ndarray) -> np.ndarray:
    """Routed discharge field (m³/s) for a given elevation, all else baseline.

    The effective temperature is the baseline macro temperature shifted by the
    orographic lapse anomaly of ``elev_m`` versus the install baseline; the
    runoff balance and routing are the discharge-observer SSOT. Precipitation
    and the D8 graph are held at their baseline. Pure / deterministic.
    """
    world = state.anchor.world
    d_elev = _clamped(elev_m) - _clamped(state.base_elev_m)
    temp_eff = np.asarray(state.base_temp_c, dtype=np.float64) \
        - LAPSE_K_PER_M * d_elev
    runoff = runoff_field_m3s(state.base_precip_mm, temp_eff,
                              state.cell_km, state.runoff_cfg)
    return route_runoff(world.flow_dir, runoff)


def _baseline_discharge(state: RiverDischargeState) -> np.ndarray:
    """Q0: routed discharge at the install-time climate (cached on the state)."""
    if state.base_discharge is None:
        state.base_discharge = _discharge_field(state, state.base_elev_m)
    return state.base_discharge


# ---------------------------------------------------------------------------
# Per-chunk river snapshot + scaling
# ---------------------------------------------------------------------------

def _ensure_chunk_river(state: RiverDischargeState,
                        coord: Tuple[int, int, int], chunk) -> bool:
    """Lazily freeze a chunk's painted river cells. Returns True if the chunk
    is a river chunk (now or already) and is coupled."""
    if coord in state.chunk_river:
        return True
    water = np.asarray(chunk.water)
    mask = water >= np.float32(_RIVER_CELL_THRESHOLD)
    if not bool(mask.any()):
        return False  # not (yet) painted — retried on a later apply
    state.chunk_river[coord] = (mask.copy(),
                                water[mask].astype(np.float32).copy())
    return True


def _ratio_at(state: RiverDischargeState, coord: Tuple[int, int, int],
              q_live: np.ndarray, q0: np.ndarray, R: int) -> Optional[float]:
    ix, iy = _macro_cell_index(state.anchor, coord, R, state.cell_km)
    base_q = float(q0[iy, ix])
    if base_q < _MIN_BASELINE_DISCHARGE:
        return None
    ratio = float(q_live[iy, ix]) / base_q
    return float(np.clip(ratio, state.min_ratio, state.max_ratio))


def _scale_chunk(state: RiverDischargeState, coord: Tuple[int, int, int],
                 chunk, ratio: float) -> None:
    mask, base_vals = state.chunk_river[coord]
    chunk.water[mask] = (base_vals * np.float32(ratio)).astype(chunk.water.dtype)
    invalidate_resource_masks(chunk)
    if abs(ratio - 1.0) > 1e-9:
        state.scaled_coords.add(coord)
    else:
        state.scaled_coords.discard(coord)


def _restore_chunk(state: RiverDischargeState, coord: Tuple[int, int, int],
                   chunk) -> None:
    mask, base_vals = state.chunk_river[coord]
    chunk.water[mask] = base_vals.astype(chunk.water.dtype)
    invalidate_resource_masks(chunk)


# ---------------------------------------------------------------------------
# Public API — install / step / state / uninstall
# ---------------------------------------------------------------------------

def install_river_discharge(sim,
                            anchor: GenesisAnchor,
                            *,
                            enabled: bool = True,
                            min_ratio: float = 0.0,
                            max_ratio: float = 4.0,
                            runoff_config: Optional[DischargeConfig] = None,
                            ) -> RiverDischargeState:
    """Idempotent installer.

    Snapshots the install-time macro climate (elevation / precip / temp) and the
    baseline discharge field, then monkey-patches :meth:`Simulation.step` so
    :func:`apply_river_discharge_step` runs after each tick. Re-installing on the
    same sim is a no-op that simply refreshes the parameters and the anchor.
    """
    existing: Optional[RiverDischargeState] = getattr(
        sim, "_river_discharge_state", None)
    if existing is not None:
        existing.anchor = anchor
        existing.enabled = bool(enabled)
        existing.min_ratio = float(min_ratio)
        existing.max_ratio = float(max_ratio)
        if runoff_config is not None:
            existing.runoff_cfg = runoff_config
        return existing

    world = anchor.world
    R = int(world.params.resolution)
    state = RiverDischargeState(
        anchor=anchor,
        enabled=bool(enabled),
        min_ratio=float(min_ratio),
        max_ratio=float(max_ratio),
        runoff_cfg=(runoff_config if runoff_config is not None
                    else DischargeConfig()),
        cell_km=float(world.params.map_size_km) / float(R),
        base_elev_m=np.asarray(world.elevation_m, dtype=np.float64).copy(),
        base_precip_mm=np.asarray(world.precip_mm, dtype=np.float64).copy(),
        base_temp_c=np.asarray(world.temp_c, dtype=np.float64).copy(),
    )
    _baseline_discharge(state)  # cache Q0 now
    sim._river_discharge_state = state

    if getattr(sim, "_river_discharge_orig_step", None) is None:
        orig_step = sim.step

        def _patched_step(*args, **kwargs):
            stats = orig_step(*args, **kwargs)
            if getattr(sim, "_river_discharge_state", None) is not None:
                apply_river_discharge_step(sim)
            return stats

        sim._river_discharge_orig_step = orig_step
        sim.step = _patched_step  # type: ignore[assignment]

    return state


def apply_river_discharge_step(sim) -> Dict[str, float]:
    """One tick of the coupling.

    On a static-elevation world this early-returns without touching any chunk
    (after restoring any river still scaled from an earlier deformation). When
    the live macro elevation differs from the install baseline, it routes the
    discharge for the live climate and rescales each river chunk's painted water
    by ``clip(Q_live / Q0, min_ratio, max_ratio)`` at its macro cell.
    """
    state: Optional[RiverDischargeState] = getattr(
        sim, "_river_discharge_state", None)
    if state is None or not state.enabled:
        return {"changed": 0.0, "chunks_scaled": 0.0}

    state.last_apply_tick = int(getattr(sim, "tick", 0))
    world = state.anchor.world
    R = int(world.params.resolution)

    elev_live = np.asarray(world.elevation_m, dtype=np.float64)
    changed = not np.array_equal(_clamped(elev_live), _clamped(state.base_elev_m))
    state.last_changed = bool(changed)

    cache = list(sim.streamer.cache.items())

    if not changed:
        # Static elevation: strict no-op, except restore any river left scaled
        # by a previous deformation that has since reverted.
        restored = 0
        if state.scaled_coords:
            cache_map = dict(cache)
            for coord in list(state.scaled_coords):
                ch = cache_map.get(coord)
                if ch is not None and coord in state.chunk_river:
                    _restore_chunk(state, coord, ch)
                restored += 1
            state.scaled_coords.clear()
        return {"changed": 0.0, "chunks_scaled": 0.0, "chunks_restored": float(restored)}

    q0 = _baseline_discharge(state)
    q_live = _discharge_field(state, elev_live)

    n_scaled = 0
    rmin, rmax = 1.0, 1.0
    for coord, chunk in cache:
        if not _ensure_chunk_river(state, coord, chunk):
            continue
        ratio = _ratio_at(state, coord, q_live, q0, R)
        if ratio is None:
            continue
        _scale_chunk(state, coord, chunk, ratio)
        n_scaled += 1
        rmin = min(rmin, ratio)
        rmax = max(rmax, ratio)

    state.chunks_coupled = len(state.chunk_river)
    state.min_ratio_seen = float(rmin)
    state.max_ratio_seen = float(rmax)

    return {
        "changed": 1.0,
        "chunks_scaled": float(n_scaled),
        "min_ratio": float(rmin),
        "max_ratio": float(rmax),
    }


def river_discharge_state(sim) -> Dict[str, object]:
    """Diagnostic reporter."""
    state: Optional[RiverDischargeState] = getattr(
        sim, "_river_discharge_state", None)
    if state is None:
        return {"installed": False}
    return {
        "installed": True,
        "enabled": bool(state.enabled),
        "min_ratio": float(state.min_ratio),
        "max_ratio": float(state.max_ratio),
        "cell_km": float(state.cell_km),
        "river_chunks_tracked": int(len(state.chunk_river)),
        "chunks_currently_scaled": int(len(state.scaled_coords)),
        "last_apply_tick": int(state.last_apply_tick),
        "last_changed": bool(state.last_changed),
        "min_ratio_seen": float(state.min_ratio_seen),
        "max_ratio_seen": float(state.max_ratio_seen),
    }


def uninstall_river_discharge(sim) -> bool:
    """Detach the coupling and restore ``sim.step``. Does not un-scale rivers
    already scaled (the world has flowed). Returns ``True`` if anything was
    removed."""
    state = getattr(sim, "_river_discharge_state", None)
    if state is None:
        return False
    orig = getattr(sim, "_river_discharge_orig_step", None)
    if orig is not None:
        sim.step = orig
        sim._river_discharge_orig_step = None
    del sim._river_discharge_state
    return True


__all__ = [
    "RiverDischargeState",
    "install_river_discharge",
    "apply_river_discharge_step",
    "river_discharge_state",
    "uninstall_river_discharge",
]
