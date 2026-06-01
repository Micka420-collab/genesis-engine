"""P125 — Wave 56 geothermal gradient & metamorphic-facies observer smoke.

 1. Public API exposed.
 2. geotherm_temperature: equals surface T at z=0; strictly ↑ with depth.
 3. metamorphic_grade / classify_facies: grade ↑ with T; high-P branch maps.
 4. compute_column on a synthetic column: T strictly ↑, P strictly ↑,
    grade non-decreasing.
 5. observe_geotherm returns a sane snapshot on a real Genesis world.
 6. Snapshot is read-only: geology layers + sim tick unchanged.
 7. Geotherm invariant holds (T↑, P↑, grade↑ with depth in every column).
 8. Deep layers reach metamorphic conditions (max grade ≥ shallow grade).
 9. install / uninstall wrap restore: sim.step round-trip.
10. Cross-sim determinism: same world seed ⇒ same signature.
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
from engine.genesis_bootstrap import bootstrap_genesis_sim             # noqa: E402
from engine import geology as geo                                       # noqa: E402
from engine.geotherm_observer import (                                  # noqa: E402
    GeothermConfig, LayerThermal, GeothermSnapshot,
    GeothermHistory, GeothermState,
    geotherm_temperature, metamorphic_grade, classify_facies,
    compute_column, column_geotherm_monotonic, observe_geotherm,
    install_geotherm_observer, uninstall_geotherm_observer,
    geotherm_summary,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


class _FakeLayer:
    def __init__(self, top, bottom, rock, density):
        self.depth_top_m = top
        self.depth_bottom_m = bottom
        self.rock_type = rock
        self.density_kg_m3 = density


class _FakeColumn:
    def __init__(self, layers):
        self.layers = layers


def _build_sim(name: str, seed: int = 0xCAFE_0123):
    cfg = SimConfig(
        name=name, seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=4, max_agents=20,
        bounds_km=(0.3, 0.3), spawn_radius_m=40.0,
        drive_accel=1500.0, cultures=1,
    )
    return Simulation(cfg)


def _booted_sim(name, seed=0xCAFE_0123, resolution=64):
    sim = _build_sim(name, seed=seed)
    gp = GenesisParams(seed=seed, resolution=resolution, n_plates=8)
    bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    return sim


def _populate_geology(sim, grid=5):
    geo.install_geology(sim)
    for cx in range(grid):
        for cy in range(grid):
            coord = (cx, cy, 0)
            if sim.streamer.get(0, coord) is not None:
                geo.chunk_geology(sim, coord)
    return sim._geology_state


def main() -> int:
    print("P125 — Wave 56 geothermal gradient & metamorphic-facies smoke")
    print("=" * 72)
    rows = []
    ok_all = True

    # 1. Public API.
    api = all(callable(f) or f is not None for f in (
        geotherm_temperature, metamorphic_grade, classify_facies,
        compute_column, column_geotherm_monotonic, observe_geotherm,
        install_geotherm_observer, uninstall_geotherm_observer,
        geotherm_summary,
        GeothermConfig, LayerThermal, GeothermSnapshot))
    rows.append(_row("public API exposed", api))
    ok_all &= api

    # 2. geotherm_temperature: surface anchor + strictly increasing.
    cfg = GeothermConfig()
    t0 = geotherm_temperature(0.0, cfg)
    incr = (abs(t0 - cfg.surface_temp_c) < 1e-12 and
            geotherm_temperature(1000.0, cfg) > t0 and
            geotherm_temperature(20000.0, cfg) >
            geotherm_temperature(1000.0, cfg))
    rows.append(_row("geotherm: T(0)=Tsurf and strictly ↑ with depth", incr,
                     f"T0={t0:.1f}°C  T@20km={geotherm_temperature(20000.0, cfg):.0f}°C"))
    ok_all &= incr

    # 3. grade + facies classifiers.
    g_shallow = metamorphic_grade(50.0, cfg)
    g_deep = metamorphic_grade(700.0, cfg)
    facies_ok = (
        g_shallow == 0 and g_deep == 4 and
        metamorphic_grade(700.0, cfg) >= metamorphic_grade(300.0, cfg) and
        classify_facies(300.0, 50.0, cfg) == "greenschist" and
        classify_facies(300.0, 900.0, cfg) == "blueschist" and
        classify_facies(400.0, 1300.0, cfg) == "eclogite")
    rows.append(_row("grade ↑ with T; high-P → blueschist/eclogite", facies_ok,
                     f"grade(50)={g_shallow} grade(700)={g_deep}"))
    ok_all &= facies_ok

    # 4. Synthetic column: T strictly ↑, P strictly ↑, grade non-decreasing.
    synth = _FakeColumn([
        _FakeLayer(0.0, 1.0, "shale", 1500.0),
        _FakeLayer(1.0, 5.0, "sandstone", 1800.0),
        _FakeLayer(5.0, 200.0, "limestone", 2300.0),
        _FakeLayer(200.0, 6000.0, "granite", 2700.0),
        _FakeLayer(6000.0, 30000.0, "gneiss", 2850.0),
    ])
    cols = compute_column(synth, cfg)
    temp = [c.temperature_c for c in cols]
    pres = [c.pressure_mpa for c in cols]
    grade = [c.metamorphic_grade for c in cols]
    strict = (all(b > a for a, b in zip(temp, temp[1:])) and
              all(b > a for a, b in zip(pres, pres[1:])) and
              all(b >= a for a, b in zip(grade, grade[1:])))
    rows.append(_row("synthetic column: T↑ P↑ grade↑ with depth", strict,
                     f"T={temp[0]:.0f}→{temp[-1]:.0f}°C  "
                     f"P={pres[0]:.2f}→{pres[-1]:.0f}MPa  grade→{grade[-1]}"))
    ok_all &= strict

    # 5. Real-world snapshot.
    sim = _booted_sim("p125_obs")
    gs = _populate_geology(sim)
    snap = observe_geotherm(gs, cfg, tick=0)
    sane = (isinstance(snap, GeothermSnapshot) and
            snap.total_layers > 0 and snap.n_chunks > 0 and
            snap.max_temperature_c >= snap.surface_temperature_c and
            snap.max_pressure_mpa >= 0.0)
    rows.append(_row("observe_geotherm snapshot on Genesis world", sane,
                     f"layers={snap.total_layers} maxT={snap.max_temperature_c:.0f}°C "
                     f"maxP={snap.max_pressure_mpa:.1f}MPa "
                     f"meta={snap.metamorphosed_layers} facies={snap.deepest_facies}"))
    ok_all &= sane

    # 6. Read-only: layers + tick unchanged.
    coord0 = sorted(gs.chunks.keys())[0]
    before = [(L.depth_top_m, L.depth_bottom_m, L.density_kg_m3)
              for L in gs.chunks[coord0].layers]
    before_tick = int(getattr(sim, "tick", 0))
    _ = observe_geotherm(gs, cfg, tick=0)
    after = [(L.depth_top_m, L.depth_bottom_m, L.density_kg_m3)
             for L in gs.chunks[coord0].layers]
    read_only = (before == after and
                 int(getattr(sim, "tick", 0)) == before_tick)
    rows.append(_row("observation is read-only (layers + tick)", read_only))
    ok_all &= read_only

    # 7. Geotherm invariant on the real world.
    rows.append(_row("geotherm invariant (T↑, P↑, grade↑ with depth)",
                     snap.geotherm_monotonic_ok))
    ok_all &= snap.geotherm_monotonic_ok

    # 8. Deep layers warmer than the surface (geotherm has bite).
    warmed = snap.max_temperature_c > snap.surface_temperature_c
    rows.append(_row("deep column warmer than surface (geotherm)", warmed,
                     f"surf={snap.surface_temperature_c:.0f}°C "
                     f"max={snap.max_temperature_c:.0f}°C"))
    ok_all &= warmed

    # 9. install / uninstall round-trip.
    orig_step = sim.step
    st = install_geotherm_observer(sim, cfg)
    installed = (getattr(sim, "_geotherm_state", None) is st and
                 sim.step is not orig_step)
    uninstall_geotherm_observer(sim)
    restored = (sim.step is orig_step and
                getattr(sim, "_geotherm_state", None) is None)
    rows.append(_row("install / uninstall wrap restore",
                     installed and restored))
    ok_all &= (installed and restored)

    # 10. Cross-sim determinism.
    sim_b = _booted_sim("p125_obs")          # same seed
    gs_b = _populate_geology(sim_b)
    snap_b = observe_geotherm(gs_b, cfg, tick=0)
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
