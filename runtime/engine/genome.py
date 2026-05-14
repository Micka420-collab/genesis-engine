"""Sprint A4 — Genome 256-d + 8 life stages.

Implements the Genesis Engine biology/genetics layer (architecture
sections 11, 12 and 13) as a non-invasive add-on:

* A 256-dimensional float32 genome per agent, organised in 4 groups of
  64 genes (appearance / cognition / health / longevity).
* Meiosis-style crossover with per-gene 1e-4 mutation.
* 8 discrete life stages (infant -> ancient) computed from
  ``(tick - born_tick) / (lifespan_ticks / 8)`` with a per-stage cognitive
  efficiency multiplier modulating decision confidence.

The module never rewrites :mod:`engine.agent`, :mod:`engine.sim` nor
:mod:`engine.cognition`. It is installed at bootstrap by
``sim_5cd_integration.install`` and hooks itself onto
``Simulation._resolve_matings`` via a monkey-patch.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Optional

import numpy as np

from engine.core import prf_rng


# ---------------------------------------------------------------------------
# Genome layout
# ---------------------------------------------------------------------------

GENOME_SIZE = 256
GROUP_SIZE = 64

GENE_GROUP_APPEARANCE = slice(0, 64)
GENE_GROUP_COGNITION = slice(64, 128)
GENE_GROUP_HEALTH = slice(128, 192)
GENE_GROUP_LONGEVITY = slice(192, 256)

# Mutation rate per gene per birth (section 12).
MUTATION_RATE = 1.0e-4
# Standard deviation of a mutation event when it fires.
MUTATION_SIGMA = 0.10


# ---------------------------------------------------------------------------
# Life stages (8 stages, section 11)
# ---------------------------------------------------------------------------

class LifeStage(IntEnum):
    INFANT = 0
    CHILD = 1
    ADOLESCENT = 2
    YOUNG_ADULT = 3
    ADULT = 4
    MIDDLE_AGE = 5
    ELDER = 6
    ANCIENT = 7


_LIFE_STAGE_NAMES = (
    "infant", "child", "adolescent", "young_adult",
    "adult", "middle_age", "elder", "ancient",
)


# Cognitive efficiency per life-stage: peak at young-adult / adult, decay at
# the extremes (newborns and very old). Matches §11: "dégradation progressive
# de la performance cognitive".
_COG_EFF = np.array(
    [0.30, 0.60, 0.85, 1.00, 1.00, 0.90, 0.75, 0.50],
    dtype=np.float32,
)


def life_stage_name(stage: LifeStage) -> str:
    return _LIFE_STAGE_NAMES[int(stage)]


def cognitive_efficiency(stage: LifeStage) -> float:
    """Return the cognitive performance multiplier for ``stage`` in [0, 1]."""
    return float(_COG_EFF[int(stage)])


# ---------------------------------------------------------------------------
# Genome attachment / inheritance
# ---------------------------------------------------------------------------

def _founder_genome(world_seed: int, founder_idx: int) -> np.ndarray:
    """Build a deterministic 256-d genome for a founder."""
    rng = prf_rng(world_seed, ["agent", "genome", "founder"], [int(founder_idx)])
    return rng.random(GENOME_SIZE, dtype=np.float32)


def attach_genome(agents, world_seed: int) -> None:
    """Attach a 256-d genome array to ``agents`` (idempotent).

    Founders that already exist on the registry are seeded immediately with a
    deterministic per-(seed, founder_idx) genome. Subsequent births are
    handled by :func:`install_genome_inheritance`.
    """
    N = agents.capacity
    if getattr(agents, "_genome_attached", False):
        # Idempotent: still make sure any newly-added founders have a genome.
        for row in range(agents.n_active):
            if not bool(agents._genome_seeded[row]):
                agents.genome[row] = _founder_genome(world_seed, row)
                agents._genome_seeded[row] = True
        return

    agents.genome = np.zeros((N, GENOME_SIZE), dtype=np.float32)
    agents._genome_seeded = np.zeros(N, dtype=bool)
    agents._genome_attached = True

    for row in range(agents.n_active):
        agents.genome[row] = _founder_genome(world_seed, row)
        agents._genome_seeded[row] = True


def gene_to_trait(genome: np.ndarray, group: slice) -> float:
    """Map a gene group to a scalar trait in [0, 1] (mean of the group)."""
    return float(genome[group].mean())


def crossover(
    genome_a: np.ndarray,
    genome_b: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Meiosis-simplified crossover with per-gene mask and 1e-4 mutation.

    Each gene is independently inherited from parent A or B with 50/50
    probability. After recombination, every gene has a ``MUTATION_RATE``
    chance of receiving a Gaussian perturbation (sigma = ``MUTATION_SIGMA``),
    clipped to [0, 1].
    """
    a = np.asarray(genome_a, dtype=np.float32)
    b = np.asarray(genome_b, dtype=np.float32)
    if a.shape != (GENOME_SIZE,) or b.shape != (GENOME_SIZE,):
        raise ValueError(
            f"genomes must be ({GENOME_SIZE},), got {a.shape} and {b.shape}"
        )
    mask = rng.random(GENOME_SIZE) < 0.5
    child = np.where(mask, a, b).astype(np.float32, copy=False)

    # Per-gene mutations (1e-4 fire-rate).
    mut_mask = rng.random(GENOME_SIZE) < MUTATION_RATE
    if mut_mask.any():
        deltas = rng.normal(0.0, MUTATION_SIGMA, size=GENOME_SIZE).astype(np.float32)
        child = child + mut_mask.astype(np.float32) * deltas
        np.clip(child, 0.0, 1.0, out=child)
    return child


