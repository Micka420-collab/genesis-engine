"""Genesis Engine — Wave 12 cognitive plasticity (Veille 2026-05-16).

Combo veille du jour
====================

Inspiration : *Project Sid: Many-agent simulations toward AI civilization*
(arxiv 2411.00114) — PIANO cognitive architecture, modules concurrents
partageant un Agent State évolutif.

Observation Wave 11 (`engine.elite_metrics`) : Hill α ≈ 3.98–4.50 sur
Léman 16 founders × 250 ticks. Queues courtes : la cognition reste
*génétique-statique* (intelligence héritée + mutation à la naissance,
puis figée à vie). Aucun mécanisme ne récompense l'effort cognitif
soutenu d'un individu — ce qui exclut par construction l'apparition
de classes cognitives à la Pareto.

Wave 12 introduit un **buffer additif** :

    intelligence_effective(row) = clip(
        intelligence_base(row) + learned_skill(row),
        0.0, 1.0,
    )

`learned_skill` est accumulé par l'expérience d'**actions cognitivement
coûteuses** (BUILD, SMELT, MINE, HARVEST, INVENT, SPEAK avec lexique).
La règle d'apprentissage est Hebbienne pondérée par la curiosité
individuelle (`curiosity[row]`). Une décroissance lente (oubli) évite
la saturation et préserve la possibilité de régression cognitive
sous stress.

Règles invariantes respectées
-----------------------------

* **Émergence pure** : aucun seuil ne déclenche un comportement
  scripté. Le module n'observe-modifie qu'un buffer additif. Les
  décisions agent restent prises par `engine.cognition`.
* **Déterminisme** : aucun appel à un PRNG. Les coefficients sont
  des constantes lues. `record_experience` est idempotente sous
  ordre identique d'événements (la simulation reste reproductible
  sous seed identique).
* **Aucun rewrite** : `agent.intelligence` (génétique) n'est jamais
  modifiée par ce module. L'héritage Phase 4 (méiose statistique
  parent_a/parent_b + mutation gaussienne) reste l'unique source
  du trait de base.
* **Persistence event-sourcing** : `save_plasticity_state` /
  `load_plasticity_state` permettent un round-trip parfait.

API publique
------------

>>> from engine.cognitive_plasticity import (
...     install_plasticity, record_experience,
...     intelligence_effective, decay_step,
...     compute_plasticity_metrics,
... )

>>> install_plasticity(sim)
>>> record_experience(sim, row=3, action_kind=int(ActionKind.SMELT))
>>> eff = intelligence_effective(sim, row=3)

Intégration avec `elite_metrics`
--------------------------------

`engine.elite_metrics.compute_elite_metrics_effective(sim)` (helper
ajouté en aval) utilise `intelligence_effective` au lieu de
`intelligence_base`. C'est par cette voie que l'hypothèse paper-Wave 11
peut être testée : Hill α effective devrait descendre vers ~2.0
quand des élites cognitives émergent par expérience.

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — l'expérience cumulée des
actions cognitives (BUILD, SMELT, INVENT, …) revient sur la cognition
agent via ``intelligence_effective``, fermant la boucle (action →
apprentissage → meilleure décision → action plus complexe).
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — composable :
applicable comme observation passive (W11) ou comme update actif
(W12), réversible via decay_step, persistante via npz.
"""
from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

import numpy as np

from engine.agent import ActionKind


# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"


# ---------------------------------------------------------------------------
# Coefficients de plasticité (constants déterministes)
# ---------------------------------------------------------------------------
#
# Calibration : valeurs faibles pour que l'effet soit visible sur
# 200–500 ticks de simulation mais sans saturer à 1.0 en moins de
# 50 ticks. Le modèle vise une accumulation lente, hebbienne, qui
# ne supplante pas la génétique mais l'amplifie en queue.

#: Gain par action selon sa complexité cognitive estimée.
#: SMELT et INVENT sont les plus coûteux (raisonnement causal),
#: SPEAK est faible (geste social fréquent), idle/walk → 0.
COMPLEXITY_WEIGHT: Dict[int, float] = {
    int(ActionKind.IDLE):         0.0,
    int(ActionKind.WALK_TO):      0.0,
    int(ActionKind.DRINK):        0.0,
    int(ActionKind.EAT):          0.0,
    int(ActionKind.SLEEP):        0.0,
    int(ActionKind.FORAGE):       0.002,
    int(ActionKind.SEEK_SHELTER): 0.001,
    int(ActionKind.MATE):         0.0,
    int(ActionKind.SPEAK):        0.004,
    int(ActionKind.SHARE):        0.003,
    int(ActionKind.FIGHT):        0.001,
    int(ActionKind.BUILD):        0.012,
    int(ActionKind.FLEE):         0.0,
    int(ActionKind.EXPLORE):      0.002,
    int(ActionKind.HUNT):         0.006,
    int(ActionKind.PLANT):        0.004,
    int(ActionKind.HARVEST):      0.006,
    int(ActionKind.MINE):         0.008,
    int(ActionKind.SMELT):        0.018,
}

