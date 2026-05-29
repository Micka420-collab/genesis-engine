"""P115 — Wave 45 open-endedness meter smoke.

  1. Public API surface.
  2. Fresh sim → observe returns a sane snapshot (population, ≥1 motif, sha256 sig).
  3. Read-only contract : observe never mutates sim (tick + agent arrays frozen).
  4. Motif encoding determinism : two observes on the same state → same signature.
  5. Cross-sim determinism : same seed ⇒ identical observed signature (blake2b,
     NOT process-randomized hash()).
  6. Cumulative novelty N(t) is monotonic non-decreasing across a run.
  7. Compression complexity sane : len > 0 and ratio ∈ (0, 1].
  8. Bedau–Packard : activity accumulates and ≥1 motif becomes persistent.
  9. install / uninstall : sim.step is wrapped then fully restored.
 10. Installed observer full-run determinism (two runs, same seed → same stream).
"""
from __future__ import annotations

import io
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import numpy as np                                                      # noqa: E402

from engine.sim import Simulation, SimConfig                            # noqa: E402
from engine.open_endedness import (                                     # noqa: E402
    OpenEndednessConfig, OpenEndednessSnapshot, OpenEndednessHistory,
    OpenEndednessState,
    observe_open_endedness, install_open_endedness,
    uninstall_open_endedness, open_endedness_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xC0FFEE_115):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=20,
        bounds_km=(0.5, 0.5), spawn_radius_m=50.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def _run_observed(seed, snapshot_every=4, steps=40):
    """Install the meter on a fresh sim, run it, return the snapshot stream
    as a comparable tuple."""
    sub = _build_sim(f"p115_det_{seed}", seed=seed)
    sub.step()
    install_open_endedness(sub, OpenEndednessConfig(snapshot_every=snapshot_every))
    for _ in range(steps):
        sub.step()
    snaps = sub._open_endedness_state.history.snapshots
    return tuple(
        (s.tick, s.population, s.distinct_motifs_cumulative,
         s.new_motifs, s.compression_len, s.diversity,
         round(s.activity_cumulative, 3), s.signature)
        for s in snaps
    )


