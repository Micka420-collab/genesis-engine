"""Genesis Engine — Wave 45 open-endedness meter (intrinsic, ontology-free).

Read-only observer that quantifies whether the simulation is *open-ended*
— i.e. whether it keeps producing genuinely new behaviour rather than
settling into a fixed repertoire. This is the instrumentation step toward
**strong artificial life**: before we can claim Genesis Engine is unbounded
in its inventiveness, we must be able to *measure* unboundedness without
smuggling in the observer's own ontology.

Why "ontology-free"
-------------------

`engine.emergence_metrics` already reports things like
``technologies_discovered`` or ``communication_entropy`` — but those count
events against a **hard-coded vocabulary** (8 event kinds, a fixed tech
list). That measures emergence *relative to categories we chose in
advance*. An open-ended system, by construction, invents categories we did
NOT anticipate, so any fixed ontology eventually saturates and stops
seeing novelty even while the system keeps innovating.

This meter sidesteps that. It builds its vocabulary **from the substrate
itself** — a "motif" is just a coarse quantization of an agent's physical
+ physiological state (its 8 drives, its speed, its local crowding). No
motif is named, privileged, or tied to a concept like "tool" or "word".
New motifs are discovered, never declared. The measures below all derive
from this self-generated motif stream.

Three measures
--------------

1. **Cumulative novelty N(t)** — number of *distinct* motifs ever observed.
   A plateau in N(t) means the behavioural space has been exhausted; a
   steadily rising N(t) is the signature of open-endedness.

2. **Compression complexity** — zlib length of a canonicalized rolling
   window of the population's motif distribution. Approximates the
   incompressibility (≈ Kolmogorov complexity) of the behavioural stream:
   a system generating structure that resists compression is producing
   information, not just churning noise.

3. **Bedau–Packard evolutionary activity** — cumulative activity A(t),
   component diversity D(t) (motifs whose accumulated usage crosses a
   persistence threshold), and new activity per window. This is the
   classic ALife test that distinguishes *adaptive* persistence from
   neutral drift. (We use the persistence-threshold variant; the full
   neutral-shadow model is noted as future work.)

Determinism
-----------

100% deterministic. Motif ids come from ``hashlib.blake2b`` (NOT Python's
process-randomized ``hash()``), compression from ``zlib`` at a fixed level,
and there is no RNG anywhere. Every snapshot carries a SHA-256 signature so
two runs on the same seed produce byte-identical observation streams.

Read-only contract
-------------------

The observer NEVER mutates simulation dynamics. It reads copies of
``sim.agents`` arrays and accumulates its own bookkeeping under
``sim._open_endedness_state``. The wrapped ``sim.step`` calls the original
step first, then observes. Uninstalling restores the original step.
"""
from __future__ import annotations

import hashlib
import math
import struct
import zlib
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Dict, List, Optional, Set

import numpy as np


PIPELINE_LAYER = "Genesis-L5 Observer"
WORLD_MODEL_CAPABILITY = "paper-L2 Open-Endedness Meter"

# The 8 Phase-4 drives, in a FIXED order so the motif encoding is stable
# across runs. These are substrate quantities (engine.agent), not an
# observer-chosen ontology of meanings.
_DRIVE_ATTRS = (
    "hunger", "thirst", "sleep", "fatigue",
    "thermal", "pain", "stress", "loneliness",
)


# ---------------------------------------------------------------------------
# Config / data model
# ---------------------------------------------------------------------------

@dataclass
class OpenEndednessConfig:
    """Knobs for the open-endedness meter. All quantization is coarse on
    purpose — we want behavioural *classes*, not per-agent fingerprints."""

    snapshot_every: int = 256          # ticks between observations
    drive_levels: int = 4              # bins per drive (∈[0,1] → 0..levels-1)
    speed_levels: int = 4              # bins for |velocity|
    neighbor_levels: int = 4           # bins for local crowding
    max_ref_speed_ms: float = 7.0      # speed mapped onto [0, this) m/s
    neighbor_radius_m: float = 8.0     # radius defining "local" crowd
    window: int = 16                   # snapshots kept for compression/activity
    persistence_threshold: float = 3.0  # accumulated activity ⇒ "persistent"
    max_motifs_tracked: int = 1_000_000  # vocabulary cap (memory guard)


