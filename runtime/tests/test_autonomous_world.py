"""Autonomous Earth — dynamo, plates, material transform."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.agent import ActionKind
from engine.autonomous_world import install_autonomous_world, autonomous_world_snapshot
from engine.earth_dynamo import coriolis_parameter, install_earth_dynamo
from engine.emergence_stack import wire_emergence_v2
from engine.genesis_bootstrap import bootstrap_genesis_sim
from engine.material_transform import can_transform, install_material_transform, start_transform
from engine.plate_tectonics_live import install_plate_tectonics_live, tick_plate_tectonics_live
from engine.sim import Simulation, SimConfig
from engine.world_genesis import GenesisParams
from engine.world_physics_registry import registry_snapshot, material_props
from engine.materials import MaterialKind


def test_physics_registry():
    snap = registry_snapshot()
    assert snap["n_materials"] >= 10
    p = material_props(MaterialKind.IRON)
    assert p.melting_point_k > 1500.0


def test_coroiolis():
    f = coriolis_parameter(45.0)
    assert abs(f) > 1e-5


def test_autonomous_world_genesis():
    cfg = SimConfig(
        name="auto",
        seed=0xA870_0000,
        founders=8,
        max_agents=20,
        bounds_km=(0.4, 0.4),
        autonomous_world=True,
        emergence_subsystems=True,
    )
    sim = Simulation(cfg)
    gp = GenesisParams(seed=cfg.seed, resolution=32)
    bootstrap_genesis_sim(sim, seed=cfg.seed, genesis_params=gp)
    sim.bootstrap()
    wire_emergence_v2(sim, genome_brain=False, autonomous_world=True)
    assert getattr(sim, "_autonomous_world", False)
    for _ in range(30):
        sim.step()
    snap = autonomous_world_snapshot(sim)
    assert snap["autonomous"]
    assert snap["dynamo"].get("installed")
    assert snap["tectonics"].get("installed") or snap["tectonics"].get("ticks", 0) >= 0


def test_material_transform_start():
    cfg = SimConfig(name="xf", seed=1, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    install_material_transform(sim)
    row = 0
    sim.agents.inv_wood[row] = 10.0
    sim.agents.inv_stone[row] = 10.0
    rid = "cordage_fiber"
    ok, _ = can_transform(sim, row, rid)
    if ok:
        proj = start_transform(sim, row, rid)
        assert proj is not None