# ---------------------------------------------------------------------------
# Life stage lookup
# ---------------------------------------------------------------------------

def _life_stage_from_age_ratio(ratio: float) -> LifeStage:
    """Map an age/lifespan ratio in [0, +inf) onto one of 8 stages."""
    if ratio < 0.0:
        ratio = 0.0
    idx = int(ratio * 8)
    if idx > 7:
        idx = 7
    return LifeStage(idx)


def current_life_stage(agents, row: int, sim) -> LifeStage:
    """Return the current life stage of ``agents[row]`` at ``sim.tick``.

    Computed as ``(sim.tick - born_tick) / (lifespan_ticks / 8)``, with the
    same drive-acceleration scaling that :meth:`Simulation._check_mortality`
    uses so that stage transitions are aligned with old-age mortality.
    """
    accel = max(1, int(sim.cfg.drive_accel))
    lifespan = max(1, int(agents.lifespan_ticks[row]) // accel)
    age = int(sim.tick) - int(agents.born_tick[row])
    if age < 0:
        age = 0
    ratio = age / float(lifespan)
    return _life_stage_from_age_ratio(ratio)


def cognitive_efficiency_for_row(agents, row: int, sim) -> float:
    """Convenience: cognitive efficiency for ``agents[row]`` at ``sim.tick``."""
    return cognitive_efficiency(current_life_stage(agents, row, sim))


def stage_distribution(agents, sim) -> dict:
    """Return a histogram of life-stages among living agents."""
    counts = {name: 0 for name in _LIFE_STAGE_NAMES}
    n = agents.n_active
    if n == 0:
        return counts
    alive = np.flatnonzero(agents.alive[:n])
    for r in alive:
        s = current_life_stage(agents, int(r), sim)
        counts[_LIFE_STAGE_NAMES[int(s)]] += 1
    return counts


# ---------------------------------------------------------------------------
# Inheritance hook (monkey-patches Simulation._resolve_matings)
# ---------------------------------------------------------------------------

def install_genome_inheritance(sim, *, world_seed: Optional[int] = None) -> None:
    """Wrap ``sim._resolve_matings`` so newborn rows receive a crossover genome.

    The base method already spawns the offspring and returns
    ``(child_row, parent_a, parent_b)`` triples. We post-process each of
    those triples and overwrite the child's genome with a crossover of the
    parents. Idempotent.
    """
    if getattr(sim, "_genome_inheritance_installed", False):
        return
    sim._genome_inheritance_installed = True

    seed = world_seed if world_seed is not None else sim.cfg.seed

    # Make sure the array exists even if attach_genome was not yet called
    # (defensive — sim_5cd_integration.install() calls attach_genome first).
    if not getattr(sim.agents, "_genome_attached", False):
        attach_genome(sim.agents, seed)

    original_resolve = sim._resolve_matings

    def patched_resolve(intents, raw_events):
        births = original_resolve(intents, raw_events)
        agents = sim.agents
        for triple in births or []:
            try:
                child, pa, pb = int(triple[0]), int(triple[1]), int(triple[2])
            except Exception:
                continue
            if child < 0:
                continue
            # Per-birth deterministic RNG.
            rng = prf_rng(seed, ["agent", "genome", "child"],
                          [pa, pb, int(sim.tick), child])
            try:
                g_a = agents.genome[pa]
                g_b = agents.genome[pb]
                agents.genome[child] = crossover(g_a, g_b, rng)
                agents._genome_seeded[child] = True
            except Exception:
                # Never break the base sim because of a genome glitch.
                pass
        return births

    sim._resolve_matings = patched_resolve


__all__ = [
    "GENOME_SIZE",
    "GROUP_SIZE",
    "GENE_GROUP_APPEARANCE",
    "GENE_GROUP_COGNITION",
    "GENE_GROUP_HEALTH",
    "GENE_GROUP_LONGEVITY",
    "MUTATION_RATE",
    "LifeStage",
    "life_stage_name",
    "cognitive_efficiency",
    "cognitive_efficiency_for_row",
    "current_life_stage",
    "stage_distribution",
    "attach_genome",
    "crossover",
    "gene_to_trait",
    "install_genome_inheritance",
]
