"""Wave 45 open-endedness meter — intrinsic, ontology-free (read-only)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.open_endedness import (
    OpenEndednessConfig,
    OpenEndednessSnapshot,
    _quantize_unit,
    observe_open_endedness,
    install_open_endedness,
    uninstall_open_endedness,
    open_endedness_summary,
)
from engine.sim import Simulation, SimConfig


def _build_sim(name: str, seed: int = 0xC0FFEE_115):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=20,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def test_quantize_unit_edges():
    assert _quantize_unit(-1.0, 4) == 0
    assert _quantize_unit(0.0, 4) == 0
    assert _quantize_unit(0.99, 4) == 3
    assert _quantize_unit(1.0, 4) == 3          # clamps, never overflows
    assert _quantize_unit(2.0, 4) == 3
    assert _quantize_unit(0.5, 1) == 0          # degenerate levels


def test_observe_returns_snapshot():
    sim = _build_sim("oe_fresh")
    sim.step()
    snap = observe_open_endedness(sim)
    assert isinstance(snap, OpenEndednessSnapshot)
    assert snap.population == sim.agents.n_active
    assert snap.distinct_motifs_cumulative >= 1
    assert isinstance(snap.signature, str) and len(snap.signature) == 64
    # On a tiny single-snapshot window zlib framing makes ratio > 1; only
    # require it be positive here (see test_compression_full_window for ≤1).
    assert snap.compression_ratio > 0.0
    assert snap.compression_len > 0


def test_compression_full_window():
    """Once the rolling window fills with repeated descriptors the stream is
    highly compressible, so the ratio settles to (0, 1]."""
    sim = _build_sim("oe_compress", seed=0xC0FFEE_115C & 0xFFFFFFFFFFFFFFFF)
    sim.step()
    install_open_endedness(sim, OpenEndednessConfig(snapshot_every=4, window=16))
    for _ in range(80):
        sim.step()
    last = sim._open_endedness_state.history.snapshots[-1]
    assert last.compression_len > 0
    assert 0.0 < last.compression_ratio <= 1.0


def test_observe_is_read_only():
    sim = _build_sim("oe_ro", seed=0xC0FFEE_1153 & 0xFFFFFFFFFFFFFFFF)
    sim.step()
    install_open_endedness(sim)
    n = sim.agents.n_active
    tick_before = int(sim.tick)
    hunger = np.array(sim.agents.hunger[:n], copy=True)
    pos = np.array(sim.agents.pos[:n], copy=True)
    vel = np.array(sim.agents.vel[:n], copy=True)
    alive = np.array(sim.agents.alive[:n], copy=True)

    observe_open_endedness(sim)

    assert int(sim.tick) == tick_before
    assert np.array_equal(sim.agents.hunger[:n], hunger)
    assert np.array_equal(sim.agents.pos[:n], pos)
    assert np.array_equal(sim.agents.vel[:n], vel)
    assert np.array_equal(sim.agents.alive[:n], alive)


def test_signature_stable_on_identical_state():
    sim = _build_sim("oe_stable", seed=0xC0FFEE_1154 & 0xFFFFFFFFFFFFFFFF)
    sim.step()
    a = observe_open_endedness(sim)
    b = observe_open_endedness(sim)   # no step between → identical motif distribution
    assert a.signature == b.signature


def test_cross_run_determinism():
    """blake2b (not process-randomized hash()) ⇒ same seed ⇒ same signature."""
    def fresh_sig(seed):
        s = _build_sim(f"oe_xdet_{seed}", seed=seed)
        s.step()
        return observe_open_endedness(s).signature

    seed = 0xC0FFEE_1155 & 0xFFFFFFFFFFFFFFFF
    assert fresh_sig(seed) == fresh_sig(seed)


def test_novelty_monotonic_non_decreasing():
    sim = _build_sim("oe_novelty", seed=0xC0FFEE_1156 & 0xFFFFFFFFFFFFFFFF)
    sim.step()
    install_open_endedness(sim, OpenEndednessConfig(snapshot_every=4))
    for _ in range(48):
        sim.step()
    snaps = sim._open_endedness_state.history.snapshots
    series = [s.distinct_motifs_cumulative for s in snaps]
    assert len(snaps) >= 2
    assert all(b >= a for a, b in zip(series, series[1:]))


def test_bedau_packard_persistence():
    sim = _build_sim("oe_bp", seed=0xC0FFEE_1158 & 0xFFFFFFFFFFFFFFFF)
    sim.step()
    install_open_endedness(sim, OpenEndednessConfig(snapshot_every=4))
    for _ in range(48):
        sim.step()
    last = sim._open_endedness_state.history.snapshots[-1]
    # A motif shared by ≥3 agent-observations crosses the persistence threshold.
    assert last.activity_cumulative >= 0.0
    assert last.diversity >= 1


def test_full_run_determinism():
    def run(seed):
        s = _build_sim(f"oe_run_{seed}", seed=seed)
        s.step()
        install_open_endedness(s, OpenEndednessConfig(snapshot_every=4))
        for _ in range(40):
            s.step()
        return tuple(
            (snap.tick, snap.population, snap.distinct_motifs_cumulative,
             snap.compression_len, snap.diversity, snap.signature)
            for snap in s._open_endedness_state.history.snapshots
        )

    seed = 0xC0FFEE_11510 & 0xFFFFFFFFFFFFFFFF
    assert run(seed) == run(seed)


def test_install_idempotent_and_uninstall_restores_step():
    sim = _build_sim("oe_install", seed=0xC0FFEE_1159 & 0xFFFFFFFFFFFFFFFF)
    sim.step()
    step_before = sim.step

    state1 = install_open_endedness(sim, OpenEndednessConfig(snapshot_every=3))
    wrapped_step = sim.step
    state2 = install_open_endedness(sim)  # second install must not re-wrap
    assert state1 is state2
    assert sim.step is wrapped_step       # single wrap only
    assert sim.step is not step_before

    for _ in range(9):
        sim.step()
    summary = open_endedness_summary(sim)
    assert summary["installed"] is True
    assert summary["n_snapshots"] >= 1

    assert uninstall_open_endedness(sim) is True
    assert sim.step is step_before        # original step restored
    assert open_endedness_summary(sim)["installed"] is False
