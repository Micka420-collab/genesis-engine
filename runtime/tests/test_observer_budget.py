"""D1 guardrail: observer-chain idempotency, stacking, and budget instrument.

Answers the two questions left open by the 2026-06-10 delta-audit (§D1) with
deterministic assertions instead of prose:

  1. Per-observer install is idempotent — installing twice does NOT re-wrap
     ``sim.step`` (proved by step-function identity, no timing involved).
  2. The chain depth is observable and the cumulative tick overhead is
     measurable (the ``overhead_fraction`` ratio is unit-tested clock-free).

Uses the real ``concavity`` and ``hypsometry`` observers against a minimal fake
sim, with ``snapshot_every=0`` so the wrap installs but never calls the snapshot
path — isolating pure wrap behaviour from observer internals.
"""
from __future__ import annotations

import math

import pytest

from engine import observer_budget as ob
from engine.concavity_observer import (
    ConcavityConfig,
    install_concavity_observer,
    uninstall_concavity_observer,
)
from engine.hypsometry_observer import (
    HypsometryConfig,
    install_hypsometry_observer,
    uninstall_hypsometry_observer,
)


class FakeSim:
    """Minimal sim: a ``step()`` that advances ``tick``. Enough to be wrapped."""

    def __init__(self) -> None:
        self.tick = 0
        self.steps = 0

    def step(self, *args, **kwargs):
        self.steps += 1
        self.tick += 1
        return None


def _install_concavity(sim):
    return install_concavity_observer(sim, ConcavityConfig(snapshot_every=0))


def _install_hypsometry(sim):
    return install_hypsometry_observer(sim, HypsometryConfig(snapshot_every=0))


# --- 1. overhead_fraction is a pure, deterministic ratio (no clock) ----------

def test_overhead_fraction_is_pure_ratio():
    assert ob.overhead_fraction(1.0, 1.5) == pytest.approx(0.5)
    assert ob.overhead_fraction(2.0, 2.0) == pytest.approx(0.0)
    # Unmeasurably-fast bare run must not masquerade as 0 % overhead.
    assert math.isinf(ob.overhead_fraction(0.0, 0.001))


# --- 2. per-observer install is idempotent (audit D1 question 1) -------------

def test_install_is_idempotent_no_double_wrap():
    sim = FakeSim()
    _install_concavity(sim)
    wrapped_once = sim.step
    assert ob.observer_wrap_depth(sim) == 1

    # Re-install: must reuse existing state and leave sim.step untouched.
    _install_concavity(sim)
    assert sim.step is wrapped_once, "second install re-wrapped sim.step"
    assert ob.observer_wrap_depth(sim) == 1
    assert ob.installed_observers(sim) == ["concavity"]


# --- 3. observers stack; depth is visible; LIFO uninstall restores -----------

def test_observers_stack_and_unwind_lifo():
    sim = FakeSim()
    _install_concavity(sim)
    inner_step = sim.step
    _install_hypsometry(sim)

    assert ob.observer_wrap_depth(sim) == 2
    assert ob.installed_observers(sim) == ["concavity", "hypsometry"]
    # Outer wrap really sits on top of the inner one.
    assert sim.step is not inner_step

    # LIFO: remove the outer observer first → inner chain is restored intact.
    uninstall_hypsometry_observer(sim)
    assert ob.observer_wrap_depth(sim) == 1
    assert ob.installed_observers(sim) == ["concavity"]
    assert sim.step is inner_step

    uninstall_concavity_observer(sim)
    assert ob.observer_wrap_depth(sim) == 0
    assert ob.installed_observers(sim) == []

    # Chain unwound cleanly: stepping still works and advances the tick.
    before = sim.tick
    sim.step()
    assert sim.tick == before + 1


# --- 4. measurement plumbing + budget guardrail ------------------------------

def test_measure_and_budget_guardrail():
    m = ob.measure_observer_overhead(
        FakeSim, [_install_concavity, _install_hypsometry], ticks=50
    )
    assert m["n_observers"] == 2
    assert m["ticks"] == 50
    assert m["observed_seconds"] >= 0.0
    assert m["installed"] == ["concavity", "hypsometry"]
    assert isinstance(m["overhead_fraction"], float)

    # Guardrail passes for any sane bound and trips for an impossible one.
    ob.assert_observer_budget({"overhead_fraction": 0.05, "n_observers": 2,
                               "ticks": 50}, max_fraction=0.10)
    with pytest.raises(AssertionError, match="exceeds budget"):
        ob.assert_observer_budget({"overhead_fraction": 0.5, "n_observers": 2,
                                   "ticks": 50}, max_fraction=0.10)


def test_measure_rejects_nonpositive_ticks():
    with pytest.raises(ValueError):
        ob.measure_observer_overhead(FakeSim, [], ticks=0)
