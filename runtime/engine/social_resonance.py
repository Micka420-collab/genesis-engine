"""Genesis Engine - Wave 15 social resonance (Veille 2026-05-17).

Combo veille du jour
====================

Inspiration : arxiv *The Synthetic Social Graph: Emergent Behavior in
AI Agent Communities* (2604.27271) -- analyse sociologique d'une
plateforme peuplee d'agents LLM (Moltbook, 184 203 posts / 465 136
commentaires sur 14 jours). Constat : les normes sociales emergent
mesurablement via la *coherence intra-groupe* et la *divergence
inter-groupes* sur les vecteurs comportementaux.

Wave 13 transpose cette observation a Genesis : la couche
``cognitive_plasticity`` (Wave 12) expose deja un buffer
``learned_skill[N]`` accumule par experience cognitive. En croisant
ce buffer avec ``agents.relations[i].culture_id`` (Phase 4), on peut
calculer trois metriques d'emergence civilisationnelle, sans script
ni mutation :

  * **cohesion intra-culture** : 1 - std(learned_skill_culture)/cap
    -> 1.0 = membres parfaitement homogenes (normes partagees),
       0.0 = totale dispersion.
  * **divergence inter-cultures** : Jensen-Shannon entre les
    histogrammes normalises de learned_skill par culture
    -> 0.0 = cultures cognitivement identiques,
       1.0 = cultures totalement differenciees.
  * **score d'emergence civilisationnelle** : moyenne harmonique de
    [cohesion moyenne, divergence moyenne, taux de "learners"].

Regles invariantes respectees
-----------------------------

* **Pur observateur** : aucune ecriture sur sim, agents ou plasticity.
  Le module est strictement read-only -- meme la creation d'un cache
  est interdite (recalcul instantane O(N)).
* **Aucun PRNG** : les histogrammes sont des grilles deterministes,
  Jensen-Shannon est purement arithmetique. Sous seed identique, deux
  appels successifs retournent un dict bit-identique.
* **Aucun event force** : pas d'integration dans la boucle agent ;
  le module est appele par les scripts d'audit / dashboard a la
  demande.
* **No-plasticity safe** : si ``sim.plasticity`` est absent, la
  fonction retourne des defauts neutres (cohesion=1.0 pour le cas
  uniforme zero, divergence=0.0, score=0.0).
* **Pas de mutation genetique** : la metrique ne touche jamais
  ``agents.intelligence``, ``agents.curiosity`` ou tout autre trait.

API publique
------------

>>> from engine.social_resonance import (
...     compute_social_resonance, compute_inter_culture_divergence,
...     compute_civilization_emergence_score, log_social_resonance,
... )

>>> per_culture = compute_social_resonance(sim)
>>> divergences = compute_inter_culture_divergence(sim)
>>> score = compute_civilization_emergence_score(sim)
>>> entry = log_social_resonance(sim, "journals/p43_social_resonance.jsonl")

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L5 Observatory"`` -- la metrique consomme
les buffers (L4 Feedback) pour produire un signal de haut niveau
(emergence civilisationnelle), sans retour sur les couches inferieures.
``WORLD_MODEL_CAPABILITY = "paper-L1 Observer"`` -- lecture passive
de l'etat, journalisable en JSONL pour analyse hors-ligne.
"""
from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np


# Taxonomy - see ADR 0005.
PIPELINE_LAYER = "Genesis-L5 Observatory"
WORLD_MODEL_CAPABILITY = "paper-L1 Observer"


# ---------------------------------------------------------------------------
# Constantes de discretisation
# ---------------------------------------------------------------------------
#
# Le buffer learned_skill est plafonne a LEARNED_SKILL_CAP=1.5 dans
# cognitive_plasticity. On discretise [0, 1.5] en N_BINS bins egaux
# pour calculer Jensen-Shannon. 12 bins offrent une resolution fine
# sans saturer les distributions petites (>=8 agents/culture).

