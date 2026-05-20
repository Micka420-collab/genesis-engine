"""Köppen–Geiger classification on Genesis macro grids + FAIR metrics.

Bridges :class:`engine.world_genesis.GenesisWorld` ``temp_c`` / ``precip_mm``
to the harness thresholds (mirrors ``native/.../biome/src/koeppen.rs``).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

PIPELINE_LAYER = "Genesis-L2 Climate"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"

# Reference climates (same as p74 / Rust harness).
REFERENCE_CLIMATES: Tuple[Tuple[str, float, float, float, str], ...] = (
    ("Singapore", 27.0, 26.0, 2600.0, "Af"),
    ("Sahara", 22.0, 12.0, 50.0, "BWh"),
    ("London", 11.0, 5.0, 600.0, "Cfb"),
    ("Moscow", 5.0, -10.0, 700.0, "Dfb"),
    ("Fairbanks", -3.0, -25.0, 300.0, "Dfc"),
    ("Greenland", -20.0, -30.0, 200.0, "EF"),
)

# Köppen class → coarse Genesis biome id expectation (for coherence metric).
_KOEPPEN_TO_BIOME_HINT: Dict[str, Tuple[int, ...]] = {
    "Af": (9,), "Am": (9,), "Aw": (10,),
    "BWh": (6,), "BWk": (7,), "BSh": (10,), "BSk": (7,),
    "Cfa": (4, 5), "Cfb": (4,), "Csa": (10,), "Csb": (7,),
    "Dfa": (3, 4), "Dfb": (3,), "Dfc": (2, 3),
    "ET": (2,), "EF": (1,),
}


def _p_thresh(t_annual: float) -> float:
    return 20.0 * t_annual + 280.0 if t_annual >= 0 else 20.0 * t_annual


def classify_koeppen(temp_annual_c: float, temp_coldest_c: float,
                     precip_mm: float) -> str:
    """Classify one climate point (annual T, coldest-month T, annual precip)."""
    p = _p_thresh(temp_annual_c)
    p_winter = 0.25 * precip_mm
    if temp_annual_c < -6.0:
        return "EF" if temp_coldest_c < -12.0 else "ET"
    if precip_mm < p:
        semi = precip_mm > 0.5 * p
        if temp_annual_c >= 18.0:
            return "BSh" if semi else "BWh"
        return "BSk" if semi else "BWk"
    if temp_coldest_c >= 18.0:
        if precip_mm >= 2500:
            return "Af"
        if p_winter < 60:
            return "Am"
        return "Aw"
    if temp_coldest_c < -3.0:
        if temp_annual_c >= 10.0:
            return "Dfa"
        if temp_annual_c >= 0.0:
            return "Dfb"
        return "Dfc"
    if p_winter > 3.0 * (precip_mm - p_winter):
        return "Csa" if temp_annual_c >= 22.0 else "Csb"
    if temp_annual_c >= 22.0 or (temp_coldest_c > 0.0 and precip_mm > 1000.0):
        return "Cfa"
    return "Cfb"


def estimate_coldest_month_c(temp_annual_c: np.ndarray,
                              latitude_deg: np.ndarray,
                              *,
                              seasonal_amp: float = 12.0) -> np.ndarray:
    """Heuristic coldest-month temperature from annual mean + latitude."""
    lat = np.abs(latitude_deg.astype(np.float32))
    amp = seasonal_amp * (0.35 + 0.65 * np.clip(lat / 90.0, 0.0, 1.0))
    return (temp_annual_c - amp).astype(np.float32)


def classify_koeppen_grid(temp_c: np.ndarray,
                           precip_mm: np.ndarray,
                           latitude_deg: np.ndarray,
                           *,
                           land_mask: Optional[np.ndarray] = None) -> np.ndarray:
    """Per-cell Köppen class codes as ``'<U3'`` string array."""
    tc = estimate_coldest_month_c(temp_c, latitude_deg)
    h, w = temp_c.shape
    out = np.empty((h, w), dtype="<U3")
    t_flat = temp_c.ravel()
    tc_flat = tc.ravel()
    p_flat = precip_mm.ravel()
    for i in range(t_flat.size):
        out.ravel()[i] = classify_koeppen(
            float(t_flat[i]), float(tc_flat[i]), float(p_flat[i]))
    if land_mask is not None:
        ocean = ~land_mask
        out[ocean] = ""
    return out


def harness_pass_rate() -> float:
    """Fraction of reference climates classified correctly."""
    ok = sum(
        1 for _name, ta, tc, p, exp in REFERENCE_CLIMATES
        if classify_koeppen(ta, tc, p) == exp
    )
    return ok / max(len(REFERENCE_CLIMATES), 1)


@dataclass
class KoeppenGridMetrics:
    harness_pass_rate: float
    grid_cells: int
    land_cells: int
    class_counts: Dict[str, int]
    biome_coherence_rate: float
    mean_temp_c: float
    mean_precip_mm: float
    fohn_orographic_boost: float


def _fohn_boost(world) -> float:
    """Mean windward/leeward precip ratio proxy (orographic realism)."""
    if not hasattr(world, "wind_u") or not hasattr(world, "precip_mm"):
        return 1.0
    p = world.precip_mm.astype(np.float64)
    wu = world.wind_u.astype(np.float64)
    # Windward: positive u wind + high precip vs leeward negative u.
    windward = p[wu > 0.5]
    leeward = p[wu < -0.5]
    if windward.size < 10 or leeward.size < 10:
        return 1.0
    return float(np.mean(windward) / max(np.mean(leeward), 1.0))


def koeppen_metrics_from_world(world) -> KoeppenGridMetrics:
    """Full-grid Köppen + coherence vs Genesis ``biome`` field."""
    elev = world.elevation_m
    land = elev > float(getattr(world.params, "sea_level_m", 0.0))
    kg = classify_koeppen_grid(
        world.temp_c, world.precip_mm, world.latitude_deg, land_mask=land)
    land_kg = kg[land]
    counts: Dict[str, int] = {}
    for c in np.unique(land_kg):
        if c:
            counts[str(c)] = int((land_kg == c).sum())
    biome = world.biome[land].astype(np.int32)
    coherent = 0
    total = int(land.sum())
    for i in range(total):
        k = str(land_kg.ravel()[i])
        hints = _KOEPPEN_TO_BIOME_HINT.get(k, ())
        if hints and int(biome.ravel()[i]) in hints:
            coherent += 1
    coherence = coherent / max(total, 1)
    return KoeppenGridMetrics(
        harness_pass_rate=harness_pass_rate(),
        grid_cells=int(kg.size),
        land_cells=total,
        class_counts=counts,
        biome_coherence_rate=float(coherence),
        mean_temp_c=float(world.temp_c[land].mean()) if total else 0.0,
        mean_precip_mm=float(world.precip_mm[land].mean()) if total else 0.0,
        fohn_orographic_boost=_fohn_boost(world),
    )


def grid_checksum_sha256(arr: np.ndarray) -> str:
    """Deterministic SHA-256 over raw array bytes (FAIR grid fingerprint)."""
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def grid_checksum_blake2b256(arr: np.ndarray) -> str:
    """BLAKE2b-256 digest (optional second fingerprint)."""
    return hashlib.blake2b(
        np.ascontiguousarray(arr).tobytes(), digest_size=32).hexdigest()


def _world_seed(world) -> int:
    if hasattr(world, "params") and hasattr(world.params, "seed"):
        return int(world.params.seed)
    return int(getattr(world, "seed", 0))


def fair_koeppen_manifest(world, *, seed: Optional[int] = None) -> Dict[str, Any]:
    """FAIR-friendly dict for scenario manifests (seed, checksums, kappa, UTC)."""
    m = koeppen_metrics_from_world(world)
    seed_val = int(seed if seed is not None else _world_seed(world))
    land = world.elevation_m > float(getattr(world.params, "sea_level_m", 0.0))
    kg = classify_koeppen_grid(
        world.temp_c, world.precip_mm, world.latitude_deg, land_mask=land)
    return {
        "schema": "genesis.koeppen.fair/v1",
        "seed": seed_val,
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "koeppen_harness_pass_rate": round(m.harness_pass_rate, 4),
        "koeppen_land_cells": m.land_cells,
        "koeppen_biome_coherence_rate": round(m.biome_coherence_rate, 4),
        "kappa_biome_coherence": round(m.biome_coherence_rate, 4),
        "koeppen_class_counts": m.class_counts,
        "koeppen_class_fractions": {
            k: round(v / max(m.land_cells, 1), 4)
            for k, v in m.class_counts.items()
        },
        "koeppen_mean_temp_c": round(m.mean_temp_c, 2),
        "koeppen_mean_precip_mm": round(m.mean_precip_mm, 1),
        "fohn_orographic_boost": round(m.fohn_orographic_boost, 3),
        "checksum_sha256": {
            "temp_c": grid_checksum_sha256(world.temp_c),
            "precip_mm": grid_checksum_sha256(world.precip_mm),
            "koeppen_grid": grid_checksum_sha256(
                kg.astype("S3") if kg.dtype.kind == "U" else kg),
            "biome": grid_checksum_sha256(world.biome),
        },
        "checksum_blake2b256": {
            "temp_c": grid_checksum_blake2b256(world.temp_c),
            "precip_mm": grid_checksum_blake2b256(world.precip_mm),
        },
    }


def export_fair_koeppen_manifest(world,
                                  path: Union[str, Path],
                                  *,
                                  seed: Optional[int] = None) -> Path:
    """Write :func:`fair_koeppen_manifest` JSON to ``path``."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = fair_koeppen_manifest(world, seed=seed)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


