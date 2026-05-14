"""Analyse Genesis Engine journals — lineage, invention, group dynamics.

Reads a JSONL journal produced by ``p4_leman.py`` (or similar) and prints
a structured analysis: lineage tree, prolific founders, invention timeline,
group formation/dissolution dynamics.

Usage::

    python scripts/analyse_lineage.py journals/phase5a_leman.jsonl
"""
from __future__ import annotations

import io
import json
import os
import sys
from collections import Counter, defaultdict


if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main(path: str) -> int:
    if not os.path.isfile(path):
        print(f"Journal not found: {path}")
        return 2

    events_by_kind: Counter = Counter()
    births = []            # list of (tick, child_uuid, parent_a_uuid, parent_b_uuid)
    deaths = []            # list of (tick, uuid, cause)
    inventions = []        # list of (tick, inventor_uuid, name, function, material)
    matings = []
    artifact_transmits = []
    tech_transmits = []
    summary = None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                j = json.loads(line)
            except Exception:
                continue
            if "_summary" in j:
                summary = j
                continue
            k = j.get("kind", "?")
            events_by_kind[k] += 1
            t = int(j.get("tick", 0))
            parts = j.get("participants") or []
            # Annalist Event objects expose data under "metadata"; the older
            # "attrs" key is read as a fallback for back-compat.
            attrs = j.get("metadata") or j.get("attrs") or {}
            if k == "birth":
                if len(parts) >= 1:
                    births.append((
                        t, parts[0],
                        parts[1] if len(parts) >= 2 else None,
                        parts[2] if len(parts) >= 3 else None,
                    ))
            elif k == "death":
                if parts:
                    deaths.append((
                        t, parts[0],
                        attrs.get("cause", "?"),
                        int(attrs.get("age_ticks", 0)),
                        int(attrs.get("generation", 0)),
                        int(attrs.get("offspring_count", 0)),
                    ))
            elif k == "invent":
                inventions.append((t, attrs.get("inventor", "?"),
                                   attrs.get("name", "?"),
                                   attrs.get("function", "?"),
                                   attrs.get("primary_material", "?")))
            elif k == "mating":
                matings.append((t, parts))
            elif k == "artifact_transmitted":
                artifact_transmits.append(t)
            elif k == "tech_transmitted":
                tech_transmits.append(t)

    print("=" * 60)
    print(f"Journal: {path}")
    if summary:
        print(f"Ticks completed: {summary.get('ticks_completed')}")
        print(f"Setup elapsed: {summary.get('setup_elapsed_s')}s  "
              f"Run elapsed: {summary.get('run_elapsed_s')}s")
        print(f"Origin (lat, lon): "
              f"{summary.get('earth_probe', {}).get('origin_lat')}, "
              f"{summary.get('earth_probe', {}).get('origin_lon')}")
    print("=" * 60)

    print("\n— Event totals —")
    for k, c in events_by_kind.most_common():
        print(f"  {k:25s}  {c}")

    if births:
        print(f"\n— Births: {len(births)} —")
        # Most prolific (uuid → child count). Parents may appear multiple times.
        parent_count: Counter = Counter()
        for _, _, pa, pb in births:
            if pa: parent_count[pa] += 1
            if pb: parent_count[pb] += 1
        print("  Top parents (most offspring):")
        for uuid, count in parent_count.most_common(10):
            print(f"    {uuid}  {count}")
        # Birth-tick histogram (buckets of 1000)
        if summary:
            bucket = max(1, int(summary.get("ticks_completed", 1000)) // 10)
        else:
            bucket = 1000
        bh: Counter = Counter()
        for t, *_ in births:
            bh[(t // bucket) * bucket] += 1
        print(f"  Births by tick (bucket={bucket}):")
        for k in sorted(bh.keys()):
            print(f"    tick {k:6d}+   {bh[k]:4d}  {'#' * min(40, bh[k])}")

    if deaths:
        print(f"\n— Deaths: {len(deaths)} —")
        cause_count: Counter = Counter()
        age_by_cause: dict = {}
        ages = []
        gens = []
        offspring_dist = []
        for _, _, cause, age, gen, offspring in deaths:
            cause_count[cause] += 1
            age_by_cause.setdefault(cause, []).append(age)
            ages.append(age)
            gens.append(gen)
            offspring_dist.append(offspring)
        print("  Causes (count + mean age at death):")
        for cause, count in cause_count.most_common():
            mean_age = sum(age_by_cause[cause]) / len(age_by_cause[cause])
            print(f"    {cause:25s}  {count:4d}  mean age {mean_age:6.0f} ticks")
        if ages:
            print(f"  Lifespan stats (ticks):")
            print(f"    mean  {sum(ages)/len(ages):6.0f}   median  {sorted(ages)[len(ages)//2]:6d}   "
                  f"min  {min(ages):4d}   max  {max(ages):4d}")
        if gens:
            gen_count: Counter = Counter(gens)
            print(f"  Generations represented in deaths:")
            for g, c in sorted(gen_count.items()):
                print(f"    gen {g:2d}  {c}")
        if offspring_dist:
            childless = sum(1 for o in offspring_dist if o == 0)
            with_kids = len(offspring_dist) - childless
            mean_kids = sum(offspring_dist) / len(offspring_dist)
            print(f"  Reproductive success at death: "
                  f"{with_kids}/{len(offspring_dist)} had ≥1 child   "
                  f"mean offspring = {mean_kids:.2f}")

    if inventions:
        print(f"\n— Inventions: {len(inventions)} —")
        for t, inv, name, fn, mat in inventions[:20]:
            print(f"  tick {t:6d}  by {inv}  → {name} (function={fn} mat={mat})")
        if len(inventions) > 20:
            print(f"  ... and {len(inventions) - 20} more")

    if artifact_transmits:
        print(f"\n— Artifact transmissions: {len(artifact_transmits)} —")
        print(f"  First at tick {min(artifact_transmits)}")
        print(f"  Last at tick {max(artifact_transmits)}")
    if tech_transmits:
        print(f"\n— Tech transmissions: {len(tech_transmits)} —")
        print(f"  First at tick {min(tech_transmits)}")
        print(f"  Last at tick {max(tech_transmits)}")

    if summary:
        print("\n— Final state —")
        print(f"  Agents alive: {summary.get('agents_alive')} / "
              f"{summary.get('agents_total_spawned')}")
        print(f"  Construction: {summary.get('construction')}")
        print(f"  Atmosphere: {summary.get('atmosphere')}")
        print(f"  L1 hits/misses: {summary.get('earth_streamer')}")
        lift = summary.get("lift_state", {})
        if lift:
            print(f"  L2 chunks: {lift.get('chunks')}  "
                  f"max ravine: {lift.get('max_ravine_depth')}")
            for state, frac in (lift.get("veg_distribution") or {}).items():
                print(f"    {state:18s}  {frac * 100:5.2f}%")
    return 0


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) >= 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "journals", "phase5a_leman.jsonl")
    raise SystemExit(main(os.path.abspath(p)))