#: Plafond physique du buffer plasticity (synchronise avec
#: cognitive_plasticity.LEARNED_SKILL_CAP). Garde la metrique
#: insensible aux valeurs au-dela du clip (cap dur en amont).
_SKILL_RANGE_MAX: float = 1.5

#: Nombre de bins pour la discretisation des histogrammes.
_N_BINS: int = 12

#: Floor de cohesion : sous ce nombre d'agents alive par culture,
#: la metrique de cohesion retourne NaN (statistique non fiable).
_MIN_AGENTS_FOR_COHESION: int = 3

#: Floor de divergence : sous ce nombre d'agents par culture,
#: la divergence vs. cette culture est ignoree.
_MIN_AGENTS_FOR_DIVERGENCE: int = 4

#: Seuil "learner" : un agent est compte comme apprenant actif si son
#: learned_skill > 1e-6 (synchronise avec compute_plasticity_metrics).
_LEARNER_THRESHOLD: float = 1e-6


# ---------------------------------------------------------------------------
# Helpers numeriques deterministes
# ---------------------------------------------------------------------------

def _safe_cohesion(skills: np.ndarray) -> float:
    """Return cohesion in [0, 1] : 1 = perfectly uniform, 0 = max spread.

    Defined as 1 - clip(std / (_SKILL_RANGE_MAX / 2), 0, 1). The /2
    normaliser comes from the fact that the worst-case std for a
    bounded distribution on [0, cap] reaches cap/2 (a Bernoulli on
    the endpoints). NaN if size < _MIN_AGENTS_FOR_COHESION.
    """
    n = int(skills.size)
    if n < _MIN_AGENTS_FOR_COHESION:
        return float("nan")
    std = float(np.std(skills.astype(np.float64)))
    normaliser = max(_SKILL_RANGE_MAX / 2.0, 1e-12)
    spread = min(1.0, max(0.0, std / normaliser))
    return float(1.0 - spread)


def _histogram(skills: np.ndarray) -> np.ndarray:
    """Normalised histogram on [0, _SKILL_RANGE_MAX] with _N_BINS bins.

    Returns a probability vector summing to 1.0 (or to 0.0 if input
    is empty). Bins are inclusive on the left, exclusive on the right
    except the last bin which is inclusive on both sides.
    """
    if skills.size == 0:
        return np.zeros(_N_BINS, dtype=np.float64)
    arr = np.clip(skills.astype(np.float64), 0.0, _SKILL_RANGE_MAX)
    edges = np.linspace(0.0, _SKILL_RANGE_MAX, _N_BINS + 1)
    counts, _ = np.histogram(arr, bins=edges)
    total = float(counts.sum())
    if total <= 0.0:
        return np.zeros(_N_BINS, dtype=np.float64)
    return counts.astype(np.float64) / total


def _kl(p: np.ndarray, q: np.ndarray) -> float:
    """KL divergence with epsilon smoothing, in nats."""
    eps = 1e-12
    p2 = p + eps
    q2 = q + eps
    p2 = p2 / p2.sum()
    q2 = q2 / q2.sum()
    return float((p2 * (np.log(p2) - np.log(q2))).sum())


