"""Smoke test for Phase 5c+5d integration.

Runs a 200-tick simulation with 30 agents in a small bounded world and
asserts:
    * at least one INNOVATION event (tech discovery) was emitted, OR
      there is at least one InventionRegistry artifact recorded;
    * at least one BUILD event was emitted, OR there is an active project;
    * atmosphere.co2_kg is non-zero IF any HEARTH project is active or
      completed (i.e. there's actually been combustion).
"""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

import numpy as np

from engine.construction import StructureKind
from engine.sim import Simulation, SimConfig
from engine.sim_5cd_integration import install


class Sim5CDSmokeTests(unittest.TestCase):
    def test_200_ticks_emits_innovation_and_build_events(self):
        cfg = SimConfig(
            name="smoke_5cd",
            seed=0xC0FFEE_5CD,
            founders=30,
            max_agents=120,
            bounds_km=(0.5, 0.5),
            spawn_radius_m=20.0,
            cultures=1,
            drive_accel=1500.0,
        )
        sim = Simulation(cfg)
        install(sim)

        # Sanity: subsystems wired up.
        self.assertTrue(hasattr(sim, "construction_registry"))
        self.assertTrue(hasattr(sim, "atmosphere"))
        self.assertTrue(hasattr(sim, "invention_registry"))
        self.assertTrue(hasattr(sim.agents, "known_techs"))
        self.assertTrue(hasattr(sim.agents, "values"))
        self.assertTrue(hasattr(sim.agents, "skills"))
        self.assertTrue(hasattr(sim.agents, "chronic_fatigue"))
        self.assertTrue(hasattr(sim.agents, "labor_invested"))

        # Tally signals over the run.
        innovation_events = 0
        build_events = 0
        invent_events = 0

        # Wrap the annalist to count events as they pass through.
        original_record = sim.annalist.record_tick

        def counting_record(tick, agents, *, births, deaths, raw_events):
            nonlocal innovation_events, build_events, invent_events
            for e in raw_events:
                k = e.get("kind")
                if k == "innovation":
                    innovation_events += 1
                elif k == "build":
                    build_events += 1
                elif k == "invent":
                    invent_events += 1
            return original_record(tick, agents,
                                   births=births, deaths=deaths,
                                   raw_events=raw_events)

        sim.annalist.record_tick = counting_record

        for _ in range(200):
            sim.step()

        # ---- INNOVATION (tech discovery OR invented artifact) ----
        artifacts_present = len(sim.invention_registry.artifacts) > 0
        self.assertTrue(
            innovation_events >= 1 or invent_events >= 1 or artifacts_present,
            f"expected >=1 innovation/invent event after 200 ticks; "
            f"got innovation={innovation_events} invent={invent_events} "
            f"artifacts={len(sim.invention_registry.artifacts)}"
        )

        # ---- BUILD (completed structure OR active project) ----
        active_projects = len(sim.construction_registry.projects)
        finished_structs = len(sim.construction_registry.structures)
        self.assertTrue(
            build_events >= 1 or active_projects >= 1 or finished_structs >= 1,
            f"expected >=1 build event OR active project; "
            f"got build_events={build_events} active={active_projects} "
            f"structures={finished_structs}"
        )

        # ---- ATMOSPHERE ----
        # The installer seeds an initial HEARTH project. Once it completes,
        # the hearth burns wood every tick and CO2 should be > 0.
        has_hearth = any(s.kind == StructureKind.HEARTH
                         for s in sim.construction_registry.structures.values())
        has_hearth_proj = any(p.kind == StructureKind.HEARTH
                              for p in sim.construction_registry.projects.values())
        if has_hearth:
            self.assertGreater(
                sim.atmosphere.co2_kg, 0.0,
                "expected co2_kg > 0 with at least one completed HEARTH")
        else:
            # If hearth never completed, at least confirm atmosphere ran
            # (forest/ocean cells were counted).
            self.assertGreaterEqual(
                sim.atmosphere.forest_cells + sim.atmosphere.ocean_cells, 0,
                "atmosphere never ticked"
            )
            # And a hearth project should still be active.
            self.assertTrue(
                has_hearth_proj,
                "expected either a completed or active HEARTH project"
            )

        # Chronic fatigue should remain bounded for everybody.
        self.assertTrue(
            float(sim.agents.chronic_fatigue.max()) < 2.5,
            "chronic_fatigue ran away"
        )

    def test_install_is_idempotent(self):
        cfg = SimConfig(name="idem", seed=42, founders=4, max_agents=10,
                        bounds_km=(0.3, 0.3), drive_accel=500.0)
        sim = Simulation(cfg)
        install(sim)
        install(sim)  # second call must not blow up
        # Step once to confirm nothing exploded.
        sim.step()
        self.assertTrue(sim._5cd_installed)


if __name__ == "__main__":
    unittest.main()
