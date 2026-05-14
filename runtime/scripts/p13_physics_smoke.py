"""P13 — smoke test for ``engine.physics`` (Sprint B1, Pillar 1, Wave 1).

Verifies that the physics knowledge base produces correct numerical values
for well-known textbook situations:

1. Kinetic energy of a 1 kg projectile at 10 m/s = 50 J.
2. Potential energy of a 1 kg mass at 1 m on Earth ~= 9.81 J.
3. Weight of a 70 kg human on Earth ~= 686.7 N.
4. Friction (kinetic) on a 100 N wood-on-wood normal load = 30 N.
5. Stress / strain self-consistency on a steel bar.
6. Stefan-Boltzmann radiation: T=300 K, emissivity=1, area=1 m^2,
   cold-side at 0 K ~= 459 W.
7. Fourier conduction: 1 m^2 of iron, 1 m thick, dT=10 K = 800 W.
8. Gibbs free energy for the combustion of methane,
   CH4 + 2 O2 -> CO2 + 2 H2O(l), dG ~ -818 kJ/mol at 298 K
   (favorable, must be negative).
9. Arrhenius: rate goes up with T (k(310 K) > k(298 K)).
10. Terminal velocity of a 75 kg human skydiver ~= 50-60 m/s in air.
11. Kepler: Earth's orbital period around the Sun ~= 1 year.

Pass if every assertion holds within the documented tolerance.
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine import physics as P


def _close(actual: float, expected: float, rel: float = 1e-3,
           abs_tol: float = 1e-9) -> bool:
    return abs(actual - expected) <= max(abs_tol, rel * abs(expected))


def main() -> int:
    checks: list[dict] = []
    failed = 0

    def check(label: str, actual, expected, *, rel: float = 1e-3,
              op: str = "approx") -> None:
        nonlocal failed
        ok: bool
        if op == "approx":
            ok = _close(float(actual), float(expected), rel=rel)
        elif op == "lt":
            ok = float(actual) < float(expected)
        elif op == "gt":
            ok = float(actual) > float(expected)
        elif op == "between":
            lo, hi = expected
            ok = lo <= float(actual) <= hi
        elif op == "true":
            ok = bool(actual) is True
        else:
            raise ValueError(f"unknown op {op}")
        checks.append({
            "label": label,
            "actual": float(actual) if op != "true" else bool(actual),
            "expected": expected,
            "op": op,
            "ok": ok,
        })
        if not ok:
            failed += 1

    try:
        # 1. Kinetic energy.
        ke = P.kinetic_energy(1.0, 10.0)
        check("kinetic_energy(1 kg, 10 m/s) = 50 J", ke, 50.0)

        # 2. Potential energy.
        pe = P.potential_energy(1.0, 1.0)
        check("potential_energy(1 kg, 1 m) ~ 9.81 J", pe, P.G_EARTH)

        # 3. Weight.
        w = P.weight(70.0)
        check("weight(70 kg) ~ 686.7 N", w, 70.0 * P.G_EARTH)

        # 4. Kinetic friction wood-on-wood.
        f = P.friction_force(100.0, P.MU_KINETIC_WOOD_WOOD)
        check("friction_force(100 N, wood/wood kinetic) = 30 N", f, 30.0)

        # 5. Stress/strain on a steel bar (1 cm^2 cross-section, 1 m long,
        # 1000 N load, 0.5 mm elongation).
        sigma = P.stress(1000.0, 1e-4)
        eps = P.strain(5e-4, 1.0)
        check("stress(1000 N, 1 cm^2) = 1e7 Pa", sigma, 1e7)
        check("strain(0.5 mm / 1 m) = 5e-4", eps, 5e-4)

        # 6. Stefan-Boltzmann blackbody at 300 K vs 0 K.
        Q_rad = P.heat_transfer_radiation(1.0, 1.0, 300.0, 0.0)
        # sigma * 300^4 = 5.670374e-8 * 8.1e9 ~= 459.27 W
        check("radiation(eps=1, A=1, 300 K vs 0 K) ~ 459 W",
              Q_rad, 459.0, rel=0.01)

        # 7. Fourier conduction through iron.
        Q_cond = P.heat_transfer_conduction(
            P.thermal_conductivity_table["iron"], 1.0, 10.0, 1.0)
        check("conduction iron, A=1, L=1, dT=10 = 800 W", Q_cond, 800.0)

        # 8. Methane combustion: CH4 + 2 O2 -> CO2 + 2 H2O (liquid).
        # Standard enthalpies of formation (CRC, kJ/mol):
        #   CH4(g) = -74.6,  O2 = 0, CO2(g) = -393.5, H2O(l) = -285.8
        # dH_rxn = (-393.5 + 2*(-285.8)) - (-74.6) = -890.5 kJ/mol
        # Standard entropies (J/(mol K)):
        #   CH4 186.3, O2 205.2, CO2 213.8, H2O(l) 69.9
        # dS = (213.8 + 2*69.9) - (186.3 + 2*205.2) = -243.1 J/(mol K)
        dH = -890.5e3  # J/mol
        dS = -243.1    # J/(mol K)
        dG = P.gibbs_free_energy(dH, P.T_STANDARD, dS)
        # Expected dG ~ -890.5e3 - 298.15 * (-243.1) ~ -818,030 J/mol
        check("methane combustion dG ~ -818 kJ/mol", dG, -818e3, rel=0.02)
        check("methane combustion is spontaneous (dG < 0)",
              P.is_thermodynamically_favorable(dG), True, op="true")

        # 9. Arrhenius — rate increases with temperature.
        k298 = P.arrhenius_rate(1e10, 50e3, 298.15)
        k310 = P.arrhenius_rate(1e10, 50e3, 310.0)
        check("arrhenius k(310 K) > k(298 K)", k310, k298, op="gt")

        # 10. Terminal velocity of a skydiver: m=75 kg, Cd=1.0, A=0.7 m^2.
        v_t = P.compute_terminal_velocity(75.0, 1.0, 0.7)
        check("skydiver terminal velocity in [40, 70] m/s",
              v_t, (40.0, 70.0), op="between")

        # 11. Kepler — Earth around the Sun. a = 1 AU = 1.496e11 m,
        # M_sun = 1.989e30 kg, expected T = 1 year = 3.156e7 s.
        T_earth = P.compute_orbital_period(1.496e11, 1.989e30)
        check("Earth orbital period ~ 1 year (3.156e7 s)",
              T_earth, 3.156e7, rel=0.01)

        # 12. Sanity: acceleration of 1 kg under 9.81 N = 9.81 m/s^2.
        a = P.compute_acceleration(9.81, 1.0)
        check("compute_acceleration(9.81 N, 1 kg) = 9.81 m/s^2", a, 9.81)

    except Exception as exc:
        print("\nFATAL during smoke run:", type(exc).__name__, exc)
        traceback.print_exc()
        return 2

    summary = {
        "_summary": True,
        "module": "engine.physics",
        "checks_total": len(checks),
        "checks_failed": failed,
        "checks": checks,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if failed:
        print(f"\nP13 PHYSICS SMOKE FAILED — {failed}/{len(checks)} checks failed")
        return 3

    print(f"\nP13 PHYSICS SMOKE PASSED — {len(checks)}/{len(checks)} checks ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
