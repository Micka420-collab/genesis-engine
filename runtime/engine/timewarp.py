"""Genesis Engine — Time-warp adaptive simulation speed (Sprint A3).

Implements Architecture §25 ("Temps Accéléré") on top of the existing sim
without rewriting it. Attaches via :func:`install_timewarp`; sub-systems
gracefully degrade as the speed multiplier rises::

  realtime  → full fidelity (every sub-tick every tick)
  x10       → full step runs 1 in every 10 ticks; on the other 9 we do
              a lightweight statistical advance (drives drift, seasons,
              tick++). Sub-systems still self-gate so even on full-step
              ticks atmosphere / vegetation / erosion / wildlife / trails
              / disease / tech_discovery / chronic_fatigue run 1 of 10.
  x100      → as x10 but ratio is 1/100. Per-agent loop bypassed on
              off-ticks. ~50-100× wall-clock speedup.
  x1000     → statistical mode (fallback): per-agent loop is bypassed,
              all sub-systems skipped except seasons + drives drift.
              sim.tick advances normally so timelines stay consistent.
              FALLBACK NOTE: a fully aggregated demographic model would
              be ideal but is out of scope for A3 — we instead skip
              999 of 1000 inner steps and advance the clock + season
              + drive drifts in a lightweight loop. Determinism preserved.
  milestone → keep running ticks until annalist reports a new event of
              kind 'birth' / 'death' / 'invent' / 'mating_success' /
              'group_formed' (or until ``max_ticks`` safety bound).

Determinism guarantee: same (seed, mode-sequence, tick-count) → same final
state. Mode toggling itself is deterministic and the ``prf_rng`` namespace
``timewarp`` is reserved for any stochastic drift introduced here.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from engine.core import prf_rng


# Sub-system functions we will gate. Imported lazily so this module is
# safe to import in isolation. Each entry is (module_name, attr_name).
_SUBSYS_TARGETS = [
    ("engine.sim_5cd_integration", "tick_atmosphere"),
    ("engine.sim_5cd_integration", "tick_tech_discovery"),
    ("engine.sim_5cd_integration", "tick_chronic_fatigue"),
    ("engine.sim_lift",            "tick_vegetation"),
    ("engine.sim_lift",            "tick_erosion"),
    ("engine.realism",             "tick_wildlife"),
    ("engine.realism",             "tick_trails"),
    ("engine.realism",             "tick_disease"),
]

# Modes & their divisor for sub-system ticks (1 == every tick).
_MODE_DIVISORS = {
    "realtime":  1,
    "x10":       10,
    "x100":      100,
    "x1000":     1000,
    "milestone": 1,   # milestone uses full fidelity ticks
}

# Modes that skip the per-agent perceive/decide loop on off-ticks.
# At x10, x100, x1000 we run the full inner step every Nth tick and a
# lightweight statistical advance on the remaining (N-1) ticks — this is
# what delivers the wall-clock speedup, since the per-agent loop dominates
# cost. The sub-system gating below still applies on the full-step ticks
# so the spec's "sub-systems run 1/N" semantics are preserved.
_AGENT_LOOP_SKIP_MODES = {"x10", "x100", "x1000"}

# Drives that drift each tick during statistical mode (x1000).
_DRIFT_PER_S = {
    # name → per-second rate (matches engine.sim constants)
    "hunger":  0.000115,
    "thirst":  0.000231,
    "fatigue": 0.000077,
    "sleep":   0.000058,
}


class TimeWarp:
    """Per-sim time-warp controller. Construct via :func:`install_timewarp`.

    Public surface:
      * ``mode`` — current mode string
      * ``set_mode(mode)`` — change mode (thread-safe enough for dashboard use)
      * ``status()`` — dict snapshot
    """

    def __init__(self, sim) -> None:
        self.sim = sim
        self.mode: str = "realtime"
        self._installed = False
        self._rng = prf_rng(sim.cfg.seed, ["timewarp"], [0])
        # Milestone bookkeeping: track baseline event counters so we can
        # detect deltas against them.
        self._milestone_baseline: Optional[dict] = None
        self._milestone_max_ticks: int = 100_000

    # ---- mode setter ------------------------------------------------------

    def set_mode(self, mode: str) -> dict:
        if mode not in _MODE_DIVISORS:
            raise ValueError(f"unknown timewarp mode: {mode!r}")
        self.mode = mode
        if mode == "milestone":
            self._milestone_baseline = self._event_counters()
        else:
            self._milestone_baseline = None
        return self.status()

    # ---- introspection ----------------------------------------------------

    def status(self) -> dict:
        return {
            "mode": self.mode,
            "divisor": _MODE_DIVISORS[self.mode],
            "skip_agent_loop": self.mode in _AGENT_LOOP_SKIP_MODES,
            "tick": int(self.sim.tick),
        }

    def _event_counters(self) -> dict:
        a = self.sim.annalist
        return {
            "births": int(a.cum_births),
            "deaths": int(a.cum_deaths),
            "matings": int(getattr(a, "cum_matings", 0)),
            "groups_formed": int(getattr(a, "cum_groups_formed", 0)),
            # invent isn't tracked as a counter; approximate via artifact
            # registry size.
            "invent": (len(self.sim.invention_registry.artifacts)
                       if hasattr(self.sim, "invention_registry") else 0),
        }

    def _milestone_reached(self) -> bool:
        if self._milestone_baseline is None:
            return False
        cur = self._event_counters()
        for k, v in cur.items():
            if v > self._milestone_baseline.get(k, 0):
                return True
        return False


# ---------------------------------------------------------------------------
# Sub-system gating (monkey-patch the tick functions to early-return when
# the divisor says so). Idempotent: patching is global per-process.
# ---------------------------------------------------------------------------

_PATCHED_FLAG = "__timewarp_gated__"


def _gate_subsys(func, mod_name: str, attr_name: str):
    """Wrap a tick_* sub-system so it early-returns when the sim's
    timewarp divisor says to skip this tick."""
    if getattr(func, _PATCHED_FLAG, False):
        return func

    def gated(sim, *args, **kwargs):
        tw: Optional[TimeWarp] = getattr(sim, "timewarp", None)
        if tw is not None:
            div = _MODE_DIVISORS.get(tw.mode, 1)
            # During x100 / x1000 the entire sim.step is bypassed by the
            # outer wrapper, so this branch only matters for x10.
            if div > 1 and (int(sim.tick) % div) != 0:
                return None
        return func(sim, *args, **kwargs)

    setattr(gated, _PATCHED_FLAG, True)
    gated.__wrapped__ = func   # type: ignore[attr-defined]
    gated.__name__ = getattr(func, "__name__", attr_name)
    return gated


def _install_subsys_gates() -> None:
    """Monkey-patch all sub-system tick functions exactly once."""
    import importlib
    for mod_name, attr_name in _SUBSYS_TARGETS:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        fn = getattr(mod, attr_name, None)
        if fn is None or getattr(fn, _PATCHED_FLAG, False):
            continue
        setattr(mod, attr_name, _gate_subsys(fn, mod_name, attr_name))


# ---------------------------------------------------------------------------
# Lightweight statistical advance (for x100 / x1000)
# ---------------------------------------------------------------------------

def _stat_advance(sim, tw: TimeWarp, drift_seconds: float) -> None:
    """Advance the sim without running the full per-agent loop.

    What we do:
      * bump ``sim.tick``
      * drift hunger / thirst / fatigue / sleep for living agents
      * advance the seasonal clock if installed
      * give the annalist an empty record so metrics stay aligned
    """
    sim.tick += 1
    agents = sim.agents
    n = agents.n_active
    if n > 0:
        m = agents.alive[:n]
        if m.any():
            accel = float(sim.cfg.drive_accel) * drift_seconds
            for name, rate in _DRIFT_PER_S.items():
                arr = getattr(agents, name)
                arr[:n][m] = np.clip(arr[:n][m] + rate * accel, 0.0, 1.5)
    # Seasonal clock — keep wall-clock consistent in time-warp.
    clk = getattr(sim, "_realism_seasons", None)
    if clk is not None:
        clk.advance(float(sim.cfg.drive_accel))
    # Record an empty tick so annalist.metrics arrays stay tick-aligned.
    try:
        sim.annalist.record_tick(sim.tick, agents, births=[], deaths=[],
                                 raw_events=[])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------

def install_timewarp(sim) -> TimeWarp:
    """Attach a TimeWarp controller to ``sim``. Idempotent.

    Must be called AFTER the other installers (5cd / lift / realism) so
    its wrap is the outermost layer of ``sim.step``.
    """
    if getattr(sim, "_timewarp_installed", False):
        return sim.timewarp
    sim._timewarp_installed = True

    tw = TimeWarp(sim)
    sim.timewarp = tw

    _install_subsys_gates()

    original_step = sim.step

    def wrapped_step():
        mode = tw.mode

        # ---- milestone: run full ticks until a milestone event lands ----
        if mode == "milestone":
            if tw._milestone_baseline is None:
                tw._milestone_baseline = tw._event_counters()
            steps = 0
            stats = None
            while steps < tw._milestone_max_ticks:
                stats = original_step()
                steps += 1
                if tw._milestone_reached():
                    # Auto-disengage on milestone to avoid infinite advance.
                    tw.mode = "realtime"
                    tw._milestone_baseline = None
                    break
            return stats

        # ---- x100 / x1000: bypass per-agent loop entirely ---------------
        if mode in _AGENT_LOOP_SKIP_MODES:
            divisor = _MODE_DIVISORS[mode]
            # Every Nth tick we still run a real step so the world doesn't
            # diverge from reality (births/deaths/inventions happen).
            if (int(sim.tick) + 1) % divisor == 0:
                return original_step()
            _stat_advance(sim, tw, drift_seconds=1.0)
            return sim.stats

        # ---- realtime / x10 : run full step, sub-systems self-gate ------
        return original_step()

    sim.step = wrapped_step
    return tw


__all__ = ["TimeWarp", "install_timewarp"]
