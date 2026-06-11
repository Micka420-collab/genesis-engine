"""Contract: a ``genesis_world`` wheel is trusted as native only by capability.

Both the ``native/world-engine/pybindings`` crate and the ``scaffolding/ge-py``
crate publish a Python module named ``genesis_world``, so a wheel can shadow the
other in site-packages. They expose different surfaces:

  - ge-py drives the simulation hot path through the *terrain* contract
    (``sample_terrain_chunk`` / ``observe_chunk``).
  - pybindings adds the *snapshot* contract (``set_voxel`` / ``save_snapshot`` …).

``try_import_genesis_world`` accepts a module as native when it satisfies
*either* contract, and falls back to the Genesis-anchored mock (with a one-time
warning) only when it matches neither. Regression guard: a wheel exposing the
terrain contract must NOT be silently rejected back to the mock — that bug kept
the Rust backend inactive at runtime despite a working wheel being installed.
"""
from __future__ import annotations

import sys
import types
import warnings

import pytest

import engine.rust_bridge as rb


def _fake_genesis_world(*, canonical: bool = False,
                        terrain: bool = False) -> types.ModuleType:
    mod = types.ModuleType("genesis_world")

    class PyWorld:
        def __init__(self, *args, **kwargs):
            pass

        def observe_chunk(self, cx, cy, cz=0):
            return {}

    if canonical:
        for name in rb._CANONICAL_PYWORLD_API:
            setattr(PyWorld, name, lambda self, *a, **k: None)
    if terrain:
        PyWorld.sample_terrain_chunk = lambda self, *a, **k: {}

    mod.PyWorld = PyWorld  # type: ignore[attr-defined]
    return mod


@pytest.fixture
def _clean_bridge_state(monkeypatch):
    monkeypatch.setattr(rb, "_warned_non_canonical", False)
    monkeypatch.delitem(sys.modules, "genesis_world", raising=False)
    yield
    monkeypatch.delitem(sys.modules, "genesis_world", raising=False)


def test_incompatible_wheel_falls_back_to_mock(monkeypatch, _clean_bridge_state):
    # PyWorld matching neither contract (observe_chunk only) → mock + warning.
    monkeypatch.setitem(sys.modules, "genesis_world",
                        _fake_genesis_world(canonical=False, terrain=False))
    with pytest.warns(RuntimeWarning, match="neither the terrain contract"):
        module, native = rb.try_import_genesis_world()
    assert native is False
    assert module is rb.MockPyWorld


def test_terrain_wheel_is_treated_as_native(monkeypatch, _clean_bridge_state):
    # Regression guard for the silent-rejection bug: a wheel exposing the
    # terrain contract (the ge-py hot-path surface) must be native, no warning.
    fake = _fake_genesis_world(terrain=True)
    monkeypatch.setitem(sys.modules, "genesis_world", fake)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # a usable backend must not warn
        module, native = rb.try_import_genesis_world()
    assert native is True
    assert module is fake


def test_canonical_wheel_is_treated_as_native(monkeypatch, _clean_bridge_state):
    fake = _fake_genesis_world(canonical=True)
    monkeypatch.setitem(sys.modules, "genesis_world", fake)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # canonical must not warn
        module, native = rb.try_import_genesis_world()
    assert native is True
    assert module is fake


def test_observe_chunk_compat_bridges_both_arities():
    # The two wheels disagree on observe_chunk arity; the adapter must serve both
    # and must NOT mask a non-arity TypeError raised inside the method.
    class Terrain:  # ge-py / mock: requires cz
        def observe_chunk(self, cx, cy, cz):
            return {"arity": 3, "cz": cz}

    class Canonical:  # pybindings: 2-arg only
        def observe_chunk(self, cx, cy):
            return {"arity": 2}

    class Broken:
        def observe_chunk(self, cx, cy, cz=0):
            raise TypeError("unrelated boom")

    assert rb.observe_chunk_compat(Terrain(), 1, 2) == {"arity": 3, "cz": 0}
    assert rb.observe_chunk_compat(Canonical(), 1, 2) == {"arity": 2}
    with pytest.raises(TypeError, match="boom"):
        rb.observe_chunk_compat(Broken(), 1, 2)


def test_contract_predicates():
    assert rb.is_canonical_pyworld(_fake_genesis_world(canonical=True)) is True
    assert rb.is_canonical_pyworld(_fake_genesis_world(terrain=True)) is False
    assert rb.is_terrain_pyworld(_fake_genesis_world(terrain=True)) is True
    assert rb.is_terrain_pyworld(_fake_genesis_world(canonical=True)) is False
    assert rb.is_native_pyworld(_fake_genesis_world(terrain=True)) is True
    assert rb.is_native_pyworld(_fake_genesis_world(canonical=True)) is True
    assert rb.is_native_pyworld(_fake_genesis_world()) is False
    assert rb.is_native_pyworld(types.ModuleType("empty")) is False
