"""Genesis Engine — Wave 60 behavioral illumination / Quality-Diversity observer.

Read-only **diversity** companion to the Wave 58 evolutionary-activity observer
(``engine.evolutionary_activity``). Wave 58 scored the *temporal* axis of
open-endedness (does novelty keep appearing over time — Bedau–Packard). This
module scores the orthogonal *spatial* axis: **how much of the emergent
behavioral space is actually filled, and how good are the behaviors there.**

Motivation (veille 2026-06-06, piste #3 — ASAL)
-----------------------------------------------

`Kumar, Lu, Faldor, Cully & Lehman / Sakana AI — "Automating the Search for
Artificial Life" (ASAL, 2024)` formalises three measures for ALife search, one
of which is the **illumination of a diversity of a space** — i.e. covering an
open-ended behavioral space rather than optimising a single target. The veille
flags this as a top-3, ``ZERO PRE-SCRIPT``-compatible build target because it is
a *read-only observation/evaluation layer* (not in the hot path) and quantifies
emergent novelty without scripting outcomes.

ASAL's reference implementation leans on a foundation **vision-language model**
to define the behavioral descriptor; that is an external, non-deterministic
dependency Genesis deliberately avoids in its deterministic tick. So this Wave
ports the *measure*, not the *VLM*: it implements the classical, fully
deterministic CPU primitives the ASAL illumination measure is built on —
**MAP-Elites** archives (Mouret & Clune 2015) and **novelty search** behavioral
distance (Lehman & Stanley 2011) — over an emergent behavioral descriptor read
straight from the agents. The "VLM descriptor" remains an honest backlog gap.

What it measures
----------------

Given a list of *(behavior descriptor, quality)* pairs — one per emergent agent
— the observer discretises the descriptor space into a regular grid of niches
and keeps, per niche, the **elite** (best-quality behavior). From that archive:

* **coverage**       — occupied niches / total niches ∈ [0, 1] (illumination).
* **qd_score**       — Σ elite quality over occupied niches (quality-diversity).
* **niche_entropy**  — Shannon entropy of the elite-quality distribution,
  normalised to [0, 1]; 1.0 ⇔ quality spread evenly across filled niches.
* **behavioral novelty** — mean distance of each behavior to its ``k`` nearest
  neighbours in descriptor space (sparsity of the behavior cloud).
* mean / max quality, occupied-niche count, best niche.

Behavioral descriptor & quality (emergent, never scripted)
----------------------------------------------------------

The default adapter reads per-agent **emergent personality traits** (the
Big-Five + Genesis traits inherited at ``spawn_offspring``) as the descriptor
axes and the agent's **reproductive success** (``offspring_count``) as the
quality. Both are produced by the simulation itself — the observer never
declares which behaviors *should* exist or assigns a target; it only reports how
the emergent population fills the space. Read-only on ``sim.agents`` arrays.

Observer contract (mirrors Waves 49 / 53 / 55 / 57 / 58)
--------------------------------------------------------

``IlluminationConfig`` / ``IlluminationStats`` / ``IlluminationSnapshot`` /
``IlluminationHistory`` / ``IlluminationState`` dataclasses; pure world-free
archive/metric functions; ``observe_illumination`` (read-only); idempotent
``install_illumination_observer`` / ``uninstall_...`` wrapping ``sim.step``
once; ``illumination_summary`` diagnostic dict.

Determinism
-----------

No RNG. Discretisation is integer ``floor`` arithmetic, the archive keeps a
stable tie-break (first-seen index on equal quality), novelty uses a full
pairwise distance sort, and the snapshot signature is ``sha256`` of a canonical
rounded tuple. Two runs with the same world seed produce identical illumination
streams.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# A behavior = a descriptor vector in R^d ; quality = a scalar fitness proxy.
Descriptor = Sequence[float]
Behavior = Tuple[Descriptor, float]
NicheKey = Tuple[int, ...]

# Default emergent descriptor axes (subset of the inherited personality traits)
# and the emergent quality field. All produced by ``spawn_offspring`` — no
# scripted target. Kept to two axes so the niche grid stays interpretable.
DEFAULT_DESCRIPTOR_TRAITS: Tuple[str, ...] = ("curiosity", "aggression")
DEFAULT_QUALITY_FIELD: str = "offspring_count"


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IlluminationConfig:
    """Read-only knobs for the behavioral illumination observer.

    Defaults assume trait axes already normalised to ``[0, 1]`` (as the Genesis
    personality traits are) binned into a ``bins`` × ``bins`` MAP-Elites grid.
    ``min_quality`` keeps the quality floor at zero so a never-reproducing agent
    still *occupies* its niche (coverage counts presence, quality may be 0).
    """
    bins: int = 8                       # niches per descriptor axis
    descriptor_lo: float = 0.0          # lower bound of each axis
    descriptor_hi: float = 1.0          # upper bound of each axis
    novelty_k: int = 3                  # neighbours for behavioral novelty
    min_quality: float = 0.0            # quality floor (presence still counts)
    snapshot_every: int = 64
    descriptor_traits: Tuple[str, ...] = DEFAULT_DESCRIPTOR_TRAITS
    quality_field: str = DEFAULT_QUALITY_FIELD


@dataclass(frozen=True)
class IlluminationStats:
    """Quality-Diversity / illumination statistics for one behavior set."""
    n_behaviors: int
    n_dims: int
    bins: int
    total_niches: int
    occupied_niches: int
    coverage: float                     # occupied / total ∈ [0, 1]
    qd_score: float                     # Σ elite quality
    mean_quality: float
    max_quality: float
    niche_entropy: float                # normalised Shannon ∈ [0, 1]
    behavioral_novelty: float           # mean k-NN descriptor distance
    best_niche: Optional[NicheKey]


@dataclass(frozen=True)
class IlluminationSnapshot:
    tick: int
    stats: IlluminationStats
    signature: str


@dataclass
class IlluminationHistory:
    snapshots: List[IlluminationSnapshot] = field(default_factory=list)


@dataclass
class IlluminationState:
    config: IlluminationConfig
    history: IlluminationHistory = field(default_factory=IlluminationHistory)
    wrapped: bool = False


# ---------------------------------------------------------------------------
# Pure-function MAP-Elites / novelty primitives  (world-free, unit-testable)
# ---------------------------------------------------------------------------

def discretize(descriptor: Descriptor, bins: int,
               lo: float = 0.0, hi: float = 1.0) -> NicheKey:
    """Map a descriptor vector to its integer niche coordinates (floor binning).

    Values are clamped to ``[lo, hi]`` then scaled to ``[0, bins-1]``. Pure
    integer arithmetic ⇒ bit-deterministic. ``hi`` maps to the last bin.
    """
    if bins < 1:
        raise ValueError("bins must be >= 1")
    span = float(hi) - float(lo)
    out: List[int] = []
    for v in descriptor:
        if span <= 0.0:
            idx = 0
        else:
            frac = (float(v) - float(lo)) / span
            frac = min(max(frac, 0.0), 1.0)
            idx = int(math.floor(frac * bins))
            if idx >= bins:
                idx = bins - 1
        out.append(idx)
    return tuple(out)


def build_archive(behaviors: Sequence[Behavior], bins: int,
                  lo: float = 0.0, hi: float = 1.0
                  ) -> Dict[NicheKey, float]:
    """MAP-Elites archive: best (highest) quality per occupied niche.

    Deterministic tie-break: on equal quality the first-seen behavior wins (the
    archive is only overwritten on a *strictly* greater quality).
    """
    archive: Dict[NicheKey, float] = {}
    for descriptor, quality in behaviors:
        key = discretize(descriptor, bins, lo, hi)
        q = float(quality)
        if key not in archive or q > archive[key]:
            archive[key] = q
    return archive


def coverage(archive: Dict[NicheKey, float], total_niches: int) -> float:
    """Fraction of niches occupied (the illumination measure) ∈ [0, 1]."""
    if total_niches <= 0:
        return 0.0
    return float(len(archive)) / float(total_niches)


def qd_score(archive: Dict[NicheKey, float]) -> float:
    """Quality-Diversity score: Σ of elite qualities over occupied niches."""
    if not archive:
        return 0.0
    return float(sum(archive.values()))


def niche_entropy(archive: Dict[NicheKey, float]) -> float:
    """Normalised Shannon entropy of the elite-quality distribution ∈ [0, 1].

    Quality 0 niches contribute presence but no probability mass; when every
    elite quality is 0 the distribution is taken uniform over occupied niches
    (pure presence ⇒ maximal evenness). 1.0 ⇔ quality spread perfectly evenly.
    """
    n = len(archive)
    if n <= 1:
        return 0.0
    vals = np.fromiter((max(v, 0.0) for v in archive.values()),
                       dtype=np.float64, count=n)
    total = float(vals.sum())
    if total <= 0.0:
        p = np.full(n, 1.0 / n, dtype=np.float64)
    else:
        p = vals / total
    nz = p > 0.0
    h = float(-(p[nz] * np.log(p[nz])).sum())
    return h / math.log(n)


def behavioral_novelty(descriptors: Sequence[Descriptor], k: int = 3) -> float:
    """Mean distance of each behavior to its ``k`` nearest neighbours.

    The novelty-search sparsity metric (Lehman & Stanley 2011). With fewer than
    two behaviors novelty is 0. ``k`` is clamped to ``n-1``. Euclidean distance
    over the (assumed normalised) descriptor space; deterministic full sort.
    """
    n = len(descriptors)
    if n < 2:
        return 0.0
    pts = np.asarray([[float(c) for c in d] for d in descriptors],
                     dtype=np.float64)
    kk = min(max(int(k), 1), n - 1)
    # Pairwise Euclidean distances (n is small: full matrix is fine, exact).
    diff = pts[:, None, :] - pts[None, :, :]
    dist = np.sqrt((diff * diff).sum(axis=2))
    np.fill_diagonal(dist, np.inf)
    dist.sort(axis=1)                       # ascending; nearest first
    knn = dist[:, :kk]
    return float(knn.mean())


def illumination_stats(behaviors: Sequence[Behavior],
                       cfg: Optional[IlluminationConfig] = None
                       ) -> IlluminationStats:
    """Full Quality-Diversity / illumination bundle for a behavior set (pure)."""
    cfg = cfg or IlluminationConfig()
    bins = cfg.bins
    descriptors = [b[0] for b in behaviors]
    n_dims = len(descriptors[0]) if descriptors else len(cfg.descriptor_traits)
    total_niches = bins ** n_dims if n_dims > 0 else 0

    archive = build_archive(behaviors, bins, cfg.descriptor_lo,
                            cfg.descriptor_hi)
    cov = coverage(archive, total_niches)
    qd = qd_score(archive)
    occupied = len(archive)
    if archive:
        vals = np.fromiter(archive.values(), dtype=np.float64, count=occupied)
        mean_q = float(vals.mean())
        max_q = float(vals.max())
        best = max(archive.items(), key=lambda kv: (kv[1], kv[0]))[0]
    else:
        mean_q = 0.0
        max_q = 0.0
        best = None
    ent = niche_entropy(archive)
    nov = behavioral_novelty(descriptors, cfg.novelty_k)

    return IlluminationStats(
        n_behaviors=len(behaviors),
        n_dims=n_dims,
        bins=bins,
        total_niches=total_niches,
        occupied_niches=occupied,
        coverage=cov,
        qd_score=qd,
        mean_quality=mean_q,
        max_quality=max_q,
        niche_entropy=ent,
        behavioral_novelty=nov,
        best_niche=best,
    )


# ---------------------------------------------------------------------------
# Snapshot / signature
# ---------------------------------------------------------------------------

def _stats_signature(tick: int, stats: IlluminationStats) -> str:
    """sha256 of a canonical, language-neutral representation."""
    seed = (
        int(tick),
        stats.n_behaviors,
        stats.n_dims,
        stats.bins,
        stats.total_niches,
        stats.occupied_niches,
        round(stats.coverage, 6),
        round(stats.qd_score, 6),
        round(stats.mean_quality, 6),
        round(stats.max_quality, 6),
        round(stats.niche_entropy, 6),
        round(stats.behavioral_novelty, 6),
        stats.best_niche,
    )
    return hashlib.sha256(repr(seed).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Emergent behavior extraction (read-only world reads)
# ---------------------------------------------------------------------------

def agent_behaviors(sim,
                    cfg: Optional[IlluminationConfig] = None
                    ) -> List[Behavior]:
    """Read the emergent per-agent *(descriptor, quality)* pairs from the sim.

    Pure read-only. Descriptor axes are the configured emergent traits; quality
    is the configured emergent field (default ``offspring_count`` — reproductive
    success). Only **alive** agents are read. Defensive: returns ``[]`` if the
    sim exposes no agents or none of the descriptor traits, so the observer
    degrades gracefully when a subsystem is not wired.
    """
    cfg = cfg or IlluminationConfig()
    agents = getattr(sim, "agents", None)
    if agents is None:
        return []
    n = int(getattr(agents, "n_active", 0) or 0)
    if n <= 0:
        return []

    alive = getattr(agents, "alive", None)
    if alive is not None:
        mask = np.asarray(alive[:n], dtype=bool)
    else:
        mask = np.ones(n, dtype=bool)

    axes: List[np.ndarray] = []
    for trait in cfg.descriptor_traits:
        arr = getattr(agents, trait, None)
        if arr is None:
            return []
        axes.append(np.asarray(arr[:n], dtype=np.float64))
    if not axes:
        return []

    q_arr = getattr(agents, cfg.quality_field, None)
    if q_arr is not None:
        quality = np.asarray(q_arr[:n], dtype=np.float64)
    else:
        quality = np.zeros(n, dtype=np.float64)

    rows = np.flatnonzero(mask)
    behaviors: List[Behavior] = []
    floor = float(cfg.min_quality)
    for r in rows:
        descriptor = tuple(float(ax[r]) for ax in axes)
        q = max(float(quality[r]), floor)
        behaviors.append((descriptor, q))
    return behaviors


# ---------------------------------------------------------------------------
# Observe (read-only)
# ---------------------------------------------------------------------------

def observe_illumination(sim, config: Optional[IlluminationConfig] = None
                         ) -> Optional[IlluminationSnapshot]:
    """Pure read-only illumination snapshot.

    Reads the emergent agent behaviors, computes the Quality-Diversity /
    illumination statistics, and returns a snapshot. Never mutates the sim;
    returns ``None`` when no emergent behavior is available.
    """
    cfg = config if config is not None else IlluminationConfig()
    behaviors = agent_behaviors(sim, cfg)
    if not behaviors:
        return None
    stats = illumination_stats(behaviors, cfg)
    tick = int(getattr(sim, "tick", 0))
    return IlluminationSnapshot(
        tick=tick, stats=stats, signature=_stats_signature(tick, stats))


# ---------------------------------------------------------------------------
# Install / uninstall (mirrors waves 49 / 53 / 55 / 57 / 58)
# ---------------------------------------------------------------------------

def install_illumination_observer(
        sim, config: Optional[IlluminationConfig] = None) -> IlluminationState:
    """Idempotent installer. Wraps ``sim.step`` once to capture an illumination
    snapshot every ``snapshot_every`` ticks (read-only)."""
    cfg = config if config is not None else IlluminationConfig()
    existing: Optional[IlluminationState] = getattr(
        sim, "_illumination_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = IlluminationState(config=cfg)
    sim._illumination_state = state

    original_step = sim.step

    def _wrapped_step(*args, **kwargs):
        result = original_step(*args, **kwargs)
        try:
            tick = int(sim.tick)
        except Exception:
            tick = 0
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            snap = observe_illumination(sim, cfg)
            if snap is not None:
                state.history.snapshots.append(snap)
        return result

    sim._illumination_original_step = original_step
    sim.step = _wrapped_step
    state.wrapped = True
    sim._illumination_wrapped = True
    return state


def uninstall_illumination_observer(sim) -> bool:
    """Restore the original ``sim.step``. ``True`` if anything was removed."""
    state = getattr(sim, "_illumination_state", None)
    if state is None:
        return False
    original = getattr(sim, "_illumination_original_step", None)
    if original is not None:
        sim.step = original
        del sim._illumination_original_step
    sim._illumination_wrapped = False
    del sim._illumination_state
    return True


def illumination_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards / ``/api/emergence_metrics`` (read-only)."""
    state: Optional[IlluminationState] = getattr(
        sim, "_illumination_state", None)
    if state is None:
        return {"installed": False}
    snaps = state.history.snapshots
    last = snaps[-1] if snaps else None
    s = last.stats if last is not None else None
    return {
        "installed": True,
        "n_snapshots": len(snaps),
        "snapshot_every": state.config.snapshot_every,
        "bins": state.config.bins,
        "descriptor_traits": list(state.config.descriptor_traits),
        "quality_field": state.config.quality_field,
        "last_signature": (last.signature if last is not None else None),
        "last_tick": (last.tick if last is not None else None),
        "coverage": (s.coverage if s is not None else None),
        "qd_score": (s.qd_score if s is not None else None),
        "occupied_niches": (s.occupied_niches if s is not None else None),
        "niche_entropy": (s.niche_entropy if s is not None else None),
        "behavioral_novelty": (s.behavioral_novelty if s is not None else None),
    }


__all__ = [
    "IlluminationConfig",
    "IlluminationStats",
    "IlluminationSnapshot",
    "IlluminationHistory",
    "IlluminationState",
    "discretize",
    "build_archive",
    "coverage",
    "qd_score",
    "niche_entropy",
    "behavioral_novelty",
    "illumination_stats",
    "agent_behaviors",
    "observe_illumination",
    "install_illumination_observer",
    "uninstall_illumination_observer",
    "illumination_summary",
]
