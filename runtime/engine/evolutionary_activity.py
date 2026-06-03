"""Genesis Engine — Wave 58 open-endedness / evolutionary-activity observer.

Read-only **falsifiability** companion that turns the project's *ZERO
PRE-SCRIPT* claim into an objective, measurable test. It implements the
classical **Bedau–Packard evolutionary-activity statistics** (Bedau & Packard
1992; Bedau, Snyder & Packard 1998), the standard battery used to *classify*
the dynamics of an artificial-life run as

* **none**     — no sustained novelty (a frozen / fully-scripted system),
* **bounded**  — novelty appears but its rate decays (a saturating system),
* **unbounded**— novelty keeps being produced (genuine open-endedness).

Motivation (veille 2026-06-03, DÉCOUVERTE_2)
-------------------------------------------

`de Pinho & Sinapayen, 2026` re-applied the open-ended-evolution (OEE) tests
— cumulative / mean / new **evolutionary activity** in the Bedau–Packard
lineage — to a speciation simulation and obtained a *nuanced, falsifiable*
verdict (cumulative activity unbounded ✅ but new activity → 0 ❌, hence "not
(yet) open-ended"). The methodology is substrate-agnostic: a *component* is
any heritable/innovable unit (a gene, a recipe, an invention, a lexeme) whose
*activity* is the number of times it is observed in use. Genesis already
emits such components (`invention_registry`, emergent construction recipes,
memetic lexicon); this module only **reads** them and scores the run — it
never injects a goal or a scripted outcome, so it lives strictly outside the
deterministic `Simulation.step()` path.

What it measures (Bedau–Packard statistics)
-------------------------------------------

For a *usage series* ``u`` — a per-tick mapping ``component_id -> increment``
(typically ``1`` when the component is present/used) — define the cumulative
activity of component ``i`` at tick ``t``::

    a_i(t) = Σ_{τ ≤ t} u_i(τ)

and then the three diagnostic curves:

* **Diversity**            ``D(t)``  — number of components ever seen by ``t``
  (monotone non-decreasing; its growth is the open-endedness signal).
* **Total cumulative activity** ``A(t) = Σ_i a_i(t)``.
* **Mean cumulative activity**  ``Ā(t) = A(t) / D(t)``.
* **New-component rate**   ``n_new(t) = D(t) − D(t−1)`` — the *innovation*
  rate, the heart of the OEE test (sustained ``n_new`` ⇒ open-endedness).

A simple **analytic neutral shadow** (the activity expected if the same total
activity were spread uniformly over all seen components, ``Ā``) gives a
threshold above which a component is *adaptively significant* — i.e. it
persists more than neutral drift would predict.

Classification is driven by **novelty**, not raw cumulative activity (which
trivially grows whenever a component merely persists): the tail innovation
rate over the last ``tail_fraction`` of the run decides none / bounded /
unbounded. This deliberately avoids the persistence artifact that would make
any non-empty system look "unbounded".

Observer contract (mirrors Waves 49 / 53 / 55 / 57)
---------------------------------------------------

``EvoActivityConfig`` / ``EvoActivityStats`` / ``EvoActivitySnapshot`` /
``EvoActivityHistory`` / ``EvoActivityState`` dataclasses; pure world-free
curve functions; ``observe_evolutionary_activity`` (read-only); idempotent
``install_evolutionary_activity_observer`` / ``uninstall_...`` wrapping
``sim.step`` once; ``evolutionary_activity_summary`` diagnostic dict.

Determinism
-----------

No RNG. Every statistic is pure float64 / integer arithmetic over the usage
series, and the snapshot signature is ``sha256`` of a canonical rounded tuple
(plus the sorted component-id set), so two runs with the same world seed
produce identical evolutionary-activity streams.

Stone-age compliance
--------------------

The observer never declares which innovations *should* exist or in what order.
It reads whatever heritable components the emergent run has produced and scores
their novelty dynamics. No mutation of any world or sim array.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

UsageStep = Mapping[str, float]
UsageSeries = Sequence[UsageStep]


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvoActivityConfig:
    """Read-only knobs for the evolutionary-activity observer.

    Defaults describe a conservative novelty test: classify on the trailing
    half of the run, calling the dynamics *unbounded* only when at least
    ``unbounded_rate`` brand-new components keep appearing per snapshot.
    """
    tail_fraction: float = 0.5      # share of the run used for the tail trend
    significance_factor: float = 1.0  # threshold = factor · mean activity
    unbounded_rate: float = 0.25    # tail new-components/step ⇒ "unbounded"
    min_steps: int = 4              # below this the verdict is "insufficient"
    snapshot_every: int = 64
    max_components_in_signature: int = 256


@dataclass(frozen=True)
class EvoActivityStats:
    """Bedau–Packard statistics for one usage series (world-free)."""
    n_steps: int
    n_components: int
    diversity_final: int
    total_cumulative_activity: float
    mean_cumulative_activity: float
    max_component_activity: float
    new_components_total: int
    new_components_tail: int
    innovation_rate_tail: float      # new components / step over the tail
    significance_threshold: float
    n_significant_components: int
    dynamics_class: str              # none | bounded | unbounded | insufficient


@dataclass(frozen=True)
class EvoActivitySnapshot:
    """Evolutionary-activity snapshot at a sim tick (stats + signature)."""
    tick: int
    stats: EvoActivityStats
    signature: str


@dataclass
class EvoActivityHistory:
    snapshots: List[EvoActivitySnapshot] = field(default_factory=list)


@dataclass
class EvoActivityState:
    config: EvoActivityConfig
    usage_series: List[Dict[str, float]] = field(default_factory=list)
    history: EvoActivityHistory = field(default_factory=EvoActivityHistory)
    wrapped: bool = False


# ---------------------------------------------------------------------------
# Pure-function statistics  (world-free, fully unit-testable)
# ---------------------------------------------------------------------------

def _component_order(usage_series: UsageSeries) -> List[str]:
    """Sorted (deterministic) list of every component id seen in the series."""
    seen: Dict[str, None] = {}
    for step in usage_series:
        for cid in step:
            seen[str(cid)] = None
    return sorted(seen)


def diversity_curve(usage_series: UsageSeries) -> np.ndarray:
    """``D(t)`` — cumulative count of distinct components seen up to each tick.

    Monotone non-decreasing, length ``len(usage_series)``. The *growth* of this
    curve is the primary open-endedness signal.
    """
    seen: set = set()
    out = np.empty(len(usage_series), dtype=np.int64)
    for t, step in enumerate(usage_series):
        for cid, inc in step.items():
            if inc > 0.0:
                seen.add(str(cid))
        out[t] = len(seen)
    return out


def new_component_curve(usage_series: UsageSeries) -> np.ndarray:
    """``n_new(t) = D(t) − D(t−1)`` — the innovation (new-component) rate."""
    div = diversity_curve(usage_series)
    if div.size == 0:
        return div.astype(np.int64)
    out = np.empty_like(div)
    out[0] = div[0]
    if div.size > 1:
        out[1:] = np.diff(div)
    return out


def component_activity(usage_series: UsageSeries) -> Dict[str, float]:
    """Final cumulative activity ``a_i(T)`` per component (Bedau persistence)."""
    acc: Dict[str, float] = {}
    for step in usage_series:
        for cid, inc in step.items():
            if inc:
                acc[str(cid)] = acc.get(str(cid), 0.0) + float(inc)
    return acc


def total_activity_curve(usage_series: UsageSeries) -> np.ndarray:
    """``A(t) = Σ_i a_i(t)`` — running total cumulative activity (float64)."""
    out = np.empty(len(usage_series), dtype=np.float64)
    running = 0.0
    for t, step in enumerate(usage_series):
        for inc in step.values():
            if inc:
                running += float(inc)
        out[t] = running
    return out


def mean_activity_curve(usage_series: UsageSeries) -> np.ndarray:
    """``Ā(t) = A(t) / D(t)`` — neutral-shadow mean activity (0 where D=0)."""
    a = total_activity_curve(usage_series)
    d = diversity_curve(usage_series).astype(np.float64)
    out = np.zeros_like(a)
    nz = d > 0
    out[nz] = a[nz] / d[nz]
    return out


def significance_threshold(activity_final: Mapping[str, float],
                           factor: float = 1.0) -> float:
    """Analytic neutral-shadow threshold ``= factor · mean activity``.

    Components whose cumulative activity exceeds this persist more than the
    neutral expectation (the total activity spread uniformly over all seen
    components) and are counted *adaptively significant*.
    """
    if not activity_final:
        return 0.0
    vals = np.fromiter(activity_final.values(), dtype=np.float64)
    return float(factor) * float(vals.mean())


def n_significant_components(activity_final: Mapping[str, float],
                             threshold: float) -> int:
    """Number of components whose activity strictly exceeds ``threshold``."""
    if not activity_final:
        return 0
    vals = np.fromiter(activity_final.values(), dtype=np.float64)
    return int((vals > threshold).sum())


def _tail_window(n_steps: int, tail_fraction: float) -> int:
    """First index of the trailing window (clamped to ``[1, n_steps-1]``)."""
    frac = min(max(tail_fraction, 0.0), 1.0)
    start = int(round(n_steps * (1.0 - frac)))
    return min(max(start, 1), max(n_steps - 1, 1))


def classify_dynamics(usage_series: UsageSeries,
                      cfg: Optional[EvoActivityConfig] = None) -> str:
    """Classify the run as none / bounded / unbounded (Bedau dynamics class).

    Driven by the **tail innovation rate** (new components per step over the
    last ``tail_fraction`` of the run), not by raw cumulative activity:

    * fewer than ``min_steps`` ticks                       → ``"insufficient"``
    * no new component in the tail window                  → ``"none"``
    * sustained tail rate ≥ ``unbounded_rate``             → ``"unbounded"``
    * otherwise (novelty present but decaying)             → ``"bounded"``
    """
    cfg = cfg or EvoActivityConfig()
    n = len(usage_series)
    if n < cfg.min_steps:
        return "insufficient"
    new_curve = new_component_curve(usage_series)
    start = _tail_window(n, cfg.tail_fraction)
    tail = new_curve[start:]
    if tail.size == 0:
        return "none"
    tail_new = int(tail.sum())
    if tail_new <= 0:
        return "none"
    rate = float(tail_new) / float(tail.size)
    return "unbounded" if rate >= cfg.unbounded_rate else "bounded"


def evolutionary_activity_stats(usage_series: UsageSeries,
                                cfg: Optional[EvoActivityConfig] = None
                                ) -> EvoActivityStats:
    """Full Bedau–Packard statistics bundle for a usage series (pure)."""
    cfg = cfg or EvoActivityConfig()
    n = len(usage_series)
    activity = component_activity(usage_series)
    div = diversity_curve(usage_series)
    new_curve = new_component_curve(usage_series)
    total_curve = total_activity_curve(usage_series)
    mean_curve = mean_activity_curve(usage_series)

    diversity_final = int(div[-1]) if div.size else 0
    total_act = float(total_curve[-1]) if total_curve.size else 0.0
    mean_act = float(mean_curve[-1]) if mean_curve.size else 0.0
    max_act = float(max(activity.values())) if activity else 0.0

    thr = significance_threshold(activity, cfg.significance_factor)
    n_sig = n_significant_components(activity, thr)

    if n >= 1:
        start = _tail_window(n, cfg.tail_fraction)
        tail = new_curve[start:]
        tail_new = int(tail.sum()) if tail.size else 0
        tail_rate = (float(tail_new) / float(tail.size)) if tail.size else 0.0
    else:
        tail_new = 0
        tail_rate = 0.0

    return EvoActivityStats(
        n_steps=n,
        n_components=len(activity),
        diversity_final=diversity_final,
        total_cumulative_activity=total_act,
        mean_cumulative_activity=mean_act,
        max_component_activity=max_act,
        new_components_total=int(div[-1]) if div.size else 0,
        new_components_tail=tail_new,
        innovation_rate_tail=tail_rate,
        significance_threshold=thr,
        n_significant_components=n_sig,
        dynamics_class=classify_dynamics(usage_series, cfg),
    )


# ---------------------------------------------------------------------------
# Snapshot / signature
# ---------------------------------------------------------------------------

def _stats_signature(tick: int, stats: EvoActivityStats,
                     usage_series: UsageSeries,
                     cfg: EvoActivityConfig) -> str:
    """sha256 of a canonical, language-neutral representation."""
    comp_ids = _component_order(usage_series)
    if len(comp_ids) > cfg.max_components_in_signature:
        # Bound the hash input: hash the id set separately, keep the digest.
        comp_token = hashlib.sha256(
            " ".join(comp_ids).encode("utf-8")).hexdigest()
    else:
        comp_token = tuple(comp_ids)
    seed = (
        int(tick),
        stats.n_steps,
        stats.n_components,
        stats.diversity_final,
        round(stats.total_cumulative_activity, 6),
        round(stats.mean_cumulative_activity, 6),
        round(stats.max_component_activity, 6),
        stats.new_components_total,
        stats.new_components_tail,
        round(stats.innovation_rate_tail, 6),
        round(stats.significance_threshold, 6),
        stats.n_significant_components,
        stats.dynamics_class,
        comp_token,
    )
    return hashlib.sha256(repr(seed).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Emergent component usage (read-only world reads)
# ---------------------------------------------------------------------------

def component_usage(sim) -> Dict[str, float]:
    """Read the set of *present* heritable/innovable components from the sim.

    Pure read-only. Each present component contributes a unit of activity for
    the current tick. Sources are namespaced and probed defensively so the
    observer degrades gracefully when a subsystem is not wired:

    * ``inv:<id>`` — inventions in ``sim.invention_registry.artifacts``,
    * ``rec:<id>`` — recipes in ``sim._emergent_construction.discovered``,
    * ``lex:<id>`` — emergent lexicon tokens (memetic), if exposed.
    """
    usage: Dict[str, float] = {}

    reg = getattr(sim, "invention_registry", None)
    artifacts = getattr(reg, "artifacts", None) if reg is not None else None
    if isinstance(artifacts, Mapping):
        for key in artifacts:
            usage[f"inv:{key}"] = 1.0

    constr = getattr(sim, "_emergent_construction", None)
    discovered = getattr(constr, "discovered", None) if constr else None
    if discovered is not None:
        try:
            for key in discovered:
                usage[f"rec:{key}"] = 1.0
        except TypeError:
            pass

    memetic = getattr(sim, "_memetic", None)
    lexicon = getattr(memetic, "lexicon", None) if memetic else None
    if isinstance(lexicon, Mapping):
        for key in lexicon:
            usage[f"lex:{key}"] = 1.0

    return usage


# ---------------------------------------------------------------------------
# Observe (read-only)
# ---------------------------------------------------------------------------

def observe_evolutionary_activity(sim,
                                  config: Optional[EvoActivityConfig] = None
                                  ) -> Optional[EvoActivitySnapshot]:
    """Pure read-only evolutionary-activity snapshot.

    Computes the Bedau–Packard statistics over the usage series accumulated by
    an installed observer (if any) plus one freshly sampled frame. Never
    mutates the sim or the stored series; returns ``None`` only when no
    component source is available *and* no history exists.
    """
    cfg = config if config is not None else EvoActivityConfig()
    state: Optional[EvoActivityState] = getattr(
        sim, "_evo_activity_state", None)

    series: List[Dict[str, float]] = []
    if state is not None and state.usage_series:
        series = [dict(s) for s in state.usage_series]
    else:
        sample = component_usage(sim)
        if not sample and not series:
            return None
        series = [sample]

    stats = evolutionary_activity_stats(series, cfg)
    sig = _stats_signature(int(getattr(sim, "tick", 0)), stats, series, cfg)
    return EvoActivitySnapshot(
        tick=int(getattr(sim, "tick", 0)), stats=stats, signature=sig)


# ---------------------------------------------------------------------------
# Install / uninstall (mirrors waves 49 / 53 / 55 / 57)
# ---------------------------------------------------------------------------

def install_evolutionary_activity_observer(
        sim, config: Optional[EvoActivityConfig] = None) -> EvoActivityState:
    """Idempotent installer. Wraps ``sim.step`` once to sample the emergent
    component usage and capture a stats snapshot every ``snapshot_every``
    ticks."""
    cfg = config if config is not None else EvoActivityConfig()
    existing: Optional[EvoActivityState] = getattr(
        sim, "_evo_activity_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = EvoActivityState(config=cfg)
    sim._evo_activity_state = state

    original_step = sim.step

    def _wrapped_step(*args, **kwargs):
        result = original_step(*args, **kwargs)
        try:
            tick = int(sim.tick)
        except Exception:
            tick = 0
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            state.usage_series.append(component_usage(sim))
            stats = evolutionary_activity_stats(state.usage_series, cfg)
            sig = _stats_signature(tick, stats, state.usage_series, cfg)
            state.history.snapshots.append(
                EvoActivitySnapshot(tick=tick, stats=stats, signature=sig))
        return result

    sim._evo_activity_original_step = original_step
    sim.step = _wrapped_step
    state.wrapped = True
    sim._evo_activity_wrapped = True
    return state


def uninstall_evolutionary_activity_observer(sim) -> bool:
    """Restore the original ``sim.step``. ``True`` if anything was removed."""
    state = getattr(sim, "_evo_activity_state", None)
    if state is None:
        return False
    original = getattr(sim, "_evo_activity_original_step", None)
    if original is not None:
        sim.step = original
        del sim._evo_activity_original_step
    sim._evo_activity_wrapped = False
    del sim._evo_activity_state
    return True


def evolutionary_activity_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards / ``/api/emergence_metrics`` (read-only)."""
    state: Optional[EvoActivityState] = getattr(
        sim, "_evo_activity_state", None)
    if state is None:
        return {"installed": False}
    snaps = state.history.snapshots
    last = snaps[-1] if snaps else None
    s = last.stats if last is not None else None
    return {
        "installed": True,
        "n_snapshots": len(snaps),
        "snapshot_every": state.config.snapshot_every,
        "n_usage_steps": len(state.usage_series),
        "last_signature": (last.signature if last is not None else None),
        "last_tick": (last.tick if last is not None else None),
        "diversity_final": (s.diversity_final if s is not None else None),
        "mean_cumulative_activity": (
            s.mean_cumulative_activity if s is not None else None),
        "innovation_rate_tail": (
            s.innovation_rate_tail if s is not None else None),
        "n_significant_components": (
            s.n_significant_components if s is not None else None),
        "dynamics_class": (s.dynamics_class if s is not None else None),
    }


__all__ = [
    "EvoActivityConfig",
    "EvoActivityStats",
    "EvoActivitySnapshot",
    "EvoActivityHistory",
    "EvoActivityState",
    "diversity_curve",
    "new_component_curve",
    "component_activity",
    "total_activity_curve",
    "mean_activity_curve",
    "significance_threshold",
    "n_significant_components",
    "classify_dynamics",
    "evolutionary_activity_stats",
    "component_usage",
    "observe_evolutionary_activity",
    "install_evolutionary_activity_observer",
    "uninstall_evolutionary_activity_observer",
    "evolutionary_activity_summary",
]
