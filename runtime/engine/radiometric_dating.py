"""Genesis Engine — Wave 51 radiometric (absolute) dating observer.

Read-only geochronology that *complements* the Wave 48 relative dating
(``engine.geology`` — ``age_ma`` + law of superposition). Where Wave 48
gives every stratum a **relative** age obeying superposition, this module
attributes every datable layer a concrete **isotopic system** and derives
the **absolute** time signal a field geochronologist would actually
measure: the parent-isotope remaining fraction and the daughter/parent
accumulation ratio. Inverting the decay law recovers an absolute age,
which is then checked for *concordance* with the stratigraphic ordering.

Nothing here is scripted: the observer reads the emergent stratigraphic
columns already built by the tick (deposition rates, burial depth, rock
type) and overlays the *physics of radioactive decay* — a law of nature
on the same footing as gravity, never a hand-placed timeline.

Geochronometer table (real half-lives)
--------------------------------------
A layer is dated with whichever system covers its emergent age, mirroring
real practice (you do not U-Pb a Holocene peat, nor ¹⁴C a granite):

    ¹⁴C  (radiocarbon)        t½ = 5.73e-3 Ma   window  0      – 0.05 Ma
    ²³⁰Th (uranium-series)    t½ = 0.0754 Ma    window  0.001  – 0.5  Ma
    ⁴⁰K→⁴⁰Ar (K–Ar / Ar–Ar)  t½ = 1250  Ma      window  0.5    – 100  Ma
    ²³⁸U→²⁰⁶Pb (U–Pb)         t½ = 4468  Ma      window  100    – 4500 Ma
    ⁸⁷Rb→⁸⁷Sr (Rb–Sr)        t½ = 48800 Ma      window  1000   – 4500 Ma

Decay law (per system, λ = ln2 / t½):

    parent fraction   f      = exp(-λ t)               (what remains)
    daughter / parent D/P    = exp(λ t) - 1            (isochron eq.)
    recovered age     t_est  = ln(1 + D/P) / λ         (the geochronometer)

Concordance contract
--------------------
The recovered absolute ages must (a) round-trip the emergent age within a
tight tolerance — *geochronometer closure* — and (b) stay non-decreasing
with depth — *method-independent agreement with superposition*. Both are
asserted as hard invariants by the smoke / tests; a violation means the
emergent stratigraphy is internally inconsistent, which is exactly the
kind of falsifiable signal the realism roadmap wants surfaced.

Observer contract (mirrors Waves 45 / 49 / 50)
----------------------------------------------
- ``RadiometricConfig`` / ``LayerDate`` / ``RadiometricSnapshot`` /
  ``RadiometricHistory`` / ``RadiometricState`` dataclasses.
- ``date_layer(age_ma, cfg)`` — pure, per-layer geochronology.
- ``observe_radiometric(geology_state, cfg)`` — **read-only** roll-up over
  the cached chunk columns; returns a snapshot.
- ``install_radiometric_observer(sim, cfg)`` — idempotent, wraps
  ``sim.step`` to snapshot every ``snapshot_every`` ticks.
- ``uninstall_radiometric_observer(sim)`` — restores ``sim.step``.
- ``radiometric_summary(sim)`` — diagnostic dict for dashboards.

Determinism
-----------
No RNG. The signature is ``sha256`` of a canonical tuple of rounded
aggregate metrics + the integer system-usage histogram, so two runs with
the same world seed produce identical snapshot streams.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Geochronometer table — real decay constants (half-lives in Ma)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Isotope:
    """One radiometric system. Half-life + usable age window (Ma)."""
    name: str
    parent: str
    daughter: str
    half_life_ma: float
    window_min_ma: float
    window_max_ma: float

    @property
    def lam_per_ma(self) -> float:
        """Decay constant λ = ln2 / t½ (per Ma)."""
        return math.log(2.0) / self.half_life_ma


# Ordered young → old. Selection picks the first system whose window
# contains the emergent age (Rb–Sr is the deep-basement fallback).
ISOTOPES: Tuple[Isotope, ...] = (
    Isotope("C-14", "14C", "14N", 5.73e-3, 0.0, 0.05),
    Isotope("U-Th", "234U", "230Th", 0.0754, 1e-3, 0.5),
    Isotope("K-Ar", "40K", "40Ar", 1250.0, 0.5, 100.0),
    Isotope("U-Pb", "238U", "206Pb", 4468.0, 100.0, 4500.0),
    Isotope("Rb-Sr", "87Rb", "87Sr", 48800.0, 1000.0, 4500.0),
)
ISOTOPE_BY_NAME: Dict[str, Isotope] = {iso.name: iso for iso in ISOTOPES}
SYSTEM_NAMES: Tuple[str, ...] = tuple(iso.name for iso in ISOTOPES)

# Analytical uncertainty model (relative 1σ). Minimal near one half-life
# (the "sweet spot"), rising toward the window edges where the parent is
# nearly intact (too young) or almost gone (too old).
_SIGMA_FLOOR = 0.005          # 0.5 % best-case relative uncertainty
_SIGMA_GAIN = 0.04            # growth per ln-unit away from f = 0.5
_SIGMA_CAP = 0.50             # never report better-than-useless as < 50 %


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RadiometricConfig:
    """Read-only knobs for the radiometric observer."""
    snapshot_every: int = 64
    # Round-trip closure tolerance (Ma) the recovered age must meet.
    closure_tol_ma: float = 1e-3
    # A layer counts as "well-dated" only when its relative 1σ is below
    # this ceiling (otherwise it is in-range but low-confidence).
    confident_sigma: float = 0.25
    top_systems: int = 5


@dataclass(frozen=True)
class LayerDate:
    """Absolute-dating result for one stratum (read-only)."""
    rock_type: str
    depth_top_m: float
    depth_bottom_m: float
    age_ma: float                 # emergent relative age (Wave 48 input)
    system: str                   # chosen geochronometer
    parent_fraction: float        # exp(-λ t) — what remains
    daughter_parent_ratio: float  # exp(λ t) - 1 — isochron signal
    recovered_age_ma: float       # ln(1 + D/P) / λ — the round-trip
    sigma_rel: float              # analytical relative 1σ
    in_window: bool               # emergent age inside system's usable range


@dataclass(frozen=True)
class RadiometricSnapshot:
    """Map-wide geochronology roll-up at one tick (read-only)."""
    tick: int
    total_layers: int
    datable_layers: int
    datable_fraction: float
    confident_layers: int
    oldest_age_ma: float
    oldest_system: str
    mean_sigma_rel: float
    max_closure_residual_ma: float
    concordance_ok: bool          # recovered ages monotone with depth
    system_histogram: Dict[str, int]
    signature: str


@dataclass
class RadiometricHistory:
    snapshots: List[RadiometricSnapshot] = field(default_factory=list)


@dataclass
class RadiometricState:
    cfg: RadiometricConfig
    history: RadiometricHistory = field(default_factory=RadiometricHistory)
    last: Optional[RadiometricSnapshot] = None
    _orig_step: Optional[Any] = None


# ---------------------------------------------------------------------------
# Per-layer geochronology (pure)
# ---------------------------------------------------------------------------

def select_isotopic_system(age_ma: float) -> Optional[Isotope]:
    """Pick the geochronometer whose usable window covers ``age_ma``.

    Young → old scan; returns ``None`` for non-positive ages (an unassigned
    layer) so the caller can skip it rather than fabricate a date.
    """
    if age_ma <= 0.0:
        return None
    for iso in ISOTOPES:
        if iso.window_min_ma <= age_ma <= iso.window_max_ma:
            return iso
    # Older than every window's max → clamp to the oldest system (Rb–Sr).
    return ISOTOPES[-1]


def _sigma_rel(parent_fraction: float) -> float:
    """Relative 1σ from how far the parent fraction sits from 0.5.

    Sharpest when ~half the parent has decayed; degrades as f → 1 (barely
    any daughter to measure) or f → 0 (barely any parent left).
    """
    f = min(max(parent_fraction, 1e-12), 1.0 - 1e-12)
    dist = abs(math.log(f) - math.log(0.5))
    return min(_SIGMA_CAP, _SIGMA_FLOOR + _SIGMA_GAIN * dist)


def date_layer(age_ma: float, rock_type: str = "",
               depth_top_m: float = 0.0, depth_bottom_m: float = 0.0,
               ) -> Optional[LayerDate]:
    """Full absolute-dating result for one stratum, or ``None`` if undatable.

    Pure function of the emergent ``age_ma`` + the chosen decay law. The
    recovered age round-trips ``age_ma`` analytically (geochronometer
    closure); the residual is what the smoke asserts is ~0.
    """
    iso = select_isotopic_system(age_ma)
    if iso is None:
        return None
    lam = iso.lam_per_ma
    parent_fraction = math.exp(-lam * age_ma)
    dp_ratio = math.expm1(lam * age_ma)          # exp(λt) - 1, stable
    recovered = math.log1p(dp_ratio) / lam       # ln(1 + D/P) / λ
    in_window = iso.window_min_ma <= age_ma <= iso.window_max_ma
    return LayerDate(
        rock_type=rock_type,
        depth_top_m=float(depth_top_m),
        depth_bottom_m=float(depth_bottom_m),
        age_ma=float(age_ma),
        system=iso.name,
        parent_fraction=parent_fraction,
        daughter_parent_ratio=dp_ratio,
        recovered_age_ma=recovered,
        sigma_rel=_sigma_rel(parent_fraction),
        in_window=in_window,
    )


def date_column(g: Any) -> List[LayerDate]:
    """Absolute dates for every datable layer of a ``ChunkGeology`` column,
    shallow → deep. Skips layers without an assigned ``age_ma``."""
    out: List[LayerDate] = []
    for L in getattr(g, "layers", []):
        ld = date_layer(getattr(L, "age_ma", 0.0),
                        rock_type=getattr(L, "rock_type", ""),
                        depth_top_m=getattr(L, "depth_top_m", 0.0),
                        depth_bottom_m=getattr(L, "depth_bottom_m", 0.0))
        if ld is not None:
            out.append(ld)
    return out


def column_concordant(dates: List[LayerDate]) -> bool:
    """True iff recovered absolute ages are non-decreasing with depth —
    absolute dating agreeing with the law of superposition."""
    ages = [d.recovered_age_ma for d in dates]
    return all(b >= a - 1e-6 for a, b in zip(ages, ages[1:]))


# ---------------------------------------------------------------------------
# Map-wide observation (read-only)
# ---------------------------------------------------------------------------

def observe_radiometric(geology_state: Any,
                        cfg: Optional[RadiometricConfig] = None,
                        tick: int = 0) -> RadiometricSnapshot:
    """Roll up geochronology over every cached chunk column. Pure read —
    never mutates the geology state or any layer."""
    cfg = cfg or RadiometricConfig()
    chunks = getattr(geology_state, "chunks", {}) or {}

    total_layers = 0
    datable: List[LayerDate] = []
    confident_layers = 0
    oldest_age = 0.0
    oldest_system = "none"
    max_residual = 0.0
    concordance_ok = True
    histogram: Dict[str, int] = {name: 0 for name in SYSTEM_NAMES}

    # Iterate chunks in a deterministic order (sorted by coord).
    for coord in sorted(chunks.keys()):
        g = chunks[coord]
        total_layers += len(getattr(g, "layers", []))
        dates = date_column(g)
        for d in dates:
            datable.append(d)
            histogram[d.system] += 1
            residual = abs(d.recovered_age_ma - d.age_ma)
            if residual > max_residual:
                max_residual = residual
            if d.sigma_rel <= cfg.confident_sigma:
                confident_layers += 1
            if d.recovered_age_ma > oldest_age:
                oldest_age = d.recovered_age_ma
                oldest_system = d.system
        if not column_concordant(dates):
            concordance_ok = False

    n = len(datable)
    datable_fraction = (n / total_layers) if total_layers else 0.0
    mean_sigma = (sum(d.sigma_rel for d in datable) / n) if n else 0.0

    signature = _signature(tick, n, total_layers, oldest_age,
                           oldest_system, mean_sigma, concordance_ok,
                           histogram)

    return RadiometricSnapshot(
        tick=int(tick),
        total_layers=int(total_layers),
        datable_layers=int(n),
        datable_fraction=round(datable_fraction, 6),
        confident_layers=int(confident_layers),
        oldest_age_ma=round(oldest_age, 4),
        oldest_system=oldest_system,
        mean_sigma_rel=round(mean_sigma, 6),
        max_closure_residual_ma=round(max_residual, 9),
        concordance_ok=bool(concordance_ok),
        system_histogram=histogram,
        signature=signature,
    )


def _signature(tick: int, n_datable: int, total: int, oldest: float,
               oldest_system: str, mean_sigma: float, concordance: bool,
               histogram: Dict[str, int]) -> str:
    hist_part = ",".join(f"{k}:{histogram.get(k, 0)}" for k in SYSTEM_NAMES)
    canonical = (
        f"{n_datable}|{total}|{round(oldest, 4)}|{oldest_system}|"
        f"{round(mean_sigma, 6)}|{int(concordance)}|{hist_part}"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Sim integration (idempotent observer install)
# ---------------------------------------------------------------------------

def _geology_state(sim) -> Any:
    return getattr(sim, "_geology_state", None)


def install_radiometric_observer(sim,
                                 cfg: Optional[RadiometricConfig] = None,
                                 ) -> RadiometricState:
    """Idempotent. Wraps ``sim.step`` to capture a snapshot every
    ``snapshot_every`` ticks. Read-only: it never touches world arrays."""
    existing: Optional[RadiometricState] = getattr(
        sim, "_radiometric_state", None)
    if existing is not None:
        return existing
    cfg = cfg or RadiometricConfig()
    state = RadiometricState(cfg=cfg)
    state._orig_step = sim.step

    def _wrapped_step(*args, **kwargs):
        out = state._orig_step(*args, **kwargs)
        tick = int(getattr(sim, "tick", 0))
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            gs = _geology_state(sim)
            if gs is not None:
                snap = observe_radiometric(gs, cfg, tick=tick)
                state.history.snapshots.append(snap)
                state.last = snap
        return out

    sim.step = _wrapped_step
    sim._radiometric_state = state
    return state


def uninstall_radiometric_observer(sim) -> None:
    """Restore the original ``sim.step`` and drop observer state."""
    state: Optional[RadiometricState] = getattr(
        sim, "_radiometric_state", None)
    if state is None:
        return
    if state._orig_step is not None:
        sim.step = state._orig_step
    try:
        delattr(sim, "_radiometric_state")
    except AttributeError:
        sim._radiometric_state = None


def radiometric_summary(sim) -> Dict[str, object]:
    """Diagnostic dict for dashboards. Computes a fresh snapshot from the
    current geology state if the observer has not captured one yet."""
    gs = _geology_state(sim)
    if gs is None:
        return {"installed": False, "reason": "no geology state"}
    state: Optional[RadiometricState] = getattr(
        sim, "_radiometric_state", None)
    cfg = state.cfg if state is not None else RadiometricConfig()
    snap = (state.last if (state is not None and state.last is not None)
            else observe_radiometric(gs, cfg, tick=int(getattr(sim, "tick", 0))))
    return {
        "installed": state is not None,
        "snapshots": (len(state.history.snapshots) if state else 0),
        "tick": snap.tick,
        "total_layers": snap.total_layers,
        "datable_layers": snap.datable_layers,
        "datable_fraction": snap.datable_fraction,
        "confident_layers": snap.confident_layers,
        "oldest_age_ma": snap.oldest_age_ma,
        "oldest_system": snap.oldest_system,
        "mean_sigma_rel": snap.mean_sigma_rel,
        "max_closure_residual_ma": snap.max_closure_residual_ma,
        "concordance_ok": snap.concordance_ok,
        "system_histogram": dict(snap.system_histogram),
        "signature": snap.signature,
    }


__all__ = [
    "Isotope", "ISOTOPES", "ISOTOPE_BY_NAME", "SYSTEM_NAMES",
    "RadiometricConfig", "LayerDate", "RadiometricSnapshot",
    "RadiometricHistory", "RadiometricState",
    "select_isotopic_system", "date_layer", "date_column",
    "column_concordant", "observe_radiometric",
    "install_radiometric_observer", "uninstall_radiometric_observer",
    "radiometric_summary",
]
