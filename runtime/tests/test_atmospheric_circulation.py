"""Atmospheric circulation L1 + agent ECS batch."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.agent_ecs_batch import PACK_SIZE, pack_agents_binary, snapshot_agents_packed, unpack_agents_binary
from engine.atmospheric_circulation import circulation_snapshot, install_atmospheric_circulation
from engine.emergence_stack import wire_emergence_v2
from engine.genesis_bootstrap import bootstrap_genesis_sim
from engine.sim import Simulation, SimConfig
from engine.world_genesis import GenesisParams


def test_pack_agents_roundtrip():
    cfg = SimConfig(name="pack", seed=2, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    raw = pack_agents_binary(sim)
    assert len(raw) % PACK_SIZE == 0
    agents = unpack_agents_binary(raw)
    assert len(agents) == sim.agents.n_active


def test_circulation_with_genesis():
    cfg = SimConfig(
        name="circ",
        seed=0xABC,
        founders=6,
        max_agents=20,
        bounds_km=(0.4, 0.4),
        emergence_subsystems=True,
        wind_advect_agents=True,
    )
    sim = Simulation(cfg)
    gp = GenesisParams(seed=int(cfg.seed) & 0xFFFFFFFFFFFFFFFF, resolution=32)
    bootstrap_genesis_sim(sim, seed=cfg.seed, genesis_params=gp)
    sim.bootstrap()
    wire_emergence_v2(sim, hydrology_mode="stub", memetic=False)
    for _ in range(15):
        sim.step()
    snap = circulation_snapshot(sim)
    assert "live" in snap or snap.get("macro_climate", {}).get("installed")
    packed = snapshot_agents_packed(sim)
    assert packed["count"] >= 1
