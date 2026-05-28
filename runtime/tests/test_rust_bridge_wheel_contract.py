"""Regression: a legacy ``genesis_world`` wheel must not be trusted as native.

Both the canonical ``native/world-engine/pybindings`` crate and the legacy
``scaffolding/ge-py`` crate publish a Python module named ``genesis_world``,
so a stale legacy wheel can shadow the canonical build in site-packages. The
two expose incompatible APIs, which used to crash the bridge with a cryptic
``TypeError``. ``try_import_genesis_world`` now verifies the PyWorld contract
and falls back to the Genesis-anchored mock instead.
"""
from __future__ import annotations

import sys
import types
import warnings

import pytest

import engine.rust_bridge as rb


def _fake_genesis_world(*, canonical: bool) -> types.ModuleType:
    mod = types.ModuleType("genesis_world")

    class PyWorld:
        def __init__(self, *args, **kwargs):
            pass

        def observe_chunk(self, cx, cy):  # canonical 2-arg signature
            return {}

    if canonical:
        for name in rb._CANONICAL_PYWORLD_API:
            setattr(PyWorld, name, lambda self, *a, **k: None)

    mod.PyWorld = PyWorld  # type: ignore[attr-defined]
    return mod


@pytest.fixture
def _clean_bridge_state(monkeypatch):
    monkeypatch.setattr(rb, "_warned_non_canonical", False)
    monkeypatch.delitem(sys.modules, "genesis_world", raising=False)
    yield
    monkeypatch.delitem(sys.modules, "genesis_world", raising=False)


def test_legacy_wheel_falls_back_to_mock(monkeypatch, _clean_bridge_state):
    monkeypatch.setitem(sys.modules, "genesis_world",
                        _fake_genesis_world(canonical=False))
    with pytest.warns(RuntimeWarning, match="legacy"):
        module, native = rb.try_import_genesis_world()
    assert native is False
    assert module is rb.MockPyWorld


def test_canonical_wheel_is_treated_as_native(monkeypatch, _clean_bridge_state):
    fake = _fake_genesis_world(canonical=True)
    monkeypatch.setitem(sys.modules, "genesis_world", fake)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # canonical must not warn
        module, native = rb.try_import_genesis_world()
    assert native is True
    assert module is fake


def test_is_canonical_pyworld_predicate():
    assert rb.is_canonical_pyworld(_fake_genesis_world(canonical=True)) is True
    assert rb.is_canonical_pyworld(_fake_genesis_world(canonical=False)) is False
    assert rb.is_canonical_pyworld(types.ModuleType("empty")) is False
