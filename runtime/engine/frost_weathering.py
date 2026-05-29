"""Genesis Engine — Wave 50 frost weathering (cryoclastie) observer.

Read-only quantification of the **emergent frost weathering field** produced
by the macro climate + topography fields already present in
:mod:`engine.world_genesis` (``temp_c``, ``precip_mm``, ``elevation_m``,
``biome``). Pure NumPy, no RNG, no mutation, no scripting.

Physical basis — Walder & Hallet (1985), Hales & Roering (2007)
---------------------------------------------------------------

Frost weathering (cryoclastie, frost cracking, freeze-thaw shattering) is
the dominant mechanism eroding bedrock at high latitude / high altitude.
Two physical conditions are necessary:

1. **Frost cracking window** — temperature must sit in the band that
   allows ice segregation lenses to grow inside rock micro-cracks. Below
   ~ -15 °C water no longer migrates through the porous network; above
   0 °C no ice forms. The classical window is **-8 °C to -3 °C** with a
   peak around -5.5 °C (Walder & Hallet 1985 ; Anderson 1998).

2. **Liquid water availability** — without unfrozen water flowing into
   the cracking band, there is nothing to freeze. Annual precipitation
   is the cheapest available proxy at macro scale.

Two further field-grade modulators are observable on the world:

3. **Slope** — steep ground exposes more bedrock per unit area, evacuates
   debris faster (no soil cover insulating the rock), and concentrates
   talus production at the toe.

4. **Altitude / biome** — high elevation + cryo biomes (ICE, TUNDRA,
   COLD_DESERT, BOREAL_FOREST) amplify the field; warm biomes attenuate.

Output fields (per cell, dimensionless 0..1)
--------------------------------------------

- ``fci`` — *Frost Cracking Index* combining the window × moisture ×
  biome amplitude factors. ``fci > 0.4`` ≈ active periglacial domain.
- ``slope_deg`` — local D8-aligned slope (degrees).
- ``talus_risk`` — composite mask ``(fci ≥ 0.4) ∧ (slope_deg ≥ 25)``
  ∧ land. This is where rockfalls and scree cones emerge naturally on
  cold mountainsides — agents standing here will eventually observe
  loose rock and discover the link "cold + steep ⇒ tool stone underfoot".
- ``permafrost`` — ``temp_c ≤ -2 °C`` ∧ land. Continuous-permafrost
  proxy (UNEP / Brown et al. 1997 threshold).
- ``alpine_active`` — ``elevation ≥ 1500 m`` ∧ ``fci ≥ 0.2`` ∧ land.

Observer contract (mirrors Waves 39 / 40 / 45 / 49)
---------------------------------------------------

- ``FrostConfig`` / ``FrostSnapshot`` / ``FrostHistory`` /
  ``FrostState`` dataclasses, all frozen except history container.
- ``observe_frost_weathering(sim, cfg)`` — **read-only**, returns a
  snapshot.
- ``install_frost_weathering_observer(sim, cfg)`` — idempotent, wraps
  ``sim.step`` so a snapshot is captured every ``snapshot_every`` ticks.
- ``uninstall_frost_weathering_observer(sim)`` — restores the original
  ``sim.step``.
- ``frost_weathering_summary(sim)`` — diagnostic dict for dashboards.

Determinism
-----------

No RNG. The signature is ``sha256`` of a canonical tuple built from
rounded global metrics + the integer biome histogram, so two runs with
the same world seed produce identical snapshots.

Stone-age compliance
--------------------

The observer never *creates* frost activity. It only reads what the
emergent temperature + precipitation + elevation fields already encode.
No script biases any cell. Talus zones emerge wherever cold meets steep
ground — exactly as on Earth.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FrostConfig:
    """Read-only knobs for the cryoclastie observer.

    The defaults are calibrated against the classical Walder & Hallet
    cracking window (-8 .. -3 °C, peak -5.5 °C, σ = 2.5 °C) and a
    1500 mm/yr precipitation saturation point typical of montane belts.
    """
    snapshot_every: int = 64
    # Frost cracking window (°C). Outside, fci → 0.
    window_peak_c: float = -5.5
    window_sigma_c: float = 2.5
    too_cold_floor_c: float = -15.0
    too_warm_ceiling_c: float = 0.0
    # Precipitation saturation (mm/yr).
    moisture_saturation_mm: float = 1500.0
    # Thresholds for emergent zones.
    talus_slope_deg: float = 25.0
    talus_fci_min: float = 0.4
    permafrost_temp_c: float = -2.0
    alpine_elev_m: float = 1500.0
    alpine_fci_min: float = 0.2
    # Top-K biomes reported in the snapshot.
    top_biomes: int = 5


@dataclass(frozen=True)
class BiomeFrostStats:
    """Per-biome aggregate frost statistics (read-only)."""
    biome_id: int
    n_cells: int
    mean_fci: float
    max_fci: float
    permafrost_fraction: float
    talus_fraction: float


@dataclass(frozen=True)
class FrostSnapshot:
    """Global + per-biome snapshot at a given sim tick."""
    tick: int
    map_area_km2: float
    cell_km: float
    land_cells: int
    land_area_km2: float
    # Frost cracking field.
    mean_fci_land: float
    max_fci: float
    fci_active_fraction: float        # land cells with fci ≥ 0.1
    fci_strong_fraction: float        # land cells with fci ≥ 0.4
    # Emergent zones.
    permafrost_cells: int
    permafrost_area_km2: float
    permafrost_fraction: float
    talus_cells: int
    talus_area_km2: float
    alpine_cells: int
    alpine_area_km2: float
    # Slope diagnostics.
    mean_slope_deg_land: float
    max_slope_deg: float
    # Per-biome breakdown.
    biomes_top: Tuple[BiomeFrostStats, ...]
    signature: str


@dataclass
class FrostHistory:
    snapshots: List[FrostSnapshot] = field(default_factory=list)


@dataclass
class FrostState:
    config: FrostConfig
    history: FrostHistory = field(default_factory=FrostHistory)
    wrapped: bool = False


# ---------------------------------------------------------------------------
# World access (read-only)
# ---------------------------------------------------------------------------

def _resolve_world(sim) -> Optional[Any]:
    """Locate the :class:`GenesisWorld` attached to ``sim`` (mirrors
    :mod:`engine.watershed_observer`)."""
    ch = getattr(sim, "_chunk_hydrology_state", None)
    if ch is not None and getattr(ch, "anchor", None) is not None:
        w = getattr(ch.anchor, "world", None)
        if w is not None:
            return w
    boot = getattr(sim, "_genesis_bootstrap_state", None)
    if boot is not None:
        w = getattr(boot, "world", None)
        if w is not None:
            return w
        a = getattr(boot, "anchor", None)
        if a is not None and getattr(a, "world", None) is not None:
            return a.world
    streamer = getattr(sim, "streamer", None)
    if streamer is not None:
        genesis = getattr(streamer, "genesis", None)
        if genesis is not None and getattr(genesis, "world", None) is not None:
            return genesis.world
    anchor = getattr(sim, "_genesis_anchor", None)
    if anchor is not None and getattr(anchor, "world", None) is not None:
        return anchor.world
    return getattr(sim, "_genesis_world", None)


# ---------------------------------------------------------------------------
# Pure-function physics
# ---------------------------------------------------------------------------

def compute_slope_field(elevation_m: np.ndarray,
                         cell_km: float) -> np.ndarray:
    """Local slope (degrees) from the elevation field.

    Uses a central-difference gradient (Horn 1981 / Sobel-1) on the
    macro grid. The slope is the angle between the surface and the
    horizontal: ``slope_deg = arctan(|grad_z| / cell_size_m) × 180/π``.

    Parameters
    ----------
    elevation_m
        ``(R, R)`` float32 cell elevation in metres.
    cell_km
        Cell width in kilometres (``world.params.map_size_km / R``).

    Returns
    -------
    slope_deg : ndarray
        ``(R, R)`` float32 in [0, 90].
    """
    if elevation_m.ndim != 2:
        raise ValueError("elevation_m must be a 2-D array")
    cell_m = float(cell_km) * 1000.0
    if cell_m <= 0.0:
        raise ValueError("cell_km must be strictly positive")
    # np.gradient yields (dz/dy, dz/dx) — both per index unit.
    dzdy, dzdx = np.gradient(elevation_m.astype(np.float32))
    # Convert per-index gradient to per-metre gradient.
    grad_mag = np.sqrt(dzdy * dzdy + dzdx * dzdx) / cell_m
    return np.degrees(np.arctan(grad_mag)).astype(np.float32)


def frost_cracking_window(temp_c: np.ndarray,
                            *,
                            peak_c: float = -5.5,
                            sigma_c: float = 2.5,
                            too_cold_floor_c: float = -15.0,
                            too_warm_ceiling_c: float = 0.0) -> np.ndarray:
    """Walder & Hallet (1985) frost cracking weight per cell.

    Returns a 0..1 weight peaking at ``peak_c`` (gaussian, σ = ``sigma_c``)
    and clamped to zero outside ``[too_cold_floor_c, too_warm_ceiling_c]``.

    The bounded support reproduces the bench observation that ice-lens
    growth requires both unfrozen film water (which vanishes below
    ~ -15 °C) and net freezing (which vanishes above 0 °C).
    """
    t = np.asarray(temp_c, dtype=np.float32)
    w = np.exp(-0.5 * ((t - float(peak_c)) / float(sigma_c)) ** 2)
    w = np.where(t > float(too_warm_ceiling_c), 0.0, w)
    w = np.where(t < float(too_cold_floor_c), 0.0, w)
    return w.astype(np.float32)


def compute_frost_cracking_index(temp_c: np.ndarray,
                                   precip_mm: np.ndarray,
                                   biome: Optional[np.ndarray] = None,
                                   *,
                                   peak_c: float = -5.5,
                                   sigma_c: float = 2.5,
                                   too_cold_floor_c: float = -15.0,
                                   too_warm_ceiling_c: float = 0.0,
                                   moisture_saturation_mm: float = 1500.0,
                                   ) -> np.ndarray:
    """Composite **Frost Cracking Index** (FCI) in [0, 1] per cell.

    ``FCI = window(T) × moisture(P) × biome_amplitude(B)``

    - ``window`` from :func:`frost_cracking_window` (gaussian on T).
    - ``moisture = clip(P / moisture_saturation_mm, 0, 1)`` — linear
      saturation at the prescribed annual precipitation.
    - ``biome_amplitude`` is identity when ``biome`` is ``None``; otherwise
      it multiplies by a factor reflecting how exposed bedrock is in
      each biome (high for ICE/TUNDRA, low for TROPICAL_RAINFOREST).
    """
    win = frost_cracking_window(
        temp_c,
        peak_c=peak_c, sigma_c=sigma_c,
        too_cold_floor_c=too_cold_floor_c,
        too_warm_ceiling_c=too_warm_ceiling_c,
    )
    p = np.asarray(precip_mm, dtype=np.float32)
    moisture = np.clip(p / max(float(moisture_saturation_mm), 1.0), 0.0, 1.0)
    fci = win * moisture
    if biome is not None:
        amp = biome_amplitude_field(biome)
        fci = fci * amp
    return np.clip(fci, 0.0, 1.0).astype(np.float32)


# Biome ↔ amplitude table. Cryo-dominant biomes amplify the field, warm
# biomes attenuate it because of soil + canopy insulation. Numerical
# values are dimensionless modulators chosen to keep the global field in
# [0, 1] when the temperature window is saturated.
#
# Biome enum (engine.world.Biome) :
#   OCEAN=0, ICE=1, TUNDRA=2, BOREAL_FOREST=3, TEMPERATE_FOREST=4,
#   TEMPERATE_RAINFOREST=5, GRASSLAND=6, HOT_DESERT=7, COLD_DESERT=8,
#   SAVANNA=9, TROPICAL_DRY_FOREST=10, TROPICAL_RAINFOREST=11
_BIOME_AMPLITUDE: Dict[int, float] = {
    0: 0.0,    # OCEAN — frost weathering on submerged bedrock is irrelevant
    1: 1.00,   # ICE — fully exposed, every cycle counts
    2: 1.00,   # TUNDRA — periglacial archetype
    3: 0.85,   # BOREAL_FOREST — partial canopy + frequent cycles
    4: 0.55,   # TEMPERATE_FOREST — canopy insulates, fewer cycles
    5: 0.45,   # TEMPERATE_RAINFOREST — wet but mild
    6: 0.70,   # GRASSLAND — exposed in winter
    7: 0.20,   # HOT_DESERT — diurnal cycles only, dry
    8: 0.95,   # COLD_DESERT — frequent freeze-thaw, dry
    9: 0.30,   # SAVANNA — rarely freezes
    10: 0.20,  # TROPICAL_DRY_FOREST — no freeze
    11: 0.10,  # TROPICAL_RAINFOREST — no freeze
}


def biome_amplitude_field(biome: np.ndarray) -> np.ndarray:
    """Lookup table mapping each biome cell to its amplitude factor."""
    b = np.asarray(biome, dtype=np.int32)
    out = np.zeros(b.shape, dtype=np.float32)
    for biome_id, amp in _BIOME_AMPLITUDE.items():
        out = np.where(b == biome_id, np.float32(amp), out)
    return out


def compute_talus_mask(slope_deg: np.ndarray,
                        fci: np.ndarray,
                        land_mask: np.ndarray,
                        *,
                        slope_threshold: float = 25.0,
                        fci_threshold: float = 0.4) -> np.ndarray:
    """Talus / scree zones: steep land with active frost weathering."""
    s = np.asarray(slope_deg, dtype=np.float32) >= float(slope_threshold)
    f = np.asarray(fci, dtype=np.float32) >= float(fci_threshold)
    return (s & f & np.asarray(land_mask, dtype=bool))


def compute_permafrost_mask(temp_c: np.ndarray,
                              land_mask: np.ndarray,
                              *,
                              temp_threshold: float = -2.0) -> np.ndarray:
    """Continuous-permafrost proxy: mean annual T ≤ threshold on land."""
    return (np.asarray(temp_c, dtype=np.float32) <= float(temp_threshold)
            ) & np.asarray(land_mask, dtype=bool)


def compute_alpine_active_mask(elevation_m: np.ndarray,
                                 fci: np.ndarray,
                                 land_mask: np.ndarray,
                                 *,
                                 elev_threshold: float = 1500.0,
                                 fci_threshold: float = 0.2) -> np.ndarray:
    """High-altitude active periglacial belt."""
    e = np.asarray(elevation_m, dtype=np.float32) >= float(elev_threshold)
    f = np.asarray(fci, dtype=np.float32) >= float(fci_threshold)
    return e & f & np.asarray(land_mask, dtype=bool)


# ---------------------------------------------------------------------------
# Per-biome stats
# ---------------------------------------------------------------------------

def _biome_breakdown(biome: np.ndarray,
                      fci: np.ndarray,
                      permafrost: np.ndarray,
                      talus: np.ndarray,
                      land_mask: np.ndarray,
                      top_biomes: int) -> Tuple[BiomeFrostStats, ...]:
    """Compute per-biome stats and return the top-K by cell count."""
    b_land = biome[land_mask]
    if b_land.size == 0:
        return tuple()
    fci_land = fci[land_mask]
    pf_land = permafrost[land_mask]
    talus_land = talus[land_mask]
    out: List[BiomeFrostStats] = []
    for biome_id in sorted(np.unique(b_land).tolist()):
        sel = (b_land == biome_id)
        n = int(sel.sum())
        if n == 0:
            continue
        out.append(BiomeFrostStats(
            biome_id=int(biome_id),
            n_cells=n,
            mean_fci=float(fci_land[sel].mean()),
            max_fci=float(fci_land[sel].max()),
            permafrost_fraction=float(pf_land[sel].sum()) / float(n),
            talus_fraction=float(talus_land[sel].sum()) / float(n),
        ))
    out.sort(key=lambda x: (-x.n_cells, x.biome_id))
    return tuple(out[:max(int(top_biomes), 0)])


# ---------------------------------------------------------------------------
# Snapshot / signature
# ---------------------------------------------------------------------------

def _snapshot_signature(seed: Tuple[Any, ...]) -> str:
    canonical = repr(seed).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def observe_frost_weathering(sim, config: Optional[FrostConfig] = None
                              ) -> Optional[FrostSnapshot]:
    """Pure read-only snapshot of the frost weathering field.

    Returns ``None`` if no :class:`GenesisWorld` is wired to ``sim``.
    """
    cfg = config if config is not None else FrostConfig()
    world = _resolve_world(sim)
    if world is None:
        return None

    elevation = np.asarray(world.elevation_m, dtype=np.float32)
    temp_c = np.asarray(world.temp_c, dtype=np.float32)
    precip_mm = np.asarray(world.precip_mm, dtype=np.float32)
    biome = np.asarray(world.biome, dtype=np.int32)
    R = int(elevation.shape[0])
    cell_km = float(world.params.map_size_km) / float(R)
    map_area_km2 = float(R * R) * cell_km * cell_km
    sea_level = float(getattr(world.params, "sea_level_m", 0.0))

    land_mask = (elevation > sea_level)
    land_cells = int(land_mask.sum())
    land_area_km2 = float(land_cells) * cell_km * cell_km

    slope_deg = compute_slope_field(elevation, cell_km)
    fci = compute_frost_cracking_index(
        temp_c, precip_mm, biome,
        peak_c=cfg.window_peak_c, sigma_c=cfg.window_sigma_c,
        too_cold_floor_c=cfg.too_cold_floor_c,
        too_warm_ceiling_c=cfg.too_warm_ceiling_c,
        moisture_saturation_mm=cfg.moisture_saturation_mm,
    )

    permafrost = compute_permafrost_mask(
        temp_c, land_mask, temp_threshold=cfg.permafrost_temp_c)
    talus = compute_talus_mask(
        slope_deg, fci, land_mask,
        slope_threshold=cfg.talus_slope_deg,
        fci_threshold=cfg.talus_fci_min,
    )
    alpine = compute_alpine_active_mask(
        elevation, fci, land_mask,
        elev_threshold=cfg.alpine_elev_m,
        fci_threshold=cfg.alpine_fci_min,
    )

    if land_cells > 0:
        mean_fci_land = float(fci[land_mask].mean())
        max_fci = float(fci[land_mask].max())
        fci_active_fraction = float((fci[land_mask] >= 0.1).sum()) / land_cells
        fci_strong_fraction = float((fci[land_mask] >= cfg.talus_fci_min).sum()
                                     ) / land_cells
        mean_slope_deg_land = float(slope_deg[land_mask].mean())
        max_slope_deg = float(slope_deg[land_mask].max())
    else:
        mean_fci_land = 0.0
        max_fci = 0.0
        fci_active_fraction = 0.0
        fci_strong_fraction = 0.0
        mean_slope_deg_land = 0.0
        max_slope_deg = 0.0

    permafrost_cells = int(permafrost.sum())
    permafrost_area_km2 = float(permafrost_cells) * cell_km * cell_km
    permafrost_fraction = (float(permafrost_cells) / land_cells
                            if land_cells > 0 else 0.0)

    talus_cells = int(talus.sum())
    talus_area_km2 = float(talus_cells) * cell_km * cell_km
    alpine_cells = int(alpine.sum())
    alpine_area_km2 = float(alpine_cells) * cell_km * cell_km

    biomes_top = _biome_breakdown(
        biome, fci, permafrost, talus, land_mask, cfg.top_biomes)

    # Canonical signature material: rounded global metrics + sorted biome
    # tuple. Dict iteration is therefore never visible.
    canonical_biomes = tuple(
        (b.biome_id, b.n_cells,
         round(b.mean_fci, 6), round(b.max_fci, 6),
         round(b.permafrost_fraction, 6), round(b.talus_fraction, 6))
        for b in sorted(biomes_top, key=lambda x: x.biome_id)
    )
    sig = _snapshot_signature((
        int(sim.tick), R, round(map_area_km2, 4), round(cell_km, 6),
        land_cells,
        round(mean_fci_land, 6), round(max_fci, 6),
        round(fci_active_fraction, 6), round(fci_strong_fraction, 6),
        permafrost_cells, talus_cells, alpine_cells,
        round(mean_slope_deg_land, 4), round(max_slope_deg, 4),
        canonical_biomes,
    ))

    return FrostSnapshot(
        tick=int(sim.tick),
        map_area_km2=map_area_km2,
        cell_km=cell_km,
        land_cells=land_cells,
        land_area_km2=land_area_km2,
        mean_fci_land=mean_fci_land,
        max_fci=max_fci,
        fci_active_fraction=fci_active_fraction,
        fci_strong_fraction=fci_strong_fraction,
        permafrost_cells=permafrost_cells,
        permafrost_area_km2=permafrost_area_km2,
        permafrost_fraction=permafrost_fraction,
        talus_cells=talus_cells,
        talus_area_km2=talus_area_km2,
        alpine_cells=alpine_cells,
        alpine_area_km2=alpine_area_km2,
        mean_slope_deg_land=mean_slope_deg_land,
        max_slope_deg=max_slope_deg,
        biomes_top=biomes_top,
        signature=sig,
    )


# ---------------------------------------------------------------------------
# Install / uninstall (mirrors Waves 39 / 40 / 45 / 49)
# ---------------------------------------------------------------------------

def install_frost_weathering_observer(sim,
                                        config: Optional[FrostConfig] = None
                                        ) -> FrostState:
    """Idempotent installer. Wraps ``sim.step`` once to capture snapshots
    every ``cfg.snapshot_every`` ticks."""
    cfg = config if config is not None else FrostConfig()
    existing: Optional[FrostState] = getattr(sim, "_frost_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = FrostState(config=cfg)
    original_step = sim.step

    def wrapped_step(*args, **kwargs):  # type: ignore[no-untyped-def]
        result = original_step(*args, **kwargs)
        try:
            tick_now = int(sim.tick)
            if cfg.snapshot_every > 0 and tick_now % cfg.snapshot_every == 0:
                snap = observe_frost_weathering(sim, cfg)
                if snap is not None:
                    state.history.snapshots.append(snap)
        except Exception:
            # Observer must NEVER break the sim. Swallow + continue.
            pass
        return result

    sim.step = wrapped_step  # type: ignore[assignment]
    state.wrapped = True
    sim._frost_state = state  # type: ignore[attr-defined]
    sim._frost_original_step = original_step  # type: ignore[attr-defined]
    sim._frost_wrapped = True  # type: ignore[attr-defined]
    return state


def uninstall_frost_weathering_observer(sim) -> bool:
    """Restore the original ``sim.step``. Returns ``True`` on success."""
    state: Optional[FrostState] = getattr(sim, "_frost_state", None)
    original = getattr(sim, "_frost_original_step", None)
    if state is None or original is None:
        return False
    sim.step = original  # type: ignore[assignment]
    try:
        delattr(sim, "_frost_state")
    except AttributeError:
        pass
    try:
        delattr(sim, "_frost_original_step")
    except AttributeError:
        pass
    try:
        delattr(sim, "_frost_wrapped")
    except AttributeError:
        pass
    return True


def frost_weathering_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards / smokes."""
    state: Optional[FrostState] = getattr(sim, "_frost_state", None)
    if state is None:
        return {"installed": False}
    last: Optional[FrostSnapshot] = (state.history.snapshots[-1]
                                       if state.history.snapshots else None)
    return {
        "installed": True,
        "snapshot_every": state.config.snapshot_every,
        "n_snapshots": len(state.history.snapshots),
        "last_tick": last.tick if last is not None else None,
        "last_signature": last.signature if last is not None else None,
        "last_mean_fci": (round(last.mean_fci_land, 6)
                            if last is not None else None),
        "last_permafrost_fraction": (round(last.permafrost_fraction, 6)
                                       if last is not None else None),
        "last_talus_cells": (last.talus_cells if last is not None else None),
        "last_alpine_cells": (last.alpine_cells if last is not None else None),
    }


__all__ = [
    "FrostConfig", "BiomeFrostStats", "FrostSnapshot",
    "FrostHistory", "FrostState",
    "compute_slope_field",
    "frost_cracking_window",
    "compute_frost_cracking_index",
    "biome_amplitude_field",
    "compute_talus_mask",
    "compute_permafrost_mask",
    "compute_alpine_active_mask",
    "observe_frost_weathering",
    "install_frost_weathering_observer",
    "uninstall_frost_weathering_observer",
    "frost_weathering_summary",
]
