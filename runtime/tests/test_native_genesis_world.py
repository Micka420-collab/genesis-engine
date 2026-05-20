"""Optional smoke for maturin-built ``genesis_world`` (skipped if not installed)."""
from __future__ import annotations

import pytest

pytest.importorskip("genesis_world", reason="run: cd native/world-engine/crates/pybindings && maturin develop")

import genesis_world as gw  # noqa: E402

from engine.genesis_bootstrap import bootstrap_genesis_sim
from engine.macro_grid_export import export_macro_grid_bytes
from engine.sim import Simulation, SimConfig
from engine.world_genesis import GenesisParams


@pytest.mark.native
def test_pyworld_macro_and_mutation():
    sim = Simulation(SimConfig(seed=0xFACE, founders=2, max_agents=8))
    st = bootstrap_genesis_sim(
        sim, genesis_params=GenesisParams(seed=0xFACE, resolution=16)
    )
    w = gw.PyWorld(
        seed=0xFACE,
        macro_grid_bytes=export_macro_grid_bytes(st.world),
        chunk_side_m=32.0,
        erosion_passes=0,
        erosion_droplets=8,
    )
    obs = w.observe_chunk(0, 0)
    assert len(obs["elevation"]) == 64 * 64
    w.set_voxel(1, 1, 2, 2)  # Material::Stone
    assert w.apply_pending() == 1
    snap = w.save_snapshot()
    assert len(snap) > 32
    m1 = w.extract_mesh(0, 0, 1)
    m2 = w.extract_mesh(0, 0, 1)
    assert m2.get("cached") is True
    w.restore_snapshot(snap)
