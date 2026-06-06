"""P129 - Wave 60 behavioral illumination / Quality-Diversity observer smoke.

 1. Public API exposed.
 2. discretize : clamps + floor binning ; hi maps to last bin.
 3. MAP-Elites archive keeps the strict best quality per niche (tie-break).
 4. coverage : full grid filled => coverage == 1.0 ; empty => 0.0.
 5. niche_entropy : uniform quality => entropy ~ 1.0 ; single spike => low.
 6. behavioral_novelty : spread cloud is more novel than a tight cluster.
 7. observe_illumination is read-only on a real Genesis world.
 8. Repeated observe is deterministic (same signature / both None).
 9. Cross-sim determinism : same world seed => same snapshot signature.
10. install / uninstall round-trip + idempotent + captures cadence.
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

from engine.sim import Simulation, SimConfig                            # noqa: E402
from engine.world_genesis import GenesisParams                          # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim              # noqa: E402
from engine.illumination_observer import (                              # noqa: E402
    IlluminationConfig, IlluminationSnapshot,
    discretize, build_archive, coverage, qd_score, niche_entropy,
    behavioral_novelty, illumination_stats, agent_behaviors,
    observe_illumination, install_illumination_observer,
    uninstall_illumination_observer, illumination_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _booted_sim(name, seed=0x111_0129, resolution=64,
                river_threshold_cells=8.0):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=20,
        bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
        drive_accel=1500.0, cultures=1,
    )
    sim = Simulation(cfg)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8,
                       river_threshold_cells=river_threshold_cells)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


def main() -> int:
    print("=" * 78)
    print("P129 - Wave 60 behavioral illumination / Quality-Diversity observer")
    print("=" * 78)
    results = []
    snap = None

    # 1. API surface --------------------------------------------------------
    try:
        api_ok = all(callable(f) for f in (
            discretize, build_archive, coverage, qd_score, niche_entropy,
            behavioral_novelty, illumination_stats, agent_behaviors,
            observe_illumination, install_illumination_observer,
            uninstall_illumination_observer, illumination_summary))
        results.append(_row("step 1 - public API exposed", api_ok))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 1 - public API exposed", False))

    # 2. discretize clamps + floor binning ---------------------------------
    try:
        bins = 8
        lo_cell = discretize((-1.0, 0.0), bins)        # clamped low -> 0
        hi_cell = discretize((1.0, 2.0), bins)         # hi + over -> last bin
        mid_cell = discretize((0.5, 0.5), bins)        # floor(0.5*8)=4
        ok2 = (lo_cell == (0, 0) and hi_cell == (bins - 1, bins - 1)
               and mid_cell == (4, 4))
        results.append(_row("step 2 - discretize clamp/floor binning", ok2,
                            f"lo={lo_cell} hi={hi_cell} mid={mid_cell}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 2 - discretize clamp/floor binning", False))

    # 3. MAP-Elites archive keeps strict best per niche --------------------
    try:
        # Three behaviors in the same niche, qualities 0.2, 0.9, 0.5.
        beh = [((0.1, 0.1), 0.2), ((0.12, 0.11), 0.9), ((0.11, 0.12), 0.5)]
        arch = build_archive(beh, bins=8)
        ok3 = (len(arch) == 1 and abs(next(iter(arch.values())) - 0.9) < 1e-12)
        results.append(_row("step 3 - archive keeps strict best/niche", ok3,
                            f"n_niches={len(arch)} elite={next(iter(arch.values())):.2f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 3 - archive keeps strict best/niche", False))

    # 4. coverage : full grid => 1.0 , empty => 0.0 ------------------------
    try:
        bins = 4
        full = [((i / bins + 1e-3, j / bins + 1e-3), 1.0)
                for i in range(bins) for j in range(bins)]
        st_full = illumination_stats(full, IlluminationConfig(bins=bins))
        st_empty = illumination_stats([], IlluminationConfig(bins=bins))
        ok4 = (abs(st_full.coverage - 1.0) < 1e-9
               and st_full.occupied_niches == bins * bins
               and st_empty.coverage == 0.0)
        results.append(_row("step 4 - coverage full=1.0 / empty=0.0", ok4,
                            f"full={st_full.coverage:.3f} "
                            f"occ={st_full.occupied_niches}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 4 - coverage full=1.0 / empty=0.0", False))

    # 5. niche_entropy : uniform high, spike low ---------------------------
    try:
        bins = 4
        uniform = [((i / bins + 1e-3, j / bins + 1e-3), 1.0)
                   for i in range(bins) for j in range(bins)]
        spike = [((i / bins + 1e-3, j / bins + 1e-3),
                  100.0 if (i == 0 and j == 0) else 0.01)
                 for i in range(bins) for j in range(bins)]
        e_uni = niche_entropy(build_archive(uniform, bins))
        e_spk = niche_entropy(build_archive(spike, bins))
        ok5 = (abs(e_uni - 1.0) < 1e-9 and e_spk < 0.5)
        results.append(_row("step 5 - entropy uniform~1.0 / spike low", ok5,
                            f"uniform={e_uni:.3f} spike={e_spk:.3f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 5 - entropy uniform~1.0 / spike low", False))

    # 6. behavioral_novelty : spread > clustered ---------------------------
    try:
        clustered = [(0.50, 0.50), (0.51, 0.50), (0.50, 0.51), (0.49, 0.50)]
        spread = [(0.05, 0.05), (0.95, 0.05), (0.05, 0.95), (0.95, 0.95)]
        nov_c = behavioral_novelty(clustered, k=2)
        nov_s = behavioral_novelty(spread, k=2)
        ok6 = nov_s > nov_c
        results.append(_row("step 6 - novelty spread > clustered", ok6,
                            f"clustered={nov_c:.3f} spread={nov_s:.3f}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 6 - novelty spread > clustered", False))

    # 7. observe read-only on real Genesis world ---------------------------
    try:
        sim = _booted_sim("p129_real")
        for _ in range(20):            # let founders act so behaviors emerge
            sim.step()
        tick0 = int(sim.tick)
        beh0 = agent_behaviors(sim)
        snap = observe_illumination(sim)
        ok7 = (int(sim.tick) == tick0
               and agent_behaviors(sim) == beh0
               and (snap is None or isinstance(snap, IlluminationSnapshot)))
        results.append(_row("step 7 - observe read-only on Genesis world", ok7,
                            f"n_behaviors={len(beh0)}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 7 - observe read-only on Genesis world",
                            False))

    # 8. Repeated observe deterministic ------------------------------------
    try:
        sim = _booted_sim("p129_repeat")
        s1 = observe_illumination(sim)
        s2 = observe_illumination(sim)
        if s1 is None:
            ok8 = s2 is None
        else:
            ok8 = (s2 is not None and s1.signature == s2.signature)
        results.append(_row("step 8 - repeated observe deterministic", ok8))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 8 - repeated observe deterministic", False))

    # 9. Cross-sim determinism (install + step) ----------------------------
    try:
        sigs = []
        for _ in range(2):
            simd = _booted_sim("p129_det", seed=0x111_5252)
            install_illumination_observer(
                simd, IlluminationConfig(snapshot_every=1))
            for _ in range(3):
                simd.step()
            snaps = simd._illumination_state.history.snapshots
            sigs.append(snaps[-1].signature if snaps else None)
        ok9 = sigs[0] == sigs[1]
        results.append(_row("step 9 - cross-sim signature determinism", ok9,
                            f"sig={str(sigs[0])[:12]}..."))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 9 - cross-sim signature determinism", False))

    # 10. install / uninstall round-trip + cadence -------------------------
    try:
        sim4 = _booted_sim("p129_install")
        original_step = sim4.step
        state = install_illumination_observer(
            sim4, IlluminationConfig(snapshot_every=1))
        idem = install_illumination_observer(sim4) is state
        for _ in range(2):
            sim4.step()
        summ = illumination_summary(sim4)
        round_trip = (uninstall_illumination_observer(sim4)
                      and sim4.step is original_step)
        ok10 = (idem and summ["installed"] and round_trip)
        results.append(_row("step 10 - install/uninstall + cadence", ok10,
                            f"n_snaps={summ['n_snapshots']}"))
    except Exception:
        traceback.print_exc()
        results.append(_row("step 10 - install/uninstall + cadence", False))

    for line in results:
        print(line)

    if snap is not None:
        s = snap.stats
        print("\nSnapshot dump (sim p129_real) :")
        print(f"  n_behaviors        : {s.n_behaviors}")
        print(f"  n_dims / bins      : {s.n_dims} / {s.bins}")
        print(f"  total_niches       : {s.total_niches}")
        print(f"  occupied_niches    : {s.occupied_niches}")
        print(f"  coverage           : {s.coverage:.4f}")
        print(f"  qd_score           : {s.qd_score:.4f}")
        print(f"  mean / max quality : {s.mean_quality:.4f} / {s.max_quality:.4f}")
        print(f"  niche_entropy      : {s.niche_entropy:.4f}")
        print(f"  behavioral_novelty : {s.behavioral_novelty:.4f}")
        print(f"  best_niche         : {s.best_niche}")
        print(f"  signature          : {snap.signature}")

    passed = sum("[OK" in r for r in results)
    total = len(results)
    print("=" * 78)
    print(f"RESULT: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
