"""Genesis Engine - Wave 61 elastic lithospheric flexure observer.

Read-only solid-earth layer that generalises the Wave 59 Airy column from
*local* to *regional* compensation (Vening Meinesz 1931; Watts 2001). Airy
treats every column as an independent float: each peak carries its own root.
A real lithosphere is an elastic plate - it bends under a topographic load
and shares the burden with its neighbours, so the Moho under a narrow ridge
is much shallower than Airy predicts while long-wavelength plateaus remain
fully compensated.

Nothing here is scripted. The observer reads the same emergent elevation
field ``world.elevation_m`` the tick has already produced (as Waves 53 / 57 /
59 do) and overlays one law of nature - the thin elastic plate equation::

    D * laplacian^2(w) + (rho_m - rho_c) * g * w = q(x, y)

with flexural rigidity ``D = E * Te^3 / (12 * (1 - nu^2))`` and the
topographic load ``q`` implied by the very same elevation field the Airy
observer compensates. Solved spectrally (FFT on the periodic Genesis grid),
the deflection per wavenumber ``k`` is the Airy root filtered by the
flexural response::

    w_hat(k) = q_hat(k) / ((rho_m - rho_c) * g) * Phi(k)
    Phi(k)   = 1 / (1 + D * k^4 / ((rho_m - rho_c) * g))

``Phi`` is the classic flexural filter: Phi(0) = 1 (long wavelengths are
Airy-compensated) and Phi -> 0 as k -> inf (short wavelengths are carried by
plate strength). The flexural parameter ``alpha = (4D / ((rho_m-rho_c) g))^(1/4)``
sets the crossover wavelength.

Falsifiable invariants (asserted by the smoke / tests)
------------------------------------------------------
1. Airy limit. With Te -> 0 (D -> 0) the flexural deflection equals the Wave
   59 Airy root field to machine precision: Airy is the zero-strength member
   of the flexure family. Falsified if the spectral solve is inconsistent
   with the local law.
2. Zero-mode load balance. Phi(0) = 1 exactly, so the *mean* deflection
   equals the mean Airy root: total buoyancy still balances total load
   (regional compensation redistributes, never creates or destroys support).
3. Regional smoothing. Phi(k) <= 1 for every mode, so by Parseval the
   deflection field is never rougher than the Airy root field:
   ``std(w) <= std(r_airy)``, strictly smaller for any relief with
   short-wavelength content and Te > 0.
4. Monotone spectral response. Phi is strictly decreasing in k and bounded
   in (0, 1] - longer loads are better compensated, as observed in gravity
   admittance studies (Watts 2001).

Observer contract (mirrors Waves 53 / 55 / 57 / 59)
---------------------------------------------------
``FlexureConfig`` / ``FlexureSnapshot`` / ``FlexureHistory`` /
``FlexureState`` dataclasses; pure helpers ``flexural_rigidity_nm`` /
``flexural_parameter_m`` / ``flexural_response`` / ``topographic_load_pa`` /
``flexural_deflection_m``; ``observe_flexure(sim, cfg)`` - read-only,
``None`` if no world wired; idempotent ``install_flexure_observer`` /
``uninstall_flexure_observer`` (returns ``bool``); ``flexure_summary``
diagnostic dict.

Determinism
-----------
No RNG. The signature is ``sha256`` of a canonical tuple of rounded
aggregate metrics, so two runs with the same world seed produce identical
snapshot streams.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

# Reuse Wave 53 world access + Wave 59 Airy laws verbatim (no duplication).
from engine.discharge_observer import _field, _resolve_world
from engine.isostasy_observer import (
    CRUST_DENSITY, GRAVITY, MANTLE_DENSITY, WATER_DENSITY, airy_root_m,
)

YOUNG_MODULUS = 70.0e9   # Pa    (continental lithosphere, Watts 2001)
POISSON_RATIO = 0.25     # -
_M_PER_KM = 1000.0


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FlexureConfig:
    """Read-only knobs for the elastic flexure observer."""
    crust_density: float = CRUST_DENSITY
    mantle_density: float = MANTLE_DENSITY
    water_density: float = WATER_DENSITY
    gravity: float = GRAVITY
    young_modulus: float = YOUNG_MODULUS
    poisson_ratio: float = POISSON_RATIO
    # Effective elastic thickness Te (km). 0 recovers Airy exactly.
    elastic_thickness_km: float = 25.0
    # Reference (datum) crustal thickness at sea level, in km (Wave 59 datum).
    reference_crust_km: float = 30.0
    snapshot_every: int = 64


@dataclass(frozen=True)
class FlexureSnapshot:
    """Map-wide flexure roll-up at one tick (read-only)."""
    tick: int
    n_cells: int
    cell_km: float
    te_km: float
    rigidity_nm: float            # flexural rigidity D (N m)
    flexural_parameter_km: float  # alpha = (4D/((rho_m-rho_c)g))^(1/4)
    mean_deflection_m: float      # mean flexural Moho deflection w
    max_deflection_m: float
    min_deflection_m: float
    mean_moho_depth_km: float     # T0 + mean(w)
    zero_mode_residual: float     # |mean(w) - mean(r_airy)| / scale -> ~0
    smoothing_ratio: float        # std(w)/std(r_airy) in (0, 1]
    response_at_nyquist: float    # Phi(k_max) in (0, 1)
    smoother_than_airy: bool      # invariant 3
    signature: str


@dataclass
class FlexureHistory:
    snapshots: List[FlexureSnapshot] = field(default_factory=list)


@dataclass
class FlexureState:
    config: FlexureConfig
    history: FlexureHistory = field(default_factory=FlexureHistory)
    wrapped: bool = False


# ---------------------------------------------------------------------------
# Flexure laws (pure, vectorised)
# ---------------------------------------------------------------------------

def flexural_rigidity_nm(cfg: Optional[FlexureConfig] = None) -> float:
    """Flexural rigidity ``D = E Te^3 / (12 (1 - nu^2))`` in N m."""
    cfg = cfg or FlexureConfig()
    te_m = cfg.elastic_thickness_km * _M_PER_KM
    return cfg.young_modulus * te_m ** 3 / (12.0 * (1.0 - cfg.poisson_ratio ** 2))


def flexural_parameter_m(cfg: Optional[FlexureConfig] = None) -> float:
    """Flexural parameter ``alpha = (4D / ((rho_m - rho_c) g))^(1/4)`` (m).

    Loads much wider than ``alpha`` are Airy-compensated; much narrower
    loads are carried by plate strength. 0 when Te = 0 (Airy limit).
    """
    cfg = cfg or FlexureConfig()
    D = flexural_rigidity_nm(cfg)
    drho_g = (cfg.mantle_density - cfg.crust_density) * cfg.gravity
    return (4.0 * D / drho_g) ** 0.25


def flexural_response(wavenumber, cfg: Optional[FlexureConfig] = None):
    """Flexural filter ``Phi(k) = 1 / (1 + D k^4 / ((rho_m - rho_c) g))``.

    Dimensionless, in (0, 1]; Phi(0) = 1; strictly decreasing in |k|.
    Vectorised: accepts a scalar or a NumPy array of wavenumbers (rad/m).
    """
    cfg = cfg or FlexureConfig()
    D = flexural_rigidity_nm(cfg)
    drho_g = (cfg.mantle_density - cfg.crust_density) * cfg.gravity
    k = np.asarray(wavenumber, dtype=np.float64)
    phi = 1.0 / (1.0 + D * k ** 4 / drho_g)
    return float(phi) if phi.ndim == 0 else phi


def topographic_load_pa(elevation_m, cfg: Optional[FlexureConfig] = None):
    """Topographic load ``q`` (Pa) implied by surface elevation ``h``.

    Exactly the load the Wave 59 Airy root compensates::

        land  (h >= 0):  q =  rho_c * g * h
        ocean (h <  0):  q = -(rho_c - rho_w) * g * |h|

    so that ``q / ((rho_m - rho_c) g)`` equals :func:`airy_root_m`.
    """
    cfg = cfg or FlexureConfig()
    rc, rw, g = cfg.crust_density, cfg.water_density, cfg.gravity
    h = np.asarray(elevation_m, dtype=np.float64)
    q = g * (rc * np.maximum(h, 0.0) - (rc - rw) * np.maximum(-h, 0.0))
    return float(q) if q.ndim == 0 else q


def flexural_deflection_m(elevation_m, cell_m: float,
                          cfg: Optional[FlexureConfig] = None) -> np.ndarray:
    """Plate deflection field ``w`` (m, positive down = root) on a periodic
    2D grid, solved spectrally::

        w_hat(k) = q_hat(k) / ((rho_m - rho_c) g) * Phi(k)

    i.e. the Airy root filtered mode-by-mode by the flexural response. With
    Te = 0 this returns the Airy root field exactly.
    """
    cfg = cfg or FlexureConfig()
    h = np.asarray(elevation_m, dtype=np.float64)
    if h.ndim != 2:
        raise ValueError("flexural_deflection_m expects a 2D elevation grid")
    drho_g = (cfg.mantle_density - cfg.crust_density) * cfg.gravity

    q = topographic_load_pa(h, cfg)
    r_airy_hat = np.fft.fft2(q / drho_g)

    ky = 2.0 * np.pi * np.fft.fftfreq(h.shape[0], d=float(cell_m))
    kx = 2.0 * np.pi * np.fft.fftfreq(h.shape[1], d=float(cell_m))
    kk = np.sqrt(ky[:, None] ** 2 + kx[None, :] ** 2)
    phi = flexural_response(kk, cfg)

    w = np.fft.ifft2(r_airy_hat * phi).real
    return w


# ---------------------------------------------------------------------------
# Map-wide observation (read-only)
# ---------------------------------------------------------------------------

def observe_flexure(sim, config: Optional[FlexureConfig] = None
                    ) -> Optional[FlexureSnapshot]:
    """Pure read-only flexure snapshot. ``None`` if no world wired."""
    cfg = config if config is not None else FlexureConfig()
    world = _resolve_world(sim)
    if world is None:
        return None

    flow_dir = np.asarray(world.flow_dir, dtype=np.uint8)
    shape = flow_dir.shape
    R = int(shape[0])
    if R == 0:
        return None
    cell_km = float(world.params.map_size_km) / float(R)
    cell_m = cell_km * _M_PER_KM

    elev = _field(world, "elevation_m", 0.0, shape)
    n_cells = int(elev.size)

    w = flexural_deflection_m(elev, cell_m, cfg)
    from engine.isostasy_observer import IsostasyConfig
    iso_cfg = IsostasyConfig(
        crust_density=cfg.crust_density, mantle_density=cfg.mantle_density,
        water_density=cfg.water_density, gravity=cfg.gravity,
        reference_crust_km=cfg.reference_crust_km)
    r_airy = airy_root_m(elev, iso_cfg)

    D = flexural_rigidity_nm(cfg)
    alpha_m = flexural_parameter_m(cfg)
    t0_m = cfg.reference_crust_km * _M_PER_KM

    # Invariant 2 - zero-mode load balance (Phi(0) = 1 exactly).
    scale = max(float(np.abs(r_airy).max()), 1e-9)
    zero_mode_residual = abs(float(w.mean()) - float(r_airy.mean())) / scale

    # Invariant 3 - regional smoothing (Parseval with Phi <= 1).
    std_airy = float(r_airy.std())
    std_w = float(w.std())
    smoothing_ratio = (std_w / std_airy) if std_airy > 0 else 1.0
    smoother = bool(std_w <= std_airy + 1e-12)

    # Invariant 4 sample - response at the grid Nyquist wavenumber.
    k_nyq = np.pi / cell_m
    phi_nyq = float(flexural_response(k_nyq, cfg))

    snap_seed = (
        int(sim.tick), n_cells, round(cell_km, 6),
        round(cfg.elastic_thickness_km, 6), round(D, 3),
        round(alpha_m / _M_PER_KM, 6),
        round(float(w.mean()), 6), round(float(w.max()), 4),
        round(float(w.min()), 4),
        round((t0_m + float(w.mean())) / _M_PER_KM, 6),
        round(zero_mode_residual, 12), round(smoothing_ratio, 9),
        round(phi_nyq, 9), int(smoother),
    )
    signature = hashlib.sha256(repr(snap_seed).encode("utf-8")).hexdigest()

    return FlexureSnapshot(
        tick=int(sim.tick),
        n_cells=n_cells,
        cell_km=cell_km,
        te_km=float(cfg.elastic_thickness_km),
        rigidity_nm=float(D),
        flexural_parameter_km=float(alpha_m / _M_PER_KM),
        mean_deflection_m=float(w.mean()),
        max_deflection_m=float(w.max()),
        min_deflection_m=float(w.min()),
        mean_moho_depth_km=float((t0_m + w.mean()) / _M_PER_KM),
        zero_mode_residual=float(zero_mode_residual),
        smoothing_ratio=float(smoothing_ratio),
        response_at_nyquist=phi_nyq,
        smoother_than_airy=smoother,
        signature=signature,
    )


# ---------------------------------------------------------------------------
# Sim integration (idempotent observer install)
# ---------------------------------------------------------------------------

def install_flexure_observer(sim, config: Optional[FlexureConfig] = None
                             ) -> FlexureState:
    """Idempotent installer. Wraps ``sim.step`` once to capture a snapshot
    every ``cfg.snapshot_every`` ticks. Read-only - never mutates the world."""
    cfg = config if config is not None else FlexureConfig()
    existing: Optional[FlexureState] = getattr(sim, "_flexure_state", None)
    if existing is not None:
        existing.config = cfg
        return existing

    state = FlexureState(config=cfg)
    sim._flexure_state = state

    original_step = sim.step

    def _wrapped_step(*args, **kwargs):
        result = original_step(*args, **kwargs)
        try:
            tick = int(sim.tick)
        except Exception:
            tick = 0
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            snap = observe_flexure(sim, cfg)
            if snap is not None:
                state.history.snapshots.append(snap)
        return result

    sim._flexure_original_step = original_step
    sim.step = _wrapped_step
    state.wrapped = True
    sim._flexure_wrapped = True
    return state


def uninstall_flexure_observer(sim) -> bool:
    """Restore the original ``sim.step``. ``True`` if anything was removed."""
    state = getattr(sim, "_flexure_state", None)
    if state is None:
        return False
    original = getattr(sim, "_flexure_original_step", None)
    if original is not None:
        sim.step = original
        del sim._flexure_original_step
    sim._flexure_wrapped = False
    del sim._flexure_state
    return True


def flexure_summary(sim) -> Dict[str, Any]:
    """Diagnostic dict for dashboards (does not mutate sim)."""
    state: Optional[FlexureState] = getattr(sim, "_flexure_state", None)
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
        "te_km": (last.te_km if last is not None else None),
        "flexural_parameter_km": (last.flexural_parameter_km
                                  if last is not None else None),
        "mean_moho_depth_km": (last.mean_moho_depth_km
                               if last is not None else None),
        "zero_mode_residual": (last.zero_mode_residual
                               if last is not None else None),
        "smoothing_ratio": (last.smoothing_ratio
                            if last is not None else None),
        "smoother_than_airy": (last.smoother_than_airy
                               if last is not None else None),
    }


__all__ = [
    "YOUNG_MODULUS", "POISSON_RATIO",
    "FlexureConfig", "FlexureSnapshot", "FlexureHistory", "FlexureState",
    "flexural_rigidity_nm", "flexural_parameter_m", "flexural_response",
    "topographic_load_pa", "flexural_deflection_m",
    "observe_flexure",
    "install_flexure_observer", "uninstall_flexure_observer",
    "flexure_summary",
]