#: Coefficient d'oubli appliqué par `decay_step` (multiplicatif).
#: 0.9995 par tick ≈ ½-vie ≈ 1385 ticks (~16 jours sim si 1 tick = 1s
#: sim, ou 1.5 sim-an si drive_accel 100). Réglable.
DEFAULT_DECAY: float = 0.9995

#: Plafond dur du buffer learned_skill, en plus du clip [0,1] de
#: l'effective. Garantit qu'un buffer ne déborde pas avant clip.
LEARNED_SKILL_CAP: float = 1.5

#: Curiosity gating : un agent à curiosity=0 apprend à 50 %, un agent
#: à curiosity=1 apprend à 150 %. Centre sur 1.0 à curiosity=0.5
#: (valeur par défaut spawn).
_CURIOSITY_FLOOR: float = 0.5
_CURIOSITY_SLOPE: float = 1.0


# ---------------------------------------------------------------------------
# Données
# ---------------------------------------------------------------------------

@dataclass
class PlasticityState:
    """Per-agent learning buffer.

    Attribute on `sim` is `sim.plasticity`. Lazy install via
    :func:`install_plasticity` keeps Wave 12 strictly opt-in : the
    Phase 4 / Wave 11 codebase keeps running untouched if the module
    is not imported.
    """

    capacity: int
    learned_skill: np.ndarray = field(default=None)
    n_events_total: int = 0
    decay: float = DEFAULT_DECAY

    def __post_init__(self) -> None:
        if self.learned_skill is None:
            self.learned_skill = np.zeros(self.capacity, dtype=np.float32)


def install_plasticity(sim, decay: float = DEFAULT_DECAY) -> PlasticityState:
    """Attach a fresh :class:`PlasticityState` to *sim*.

    Idempotent : if `sim.plasticity` already exists, returns it.
    """
    existing = getattr(sim, "plasticity", None)
    if isinstance(existing, PlasticityState):
        return existing
    cap = int(sim.agents.capacity)
    state = PlasticityState(capacity=cap, decay=float(decay))
    sim.plasticity = state
    return state


def _curiosity_factor(curiosity: float) -> float:
    """Linear curiosity → [0.5, 1.5] gating factor.

    Centered on 1.0 at curiosity=0.5. Determinism-safe (pure arithmetic).
    """
    c = max(0.0, min(1.0, float(curiosity)))
    return _CURIOSITY_FLOOR + _CURIOSITY_SLOPE * c


# ---------------------------------------------------------------------------
# Boucle d'apprentissage
# ---------------------------------------------------------------------------

def record_experience(sim, row: int, action_kind: int,
                      intensity: float = 1.0) -> float:
    """Increment `learned_skill[row]` by an experience event.

    Returns the new buffer value (post-clip). No-op if plasticity not
    installed, or if action is non-cognitive (weight 0), or if row
    is dead. Determinism is preserved : pure read of curiosity[row],
    pure write of learned_skill[row].
    """
    state = getattr(sim, "plasticity", None)
    if state is None:
        return 0.0
    agents = sim.agents
    if row < 0 or row >= agents.n_active:
        return 0.0
    if not bool(agents.alive[row]):
        return float(state.learned_skill[row])

    base_weight = COMPLEXITY_WEIGHT.get(int(action_kind), 0.0)
    if base_weight <= 0.0:
        return float(state.learned_skill[row])

    factor = _curiosity_factor(float(agents.curiosity[row]))
    delta = base_weight * factor * max(0.0, float(intensity))

    new = float(state.learned_skill[row]) + delta
    new = max(0.0, min(LEARNED_SKILL_CAP, new))
    state.learned_skill[row] = np.float32(new)
    state.n_events_total += 1
    return new


def record_experience_batch(sim, events: Iterable) -> int:
    """Apply a stream of (row, action_kind[, intensity]) tuples.

    Returns the count of events actually applied (weight>0 & alive).
    """
    applied = 0
    for ev in events:
        if len(ev) == 2:
            row, kind = ev
            intensity = 1.0
        else:
            row, kind, intensity = ev[0], ev[1], ev[2]
        before = 0.0
        state = getattr(sim, "plasticity", None)
        if state is not None and 0 <= int(row) < int(sim.agents.n_active):
            before = float(state.learned_skill[int(row)])
        after = record_experience(sim, int(row), int(kind), float(intensity))
        if after != before:
            applied += 1
    return applied


def decay_step(sim, factor: Optional[float] = None) -> None:
    """Apply one multiplicative forgetting step to the entire buffer.

    Cheap O(N) numpy op. Determinism-safe (no PRNG). Call once per
    sim tick if you want forgetting wired into the main loop ; the
    smoke test exercises this path explicitly without sim wiring.
    """
    state = getattr(sim, "plasticity", None)
    if state is None:
        return
    f = float(state.decay if factor is None else factor)
    if f >= 1.0:
        return
    state.learned_skill *= np.float32(f)


# ---------------------------------------------------------------------------
# Effective intelligence accessors
# ---------------------------------------------------------------------------

