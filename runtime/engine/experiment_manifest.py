"""Experiment manifest — provenance capture for reproducible runs.

Wraps any block producing a world-like object with ``.summary()`` and writes
a triplet under ``runtime/experiments/<run_id>/``:

* ``manifest.json`` — provenance (git, pyproject hash, platform, timing) +
  the captured summary + a state fingerprint sha256.
* ``summary.json`` — the bare ``world.summary()`` payload, for direct
  dashboard consumption without parsing the full manifest.

The goal is the C1/C2 spine of `RUNTIME-LAYOUT.md` §"méthodologie scientifique":
every long run gets a self-contained record so two runs of the same code on
the same commit are bit-comparable, and a falsifiability claim about run X
can quote run X's manifest hash rather than waving at a directory.

Usage::

    from engine.experiment_manifest import experimental_run
    from engine.world_builder import WorldBuilder

    with experimental_run("lausanne-baseline") as ctx:
        world = (
            WorldBuilder("demo")
            .anchor(46.51, 6.63)
            .size_km(2.0)
            .founders(20)
            .build()
        )
        world.run(500)
        ctx.attach(world)        # records summary + fingerprint
        ctx.note("baseline parameters; no perturbations")

    # → runtime/experiments/lausanne-baseline_20260527T143012Z/manifest.json
    # → runtime/experiments/lausanne-baseline_20260527T143012Z/summary.json

The context manager **does not** swallow exceptions: a crash inside the
block still writes a manifest with ``summary = None`` and a note recording
the exception type, so partial runs are diagnosable.

Determinism note: the state fingerprint is computed from the summary dict
via a canonical JSON serialization (sorted keys). It tracks whatever the
``world.summary()`` chooses to expose. To make two runs bit-comparable on a
specific metric, surface that metric in summary.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


__all__ = [
    "RunManifest",
    "capture_provenance",
    "compute_state_fingerprint",
    "experimental_run",
]


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------


def _git_provenance(repo_root: Path) -> dict:
    """Best-effort git HEAD capture. Returns empty dict if not a repo or
    git binary is missing — we never block a run on missing provenance."""
    if not (repo_root / ".git").exists():
        return {}
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5.0,
        ).strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return {}
    dirty: Optional[bool] = None
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5.0,
        )
        dirty = bool(status.strip())
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    return {"commit": sha, "dirty": dirty}


def _file_sha256(path: Path) -> Optional[str]:
    """Return the hex sha256 of a file, or None if it does not exist."""
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_repo_root() -> Path:
    """Walk up from this file looking for a directory containing
    ``pyproject.toml``. Falls back to the immediate parent if nothing matches."""
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return here.parent


def capture_provenance(repo_root: Optional[Path] = None) -> dict:
    """Snapshot the reproducibility-relevant state of the current process.

    All fields are best-effort; missing values become ``None`` rather than
    raising. The intent is that the manifest is always written even on
    machines without git installed.
    """
    root = Path(repo_root) if repo_root is not None else _find_repo_root()
    return {
        "repo_root": str(root),
        "git": _git_provenance(root),
        "pyproject_sha256": _file_sha256(root / "pyproject.toml"),
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "platform_machine": platform.machine(),
        "captured_at_iso": datetime.now(timezone.utc).isoformat(),
        "env_pythonpath": os.environ.get("PYTHONPATH", ""),
    }


def compute_state_fingerprint(summary: Any) -> str:
    """Deterministic sha256 over a JSON-serializable payload.

    ``sort_keys=True`` makes the hash invariant under dict iteration order.
    ``default=str`` is a last-resort serializer for stray dataclasses or
    numpy scalars — these become their ``str()`` representation, which
    is stable within a single Python build but **not** guaranteed across
    types we don't recognize. Keep summary payloads to plain JSON types
    when you want cross-process bit-identity.
    """
    canonical = json.dumps(summary, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Manifest dataclass
# ---------------------------------------------------------------------------


@dataclass
class RunManifest:
    """Complete record written to ``manifest.json`` at run end."""

    name: str
    run_id: str
    started_at: str
    ended_at: Optional[str] = None
    wall_clock_s: Optional[float] = None
    provenance: dict = field(default_factory=dict)
    summary: Optional[dict] = None
    state_fingerprint: Optional[str] = None
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Context object exposed inside the `with` block
# ---------------------------------------------------------------------------


class _RunContext:
    """Handle yielded by :class:`experimental_run`.

    The block must call :meth:`attach` exactly once with the final world
    (or summary dict) to record the run's state. :meth:`note` adds a free
    text annotation to the manifest — use it for hypotheses, perturbation
    descriptions, or post-hoc observations.
    """

    def __init__(self, manifest: RunManifest, run_dir: Path) -> None:
        self.manifest = manifest
        self.run_dir = run_dir
        self._monotonic_start = time.monotonic()
        self._attached_summary: Optional[dict] = None

    def attach(self, world_or_summary: Any) -> None:
        """Capture the run's final state.

        Accepts either:
          * an object exposing a ``.summary()`` method returning a JSON-
            serializable dict (this is what :class:`engine.world_builder.World`
            returns), or
          * a plain dict (e.g. when the caller already aggregated stats).

        Calling :meth:`attach` more than once overwrites the previous
        capture — the latest one wins.
        """
        if hasattr(world_or_summary, "summary") and callable(
            getattr(world_or_summary, "summary")
        ):
            payload = world_or_summary.summary()
        elif isinstance(world_or_summary, dict):
            payload = world_or_summary
        else:
            raise TypeError(
                "experimental_run.attach() expects an object with a "
                ".summary() method or a dict; got "
                f"{type(world_or_summary).__name__}"
            )
        if not isinstance(payload, dict):
            raise TypeError(
                "experimental_run: .summary() must return a dict; got "
                f"{type(payload).__name__}"
            )
        self._attached_summary = payload

    def note(self, line: str) -> None:
        """Append a free text line to the manifest's ``notes`` list."""
        self.manifest.notes.append(str(line))


