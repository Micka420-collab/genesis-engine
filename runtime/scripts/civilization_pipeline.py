#!/usr/bin/env python
"""Deterministic civilization emergence pipeline (seed-driven).

Chains Genesis bootstrap → multi-rate coupler → agent ticks → observers.
All macro/climate exports read the bootstrapped sim world — no silent
synthetic grids unless ``--synthetic-only`` (CI isolation only).

Usage::

    PYTHONPATH=runtime python runtime/scripts/civilization_pipeline.py \\
        --seed 0xC1A71CE0 --ticks 200 --founders 12

Writes ``runtime/artifacts/civilization_run_manifest.json`` on success.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(ROOT, ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine.sim import Simulation, SimConfig  # noqa: E402
from engine.world_genesis import GenesisParams, world_signature  # noqa: E402
from engine.genesis_bootstrap import bootstrap_state  # noqa: E402
from engine.multi_rate_coupler import install_multi_rate_coupler, coupler_summary  # noqa: E402
from engine.physiology import install_physiology  # noqa: E402
from engine.epidemic_observer import (  # noqa: E402
    EpidemicConfig, install_epidemic_observer, epidemic_export_for_artifacts,
)
from engine.agent_observation import (  # noqa: E402
    export_observable_snapshot, observable_summary, genesis_observable_meta,
)
from engine.koeppen_grid import export_fair_koeppen_from_sim  # noqa: E402
from engine.chunk_hydrology import chunk_hydrology_state, genesis_anchor_from_sim  # noqa: E402
from engine.rust_bridge import bridge_status  # noqa: E402
from engine.rust_worldgraph_tick import rust_worldgraph_snapshot  # noqa: E402


def _parse_seed(raw: str) -> int:
    raw = raw.strip().lower()
    return int(raw, 16) if raw.startswith("0x") else int(raw)


def run_civilization_pipeline(
    *,
    seed: int,
    ticks: int,
    founders: int,
    max_agents: int,
    resolution: int,
    artifacts_dir: Path,
    synthetic_only: bool = False,
    renders: bool = False,
    journal: Optional[str] = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Execute the pipeline and return the run manifest dict."""
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    if journal is None:
        journal = str(artifacts_dir / "civilization_run.jsonl")
    open(journal, "w").close()

    cfg = SimConfig(
        name="civilization_pipeline",
        seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=founders,
        max_agents=max_agents,
        bounds_km=(0.4, 0.4),
        spawn_radius_m=60.0,
        drive_accel=1500.0,
        cultures=max(1, founders // 4),
    )
    sim = Simulation(cfg, journal_path=journal)

    gp = GenesisParams(
        seed=seed & 0xFFFFFFFFFFFFFFFF,
        resolution=resolution,
        n_plates=8,
        erosion_iters=12,
        rain_iters=3,
    )

    stack_status: Dict[str, Any] = {}
    if synthetic_only:
        from engine.world_genesis import generate_world, make_anchor
        world = generate_world(gp)
        anchor = make_anchor(world)
        sim.streamer.set_genesis(anchor)
        sim.streamer.clear_cache()
        boot = None
    else:
        from engine.full_stack import wire_full_stack

        stack_status = wire_full_stack(
            sim,
            genesis=True,
            rust_worldgraph=True,
            mp_api=bool(cfg.knowledge_layers),
            five_cd=True,
            genesis_resolution=resolution,
        )
        boot = bootstrap_state(sim)
        world = boot.world if boot is not None else None

    install_multi_rate_coupler(sim, master_dt=int(sim.cfg.drive_accel))
    install_physiology(sim)
    install_epidemic_observer(
        sim, EpidemicConfig(snapshot_every=max(1, ticks // 20)))

    sim.bootstrap()

    t0 = time.monotonic()
    try:
        for i in range(ticks):
            stats = sim.step()
            if verbose and ticks >= 10 and (i + 1) % max(1, ticks // 5) == 0:
                print(f"  tick {i + 1}/{ticks} alive={stats.alive} "
                      f"births={stats.cum_births} deaths={stats.cum_deaths}")
    finally:
        sim.annalist.close()

    elapsed = time.monotonic() - t0
    n_alive = int(sim.stats.alive)

    observable_path = artifacts_dir / "observable.json"
    snap = export_observable_snapshot(sim, str(observable_path))
    obs_summary = observable_summary(snap)

    koeppen_path = artifacts_dir / "koeppen_fair.json"
    if synthetic_only:
        from engine.koeppen_grid import export_fair_koeppen_manifest
        export_fair_koeppen_manifest(world, koeppen_path, seed=seed)
        koeppen_source = "synthetic_only"
    else:
        export_fair_koeppen_from_sim(sim, koeppen_path)
        koeppen_source = "genesis_bootstrap"

    epidemic_path = artifacts_dir / "epidemic_contact.json"
    epidemic_block = epidemic_export_for_artifacts(sim)
    epidemic_path.write_text(
        json.dumps(epidemic_block, indent=2), encoding="utf-8")

    render_paths: Dict[str, str] = {}
    if renders and world is not None:
        try:
            from engine.world_render import render_macro_world
            macro_png = artifacts_dir / "civilization_macro.png"
            render_macro_world(world, str(macro_png), mode="biome")
            render_paths["macro_biome"] = str(macro_png)
        except Exception as exc:
            render_paths["error"] = repr(exc)

    py_world = getattr(getattr(sim, "_rust_worldgraph", None), "py_world", None)
    if py_world is None and not synthetic_only:
        from engine.rust_bridge import create_py_world_from_sim
        py_world = create_py_world_from_sim(sim)
    rust_obs = py_world.observe_chunk(0, 0, 0) if py_world is not None else {}
    rust_bridge = bridge_status(sim)
    rw_snap = rust_worldgraph_snapshot(sim) if not synthetic_only else {}

    manifest: Dict[str, Any] = {
        "schema": "genesis.civilization_run/v1",
        "seed": seed,
        "ticks": ticks,
        "founders": founders,
        "synthetic_only": synthetic_only,
        "wall_clock_s": round(elapsed, 3),
        "tps": round(ticks / max(elapsed, 1e-6), 2),
        "n_alive": n_alive,
        "n_agents_active": int(sim.agents.n_active),
        "cum_births": int(sim.stats.cum_births),
        "cum_deaths": int(sim.stats.cum_deaths),
        "world_signature": world_signature(world) if world is not None else None,
        "genesis_meta": genesis_observable_meta(sim),
        "koeppen_source": koeppen_source,
        "artifacts": {
            "observable": str(observable_path),
            "koeppen_fair": str(koeppen_path),
            "epidemic_contact": str(epidemic_path),
            "journal": journal,
        },
        "observable_summary": obs_summary,
        "epidemic": epidemic_block,
        "multi_rate_coupler": coupler_summary(sim),
        "chunk_hydrology": chunk_hydrology_state(sim),
        "genesis_anchor": genesis_anchor_from_sim(
            sim, synthetic_only=synthetic_only) is not None,
        "rust_bridge": rust_bridge,
        "rust_worldgraph": rw_snap,
        "full_stack": stack_status or None,
        "five_cd_installed": bool(stack_status.get("five_cd")),
        "rust_observe_chunk_mock": bool(rust_obs.get("mock")),
        "render_paths": render_paths,
    }
    if boot is not None:
        manifest["modules_installed"] = sorted(boot.modules_installed)
        manifest["modules_skipped"] = dict(boot.modules_skipped)

    manifest_path = artifacts_dir / "civilization_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def _ensure_utf8_stdio() -> None:
    if hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                      errors="replace")


def main() -> int:
    _ensure_utf8_stdio()
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--seed", default="0xC1A71CE0",
                   help="PRF seed (decimal or 0x hex, A-F only in hex form)")
    p.add_argument("--ticks", type=int, default=100)
    p.add_argument("--founders", type=int, default=8)
    p.add_argument("--max-agents", type=int, default=64)
    p.add_argument("--resolution", type=int, default=48,
                   help="Genesis macro grid resolution")
    p.add_argument("--artifacts-dir", default=None,
                   help="Output dir (default: runtime/artifacts)")
    p.add_argument("--synthetic-only", action="store_true",
                   help="Skip bootstrap; isolated macro (not civilization emergence)")
    p.add_argument("--renders", action="store_true",
                   help="Optional macro PNG render")
    p.add_argument("-q", "--quiet", action="store_true")
    args = p.parse_args()

    seed = _parse_seed(args.seed)
    artifacts = Path(args.artifacts_dir or os.path.join(ROOT, "artifacts"))

    print("=" * 78)
    print("Civilization pipeline — emergence from Genesis bootstrap")
    print(f"  seed={seed:#x} ticks={args.ticks} founders={args.founders}")
    if args.synthetic_only:
        print("  WARNING: --synthetic-only (not civilization emergence path)")
    print("=" * 78)

    try:
        manifest = run_civilization_pipeline(
            seed=seed,
            ticks=args.ticks,
            founders=args.founders,
            max_agents=args.max_agents,
            resolution=args.resolution,
            artifacts_dir=artifacts,
            synthetic_only=args.synthetic_only,
            renders=args.renders,
            verbose=not args.quiet,
        )
    except Exception:
        traceback.print_exc()
        return 1

    print(f"  manifest: {manifest['manifest_path']}")
    print(f"  alive={manifest['n_alive']} agents_active={manifest['n_agents_active']}")
    print(f"  koeppen: {manifest['artifacts']['koeppen_fair']}")
    print("=" * 78)
    if manifest["n_alive"] <= 0:
        print("FAIL — no alive agents at end of run")
        return 1
    print("PASS — civilization pipeline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
