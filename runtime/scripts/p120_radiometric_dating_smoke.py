"""P120 — Wave 51 radiometric (absolute) dating observer smoke.

 1. Public API exposed.
 2. select_isotopic_system picks the right chronometer per age band.
 3. Decay law round-trips: recovered age == emergent age (closure).
 4. Daughter/parent ratio is monotincreasing with age; parent fraction falls.
 5. observe_radiometric returns a sane snapshot on a real Genesis world.
 6. Snapshot is read-only: geology layers + sim tick unchanged.
 7. Absolute ages are concordant with superposition (non-decreasing w/ depth).
 8. Datable layers are a subset of total layers; histogram sums to datable.
 9. install / uninstall wrap restore: sim.step round-trip.
10. Cross-sim determinism: same world seed ⇒ same signature.
"""
from __future__ import annotations

import io
import math
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
from engine import geology as geo                                       # noqa: E402
from engine.radiometric_dating import (                                 # noqa: E402
    Isotope, ISOTOPES, ISOTOPE_BY_NAME, SYSTEM_NAMES,
    RadiometricConfig, LayerDate, RadiometricSnapshot,
    RadiometricHistory, RadiometricState,
    select_isotopic_system, date_layer, date_column,
    column_concordant, observe_radiometric,
    install_radiometric_observer, uninstall_radiometric_observer,
    radiometric_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def _build_sim(name: str, seed: int = 0xCAFE_0120):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=20,
        bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def _booted_sim(name, seed=0xCAFE_0120, resolution=64):
    sim = _build_sim(name, seed=seed)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


def _populate_geology(sim, grid=5):
    """Stream a small grid of chunks into the cache, then lazily generate
    their emergent strata so the observer has real columns to date. The
    only side effect is the standard lazy chunk + strata creation that the
    live engine performs anyway."""
    geo.install_geology(sim)
    for cx in range(grid):
        for cy in range(grid):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
    return sim._geology_state


def main() -> int:
    print("P120 — Wave 51 radiometric (absolute) dating observer smoke")
    print("=" * 72)
    rows = []
    ok_all = True

    # 1. Public API.
    api = all(callable(f) or f is not None for f in (
        select_isotopic_system, date_layer, date_column, column_concordant,
        observe_radiometric, install_radiometric_observer,
        uninstall_radiometric_observer, radiometric_summary,
        RadiometricConfig, LayerDate, RadiometricSnapshot, Isotope))
    rows.append(_row("public API exposed", api))
    ok_all &= api

    # 2. System selection per band.
    sel = (
        select_isotopic_system(0.01).name == "C-14" and
        select_isotopic_system(0.2).name == "U-Th" and
        select_isotopic_system(10.0).name == "K-Ar" and
        select_isotopic_system(540.0).name == "U-Pb" and
        select_isotopic_system(0.0) is None
    )
    rows.append(_row("isotopic system selection per age band", sel))
    ok_all &= sel

    # 3. Decay-law closure: recovered == emergent for a spread of ages.
    closure = True
    worst = 0.0
    for age in (0.005, 0.02, 0.2, 5.0, 60.0, 540.0, 1100.0, 3000.0):
        ld = date_layer(age)
        if ld is None:
            closure = False
            break
        worst = max(worst, abs(ld.recovered_age_ma - age))
    closure &= worst < 1e-6
    rows.append(_row("decay-law closure (recovered == emergent)",
                     closure, f"max residual={worst:.2e} Ma"))
    ok_all &= closure

    # 4. Monotonic decay signals within one system (K-Ar band).
    d5 = date_layer(5.0)
    d60 = date_layer(60.0)
    mono = (d5 is not None and d60 is not None and
            d60.daughter_parent_ratio > d5.daughter_parent_ratio and
            d60.parent_fraction < d5.parent_fraction)
    rows.append(_row("daughter/parent ↑ and parent fraction ↓ with age",
                     mono))
    ok_all &= mono

    # 5. Real-world snapshot.
    sim = _booted_sim("p120_obs")
    gs = _populate_geology(sim)
    cfg = RadiometricConfig()
    snap = observe_radiometric(gs, cfg, tick=0)
    sane = (isinstance(snap, RadiometricSnapshot) and
            snap.total_layers > 0 and snap.datable_layers > 0 and
            snap.oldest_age_ma > 0.0 and snap.oldest_system in SYSTEM_NAMES)
    rows.append(_row("observe_radiometric snapshot on Genesis world", sane,
                     f"datable={snap.datable_layers}/{snap.total_layers} "
                     f"oldest={snap.oldest_age_ma:.0f}Ma ({snap.oldest_system})"))
    ok_all &= sane

    # 6. Read-only: layers + tick unchanged.
    coord0 = sorted(gs.chunks.keys())[0]
    before_ages = [L.age_ma for L in gs.chunks[coord0].layers]
    before_tick = int(getattr(sim, "tick", 0))
    _ = observe_radiometric(gs, cfg, tick=0)
    after_ages = [L.age_ma for L in gs.chunks[coord0].layers]
    read_only = (before_ages == after_ages and
                 int(getattr(sim, "tick", 0)) == before_tick)
    rows.append(_row("observation is read-only (layers + tick)", read_only))
    ok_all &= read_only

    # 7. Concordance with superposition.
    conc = snap.concordance_ok and snap.max_closure_residual_ma < cfg.closure_tol_ma
    rows.append(_row("absolute ages concordant w/ superposition", conc,
                     f"residual={snap.max_closure_residual_ma:.2e} Ma"))
    ok_all &= conc

    # 8. Datable ⊆ total ; histogram sums to datable.
    hist_sum = sum(snap.system_histogram.values())
    subset = (snap.datable_layers <= snap.total_layers and
              hist_sum == snap.datable_layers and
              0.0 <= snap.datable_fraction <= 1.0)
    rows.append(_row("datable ⊆ total ; histogram sums to datable", subset,
                     f"hist={snap.system_histogram}"))
    ok_all &= subset

    # 9. install / uninstall round-trip.
    orig_step = sim.step
    st = install_radiometric_observer(sim, cfg)
    installed = (getattr(sim, "_radiometric_state", None) is st and
                 sim.step is not orig_step)
    uninstall_radiometric_observer(sim)
    restored = (sim.step is orig_step and
                getattr(sim, "_radiometric_state", None) is None)
    rows.append(_row("install / uninstall wrap restore",
                     installed and restored))
    ok_all &= (installed and restored)

    # 10. Cross-sim determinism.
    sim_b = _booted_sim("p120_obs")          # same seed
    gs_b = _populate_geology(sim_b)
    snap_b = observe_radiometric(gs_b, cfg, tick=0)
    det = snap_b.signature == snap.signature
    rows.append(_row("cross-sim determinism (same seed ⇒ same signature)",
                     det, f"sig={snap.signature}"))
    ok_all &= det

    print("\n".join(rows))
    print("=" * 72)
    n_ok = sum(1 for r in rows if "[OK" in r)
    print(f"{n_ok}/{len(rows)} checks passed")
    print("RESULT:", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
