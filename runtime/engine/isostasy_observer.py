"""Genesis Engine - Wave 59 Airy isostasy / crustal-root observer.

Read-only solid-earth layer that closes the topography -> crustal root loop
of the geology stack. Where Wave 54 (compaction) squeezes a column by its
own weight and Wave 56 (geotherm + metamorphic facies) reads the
pressure-temperature path, this observer answers the complementary question a
geophysicist asks of the *same* emergent relief: why does the mountain stand
up at all? In Airy's model (Airy 1855; Heiskanen & Vening Meinesz 1958)
topography is supported by buoyancy - a light crust floating in a denser
mantle, with high ground compensated by a deep crustal *root* and ocean
basins by a mantle *anti-root*.

Nothing here is scripted. The observer reads the emergent elevation field
``world.elevation_m`` the tick has already produced (the same field the Wave
53 discharge and Wave 57 Exner observers route on) and overlays one law of
nature - hydrostatic (Archimedean) equilibrium of the lithosphere - exactly
as gravity already acts elsewhere in the engine. No hand-placed Moho.

Physics (Airy local compensation, SI internally, km reported)
-------------------------------------------------------------
Take sea level as the datum (z positive down). A reference continental column
has crustal thickness ``T0`` and floats with its surface at z = 0. A column
whose emergent surface elevation is ``h`` (m, positive up) must, to exert the
same lithostatic pressure at the depth of compensation, carry a crustal root::

    land  (h >= 0):  root r      =  rho_c / (rho_m - rho_c) * h
    ocean (h <  0):  anti-root a = (rho_c - rho_w) / (rho_m - rho_c) * |h|

so the crust-mantle boundary (Moho) sits at depth ``T0 + r`` under mountains
and ``T0 - a`` under basins: mountains have deep roots, oceans thin crust.
The crust top sits at z = -h in both regimes (mountain surface on land, sea
floor in oceans), so the crustal thickness is uniformly::

    H = Moho - (-h) = T0 + r + h

These roots are *derived*, not posted: they are the unique compensation that
equalises the column load at the reference compensation depth.

Falsifiable invariants (asserted by the smoke / tests)
------------------------------------------------------
1. Equal-pressure compensation. The lithostatic pressure integrated from each
   column's surface down to a common compensation depth ``D_c`` (deeper than
   any root) is identical for every cell - the Airy isostatic residual
   ``(P_max - P_min)/P_mean`` is zero to machine precision. This is the
   solid-earth analogue of the Wave 53/57 mass-closure residual.
2. Mountain roots. Crustal thickness is an increasing function of surface
   elevation: the highest cell has a thicker crust (deeper Moho) than the
   lowest. Falsified if the emergent relief is internally inconsistent.
3. Closed-form root law. The recovered land root equals
   ``rho_c/(rho_m - rho_c)*h`` to machine precision.

Observer contract (mirrors Waves 53 / 55 / 57)
----------------------------------------------
``IsostasyConfig`` / ``ColumnIsostasy`` / ``IsostasySnapshot`` /
``IsostasyHistory`` / ``IsostasyState`` dataclasses; pure helpers
``airy_root_m`` / ``crustal_thickness_m`` / ``compensation_pressure_pa``;
``observe_isostasy(sim, cfg)`` - read-only, ``None`` if no world wired;
idempotent ``install_isostasy_observer`` / ``uninstall_isostasy_observer``
(returns ``bool``); ``isostasy_summary`` diagnostic dict.

Determinism
-----------
No RNG. The signature is ``sha256`` of a canonical tuple of rounded aggregate
metrics, so two runs with the same world seed produce identical snapshot
streams.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

# Reuse Wave 53 world access verbatim (no duplication).
from engine.discharge_observer import _field, _resolve_world

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

GRAVITY = 9.81           # m s-2
CRUST_DENSITY = 2670.0   # kg m-3  (mean continental upper crust)
MANTLE_DENSITY = 3300.0  # kg m-3  (uppermost mantle / peridotite)
WATER_DENSITY = 1030.0   # kg m-3  (sea water)
_M_PER_KM = 1000.0


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IsostasyConfig:
    """Read-only knobs for the Airy isostasy observer."""
    crust_density: float = CRUST_DENSITY
    mantle_density: float = MANTLE_DENSITY
    water_density: float = WATER_DENSITY
    gravity: float = GRAVITY
    # Reference (datum) crustal thickness at sea level, in km.
    reference_crust_km: float = 30.0
    # Extra margin (km) added below the deepest root to set the common
    # compensation depth D_c. Any positive margin yields the same residual.
    compensation_margin_km: float = 5.0
    snapshot_every: int = 64


@dataclass(frozen=True)
class ColumnIsostasy:
    """Airy state of one representative column (read-only, km units)."""
    elevation_m: float
    root_m: float                 # crustal root (>0) or -anti-root (<0)
    moho_depth_km: float          # crust-mantle boundary below sea level
    crust_thickness_km: float     # surface (or sea floor) -> Moho


@dataclass(frozen=True)
class IsostasySnapshot:
    """Map-wide Airy roll-up at one tick (read-only)."""
    tick: int
    n_cells: int
    cell_km: float
    crust_density: float
    mantle_density: float
    mean_elevation_m: float
    mean_crust_thickness_km: float
    max_crust_thickness_km: float
    min_crust_thickness_km: float
    mean_moho_depth_km: float
    max_root_m: float             # deepest continental root
    max_antiroot_m: float         # thickest ocean anti-root (positive)
    compensation_depth_km: float
    isostatic_residual: float     # (P_max-P_min)/P_mean at D_c -> ~0 (invariant)
    roots_track_elevation: bool   # crust thickens with elevation (invariant)
    signature: str


@dataclass
class IsostasyHistory:
    snapshots: List[IsostasySnapshot] = field(default_factory=list)


@dataclass
class IsostasyState:
    config: IsostasyConfig
    history: IsostasyHistory = field(default_factory=IsostasyHistory)
    wrapped: bool = False


# ---------------------------------------------------------------------------
# Airy isostasy laws (pure, vectorised)
# ---------------------------------------------------------------------------

def airy_root_m(elevation_m, cfg: Optional[IsostasyConfig] = None):
    """Airy compensation depth for surface elevation ``h`` (m).

    Returns the signed root: positive = continental root below the reference
    Moho (land), negative = mantle anti-root (ocean basin). Vectorised:
    accepts a scalar or a NumPy array.

        land  (h >= 0):  r = rho_c/(rho_m - rho_c) * h
        ocean (h <  0):  r = -(rho_c - rho_w)/(rho_m - rho_c) * |h|

    The ocean coefficient uses ``rho_c - rho_w`` (not ``rho_m - rho_w``)
    because the crust top sits at the sea floor: the water column replaces
    crust, so the buoyancy deficit scales with the crust-water contrast. This
    is the unique anti-root that equalises the column load at the compensation
    depth (see :func:`compensation_pressure_pa`).
    """
    cfg = cfg or IsostasyConfig()
    rc, rm, rw = cfg.crust_density, cfg.mantle_density, cfg.water_density
    h = np.asarray(elevation_m, dtype=np.float64)
    land = rc / (rm - rc) * np.maximum(h, 0.0)
    ocean = -(rc - rw) / (rm - rc) * np.maximum(-h, 0.0)
    out = land + ocean
    return float(out) if out.ndim == 0 else out


def crustal_thickness_m(elevation_m, cfg: Optional[IsostasyConfig] = None):
    """Crust thickness (m): surface->Moho on land, sea floor->Moho in oceans.

    The crust top sits at z = -h in both regimes (the mountain surface on
    land, the sea floor in oceans), and the Moho at z = T0 + r, so the crust
    thickness is uniformly ``H = Moho - (-h) = T0 + r + h``::

        land :  H = T0 + r + h          (h > 0 -> thick crust + root)
        ocean:  H = T0 + r + h          (h < 0, r < 0 -> thin crust, water on top)
    """
    cfg = cfg or IsostasyConfig()
    h = np.asarray(elevation_m, dtype=np.float64)
    t0 = cfg.reference_crust_km * _M_PER_KM
    r = airy_root_m(h, cfg)
    H = t0 + r + h  # crust top at z = -h in both regimes
    return float(H) if H.ndim == 0 else H


def compensation_pressure_pa(elevation_m, compensation_depth_m: float,
                             cfg: Optional[IsostasyConfig] = None):
    """Lithostatic pressure (Pa) at ``compensation_depth_m`` below sea level,
    integrating each column from its own surface (water + crust + mantle).

    For an Airy-compensated field this is constant across all cells - the
    falsifiable equal-pressure invariant.
    """
    cfg = cfg or IsostasyConfig()
    rc, rm, rw, g = (cfg.crust_density, cfg.mantle_density,
                     cfg.water_density, cfg.gravity)
    h = np.asarray(elevation_m, dtype=np.float64)
    t0 = cfg.reference_crust_km * _M_PER_KM
    Dc = float(compensation_depth_m)

    r = airy_root_m(h, cfg)
    moho = t0 + r                       # Moho depth below sea level (m)
    water_col = np.maximum(-h, 0.0)     # ocean water thickness (m)
    crust_col = crustal_thickness_m(h, cfg)
    mantle_col = np.maximum(Dc - moho, 0.0)

    P = g * (rw * water_col + rc * crust_col + rm * mantle_col)
    return float(P) if P.ndim == 0 else P


# ---------------------------------------------------------------------------
# Map-wide observation (read-only)
# ---------------------------------------------------------------------------

def observe_isostasy(sim, config: Optional[IsostasyConfig] = None
                     ) -> Optional[IsostasySnapshot]:
    """Pure read-only Airy isostasy snapshot. ``None`` if no world wired."""
    cfg = config if config is not None else IsostasyConfig()
    world = _resolve_world(sim)
    if world is None:
        return None

    flow_dir = np.asarray(world.flow_dir, dtype=np.uint8)
    shape = flow_dir.shape
    R = int(shape[0])
    if R == 0:
        return None
    cell_km = float(world.params.map_size_km) / float(R)

    elev = _field(world, "elevation_m", 0.0, shape)
    n_cells = int(elev.size)

    root = airy_root_m(elev, cfg)
    crust = crustal_thickness_m(elev, cfg)            # m
    t0_m = cfg.reference_crust_km * _M_PER_KM
    moho = t0_m + root                                 # m below sea level

    max_root_m = float(np.maximum(root, 0.0).max())
    max_antiroot_m = float(np.maximum(-root, 0.0).max())

    # Common compensation depth: below the deepest root + a margin.
    Dc_m = moho.max() + cfg.compensation_margin_km * _M_PER_KM
    P = compensation_pressure_pa(elev, Dc_m, cfg)
    p_mean = float(P.mean())
    residual = (float(P.max() - P.min()) / p_mean) if p_mean > 0 else 0.0

    # Invariant 2 - crust thickens with elevation (mountain roots).
    flat_hi = int(elev.argmax())
    flat_lo = int(elev.argmin())
    roots_track = bool(crust.flat[flat_hi] >= crust.flat[flat_lo] - 1e-6)

    crust_km = crust / _M_PER_KM
    moho_km = moho / _M_PER_KM

    snap_seed = (
        int(sim.tick), n_cells, round(cell_km, 6),
        round(cfg.crust_density, 3), round(cfg.mantle_density, 3),
        round(float(elev.mean()), 4),
        round(float(crust_km.mean()), 6),
        round(float(crust_km.max()), 6), round(float(crust_km.min()), 6),
        round(float(moho_km.mean()), 6),
        round(max_root_m, 4), round(max_antiroot_m, 4),
        round(Dc_m / _M_PER_KM, 6), round(residual, 12), int(roots_track),
    )
    signature = hashlib.sha256(repr(snap_seed).encode("utf-8")).hexdigest()

    return IsostasySnapshot(
        tick=int(sim.tick),
        n_cells=n_cells,
        cell_km=cell_km,
        crust_density=float(cfg.crust_density),
        mantle_density=float(cfg.mantle_density),
        mean_elevation_m=float(elev.mean()),
        mean_crust_thickness_km=float(crust_km.mean()),
        max_crust_thickness_km=float(crust_km.max()),
        min_crust_thickness_km=float(crust_km.min()),
        mean_moho_depth_km=float(moho_km.mean()),
        max_root_m=max_root_m,
        max_antiroot_m=max_antiroot_m,
        compensation_depth_km=float(Dc_m / _M_PER_KM),
        isostatic_residual=float(residual),
        roots_track_elevation=roots_track,
        signature=signature,
    )


# ---------------------------------------------------------------------------
# Sim integration (idempotent observer install)
# ---------------------------------------------------------------------------

def install_isostasy_observer(sim, config: Optional[IsostasyConfig] = None
                              ) -> IsostasyState:
    """Idempotent installer. Wraps ``sim.step`` once to capture a snapshot
    every ``cfg.snapshot_every`` ticks. Read-only - never mutates the world."""
    cfg = config if config is not None else IsostasyConfig()
    existing: Optional[IsostasyState] = getattr(sim, "_isostasy_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = IsostasyState(config=cfg)
    sim._isostasy_state = state

    original_step = sim.step

    def _wrapped_step(*args, **kwargs):
        result = original_step(*args, **kwargs)
        try:
            tick = int(sim.tick)
        except Exception:
            tick = 0
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            snap = observe_isostasy(sim, cfg)
            if snap is not None:
                state.history.snapshots.append(snap)
        return result

    sim._isostasy_original_step = original_step
    sim.step = _wrapped_step
    state.wrapped = True
    sim._isostasy_wrapped = True
    return state


def uninstall_isostasy_observer(sim) -> bool:
    """Restore the original ``sim.step``. ``True`` if anything was removed."""
    state = getattr(sim, "_isostasy_state", None)
    if state is None:
        return False
    original = getattr(sim, "_isostasy_original_step", None)
    if original is not None:
        sim.step = original
        del sim._isostasy_original_step
    sim._isostasy_wrapped = False
    del sim._isostasy_state
    return True


def isostasy_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards (does not mutate sim)."""
    state: Optional[IsostasyState] = getattr(sim, "_isostasy_state", None)
    if state is None:
        return {"installed": False}
    snaps = state.history.snapshots
    last = snaps[-1] if snaps else None
    return {
        "installed": True,
        "n_snapshots": len(snaps),
        "snapshot_every": state.config.snapshot_every,
        "last_signature": (last.signature if last is not None else None),
        "last_tick": (last.tick if last is not None else None),
        "mean_crust_thickness_km": (last.mean_crust_thickness_km
                                    if last is not None else None),
        "mean_moho_depth_km": (last.mean_moho_depth_km
                               if last is not None else None),
        "max_root_m": (last.max_root_m if last is not None else None),
        "isostatic_residual": (last.isostatic_residual
                               if last is not None else None),
        "roots_track_elevation": (last.roots_track_elevation
                                  if last is not None else None),
    }


__all__ = [
    "GRAVITY", "CRUST_DENSITY", "MANTLE_DENSITY", "WATER_DENSITY",
    "IsostasyConfig", "ColumnIsostasy", "IsostasySnapshot",
    "IsostasyHistory", "IsostasyState",
    "airy_root_m", "crustal_thickness_m", "compensation_pressure_pa",
    "observe_isostasy",
    "install_isostasy_observer", "uninstall_isostasy_observer",
    "isostasy_summary",
]
