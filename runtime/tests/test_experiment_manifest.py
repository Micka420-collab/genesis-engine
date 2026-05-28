"""Tests for engine.experiment_manifest.

Covers provenance capture, deterministic fingerprinting, both object-with-
summary() and plain-dict attach paths, and exception handling. The
context manager must always write a manifest, even on crash, so partial
runs are diagnosable.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.experiment_manifest import (
    RunManifest,
    capture_provenance,
    compute_state_fingerprint,
    experimental_run,
)


def test_capture_provenance_returns_expected_keys():
    p = capture_provenance()
    # All keys must be present even when individual values are None.
    expected = {
        "repo_root",
        "git",
        "pyproject_sha256",
        "python_version",
        "python_executable",
        "platform",
        "platform_machine",
        "captured_at_iso",
        "env_pythonpath",
    }
    assert expected.issubset(set(p.keys()))
    assert isinstance(p["python_version"], str)
    assert p["python_version"]  # non-empty


def test_capture_provenance_does_not_raise_outside_repo(tmp_path):
    # tmp_path has no .git and no pyproject.toml — provenance must still work.
    p = capture_provenance(repo_root=tmp_path)
    assert p["git"] == {}
    assert p["pyproject_sha256"] is None
    assert p["repo_root"] == str(tmp_path)


def test_state_fingerprint_is_deterministic_for_same_dict():
    summary = {"tick": 100, "n_alive": 5, "seed": 0xC0FFEE}
    f1 = compute_state_fingerprint(summary)
    f2 = compute_state_fingerprint(summary)
    assert f1 == f2
    assert len(f1) == 64  # sha256 hex


def test_state_fingerprint_is_invariant_under_key_order():
    # The whole point of sort_keys=True — two dicts with same content but
    # different iteration order must hash identically.
    a = {"alpha": 1, "beta": 2, "gamma": 3}
    b = {"gamma": 3, "alpha": 1, "beta": 2}
    assert compute_state_fingerprint(a) == compute_state_fingerprint(b)


def test_state_fingerprint_changes_on_value_change():
    base = {"tick": 100, "n_alive": 5}
    diff = {"tick": 101, "n_alive": 5}
    assert compute_state_fingerprint(base) != compute_state_fingerprint(diff)


def test_state_fingerprint_ignores_volatile_keys():
    # Same simulation state, different wall-clock/host noise → same hash.
    # This is what makes a fingerprint a reproducible, citable identity.
    a = {"tick": 100, "n_alive": 5, "tps": 19.84, "wall_clock_s": 16.1,
         "manifest_path": "/home/alice/genesis/run.json"}
    b = {"tick": 100, "n_alive": 5, "tps": 12.07, "wall_clock_s": 27.9,
         "manifest_path": "C:\\Users\\bob\\genesis\\run.json"}
    assert compute_state_fingerprint(a) == compute_state_fingerprint(b)


def test_state_fingerprint_strips_volatile_keys_at_depth():
    a = {"summary": {"n_alive": 5, "tps": 1.0}, "epidemic": {"r0": 0.75}}
    b = {"summary": {"n_alive": 5, "tps": 99.0}, "epidemic": {"r0": 0.75}}
    assert compute_state_fingerprint(a) == compute_state_fingerprint(b)
    # but a real observable still moves the hash
    c = {"summary": {"n_alive": 6, "tps": 1.0}, "epidemic": {"r0": 0.75}}
    assert compute_state_fingerprint(a) != compute_state_fingerprint(c)


class _FakeWorld:
    """Minimal stand-in for engine.world_builder.World — same .summary()
    surface, no dependencies."""

    def __init__(self, payload: dict):
        self._payload = payload

    def summary(self) -> dict:
        return dict(self._payload)


def test_experimental_run_writes_manifest_and_summary(tmp_path):
    with experimental_run("smoke", root=tmp_path) as ctx:
        world = _FakeWorld({"tick": 42, "n_alive": 7, "seed": 0xC0FFEE})
        ctx.attach(world)
        ctx.note("synthetic baseline")

    runs = list(tmp_path.iterdir())
    assert len(runs) == 1
    run_dir = runs[0]
    assert run_dir.name.startswith("smoke_")
    manifest_path = run_dir / "manifest.json"
    summary_path = run_dir / "summary.json"
    assert manifest_path.exists()
    assert summary_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["name"] == "smoke"
    assert manifest["summary"]["tick"] == 42
    assert manifest["state_fingerprint"]
    assert manifest["wall_clock_s"] >= 0.0
    assert manifest["provenance"]["python_version"]
    assert "synthetic baseline" in manifest["notes"]


def test_experimental_run_accepts_dict_summary(tmp_path):
    with experimental_run("dict_attach", root=tmp_path) as ctx:
        ctx.attach({"tick": 1, "n_alive": 1})
    runs = list(tmp_path.iterdir())
    manifest = json.loads((runs[0] / "manifest.json").read_text("utf-8"))
    assert manifest["summary"]["tick"] == 1


def test_experimental_run_rejects_non_world_non_dict(tmp_path):
    with pytest.raises(TypeError):
        with experimental_run("type_check", root=tmp_path) as ctx:
            ctx.attach(42)  # int has no .summary() and isn't a dict


def test_experimental_run_rejects_summary_not_returning_dict(tmp_path):
    class BadWorld:
        def summary(self):
            return ["not", "a", "dict"]

    with pytest.raises(TypeError):
        with experimental_run("bad_summary", root=tmp_path) as ctx:
            ctx.attach(BadWorld())


def test_experimental_run_writes_manifest_on_exception(tmp_path):
    class Boom(Exception):
        pass

    with pytest.raises(Boom):
        with experimental_run("crash", root=tmp_path) as ctx:
            ctx.note("about to crash")
            raise Boom("intentional")

    runs = list(tmp_path.iterdir())
    assert len(runs) == 1
    manifest = json.loads((runs[0] / "manifest.json").read_text("utf-8"))
    # Crash recorded as a note, summary is None (nothing attached).
    assert any("Boom" in n for n in manifest["notes"])
    assert manifest["summary"] is None
    assert manifest["state_fingerprint"] is None
    # No summary.json should be written when there is no summary.
    assert not (runs[0] / "summary.json").exists()


def test_experimental_run_uses_explicit_run_id(tmp_path):
    with experimental_run("baseline", root=tmp_path, run_id="r001") as ctx:
        ctx.attach({"tick": 0})
    assert (tmp_path / "r001" / "manifest.json").exists()


def test_two_runs_with_same_summary_produce_same_fingerprint(tmp_path):
    """The bit-comparison spine: identical worlds → identical fingerprints,
    so a falsifiability claim can quote a hash."""
    payload = {"tick": 500, "n_alive": 12, "seed": 0xC0FFEE_5A}
    with experimental_run("a", root=tmp_path) as ctx:
        ctx.attach(payload)
    with experimental_run("b", root=tmp_path) as ctx:
        ctx.attach(payload)
    manifests = sorted(tmp_path.glob("*/manifest.json"))
    assert len(manifests) == 2
    fp_a = json.loads(manifests[0].read_text("utf-8"))["state_fingerprint"]
    fp_b = json.loads(manifests[1].read_text("utf-8"))["state_fingerprint"]
    assert fp_a == fp_b


def test_experimental_run_rejects_reuse(tmp_path):
    # A single experimental_run instance is one-shot — calling `with` on
    # the same object twice would silently clobber the prior manifest's
    # in-memory state. We force a clear error instead.
    runner = experimental_run("reuse", root=tmp_path)
    with runner as ctx:
        ctx.attach({"tick": 1})
    with pytest.raises(RuntimeError, match="single-use"):
        with runner:
            pass


def test_experimental_run_exit_without_enter_raises_runtime_error():
    # Defends against `assert`-stripping under `python -O` and against
    # exotic contextlib wrappers that might call __exit__ without
    # __enter__. Behaviour must be a clear RuntimeError, not an
    # AttributeError on `None._monotonic_start`.
    runner = experimental_run("never_entered")
    with pytest.raises(RuntimeError, match="without __enter__"):
        runner.__exit__(None, None, None)


def test_run_manifest_dataclass_round_trip():
    # to_dict() must be JSON-safe and lossless for the fields we populate.
    m = RunManifest(
        name="x", run_id="x_1", started_at="2026-05-27T00:00:00Z",
        summary={"tick": 1}, state_fingerprint="abc",
    )
    d = m.to_dict()
    j = json.loads(json.dumps(d))  # round-trip through JSON
    assert j["name"] == "x"
    assert j["summary"]["tick"] == 1
    assert j["state_fingerprint"] == "abc"
