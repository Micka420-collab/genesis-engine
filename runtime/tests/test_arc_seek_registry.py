"""Invariants — the arc-consumption registry (refactor, 2026-06-29; ADR-0009 D12 debt).

``cognition.decide()`` used to call the per-capability ``_seek_*`` helpers as a hand-written
sequence that grew with every D12 wire. This refactor centralises them in an ordered registry
``_ARC_SEEKS`` evaluated by ``_run_arc_seeks`` under a perception budget ``ARC_SEEK_BUDGET``.

These tests lock the contract WITHOUT booting a world (fast, pure):
1. The registry order is the canonical one (survival/tools → fire → transforms → symbol).
2. Every entry maps a stable name to the real ``cognition._seek_*`` callable.
3. The budget is ≥ the registry length, so the refactor is behaviour-identical to the old inlined
   sequence (no seek is silently dropped during the arc campaign).
4. ``_run_arc_seeks`` returns the FIRST non-None decision in order, and ``None`` when all yield —
   i.e. exactly the short-circuit semantics of the former ``if d is not None: return d`` chain.
5. The budget actually bounds how many seeks are evaluated (the hot-loop rail works).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine import cognition as cog                               # noqa: E402

# The canonical order the inlined sequence used (frozen here as the contract).
EXPECTED_ORDER = [
    "frost_clast", "toolstone", "firesite", "tempersite",
    "clay", "kiln", "limestone", "limekiln", "saltpan", "fuel", "kilnbuild",
    "forcedraught", "smelt", "bloom", "cure", "ochre", "canvas", "prospect",
]


def test_registry_order_is_canonical():
    assert [name for name, _ in cog._ARC_SEEKS] == EXPECTED_ORDER


def test_registry_entries_map_to_real_seek_callables():
    expected_func = {
        "frost_clast": cog._seek_frost_clast,
        "toolstone": cog._seek_toolstone,
        "firesite": cog._seek_firesite,
        "tempersite": cog._seek_tempersite,
        "clay": cog._seek_clay,
        "kiln": cog._seek_kiln,
        "limestone": cog._seek_limestone,
        "limekiln": cog._seek_limekiln,
        "saltpan": cog._seek_saltpan,
        "fuel": cog._seek_fuel,
        "kilnbuild": cog._seek_kilnbuild,
        "forcedraught": cog._seek_forcedraught,
        "smelt": cog._seek_smelt,
        "bloom": cog._seek_bloom,
        "cure": cog._seek_cure,
        "ochre": cog._seek_ochre,
        "canvas": cog._seek_canvas,
        "prospect": cog._seek_prospect,
    }
    for name, func in cog._ARC_SEEKS:
        assert callable(func)
        assert func is expected_func[name], f"registry entry {name!r} points at the wrong callable"


def test_budget_covers_the_whole_registry():
    # ≥ len ⇒ behaviour-identical to the former hand-written sequence (nothing dropped).
    assert cog.ARC_SEEK_BUDGET >= len(cog._ARC_SEEKS)


def test_run_arc_seeks_returns_first_non_none_in_order(monkeypatch):
    calls = []

    def mk(name, result):
        def _seek(agents, row, obs, sim):
            calls.append(name)
            return result
        return _seek

    sentinel = object()
    # second entry fires; the third must NOT be evaluated (short-circuit), first returns None.
    monkeypatch.setattr(cog, "_ARC_SEEKS", (
        ("a", mk("a", None)),
        ("b", mk("b", sentinel)),
        ("c", mk("c", object())),
    ))
    out = cog._run_arc_seeks(agents=None, row=0, obs=None, sim=None)
    assert out is sentinel
    assert calls == ["a", "b"]          # stopped at the first non-None, never reached "c"


def test_run_arc_seeks_returns_none_when_all_yield(monkeypatch):
    monkeypatch.setattr(cog, "_ARC_SEEKS", tuple(
        (n, (lambda *a, **k: None)) for n in ("a", "b", "c")))
    assert cog._run_arc_seeks(agents=None, row=0, obs=None, sim=None) is None


def test_budget_bounds_seeks_evaluated(monkeypatch):
    calls = []

    def mk(name):
        def _seek(agents, row, obs, sim):
            calls.append(name)
            return None
        return _seek

    monkeypatch.setattr(cog, "_ARC_SEEKS", tuple((n, mk(n)) for n in "abcdef"))
    monkeypatch.setattr(cog, "ARC_SEEK_BUDGET", 3)
    cog._run_arc_seeks(agents=None, row=0, obs=None, sim=None)
    assert calls == ["a", "b", "c"]     # budget capped evaluation at 3, the rest skipped
