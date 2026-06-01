"""Genesis Engine — Wave 56 geothermal gradient & metamorphic-facies observer.

Read-only thermal geology that *closes the pressure–temperature loop* on the
existing geology stack. Wave 48 relative dating (``engine.geology``) gives
*when* a unit formed; Wave 51 radiometric dating
(``engine.radiometric_dating``) gives its absolute age; Wave 54 diagenetic
compaction (``engine.compaction_observer``) gives the **pressure** axis
(lithostatic overburden / Terzaghi effective stress). This observer adds the
**temperature** axis — the conductive geotherm ``T(z)`` — and reads the two
together to recover the **metamorphic facies** a field petrologist would map
(diagenesis → zeolite → greenschist → amphibolite → granulite, with a
high-pressure blueschist / eclogite branch).

Nothing here is scripted. The observer reads the stratigraphic columns the
tick has already built (per-layer ``depth_top_m`` / ``depth_bottom_m`` /
``density_kg_m3``) and overlays two laws of nature already implicit in the
engine — heat flowing up a conductive crust (a linear geotherm) and gravity
loading the overburden — exactly as gravity already acts in the compaction
observer. No hand-placed metamorphic map.

Physics (per layer, SI internally, reported in °C / MPa)
--------------------------------------------------------
Walking the column top→down::

    temperature T(z)   = T_surface + Γ · z            (linear geotherm, Γ in °C/m)
    overburden P(z)    = g · Σ ρ_i · Δz_i             (cumulative lithostatic load)
    metamorphic_grade  = band(T)                      (prograde Barrovian ordinal)
    facies             = facies(T, P)                 (+ high-P blueschist/eclogite)

The **grade index** is a function of temperature alone, so along any column
it is a monotone non-decreasing function of depth — the falsifiable
invariant below. The *facies name* may additionally carry a high-pressure
qualifier (blueschist / eclogite) when P/T is anomalously high, but that
qualifier never lowers the monotone grade.

Geotherm contract (falsifiable invariants)
------------------------------------------
Because the geotherm gradient Γ > 0 and every grain density exceeds zero,
going deeper:

- **temperature is strictly increasing with depth**,
- **lithostatic pressure is non-decreasing with depth**, and
- **metamorphic grade is non-decreasing with depth** (prograde burial).

All three are asserted as hard invariants by the smoke / tests. A violation
means the emergent stratigraphy is internally inconsistent — the same kind
of self-checking signal the realism roadmap wants surfaced.

Observer contract (mirrors Waves 49 / 50 / 51 / 54)
---------------------------------------------------
- ``GeothermConfig`` / ``LayerThermal`` / ``GeothermSnapshot`` /
  ``GeothermHistory`` / ``GeothermState`` dataclasses.
- ``geotherm_temperature(z_m, cfg)`` — pure linear geotherm.
- ``metamorphic_grade(temp_c, cfg)`` / ``classify_facies(temp_c, p_mpa, cfg)``
  — pure classifiers.
- ``compute_column(chunk_geology, cfg)`` — per-layer thermobarometry for one
  column (cumulative overburden integration).
- ``observe_geotherm(geology_state, cfg)`` — **read-only** roll-up over the
  cached chunk columns; returns a snapshot.
- ``install_geotherm_observer(sim, cfg)`` — idempotent, wraps ``sim.step`` to
  snapshot every ``snapshot_every`` ticks.
- ``uninstall_geotherm_observer(sim)`` — restores ``sim.step``.
- ``geotherm_summary(sim)`` — diagnostic dict for dashboards.

Determinism
-----------
No RNG. The signature is ``sha256`` of a canonical tuple of rounded
aggregate metrics, so two runs with the same world seed produce identical
snapshot streams.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

GRAVITY = 9.81          # m s⁻²
_PA_PER_MPA = 1.0e6

# Prograde Barrovian temperature bands (°C). band(T) → ordinal grade.
# Index i is reached once T ≥ _GRADE_ONSET_C[i].
_GRADE_ONSET_C: Tuple[float, ...] = (150.0, 250.0, 450.0, 650.0)
_GRADE_NAME: Tuple[str, ...] = (
    "diagenetic",   # 0 : unmetamorphosed sediment / soil
    "zeolite",      # 1 : very-low-grade
    "greenschist",  # 2 : low-grade
    "amphibolite",  # 3 : medium-grade
    "granulite",    # 4 : high-grade
)


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GeothermConfig:
    """Read-only knobs for the geotherm / metamorphism observer."""
    # Mean annual surface temperature (°C) at the top of the column.
    surface_temp_c: float = 15.0
    # Conductive geothermal gradient Γ (°C per kilometre). 25 °C/km is the
    # textbook continental average.
    gradient_c_per_km: float = 25.0
    gravity: float = GRAVITY
    snapshot_every: int = 64
    # Onset temperature of metamorphism (°C) — grade ≥ 1 above this.
    metamorphism_onset_c: float = 150.0
    # High-pressure branch thresholds (MPa). Above these P at sub-granulite
    # T the facies switches to the high-P series.
    blueschist_pressure_mpa: float = 700.0    # ~7 kbar, low-T high-P
    eclogite_pressure_mpa: float = 1200.0     # ~12 kbar


@dataclass(frozen=True)
class LayerThermal:
    """Thermobarometric state of one stratum (read-only)."""
    rock_type: str
    depth_top_m: float
    depth_bottom_m: float
    z_mid_m: float
    temperature_c: float         # T(z_mid) on the conductive geotherm
    pressure_mpa: float          # lithostatic overburden at z_mid
    metamorphic_grade: int       # prograde Barrovian ordinal 0..4
    facies: str                  # facies name (+ high-P qualifier)


@dataclass(frozen=True)
class GeothermSnapshot:
    """Map-wide thermal roll-up at one tick (read-only)."""
    tick: int
    total_layers: int
    n_chunks: int
    surface_temperature_c: float
    mean_temperature_c: float
    max_temperature_c: float
    max_pressure_mpa: float
    metamorphosed_layers: int      # grade ≥ 1
    max_metamorphic_grade: int
    deepest_facies: str
    geotherm_monotonic_ok: bool    # T↑, P↑, grade↑ with depth in every column
    signature: str


@dataclass
class GeothermHistory:
    snapshots: List[GeothermSnapshot] = field(default_factory=list)


@dataclass
class GeothermState:
    cfg: GeothermConfig
    history: GeothermHistory = field(default_factory=GeothermHistory)
    last: Optional[GeothermSnapshot] = None
    _orig_step: Optional[Any] = None


# ---------------------------------------------------------------------------
# Pure thermobarometry
# ---------------------------------------------------------------------------

def geotherm_temperature(z_m: float,
                         cfg: Optional[GeothermConfig] = None) -> float:
    """Conductive geotherm: T(z) = T_surface + Γ·z.

    Strictly increasing in depth (Γ > 0); equals the surface temperature at
    z = 0. Negative depths are clamped to the surface.
    """
    cfg = cfg or GeothermConfig()
    z = max(0.0, float(z_m))
    return cfg.surface_temp_c + cfg.gradient_c_per_km * (z / 1000.0)


def metamorphic_grade(temp_c: float,
                      cfg: Optional[GeothermConfig] = None) -> int:
    """Prograde Barrovian grade ordinal (0..4) from temperature alone.

    Monotone non-decreasing in temperature, hence in depth along a geotherm.
    """
    grade = 0
    for onset in _GRADE_ONSET_C:
        if temp_c >= onset:
            grade += 1
        else:
            break
    return grade


def classify_facies(temp_c: float, pressure_mpa: float,
                    cfg: Optional[GeothermConfig] = None) -> str:
    """Metamorphic facies name from (T, P).

    Standard prograde series by temperature, with a high-pressure branch:
    very high P at low–moderate T yields blueschist; extreme P yields
    eclogite. The high-P qualifier never lowers the temperature-driven
    grade ordinal (kept separate by design).
    """
    cfg = cfg or GeothermConfig()
    grade = metamorphic_grade(temp_c, cfg)
    base = _GRADE_NAME[grade]
    # High-pressure overprint only applies once metamorphism has begun and
    # below granulite temperatures (the classic blueschist/eclogite window).
    if grade >= 1 and grade < 4:
        if pressure_mpa >= cfg.eclogite_pressure_mpa:
            return "eclogite"
        if pressure_mpa >= cfg.blueschist_pressure_mpa and temp_c < 450.0:
            return "blueschist"
    return base


def compute_column(g: Any,
                   cfg: Optional[GeothermConfig] = None) -> List[LayerThermal]:
    """Per-layer thermobarometry for one ``ChunkGeology`` column, shallow→deep.

    Integrates the lithostatic overburden cumulatively from the real
    stratigraphic densities (same convention as the compaction observer);
    pure read — never mutates the layers.
    """
    cfg = cfg or GeothermConfig()
    gg = cfg.gravity
    out: List[LayerThermal] = []
    load_pa = 0.0  # overburden pressure at the top of the current layer
    for L in getattr(g, "layers", []):
        top = float(getattr(L, "depth_top_m", 0.0))
        bottom = float(getattr(L, "depth_bottom_m", 0.0))
        rho = float(getattr(L, "density_kg_m3", 0.0))
        thickness = max(0.0, bottom - top)
        z_mid = 0.5 * (top + bottom)

        over_pa = load_pa + rho * gg * max(0.0, z_mid - top)
        p_mpa = over_pa / _PA_PER_MPA
        temp_c = geotherm_temperature(z_mid, cfg)
        grade = metamorphic_grade(temp_c, cfg)
        facies = classify_facies(temp_c, p_mpa, cfg)

        out.append(LayerThermal(
            rock_type=str(getattr(L, "rock_type", "")),
            depth_top_m=top,
            depth_bottom_m=bottom,
            z_mid_m=z_mid,
            temperature_c=temp_c,
            pressure_mpa=p_mpa,
            metamorphic_grade=grade,
            facies=facies,
        ))
        load_pa += rho * gg * thickness
    return out


def column_geotherm_monotonic(layers: List[LayerThermal]) -> bool:
    """True iff, going deeper, temperature is non-decreasing, pressure is
    non-decreasing AND metamorphic grade is non-decreasing — the prograde
    burial invariant."""
    temp = [lt.temperature_c for lt in layers]
    pres = [lt.pressure_mpa for lt in layers]
    grade = [lt.metamorphic_grade for lt in layers]
    temp_ok = all(b >= a - 1e-9 for a, b in zip(temp, temp[1:]))
    pres_ok = all(b >= a - 1e-9 for a, b in zip(pres, pres[1:]))
    grade_ok = all(b >= a for a, b in zip(grade, grade[1:]))
    return temp_ok and pres_ok and grade_ok


# ---------------------------------------------------------------------------
# Map-wide observation (read-only)
# ---------------------------------------------------------------------------

def observe_geotherm(geology_state: Any,
                     cfg: Optional[GeothermConfig] = None,
                     tick: int = 0) -> GeothermSnapshot:
    """Roll up geotherm / metamorphism over every cached chunk column. Pure
    read — never mutates the geology state or any layer."""
    cfg = cfg or GeothermConfig()
    chunks = getattr(geology_state, "chunks", {}) or {}

    total_layers = 0
    n_chunks = 0
    temps: List[float] = []
    max_temp = cfg.surface_temp_c
    max_pres = 0.0
    metamorphosed = 0
    max_grade = 0
    monotonic_ok = True
    deepest_facies = "diagenetic"
    deepest_z: Optional[float] = None

    for coord in sorted(chunks.keys()):
        g = chunks[coord]
        n_chunks += 1
        total_layers += len(getattr(g, "layers", []))
        cols = compute_column(g, cfg)
        for lt in cols:
            temps.append(lt.temperature_c)
            if lt.temperature_c > max_temp:
                max_temp = lt.temperature_c
            if lt.pressure_mpa > max_pres:
                max_pres = lt.pressure_mpa
            if lt.metamorphic_grade >= 1:
                metamorphosed += 1
            if lt.metamorphic_grade > max_grade:
                max_grade = lt.metamorphic_grade
            if deepest_z is None or lt.z_mid_m > deepest_z:
                deepest_z = lt.z_mid_m
                deepest_facies = lt.facies
        if cols and not column_geotherm_monotonic(cols):
            monotonic_ok = False

    n = len(temps)
    mean_temp = (sum(temps) / n) if n else cfg.surface_temp_c

    signature = _signature(total_layers, n_chunks, mean_temp, max_temp,
                           max_pres, metamorphosed, max_grade, monotonic_ok)

    return GeothermSnapshot(
        tick=int(tick),
        total_layers=int(total_layers),
        n_chunks=int(n_chunks),
        surface_temperature_c=round(cfg.surface_temp_c, 4),
        mean_temperature_c=round(mean_temp, 4),
        max_temperature_c=round(max_temp, 4),
        max_pressure_mpa=round(max_pres, 4),
        metamorphosed_layers=int(metamorphosed),
        max_metamorphic_grade=int(max_grade),
        deepest_facies=str(deepest_facies),
        geotherm_monotonic_ok=bool(monotonic_ok),
        signature=signature,
    )


def _signature(total_layers: int, n_chunks: int, mean_temp: float,
               max_temp: float, max_pres: float, metamorphosed: int,
               max_grade: int, monotonic: bool) -> str:
    canonical = (
        f"{total_layers}|{n_chunks}|{round(mean_temp, 4)}|"
        f"{round(max_temp, 4)}|{round(max_pres, 4)}|{metamorphosed}|"
        f"{max_grade}|{int(monotonic)}"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Sim integration (idempotent observer install)
# ---------------------------------------------------------------------------

def _geology_state(sim) -> Any:
    return getattr(sim, "_geology_state", None)


def install_geotherm_observer(sim,
                              cfg: Optional[GeothermConfig] = None,
                              ) -> GeothermState:
    """Idempotent. Wraps ``sim.step`` to capture a snapshot every
    ``snapshot_every`` ticks. Read-only: it never touches world arrays."""
    existing: Optional[GeothermState] = getattr(sim, "_geotherm_state", None)
    if existing is not None:
        return existing
    cfg = cfg or GeothermConfig()
    state = GeothermState(cfg=cfg)
    state._orig_step = sim.step

    def _wrapped_step(*args, **kwargs):
        out = state._orig_step(*args, **kwargs)
        tick = int(getattr(sim, "tick", 0))
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            gs = _geology_state(sim)
            if gs is not None:
                snap = observe_geotherm(gs, cfg, tick=tick)
                state.history.snapshots.append(snap)
                state.last = snap
        return out

    sim.step = _wrapped_step
    sim._geotherm_state = state
    return state


def uninstall_geotherm_observer(sim) -> None:
    """Restore the original ``sim.step`` and drop observer state."""
    state: Optional[GeothermState] = getattr(sim, "_geotherm_state", None)
    if state is None:
        return
    if state._orig_step is not None:
        sim.step = state._orig_step
    try:
        delattr(sim, "_geotherm_state")
    except AttributeError:
        sim._geotherm_state = None


def geotherm_summary(sim) -> Dict[str, object]:
    """Diagnostic dict for dashboards. Computes a fresh snapshot from the
    current geology state if the observer has not captured one yet."""
    gs = _geology_state(sim)
    if gs is None:
        return {"installed": False, "reason": "no geology state"}
    state: Optional[GeothermState] = getattr(sim, "_geotherm_state", None)
    cfg = state.cfg if state is not None else GeothermConfig()
    snap = (state.last if (state is not None and state.last is not None)
            else observe_geotherm(gs, cfg, tick=int(getattr(sim, "tick", 0))))
    return {
        "installed": state is not None,
        "snapshots": (len(state.history.snapshots) if state else 0),
        "tick": snap.tick,
        "total_layers": snap.total_layers,
        "n_chunks": snap.n_chunks,
        "surface_temperature_c": snap.surface_temperature_c,
        "mean_temperature_c": snap.mean_temperature_c,
        "max_temperature_c": snap.max_temperature_c,
        "max_pressure_mpa": snap.max_pressure_mpa,
        "metamorphosed_layers": snap.metamorphosed_layers,
        "max_metamorphic_grade": snap.max_metamorphic_grade,
        "deepest_facies": snap.deepest_facies,
        "geotherm_monotonic_ok": snap.geotherm_monotonic_ok,
        "signature": snap.signature,
    }


__all__ = [
    "GRAVITY",
    "GeothermConfig", "LayerThermal", "GeothermSnapshot",
    "GeothermHistory", "GeothermState",
    "geotherm_temperature", "metamorphic_grade", "classify_facies",
    "compute_column", "column_geotherm_monotonic", "observe_geotherm",
    "install_geotherm_observer", "uninstall_geotherm_observer",
    "geotherm_summary",
]
