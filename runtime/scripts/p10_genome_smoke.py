"""Sprint A4 smoke — 256-gene genome + 8 life-stages.

Pass criteria:
* 12 founders, all with unique 256-d genomes (deterministic per (seed, idx)).
* >= 1 child born during the run with a genome that is a verifiable
  per-gene mix of its two parents (every gene equal to one of them, modulo
  a tiny number of post-crossover mutations).
* Living population covers >= 2 distinct life stages by the end of the run.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import numpy as np

from engine.earth_loader import EarthLoader
from engine.earth_streamer import attach_earth_loader, attach_land_filter
from engine.genome import (GENOME_SIZE, MUTATION_RATE, GENE_GROUP_APPEARANCE,
                           GENE_GROUP_COGNITION, GENE_GROUP_HEALTH,
                           GENE_GROUP_LONGEVITY, LifeStage, gene_to_trait,
                           current_life_stage, stage_distribution,
                           cognitive_efficiency, life_stage_name)
from engine.sim import Simulation, SimConfig
from engine.sim_5cd_integration import install


def _verify_crossover(child_g: np.ndarray, pa_g: np.ndarray,
                      pb_g: np.ndarray) -> dict:
    """Check that ``child_g`` is a per-gene mix of ``pa_g`` and ``pb_g``.

    Returns counts of genes matching parent A, parent B, and likely-mutated
    genes (neither parent within a small epsilon).
    """
    eps = 1e-5
    diff_a = np.abs(child_g - pa_g)
    diff_b = np.abs(child_g - pb_g)
    from_a = int(((diff_a < eps) & (diff_b >= eps)).sum())
    from_b = int(((diff_b < eps) & (diff_a >= eps)).sum())
    from_either = int(((diff_a < eps) & (diff_b < eps)).sum())
    mutated = int(((diff_a >= eps) & (diff_b >= eps)).sum())
    return {
        "from_a": from_a,
        "from_b": from_b,
        "from_either": from_either,
        "mutated_or_unknown": mutated,
    }


def main() -> int:
    out_path = os.path.join(ROOT, "journals", "sprint_a4_genome.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w").close()

    n_ticks_env = os.environ.get("A4_TICKS", "")
    try:
        N_TICKS = int(n_ticks_env) if n_ticks_env else 2000
    except ValueError:
        N_TICKS = 2000

    # Lausanne-Ouchy (same setup as P4).
    origin_lat = 46.510
    origin_lon = 6.633
    cache_dir = os.path.abspath(os.path.join(ROOT, "..", "cache",
                                             "earth_leman"))
    os.makedirs(cache_dir, exist_ok=True)
    loader = EarthLoader(origin_lat=origin_lat, origin_lon=origin_lon,
                         bounds_km=2.0, cache_dir=cache_dir)

    cfg = SimConfig(
        name="sprint_a4_genome",
        seed=0xA4_5EED_C0FFEE & 0xFFFFFFFF_FFFFFFFF,
        founders=12,
        max_agents=500,
        bounds_km=(2.0, 2.0),
        spawn_radius_m=150.0,
        cultures=2,
        drive_accel=1500.0,
    )

    t_setup = time.monotonic()
    sim = Simulation(cfg)
    sim.earth_loader = loader
    attach_earth_loader(sim.streamer, loader, strict=False, log_first_hit=False)
    attach_land_filter(sim)
    install(sim)
    setup_elapsed = time.monotonic() - t_setup

    agents = sim.agents

    # ---- Stage-rate compression --------------------------------------------
    # Founders have a default lifespan of ~80 years (~1.68M ticks at
    # drive_accel=1500). Over a 2000-tick smoke run, no founder transitions
    # past the infant stage. To exercise the 8-stage mechanism within the
    # budget, we (a) compress lifespans to ~N_TICKS so each stage spans
    # ~N_TICKS/8 ticks, and (b) stagger the founders' born_tick so the cohort
    # already spans multiple stages on tick 0.
    accel = max(1, int(cfg.drive_accel))
    target_lifespan_ticks = N_TICKS * accel  # so lifespan//accel ~= N_TICKS
    stage_ticks = max(1, N_TICKS // 8)
    n_founders = agents.n_active
    for r in range(n_founders):
        agents.lifespan_ticks[r] = int(target_lifespan_ticks)
        # Stagger: founder r is born at tick -(r * stage_ticks * 0.9) so by
        # tick 0 the cohort spans roughly stages 0..min(7, n_founders-1).
        stagger = int(-(r % 8) * stage_ticks * 0.9)
        agents.born_tick[r] = stagger

    # ---- Founder genome uniqueness -----------------------------------------
    n_founders = agents.n_active
    founder_g = agents.genome[:n_founders].copy()
    unique = {tuple(np.round(g, 6).tolist()) for g in founder_g}
    founder_unique = len(unique) == n_founders

    # Capture child genomes by hooking spawn_offspring.
    birth_records = []  # list of (child_row, pa, pb, child_genome, pa_genome, pb_genome)
    original_resolve = sim._resolve_matings

    def capture_resolve(intents, raw_events):
        births = original_resolve(intents, raw_events)
        for triple in births or []:
            try:
                child, pa, pb = int(triple[0]), int(triple[1]), int(triple[2])
            except Exception:
                continue
            if child < 0:
                continue
            birth_records.append({
                "tick": int(sim.tick),
                "child": child,
                "pa": pa,
                "pb": pb,
                "child_genome": agents.genome[child].copy(),
                "pa_genome": agents.genome[pa].copy(),
                "pb_genome": agents.genome[pb].copy(),
            })
        return births

    sim._resolve_matings = capture_resolve

    # ---- Run ---------------------------------------------------------------
    errors = []
    t0 = time.monotonic()
    for t in range(N_TICKS):
        try:
            sim.step()
        except Exception as exc:
            errors.append({
                "tick": t, "exception": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc().splitlines()[-6:],
            })
            break
    elapsed = time.monotonic() - t0

    # ---- Stats -------------------------------------------------------------
    n_now = agents.n_active
    alive_mask = agents.alive[:n_now]
    n_alive = int(alive_mask.sum())

    # Genome stats.
    if n_now > 0:
        g = agents.genome[:n_now]
        gmean = float(g.mean())
        gstd = float(g.std())
    else:
        gmean = 0.0
        gstd = 0.0

    # Group-level means (so we can see per-group spread).
    group_stats = {}
    if n_alive > 0:
        live_g = agents.genome[:n_now][alive_mask]
        for name, sl in (("appearance", GENE_GROUP_APPEARANCE),
                         ("cognition", GENE_GROUP_COGNITION),
                         ("health", GENE_GROUP_HEALTH),
                         ("longevity", GENE_GROUP_LONGEVITY)):
            sub = live_g[:, sl]
            group_stats[name] = {
                "mean": round(float(sub.mean()), 4),
                "std": round(float(sub.std()), 4),
            }

    # Life stage distribution among alive agents.
    life_dist = stage_distribution(agents, sim)
    distinct_stages = sum(1 for v in life_dist.values() if v > 0)

    # Cognitive efficiency distribution.
    cog_eff_samples = []
    if n_alive > 0:
        for r in np.flatnonzero(alive_mask):
            stage = current_life_stage(agents, int(r), sim)
            cog_eff_samples.append(cognitive_efficiency(stage))
    cog_eff_summary = {
        "mean": round(float(np.mean(cog_eff_samples)), 4) if cog_eff_samples else 0.0,
        "min": round(float(np.min(cog_eff_samples)), 4) if cog_eff_samples else 0.0,
        "max": round(float(np.max(cog_eff_samples)), 4) if cog_eff_samples else 0.0,
    }

    # Verify the first (up to 5) child genomes.
    crossover_checks = []
    for rec in birth_records[:5]:
        chk = _verify_crossover(rec["child_genome"], rec["pa_genome"],
                                rec["pb_genome"])
        chk["tick"] = rec["tick"]
        chk["child"] = rec["child"]
        chk["pa"] = rec["pa"]
        chk["pb"] = rec["pb"]
        crossover_checks.append(chk)

    # A "verifiable crossover": at least one gene matches each parent
    # exclusively, and the total of (from_a + from_b + from_either) is
    # close to GENOME_SIZE (allowing for the rare mutation).
    verified_crossovers = 0
    for chk in crossover_checks:
        if (chk["from_a"] > 0 and chk["from_b"] > 0 and
                (chk["from_a"] + chk["from_b"] + chk["from_either"])
                >= GENOME_SIZE - 5):
            verified_crossovers += 1

    summary = {
        "_summary": True,
        "config": {
            "name": cfg.name, "seed": cfg.seed, "founders": cfg.founders,
            "ticks_target": N_TICKS, "drive_accel": cfg.drive_accel,
        },
        "setup_elapsed_s": round(setup_elapsed, 3),
        "run_elapsed_s": round(elapsed, 3),
        "ticks_completed": int(sim.tick),
        "agents_total_spawned": int(n_now),
        "agents_alive": n_alive,
        "founder_genome": {
            "count": n_founders,
            "unique": founder_unique,
            "genome_size": GENOME_SIZE,
        },
        "genome_stats": {
            "mean": round(gmean, 4),
            "std": round(gstd, 4),
            "groups": group_stats,
        },
        "births": {
            "total": len(birth_records),
            "verified_crossovers": verified_crossovers,
            "samples": crossover_checks,
        },
        "life_stages": {
            "distribution": life_dist,
            "distinct_alive": distinct_stages,
            "cognitive_efficiency": cog_eff_summary,
        },
        "mutation_rate": MUTATION_RATE,
        "errors": errors,
    }

    with open(out_path, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(summary, separators=(",", ":")) + "\n")

    print(json.dumps(summary, indent=2))

    if errors:
        print("\n[X] A4 GENOME SMOKE FAILED — exception thrown.")
        return 2
    if not founder_unique:
        print("\n[X] A4 GENOME SMOKE FAILED — founder genomes not unique.")
        return 3
    if len(birth_records) < 1:
        print("\n[!] A4 GENOME SMOKE WEAK — no births recorded in run.")
        return 4
    if verified_crossovers < 1:
        print("\n[X] A4 GENOME SMOKE FAILED — no verifiable crossover.")
        return 5
    if distinct_stages < 2:
        print(f"\n[!] A4 GENOME SMOKE WEAK — only {distinct_stages} life stage(s) observed.")
        return 6

    print("\n[OK] A4 GENOME SMOKE PASSED")
    print(f"   founders unique: {founder_unique} ({n_founders})")
    print(f"   births: {len(birth_records)}  verified crossovers: {verified_crossovers}")
    print(f"   distinct life stages alive: {distinct_stages}")
    print(f"   genome mean/std: {gmean:.4f} / {gstd:.4f}")
    print(f"   journal: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