def _js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen-Shannon divergence normalised to [0, 1].

    Defined as 0.5*KL(p||m) + 0.5*KL(q||m) where m = (p+q)/2, then
    divided by log(2) so that the maximum value (orthogonal distros)
    equals 1.0. Symmetric, bounded, smooth.
    """
    if p.size != q.size or p.size == 0:
        return float("nan")
    if p.sum() <= 0.0 or q.sum() <= 0.0:
        return float("nan")
    m = 0.5 * (p + q)
    raw = 0.5 * _kl(p, m) + 0.5 * _kl(q, m)
    # Divide by ln(2) for normalisation to [0, 1] (max JS = ln 2 in nats).
    return max(0.0, min(1.0, raw / math.log(2.0)))


def _harmonic_mean(values: List[float]) -> float:
    """Strict harmonic mean : NaN inputs are dropped, but any zero or
    negative component collapses the score to 0.0.

    Rationale : in the emergence-score context, a zero sub-signal is
    not a "missing data point" -- it is the affirmation that the
    civilisation has *no learners* (or zero cohesion, or zero
    divergence), and the composite metric must reflect that.
    """
    finite = [float(v) for v in values
              if isinstance(v, float) and math.isfinite(v)]
    if not finite:
        return 0.0
    if any(v <= 0.0 for v in finite):
        return 0.0
    return float(len(finite) / sum(1.0 / v for v in finite))


# ---------------------------------------------------------------------------
# Acces lecture-seule au buffer plasticity
# ---------------------------------------------------------------------------

def _read_learned_skill_for_alive(sim) -> Tuple[np.ndarray, np.ndarray]:
    """Return ``(skills_alive, alive_idx)`` -- read-only views.

    ``skills_alive`` is a fresh ndarray (copy), so callers cannot
    accidentally mutate the sim. Empty arrays returned if there is
    no plasticity, no agents, or all dead.
    """
    agents = sim.agents
    n = int(agents.n_active)
    if n <= 0:
        return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.int64)
    alive_idx = np.flatnonzero(agents.alive[:n])
    if alive_idx.size == 0:
        return np.zeros(0, dtype=np.float64), alive_idx
    state = getattr(sim, "plasticity", None)
    if state is None:
        # No plasticity installed -> zero buffer.
        return (np.zeros(alive_idx.size, dtype=np.float64),
                alive_idx.astype(np.int64))
    skills = state.learned_skill[alive_idx].astype(np.float64, copy=True)
    return skills, alive_idx.astype(np.int64)


def _culture_ids_for(sim, alive_idx: np.ndarray) -> np.ndarray:
    """Return per-alive culture ids as int32 ndarray. Empty -> empty."""
    if alive_idx.size == 0:
        return np.zeros(0, dtype=np.int32)
    rels = sim.agents.relations
    return np.array([int(rels[int(i)].culture_id) for i in alive_idx],
                    dtype=np.int32)


# ---------------------------------------------------------------------------
# Metriques publiques
# ---------------------------------------------------------------------------

def compute_social_resonance(sim) -> Dict[int, Dict[str, float]]:
    """Per-culture social-resonance metric.

    Returns ``{culture_id: {n_alive, learned_mean, learned_std,
    cohesion, n_learners, learner_ratio}}``. Cohesion is NaN below
    ``_MIN_AGENTS_FOR_COHESION`` alive. Cultures with zero alive are
    omitted entirely (consistent with elite_metrics behaviour).
    """
    skills, alive_idx = _read_learned_skill_for_alive(sim)
    if skills.size == 0:
        return {}
    cult_ids = _culture_ids_for(sim, alive_idx)
    result: Dict[int, Dict[str, float]] = {}
    for cid in np.unique(cult_ids):
        mask = cult_ids == cid
        s = skills[mask]
        if s.size == 0:
            continue
        n_learners = int(np.count_nonzero(s > _LEARNER_THRESHOLD))
        result[int(cid)] = {
            "n_alive": int(s.size),
            "learned_mean": float(s.mean()),
            "learned_std": float(s.std()),
            "cohesion": _safe_cohesion(s),
            "n_learners": n_learners,
            "learner_ratio": float(n_learners) / float(s.size),
        }
    return result


def compute_inter_culture_divergence(sim) -> Dict[str, float]:
    """Pairwise Jensen-Shannon divergence between cultures.

    Keys are ``"a__b"`` with ``a < b`` to keep them deterministic
    and JSON-safe. Each value is in [0, 1] (1.0 = orthogonal skill
    distributions, 0.0 = identical). Cultures with fewer than
    ``_MIN_AGENTS_FOR_DIVERGENCE`` agents are skipped entirely.
    """
    skills, alive_idx = _read_learned_skill_for_alive(sim)
    if skills.size == 0:
        return {}
    cult_ids = _culture_ids_for(sim, alive_idx)
    unique = sorted(int(c) for c in np.unique(cult_ids))
    hists: Dict[int, np.ndarray] = {}
    for cid in unique:
        mask = cult_ids == cid
        s = skills[mask]
        if s.size < _MIN_AGENTS_FOR_DIVERGENCE:
            continue
        hists[cid] = _histogram(s)
    out: Dict[str, float] = {}
    keys = sorted(hists.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            out[f"{a}__{b}"] = _js_divergence(hists[a], hists[b])
    return out


def compute_civilization_emergence_score(sim) -> Dict[str, float]:
    """Composite emergence score on [0, 1] plus its sub-components.

    The score is the harmonic mean of three sub-signals :

      * ``avg_cohesion`` -- mean of finite per-culture cohesion ;
        rewards within-culture homogeneity (shared norms).
      * ``avg_divergence`` -- mean pairwise inter-culture JS divergence ;
        rewards between-culture differentiation (distinct identities).
      * ``learner_share`` -- fraction of alive agents who have any
        learned_skill ; gates the metric to "civilisations qui
        apprennent".

    A culture cannot be "emergent" if it has zero learners, no
    cohesion, or is indistinguishable from its neighbours. The
    harmonic mean enforces that intuition by collapsing to ~0 when
    any sub-signal does.
    """
    per_culture = compute_social_resonance(sim)
    divergences = compute_inter_culture_divergence(sim)

    cohesions = [m["cohesion"] for m in per_culture.values()
                 if isinstance(m.get("cohesion"), float)
                 and math.isfinite(m["cohesion"])]
    div_values = [v for v in divergences.values()
                  if isinstance(v, float) and math.isfinite(v)]

    n_alive = sum(int(m["n_alive"]) for m in per_culture.values())
    n_learners = sum(int(m["n_learners"]) for m in per_culture.values())
    learner_share = (float(n_learners) / float(n_alive)) if n_alive > 0 else 0.0

    avg_cohesion = float(np.mean(cohesions)) if cohesions else 0.0
    avg_divergence = float(np.mean(div_values)) if div_values else 0.0

    score = _harmonic_mean([avg_cohesion, avg_divergence, learner_share])

    return {
        "score": score,
        "avg_cohesion": avg_cohesion,
        "avg_divergence": avg_divergence,
        "learner_share": learner_share,
        "n_alive": int(n_alive),
        "n_learners": int(n_learners),
        "n_cultures": int(len(per_culture)),
        "n_culture_pairs": int(len(div_values)),
    }


# ---------------------------------------------------------------------------
# Journalisation
# ---------------------------------------------------------------------------

def log_social_resonance(sim, journal_path: str,
                          extra: Optional[Dict] = None) -> Dict:
    """Append a JSONL entry combining all three measurements.

    Atomically writes one line per call. Creates the parent dir if
    needed. Returns the entry just written.
    """
    per_culture = compute_social_resonance(sim)
    divergences = compute_inter_culture_divergence(sim)
    composite = compute_civilization_emergence_score(sim)
    entry = {
        "tick": int(getattr(sim, "tick", 0)),
        "alive": int(sim.agents.alive[:sim.agents.n_active].sum()),
        "cultures": {str(k): v for k, v in per_culture.items()},
        "divergences": divergences,
        "composite": composite,
    }
    if extra:
        entry["extra"] = extra
    os.makedirs(os.path.dirname(os.path.abspath(journal_path)), exist_ok=True)
    with open(journal_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True, ensure_ascii=False))
        fh.write("\n")
    return entry


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "compute_social_resonance",
    "compute_inter_culture_divergence",
    "compute_civilization_emergence_score",
    "log_social_resonance",
]