@dataclass
class OpenEndednessSnapshot:
    """One observation. Pure summary statistics — no agent identities."""

    tick: int
    population: int
    distinct_motifs_cumulative: int     # N(t)
    new_motifs: int                     # motifs first seen this snapshot
    motif_entropy_bits: float           # Shannon entropy of current distribution
    compression_len: int                # zlib length of canonical window
    compression_ratio: float            # compressed / raw  (>0; may exceed 1 on
                                        #   tiny windows — zlib framing overhead)
    activity_cumulative: float          # A(t)  (sum over persistent motifs)
    diversity: int                      # D(t)  (# persistent motifs)
    new_activity: float                 # activity gained by newly-persistent
    signature: str                      # sha256 of canonical descriptor


@dataclass
class OpenEndednessHistory:
    config: OpenEndednessConfig
    snapshots: List[OpenEndednessSnapshot] = field(default_factory=list)
    n_ticks_run: int = 0


@dataclass
class OpenEndednessState:
    config: OpenEndednessConfig
    history: OpenEndednessHistory
    seen_motifs: Set[int] = field(default_factory=set)      # all ids ever
    activity: Dict[int, float] = field(default_factory=dict)  # id → accum usage
    persistent: Set[int] = field(default_factory=set)        # ids ≥ threshold
    window_descriptors: Deque[bytes] = field(default_factory=deque)
    last_snapshot_tick: int = -1
    _original_step: Optional[Callable] = None


# ---------------------------------------------------------------------------
# Motif encoding (the ontology-free vocabulary)
# ---------------------------------------------------------------------------

def _quantize_unit(value: float, levels: int) -> int:
    """Map a value expected in [0, 1] onto an integer bin 0..levels-1."""
    if levels <= 1:
        return 0
    b = int(value * levels)
    if b < 0:
        return 0
    if b >= levels:
        return levels - 1
    return b


def _neighbor_counts(pos_xy: np.ndarray, radius_m: float) -> np.ndarray:
    """Number of *other* agents within ``radius_m`` of each agent.

    O(n²) but populations are small (≤ few hundred). Pure read."""
    n = pos_xy.shape[0]
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    if n == 1:
        return np.zeros(1, dtype=np.int64)
    diff = pos_xy[:, None, :] - pos_xy[None, :, :]
    d2 = np.einsum("ijk,ijk->ij", diff, diff)
    within = d2 <= (radius_m * radius_m)
    counts = within.sum(axis=1) - 1  # exclude self
    return counts.astype(np.int64)


def _agent_motifs(sim, cfg: OpenEndednessConfig) -> List[int]:
    """Compute the motif id of every *alive* agent.

    A motif = blake2b(8 drive bins ‖ speed bin ‖ neighbor bin) → uint64.
    Fully deterministic; never touches RNG or mutates the sim.
    """
    agents = sim.agents
    n = int(getattr(agents, "n_active", 0))
    if n == 0:
        return []
    alive = np.asarray(agents.alive[:n], dtype=bool)
    idx = np.flatnonzero(alive)
    if idx.size == 0:
        return []

    # Drives → bins (one column per drive, ordered by _DRIVE_ATTRS).
    drive_bins = np.zeros((idx.size, len(_DRIVE_ATTRS)), dtype=np.uint8)
    for col, attr in enumerate(_DRIVE_ATTRS):
        arr = getattr(agents, attr, None)
        if arr is None:
            continue
        vals = np.asarray(arr[:n], dtype=np.float64)[idx]
        lv = cfg.drive_levels
        binned = np.clip((vals * lv).astype(np.int64), 0, lv - 1)
        drive_bins[:, col] = binned.astype(np.uint8)

    # Speed → bin.
    vel = np.asarray(agents.vel[:n, :], dtype=np.float64)[idx]
    speed = np.sqrt(np.einsum("ij,ij->i", vel, vel))
    ref = max(cfg.max_ref_speed_ms, 1e-6)
    speed_bins = np.clip(
        (speed / ref * cfg.speed_levels).astype(np.int64),
        0, cfg.speed_levels - 1).astype(np.uint8)

    # Local crowding → bin (counts above neighbor_levels-1 saturate).
    pos_xy = np.asarray(agents.pos[:n, :2], dtype=np.float64)[idx]
    ncounts = _neighbor_counts(pos_xy, cfg.neighbor_radius_m)
    neigh_bins = np.clip(
        ncounts, 0, cfg.neighbor_levels - 1).astype(np.uint8)

    motifs: List[int] = []
    for i in range(idx.size):
        payload = drive_bins[i].tobytes() + bytes(
            (int(speed_bins[i]), int(neigh_bins[i])))
        digest = hashlib.blake2b(payload, digest_size=8).digest()
        motifs.append(int.from_bytes(digest, "little"))
    return motifs


