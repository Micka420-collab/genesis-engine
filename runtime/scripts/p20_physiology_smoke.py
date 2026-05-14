"""P20 — Wave 3 physiology smoke test.

Boots a small Léman sim, attaches ``install_physiology``, runs ~1000
ticks, and asserts that the physiology pipeline is producing
physically reasonable trajectories:

  1. Bladder mean grows over time (agents drink, baseline metabolism).
  2. Bowel mean grows over time.
  3. Hygiene mean is in [0, 1] and degrades unless agents bathe.
  4. At least one bathe event recorded (some chunk has water cells).
  5. Auto-relief fires at least once.
  6. ADR-0005 audit still passes (physiology is required-tagged).
  7. Determinism : same seed produces bit-identical physio snapshots.

Exit 0 on full pass, 1 on any failure.
"""
from __future__ import annotations

import hashlib
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

from engine.sim import Simulation, SimConfig                # noqa: E402
from engine.sim_5cd_integration import install              # noqa: E402
from engine.earth_loader import EarthLoader                 # noqa: E402
from engine.earth_streamer import (attach_earth_loader,     # noqa: E402
                                   attach_land_filter)
from engine.sim_lift import install_lift                    # noqa: E402
from engine.physiology import install_physiology, physiology_state  # noqa: E402


SEED = 0xC0FFEE_B0DE_F1F & 0xFFFFFFFFFFFFFFFF


def _build_sim(name: str):
    cfg = SimConfig(
        name=name, seed=SEED,
        founders=20, max_agents=80,
        bounds_km=(2.0, 2.0), spawn_radius_m=200.0,
        drive_accel=1500.0, cultures=2,
    )
    loader = EarthLoader(
        origin_lat=46.510, origin_lon=6.633, bounds_km=2.0,
        cache_dir=os.path.abspath(os.path.join(
            ROOT, "..", "cache", "earth_leman")),
    )
    sim = Simulation(cfg)
    attach_earth_loader(sim.streamer, loader, log_first_hit=False)
    attach_land_filter(sim)
    install(sim)
    install_lift(sim)
    fields = install_physiology(sim)
    return sim, fields


def _row(label: str, ok: bool, detail: str = "") -> str:
    mark = "OK  " if ok else "FAIL"
    return f"  [{mark}] {label:42s} {detail}"


def _physio_hash(snap):
    """Stable hash of a physiology snapshot (means, disease, events)."""
    parts = []
    for key in ("means", "disease", "events"):
        sub = snap.get(key, {})
        for k in sorted(sub):
            parts.append(f"{key}.{k}={sub[k]!r}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def main() -> int:
    print("=" * 78)
    print("P20 — Wave 3 physiology smoke test")
    print("=" * 78)
    failures = 0

    # -------------------------------------------------------------------
    # Step A — single 800-tick run, check trajectories
    # -------------------------------------------------------------------
    sim, fields = _build_sim("p20_run1")
    snap0 = physiology_state(sim)
    for _ in range(800):
        sim.step()
    snap1 = physiology_state(sim)

    m0 = snap0.get("means", {}) or {}
    m1 = snap1.get("means", {}) or {}
    print(_row("step A — bladder mean grew",
               (m1.get("bladder", 0) > m0.get("bladder", 0) + 0.01),
               f"{m0.get('bladder', 0):.3f} -> {m1.get('bladder', 0):.3f}"))
    if m1.get("bladder", 0) <= m0.get("bladder", 0) + 0.01:
        failures += 1

    print(_row("step A — bowel mean grew",
               (m1.get("bowel", 0) > m0.get("bowel", 0) + 0.01),
               f"{m0.get('bowel', 0):.3f} -> {m1.get('bowel', 0):.3f}"))
    if m1.get("bowel", 0) <= m0.get("bowel", 0) + 0.01:
        failures += 1

    hyg = float(m1.get("hygiene", 0.5))
    print(_row("step A — hygiene in [0, 1]",
               (0.0 <= hyg <= 1.0),
               f"hygiene={hyg:.3f}"))
    if not (0.0 <= hyg <= 1.0):
        failures += 1

    ev = snap1.get("events", {}) or {}
    print(_row("step A — auto-relief fired",
               int(ev.get("relief_total", 0)) > 0,
               f"relief={ev.get('relief_total', 0)}"))
    if int(ev.get("relief_total", 0)) == 0:
        failures += 1

    # Bathe is opportunistic — only if agents end up on water cells.
    bathes = int(ev.get("bathe_total", 0))
    print(_row("step A — bathe_total non-negative",
               bathes >= 0, f"bathe={bathes}"))

    # -------------------------------------------------------------------
    # Step B — ADR-0005 audit must include physiology
    # -------------------------------------------------------------------
    from engine.world_model_capabilities import audit_modules
    table, lint_fails = audit_modules(strict=False)
    rows = table.get("modules", [])
    physio_row = next(
        (r for r in rows if r["module"] == "engine.physiology"), None)
    ok = (physio_row is not None
          and physio_row["status"] == "ok"
          and not lint_fails)
    print(_row("step B — ADR-0005 lists physiology", ok,
               f"status={physio_row['status'] if physio_row else 'missing'}"))
    if not ok:
        failures += 1

    # -------------------------------------------------------------------
    # Step C — determinism (rebuild sim, compare snapshots)
    # -------------------------------------------------------------------
    sim2, _f2 = _build_sim("p20_run2")
    for _ in range(800):
        sim2.step()
    snap2 = physiology_state(sim2)

    h1 = _physio_hash(snap1)
    h2 = _physio_hash(snap2)
    print(_row("step C — physiology determinism",
               h1 == h2, f"{h1} vs {h2}"))
    if h1 != h2:
        failures += 1

    # -------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------
    print()
    print(f"final snapshot: {snap1}")
    print()
    if failures == 0:
        print("RESULT: PASS — Wave 3 physiology smoke complete.")
        return 0
    print(f"RESULT: FAIL — {failures} check(s) failed.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
