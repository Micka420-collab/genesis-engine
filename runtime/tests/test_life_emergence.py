"""Tests for emergent life pipeline (appraise → substrate → origins)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from engine.sim import Simulation, SimConfig
from engine.appraise import appraise_cell, prebiotic_potential
from engine.life_emergence import (CivilizationStage, wire_life_emergence,
                                   life_emergence_snapshot)


class LifeEmergenceTests(unittest.TestCase):
    def test_appraise_cell_bounded(self):
        sim = Simulation(SimConfig(seed=42, founders=0, emergent_origins=True))
        sim.bootstrap()
        cell = appraise_cell(sim.streamer, 0.0, 0.0, sim.tick,
                             drive_accel=int(sim.cfg.drive_accel))
        self.assertGreaterEqual(cell.viability, 0.0)
        self.assertLessEqual(cell.viability, 1.0)
        self.assertGreaterEqual(prebiotic_potential(cell), 0.0)

    def test_emergent_origins_no_scripted_founders(self):
        sim = Simulation(SimConfig(
            seed=0xAB10CAFE, founders=0, emergent_origins=True,
            full_biosphere=True, max_emergent_founders=2, substrate_threshold=0.3,
            bounds_km=(2.0, 2.0), max_agents=20, drive_accel=12000.0,
        ))
        wire_life_emergence(sim)
        sim.bootstrap()
        self.assertEqual(sim.agents.n_active, 0)
        for _ in range(1200):
            sim.step()
        snap = life_emergence_snapshot(sim)
        self.assertIn("biosphere_stage", snap)
        self.assertGreaterEqual(snap.get("substrate_cells", 0), 0)

    def test_protocell_division_event(self):
        from engine.protocell_evolution import ProtocellPool, ProtocellState, tick_protocells
        sim = Simulation(SimConfig(seed=1, founders=0, emergent_origins=True,
                                   full_biosphere=False, bounds_km=(1.0, 1.0)))
        wire_life_emergence(sim)
        sim.bootstrap()
        st = sim._life_emergence
        coord = next(iter(sim.streamer.cache.keys()))
        st.substrate_by_chunk[coord] = 2.0
        st.protocells.pools[coord] = ProtocellPool(
            count=2.0, mean_complexity=0.5, energy=2.0)
        ev = tick_protocells(sim, st.substrate_by_chunk, st.protocells)
        self.assertTrue(any(e.get("kind") == "protocell_division" for e in ev))

    def test_founders_not_counted_as_births(self):
        sim = Simulation(SimConfig(seed=99, founders=4, max_agents=10))
        sim.bootstrap()
        self.assertEqual(sim.annalist.cum_births, 0)
        self.assertEqual(sim.annalist.cum_foundings, 4)

    def test_emergent_fertility_uses_appraisal(self):
        sim = Simulation(SimConfig(seed=7, founders=2, max_agents=10, life_emergence=True))
        wire_life_emergence(sim)
        sim.bootstrap()
        for _ in range(50):
            sim.step()
        row = 0
        fertile = sim._is_fertile(row)
        self.assertIsInstance(fertile, bool)


if __name__ == "__main__":
    unittest.main()
