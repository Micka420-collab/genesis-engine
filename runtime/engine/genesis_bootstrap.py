"""Genesis Engine — attach continental world substrate to a Simulation.

Chains Waves 16-19 (and future 20-22) under a single ``bootstrap_genesis_sim(sim, ...)``
call. This wires world modules into the sim streamer — effects then emerge from
``sim.step()``, not from external batch jobs. Replaces the verbose 7-line pattern :

Before (Wave 16-19 manual)::

    world = generate_world(GenesisParams(seed=0xCAFE, resolution=128))
    anchor = make_anchor(world)
    sim.streamer.set_genesis(anchor); sim.streamer.clear_cache()
    install_geology(sim)
    install_tectonic_overlay(sim, anchor)
    install_chunk_hydrology(sim, anchor)
    install_meteorology(sim)
    install_marine(sim)
    install_wildfire(sim)
    install_macro_climate(sim, anchor)

After (Wave 16-19 bootstrapped)::

    state = bootstrap_genesis_sim(sim, seed=0xCAFE)

The bootstrap is :

  - **Composable** : ``modules=`` lets you select which subsystems to wire
    (e.g. ``modules={'geology', 'hydrology'}`` to skip climate).
  - **Idempotent** : calling twice on the same sim returns the same state.
  - **Read-only on GenesisWorld** : the world is created once at install
    and never mutated afterwards.
  - **Deterministic** : same seed → bit-identical world + same install order.

When Waves 20-22 ship, they integrate here by registering optional
modules (climate_biome, marine_bathymetry, world_genesis_global). The
bootstrap function auto-detects their presence at import time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple

from engine.world_genesis import (GenesisParams, GenesisWorld, GenesisAnchor,
                                    generate_world, make_anchor)


# Module identifiers (kept stable across waves).
MOD_GENESIS = "genesis"          # Wave 16  — generate_world + anchor + streamer wire
MOD_GEOLOGY = "geology"          # Wave 10 + 17 — install_geology + tectonic overlay
MOD_HYDROLOGY = "hydrology"      # Wave 18 — chunk_hydrology
MOD_METEOROLOGY = "meteorology"  # base meteorology
MOD_MARINE = "marine"            # base marine
MOD_WILDFIRE = "wildfire"        # base wildfire
MOD_CLIMATE = "climate"          # Wave 19 — macro_climate (unifies 3 wind sources)
# Reserved for Waves 20-22 (loaded if available at runtime)
MOD_CLIMATE_BIOME = "climate_biome"      # Wave 20
MOD_MARINE_BATHYMETRY = "bathymetry"     # Wave 21
MOD_GLOBAL_GENESIS = "global_genesis"    # Wave 22


_DEFAULT_MODULES: Set[str] = {
    MOD_GENESIS, MOD_GEOLOGY, MOD_HYDROLOGY,
    MOD_METEOROLOGY, MOD_MARINE, MOD_WILDFIRE, MOD_CLIMATE,
}


@dataclass
class BootstrapState:
    """State returned by :func:`bootstrap_genesis_sim`."""
    world: GenesisWorld
    anchor: GenesisAnchor
    modules_installed: Set[str] = field(default_factory=set)
    modules_skipped: Dict[str, str] = field(default_factory=dict)  # name -> reason
    sub_states: Dict[str, object] = field(default_factory=dict)    # raw state objects

    def __repr__(self) -> str:
        return (f"BootstrapState(installed={sorted(self.modules_installed)}, "
                f"skipped={list(self.modules_skipped.keys())})")


def bootstrap_genesis_sim(sim,
                            *,
                            seed: Optional[int] = None,
                            world: Optional[GenesisWorld] = None,
                            anchor: Optional[GenesisAnchor] = None,
                            genesis_params: Optional[GenesisParams] = None,
                            sim_origin_macro_km: Optional[Tuple[float, float]] = None,
                            modules: Optional[Set[str]] = None,
                            ) -> BootstrapState:
    """Wire all Genesis Wave 16-19+ subsystems into ``sim`` in one call.

    Parameters
    ----------
    sim
        A constructed :class:`engine.sim.Simulation`. Its ``cfg.seed`` is
        the default seed for the genesis world.
    seed
        Override the macro seed. Defaults to ``sim.cfg.seed``.
    world
        Pre-built :class:`GenesisWorld` (skip generation). Use to share
        a world across sims (Wave 22 future hook).
    anchor
        Pre-built :class:`GenesisAnchor`. Implies ``world`` is provided.
    genesis_params
        Override default :class:`GenesisParams` (size, resolution,
        n_plates, etc.). Ignored if ``world`` is provided.
    sim_origin_macro_km
        Macro coordinate to anchor the sim at. Defaults to the macro
        centre (via :func:`make_anchor`).
    modules
        Subset of subsystems to install. Defaults to :data:`_DEFAULT_MODULES`.
        Use a smaller set for tests.

    Returns
    -------
    BootstrapState
        ``world`` and ``anchor`` references + ``modules_installed`` set
        + ``sub_states`` dict for direct access to each subsystem's state.

    Idempotent. Calling twice on the same sim returns the same state.
    """
    existing = getattr(sim, "_genesis_bootstrap_state", None)
    if existing is not None:
        return existing

    if anchor is not None and world is None:
        world = anchor.world

    if world is None:
        params = genesis_params or GenesisParams(
            seed=seed if seed is not None else int(sim.cfg.seed))
        # Force the seed if both seed= and genesis_params= are provided.
        if seed is not None and (genesis_params is None or
                                  genesis_params.seed != seed):
            params = GenesisParams(
                seed=seed,
                map_size_km=params.map_size_km,
                resolution=params.resolution,
                n_plates=params.n_plates,
                oceanic_fraction=params.oceanic_fraction,
                sea_level_m=params.sea_level_m,
                max_elev_m=params.max_elev_m,
                abyssal_depth_m=params.abyssal_depth_m,
                continent_base_m=params.continent_base_m,
                erosion_iters=params.erosion_iters,
                erodibility_k=params.erodibility_k,
                erosion_m=params.erosion_m,
                erosion_n=params.erosion_n,
                erosion_dt_myr=params.erosion_dt_myr,
                uplift_per_myr_max=params.uplift_per_myr_max,
                fbm_continent_km=params.fbm_continent_km,
                fbm_region_km=params.fbm_region_km,
                fbm_hills_km=params.fbm_hills_km,
                fbm_amp_continent_m=params.fbm_amp_continent_m,
                fbm_amp_region_m=params.fbm_amp_region_m,
                fbm_amp_hills_m=params.fbm_amp_hills_m,
                rain_iters=params.rain_iters,
                orographic_gain=params.orographic_gain,
                rain_shadow_decay=params.rain_shadow_decay,
                base_precip_mm=params.base_precip_mm,
                equator_y_frac=params.equator_y_frac,
                lat_span_deg=params.lat_span_deg,
                river_threshold_cells=params.river_threshold_cells,
                continentality_km=params.continentality_km,
            )
        world = generate_world(params)

    if anchor is None:
        anchor = make_anchor(
            world, sim_origin_macro_km=sim_origin_macro_km)

    selected = set(modules) if modules is not None else set(_DEFAULT_MODULES)
    state = BootstrapState(world=world, anchor=anchor)
    sim._genesis_bootstrap_state = state

    # ---- Genesis anchor → streamer ----------------------------------------
    if MOD_GENESIS in selected:
        sim.streamer.set_genesis(anchor)
        sim.streamer.clear_cache()
        state.modules_installed.add(MOD_GENESIS)

    # ---- Geology (Wave 10 base + Wave 17 tectonic overlay) -----------------
    if MOD_GEOLOGY in selected:
        try:
            from engine.geology import install_geology
            from engine.tectonic_geology import install_tectonic_overlay
            geo_st = install_geology(sim)
            tec_st = install_tectonic_overlay(sim, anchor)
            state.sub_states["geology"] = geo_st
            state.sub_states["tectonic_geology"] = tec_st
            state.modules_installed.add(MOD_GEOLOGY)
        except Exception as e:
            state.modules_skipped[MOD_GEOLOGY] = repr(e)

    # ---- Chunk hydrology (Wave 18) ----------------------------------------
    if MOD_HYDROLOGY in selected:
        try:
            from engine.chunk_hydrology import install_chunk_hydrology
            hyd_st = install_chunk_hydrology(sim, anchor)
            state.sub_states["chunk_hydrology"] = hyd_st
            state.modules_installed.add(MOD_HYDROLOGY)
        except Exception as e:
            state.modules_skipped[MOD_HYDROLOGY] = repr(e)

    # ---- Meteorology + marine + wildfire (base) ---------------------------
    if MOD_METEOROLOGY in selected:
        try:
            from engine.meteorology import install_meteorology
            met_st = install_meteorology(sim)
            state.sub_states["meteorology"] = met_st
            state.modules_installed.add(MOD_METEOROLOGY)
        except Exception as e:
            state.modules_skipped[MOD_METEOROLOGY] = repr(e)

    if MOD_MARINE in selected:
        try:
            from engine.marine import install_marine
            mar_st = install_marine(sim)
            state.sub_states["marine"] = mar_st
            state.modules_installed.add(MOD_MARINE)
        except Exception as e:
            state.modules_skipped[MOD_MARINE] = repr(e)

    if MOD_WILDFIRE in selected:
        try:
            from engine.wildfire import install_wildfire
            wf_st = install_wildfire(sim)
            state.sub_states["wildfire"] = wf_st
            state.modules_installed.add(MOD_WILDFIRE)
        except Exception as e:
            state.modules_skipped[MOD_WILDFIRE] = repr(e)

    # ---- Macro climate (Wave 19, unifies 3 wind sources) ------------------
    if MOD_CLIMATE in selected:
        try:
            from engine.macro_climate import install_macro_climate
            clim_st = install_macro_climate(sim, anchor)
            state.sub_states["macro_climate"] = clim_st
            state.modules_installed.add(MOD_CLIMATE)
        except Exception as e:
            state.modules_skipped[MOD_CLIMATE] = repr(e)

    # ---- Optional Wave 20 — climate_biome (loaded if module exists) -------
    if MOD_CLIMATE_BIOME in selected:
        try:
            from engine.climate_biome import install_climate_biome
            cb_st = install_climate_biome(sim, anchor)
            state.sub_states["climate_biome"] = cb_st
            state.modules_installed.add(MOD_CLIMATE_BIOME)
        except ImportError:
            state.modules_skipped[MOD_CLIMATE_BIOME] = "not yet implemented"
        except Exception as e:
            state.modules_skipped[MOD_CLIMATE_BIOME] = repr(e)

    # ---- Optional Wave 21 — marine_bathymetry -----------------------------
    if MOD_MARINE_BATHYMETRY in selected:
        try:
            from engine.marine_bathymetry import install_marine_bathymetry
            mb_st = install_marine_bathymetry(sim, anchor)
            state.sub_states["marine_bathymetry"] = mb_st
            state.modules_installed.add(MOD_MARINE_BATHYMETRY)
        except ImportError:
            state.modules_skipped[MOD_MARINE_BATHYMETRY] = "not yet implemented"
        except Exception as e:
            state.modules_skipped[MOD_MARINE_BATHYMETRY] = repr(e)

    # ---- Optional Wave 22 — global_genesis is opt-in, not default ---------
    # Use engine.world_genesis_global directly when running multi-region.

    return state


def bootstrap_state(sim) -> Optional[BootstrapState]:
    """Return the :class:`BootstrapState` attached to ``sim``, or None."""
    return getattr(sim, "_genesis_bootstrap_state", None)


def resolve_genesis_world(sim, *, synthetic_only: bool = False):
    """Return the :class:`GenesisWorld` wired into ``sim``.

  Used by civilization pipeline exports (Köppen FAIR, renders). When
  ``synthetic_only`` is False and no bootstrap ran, raises — no silent
  fake macro grid.
    """
    if synthetic_only:
        return None
    state = bootstrap_state(sim)
    if state is None or not hasattr(state, "world"):
        raise RuntimeError(
            "Genesis world missing on sim — call bootstrap_genesis_sim() first "
            "(civilization pipeline requires emergent substrate, not synthetic-only)."
        )
    return state.world


def resolve_genesis_anchor(sim, *, synthetic_only: bool = False) -> Optional[GenesisAnchor]:
    """Return the :class:`GenesisAnchor` on ``sim`` (bootstrap or streamer)."""
    if synthetic_only:
        return None
    state = bootstrap_state(sim)
    if state is not None and hasattr(state, "anchor"):
        return state.anchor
    anchor = getattr(getattr(sim, "streamer", None), "genesis", None)
    if anchor is None:
        raise RuntimeError(
            "Genesis anchor missing on sim — call bootstrap_genesis_sim() first."
        )
    return anchor


# Convenience set re-export so callers can pass `modules=ALL_MODULES` etc.
ALL_MODULES: Set[str] = set(_DEFAULT_MODULES) | {
    MOD_CLIMATE_BIOME, MOD_MARINE_BATHYMETRY,
}

MINIMAL_MODULES: Set[str] = {MOD_GENESIS, MOD_GEOLOGY, MOD_HYDROLOGY}
"""Just the substrate (no climate). Useful for fast tests."""

CLIMATE_MODULES: Set[str] = {MOD_GENESIS, MOD_METEOROLOGY, MOD_MARINE,
                              MOD_WILDFIRE, MOD_CLIMATE}
"""Just the climate stack."""
