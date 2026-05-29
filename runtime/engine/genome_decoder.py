"""Genesis Engine — Wave 47 heritable genotype→phenotype decoder.

The semantic-closure step toward **strong artificial life**.

(Wave 46 — the Bedau–Packard neutral-shadow control — landed inside
``engine.open_endedness``; this decoder is the next, independent wave.)

The problem (Pattee)
--------------------

Today the genome is decoded by :func:`engine.genome.gene_to_trait` —

    gene_to_trait(genome, group) = mean(genome[group])

This is an **external, fixed, observer-declared** map. *We* decided that
loci 0..63 mean "appearance", that the trait is their mean, and that this
rule is the same for every individual forever. In Howard Pattee's terms the
genome is then "a single level of signs **devoid of intrinsic dynamics**":
its meaning is assigned from outside, by us, and never participates in the
system's own evolution. That is precisely the gap that separates *weak*
artificial life (we interpret the symbols) from *strong* artificial life
(the system interprets its own symbols, and that act of interpretation is
itself alive — heritable, variable, selectable).

The move (heritable evolvable code)
------------------------------------

Wave 46 puts the **interpreter inside the genome**. The genome is split:

  * **Structural region** S = loci ``[0, 192)`` — raw coding content.
  * **Regulatory region** R = loci ``[192, 256)`` — a ``K×F`` weight matrix,
    the *code* that decides what the structural genes **mean**.

The phenotype is

    feats[j]   = mean(S over chunk j)              for j in 0..F-1
    W[k,j]     = (R reshaped to K×F, mapped to [-gain, +gain])
    P[k]       = sigmoid( Σ_j W[k,j] · (feats[j] - 0.5) )

Because R lives in the genome, it is inherited and mutated by the **same**
:func:`engine.genome.crossover` operator as S. So the genotype→phenotype
map is per-individual, heritable, and itself under selection. Two genomes
with **identical structural genes but different regulatory genes produce
different phenotypes** — meaning is no longer externally fixed, it is
carried and evolved by the organism. That is the practical, testable core
of semantic closure.

Honesty about the remaining gap
-------------------------------

This closes the *description→interpretation* side of Pattee's loop (the
code that relates genes to traits is maintained by the lineage). It does
**not** yet close the *construction* side — the phenotype does not yet
physically rebuild the machinery that will decode the next generation (von
Neumann self-reproduction). That deeper loop is future work; we do not
claim it here.

Determinism & safety
--------------------

Decoding is a **pure function** of the genome — no RNG, deterministic to
the byte (sha256 phenotype signatures). This module is **additive**: it
never rewrites :mod:`engine.genome`, :mod:`engine.agent` or the live agent
loop. Wiring it in to replace ``gene_to_trait`` is a separate, gated wave.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

import numpy as np

from engine.genome import GENOME_SIZE


PIPELINE_LAYER = "Genesis-L2 Biology"
CAPABILITY = "paper-strongVA Semantic-Closure (heritable G→P code)"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class PhenotypeConfig:
    """Layout of the heritable decoder.

    Defaults: structural region = loci [0, 192), regulatory region =
    loci [192, 256) reinterpreted as a ``k_traits × n_features`` weight
    matrix. With the defaults ``16 × 4 == 64`` exactly fills the regulatory
    region.
    """

    k_traits: int = 16          # phenotype dimensionality K
    n_features: int = 4         # structural feature count F
    struct_start: int = 0
    struct_end: int = 192       # S = [struct_start, struct_end)
    reg_start: int = 192
    reg_end: int = 256          # R = [reg_start, reg_end)
    weight_gain: float = 6.0    # R∈[0,1] → W∈[-gain, +gain]
    quantize_levels: int = 256  # for the deterministic signature

    @property
    def n_weights(self) -> int:
        return self.k_traits * self.n_features


_DEFAULT = PhenotypeConfig()


# ---------------------------------------------------------------------------
# Core decode (pure, deterministic)
# ---------------------------------------------------------------------------

def _as_genome(genome: np.ndarray) -> np.ndarray:
    g = np.asarray(genome, dtype=np.float64).reshape(-1)
    if g.shape[0] != GENOME_SIZE:
        raise ValueError(f"genome must be ({GENOME_SIZE},), got {g.shape}")
    return g


def structural_features(genome: np.ndarray,
                        cfg: Optional[PhenotypeConfig] = None) -> np.ndarray:
    """The F structural inputs: mean of each of F equal chunks of S."""
    cfg = cfg or _DEFAULT
    g = _as_genome(genome)
    s = g[cfg.struct_start:cfg.struct_end]
    chunks = np.array_split(s, cfg.n_features)
    return np.array([float(c.mean()) if c.size else 0.5 for c in chunks],
                    dtype=np.float64)


def regulatory_weights(genome: np.ndarray,
                       cfg: Optional[PhenotypeConfig] = None) -> np.ndarray:
    """The K×F signed weight code carried by the regulatory region R.

    R∈[0,1] is mapped to [-gain, +gain] so the code can *invert* as well as
    amplify the meaning of a structural feature."""
    cfg = cfg or _DEFAULT
    g = _as_genome(genome)
    r = g[cfg.reg_start:cfg.reg_end]
    need = cfg.n_weights
    if r.shape[0] < need:                       # tile if region too short
        reps = int(np.ceil(need / max(1, r.shape[0])))
        r = np.tile(r, reps)
    r = r[:need].reshape(cfg.k_traits, cfg.n_features)
    return (r - 0.5) * 2.0 * cfg.weight_gain


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -60.0, 60.0)))


def decode_phenotype(genome: np.ndarray,
                     cfg: Optional[PhenotypeConfig] = None) -> np.ndarray:
    """Decode a genome into a K-dim phenotype in (0, 1).

    Pure deterministic function — the heritable regulatory code R sets how
    the structural features are read."""
    cfg = cfg or _DEFAULT
    feats = structural_features(genome, cfg)          # (F,)
    w = regulatory_weights(genome, cfg)               # (K, F)
    z = w @ (feats - 0.5)                              # (K,)
    return _sigmoid(z).astype(np.float32)


def decode_population(genomes: np.ndarray,
                      cfg: Optional[PhenotypeConfig] = None) -> np.ndarray:
    """Decode an (N, 256) stack into an (N, K) phenotype matrix."""
    cfg = cfg or _DEFAULT
    arr = np.asarray(genomes, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr[None, :]
    if arr.shape[0] == 0:                       # no genomes → empty (0, K)
        return np.zeros((0, cfg.k_traits), dtype=np.float32)
    return np.stack([decode_phenotype(arr[i], cfg) for i in range(arr.shape[0])])


# ---------------------------------------------------------------------------
# Signatures & metrics
# ---------------------------------------------------------------------------

def phenotype_signature(genome: np.ndarray,
                        cfg: Optional[PhenotypeConfig] = None) -> str:
    """Deterministic sha256 over the quantized phenotype (byte-stable)."""
    cfg = cfg or _DEFAULT
    p = decode_phenotype(genome, cfg)
    q = np.clip((p * cfg.quantize_levels).astype(np.int64),
                0, cfg.quantize_levels - 1).astype(np.uint16)
    return hashlib.sha256(q.tobytes()).hexdigest()


def phenotype_distance(p: np.ndarray, q: np.ndarray) -> float:
    """L2 distance between two phenotype vectors."""
    a = np.asarray(p, dtype=np.float64).reshape(-1)
    b = np.asarray(q, dtype=np.float64).reshape(-1)
    return float(np.sqrt(np.sum((a - b) ** 2)))


def phenotype_diversity(genomes: np.ndarray,
                        cfg: Optional[PhenotypeConfig] = None,
                        max_pairs: int = 4096) -> float:
    """Mean pairwise L2 distance among decoded phenotypes (capped)."""
    cfg = cfg or _DEFAULT
    phen = decode_population(genomes, cfg)
    n = phen.shape[0]
    if n < 2:
        return 0.0
    total = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += phenotype_distance(phen[i], phen[j])
            count += 1
            if count >= max_pairs:
                return total / count
    return total / max(1, count)


def code_sensitivity(genome: np.ndarray,
                     world_seed: int,
                     trials: int = 32,
                     cfg: Optional[PhenotypeConfig] = None) -> float:
    """Mean phenotype shift when the **regulatory code R is replaced** while
    the structural region S is held fixed.

    A large value is the signature of semantic closure: the meaning of the
    structural genes is set by the heritable code, not externally fixed. (By
    contrast the legacy ``gene_to_trait`` is completely insensitive to R.)
    """
    from engine.core import prf_rng
    cfg = cfg or _DEFAULT
    g0 = _as_genome(genome).astype(np.float32)
    base = decode_phenotype(g0, cfg)
    acc = 0.0
    for t in range(trials):
        rng = prf_rng(world_seed, ["genome", "decoder", "code_probe"], [t])
        g = g0.copy()
        g[cfg.reg_start:cfg.reg_end] = rng.random(
            cfg.reg_end - cfg.reg_start, dtype=np.float32)
        acc += phenotype_distance(base, decode_phenotype(g, cfg))
    return acc / max(1, trials)


def decoder_summary(cfg: Optional[PhenotypeConfig] = None) -> dict:
    """Diagnostic dict describing the decoder layout."""
    cfg = cfg or _DEFAULT
    return {
        "capability": CAPABILITY,
        "philosophy": "HERITABLE_EVOLVABLE_CODE",
        "k_traits": cfg.k_traits,
        "n_features": cfg.n_features,
        "structural_region": [cfg.struct_start, cfg.struct_end],
        "regulatory_region": [cfg.reg_start, cfg.reg_end],
        "n_weights": cfg.n_weights,
        "weight_gain": cfg.weight_gain,
        "semantic_closure": "description-side (interpreter is heritable)",
        "open_gap": "construction-side (von Neumann self-build) — future work",
    }


__all__ = [
    "PhenotypeConfig",
    "structural_features",
    "regulatory_weights",
    "decode_phenotype",
    "decode_population",
    "phenotype_signature",
    "phenotype_distance",
    "phenotype_diversity",
    "code_sensitivity",
    "decoder_summary",
    "PIPELINE_LAYER",
    "CAPABILITY",
]
