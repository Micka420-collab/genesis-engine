"""Capability aggregator — feeds ``/api/world_model_capabilities``.

Implements **P-NEW.20** from `NEXT-SPRINT.md`, completing the ADR-0005
validation horizon (30 days, cible 2026-06-13).

Each Genesis module that contributes a world-model layer publishes two
machine-readable constants right after its docstring (per ADR 0005):

``PIPELINE_LAYER``           — Genesis pipeline axis (L1-L5).
``WORLD_MODEL_CAPABILITY``   — arxiv 2604.22748 axis (paper-L1/L2/L3).

This module discovers them at runtime and exposes a single, dependency-free
table consumable by the dashboard endpoint and by CI:

``world_model_capabilities()`` returns the table as a list of dicts.
``audit_modules(strict=False)`` returns ``(table, missing)`` so a CI linter
can fail the build when an *expected* module forgets its tags.

Determinism: pure introspection, no side effects, no RNG, no I/O beyond
imports. Safe to call from any handler thread.
"""
from __future__ import annotations

import importlib
from typing import Dict, List, Tuple

# Taxonomy — meta-module, declares itself in the table for self-completeness.
PIPELINE_LAYER = "meta"
WORLD_MODEL_CAPABILITY = "n/a"


# Modules required by ADR-0005 to publish capability tags. The list is the
# enforcement contract for the CI linter (P-NEW.20). Adding a new layer
# module means: (1) publish constants, (2) append the dotted name here.
_REQUIRED_MODULES: Tuple[str, ...] = (
    "engine.earth_loader",
    "engine.sim_lift",
    "engine.realism",
    "engine.physiology",
    "engine.photosynthesis",
    "engine.material_aging",
    "engine.marine",
    "engine.global_world",
    "engine.plant_evolution",
    "engine.meteorology",
    "engine.animal_evolution",
    "engine.agriculture",
    "engine.writing",
    "engine.polity",
    "engine.geology",
    "engine.metallurgy",
    "engine.realistic_construction",
    "engine.building_discovery",
    "engine.art_discovery",
    "engine.wildfire",
    "engine.surface_mineralization",
    "engine.lithic_outcrop",
    "engine.water_potability",
)

# Modules that ADR-0005 references but which are still R&D. They are queried
# best-effort: present → reported; absent → not an error.
_OPTIONAL_MODULES: Tuple[str, ...] = (
    "engine.ai_detail",
    "engine.world_model",
)

# Allow-list for WORLD_MODEL_CAPABILITY values — ADR-0005 §"Convention de code".
_ALLOWED_CAPABILITIES = frozenset({
    "paper-L1 Predictor",
    "paper-L2 Simulator",
    "paper-L3 Evolver",
    "paper-L2 Simulator → paper-L3 Evolver",  # trajectory-of-feature variant
    "n/a",
})


def _probe(dotted: str) -> Dict[str, str]:
    """Import a module and read its two taxonomy constants.

    Returns a row suitable for the API table. ``status`` carries the load
    outcome so the linter and the dashboard can react accordingly.
    """
    row: Dict[str, str] = {
        "module": dotted,
        "pipeline_layer": "",
        "world_model_capability": "",
        "status": "ok",
        "error": "",
    }
    try:
        mod = importlib.import_module(dotted)
    except Exception as exc:  # missing R&D module is fine for OPTIONAL list
        row["status"] = "missing"
        row["error"] = f"{type(exc).__name__}: {exc}"
        return row

    pipeline = getattr(mod, "PIPELINE_LAYER", None)
    capability = getattr(mod, "WORLD_MODEL_CAPABILITY", None)

    if pipeline is None or capability is None:
        row["status"] = "untagged"
        row["error"] = "missing PIPELINE_LAYER or WORLD_MODEL_CAPABILITY"
        return row

    row["pipeline_layer"] = str(pipeline)
    row["world_model_capability"] = str(capability)

    if capability not in _ALLOWED_CAPABILITIES:
        row["status"] = "invalid_capability"
        row["error"] = (
            f"WORLD_MODEL_CAPABILITY={capability!r} not in ADR-0005 allow-list"
        )

    return row


def world_model_capabilities() -> Dict[str, object]:
    """Aggregate the taxonomy table for the API endpoint.

    Shape::

        {
          "axes": {
            "pipeline":   "Genesis L1-L5 — pipeline d'origine d'état du monde",
            "capability": "arxiv 2604.22748 — capacité prédictive offerte à un agent",
          },
          "modules": [
            {"module": "engine.earth_loader",
             "pipeline_layer": "Genesis-L1 Earth-Seed",
             "world_model_capability": "paper-L1 Predictor",
             "status": "ok", "error": ""},
            ...
          ],
          "summary": {
            "tagged": 3, "missing": 2, "untagged": 0, "invalid": 0,
          },
        }
    """
    rows: List[Dict[str, str]] = []
    for dotted in _REQUIRED_MODULES + _OPTIONAL_MODULES:
        rows.append(_probe(dotted))

    summary = {"tagged": 0, "missing": 0, "untagged": 0, "invalid": 0}
    for r in rows:
        st = r["status"]
        if st == "ok":
            summary["tagged"] += 1
        elif st == "missing":
            summary["missing"] += 1
        elif st == "untagged":
            summary["untagged"] += 1
        elif st == "invalid_capability":
            summary["invalid"] += 1

    return {
        "axes": {
            "pipeline":
                "Genesis L1-L5 — pipeline d'origine d'état du monde",
            "capability":
                "arxiv 2604.22748 — capacité prédictive offerte à un agent",
        },
        "modules": rows,
        "summary": summary,
        "adr": "0005",
    }


def audit_modules(strict: bool = False) -> Tuple[Dict[str, object], List[str]]:
    """CI hook — returns the table and the list of modules that fail policy.

    Policy: every name in ``_REQUIRED_MODULES`` MUST load AND publish both
    taxonomy constants AND use an allow-listed capability value. R&D
    modules in ``_OPTIONAL_MODULES`` may be absent without failing.

    Parameters
    ----------
    strict
        If ``True``, optional modules that *exist* but are missing tags
        are also reported as failures. Default ``False`` so R&D placeholders
        don't gate the build.

    Returns
    -------
    (table, failures)
        ``table`` is the same dict as ``world_model_capabilities()``.
        ``failures`` is a list of human-readable failure lines, empty on
        success.
    """
    table = world_model_capabilities()
    failures: List[str] = []
    for row in table["modules"]:  # type: ignore[index]
        name = row["module"]
        st = row["status"]
        required = name in _REQUIRED_MODULES
        if required and st != "ok":
            failures.append(f"REQUIRED {name}: {st} — {row['error']}")
            continue
        if strict and st in {"untagged", "invalid_capability"}:
            failures.append(f"OPTIONAL {name}: {st} — {row['error']}")
    return table, failures


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "world_model_capabilities",
    "audit_modules",
]
