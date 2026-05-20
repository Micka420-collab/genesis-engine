"""Fast integration-style unit tests (genesis bootstrap, hydrology, knowledge wiring)."""
from __future__ import annotations

import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from engine.architecture_layer import install_architecture_layer
from engine.chunk_hydrology import (
    cross_chunk_flow_stub,
    cross_chunk_saint_venant_1d,
)
from engine.genesis_bootstrap import MOD_GENESIS, bootstrap_genesis_sim, bootstrap_state
from engine.knowledge_wiring import wire_knowledge_cognition
from engine.sim import Simulation, SimConfig
from engine.world import TerrainParams, generate_chunk
from engine.world_genesis import GenesisParams


class IntegrationRiskyTests(unittest.TestCase):
    def test_genesis_bootstrap_idempotent(self):
        """Calling bootstrap twice yields identical state; streamer carries genesis."""
        gp = GenesisParams(
            seed=0xACE,
            map_size_km=96.0,
            resolution=16,
            erosion_iters=2,
            rain_iters=2,
            n_plates=4,
        )
        sim = Simulation(
            SimConfig(
                seed=gp.seed,
                founders=2,
                max_agents=8,
                bounds_km=(0.12, 0.12),
                life_emergence=False,
                epidemic_observer=False,
                emergence_subsystems=False,
            )
        )
        st1 = bootstrap_genesis_sim(
            sim, genesis_params=gp, modules={MOD_GENESIS}
        )
        st2 = bootstrap_genesis_sim(
            sim, genesis_params=gp, modules={MOD_GENESIS}
        )
        self.assertIs(st1, st2)
        self.assertIsNotNone(getattr(sim.streamer, "genesis", None))
        b = bootstrap_state(sim)
        self.assertIsNotNone(b)
        self.assertIs(sim.streamer.genesis, b.anchor)

    def test_hydrology_stub_moves_water(self):
        """``cross_chunk_flow_stub`` redistributes water across an east boundary."""
        p = TerrainParams()
        seed = 0xD00D
        chunk_a = generate_chunk(seed, (0, 0, 0), p)
        chunk_b = generate_chunk(seed, (1, 0, 0), p)
        chunk_a.water[:, -1] = 400.0
        chunk_b.water[:, 0] = 20.0
        strip_before_a = float(chunk_a.water[:, -1].mean())
        strip_before_b = float(chunk_b.water[:, 0].mean())
        total_before = float(chunk_a.water.sum() + chunk_b.water.sum())
        q = cross_chunk_flow_stub(chunk_a, chunk_b, "east", manning_n=0.035, dt_s=1.0)
        self.assertGreater(q, 0.0)
        total_after = float(chunk_a.water.sum() + chunk_b.water.sum())
        self.assertLess(float(chunk_a.water[:, -1].mean()), strip_before_a)
        self.assertGreater(float(chunk_b.water[:, 0].mean()), strip_before_b)
        # Mass lost only to clipping at zero on boundary cells.
        self.assertGreaterEqual(total_after, total_before - 1e-3)

    def test_hydrology_sv1d_smoke(self):
        """Saint-Venant 1D wrapper runs on paired chunks and returns a scalar."""
        p = TerrainParams()
        seed = 0x51D
        ca = generate_chunk(seed, (2, 2, 0), p)
        cb = generate_chunk(seed, (3, 2, 0), p)
        ca.water.fill(50.0)
        cb.water.fill(11.0)
        out = cross_chunk_saint_venant_1d(
            ca, cb, "east", manning_n=0.03, dt_s=0.5, channel_width_m=8.0
        )
        self.assertIsInstance(out, float)
        self.assertTrue(np.isfinite(out))

    def test_knowledge_wiring_build(self):
        """Thin path: architecture + ``wire_knowledge_cognition`` only (no full stack)."""
        sim = Simulation(
            SimConfig(
                founders=2,
                max_agents=6,
                knowledge_layers=False,
                life_emergence=False,
                epidemic_observer=False,
            )
        )
        install_architecture_layer(sim)
        sim._knowledge_layers_installed = True
        wire_knowledge_cognition(sim)
        sim.bootstrap()
        sim.agents.inv_stone[0] = 2.0
        from engine.agent import ActionKind, DriveKind
        from engine.cognition import apply_decision, decide, perceive

        obs = perceive(sim.agents, 0, sim.streamer, tick=sim.tick)
        obs.drives[int(DriveKind.THERMAL)] = 0.6
        d = decide(sim.agents, obs, sim)
        self.assertEqual(int(d.action), int(ActionKind.BUILD))
        ev = apply_decision(sim.agents, 0, d, sim.streamer, sim.tick)
        kinds = [e.get("kind") for e in (ev or [])]
        self.assertIn("voxel_placed", kinds)

    def test_hydrology_mode_tick(self):
        """Sim with ``hydrology_mode='stub'`` completes one step without error."""
        sim = Simulation(
            SimConfig(
                founders=2,
                max_agents=8,
                bounds_km=(0.1, 0.1),
                life_emergence=False,
                hydrology_mode="stub",
                hydrology_cross_chunk=True,
                epidemic_observer=False,
            )
        )
        sim.bootstrap()
        stats = sim.step()
        self.assertIsNotNone(stats)
        self.assertEqual(sim.tick, 1)

    def test_wire_full_stack_wires_genesis_and_rust(self):
        sim = Simulation(
            SimConfig(
                seed=0xF01157AC,
                founders=2,
                max_agents=8,
                bounds_km=(0.1, 0.1),
                life_emergence=False,
                epidemic_observer=False,
                emergence_subsystems=True,
                knowledge_layers=True,
            )
        )
        from engine.full_stack import wire_full_stack

        st = wire_full_stack(
            sim,
            genesis=True,
            rust_worldgraph=True,
            mp_api=False,
            five_cd=False,
        )
        self.assertTrue(st["genesis_bootstrapped"])
        self.assertTrue(st["rust_worldgraph"])
        self.assertIsNotNone(getattr(sim, "_rust_worldgraph", None))
        sim.bootstrap()
        stats = sim.step()
        self.assertIsNotNone(stats)
        self.assertGreaterEqual(sim.tick, 1)

    def test_mp_bootstrap_skips_without_api_key(self):
        prev = os.environ.pop("MP_API_KEY", None)
        try:
            sim = Simulation(
                SimConfig(
                    founders=2,
                    max_agents=6,
                    knowledge_layers=True,
                    life_emergence=False,
                    epidemic_observer=False,
                )
            )
            from engine.materials_project import try_fetch_mp_bootstrap

            self.assertEqual(try_fetch_mp_bootstrap(sim), 0)
        finally:
            if prev is not None:
                os.environ["MP_API_KEY"] = prev

    def test_commerce_emergence_after_genesis(self):
        gp = GenesisParams(
            seed=0xC0110ACE,
            resolution=16,
            erosion_iters=2,
            rain_iters=2,
            n_plates=4,
        )
        sim = Simulation(
            SimConfig(
                seed=gp.seed,
                founders=2,
                max_agents=8,
                bounds_km=(0.12, 0.12),
                life_emergence=False,
                epidemic_observer=False,
                emergence_subsystems=True,
                knowledge_layers=True,
                macro_commerce=True,
            )
        )
        bootstrap_genesis_sim(sim, genesis_params=gp, modules={MOD_GENESIS})
        from engine.commerce_emergence import install_commerce_emergence

        st = install_commerce_emergence(sim, refresh_every=1000)
        self.assertIsNotNone(st.trade)
        self.assertGreaterEqual(len(st.settlements), 2)
        snap = __import__(
            "engine.commerce_emergence",
            fromlist=["commerce_emergence_snapshot"],
        ).commerce_emergence_snapshot(sim)
        self.assertTrue(snap.get("installed"))

    def test_rust_worldgraph_prod_flag(self):
        sim = Simulation(
            SimConfig(
                founders=2,
                max_agents=6,
                life_emergence=False,
                epidemic_observer=False,
                emergence_subsystems=True,
                rust_worldgraph_prod=True,
            )
        )
        from engine.rust_worldgraph_tick import install_rust_worldgraph

        st = install_rust_worldgraph(sim, prod_mode=True)
        self.assertTrue(st.prod_mode)

    def test_terre_preset_keys(self):
        sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
        import run as run_mod

        terre = run_mod.PRESETS["terre"]
        self.assertTrue(terre["emergent_origins"])
        self.assertTrue(terre["full_biosphere"])
        self.assertTrue(terre["knowledge_layers"])
        self.assertEqual(terre["hydrology_mode"], "sv1d")
        self.assertEqual(terre["founders"], 0)
        self.assertTrue(terre.get("macro_commerce"))
        self.assertTrue(terre.get("rust_worldgraph_prod"))


if __name__ == "__main__":
    unittest.main()