def _canonical_descriptor(counts: "Counter[int]") -> bytes:
    """Deterministic byte encoding of a motif→count multiset.

    Sorted by motif id so the encoding is order-independent. Each entry is
    packed as ``<Q I`` (uint64 motif id, uint32 count)."""
    out = bytearray()
    out += struct.pack("<I", len(counts))
    for motif_id in sorted(counts.keys()):
        out += struct.pack("<QI", motif_id & 0xFFFFFFFFFFFFFFFF,
                           int(counts[motif_id]) & 0xFFFFFFFF)
    return bytes(out)


def _shannon_bits(counts: "Counter[int]") -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    h = 0.0
    for c in counts.values():
        p = c / total
        if p > 0.0:
            h -= p * math.log2(p)
    return h


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------

def _get_or_create_state(sim,
                          cfg: Optional[OpenEndednessConfig] = None
                          ) -> OpenEndednessState:
    existing: Optional[OpenEndednessState] = getattr(
        sim, "_open_endedness_state", None)
    if existing is not None:
        if cfg is not None:
            existing.config = cfg
        return existing
    cfg = cfg or OpenEndednessConfig()
    state = OpenEndednessState(
        config=cfg, history=OpenEndednessHistory(config=cfg))
    state.window_descriptors = deque(maxlen=max(1, cfg.window))
    sim._open_endedness_state = state
    return state


def observe_open_endedness(sim,
                           cfg: Optional[OpenEndednessConfig] = None
                           ) -> OpenEndednessSnapshot:
    """Compute one snapshot from the *current* sim state.

    Updates the OBSERVER accumulators (seen motifs, activity counters,
    rolling window) — never the simulation. Does NOT append to history;
    the wrapped step does that so repeated standalone calls stay explicit.
    """
    state = _get_or_create_state(sim, cfg)
    cfg = state.config

    motifs = _agent_motifs(sim, cfg)
    counts: "Counter[int]" = Counter(motifs)
    population = len(motifs)

    # (1) Cumulative novelty — discover new motifs (respecting the cap).
    new_motifs = 0
    capped = len(state.seen_motifs) >= cfg.max_motifs_tracked
    for m in counts:
        if m not in state.seen_motifs:
            if capped:
                continue
            state.seen_motifs.add(m)
            new_motifs += 1
            if len(state.seen_motifs) >= cfg.max_motifs_tracked:
                capped = True

    # (3) Bedau–Packard activity — accumulate usage, track persistence.
    new_activity = 0.0
    for m, c in counts.items():
        prev = state.activity.get(m, 0.0)
        cur = prev + float(c)
        state.activity[m] = cur
        if m not in state.persistent and cur >= cfg.persistence_threshold:
            state.persistent.add(m)
            new_activity += cur
    activity_cumulative = float(
        sum(state.activity[m] for m in state.persistent))
    diversity = len(state.persistent)

    # (2) Compression complexity over the rolling window.
    descriptor = _canonical_descriptor(counts)
    state.window_descriptors.append(descriptor)
    blob = bytearray()
    for d in state.window_descriptors:
        blob += struct.pack("<I", len(d))
        blob += d
    raw_len = len(blob)
    compressed = zlib.compress(bytes(blob), 6)
    compression_len = len(compressed)
    compression_ratio = (compression_len / raw_len) if raw_len > 0 else 0.0

    signature = hashlib.sha256(descriptor).hexdigest()

    return OpenEndednessSnapshot(
        tick=int(getattr(sim, "tick", 0)),
        population=population,
        distinct_motifs_cumulative=len(state.seen_motifs),
        new_motifs=new_motifs,
        motif_entropy_bits=round(_shannon_bits(counts), 6),
        compression_len=compression_len,
        compression_ratio=round(compression_ratio, 6),
        activity_cumulative=activity_cumulative,
        diversity=diversity,
        new_activity=new_activity,
        signature=signature,
    )


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------

