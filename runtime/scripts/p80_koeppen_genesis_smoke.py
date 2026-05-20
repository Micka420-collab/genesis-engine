"""P80 — Köppen on Genesis bootstrap world + FAIR manifest export."""
from __future__ import annotations

import io
import json
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(ROOT, ".."))
sys.path.insert(0, ROOT)

from engine.sim import Simulation, SimConfig  # noqa: E402
from engine.world_genesis import GenesisParams  # noqa: E402
from engine.genesis_bootstrap import bootstrap_genesis_sim  # noqa: E402
from engine.koeppen_grid import (  # noqa: E402
    export_fair_koeppen_manifest, fair_koeppen_manifest, koeppen_from_genesis_bootstrap,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P80 — Köppen Genesis bootstrap + FAIR manifest")
    print("=" * 78)
    failures = 0
    seed = 0xC055E080
    sim = Simulation(SimConfig(name="p80_koeppen", seed=seed, founders=4,
                                max_agents=20, bounds_km=(0.3, 0.3)))
    gp = GenesisParams(seed=seed, resolution=48, n_plates=6)
    state = bootstrap_genesis_sim(sim, seed=seed, genesis_params=gp)
    world = state.world
    fair = fair_koeppen_manifest(world, seed=seed)
    ok = "checksum_sha256" in fair and fair["seed"] == seed
    print(_row("FAIR manifest checksums + seed", ok, list(fair["checksum_sha256"])[:2]))
    if not ok:
        failures += 1
    ok = fair["koeppen_land_cells"] > 50 and fair["kappa_biome_coherence"] > 0.1
    print(_row("land cells + kappa", ok,
               f"land={fair['koeppen_land_cells']} kappa={fair['kappa_biome_coherence']}"))
    if not ok:
        failures += 1
    via_sim = koeppen_from_genesis_bootstrap(sim)
    ok = via_sim is not None and via_sim["seed"] == seed
    print(_row("koeppen_from_genesis_bootstrap", ok))
    if not ok:
        failures += 1
    out_dir = os.path.join(REPO, "runtime", "artifacts")
    out_path = os.path.join(out_dir, "koeppen_genesis_fair_example.json")
    export_fair_koeppen_manifest(world, out_path, seed=seed)
    ok = os.path.isfile(out_path) and os.path.getsize(out_path) > 100
    print(_row("export example artifact", ok, out_path))
    if not ok:
        failures += 1
    compliance = os.path.join(REPO, "docs", "compliance", "koeppen_genesis_fair_example.json")
    os.makedirs(os.path.dirname(compliance), exist_ok=True)
    with open(out_path, encoding="utf-8") as f:
        compliance_data = json.load(f)
    with open(compliance, "w", encoding="utf-8") as f:
        json.dump(compliance_data, f, indent=2)
    print(_row("compliance copy", os.path.isfile(compliance), compliance))
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