# ---------------------------------------------------------------------------
# The context manager itself
# ---------------------------------------------------------------------------


class experimental_run:
    """Context manager that produces a provenance manifest for a run.

    Parameters
    ----------
    name : str
        Human-readable run identity. Becomes the prefix of ``run_id``.
    root : Path, optional
        Directory under which ``<run_id>/`` is created. Defaults to
        ``runtime/experiments`` next to the repo root.
    run_id : str, optional
        Override the auto-generated identifier. Useful when re-running a
        named experiment for comparison; you accept overwriting prior
        results in that directory.

    The class name is lowercased intentionally because callers use it like
    a function: ``with experimental_run("name") as ctx:``. Aliasing it to a
    factory function would obscure the typing.
    """

    def __init__(
        self,
        name: str,
        root: Optional[Path] = None,
        run_id: Optional[str] = None,
    ) -> None:
        self.name = str(name)
        if root is None:
            root = _find_repo_root() / "runtime" / "experiments"
        self.root = Path(root)
        if run_id is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            run_id = f"{name}_{ts}"
        self.run_id = str(run_id)
        self._ctx: Optional[_RunContext] = None

    def __enter__(self) -> _RunContext:
        # Guard against reuse: a single experimental_run instance is a
        # one-shot. Trying to re-enter would silently overwrite self._ctx
        # and lose the previous manifest. Force the caller to construct a
        # fresh instance — clearer intent + no chance of corrupting the
        # already-on-disk manifest with a half-written second one.
        if self._ctx is not None:
            raise RuntimeError(
                "experimental_run is single-use; instantiate a new "
                f"experimental_run({self.name!r}, ...) for the next run"
            )
        run_dir = self.root / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = RunManifest(
            name=self.name,
            run_id=self.run_id,
            started_at=datetime.now(timezone.utc).isoformat(),
            provenance=capture_provenance(),
        )
        self._ctx = _RunContext(manifest, run_dir)
        return self._ctx

    def __exit__(self, exc_type, exc, tb) -> bool:
        # Use an explicit check rather than `assert`: assertions can be
        # stripped by `python -O` and we still need the invariant to hold
        # in production.
        if self._ctx is None:
            raise RuntimeError(
                "experimental_run.__exit__ called without __enter__; "
                "this should be impossible — likely a custom "
                "contextlib wrapper bug"
            )
        ctx = self._ctx
        ctx.manifest.wall_clock_s = time.monotonic() - ctx._monotonic_start
        ctx.manifest.ended_at = datetime.now(timezone.utc).isoformat()
        if exc is not None:
            ctx.manifest.notes.append(
                f"exception:{exc_type.__name__}:{exc}"
            )
        if ctx._attached_summary is not None:
            ctx.manifest.summary = ctx._attached_summary
            ctx.manifest.state_fingerprint = compute_state_fingerprint(
                ctx._attached_summary
            )
            (ctx.run_dir / "summary.json").write_text(
                json.dumps(ctx._attached_summary, indent=2, default=str),
                encoding="utf-8",
            )
        (ctx.run_dir / "manifest.json").write_text(
            json.dumps(ctx.manifest.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        # Never swallow — caller decides how to handle.
        return False