def main() -> int:
    print("=" * 78)
    print("P115 — Wave 45 open-endedness meter smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API.
    ok = all(name in globals() for name in (
        "OpenEndednessConfig", "OpenEndednessSnapshot", "OpenEndednessHistory",
        "OpenEndednessState",
        "observe_open_endedness", "install_open_endedness",
        "uninstall_open_endedness", "open_endedness_summary",
    ))
    print(_row("step 1 - public API exposed", ok))
    if not ok:
        failures += 1

    # Step 2 — fresh sim → sane snapshot.
    sim = _build_sim("p115_fresh")
    sim.step()
    snap = observe_open_endedness(sim)
    sig_ok = isinstance(snap.signature, str) and len(snap.signature) == 64
    ok = (snap.population == sim.agents.n_active
          and snap.distinct_motifs_cumulative >= 1
          and snap.population >= 1
          and sig_ok)
    print(_row("step 2 - fresh observe : population + ≥1 motif + sha256",
               ok, f"pop={snap.population} motifs={snap.distinct_motifs_cumulative} "
                   f"sig_len={len(snap.signature)}"))
    if not ok:
        failures += 1

    # Step 3 — read-only contract.
    sim3 = _build_sim("p115_readonly", seed=0xC0FFEE_1153 & 0xFFFFFFFFFFFFFFFF)
    sim3.step()
    install_open_endedness(sim3)  # state already attached; isolate the mutation test
    n = sim3.agents.n_active
    tick_before = int(sim3.tick)
    hunger_before = np.array(sim3.agents.hunger[:n], copy=True)
    pos_before = np.array(sim3.agents.pos[:n], copy=True)
    vel_before = np.array(sim3.agents.vel[:n], copy=True)
    alive_before = np.array(sim3.agents.alive[:n], copy=True)
    _ = observe_open_endedness(sim3)
    ok = (int(sim3.tick) == tick_before
          and np.array_equal(sim3.agents.hunger[:n], hunger_before)
          and np.array_equal(sim3.agents.pos[:n], pos_before)
          and np.array_equal(sim3.agents.vel[:n], vel_before)
          and np.array_equal(sim3.agents.alive[:n], alive_before))
    print(_row("step 3 - observe is read-only (sim arrays + tick frozen)",
               ok, f"tick={tick_before}->{int(sim3.tick)}"))
    if not ok:
        failures += 1

    # Step 4 — motif encoding determinism (same state → same signature).
    sim4 = _build_sim("p115_motif", seed=0xC0FFEE_1154 & 0xFFFFFFFFFFFFFFFF)
    sim4.step()
    s_a = observe_open_endedness(sim4)
    s_b = observe_open_endedness(sim4)  # no step in between
    ok = (s_a.signature == s_b.signature)
    print(_row("step 4 - motif signature stable on identical state",
               ok, f"match={s_a.signature == s_b.signature}"))
    if not ok:
        failures += 1

    # Step 5 — cross-sim determinism (blake2b, not process-randomized).
    def _fresh_sig(seed):
        s = _build_sim(f"p115_xdet_{seed}", seed=seed)
        s.step()
        return observe_open_endedness(s).signature
    seed_x = 0xC0FFEE_1155 & 0xFFFFFFFFFFFFFFFF
    sig1 = _fresh_sig(seed_x)
    sig2 = _fresh_sig(seed_x)
    ok = (sig1 == sig2)
    print(_row("step 5 - cross-sim determinism (same seed → same sig)",
               ok, f"match={sig1 == sig2}"))
    if not ok:
        failures += 1

    # Step 6 — cumulative novelty monotonic non-decreasing.
    sim6 = _build_sim("p115_novelty", seed=0xC0FFEE_1156 & 0xFFFFFFFFFFFFFFFF)
    sim6.step()
    install_open_endedness(sim6, OpenEndednessConfig(snapshot_every=4))
    for _ in range(48):
        sim6.step()
    snaps6 = sim6._open_endedness_state.history.snapshots
    novelty_series = [s.distinct_motifs_cumulative for s in snaps6]
    monotonic = all(b >= a for a, b in zip(novelty_series, novelty_series[1:]))
    ok = (len(snaps6) >= 2 and monotonic)
    print(_row("step 6 - cumulative novelty N(t) monotonic non-decreasing",
               ok, f"n_snaps={len(snaps6)} N(t)={novelty_series}"))
    if not ok:
        failures += 1

    # Step 7 — compression complexity sane.
    last6 = snaps6[-1]
    ok = (last6.compression_len > 0
          and 0.0 < last6.compression_ratio <= 1.0)
    print(_row("step 7 - compression len>0 and ratio ∈ (0,1]",
               ok, f"len={last6.compression_len} ratio={last6.compression_ratio:.4f}"))
    if not ok:
        failures += 1

    # Step 8 — Bedau–Packard activity / persistence.
    activity_series = [s.activity_cumulative for s in snaps6]
    activity_grows = activity_series[-1] >= activity_series[0]
    ok = (activity_grows and last6.activity_cumulative >= 0.0
          and last6.diversity >= 1)
    print(_row("step 8 - Bedau–Packard activity grows, ≥1 persistent motif",
               ok, f"A(t)={last6.activity_cumulative:.1f} D(t)={last6.diversity}"))
    if not ok:
        failures += 1

    # Step 9 — install / uninstall restores sim.step.
    sim9 = _build_sim("p115_install", seed=0xC0FFEE_1159 & 0xFFFFFFFFFFFFFFFF)
    sim9.step()
    step_before = sim9.step
    install_open_endedness(sim9, OpenEndednessConfig(snapshot_every=3))
    wrapped = sim9.step is not step_before and getattr(sim9, "_open_endedness_wrapped", False)
    for _ in range(9):
        sim9.step()
    summary_installed = open_endedness_summary(sim9)
    restored = uninstall_open_endedness(sim9)
    step_after = sim9.step
    ok = (wrapped
          and summary_installed.get("installed") is True
          and summary_installed.get("n_snapshots", 0) >= 1
          and restored
          and step_after is step_before
          and open_endedness_summary(sim9).get("installed") is False)
    print(_row("step 9 - install wraps step, uninstall restores it",
               ok, f"wrapped={wrapped} restored={restored} "
                   f"n_snaps={summary_installed.get('n_snapshots')}"))
    if not ok:
        failures += 1

    # Step 10 — installed observer full-run determinism.
    seed_d = 0xC0FFEE_11510 & 0xFFFFFFFFFFFFFFFF
    h_a = _run_observed(seed_d)
    h_b = _run_observed(seed_d)
    ok = (h_a == h_b and len(h_a) >= 2)
    print(_row("step 10 - installed observer full-run determinism",
               ok, f"len={len(h_a)} match={h_a == h_b}"))
    if not ok:
        failures += 1

    # Diagnostic dump.
    print(f"\nOpen-endedness summary on sim6: {open_endedness_summary(sim6)}")

    total = 10
    passed = total - failures
    print("=" * 78)
    if failures == 0:
        print(f"RESULT: {total}/{total} PASS")
        return 0
    else:
        print(f"RESULT: {passed}/{total} PASS, {failures} FAIL")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
