"""P123 — Wave 54 diagenetic compaction & lithostatic pressure observer smoke.

 1. Public API exposed.
 2. porosity_from_stress: decreasing in stress; equals surface porosity at 0.
 3. compute_column on a synthetic column: σ' strictly ↑, porosity strictly ↓.
 4. bulk density stays between water and grain density for every layer.
 5. observe_compaction returns a sane snapshot on a real Genesis world.
 6. Snapshot is read-only: geology layers + sim tick unchanged.
 7. Compaction invariant holds (σ' ↑ and φ ↓ with depth in every column).
 8. Shallow porosity > deep porosity (mechanical compaction with burial).
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
from engine.compaction_observer import (                                # noqa: E402
    CompactionConfig, LayerCompaction, CompactionSnapshot,
    CompactionHistory, CompactionState,
    porosity_from_stress, compute_column, column_compaction_monotonic,
    observe_compaction, install_compaction_observer,
    uninstall_compaction_observer, compaction_summary,
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
    print("P123 — Wave 54 diagenetic compaction & lithostatic pressure smoke")
    print("=" * 72)
    rows = []
    ok_all = True

    # 1. Public API.
    api = all(callable(f) or f is not None for f in (
        porosity_from_stress, compute_column, column_compaction_monotonic,
        observe_compaction, install_compaction_observer,
        uninstall_compaction_observer, compaction_summary,
        CompactionConfig, LayerCompaction, CompactionSnapshot))
    rows.append(_row("public API exposed", api))
    ok_all &= api

    # 2. porosity_from_stress monotone + surface anchor.
    cfg = CompactionConfig()
    p0 = porosity_from_stress(0.0, cfg)
    decr = (abs(p0 - cfg.surface_porosity) < 1e-12 and
            porosity_from_stress(5.0, cfg) < p0 and
            porosity_from_stress(50.0, cfg) < porosity_from_stress(5.0, cfg))
    rows.append(_row("porosity law: φ(0)=φ0 and decreasing in σ'", decr,
                     f"φ0={p0:.3f}"))
    ok_all &= decr

    # 3. Synthetic column: σ' strictly ↑, porosity strictly ↓.
    synth = _FakeColumn([
        _FakeLayer(0.0, 1.0, "shale", 1500.0),
        _FakeLayer(1.0, 5.0, "sandstone", 1800.0),
        _FakeLayer(5.0, 200.0, "limestone", 2300.0),
        _FakeLayer(200.0, 1000.0, "granite", 2700.0),
        _FakeLayer(1000.0, 3000.0, "gneiss", 2850.0),
    ])
    cols = compute_column(synth, cfg)
    eff = [c.effective_stress_mpa for c in cols]
    por = [c.porosity for c in cols]
    strict = (all(b > a for a, b in zip(eff, eff[1:])) and
              all(b < a for a, b in zip(por, por[1:])))
    rows.append(_row("synthetic column: σ' strictly ↑, φ strictly ↓", strict,
                     f"σ'={eff[0]:.3f}→{eff[-1]:.1f} MPa  φ={por[0]:.3f}→{por[-1]:.3f}"))
    ok_all &= strict

    # 4. Bulk density bracketed by water and grain density.
    bracket = all(cfg.water_density <= c.bulk_density_kg_m3 <= grain + 1e-6
                  for c, grain in zip(cols, (1500.0, 1800.0, 2300.0,
                                             2700.0, 2850.0)))
    rows.append(_row("bulk density ∈ [water, grain] per layer", bracket))
    ok_all &= bracket

    # 5. Real-world snapshot.
    sim = _booted_sim("p123_obs")
    gs = _populate_geology(sim)
    snap = observe_compaction(gs, cfg, tick=0)
    sane = (isinstance(snap, CompactionSnapshot) and
            snap.total_layers > 0 and snap.n_chunks > 0 and
            0.0 < snap.mean_porosity <= cfg.surface_porosity + 1e-9 and
            snap.max_effective_stress_mpa > 0.0)
    rows.append(_row("observe_compaction snapshot on Genesis world", sane,
                     f"layers={snap.total_layers} meanφ={snap.mean_porosity:.3f} "
                     f"maxσ'={snap.max_effective_stress_mpa:.1f}MPa "
                     f"lith={snap.lithified_layers}"))
    ok_all &= sane

    # 6. Read-only: layers + tick unchanged.
    coord0 = sorted(gs.chunks.keys())[0]
    before = [(L.depth_top_m, L.depth_bottom_m, L.density_kg_m3)
              for L in gs.chunks[coord0].layers]
    before_tick = int(getattr(sim, "tick", 0))
    _ = observe_compaction(gs, cfg, tick=0)
    after = [(L.depth_top_m, L.depth_bottom_m, L.density_kg_m3)
             for L in gs.chunks[coord0].layers]
    read_only = (before == after and
                 int(getattr(sim, "tick", 0)) == before_tick)
    rows.append(_row("observation is read-only (layers + tick)", read_only))
    ok_all &= read_only

    # 7. Compaction invariant on the real world.
    rows.append(_row("compaction invariant (σ' ↑, φ ↓ with depth)",
                     snap.compaction_monotonic_ok))
    ok_all &= snap.compaction_monotonic_ok

    # 8. Shallow porosity > deep porosity.
    burial = snap.shallow_porosity > snap.deep_porosity
    rows.append(_row("shallow φ > deep φ (compaction with burial)", burial,
                     f"shallow={snap.shallow_porosity:.3f} deep={snap.deep_porosity:.3f}"))
    ok_all &= burial

    # 9. install / uninstall round-trip.
    orig_step = sim.step
    st = install_compaction_observer(sim, cfg)
    installed = (getattr(sim, "_compaction_state", None) is st and
                 sim.step is not orig_step)
    uninstall_compaction_observer(sim)
    restored = (sim.step is orig_step and
                getattr(sim, "_compaction_state", None) is None)
    rows.append(_row("install / uninstall wrap restore",
                     installed and restored))
    ok_all &= (installed and restored)

    # 10. Cross-sim determinism.
    sim_b = _booted_sim("p123_obs")          # same seed
    gs_b = _populate_geology(sim_b)
    snap_b = observe_compaction(gs_b, cfg, tick=0)
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
