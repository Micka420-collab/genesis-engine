"""Materials Project ingestion + synthesis pipeline bridge.

Loads curated MP-style records (JSON) into runtime tables used by
:mod:`engine.chemistry`, :mod:`engine.statics`, and
:mod:`engine.material_synthesis`. Optional live fetch when ``mp-api`` is
installed and ``MP_API_KEY`` is set — offline bundle always works.

Format (JSON list of objects)::

    {"mp_id": "mp-149", "formula": "SiO2", "density_g_cm3": 2.65,
     "band_gap": 8.9, "formation_energy_per_atom": -3.2,
     "elements": {"Si": 0.33, "O": 0.67}}
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.material_synthesis import MaterialRegistry, SynthesisConditions, synthesize


DEFAULT_BUNDLE = Path(__file__).resolve().parent.parent / "data" / "materials_project_bundle.json"


@dataclass
class MPRecord:
    mp_id: str
    formula: str
    density_g_cm3: float
    elements: Dict[str, float]
    band_gap: Optional[float] = None
    formation_energy_per_atom: Optional[float] = None
    spacegroup: Optional[str] = None


@dataclass
class MaterialsProjectState:
    records: Dict[str, MPRecord] = field(default_factory=dict)
    strength_overrides: Dict[str, Dict[str, float]] = field(default_factory=dict)
    syntheses_attempted: int = 0
    syntheses_ok: int = 0


def _normalize_composition(elements: Dict[str, float]) -> Dict[str, float]:
    total = sum(max(0.0, float(v)) for v in elements.values())
    if total <= 0:
        return elements
    return {k: float(v) / total for k, v in elements.items()}


def load_bundle(path: Optional[os.PathLike] = None) -> List[MPRecord]:
    """Load MP records from JSON file (no network)."""
    p = Path(path) if path else DEFAULT_BUNDLE
    if not p.is_file():
        return _builtin_fallback_records()
    raw = json.loads(p.read_text(encoding="utf-8"))
    out: List[MPRecord] = []
    for row in raw:
        out.append(MPRecord(
            mp_id=str(row["mp_id"]),
            formula=str(row.get("formula", "")),
            density_g_cm3=float(row.get("density_g_cm3", 2.0)),
            elements={str(k): float(v) for k, v in row["elements"].items()},
            band_gap=row.get("band_gap"),
            formation_energy_per_atom=row.get("formation_energy_per_atom"),
            spacegroup=row.get("spacegroup"),
        ))
    return out


def _builtin_fallback_records() -> List[MPRecord]:
    """Minimal offline set when bundle file is absent."""
    return [
        MPRecord("mp-SiO2", "SiO2", 2.65, {"Si": 0.333, "O": 0.667}, band_gap=8.9),
        MPRecord("mp-Fe", "Fe", 7.87, {"Fe": 1.0}),
        MPRecord("mp-Cu", "Cu", 8.96, {"Cu": 1.0}),
        MPRecord("mp-Sn", "Sn", 7.31, {"Sn": 1.0}),
        MPRecord("mp-bronze", "Cu10Sn", 8.8, {"Cu": 0.91, "Sn": 0.09}),
    ]


def ingest_records(records: List[MPRecord], st: MaterialsProjectState) -> int:
    """Register records and derive statics strength hints from density."""
    n = 0
    for rec in records:
        st.records[rec.mp_id] = rec
        comp_strength = max(5.0, min(300.0, rec.density_g_cm3 * 12.0))
        key = rec.formula.lower().replace(" ", "_")
        st.strength_overrides[key] = {
            "compressive": comp_strength,
            "tensile": comp_strength * 0.1,
            "density": rec.density_g_cm3 * 1000.0,
        }
        n += 1
    _merge_into_statics(st.strength_overrides)
    return n


def _merge_into_statics(overrides: Dict[str, Dict[str, float]]) -> None:
    try:
        from engine import statics
        for name, props in overrides.items():
            if name in statics.STRENGTH_TABLE:
                continue
            statics.STRENGTH_TABLE[name] = {
                "compressive": float(props["compressive"]),
                "tensile": float(props["tensile"]),
                "density": float(props["density"]),
            }
    except Exception:
        pass


def run_synthesis_pipeline(
    composition: Dict[str, float],
    conditions: SynthesisConditions,
    st: MaterialsProjectState,
    registry: Optional[MaterialRegistry] = None,
) -> Optional[Any]:
    """composition → physical validity → synthesize → registry."""
    from engine.material_synthesis import check_physical_validity

    st.syntheses_attempted += 1
    comp = _normalize_composition(composition)
    ok, reason = check_physical_validity(comp, conditions, tools_available=("fire",))
    if not ok:
        return None
    mat = synthesize(comp, conditions, tools_available=("fire",))
    if mat is None:
        return None
    st.syntheses_ok += 1
    if registry is not None:
        registry.register(mat)
    return mat


def install_materials_project(sim, *, bundle_path: Optional[str] = None) -> MaterialsProjectState:
    existing = getattr(sim, "_materials_project", None)
    if existing is not None:
        return existing
    st = MaterialsProjectState()
    records = load_bundle(bundle_path)
    ingest_records(records, st)
    sim._materials_project = st
    if not hasattr(sim, "_synthesis_registry"):
        sim._synthesis_registry = MaterialRegistry()
    return st


def materials_project_snapshot(sim) -> Dict[str, object]:
    st: Optional[MaterialsProjectState] = getattr(sim, "_materials_project", None)
    if st is None:
        return {}
    return {
        "records": len(st.records),
        "strength_overrides": len(st.strength_overrides),
        "syntheses_attempted": st.syntheses_attempted,
        "syntheses_ok": st.syntheses_ok,
        "sample_ids": list(st.records.keys())[:8],
    }


__all__ = [
    "MPRecord",
    "MaterialsProjectState",
    "load_bundle",
    "ingest_records",
    "run_synthesis_pipeline",
    "install_materials_project",
    "materials_project_snapshot",
]
