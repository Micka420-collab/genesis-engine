"""Tests fonctionnels — biosphère émergente (origins)."""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from engine.life_emergence import life_emergence_snapshot, wire_life_emergence
from engine.sim import Simulation, SimConfig


class BiosphereFunctionalTests(unittest.TestCase):
    def test_origins_500_ticks_no_crash(self):
        """Mode origins : 0 fondateurs, stack biosphère, pas d'exception."""
        sim = Simulation(SimConfig(
            name="origins_func",
            seed=0x0B1601FE,
            founders=0,
            emergent_origins=True,
            full_biosphere=True,
            max_agents=30,
            bounds_km=(1.5, 1.5),
            drive_accel=15000.0,
        ))
        wire_life_emergence(sim)
        sim.bootstrap()
        self.assertEqual(sim.agents.n_active, 0)
        for _ in range(500):
            sim.step()
        snap = life_emergence_snapshot(sim)
        self.assertIn(snap.get("biosphere_stage"), (
            "void", "prebiotic", "protocell", "microbe", "flora", "fauna", "sapient",
        ))
        self.assertGreater(snap.get("substrate_cells", 0), 0)

    def test_substrate_and_protocell_progression(self):
        """Après 1500 ticks, substrat ou protocellules doivent exister."""
        sim = Simulation(SimConfig(
            seed=0xDEADBEEF,
            founders=0,
            emergent_origins=True,
            full_biosphere=True,
            max_agents=20,
            bounds_km=(2.0, 2.0),
            drive_accel=12000.0,
        ))
        wire_life_emergence(sim)
        sim.bootstrap()
        for _ in range(1500):
            sim.step()
        snap = life_emergence_snapshot(sim)
        proto = float(snap.get("total_protocells", 0))
        sub_max = float(snap.get("substrate_max", 0))
        self.assertTrue(
            proto > 0 or sub_max > 0.1,
            f"expected substrate or protocells; snap={snap}",
        )

    def test_classic_founders_with_life_emergence(self):
        """Mode classique (4 fondateurs) + life_emergence reste stable."""
        sim = Simulation(SimConfig(
            founders=4, max_agents=12, bounds_km=(0.5, 0.5), drive_accel=3000.0,
        ))
        wire_life_emergence(sim)
        for _ in range(30):
            sim.step()
        self.assertGreaterEqual(sim.stats.alive, 1)
        self.assertEqual(sim.annalist.cum_foundings, 4)
        self.assertEqual(sim.annalist.cum_births, 0)


if __name__ == "__main__":
    unittest.main()
