"""Python ↔ Rust bridge — native ``genesis_world`` or Genesis-anchored mock."""
from __future__ import annotations

import warnings
from typing import Any, Dict, Optional, Tuple

import numpy as np

from engine.world import CHUNK_SIDE_M, CHUNK_SIZE, VOXEL_SIZE_M

PIPELINE_LAYER = "Genesis-L0 Core"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# Both the canonical `native/world-engine/pybindings` crate and the legacy
# `scaffolding/ge-py` crate compile to a Python module literally named
# `genesis_world`, so a stale legacy wheel can shadow the canonical build in
# site-packages. They expose incompatible APIs (the legacy `observe_chunk`
# requires a 3rd positional `cz`, and it lacks the mutation/snapshot surface),
# which previously surfaced as a cryptic ``TypeError`` deep in the bridge.
# Treat a module as the native backend only when it satisfies this contract.
_CANONICAL_PYWORLD_API = (
    "set_voxel",
    "apply_pending",
    "save_snapshot",
    "restore_snapshot",
)
_warned_non_canonical = False


class MockPyWorld:
    """Stand-in for ``genesis_world.PyWorld`` when maturin wheel is absent.

    When a :class:`engine.world_genesis.GenesisWorld` is supplied, chunk
    observations sample the macro grid (same seed as the Python sim) instead
    of drawing a synthetic RNG field.
    """

    def __init__(self, seed: int = 42, *,
                 genesis_world: Any = None,
                 genesis_anchor: Any = None,
                 **kwargs: Any):
        self.seed = int(seed) & 0xFFFFFFFFFFFFFFFF
        self._genesis = genesis_world
        self._anchor = genesis_anchor
        self._kwargs = kwargs

    def _chunk_macro_km(self, cx: int, cy: int) -> Tuple[float, float]:
        """Chunk centre in continental macro km."""
        ox_m = cx * CHUNK_SIDE_M + CHUNK_SIDE_M * 0.5
        oy_m = cy * CHUNK_SIDE_M + CHUNK_SIDE_M * 0.5
        origin = (0.0, 0.0)
        if self._anchor is not None:
            origin = tuple(self._anchor.sim_origin_macro_km)
        return ox_m / 1000.0 + origin[0], oy_m / 1000.0 + origin[1]

    def observe_chunk(self, cx: int, cy: int, cz: int = 0) -> Dict[str, Any]:
        if self._genesis is not None:
            from engine.world_genesis import sample_macro_grid_full

            world = self._genesis
            ox_m = cx * CHUNK_SIDE_M
            oy_m = cy * CHUNK_SIDE_M
            origin = (0.0, 0.0)
            if self._anchor is not None:
                origin = tuple(self._anchor.sim_origin_macro_km)
            xs = (ox_m + (np.arange(CHUNK_SIZE, dtype=np.float32) + 0.5)
                  * VOXEL_SIZE_M) / 1000.0 + origin[0]
            ys = (oy_m + (np.arange(CHUNK_SIZE, dtype=np.float32) + 0.5)
                  * VOXEL_SIZE_M) / 1000.0 + origin[1]
            XX, YY = np.meshgrid(xs, ys, indexing="xy")
            fields = sample_macro_grid_full(world, XX.ravel(), YY.ravel())
            elev = fields["elevation_m"].astype(np.float32).tolist()
            biome = fields["biome"].astype(np.int32).tolist()
            return {
                "elevation": elev,
                "biome": biome,
                "mock": False,
                "genesis": True,
                "coord": [int(cx), int(cy), int(cz)],
            }

        rng = np.random.default_rng(self.seed ^ (cx * 73856093) ^ (cy * 19349663))
        n = CHUNK_SIZE * CHUNK_SIZE
        elev = (rng.random(n, dtype=np.float32) * 400.0 - 50.0).tolist()
        biome = (rng.integers(0, 10, n, dtype=np.int32)).tolist()
        return {
            "elevation": elev,
            "biome": biome,
            "mock": True,
            "coord": [int(cx), int(cy), int(cz)],
        }

    def biome_at(self, x: float, y: float, z: float = 0.0) -> int:
        if self._genesis is not None:
            from engine.world_genesis import sample_macro

            x_km, y_km = self._chunk_macro_km(int(x // CHUNK_SIDE_M),
                                              int(y // CHUNK_SIDE_M))
            fields = sample_macro(self._genesis, x_km, y_km)
            return int(fields.get("biome", 0))
        h = hash((self.seed, int(x), int(y), int(z))) & 0xFF
        return int(h % 10)


def is_canonical_pyworld(module: Any) -> bool:
    """True when ``module`` exposes the canonical native ``PyWorld`` contract."""
    pyworld = getattr(module, "PyWorld", None)
    if pyworld is None:
        return False
    return all(hasattr(pyworld, name) for name in _CANONICAL_PYWORLD_API)


def try_import_genesis_world() -> Tuple[Any, bool]:
    """Return ``(module_or_mock, is_native)``.

    A module named ``genesis_world`` is accepted as the native backend only
    when it satisfies the canonical ``PyWorld`` contract. A legacy ``ge-py``
    wheel shadowing the name falls back to the API-compatible mock with a
    one-time warning, rather than crashing the bridge downstream.
    """
    global _warned_non_canonical
    try:
        import genesis_world as gw  # type: ignore
    except ImportError:
        return MockPyWorld, False
    if is_canonical_pyworld(gw):
        return gw, True
    if not _warned_non_canonical:
        _warned_non_canonical = True
        warnings.warn(
            "Imported `genesis_world` lacks the canonical PyWorld API ("
            + ", ".join(_CANONICAL_PYWORLD_API)
            + ") — this is the legacy scaffolding/ge-py wheel shadowing the "
            "native build. Falling back to the Genesis-anchored mock. Rebuild "
            "the canonical wheel with `make maturin-dev`.",
            RuntimeWarning,
            stacklevel=2,
        )
    return MockPyWorld, False


def _macro_kwargs(genesis_world: Any = None,
                  genesis_anchor: Any = None,
                  **kwargs: Any) -> Dict[str, Any]:
    """Attach GENM v2 bytes + anchor params to native PyWorld.

    When a GenesisWorld is available, exports the full macro grid
    (elevation + temperature + precipitation + biome) so the Rust
    backend can do genesis-blend sampling without a Python round-trip.
    """
    if genesis_world is None:
        return dict(kwargs)
    try:
        from engine.macro_grid_export import export_macro_grid_bytes

        kwargs = dict(kwargs)
        kwargs["macro_grid_bytes"] = export_macro_grid_bytes(genesis_world)
        from engine.world import CHUNK_SIDE_M

        kwargs.setdefault("chunk_side_m", float(CHUNK_SIDE_M))
        # Pass anchor params if available (Phase 3e).
        if genesis_anchor is not None:
            ox, oy = genesis_anchor.sim_origin_macro_km
            kwargs["sim_origin_x_km"] = float(ox)
            kwargs["sim_origin_y_km"] = float(oy)
            kwargs["blend"] = float(genesis_anchor.blend)
            kwargs["micro_amp_m"] = float(genesis_anchor.micro_amp_m)
            kwargs["micro_amp_temp_c"] = float(genesis_anchor.micro_amp_temp_c)
            kwargs["micro_amp_precip_mm"] = float(genesis_anchor.micro_amp_precip_mm)
    except Exception:
        pass
    return kwargs


def create_py_world(seed: int = 42, *,
                    genesis_world: Any = None,
                    genesis_anchor: Any = None,
                    synthetic_only: bool = False,
                    **kwargs: Any) -> Any:
    """Construct native ``PyWorld`` or :class:`MockPyWorld`.

    When ``genesis_world`` is set (or ``synthetic_only`` is False and a
    sim with bootstrap is passed via :func:`create_py_world_from_sim`),
    mock observations align with the Python Genesis macro map.
    """
    gw, native = try_import_genesis_world()
    if native:
        kw = _macro_kwargs(genesis_world, genesis_anchor=genesis_anchor, **kwargs)
        return gw.PyWorld(seed=seed, **kw)
    if synthetic_only and genesis_world is None:
        return MockPyWorld(seed=seed, **kwargs)
    return MockPyWorld(
        seed=seed,
        genesis_world=genesis_world,
        genesis_anchor=genesis_anchor,
        **kwargs,
    )


def create_py_world_from_sim(sim, *,
                             synthetic_only: bool = False,
                             **kwargs: Any) -> Any:
    """Build a Rust/mock world handle using the sim's Genesis bootstrap context."""
    seed = int(getattr(sim.cfg, "seed", 42))
    world = None
    anchor = None
    if not synthetic_only:
        try:
            from engine.genesis_bootstrap import bootstrap_state
            state = bootstrap_state(sim)
            if state is not None:
                world = state.world
                anchor = state.anchor
        except Exception:
            pass
        if anchor is None:
            anchor = getattr(getattr(sim, "streamer", None), "genesis", None)
    gw, native = try_import_genesis_world()
    if native:
        world = world or getattr(anchor, "world", None) if anchor else world
        kw = _macro_kwargs(world, genesis_anchor=anchor, **kwargs)
        return gw.PyWorld(seed=seed, **kw)
    return MockPyWorld(
        seed=seed,
        genesis_world=world,
        genesis_anchor=anchor,
        **kwargs,
    )


def bridge_status(sim=None) -> Dict[str, Any]:
    """Diagnostic for dashboards / CI."""
    _, native = try_import_genesis_world()
    out: Dict[str, Any] = {
        "native": native,
        "module": "genesis_world" if native else "engine.rust_bridge.MockPyWorld",
    }
    if sim is not None:
        try:
            from engine.genesis_bootstrap import bootstrap_state
            st = bootstrap_state(sim)
            out["genesis_bootstrapped"] = st is not None
            out["genesis_seed"] = int(sim.cfg.seed) if st else None
        except Exception:
            out["genesis_bootstrapped"] = False
    return out


__all__ = [
    "MockPyWorld",
    "is_canonical_pyworld",
    "try_import_genesis_world",
    "create_py_world",
    "create_py_world_from_sim",
    "bridge_status",
]
