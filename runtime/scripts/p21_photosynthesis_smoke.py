"""P21 — Wave 4 photosynthesis smoke test (Farquhar-von Caemmerer-Berry).

Asserts that the leaf-level model produces realistic CO2 assimilation
rates at standard noon conditions, that CO2 elevation increases C3
output (the "CO2 fertilization effect" — real biology), that C4 outperforms
C3 at high temperature, and that chunk-level GPP is non-zero on a real
Léman sim once install_photosynthesis is wired in.

Exit 0 on full pass, 1 otherwise.
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

from engine.photosynthesis import (  # noqa: E402
    assimilation_c3, assimilation_c4, assimilation_cam,
    install_photosynthesis, photosynthesis_state,
)
from engine.sim import Simulation, SimConfig                # noqa: E402
from engine.sim_5cd_integration import install              # noqa: E402
from engine.earth_loader import EarthLoader                 # noqa: E402
from engine.earth_streamer import (attach_earth_loader,     # noqa: E402
                                   attach_land_filter)
from engine.sim_lift import install_lift                    # noqa: E402


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:50s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P21 — Wave 4 photosynthesis smoke (Farquhar / Collatz)")
    print("=" * 78)
    failures = 0

    # ------------------------------------------------------------------
    # Step 1 — C3 at noon, 25 °C, 280 ppm baseline.
    # ------------------------------------------------------------------
    par_noon = 1500.0
    a_c3_280 = assimilation_c3(Ca_ppm=280.0, par_umol_m2_s=par_noon,
                               T_C=25.0, water_factor=1.0)
    # Pre-industrial 280 ppm. Modern (400 ppm) gives ~25; 280 ppm gives ~8.
    # Literature instantaneous-A range at 280 ppm noon: 5-15.
    ok = 5.0 <= a_c3_280 <= 18.0
    print(_row("step 1 — C3 noon 25°C 280 ppm in [5, 18] μmol/m²/s",
               ok, f"A = {a_c3_280:.2f}"))
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Step 2 — CO2 fertilization : doubling CO2 raises C3 output.
    # Instantaneous Farquhar predicts ~1.8-2.1x at doubling without
    # acclimation; long-term FACE experiments show ~1.15-1.30x. We test
    # the instantaneous regime.
    # ------------------------------------------------------------------
    a_c3_560 = assimilation_c3(Ca_ppm=560.0, par_umol_m2_s=par_noon,
                               T_C=25.0, water_factor=1.0)
    ratio = a_c3_560 / max(a_c3_280, 1e-6)
    ok = 1.40 <= ratio <= 2.30
    print(_row("step 2 — CO2 fertilization 280→560 ppm ratio ∈[1.4,2.3]",
               ok, f"A(560)={a_c3_560:.2f} ratio={ratio:.3f}"))
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Step 3 — C4 beats C3 at high T (35 °C) and high light.
    # ------------------------------------------------------------------
    a_c3_hot = assimilation_c3(Ca_ppm=280.0, par_umol_m2_s=par_noon,
                               T_C=35.0, water_factor=1.0)
    a_c4_hot = assimilation_c4(Ca_ppm=280.0, par_umol_m2_s=par_noon,
                               T_C=35.0, water_factor=1.0)
    ok = a_c4_hot > a_c3_hot
    print(_row("step 3 — C4 > C3 at 35°C high light",
               ok, f"C3={a_c3_hot:.2f} C4={a_c4_hot:.2f}"))
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Step 4 — Night = no positive A (only respiration losses).
    # ------------------------------------------------------------------
    a_night = assimilation_c3(Ca_ppm=280.0, par_umol_m2_s=0.0,
                              T_C=15.0, water_factor=1.0)
    ok = a_night < 0.0
    print(_row("step 4 — C3 at night is negative (respiration only)",
               ok, f"A = {a_night:.2f}"))
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Step 5 — Drought : water_factor = 0 should kill GPP.
    # ------------------------------------------------------------------
    a_dry = assimilation_c3(Ca_ppm=280.0, par_umol_m2_s=par_noon,
                            T_C=25.0, water_factor=0.0)
    ok = a_dry <= 0.0
    print(_row("step 5 — drought drops C3 to respiration-only",
               ok, f"A = {a_dry:.2f}"))
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Step 6 — Install on a real Léman sim and verify global GPP > 0.
    # ------------------------------------------------------------------
    cfg = SimConfig(
        name="p21_photo", seed=0xC0FFEE_42 & 0xFFFFFFFFFFFFFFFF,
        founders=10, max_agents=20,
        bounds_km=(1.5, 1.5), spawn_radius_m=150.0,
        drive_accel=1500.0, cultures=1,
    )
    loader = EarthLoader(
        origin_lat=46.510, origin_lon=6.633, bounds_km=1.5,
        cache_dir=os.path.abspath(os.path.join(
            ROOT, "..", "cache", "earth_leman")),
    )
    sim = Simulation(cfg)
    attach_earth_loader(sim.streamer, loader, log_first_hit=False)
    attach_land_filter(sim)
    install(sim)
    install_lift(sim)
    state = install_photosynthesis(sim)
    for _ in range(150):
        sim.step()
    snap = photosynthesis_state(sim)
    global_gpp = float(snap.get("global_gpp_kcal_per_tick", 0.0))
    chunks = int(snap.get("chunks_tracked", 0))
    ok = global_gpp > 0.0 and chunks > 0
    print(_row("step 6 — sim integration produces positive GPP",
               ok,
               f"chunks={chunks} global={global_gpp:.4f} kcal/tick "
               f"Ca={snap.get('Ca_ppm')} PAR={snap.get('PAR_umol_m2_s')}"))
    if not ok:
        failures += 1

    # ------------------------------------------------------------------
    # Step 7 — ADR-0005 audit must keep passing.
    # ------------------------------------------------------------------
    from engine.world_model_capabilities import audit_modules
    table, lint_fails = audit_modules(strict=False)
    ok = not lint_fails
    print(_row("step 7 — ADR-0005 audit clean", ok,
               f"required-tagged={table['summary']['tagged']}"))
    if not ok:
        failures += 1

    print()
    if failures == 0:
        print("RESULT: PASS — Wave 4 photosynthesis smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) did not pass.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