def koeppen_from_genesis_bootstrap(sim, *, synthetic_only: bool = False
                                   ) -> Optional[Dict[str, Any]]:
    """Köppen FAIR manifest from the sim's bootstrapped Genesis world.

    When ``synthetic_only`` is False (default), returns ``None`` only if
    bootstrap never ran — callers in the civilization pipeline should treat
    that as an error. Pass ``synthetic_only=True`` only in isolated unit
    smokes that deliberately skip ``bootstrap_genesis_sim``.
    """
    if synthetic_only:
        return None
    from engine.genesis_bootstrap import resolve_genesis_world
    world = resolve_genesis_world(sim, synthetic_only=False)
    seed = int(getattr(sim.cfg, "seed", _world_seed(world)))
    return fair_koeppen_manifest(world, seed=seed)


def export_fair_koeppen_from_sim(sim,
                                  path: Union[str, Path],
                                  *,
                                  synthetic_only: bool = False) -> Path:
    """Write FAIR Köppen JSON from ``sim``'s Genesis world (not a fake grid)."""
    from engine.genesis_bootstrap import resolve_genesis_world
    world = resolve_genesis_world(sim, synthetic_only=synthetic_only)
    return export_fair_koeppen_manifest(
        world, path, seed=int(sim.cfg.seed))


__all__ = [
    "REFERENCE_CLIMATES",
    "classify_koeppen",
    "classify_koeppen_grid",
    "estimate_coldest_month_c",
    "harness_pass_rate",
    "KoeppenGridMetrics",
    "koeppen_metrics_from_world",
    "fair_koeppen_manifest",
    "export_fair_koeppen_manifest",
    "grid_checksum_sha256",
    "grid_checksum_blake2b256",
    "koeppen_from_genesis_bootstrap",
    "export_fair_koeppen_from_sim",
]
