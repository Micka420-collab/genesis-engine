"""Observer-chain introspection & tick-budget guardrail (audit risk D1).

Genesis ships scientific phenomena as read-only *observers* (``engine/*_observer.py``)
that each wrap ``sim.step`` **once** to capture a snapshot every N ticks. The
2026-06-10 delta-audit (``native/world-engine/AUDIT-DELTA-2026-06-10.md`` §D1)
flagged this as an *observer treadmill*: 14 observers shipped in 14 days, each
additive to the tick, with two open questions left unanswered —

  1. Is the per-observer install genuinely idempotent (no double-wrap)?
  2. What fraction of the tick do the chained observers cost cumulatively?

This module answers both *deterministically* and *without modifying any observer*.
It is pure instrumentation: it never mutates the world and adds nothing to the
tick unless a caller explicitly measures.

Wrap convention
---------------
Every observer ``X`` sets ``sim._X_wrapped = True`` when installed and
``False``/deletes it when uninstalled (see e.g. ``concavity_observer``,
``hypsometry_observer``). ``installed_observers`` discovers them generically from
that sentinel, so it needs no hard-coded registry and stays correct as observers
come and go.

Cross-observer ordering
-----------------------
Observers form a *stack*: observer B wraps A's already-wrapped ``sim.step``.
Therefore uninstalling must happen **in reverse install order (LIFO)**. Removing
an inner observer first restores ``sim.step`` to its captured original and
silently drops every outer wrap. ``observer_wrap_depth`` makes that stack depth
visible so a caller can assert the chain is what it expects.
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, List

__all__ = [
    "WRAP_SENTINEL_RE",
    "installed_observers",
    "observer_wrap_depth",
    "overhead_fraction",
    "measure_observer_overhead",
    "assert_observer_budget",
    "DEFAULT_TICK_BUDGET",
]

# An observer marks itself installed with ``sim._<name>_wrapped = True``.
WRAP_SENTINEL_RE = re.compile(r"^_(?P<name>.+)_wrapped$")

# Audit D1 target: the whole observer chain should cost < 10 % of the tick.
DEFAULT_TICK_BUDGET = 0.10


def installed_observers(sim: Any) -> List[str]:
    """Return the sorted names of observers currently wrapping ``sim.step``.

    Detected generically from the ``_<name>_wrapped`` truthy sentinels, so this
    reflects reality even for observers added after this module was written.
    """
    found: List[str] = []
    for attr, value in vars(sim).items():
        if not value:
            continue
        m = WRAP_SENTINEL_RE.match(attr)
        if m is not None:
            found.append(m.group("name"))
    return sorted(found)


def observer_wrap_depth(sim: Any) -> int:
    """How many observers are stacked on ``sim.step`` (== chain depth)."""
    return len(installed_observers(sim))


def overhead_fraction(bare_seconds: float, observed_seconds: float) -> float:
    """Relative cost the observer chain adds over a bare run.

    ``(observed - bare) / bare``. Pure and deterministic — the timing-free core
    so the ratio logic is unit-testable without a clock. Returns ``inf`` when the
    bare run is unmeasurably fast (avoids a divide-by-zero masquerading as 0 %).
    """
    if bare_seconds <= 0.0:
        return float("inf")
    return (observed_seconds - bare_seconds) / bare_seconds


def measure_observer_overhead(
    make_sim: Callable[[], Any],
    install_fns: List[Callable[[Any], Any]],
    *,
    ticks: int = 200,
) -> Dict[str, Any]:
    """Time ``ticks`` bare steps vs. the same steps with ``install_fns`` applied.

    ``make_sim`` must return a fresh, independent sim each call (one for the bare
    baseline, one for the observed run) so the two measurements don't share
    wrapped state. Returns a measurement dict consumable by
    ``assert_observer_budget``. Wall-clock by nature — treat a single reading as
    indicative, not a hard SLA; gate CI on a generous bound, not a tight one.
    """
    if ticks <= 0:
        raise ValueError("ticks must be positive")

    bare = make_sim()
    t0 = time.perf_counter()
    for _ in range(ticks):
        bare.step()
    bare_seconds = time.perf_counter() - t0

    observed = make_sim()
    for fn in install_fns:
        fn(observed)
    t0 = time.perf_counter()
    for _ in range(ticks):
        observed.step()
    observed_seconds = time.perf_counter() - t0

    return {
        "ticks": ticks,
        "n_observers": len(install_fns),
        "bare_seconds": bare_seconds,
        "observed_seconds": observed_seconds,
        "overhead_fraction": overhead_fraction(bare_seconds, observed_seconds),
        "installed": installed_observers(observed),
    }


def assert_observer_budget(
    measurement: Dict[str, Any],
    *,
    max_fraction: float = DEFAULT_TICK_BUDGET,
) -> None:
    """Raise ``AssertionError`` if the observer chain blew the tick budget.

    Opt-in guardrail — callers (a bench, a long-run harness) decide the bound.
    Kept out of the unit-test fast path because absolute timings are machine- and
    load-dependent; use it where a stable, warm measurement is available.
    """
    frac = measurement["overhead_fraction"]
    if frac > max_fraction:
        raise AssertionError(
            f"observer chain overhead {frac:.1%} exceeds budget {max_fraction:.1%} "
            f"({measurement['n_observers']} observers, {measurement['ticks']} ticks; "
            f"installed={measurement.get('installed')})"
        )
