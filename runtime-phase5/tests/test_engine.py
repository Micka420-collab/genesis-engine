"""Smoke + regression tests for the operational engine (Phase 5)."""
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from engine.core import derive_agent_id, prf_rng
from engine.world import (Biome, _stable_bytes_sig, _stable_layer_salt,
                          classify_biome, generate_chunk, TerrainParams)
from engine.sim import Simulation, SimConfig
from engine.cognition import _jitter_target


class DeterminismTests(unittest.TestCase):
    def test_agent_id_deterministic(self):
        a = derive_agent_id(42, ["x"], [1])
        b = derive_agent_id(42, ["x"], [1])
        self.assertEqual(a, b)

    def test_agent_id_differs_with_index(self):
        a = derive_agent_id(42, ["x"], [1])
        b = derive_agent_id(42, ["x"], [2])
        self.assertNotEqual(a, b)

    def test_prf_deterministic(self):
        r1 = prf_rng(123, ["test"], [7]).random(10)
        r2 = prf_rng(123, ["test"], [7]).random(10)
        self.assertTrue((r1 == r2).all())

    def test_chunk_deterministic(self):
        p = TerrainParams()
        c1 = generate_chunk(0xCAFE, (1, 2, 0), p)
        c2 = generate_chunk(0xCAFE, (1, 2, 0), p)
        self.assertEqual(c1.content_root, c2.content_root)

    def test_stable_layer_salt_is_process_invariant(self):
        a = _stable_layer_salt(0xCAFE, "elev")
        b = _stable_layer_salt(0xCAFE, "elev")
        self.assertEqual(a, b)
        self.assertNotEqual(_stable_layer_salt(0xCAFE, "elev"),
                            _stable_layer_salt(0xCAFE, "precip"))
        self.assertNotEqual(_stable_layer_salt(0xCAFE, "elev"),
                            _stable_layer_salt(0xCAFF, "elev"))

    def test_world_deterministic_across_hashseed(self):
        ref = generate_chunk(0xCAFE, (5, 5, 0), TerrainParams())
        ref_h = float(ref.height[10, 10])
        runtime = os.path.abspath(os.path.join(HERE, ".."))
        script = (
            "import sys; sys.path.insert(0, " + repr(runtime) + "); "
            "from engine.world import generate_chunk, TerrainParams; "
            "c = generate_chunk(0xCAFE, (5, 5, 0), TerrainParams()); "
            "print(float(c.height[10, 10]))"
        )
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = "random"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run([sys.executable, "-B", "-c", script],
                              env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        child_h = float(proc.stdout.strip())
        self.assertAlmostEqual(ref_h, child_h, places=4)

    def test_stable_bytes_sig(self):
        import numpy as np
        a = _stable_bytes_sig(np.array([0.1, 0.2, 0.3], dtype=np.float32).tobytes())
        b = _stable_bytes_sig(np.array([0.1, 0.2, 0.3], dtype=np.float32).tobytes())
        c = _stable_bytes_sig(np.array([0.1, 0.2, 0.4], dtype=np.float32).tobytes())
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertGreaterEqual(a, 0)
        self.assertLess(a, 1 << 32)


class WorldTests(unittest.TestCase):
    def test_biome_classification_basic(self):
        self.assertEqual(classify_biome(0, 0, -10), Biome.OCEAN)
        self.assertEqual(classify_biome(25, 3000, 100), Biome.TROPICAL_RAINFOREST)
        self.assertEqual(classify_biome(-20, 100, 100), Biome.ICE)
        self.assertEqual(classify_biome(5, 100, 100), Biome.COLD_DESERT)


class CognitionTests(unittest.TestCase):
    def test_jitter_target_deterministic_and_bounded(self):
        x1, y1 = _jitter_target(42, 100.0, 50.0, 1)
        x2, y2 = _jitter_target(42, 100.0, 50.0, 1)
        self.assertAlmostEqual(x1, x2)
        self.assertAlmostEqual(y1, y2)
        self.assertLess(abs(x1 - 100.0), 0.5)
        self.assertLess(abs(y1 - 50.0), 0.5)
        x3, y3 = _jitter_target(43, 100.0, 50.0, 1)
        self.assertFalse(x1 == x3 and y1 == y3)


class SimTests(unittest.TestCase):
    def test_short_run_no_crash(self):
        cfg = SimConfig(founders=4, max_agents=20, bounds_km=(0.4, 0.4), drive_accel=2000.0)
        sim = Simulation(cfg)
        for _ in range(20):
            sim.step()
        self.assertGreaterEqual(sim.stats.alive, 0)
        self.assertGreaterEqual(sim.stats.cum_births, cfg.founders)
        sim.annalist.close()

    def test_replay_equivalent(self):
        cfg = SimConfig(founders=4, max_agents=20, bounds_km=(0.4, 0.4), drive_accel=2000.0)
        s1 = Simulation(cfg)
        s2 = Simulation(cfg)
        for _ in range(10):
            s1.step()
            s2.step()
        for r in range(s1.agents.n_active):
            if s1.agents.generation[r] == 0:
                self.assertEqual(s1.agents.uuid[r], s2.agents.uuid[r])
        s1.annalist.close()
        s2.annalist.close()

    def test_share_fires_under_stockpile_conditions(self):
        """Phase 5 calibration regression: SHARE must fire when stockpiles
        exist and recipients are hungry.  The Phase 4 audit reported 0
        shares across all four reference experiments."""
        cfg = SimConfig(name="share_calibration", seed=0xBEEF, founders=20,
                        max_agents=80, bounds_km=(0.4, 0.4), spawn_radius_m=60.0,
                        cultures=1, drive_accel=2000.0)
        sim = Simulation(cfg)
        sim.bootstrap()
        n = sim.agents.n_active
        sim.agents.agreeableness[:n] = 0.85
        # Hunger 0.62: above the mating branch's 0.6 cap (so MATE doesn't
        # preempt SHARE) but below 0.85 (so the critical-drive branch is off).
        sim.agents.hunger[:n] = 0.62
        sim.agents.inv_food[:n] = 0.4
        # Pair providers next to recipients within SOCIAL_TALK_RADIUS_M (3.5 m)
        for i in range(0, n - 1, 2):
            sim.agents.pos[i + 1, 0] = sim.agents.pos[i, 0] + 1.0
            sim.agents.pos[i + 1, 1] = sim.agents.pos[i, 1]
        # Drive the simulator a few ticks, replenishing the conditions each
        # tick so the EAT path doesn't drain stockpiles before SHARE fires.
        for _ in range(5):
            sim.step()
            sim.agents.inv_food[:n] = 0.4
            sim.agents.hunger[:n] = 0.62
        m = sim.annalist.metrics_to_dict()
        self.assertGreater(m["shares_cum"][-1], 0,
                           msg=f"SHARE never fired; cum_shares={m['shares_cum'][-1]}")
        sim.annalist.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
