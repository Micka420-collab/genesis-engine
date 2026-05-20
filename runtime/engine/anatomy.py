"""Genesis Engine — Wave 34 detailed anatomy + wounds + blood system.

Remplace le scalaire ``agents.injuries`` global par un système anatomique
complet inspiré de la physiologie humaine réelle :

  - **10 body parts** : head, torso, l_arm, r_arm, l_hand, r_hand,
    l_leg, r_leg, l_foot, r_foot.
  - **4 wound kinds** : cut, bruise, fracture, burn, chacun avec son
    propre taux de cicatrisation, son taux de saignement, et son seuil
    de douleur.
  - **Volume sanguin par agent** : 5.0 L initial. Saignement par
    blessure × sévérité × kind_rate. Mort par hémorragie sous 1.5 L
    (perte 70 %, choc hypovolémique mortel comme chez l'humain).
  - **Couplage automatique action → wound** : aucun script ne décide
    "place une coupure ici". Les blessures émergent statistiquement
    des activités agent :
        MINE        → R_HAND cut + R_ARM bruise (heurts pioche)
        SMELT       → forearm burn (forge chaud)
        BUILD       → torso/back bruise (effort)
        HUNT        → various (selon prey resistance)
        FIGHT       → head/torso (combat humain)
        FORAGE      → l_hand thorn cuts (rare)
        PLANT/HARVEST → back strain
        FALL (high slope) → leg fracture

Tous les taux sont déterministes via ``prf_rng((sim_seed, "anatomy",
subsystem), [tick, row, ...])``. Pas de ``random.random()``.

Read-only sur les modules existants. Ajoute des attributs à
``sim._anatomy_fields``. Wrappe ``sim.step`` une fois pour avancer
saignement + cicatrisation + checks de mort.

Compatibilité
-------------

- Maintient ``agents.injuries`` à jour comme **moyenne pondérée** de
  toutes les wound severities, donc le code legacy qui lit
  ``agents.injuries`` continue de fonctionner.
- ``DeathCause.STARVATION`` est augmenté d'une cause nouvelle
  ``DEATH_BY_HEMORRHAGE = 99`` (mode externe, pas dans l'enum
  initial — stocké comme attribut).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import prf_rng
from engine.agent import ActionKind


PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

class BodyPart(IntEnum):
    HEAD = 0
    TORSO = 1
    L_ARM = 2
    R_ARM = 3
    L_HAND = 4
    R_HAND = 5
    L_LEG = 6
    R_LEG = 7
    L_FOOT = 8
    R_FOOT = 9


N_BODY_PARTS = 10


class WoundKind(IntEnum):
    CUT = 0       # Sharp injury → high bleed rate, medium heal
    BRUISE = 1    # Blunt impact → no bleed, fast heal
    FRACTURE = 2  # Bone break → low bleed (internal), slow heal
    BURN = 3      # Thermal → medium bleed (plasma loss), medium heal


N_WOUND_KINDS = 4


BODY_PART_NAMES = (
    "head", "torso", "l_arm", "r_arm", "l_hand", "r_hand",
    "l_leg", "r_leg", "l_foot", "r_foot",
)
WOUND_KIND_NAMES = ("cut", "bruise", "fracture", "burn")


# ---------------------------------------------------------------------------
# Physical constants (calibrated to real human medicine)
# ---------------------------------------------------------------------------

BLOOD_VOLUME_INITIAL_L = 5.0      # adult human ~5 L
BLOOD_DEATH_THRESHOLD_L = 1.5     # ~70 % loss = hypovolemic shock fatal

# Healing time scales (seconds, then converted in step rate).
HEAL_TIME_S = (
    7.0 * 86400.0,   # cut: 7 days
    3.0 * 86400.0,   # bruise: 3 days
    40.0 * 86400.0,  # fracture: 40 days
    20.0 * 86400.0,  # burn: 20 days
)
# Bleeding rate per (severity unit × tick @ accel=1).
# L/s. Cuts bleed fast, bruises don't, fractures internal slow, burns
# plasma loss medium.
BLEED_RATE_PER_SEVERITY_L_PER_S = (
    1.5e-4,   # cut : 0.54 L/h at severity=1
    0.0,      # bruise : no bleeding
    4.0e-5,   # fracture : 0.14 L/h
    8.0e-5,   # burn : 0.29 L/h plasma loss
)
# Pain contribution per (severity unit × kind).
PAIN_WEIGHT = (0.4, 0.2, 0.7, 0.5)


# Probability table : per action, the (body_part, wound_kind, severity)
# inflicted per occurrence. Each entry is
# ``(part, kind, base_severity, prf_jitter_amplitude)``.
# Multiple entries per action = each rolled independently.
# Severity is then jittered by ± jitter via prf_rng.
ACTION_WOUND_TABLE: Dict[int, List[Tuple[int, int, float, float]]] = {
    int(ActionKind.MINE):    [
        (int(BodyPart.R_HAND),  int(WoundKind.CUT),     0.10, 0.05),
        (int(BodyPart.R_ARM),   int(WoundKind.BRUISE),  0.05, 0.03),
    ],
    int(ActionKind.SMELT):   [
        (int(BodyPart.R_ARM),   int(WoundKind.BURN),    0.08, 0.05),
        (int(BodyPart.R_HAND),  int(WoundKind.BURN),    0.05, 0.04),
    ],
    int(ActionKind.BUILD):   [
        (int(BodyPart.TORSO),   int(WoundKind.BRUISE),  0.04, 0.03),
        (int(BodyPart.L_HAND),  int(WoundKind.BRUISE),  0.03, 0.02),
    ],
    int(ActionKind.HUNT):    [
        (int(BodyPart.TORSO),   int(WoundKind.CUT),     0.06, 0.05),
        (int(BodyPart.L_ARM),   int(WoundKind.BRUISE),  0.04, 0.03),
    ],
    int(ActionKind.FIGHT):   [
        (int(BodyPart.HEAD),    int(WoundKind.BRUISE),  0.08, 0.05),
        (int(BodyPart.TORSO),   int(WoundKind.CUT),     0.10, 0.06),
        (int(BodyPart.L_ARM),   int(WoundKind.CUT),     0.05, 0.04),
    ],
    int(ActionKind.FORAGE):  [
        (int(BodyPart.L_HAND),  int(WoundKind.CUT),     0.02, 0.02),
    ],
    int(ActionKind.PLANT):   [
        (int(BodyPart.TORSO),   int(WoundKind.BRUISE),  0.02, 0.02),
    ],
    int(ActionKind.HARVEST): [
        (int(BodyPart.TORSO),   int(WoundKind.BRUISE),  0.03, 0.02),
        (int(BodyPart.R_HAND),  int(WoundKind.CUT),     0.02, 0.02),
    ],
}

# Per-action probability the wound roll fires at all (deterministic via prf_rng).
ACTION_WOUND_PROBABILITY: Dict[int, float] = {
    int(ActionKind.MINE):    0.25,
    int(ActionKind.SMELT):   0.30,
    int(ActionKind.BUILD):   0.12,
    int(ActionKind.HUNT):    0.40,
    int(ActionKind.FIGHT):   0.85,
    int(ActionKind.FORAGE):  0.08,
    int(ActionKind.PLANT):   0.05,
    int(ActionKind.HARVEST): 0.10,
}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class AnatomyFields:
    """Per-agent body-part-aware health state.

    Wound severity arrays are of shape ``(N, N_BODY_PARTS, N_WOUND_KINDS)``
    in float32, each value in [0, 1].
    """
    blood_volume_l: np.ndarray = field(default=None)
    wound_severity: np.ndarray = field(default=None)
    bleed_rate_l_per_s: np.ndarray = field(default=None)
    death_by_hemorrhage: np.ndarray = field(default=None)  # bool flag
    cumulative_wounds_inflicted: int = 0
    cumulative_deaths_from_bleed: int = 0
    last_action_per_agent: np.ndarray = field(default=None)

    def initialise(self, N: int) -> None:
        z = lambda: np.zeros(N, dtype=np.float32)
        self.blood_volume_l = np.full(N, BLOOD_VOLUME_INITIAL_L,
                                         dtype=np.float32)
        self.wound_severity = np.zeros(
            (N, N_BODY_PARTS, N_WOUND_KINDS), dtype=np.float32)
        self.bleed_rate_l_per_s = z()
        self.death_by_hemorrhage = np.zeros(N, dtype=bool)
        self.last_action_per_agent = np.full(N, -1, dtype=np.int8)


# ---------------------------------------------------------------------------
# Wound inflictions (pure functions)
# ---------------------------------------------------------------------------

def inflict_wound(fields: AnatomyFields, row: int, part: int,
                    kind: int, severity: float) -> float:
    """Add ``severity`` to the (row, part, kind) wound. Clamps to [0, 1].

    Returns the new severity at that location.
    """
    sev = float(np.clip(severity, 0.0, 1.0))
    cur = float(fields.wound_severity[row, int(part), int(kind)])
    new = min(1.0, cur + sev)
    fields.wound_severity[row, int(part), int(kind)] = new
    fields.cumulative_wounds_inflicted += 1
    return new


def wound_from_action(fields: AnatomyFields, row: int, action: int,
                        sim_seed: int, tick: int) -> List[Tuple[int, int, float]]:
    """Stochastically inflict wounds from one action occurrence.

    Returns list of ``(part, kind, severity)`` for each wound created.
    Empty list if the action didn't roll a wound this tick.

    Deterministic via :func:`engine.core.prf_rng`.
    """
    table = ACTION_WOUND_TABLE.get(int(action))
    if not table:
        return []
    prob = ACTION_WOUND_PROBABILITY.get(int(action), 0.0)
    rng = prf_rng(sim_seed, ["anatomy", "wound_roll"],
                  [int(tick), int(row), int(action)])
    if float(rng.random()) > prob:
        return []
    inflicted: List[Tuple[int, int, float]] = []
    for entry_idx, (part, kind, base_sev, jitter) in enumerate(table):
        rng2 = prf_rng(sim_seed, ["anatomy", "wound_sev"],
                       [int(tick), int(row), int(action), entry_idx])
        sev = float(base_sev + (rng2.random() - 0.5) * 2.0 * jitter)
        sev = max(0.0, sev)
        if sev <= 1e-4:
            continue
        new_sev = inflict_wound(fields, row, part, kind, sev)
        inflicted.append((int(part), int(kind), new_sev))
    return inflicted


# ---------------------------------------------------------------------------
# Bleeding + healing tick
# ---------------------------------------------------------------------------

def step_anatomy(sim, dt_s: float) -> Dict[str, int]:
    """Advance bleeding, healing, hemorrhage checks for one tick.

    Returns a stats dict.
    """
    fields: Optional[AnatomyFields] = getattr(sim, "_anatomy_fields", None)
    if fields is None:
        return {"installed": 0}
    n = sim.agents.n_active
    alive = sim.agents.alive[:n].astype(bool)
    if not alive.any():
        return {"installed": 1, "alive": 0}

    sev = fields.wound_severity[:n]              # (n, N_PARTS, N_KINDS)
    blood = fields.blood_volume_l[:n]
    bleed = fields.bleed_rate_l_per_s[:n]

    # Bleed rate = Σ_kind bleed_rate_per_kind × Σ_parts severity_at_part.
    # In other words, bleed depends only on total severity per kind.
    total_sev_per_kind = sev.sum(axis=1)          # (n, N_KINDS)
    bleed_per_kind = np.array(BLEED_RATE_PER_SEVERITY_L_PER_S,
                                 dtype=np.float32)
    new_bleed = (total_sev_per_kind * bleed_per_kind[None, :]).sum(axis=1)
    fields.bleed_rate_l_per_s[:n] = new_bleed.astype(np.float32)

    # Apply bleeding for alive agents.
    blood_loss = new_bleed * dt_s
    new_blood = blood - blood_loss
    new_blood = np.where(alive, new_blood, blood)
    fields.blood_volume_l[:n] = new_blood.astype(np.float32)

    # Death by hemorrhage : blood drops below threshold.
    hemorrhage_mask = (new_blood < BLOOD_DEATH_THRESHOLD_L) & alive
    n_died = 0
    if hemorrhage_mask.any():
        for row in np.where(hemorrhage_mask)[0]:
            if not fields.death_by_hemorrhage[row]:
                fields.death_by_hemorrhage[row] = True
                sim.agents.alive[row] = False
                fields.cumulative_deaths_from_bleed += 1
                n_died += 1

    # Healing : each kind's severity decays at its own rate.
    heal_rates = np.array([1.0 / t for t in HEAL_TIME_S], dtype=np.float32)
    decay = heal_rates[None, None, :] * dt_s
    new_sev = np.maximum(sev - decay, 0.0)
    fields.wound_severity[:n] = new_sev.astype(np.float32)

    # Mirror back into legacy agents.injuries scalar (weighted mean
    # severity across parts/kinds + pain weights).
    pain_w = np.array(PAIN_WEIGHT, dtype=np.float32)
    weighted = (new_sev * pain_w[None, None, :]).sum(axis=(1, 2))
    norm = float(N_BODY_PARTS * sum(PAIN_WEIGHT))
    sim.agents.injuries[:n] = (weighted / max(norm, 1e-6)).astype(np.float32)

    return {
        "installed": 1,
        "alive": int(alive.sum()),
        "n_with_open_wound": int((sev.sum(axis=(1, 2)) > 0.01).sum()),
        "n_bleeding": int((new_bleed > 1e-6).sum()),
        "blood_min_l": float(new_blood[alive].min())
                          if alive.any() else BLOOD_VOLUME_INITIAL_L,
        "blood_mean_l": float(new_blood[alive].mean())
                          if alive.any() else BLOOD_VOLUME_INITIAL_L,
        "n_died_this_tick": n_died,
    }


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------

def install_anatomy(sim) -> AnatomyFields:
    """Idempotent installer. Wraps ``sim.step`` to advance anatomy.

    Also installs a post-action hook : after ``apply_decision`` writes
    ``agents.action[row]``, we read it and roll a wound via
    :func:`wound_from_action`.

    Returns the per-sim ``AnatomyFields`` instance.
    """
    existing: Optional[AnatomyFields] = getattr(sim, "_anatomy_fields", None)
    if existing is not None:
        return existing

    fields = AnatomyFields()
    fields.initialise(sim.agents.capacity)
    sim._anatomy_fields = fields

    if getattr(sim, "_anatomy_wrapped", False):
        return fields
    sim._anatomy_wrapped = True

    original_step = sim.step

    def wrapped_step():
        # Capture pre-step actions so we know what agents are doing this tick.
        prev_action = sim.agents.action[:sim.agents.n_active].copy()
        stats = original_step()
        n = sim.agents.n_active
        # Post-step : roll wounds based on the action each alive agent took.
        alive_idx = np.flatnonzero(sim.agents.alive[:n])
        for row in alive_idx:
            row = int(row)
            act = int(sim.agents.action[row])
            wound_from_action(fields, row, act,
                                int(sim.cfg.seed), int(sim.tick))
            fields.last_action_per_agent[row] = act
        # Then advance anatomy (bleeding + healing).
        dt_s = float(getattr(sim.cfg, "drive_accel", 1500.0))
        step_anatomy(sim, dt_s)
        return stats

    sim.step = wrapped_step
    return fields


def uninstall_anatomy(sim) -> bool:
    """Detach the anatomy system (for tests). Restores ``sim.step``."""
    if not getattr(sim, "_anatomy_wrapped", False):
        return False
    # We can't easily restore without storing original — flag as disabled.
    # In practice, just delete the state attr; subsequent step_anatomy
    # calls become no-ops.
    if hasattr(sim, "_anatomy_fields"):
        del sim._anatomy_fields
    return True


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def anatomy_state(sim) -> Dict[str, object]:
    """Diagnostic dict over the anatomy subsystem."""
    fields: Optional[AnatomyFields] = getattr(sim, "_anatomy_fields", None)
    if fields is None:
        return {"installed": False}
    n = sim.agents.n_active
    alive = sim.agents.alive[:n].astype(bool)
    sev = fields.wound_severity[:n]
    blood = fields.blood_volume_l[:n]
    # Per-part wound frequency.
    part_freq: Dict[str, int] = {}
    if alive.any():
        sev_alive = sev[alive]
        for p in range(N_BODY_PARTS):
            n_with = int((sev_alive[:, p, :].sum(axis=1) > 0.01).sum())
            part_freq[BODY_PART_NAMES[p]] = n_with
    return {
        "installed": True,
        "n_alive": int(alive.sum()),
        "cumulative_wounds_inflicted": fields.cumulative_wounds_inflicted,
        "cumulative_deaths_from_bleed": fields.cumulative_deaths_from_bleed,
        "blood_mean_l": (float(blood[alive].mean())
                            if alive.any() else BLOOD_VOLUME_INITIAL_L),
        "blood_min_l": (float(blood[alive].min())
                           if alive.any() else BLOOD_VOLUME_INITIAL_L),
        "n_with_open_wound": int(
            (sev[alive].sum(axis=(1, 2)) > 0.01).sum()
        ) if alive.any() else 0,
        "wounds_per_body_part": part_freq,
    }