def install_open_endedness(sim,
                           cfg: Optional[OpenEndednessConfig] = None
                           ) -> OpenEndednessState:
    """Idempotent installer. Wraps ``sim.step`` to capture a snapshot every
    ``cfg.snapshot_every`` ticks. Read-only on the simulation."""
    state = _get_or_create_state(sim, cfg)

    if getattr(sim, "_open_endedness_wrapped", False):
        return state
    sim._open_endedness_wrapped = True
    original_step = sim.step
    state._original_step = original_step

    def wrapped_step():
        stats = original_step()
        st: Optional[OpenEndednessState] = getattr(
            sim, "_open_endedness_state", None)
        if st is None:
            return stats
        cfg_now = st.config
        if (int(sim.tick) - st.last_snapshot_tick) >= cfg_now.snapshot_every:
            snap = observe_open_endedness(sim)
            st.history.snapshots.append(snap)
            st.last_snapshot_tick = int(sim.tick)
            st.history.n_ticks_run = int(sim.tick)
        return stats

    sim.step = wrapped_step
    return state


def uninstall_open_endedness(sim) -> bool:
    """Restore the original ``sim.step`` and drop observer state."""
    state: Optional[OpenEndednessState] = getattr(
        sim, "_open_endedness_state", None)
    restored = False
    if state is not None and state._original_step is not None:
        if getattr(sim, "_open_endedness_wrapped", False):
            sim.step = state._original_step
            sim._open_endedness_wrapped = False
            restored = True
    if hasattr(sim, "_open_endedness_state"):
        delattr(sim, "_open_endedness_state")
        restored = True
    return restored


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def open_endedness_summary(sim) -> Dict[str, object]:
    """Diagnostic dict over the trajectory. Includes a crude *trend* on
    cumulative novelty: a positive slope across the last snapshots is the
    headline open-endedness signal."""
    state: Optional[OpenEndednessState] = getattr(
        sim, "_open_endedness_state", None)
    if state is None:
        return {"installed": False}
    history = state.history
    if not history.snapshots:
        return {"installed": True, "n_snapshots": 0}

    snaps = history.snapshots
    last = snaps[-1]

    # Novelty trend: mean new_motifs per snapshot over the last `window`.
    tail = snaps[-min(len(snaps), state.config.window):]
    recent_new = sum(s.new_motifs for s in tail)
    novelty_rate = recent_new / max(1, len(tail))
    still_innovating = bool(recent_new > 0)

    return {
        "installed": True,
        "philosophy": "ONTOLOGY_FREE_OPEN_ENDEDNESS",
        "n_snapshots": len(snaps),
        "n_ticks_run": history.n_ticks_run,
        "last_tick": last.tick,
        "population_last": last.population,
        # (1) novelty
        "distinct_motifs_cumulative": last.distinct_motifs_cumulative,
        "novelty_rate_recent": round(novelty_rate, 4),
        "still_innovating": still_innovating,
        # (2) complexity
        "compression_len_last": last.compression_len,
        "compression_ratio_last": last.compression_ratio,
        "motif_entropy_bits_last": last.motif_entropy_bits,
        # (3) Bedau–Packard
        "activity_cumulative": last.activity_cumulative,
        "diversity": last.diversity,
        "new_activity_last": last.new_activity,
        "signature_last": last.signature,
    }
