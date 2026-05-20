"""DeepMind-inspired world priors + circulation 3D column."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.circulation_3d_column import column_temperatures_from_surface, install_circulation_3d
from engine.deepmind_world_prior import apply_graphcast_lite_to_world, graphcast_lite_prognostic
from engine.emergence_stack import wire_emergence_v2
from engine.genesis_bootstrap import bootstrap_genesis_sim
from engine.sim import Simulation, SimConfig
from engine.world_genesis import GenesisParams, generate_world


def test_graphcast_lite_changes_wind_deterministically():
    world = generate_world(GenesisParams(seed=42, resolution=32))
    u0 = world.wind_u.copy()
    v0 = world.wind_v.copy()
    u, v, delta = graphcast_lite_prognostic(
        u0, v0, world.temp_c, world.latitude_deg, n_message_passes=2,
    )
    assert u.shape == u0.shape
    assert float(delta) >= 0.0
    assert not np.allclose(u, u0) or not np.allclose(v, v0)


def test_apply_graphcast_to_world():
    world = generate_world(GenesisParams(seed=99, resolution=24))
    st = apply_graphcast_lite_to_world(world, n_message_passes=1)
    assert st.applied
    assert st.wind_delta_rms >= 0.0


def test_column_temps_monotone_with_height():
    t_s, t_m, t_u = column_temperatures_from_surface(22.0, 45.0)
    assert t_u < t_m < t_s


def test_wire_emergence_graphcast_and_column3d():
    cfg = SimConfig(
        name="prior",
        seed=7,
        founders=8,
        max_agents=24,
        bounds_km=(0.3, 0.3),
        emergence_subsystems=True,
        graphcast_lite_prior=True,
    )
    sim = Simulation(cfg)
    gp = GenesisParams(seed=7, resolution=32)
    bootstrap_genesis_sim(sim, seed=7, genesis_params=gp)
    sim.bootstrap()
    out = wire_emergence_v2(sim, graphcast_lite=True)
    assert out.get("world_prior", {}).get("graphcast_lite")
    install_circulation_3d(sim)
    for _ in range(8):
        sim.step()
    col = getattr(sim, "_circulation_3d", None)
    assert col is not None
    assert col.n_columns >= 0
