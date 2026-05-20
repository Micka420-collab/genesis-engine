"""Genesis Engine — Wave 19 macro climate propagation.

Unifies the three independent wind sources of the engine —
``engine.meteorology``, ``engine.marine`` and ``engine.wildfire`` — under
the continental-scale ``wind_u`` / ``wind_v`` field produced by
:mod:`engine.world_genesis`.

Before Wave 19, each module had its own synthetic wind model :

  - **meteorology** ``_wind_for_chunk`` — synthetic pressure gradient
    keyed by `(tick, lat_hash, sim_seed)` with a Coriolis rotation and
    altitude amplification.
  - **marine** ``_wind_for_chunk`` — synoptic-scale period (6 sim-days)
    + per-chunk deterministic phase ; sin/cos breathing.
  - **wildfire** ``tick_fire_spread`` — accepts an optional ``wind=``
    tuple from the caller, otherwise neutral 0-wind.

The three are decorrelated. A storm cell flows east in meteorology while
the ocean current beneath it drifts west, and the wildfire next door
burns into a non-existent wind. After Wave 19, all three read from the
same Hadley/Ferrel/polar circulation determined at world generation,
giving the planet ONE consistent atmosphere.

Installation
------------

``install_macro_climate(sim, anchor)`` monkey-patches the three modules
in place. Subsequent installs update the active anchor without
re-patching. ``uninstall_macro_climate(sim)`` restores the originals.

Blend parameter
---------------

``blend=1.0`` (default) -> pure macro wind. ``blend=0.0`` -> legacy
synthetic. Intermediate values lerp linearly. Useful for A/B testing
or for transitions when the anchor changes mid-simulation.

Determinism
-----------

``sample_macro_wind_at(anchor, x_m, y_m)`` is a pure bilinear lookup —
no RNG. Two sims anchored to the same world receive identical winds
at the same coordinates.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from engine.world import CHUNK_SIDE_M
from engine.world_genesis import GenesisAnchor


PIPELINE_LAYER = "Genesis-L2 Climate"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# ---------------------------------------------------------------------------
# Pure-function macro wind lookup
# ---------------------------------------------------------------------------

def sample_macro_wind_at(anchor: GenesisAnchor,
                          x_m: float, y_m: float) -> Tuple[float, float]:
    """Bilinear sample of (wind_u, wind_v) at sim coord ``(x_m, y_m)``.

    Sim coords map to macro km via ``anchor.sim_origin_macro_km``.
    Coordinates outside the macro extent clamp to the nearest border.
    Returns ``(u_ms, v_ms)`` in m/s, east- and north-positive.
    """
    world = anchor.world
    p = world.params
    R = p.resolution
    cell_km = p.map_size_km / R
    x_km = x_m / 1000.0 + anchor.sim_origin_macro_km[0]
    y_km = y_m / 1000.0 + anchor.sim_origin_macro_km[1]
    fx = float(np.clip(x_km / cell_km - 0.5, 0.0, R - 1.001))
    fy = float(np.clip(y_km / cell_km - 0.5, 0.0, R - 1.001))
    ix = int(math.floor(fx)); iy = int(math.floor(fy))
    tx = fx - ix; ty = fy - iy

    def _bil(arr: np.ndarray) -> float:
        a = float(arr[iy, ix]); b = float(arr[iy, ix + 1])
        c = float(arr[iy + 1, ix]); d = float(arr[iy + 1, ix + 1])
        return (a * (1.0 - tx) * (1.0 - ty) + b * tx * (1.0 - ty)
                + c * (1.0 - tx) * ty + d * tx * ty)

    return _bil(world.wind_u), _bil(world.wind_v)


def chunk_wind_at(anchor: GenesisAnchor,
                   coord: Tuple[int, int, int]) -> Tuple[float, float]:
    """Convenience : macro wind sampled at the centre of a chunk."""
    cx, cy, _cz = coord
    x_m = (cx + 0.5) * CHUNK_SIDE_M
    y_m = (cy + 0.5) * CHUNK_SIDE_M
    return sample_macro_wind_at(anchor, x_m, y_m)


# ---------------------------------------------------------------------------
# Per-sim state
# ---------------------------------------------------------------------------

@dataclass
class MacroClimateState:
    anchor: GenesisAnchor
    blend: float = 1.0
    chunks_winded: int = 0
    queries_total: int = 0
    modules_patched: int = 0


# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------

def install_macro_climate(sim,
                            anchor: GenesisAnchor,
                            *,
                            blend: float = 1.0
                            ) -> MacroClimateState:
    """Idempotent installer.

    Patches the three wind sources to read the macro wind field :

      - ``engine.marine._wind_for_chunk(sim, coord)`` ->
        ``sample_macro_wind_at(anchor, chunk_center)``
      - ``engine.meteorology.tick_meteorology(sim, state)`` post-pass
        overwrites every ``CellMeteorology`` wind with macro values.
      - ``engine.wildfire.tick_wildfire(sim, ..., wind=None)`` injects
        a global mean macro wind when none provided.

    Returns the per-sim :class:`MacroClimateState`. Calling install
    twice on the same sim is a no-op (returns the existing state with
    its anchor/blend updated).
    """
    existing: Optional[MacroClimateState] = getattr(
        sim, "_macro_climate_state", None)
    if existing is not None:
        existing.anchor = anchor
        existing.blend = float(blend)
        return existing

    state = MacroClimateState(anchor=anchor, blend=float(blend))
    sim._macro_climate_state = state

    # ---- marine ------------------------------------------------------------
    import engine.marine as _marine
    if getattr(_marine, "_macro_orig_wind_for_chunk", None) is None:
        _marine._macro_orig_wind_for_chunk = _marine._wind_for_chunk

        def _patched_marine_wind(sim_inner, coord):
            st: Optional[MacroClimateState] = getattr(
                sim_inner, "_macro_climate_state", None)
            if st is None:
                return _marine._macro_orig_wind_for_chunk(sim_inner, coord)
            u, v = chunk_wind_at(st.anchor, coord)
            if st.blend < 1.0:
                u0, v0 = _marine._macro_orig_wind_for_chunk(sim_inner, coord)
                u = u * st.blend + u0 * (1.0 - st.blend)
                v = v * st.blend + v0 * (1.0 - st.blend)
            st.queries_total += 1
            return float(u), float(v)

        _marine._wind_for_chunk = _patched_marine_wind
        state.modules_patched += 1

    # ---- meteorology -------------------------------------------------------
    import engine.meteorology as _meteo
    if getattr(_meteo, "_macro_orig_tick_meteorology", None) is None:
        _meteo._macro_orig_tick_meteorology = _meteo.tick_meteorology

        def _patched_tick_meteo(sim_inner, meteo_state):
            _meteo._macro_orig_tick_meteorology(sim_inner, meteo_state)
            st: Optional[MacroClimateState] = getattr(
                sim_inner, "_macro_climate_state", None)
            if st is None:
                return
            for coord, cell in meteo_state.chunk_meteo.items():
                u_macro, v_macro = chunk_wind_at(st.anchor, coord)
                if st.blend < 1.0:
                    u = u_macro * st.blend + cell.wind_u_ms * (1.0 - st.blend)
                    v = v_macro * st.blend + cell.wind_v_ms * (1.0 - st.blend)
                else:
                    u, v = u_macro, v_macro
                cell.wind_u_ms = float(u)
                cell.wind_v_ms = float(v)
                cell.wind_speed_ms = float(math.hypot(u, v))
                st.chunks_winded += 1
                st.queries_total += 1

        _meteo.tick_meteorology = _patched_tick_meteo
        state.modules_patched += 1

    # ---- wildfire ----------------------------------------------------------
    import engine.wildfire as _wf
    if getattr(_wf, "_macro_orig_tick_wildfire", None) is None:
        _wf._macro_orig_tick_wildfire = _wf.tick_wildfire

        def _patched_tick_wildfire(sim_inner, *, storm_factor=1.0, wind=None):
            st: Optional[MacroClimateState] = getattr(
                sim_inner, "_macro_climate_state", None)
            if st is None or wind is not None:
                return _wf._macro_orig_tick_wildfire(
                    sim_inner, storm_factor=storm_factor, wind=wind)
            # Inject mean macro wind across cached chunks.
            us = []; vs = []
            for coord, _ch in sim_inner.streamer.cache.items():
                u, v = chunk_wind_at(st.anchor, coord)
                us.append(u); vs.append(v)
            if us:
                mean_wind = (sum(us) / len(us), sum(vs) / len(vs))
                st.queries_total += len(us)
            else:
                mean_wind = None
            return _wf._macro_orig_tick_wildfire(
                sim_inner, storm_factor=storm_factor, wind=mean_wind)

        _wf.tick_wildfire = _patched_tick_wildfire
        state.modules_patched += 1

    return state


def uninstall_macro_climate(sim) -> bool:
    """Detach the macro wind from all three modules. Restores originals.

    Returns ``True`` if anything was uninstalled.
    """
    state = getattr(sim, "_macro_climate_state", None)
    if state is None:
        return False

    import engine.marine as _marine
    import engine.meteorology as _meteo
    import engine.wildfire as _wf

    orig = getattr(_marine, "_macro_orig_wind_for_chunk", None)
    if orig is not None:
        _marine._wind_for_chunk = orig
        _marine._macro_orig_wind_for_chunk = None

    orig = getattr(_meteo, "_macro_orig_tick_meteorology", None)
    if orig is not None:
        _meteo.tick_meteorology = orig
        _meteo._macro_orig_tick_meteorology = None

    orig = getattr(_wf, "_macro_orig_tick_wildfire", None)
    if orig is not None:
        _wf.tick_wildfire = orig
        _wf._macro_orig_tick_wildfire = None

    del sim._macro_climate_state
    return True


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def macro_climate_state(sim) -> Dict[str, object]:
    state: Optional[MacroClimateState] = getattr(
        sim, "_macro_climate_state", None)
    if state is None:
        return {"installed": False}
    return {
        "installed": True,
        "blend": state.blend,
        "chunks_winded": state.chunks_winded,
        "queries_total": state.queries_total,
        "modules_patched": state.modules_patched,
    }
