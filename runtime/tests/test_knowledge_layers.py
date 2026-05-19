"""Tests for physics / chemistry / architecture / social layers."""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from engine.sim import Simulation, SimConfig
from engine.physics_layer import check_voxel_structure_stable
from engine.materials_project import load_bundle, ingest_records, MaterialsProjectState, run_synthesis_pipeline
from engine.material_synthesis import SynthesisConditions, MaterialRegistry
from engine.architecture_layer import agent_place_voxel, install_architecture_layer
from engine.social_topology import EdgeKind, add_edge, create_topology, install_social_topology
from engine.knowledge_layers import install_knowledge_layers, knowledge_layers_snapshot
from engine.statics_load import compute_stability_score, distribute_vertical_loads
from engine.statics import Structure, VoxelBlock
from engine.social_topology import gravity_trade_probability
from engine.materials_project import find_nearest_record


class KnowledgeLayerTests(unittest.TestCase):
    def test_statics_stable_tower(self):
        blocks = [(0, 0, z, "stone") for z in range(3)]
        ok, reason = check_voxel_structure_stable(blocks)
        self.assertTrue(ok, reason)

    def test_statics_rejects_unsupported(self):
        blocks = [(3, 3, 5, "stone")]
        ok, reason = check_voxel_structure_stable(blocks)
        self.assertFalse(ok)
        self.assertIn("unsupported", reason)

    def test_materials_project_ingest(self):
        st = MaterialsProjectState()
        n = ingest_records(load_bundle(), st)
        self.assertGreaterEqual(n, 5)
        from engine import statics
        self.assertIn("sio2", statics.STRENGTH_TABLE)

    def test_synthesis_pipeline(self):
        st = MaterialsProjectState()
        ingest_records(load_bundle(), st)
        reg = MaterialRegistry()
        mat = run_synthesis_pipeline(
            {"Cu": 0.7, "Sn": 0.3},
            SynthesisConditions(temperature_K=1100.0, time_s=3600.0),
            st, reg,
        )
        self.assertIsNotNone(mat)
        self.assertEqual(st.syntheses_ok, 1)

    def test_architecture_place_voxel(self):
        sim = Simulation(SimConfig(founders=2, max_agents=5, bounds_km=(0.3, 0.3)))
        install_architecture_layer(sim)
        sim.bootstrap()
        ok, msg = agent_place_voxel(sim, 0, 0, 0, 0, "stone")
        self.assertTrue(ok, msg)

    def test_social_topology_edges(self):
        sim = Simulation(SimConfig(founders=4, max_agents=8))
        st = install_social_topology(sim)
        sim.bootstrap()
        add_edge(st, 0, 1, EdgeKind.TRADE, weight=0.5)
        topo = create_topology(st, "guild_test", members={0, 1, 2})
        self.assertEqual(len(st.edges), 1)
        self.assertIn(0, topo.members)

    def test_install_all_layers(self):
        sim = Simulation(SimConfig(founders=4, max_agents=10, knowledge_layers=True))
        for _ in range(40):
            sim.step()
        snap = knowledge_layers_snapshot(sim)
        self.assertIn("physics", snap)
        self.assertIn("chemistry", snap)
        self.assertIn("social", snap)

    def test_load_spreading_tower_score(self):
        blocks = [
            VoxelBlock.from_material((0, 0, z), "stone", 0.25)
            for z in range(4)
        ]
        struct = Structure(0, blocks, voxel_size_m=0.25)
        loads = distribute_vertical_loads(struct)
        self.assertGreater(loads[(0, 0, 0)], loads[(0, 0, 3)])
        score = compute_stability_score(struct)
        self.assertGreater(score, 0.3)

    def test_gravity_trade_probability(self):
        p_near = gravity_trade_probability(10.0, 10.0, 5.0)
        p_far = gravity_trade_probability(10.0, 10.0, 50.0)
        self.assertGreater(p_near, p_far)

    def test_mp_nearest_bronze(self):
        st = MaterialsProjectState()
        ingest_records(load_bundle(), st)
        rec = find_nearest_record({"Cu": 0.7, "Sn": 0.3}, st)
        self.assertIsNotNone(rec)
        self.assertIn("Cu", rec.elements)

    def test_knowledge_wiring_build(self):
        sim = Simulation(SimConfig(founders=2, max_agents=5, knowledge_layers=True))
        sim.bootstrap()
        sim.agents.inv_stone[0] = 2.0
        from engine.cognition import decide, perceive, apply_decision
        from engine.agent import ActionKind
        from engine.agent import DriveKind
        obs = perceive(sim.agents, 0, sim.streamer, tick=sim.tick)
        obs.drives[int(DriveKind.THERMAL)] = 0.6
        d = decide(sim.agents, obs, sim)
        self.assertEqual(int(d.action), int(ActionKind.BUILD))
        ev = apply_decision(sim.agents, 0, d, sim.streamer, sim.tick)
        kinds = [e.get("kind") for e in ev]
        self.assertIn("voxel_placed", kinds)


if __name__ == "__main__":
    unittest.main()
