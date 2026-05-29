"""Genesis Engine — Wave 52: heritable decoder wired into the live brain.

This is the *gated wiring* wave promised at the end of Wave 47
(:mod:`engine.genome_decoder`). Wave 47 built a pure, heritable
genotype→phenotype decoder but left it disconnected from behaviour — it
explicitly said "wiring it in to replace ``gene_to_trait`` is a separate,
gated wave". This is that wave.

The semantic-closure gap, restated for *behaviour*
--------------------------------------------------

The live policy (:mod:`engine.neat_brain`) reads the genome through a
**fixed, observer-declared** rule: the cognition slice ``[64, 128)`` is
``tanh``-squashed and tiled into a 2-layer MLP. *We* decided that those 64
loci mean "the policy weights", and that rule is identical for every
individual forever — exactly Pattee's "signs devoid of intrinsic dynamics",
now on the behaviour side rather than the trait side.

The move
--------

We let the **heritable regulatory code** R = loci ``[192, 256)`` reinterpret
the cognition slice *before* the brain reads it:

    P            = decode_phenotype(genome)          # (K,) in (0,1), uses R
    gain[k]      = 1 + A·(2·P[k] - 1)                # in (1-A, 1+A)
    gain_cog     = tile(gain, 64)                    # one gain per cognition gene
    cognition'   = cognition · gain_cog              # reinterpreted slice

``regulated_genome_view`` returns a **copy** of the genome whose cognition
slice has been gain-modulated by the decoded phenotype. The brain then
decides on that view. Because P depends on R, and R is inherited and mutated
by the *same* :func:`engine.genome.crossover` operator as the rest of the
genome, the genotype→behaviour map is now **per-individual, heritable, and
under selection**.

The testable core
-----------------

Two genomes **identical on the whole structural region** S = ``[0, 192)``
(which contains the cognition slice the brain reads) but **differing only on
the regulatory region** R = ``[192, 256)``:

  * produce *identical* logits under the legacy brain (it never looks at R);
  * produce *different* logits under the regulated brain (R reinterprets the
    cognition slice via the decoded phenotype).

That difference **is** semantic closure expressed in behaviour: what the
cognition genes *mean* is no longer fixed from outside, it is carried and
evolved by the organism.

Neutral code recovers the legacy brain
--------------------------------------

When the regulatory code decodes to the neutral phenotype P ≡ 0.5, every
gain is exactly 1.0, the view equals the original genome, and the regulated
brain is **byte-identical** to the legacy brain. The legacy fixed decoder is
therefore the *neutral special case* of this heritable family, and evolution
can move away from it. This is the formal basis of the non-regression
guarantee (and the flag defaults OFF on top of that).

Determinism & safety
--------------------

The view is a **pure deterministic function** of the genome — no RNG. The
module is **additive**: it never rewrites :mod:`engine.genome`,
:mod:`engine.genome_decoder`, :mod:`engine.neat_brain`, or the agent loop.
The only behavioural change is a single flag-gated hook in
:func:`engine.neat_brain.genome_decide`; with ``SimConfig.heritable_brain``
False (the default) the legacy path is taken unchanged.

Honesty about scope
-------------------

This closes the *description→interpretation* side of Pattee's loop **for
behaviour** (the gene→policy code is heritable). It does **not** close the
*construction* side (von Neumann self-build) — future work, not claimed.
Known minor boundary: the EXPLORE walk-offset in
``engine.neat_brain._targets_for_action`` still reads the raw genome latent;
the regulated view governs *which* action is chosen, not that locomotion
detail.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from engine.genome import GENE_GROUP_COGNITION
from engine.genome_decoder import PhenotypeConfig, decode_phenotype

PIPELINE_LAYER = "Genesis-L3 Cognition"
CAPABILITY = "paper-strongVA Semantic-Closure wired into live policy (gated)"

# How strongly the decoded phenotype is allowed to re-weight a cognition
# gene. gain ∈ (1 - A, 1 + A). A = 0.6 → gain ∈ (0.4, 1.6): a strong but
# bounded reinterpretation that keeps the brain's tanh inputs finite.
REGULATION_AMPLITUDE: float = 0.6

_COG_LEN = GENE_GROUP_COGNITION.stop - GENE_GROUP_COGNITION.start  # 64


def regulatory_modulation(genome: np.ndarray,
                          cfg: Optional[PhenotypeConfig] = None) -> np.ndarray:
    """Per-cognition-gene multiplicative gain decoded from the genome.

    Returns a ``(64,)`` float32 vector in ``(1-A, 1+A)``. The K decoded
    phenotype traits are tiled across the 64 cognition genes, so each trait
    pleiotropically re-weights several genes. Pure / deterministic.

    At the neutral phenotype P ≡ 0.5 every gain is exactly 1.0.
    """
    cfg = cfg or PhenotypeConfig()
    p = decode_phenotype(genome, cfg)                       # (K,) in (0,1)
    gain = 1.0 + REGULATION_AMPLITUDE * (2.0 * p - 1.0)     # (K,) in (1-A,1+A)
    if gain.size == 0:
        return np.ones(_COG_LEN, dtype=np.float32)
    reps = int(np.ceil(_COG_LEN / gain.size))
    return np.tile(gain, reps)[:_COG_LEN].astype(np.float32)


def regulated_genome_view(genome: np.ndarray,
                          cfg: Optional[PhenotypeConfig] = None) -> np.ndarray:
    """A genome **copy** whose cognition slice is reinterpreted by R.

    The brain reads the cognition slice ``[64, 128)`` through ``tanh``; we
    multiply that slice by the decoded per-gene gain *before* the brain sees
    it. No clipping: the neutral code (gain ≡ 1.0) reproduces the original
    slice exactly, so the regulated brain degrades gracefully to the legacy
    brain. The brain's own ``tanh(g·0.35)`` bounds the modulated values.

    Pure / deterministic — never mutates the input.
    """
    g = np.array(genome, dtype=np.float32, copy=True).reshape(-1)
    gain = regulatory_modulation(g, cfg)
    g[GENE_GROUP_COGNITION] = g[GENE_GROUP_COGNITION] * gain
    return g


def heritable_brain_enabled(sim) -> bool:
    """True iff the live loop should decide on the regulated genome view."""
    return bool(getattr(getattr(sim, "cfg", None), "heritable_brain", False))


def regulation_summary(genome: np.ndarray,
                       cfg: Optional[PhenotypeConfig] = None) -> dict:
    """Diagnostic dict for smoke tests / the observer layer."""
    cfg = cfg or PhenotypeConfig()
    p = decode_phenotype(genome, cfg)
    gain = regulatory_modulation(genome, cfg)
    # "near-neutral" → the regulated brain ≈ the legacy brain.
    neutral = bool(np.max(np.abs(gain - 1.0)) < 1e-6)
    return {
        "capability": CAPABILITY,
        "philosophy": "HERITABLE_EVOLVABLE_CODE → BEHAVIOUR",
        "regulation_amplitude": REGULATION_AMPLITUDE,
        "cognition_region": [GENE_GROUP_COGNITION.start, GENE_GROUP_COGNITION.stop],
        "k_traits": int(p.size),
        "gain_min": float(gain.min()),
        "gain_max": float(gain.max()),
        "gain_mean": float(gain.mean()),
        "is_neutral_code": neutral,
        "semantic_closure": "behaviour-side (gene→policy code is heritable)",
        "open_gap": "construction-side (von Neumann self-build) — future work",
    }


__all__ = [
    "REGULATION_AMPLITUDE",
    "regulatory_modulation",
    "regulated_genome_view",
    "heritable_brain_enabled",
    "regulation_summary",
    "PIPELINE_LAYER",
    "CAPABILITY",
]
