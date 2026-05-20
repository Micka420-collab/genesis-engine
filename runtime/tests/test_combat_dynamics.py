"""Combat dynamics — weapons, install, state."""
from __future__ import annotations

import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.combat_dynamics import (
    WeaponKind,
    combat_state,
    install_combat_dynamics,
    unarmed_profile,
)
from engine.sim import Simulation, SimConfig


def test_unarmed_profile_positive_damage():
    p = unarmed_profile()
    assert p.base_damage > 0
    assert p.kind == int(WeaponKind.UNARMED)


def test_install_combat_state():
    cfg = SimConfig(name="combat", seed=32, founders=4, max_agents=12, bounds_km=(0.2, 0.2))
    sim = Simulation(cfg)
    sim.bootstrap()
    st = install_combat_dynamics(sim)
    assert st is not None
    st2 = install_combat_dynamics(sim)
    assert st2 is st
    for _ in range(3):
        sim.step()
    snap = combat_state(sim)
    assert isinstance(snap, dict)