def intelligence_effective(sim, row: int) -> float:
    """Return `clip(intelligence_base + learned_skill, 0, 1)` for a row."""
    base = float(sim.agents.intelligence[row])
    state = getattr(sim, "plasticity", None)
    bonus = float(state.learned_skill[row]) if state is not None else 0.0
    return max(0.0, min(1.0, base + bonus))


def intelligence_effective_array(sim) -> np.ndarray:
    """Vectorised version : returns clipped float32 array of size n_active."""
    n = int(sim.agents.n_active)
    base = sim.agents.intelligence[:n].astype(np.float32)
    state = getattr(sim, "plasticity", None)
    if state is None:
        return np.clip(base, 0.0, 1.0)
    bonus = state.learned_skill[:n]
    return np.clip(base + bonus, 0.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Metrics & inspection
# ---------------------------------------------------------------------------

def compute_plasticity_metrics(sim) -> Dict[str, float]:
    """Lightweight stats for dashboards / sprint reports."""
    state = getattr(sim, "plasticity", None)
    n = int(sim.agents.n_active)
    if state is None or n == 0:
        return {
            "n_active": n,
            "learned_mean": 0.0, "learned_std": 0.0,
            "learned_max": 0.0, "n_events_total": 0,
            "n_learners": 0,
        }
    alive_mask = sim.agents.alive[:n]
    arr = state.learned_skill[:n][alive_mask]
    if arr.size == 0:
        return {
            "n_active": n,
            "learned_mean": 0.0, "learned_std": 0.0,
            "learned_max": 0.0, "n_events_total": int(state.n_events_total),
            "n_learners": 0,
        }
    return {
        "n_active": int(n),
        "learned_mean": float(arr.mean()),
        "learned_std": float(arr.std()),
        "learned_max": float(arr.max()),
        "n_events_total": int(state.n_events_total),
        "n_learners": int(np.count_nonzero(arr > 1e-6)),
    }


# ---------------------------------------------------------------------------
# Persistence (event-sourcing friendly : full state in two arrays)
# ---------------------------------------------------------------------------

_PLASTICITY_FILENAME = "plasticity.npz"


def save_plasticity_state(sim, world_dir: str) -> Optional[str]:
    """Persist plasticity buffer to <world_dir>/plasticity.npz.

    Returns the path written, or None if plasticity not installed.
    Skipped silently if the directory is unwritable rather than
    crashing — Wave 12 is non-critical to world load.
    """
    state = getattr(sim, "plasticity", None)
    if state is None:
        return None
    path = os.path.join(world_dir, _PLASTICITY_FILENAME)
    try:
        os.makedirs(world_dir, exist_ok=True)
        np.savez(
            path,
            learned_skill=state.learned_skill,
            meta=np.array([state.capacity, state.n_events_total], dtype=np.int64),
            decay=np.array([state.decay], dtype=np.float64),
        )
        return path
    except OSError:
        return None


def load_plasticity_state(sim, world_dir: str) -> bool:
    """Restore plasticity from <world_dir>/plasticity.npz if present.

    Returns True if restored. If the file is missing, a fresh state
    is installed (zeros) and False is returned.
    """
    path = os.path.join(world_dir, _PLASTICITY_FILENAME)
    if not os.path.isfile(path):
        install_plasticity(sim)
        return False
    data = np.load(path)
    meta = data["meta"]
    cap = int(meta[0])
    n_events = int(meta[1])
    decay = float(data["decay"][0])
    state = PlasticityState(capacity=cap, decay=decay)
    saved = data["learned_skill"].astype(np.float32, copy=True)
    # Resize if capacity differs (agents capacity can grow between runs).
    target_cap = int(sim.agents.capacity)
    if target_cap != saved.size:
        new_buf = np.zeros(target_cap, dtype=np.float32)
        n_copy = min(target_cap, saved.size)
        new_buf[:n_copy] = saved[:n_copy]
        state.learned_skill = new_buf
        state.capacity = target_cap
    else:
        state.learned_skill = saved
        state.capacity = cap
    state.n_events_total = n_events
    sim.plasticity = state
    return True


# ---------------------------------------------------------------------------
# Optional convenience : a single helper that consumes a sim tick's
# action ledger. The smoke test exercises this path.
# ---------------------------------------------------------------------------

def tick_step(sim, action_events: Iterable, apply_decay: bool = True) -> int:
    """One-shot per-tick update : record events then optional decay.

    `action_events` is an iterable of (row, action_kind) or
    (row, action_kind, intensity). Returns the number of events
    that produced a non-zero learning delta.
    """
    n = record_experience_batch(sim, action_events)
    if apply_decay:
        decay_step(sim)
    return n


__all__ = [
    "PlasticityState",
    "COMPLEXITY_WEIGHT",
    "DEFAULT_DECAY",
    "LEARNED_SKILL_CAP",
    "install_plasticity",
    "record_experience",
    "record_experience_batch",
    "decay_step",
    "tick_step",
    "intelligence_effective",
    "intelligence_effective_array",
    "compute_plasticity_metrics",
    "save_plasticity_state",
    "load_plasticity_state",
]
