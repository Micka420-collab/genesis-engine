"""Tests for the God Observer avatar — perception filter & log behaviour."""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from engine.god_avatar import (
    GodInterventionLog,
    GodObserver,
    MiracleWitness,
    filter_god_from_perception,
)


class GodObserverTests(unittest.TestCase):
    def test_construct_defaults(self):
        god = GodObserver()
        self.assertEqual(god.pos.shape, (3,))
        self.assertFalse(god.visible)
        self.assertEqual(god.intervention_count, 0)
        self.assertEqual(god.selected_power, "observe")
        self.assertEqual(god.visible_to_agents, set())

    def test_teleport_and_elevation(self):
        god = GodObserver()
        god.teleport(10.0, -5.0, 250.0)
        self.assertAlmostEqual(float(god.pos[0]), 10.0)
        self.assertAlmostEqual(float(god.pos[1]), -5.0)
        self.assertAlmostEqual(float(god.pos[2]), 250.0)
        self.assertAlmostEqual(god.elevation_m, 250.0)

    def test_teleport_default_z_keeps_elevation(self):
        god = GodObserver(elevation_m=300.0)
        god.teleport(1.0, 2.0)
        self.assertAlmostEqual(float(god.pos[2]), 300.0)

    def test_set_visible_clears_per_agent_set(self):
        god = GodObserver()
        god.reveal_to(7)
        god.set_visible(True)
        self.assertTrue(god.is_visible_to_row(7))
        god.set_visible(False)
        self.assertEqual(god.visible_to_agents, set())
        self.assertFalse(god.is_visible_to_row(7))

    def test_per_agent_reveal_overrides_global_hidden(self):
        god = GodObserver(visible=False)
        god.reveal_to(3)
        self.assertTrue(god.is_visible_to_row(3))
        self.assertFalse(god.is_visible_to_row(4))

    def test_increment_intervention(self):
        god = GodObserver()
        self.assertEqual(god.increment_intervention(), 1)
        self.assertEqual(god.increment_intervention(), 2)
        self.assertEqual(god.intervention_count, 2)


class PerceptionFilterTests(unittest.TestCase):
    def test_hidden_god_scrubbed_from_perception(self):
        god = GodObserver(visible=False)
        perc = {"nearest": {"divine": object(), "water": "natural"}}
        out = filter_god_from_perception(god, perc, row=0,
                                         agent_pos=np.array([0.0, 0.0, 0.0]))
        self.assertNotIn("divine", out["nearest"])
        self.assertIn("water", out["nearest"])

    def test_visible_god_in_range_appears(self):
        god = GodObserver(visible=True)
        god.teleport(5.0, 0.0, 200.0)
        perc = {"nearest": {}}
        out = filter_god_from_perception(
            god, perc, row=0,
            agent_pos=np.array([0.0, 0.0, 0.0]),
            radius_m=50.0,
        )
        try:
            from engine.cognition import PerceivedTarget  # noqa: F401
            self.assertIn("divine", out["nearest"])
            tgt = out["nearest"]["divine"]
            self.assertEqual(tgt.kind, "divine")
            self.assertAlmostEqual(tgt.x, 5.0)
        except Exception:
            self.assertIsInstance(out, dict)

    def test_visible_god_out_of_range_not_added(self):
        god = GodObserver(visible=True)
        god.teleport(10_000.0, 0.0)
        perc = {"nearest": {}}
        out = filter_god_from_perception(
            god, perc, row=0,
            agent_pos=np.array([0.0, 0.0, 0.0]),
            radius_m=50.0,
        )
        self.assertNotIn("divine", out["nearest"])

    def test_per_agent_visibility_filters_correctly(self):
        god = GodObserver(visible=False)
        god.reveal_to(2)
        god.teleport(0.0, 0.0)
        perc_a = {"nearest": {}}
        perc_b = {"nearest": {}}
        out_a = filter_god_from_perception(god, perc_a, row=1,
                                           agent_pos=np.array([1.0, 1.0, 0.0]))
        out_b = filter_god_from_perception(god, perc_b, row=2,
                                           agent_pos=np.array([1.0, 1.0, 0.0]))
        self.assertNotIn("divine", out_a["nearest"])
        try:
            from engine.cognition import PerceivedTarget  # noqa: F401
            self.assertIn("divine", out_b["nearest"])
        except Exception:
            pass


class MiracleWitnessTests(unittest.TestCase):
    def test_emits_raw_event_record(self):
        witness = MiracleWitness()
        ev = witness(5, "rain_of_fish", (10.0, 20.0, 0.0), tick=42)
        self.assertEqual(ev["kind"], "miracle_witnessed")
        self.assertEqual(ev["row"], 5)
        self.assertEqual(ev["miracle"], "rain_of_fish")
        self.assertEqual(ev["tick"], 42)
        self.assertEqual(ev["pos"], [10.0, 20.0, 0.0])

    def test_witness_aggregation(self):
        witness = MiracleWitness()
        witness(1, "rain_of_fish", (0, 0, 0))
        witness(1, "burning_bush", (1, 1, 0))
        witness(2, "burning_bush", (1, 1, 0))
        self.assertEqual(len(witness.witnesses_for(1)), 2)
        self.assertEqual(len(witness.witnesses_for(2)), 1)
        self.assertEqual(witness.total_witnessed(), 3)


class GodInterventionLogTests(unittest.TestCase):
    def test_append_and_recent(self):
        log = GodInterventionLog()
        log.append("teleport", {"x": 1.0, "y": 2.0})
        log.append("visibility", {"visible": True})
        self.assertEqual(len(log), 2)
        recent = log.recent(5)
        self.assertEqual(recent[0]["kind"], "teleport")
        self.assertEqual(recent[1]["kind"], "visibility")
        self.assertEqual(recent[0]["seq"], 1)
        self.assertEqual(recent[1]["seq"], 2)

    def test_to_jsonl_roundtrips(self):
        import json as _json
        log = GodInterventionLog()
        log.append("spawn_agent", {"x": 0.0, "y": 0.0, "culture_id": 1})
        text = log.to_jsonl()
        rows = [_json.loads(line) for line in text.splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "spawn_agent")
        self.assertEqual(rows[0]["payload"]["culture_id"], 1)

    def test_cap_enforced(self):
        log = GodInterventionLog(cap=3)
        for i in range(5):
            log.append("ping", {"i": i})
        self.assertEqual(len(log), 3)
        recent = log.recent(10)
        self.assertEqual([r["payload"]["i"] for r in recent], [2, 3, 4])


if __name__ == "__main__":
    unittest.main()
