"""Phase 5c+5d : extension non-invasive de l'AgentRegistry.

Ajoute les nouveaux champs sans réécrire agent.py — appeler extend_registry()
au bootstrap de la simulation.
"""
from __future__ import annotations

import numpy as np

from engine.core import prf_rng
from engine.materials import MaterialKind
from engine.tech_tree import NUM_TECHS, TechKind


# Emotion dimensions: joy / fear / anger / sadness / disgust / surprise
N_EMOTIONS = 6
EMO_JOY, EMO_FEAR, EMO_ANGER, EMO_SAD, EMO_DISGUST, EMO_SURPRISE = range(6)

# Value dimensions: survival / family / curiosity / community / legacy / freedom / dominance
N_VALUES = 7
VAL_SURVIVAL, VAL_FAMILY, VAL_CURIOSITY, VAL_COMMUNITY, VAL_LEGACY, VAL_FREEDOM, VAL_DOMINANCE = range(7)

# Per-material inventory tracked (kg). The existing arrays in agent.py
# (inv_wood, inv_stone, inv_metal) stay for backward compat; the new richer
# set below is added side-by-side.
MATERIAL_INV_FIELDS = {
    MaterialKind.WOOD: "inv_wood",       # already exists
    MaterialKind.STONE: "inv_stone",     # already exists
    MaterialKind.FLINT: "inv_flint",
    MaterialKind.CLAY: "inv_clay",
    MaterialKind.FIBER: "inv_fiber",
    MaterialKind.LEATHER: "inv_leather",
    MaterialKind.BONE: "inv_bone",
    MaterialKind.COPPER: "inv_copper",
    MaterialKind.TIN: "inv_tin",
    MaterialKind.BRONZE: "inv_bronze",
    MaterialKind.IRON: "inv_iron",
    MaterialKind.CERAMIC: "inv_ceramic",
    MaterialKind.CHARCOAL: "inv_charcoal",
    MaterialKind.GRAIN: "inv_grain",
}


def extend_registry(agents, world_seed: int) -> None:
    """Add Phase 5c+5d fields to an existing AgentRegistry instance.

    Idempotent — safe to call multiple times.
    """
    N = agents.capacity
    if hasattr(agents, "_phase5cd_extended"):
        return
    agents._phase5cd_extended = True

    # Construction / technology
    agents.known_techs = np.zeros((N, NUM_TECHS), dtype=bool)
    agents.current_project_id = np.full(N, -1, dtype=np.int32)
    agents.labor_invested = np.zeros(N, dtype=np.float32)

    # Per-material inventory (kg) — add fields not already present on the
    # original registry.
    for mat, fld in MATERIAL_INV_FIELDS.items():
        if not hasattr(agents, fld):
            setattr(agents, fld, np.zeros(N, dtype=np.float32))

    # Emotions (6-dim) — bounded [0, 1].
    agents.emotions = np.zeros((N, N_EMOTIONS), dtype=np.float32)

    # Values / moral priorities (7-dim) — bounded [0, 1], normalized so they sum to 1
    # at spawn time. Seeded deterministically.
    agents.values = np.full((N, N_VALUES), 1.0 / N_VALUES, dtype=np.float32)

    # Fatigue chronique (cumulative, separate from per-tick `fatigue` drive).
    agents.chronic_fatigue = np.zeros(N, dtype=np.float32)

    # Injury localisée — vector of body-part injuries (head/torso/arm_l/arm_r/leg_l/leg_r).
    agents.injury_parts = np.zeros((N, 6), dtype=np.float32)

    # Disease state — pathogen load already exists; add infectious flag + counter.
    agents.infectious_until = np.full(N, -1, dtype=np.int64)

    # Skill / learning — proficiency per skill category (0..1), used for craft + build speed.
    # 8 categories: forage, hunt, build, craft, heal, teach, fight, navigate
    agents.skills = np.full((N, 8), 0.2, dtype=np.float32)

    # Awareness flags
    agents.has_seen_fire = np.zeros(N, dtype=bool)
    agents.has_seen_tool = np.zeros(N, dtype=bool)

    # Stamp the existing founders with seeded values + initial techs.
    # Founders have a slim chance of starting with FIRE knowledge (paleolithic
    # baseline — humans had fire long before the simulation start).
    for row in range(agents.n_active):
        rng = prf_rng(world_seed, ["agent", "values"], [row])
        v = rng.random(N_VALUES, dtype=np.float32)
        v = v / max(v.sum(), 1e-6)
        agents.values[row] = v

        rng = prf_rng(world_seed, ["agent", "starting_techs"], [row])
        # All founders know FIRE (Earth's initial condition at simulation
        # bootstrap = late paleolithic / mesolithic baseline).
        agents.known_techs[row, int(TechKind.FIRE)] = True
        # 60% chance of knowing STONE_TOOLS
        if rng.random() < 0.60:
            agents.known_techs[row, int(TechKind.STONE_TOOLS)] = True
        # 20% chance of knowing SHELTER
        if rng.random() < 0.20:
            agents.known_techs[row, int(TechKind.SHELTER)] = True
        # Skills seeded by personality
        agents.skills[row, 0] = 0.2 + 0.4 * float(agents.curiosity[row])      # forage
        agents.skills[row, 1] = 0.2 + 0.4 * float(agents.aggression[row])     # hunt
        agents.skills[row, 2] = 0.2 + 0.3 * float(agents.intelligence[row])   # build
        agents.skills[row, 3] = 0.2 + 0.4 * float(agents.intelligence[row])   # craft
        agents.skills[row, 4] = 0.2 + 0.4 * float(agents.empathy[row])        # heal
        agents.skills[row, 5] = 0.2 + 0.4 * float(agents.openness[row])       # teach
        agents.skills[row, 6] = 0.2 + 0.4 * float(agents.aggression[row])     # fight
        agents.skills[row, 7] = 0.2 + 0.4 * float(agents.openness[row])       # navigate


def inherit_5cd_fields(agents, world_seed: int, child_row: int,
                       parent_a: int, parent_b: int, tick: int) -> None:
    """When an offspring is spawned, inherit techs / values / skills.

    Must be called from the sim after agents.spawn_offspring().
    """
    if not hasattr(agents, "_phase5cd_extended"):
        return

    # Known techs: child knows tech if either parent knew it (passed by upbringing).
    # Lose ~5% per tech (children don't always learn everything).
    rng = prf_rng(world_seed, ["agent", "child_techs"], [parent_a, parent_b, tick])
    for t in range(agents.known_techs.shape[1]):
        if agents.known_techs[parent_a, t] or agents.known_techs[parent_b, t]:
            if rng.random() < 0.95:
                agents.known_techs[child_row, t] = True

    # Values: mid-parent + Gaussian mutation + re-normalize.
    vmid = (agents.values[parent_a] + agents.values[parent_b]) * 0.5
    vmut = rng.normal(0.0, 0.05, size=agents.values.shape[1]).astype(np.float32)
    new_v = np.clip(vmid + vmut, 0.01, 1.0)
    agents.values[child_row] = new_v / new_v.sum()

    # Skills: start at half the parent average (the child has to learn).
    smid = (agents.skills[parent_a] + agents.skills[parent_b]) * 0.5
    agents.skills[child_row] = 0.2 + 0.5 * (smid - 0.2)
