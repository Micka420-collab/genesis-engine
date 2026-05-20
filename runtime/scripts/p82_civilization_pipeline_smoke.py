"""P82 — Civilization pipeline smoke (20 ticks, manifest, agents > 0)."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from civilization_pipeline import run_civilization_pipeline  # noqa: E402


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P82 — Civilization pipeline smoke")
    print("=" * 78)
    failures = 0
    seed = 0xC082_0001

    with tempfile.TemporaryDirectory() as tmp:
        art = os.path.join(tmp, "artifacts")
        manifest = run_civilization_pipeline(
            seed=seed,
            ticks=20,
            founders=6,
            max_agents=24,
            resolution=32,
            artifacts_dir=os.path.join(art),
            synthetic_only=False,
            renders=False,
            verbose=False,
        )
        mpath = manifest.get("manifest_path") or os.path.join(
            art, "civilization_run_manifest.json")
        ok = os.path.isfile(mpath)
        print(_row("manifest exists", ok, mpath))
        if not ok:
            failures += 1

        ok = manifest.get("n_alive", 0) > 0 and manifest.get("n_agents_active", 0) > 0
        print(_row("agents > 0", ok,
                   f"alive={manifest.get('n_alive')} active={manifest.get('n_agents_active')}"))
        if not ok:
            failures += 1

        ok = manifest.get("koeppen_source") == "genesis_bootstrap"
        print(_row("koeppen from bootstrap", ok, str(manifest.get("koeppen_source"))))
        if not ok:
            failures += 1

        koeppen_file = manifest.get("artifacts", {}).get("koeppen_fair")
        ok = koeppen_file and os.path.isfile(koeppen_file)
        if ok:
            with open(koeppen_file, encoding="utf-8") as f:
                fair = json.load(f)
            ok = fair.get("seed") == seed and "checksum_sha256" in fair
        print(_row("FAIR koeppen checksums", ok))
        if not ok:
            failures += 1

        obs_file = manifest.get("artifacts", {}).get("observable")
        ok = obs_file and os.path.isfile(obs_file)
        if ok:
            with open(obs_file, encoding="utf-8") as f:
                obs = json.load(f)
            ok = obs.get("meta", {}).get("genesis") is True
        print(_row("observable genesis meta", ok))
        if not ok:
            failures += 1

        ok = not manifest.get("rust_observe_chunk_mock", True)
        print(_row("rust bridge uses genesis mock grid", ok,
                   f"mock={manifest.get('rust_observe_chunk_mock')}"))
        if not ok:
            failures += 1

    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
