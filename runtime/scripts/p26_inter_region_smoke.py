"""P26 — Inter-region coherence smoke (Phase 15, P3).

Builds TWO regions a short walk apart, installs Wave 1-4 on both,
attaches them to a single :class:`engine.global_world.GlobalWorld`,
and checks:

  1. Shared atmosphere — both sims see the same ``co2_ppm`` at every
     tick after attach.
  2. Shared clock — ``GlobalClock`` advances monotonically.
  3. Migration — taking an agent from Léman and requesting migration
     to a (lat, lon) inside the other region succeeds: the agent
     disappears from Léman registry, reappears in the other region
     with preserved drives + traits + physiology.
  4. Survival — after 50 more ticks the migrated agent is either
     still alive or has died with a real death cause (not stuck in a
     limbo / NaN'd state).
  5. Determinism — rebuilding the same recipe twice with the same
     seed yields the same global-state hash.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tempfile
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

# Pin the library root to a temp directory so we never pollute the real one.
TMP_LIB = tempfile.mkdtemp(prefix="genesis_p26_")
os.environ["GENESIS_LIBRARY_ROOT"] = TMP_LIB


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:60s} {detail}"


def _build_pair(seed: int = 0xC0FFEE_15 & 0xFFFFFFFF_FFFFFFFF):
    """Build the two-region recipe used by every check (and for determinism)."""
    from engine.world_builder import WorldBuilder
    from engine.physiology import install_physiology
    from engine.photosynthesis import install_photosynthesis
    from engine.material_aging import install_material_aging
    from engine.global_world import GlobalWorld, attach_to_global

    # Region A — Léman (Lausanne north shore).
    region_a = (WorldBuilder("leman")
                .anchor(46.510, 6.633)
                .size_km(1.5)
                .founders(10)
                .max_agents(40)
                .cultures(2)
                .drive_accel(1500.0)
                .seed(seed)
                .build())
    install_physiology(region_a.sim)
    install_photosynthesis(region_a.sim)
    install_material_aging(region_a.sim)

    # Region B — 47.0 / 7.5 (≈ Solothurn / Jura range, ~80 km north-east).
    region_b = (WorldBuilder("jura")
                .anchor(47.0, 7.5)
                .size_km(1.5)
                .founders(10)
                .max_agents(40)
                .cultures(2)
                .drive_accel(1500.0)
                .seed(seed ^ 0xAB)
                .build())
    install_physiology(region_b.sim)
    install_photosynthesis(region_b.sim)
    install_material_aging(region_b.sim)

    gw = GlobalWorld(seed=seed)
    attach_to_global(region_a.sim, gw, name="leman",
                     anchor_lat=46.510, anchor_lon=6.633,
                     bounds_km=1.5)
    attach_to_global(region_b.sim, gw, name="jura",
                     anchor_lat=47.0, anchor_lon=7.5,
                     bounds_km=1.5)
    return region_a, region_b, gw


def _global_state_hash(gw) -> str:
    s = gw.state()
    blob = json.dumps(s, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _hash_only_run() -> int:
    """Compute the global state hash for one fresh recipe and print it.

    Used by the determinism check (subprocess harness) so the main run
    can compare its hash against a clean-process re-run.
    """
    region_a, region_b, gw = _build_pair()
    for _ in range(100):
        region_a.step()
        region_b.step()
    src = region_a.sim
    live_idx = -1
    for r in range(src.agents.n_active):
        if bool(src.agents.alive[r]):
            live_idx = r
            break
    if live_idx >= 0:
        gw.migrations.request_migration(
            from_sim=src, agent_row=live_idx,
            target_lat=47.0, target_lon=7.5)
    for _ in range(50):
        region_a.step()
        region_b.step()
    print(f"HASH_ONLY:{_global_state_hash(gw)}")
    return 0


def main() -> int:
    if os.environ.get("GENESIS_P26_HASH_ONLY") == "1":
        return _hash_only_run()
    print("=" * 78)
    print("Genesis Engine — P26 inter-region coherence smoke")
    print("=" * 78)

    rows = []

    # ---- recipe 1 ---------------------------------------------------------
    region_a, region_b, gw = _build_pair()
    ok = (len(gw.sims) == 2)
    rows.append(_row("two sims attached to GlobalWorld", ok,
                     f"n_sims={len(gw.sims)}"))
    # Shared atmosphere identity check.
    ok = (region_a.sim.atmosphere is region_b.sim.atmosphere
          is gw.atmosphere)
    rows.append(_row("region_a.atmosphere is region_b.atmosphere is gw.atmosphere",
                     ok))

    # Run 100 ticks.
    for _ in range(100):
        region_a.step()
        region_b.step()

    # Check shared atmosphere by reading both sims.
    co2_a = float(region_a.sim.atmosphere.co2_ppm)
    co2_b = float(region_b.sim.atmosphere.co2_ppm)
    ok = (abs(co2_a - co2_b) < 1e-9)
    rows.append(_row("shared co2_ppm across regions",
                     ok, f"A={co2_a:.4f} B={co2_b:.4f}"))

    # Clock should be at least 100.
    ok = (gw.clock.tick >= 100)
    rows.append(_row("global clock advanced ≥ 100 ticks",
                     ok, f"tick={gw.clock.tick}"))

    # ---- migration --------------------------------------------------------
    # Pick a live agent in region_a.
    src = region_a.sim
    n = src.agents.n_active
    live_idx = -1
    for r in range(n):
        if bool(src.agents.alive[r]):
            live_idx = r
            break
    ok = (live_idx >= 0)
    rows.append(_row("found a live agent in Léman", ok,
                     f"row={live_idx}"))

    # Snapshot pre-migration state for the verification step.
    pre_hunger = float(src.agents.hunger[live_idx]) if live_idx >= 0 else 0.0
    pre_curiosity = float(src.agents.curiosity[live_idx]) if live_idx >= 0 else 0.0
    pre_genome = None
    if (live_idx >= 0 and getattr(src.agents, "genome", None) is not None):
        try:
            import numpy as np
            pre_genome = np.asarray(src.agents.genome[live_idx]).copy()
        except Exception:
            pre_genome = None
    pre_physio = {}
    pf = getattr(src, "_physio_fields", None)
    if pf is not None and live_idx >= 0:
        for f in ("hygiene", "bladder", "melanin", "body_fat"):
            arr = getattr(pf, f, None)
            if arr is not None:
                pre_physio[f] = float(arr[live_idx])

    # Migrate to (47.0, 7.5) — that lat/lon is inside region_b by definition.
    result = gw.migrations.request_migration(
        from_sim=src, agent_row=live_idx,
        target_lat=47.0, target_lon=7.5)
    rows.append(_row("migration request succeeded",
                     bool(result.get("ok")),
                     f"reason={result.get('reason')!r}"))

    # Source row should now be alive=False (migrated out).
    rows.append(_row("source row marked alive=False after migration",
                     not bool(src.agents.alive[live_idx]),
                     f"alive[{live_idx}]={bool(src.agents.alive[live_idx])}"))

    # Destination should have a new alive row.
    dst_row = int(result.get("dst_row", -1))
    dst = region_b.sim
    ok = (dst_row >= 0 and dst_row < dst.agents.n_active
          and bool(dst.agents.alive[dst_row]))
    rows.append(_row("destination row alive after migration",
                     ok, f"dst_row={dst_row}"))

    # Drives + curiosity preserved.
    post_hunger = (float(dst.agents.hunger[dst_row])
                   if dst_row >= 0 else float("nan"))
    post_curiosity = (float(dst.agents.curiosity[dst_row])
                      if dst_row >= 0 else float("nan"))
    ok = abs(post_hunger - pre_hunger) < 1e-5
    rows.append(_row("hunger preserved across migration",
                     ok, f"pre={pre_hunger:.4f} post={post_hunger:.4f}"))
    ok = abs(post_curiosity - pre_curiosity) < 1e-5
    rows.append(_row("curiosity preserved across migration",
                     ok, f"pre={pre_curiosity:.4f} post={post_curiosity:.4f}"))

    # Genome preserved (if present).
    if pre_genome is not None:
        import numpy as np
        post_genome = np.asarray(dst.agents.genome[dst_row])
        ok = bool(np.array_equal(pre_genome, post_genome))
        rows.append(_row("genome preserved across migration",
                         ok, f"hash {hashlib.sha256(pre_genome.tobytes()).hexdigest()[:8]}"))

    # Physiology preserved (if installed).
    if pre_physio:
        post_pf = getattr(dst, "_physio_fields", None)
        if post_pf is None:
            rows.append(_row("physiology fields installed on dst sim",
                             False, "dst._physio_fields missing"))
        else:
            mismatches = []
            for f, v in pre_physio.items():
                arr = getattr(post_pf, f, None)
                if arr is None:
                    mismatches.append(f"{f}=missing")
                    continue
                pv = float(arr[dst_row])
                if abs(pv - v) > 1e-5:
                    mismatches.append(f"{f}({v:.4f}≠{pv:.4f})")
            ok = (not mismatches)
            rows.append(_row("physiology fields preserved across migration",
                             ok, ",".join(mismatches) or "all-match"))

    # Run 50 more ticks — migrated agent stays alive OR dies with cause.
    for _ in range(50):
        region_a.step()
        region_b.step()
    alive_post = (dst_row >= 0 and bool(dst.agents.alive[dst_row]))
    death_cause = int(dst.agents.death_cause[dst_row]) if dst_row >= 0 else -1
    ok = alive_post or (death_cause > 0)
    rows.append(_row("migrated agent stays alive or dies gracefully",
                     ok, f"alive={alive_post} death_cause={death_cause}"))

    # Migration registered in counter.
    ok = (len(gw.migrations.migrations) >= 1)
    rows.append(_row("migration logged in coordinator",
                     ok, f"count={len(gw.migrations.migrations)}"))

    # Endpoint shape sanity check via gw.state().
    state = gw.state()
    expected_keys = {"sims", "atmosphere", "clock",
                     "migration_count", "migration_fail_count"}
    ok = expected_keys.issubset(state.keys())
    rows.append(_row("/api/global_world_state payload shape",
                     ok, f"keys={sorted(state.keys())}"))

    h1 = _global_state_hash(gw)

    # ---- recipe 2 (determinism) ------------------------------------------
    # Determinism is checked across **fresh subprocesses** because several
    # Genesis modules (physiology dispatch, cognition apply_decision
    # patches) install process-global hooks on first install. Re-entering
    # _build_pair in the same process leaks state from run 1 into run 2 —
    # that's a known limitation of the existing patch system, not of the
    # GlobalWorld layer itself. Re-running in a subprocess is the
    # canonical determinism harness for Genesis (see p23).
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    helper = os.path.join(here, "p26_inter_region_smoke.py")
    env = dict(os.environ)
    env["GENESIS_P26_HASH_ONLY"] = "1"
    h2 = ""
    try:
        proc = subprocess.run(
            [sys.executable, helper],
            env=env, capture_output=True, text=True, timeout=600)
        out = proc.stdout
        for line in out.splitlines():
            if line.startswith("HASH_ONLY:"):
                h2 = line.split(":", 1)[1].strip()
                break
    except Exception as exc:
        h2 = f"<subprocess failed: {exc}>"
    ok = bool(h2) and (h1 == h2)
    rows.append(_row("determinism: same recipe → same global-state hash",
                     ok, f"{h1} == {h2}"))

    # ---- summary ---------------------------------------------------------
    print("\nResults:")
    for r in rows:
        print(r)
    n_fail = sum(1 for r in rows if "[FAIL]" in r)
    n_ok = sum(1 for r in rows if "[OK  ]" in r)
    print(f"\n→ {n_ok}/{n_ok + n_fail} PASS")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        traceback.print_exc()
        sys.exit(2)
