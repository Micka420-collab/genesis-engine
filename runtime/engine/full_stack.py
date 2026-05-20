"""Wire the full Earth-realism stack on a Simulation (post-construct).

Used by ``run.py`` presets ``realism`` / ``terre`` and
``civilization_pipeline.py``.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from engine.world_genesis import GenesisParams


def wire_full_stack(
    sim,
    *,
    genesis: bool = True,
    rust_worldgraph: bool = True,
    mp_api: bool = True,
    five_cd: bool = True,
    genesis_resolution: int = 64,
) -> Dict[str, Any]:
    """Idempotent post-``Simulation()`` wiring. Returns status dict."""
    out: Dict[str, Any] = {
        "genesis_bootstrapped": False,
        "rust_worldgraph": False,
        "mp_api_records": 0,
        "five_cd": False,
    }

    if genesis:
        existing = getattr(sim, "_genesis_bootstrap_state", None)
        if existing is None:
            from engine.genesis_bootstrap import bootstrap_genesis_sim

            seed = int(sim.cfg.seed) & 0xFFFFFFFFFFFFFFFF
            gp = GenesisParams(
                seed=seed,
                resolution=genesis_resolution,
                n_plates=8,
                erosion_iters=12,
                rain_iters=3,
            )
            bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
        out["genesis_bootstrapped"] = True

    if rust_worldgraph:
        from engine.rust_worldgraph_tick import install_rust_worldgraph

        install_rust_worldgraph(sim)
        out["rust_worldgraph"] = True

    if mp_api and getattr(sim, "_materials_project", None) is not None:
        from engine.materials_project import try_fetch_mp_bootstrap

        out["mp_api_records"] = try_fetch_mp_bootstrap(sim)

    if five_cd and not getattr(sim, "_5cd_installed", False):
        try:
            from engine.sim_5cd_integration import install

            install(sim)
            sim._5cd_installed = True
            out["five_cd"] = True
        except Exception:
            out["five_cd"] = False

    return out


__all__ = ["wire_full_stack"]
