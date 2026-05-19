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


if __name__ == "__main__":
    unittest.main()
