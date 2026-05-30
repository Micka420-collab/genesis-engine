"""Genesis Engine — Wave 54 diagenetic compaction & lithostatic pressure observer.

Read-only sedimentary geomechanics that *complements* the existing geology
stack: Wave 48 relative dating (``engine.geology`` — ``age_ma`` +
superposition), Wave 50 cryoclastie (``engine.frost_weathering``) and
Wave 51 radiometric dating (``engine.radiometric_dating``). Where those
modules describe *when* and *how* rock breaks, this observer describes how
the column is **squeezed by its own weight**: it integrates the emergent
stratigraphic densities into a lithostatic (overburden) pressure, removes
the hydrostatic pore pressure to obtain the **vertical effective stress**,
and from that recovers the **porosity** a sedimentologist would log
(mechanical compaction / lithification).

Nothing here is scripted. The observer reads the stratigraphic columns the
tick has already built (per-layer ``depth_top_m`` / ``depth_bottom_m`` /
``density_kg_m3``) and overlays two laws of nature — gravity acting on the
overburden, and stress-driven compaction — exactly as gravity already acts
elsewhere in the engine. No hand-placed compaction profile.

Physics (per layer, SI internally, reported in MPa)
---------------------------------------------------
Walking the column top→down we accumulate the overburden load::

    overburden(z)      = g · Σ ρ_i · Δz_i               (cumulative, to z)
    pore_pressure(z)   = ρ_water · g · z                (water table at surface)
    effective_stress σ'= overburden − pore_pressure     (Terzaghi)
    porosity φ(σ')     = φ₀ · exp(−b · σ')              (effective-stress law)
    bulk_density       = (1−φ)·ρ_grain + φ·ρ_water

Driving compaction with the **effective stress** (Terzaghi), rather than a
raw Athy depth proxy, is both more physical and guarantees the falsifiable
invariants below regardless of rock ordering.

Compaction contract (falsifiable invariants)
--------------------------------------------
Because every grain density in the emergent strata exceeds water
(ρ_grain ≥ 1500 > 1000 kg/m³), going deeper:

- **effective stress is non-decreasing with depth** (overburden grows
  faster than the hydrostatic column), and
- **porosity is non-increasing with depth** (φ is a decreasing function of
  σ').

Both are asserted as hard invariants by the smoke / tests. A violation
means the emergent stratigraphy is internally inconsistent — the same kind
of self-checking signal the realism roadmap wants surfaced.

Observer contract (mirrors Waves 45 / 49 / 50 / 51)
---------------------------------------------------
- ``CompactionConfig`` / ``LayerCompaction`` / ``CompactionSnapshot`` /
  ``CompactionHistory`` / ``CompactionState`` dataclasses.
- ``porosity_from_stress(sigma_mpa, cfg)`` — pure compaction law.
- ``compute_column(chunk_geology, cfg)`` — per-layer geomechanics for one
  column (cumulative overburden integration).
- ``observe_compaction(geology_state, cfg)`` — **read-only** roll-up over
  the cached chunk columns; returns a snapshot.
- ``install_compaction_observer(sim, cfg)`` — idempotent, wraps
  ``sim.step`` to snapshot every ``snapshot_every`` ticks.
- ``uninstall_compaction_observer(sim)`` — restores ``sim.step``.
- ``compaction_summary(sim)`` — diagnostic dict for dashboards.

Determinism
-----------
No RNG. The signature is ``sha256`` of a canonical tuple of rounded
aggregate metrics, so two runs with the same world seed produce identical
snapshot streams.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

GRAVITY = 9.81          # m s⁻²
WATER_DENSITY = 1000.0  # kg m⁻³  (hydrostatic pore fluid)
_PA_PER_MPA = 1.0e6


# ---------------------------------------------------------------------------
# Configuration / dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CompactionConfig:
    """Read-only knobs for the compaction observer."""
    # Depositional surface porosity φ₀ (fraction) before any burial.
    surface_porosity: float = 0.60
    # Compaction coefficient b (per MPa) in φ = φ₀·exp(−b·σ').
    compaction_coeff_per_mpa: float = 0.045
    water_density: float = WATER_DENSITY
    gravity: float = GRAVITY
    snapshot_every: int = 64
    # A layer is "lithified" once its porosity falls below this ceiling.
    lithified_porosity: float = 0.10


@dataclass(frozen=True)
class LayerCompaction:
    """Geomechanical state of one stratum (read-only)."""
    rock_type: str
    depth_top_m: float
    depth_bottom_m: float
    z_mid_m: float
    overburden_mpa: float        # lithostatic pressure at mid-depth
    pore_pressure_mpa: float     # hydrostatic pore pressure at mid-depth
    effective_stress_mpa: float  # σ' = overburden − pore (Terzaghi)
    porosity: float              # φ(σ') after mechanical compaction
    bulk_density_kg_m3: float    # (1−φ)·ρ_grain + φ·ρ_water


@dataclass(frozen=True)
class CompactionSnapshot:
    """Map-wide compaction roll-up at one tick (read-only)."""
    tick: int
    total_layers: int
    n_chunks: int
    mean_porosity: float
    shallow_porosity: float       # porosity of the shallowest layer seen
    deep_porosity: float          # porosity of the deepest layer seen
    max_overburden_mpa: float
    max_effective_stress_mpa: float
    mean_bulk_density_kg_m3: float
    lithified_layers: int
    compaction_monotonic_ok: bool  # σ' ↑ and φ ↓ with depth in every column
    signature: str


@dataclass
class CompactionHistory:
    snapshots: List[CompactionSnapshot] = field(default_factory=list)


@dataclass
class CompactionState:
    cfg: CompactionConfig
    history: CompactionHistory = field(default_factory=CompactionHistory)
    last: Optional[CompactionSnapshot] = None
    _orig_step: Optional[Any] = None


# ---------------------------------------------------------------------------
# Compaction law (pure)
# ---------------------------------------------------------------------------

def porosity_from_stress(effective_stress_mpa: float,
                         cfg: Optional[CompactionConfig] = None) -> float:
    """Porosity from vertical effective stress: φ = φ₀·exp(−b·σ').

    Monotonically decreasing in σ'; equals the surface porosity at σ'=0.
    Negative stresses are clamped to zero (no tensile compaction).
    """
    cfg = cfg or CompactionConfig()
    s = max(0.0, float(effective_stress_mpa))
    return cfg.surface_porosity * math.exp(-cfg.compaction_coeff_per_mpa * s)


def compute_column(g: Any,
                   cfg: Optional[CompactionConfig] = None) -> List[LayerCompaction]:
    """Per-layer geomechanics for one ``ChunkGeology`` column, shallow→deep.

    Integrates the overburden cumulatively from the real stratigraphic
    densities; pure read — never mutates the layers.
    """
    cfg = cfg or CompactionConfig()
    gg = cfg.gravity
    out: List[LayerCompaction] = []
    load_pa = 0.0  # overburden pressure at the top of the current layer
    for L in getattr(g, "layers", []):
        top = float(getattr(L, "depth_top_m", 0.0))
        bottom = float(getattr(L, "depth_bottom_m", 0.0))
        rho = float(getattr(L, "density_kg_m3", 0.0))
        thickness = max(0.0, bottom - top)
        z_mid = 0.5 * (top + bottom)

        over_pa = load_pa + rho * gg * max(0.0, z_mid - top)
        pore_pa = cfg.water_density * gg * z_mid
        eff_pa = max(0.0, over_pa - pore_pa)
        eff_mpa = eff_pa / _PA_PER_MPA
        por = porosity_from_stress(eff_mpa, cfg)
        bulk = (1.0 - por) * rho + por * cfg.water_density

        out.append(LayerCompaction(
            rock_type=str(getattr(L, "rock_type", "")),
            depth_top_m=top,
            depth_bottom_m=bottom,
            z_mid_m=z_mid,
            overburden_mpa=over_pa / _PA_PER_MPA,
            pore_pressure_mpa=pore_pa / _PA_PER_MPA,
            effective_stress_mpa=eff_mpa,
            porosity=por,
            bulk_density_kg_m3=bulk,
        ))
        # Advance the cumulative load to the bottom of this layer.
        load_pa += rho * gg * thickness
    return out


def column_compaction_monotonic(layers: List[LayerCompaction]) -> bool:
    """True iff, going deeper, effective stress is non-decreasing AND
    porosity is non-increasing — the compaction invariant."""
    eff = [lc.effective_stress_mpa for lc in layers]
    por = [lc.porosity for lc in layers]
    eff_ok = all(b >= a - 1e-9 for a, b in zip(eff, eff[1:]))
    por_ok = all(b <= a + 1e-9 for a, b in zip(por, por[1:]))
    return eff_ok and por_ok


# ---------------------------------------------------------------------------
# Map-wide observation (read-only)
# ---------------------------------------------------------------------------

def observe_compaction(geology_state: Any,
                       cfg: Optional[CompactionConfig] = None,
                       tick: int = 0) -> CompactionSnapshot:
    """Roll up compaction over every cached chunk column. Pure read —
    never mutates the geology state or any layer."""
    cfg = cfg or CompactionConfig()
    chunks = getattr(geology_state, "chunks", {}) or {}

    total_layers = 0
    n_chunks = 0
    porosities: List[float] = []
    bulks: List[float] = []
    max_over = 0.0
    max_eff = 0.0
    lithified = 0
    monotonic_ok = True
    shallow_por = 0.0
    deep_por = 0.0
    shallowest_z: Optional[float] = None
    deepest_z: Optional[float] = None

    for coord in sorted(chunks.keys()):
        g = chunks[coord]
        n_chunks += 1
        total_layers += len(getattr(g, "layers", []))
        cols = compute_column(g, cfg)
        for lc in cols:
            porosities.append(lc.porosity)
            bulks.append(lc.bulk_density_kg_m3)
            if lc.overburden_mpa > max_over:
                max_over = lc.overburden_mpa
            if lc.effective_stress_mpa > max_eff:
                max_eff = lc.effective_stress_mpa
            if lc.porosity <= cfg.lithified_porosity:
                lithified += 1
            if shallowest_z is None or lc.z_mid_m < shallowest_z:
                shallowest_z = lc.z_mid_m
                shallow_por = lc.porosity
            if deepest_z is None or lc.z_mid_m > deepest_z:
                deepest_z = lc.z_mid_m
                deep_por = lc.porosity
        if cols and not column_compaction_monotonic(cols):
            monotonic_ok = False

    n = len(porosities)
    mean_por = (sum(porosities) / n) if n else 0.0
    mean_bulk = (sum(bulks) / n) if n else 0.0

    signature = _signature(total_layers, n_chunks, mean_por, max_eff,
                           mean_bulk, lithified, monotonic_ok)

    return CompactionSnapshot(
        tick=int(tick),
        total_layers=int(total_layers),
        n_chunks=int(n_chunks),
        mean_porosity=round(mean_por, 6),
        shallow_porosity=round(shallow_por, 6),
        deep_porosity=round(deep_por, 6),
        max_overburden_mpa=round(max_over, 4),
        max_effective_stress_mpa=round(max_eff, 4),
        mean_bulk_density_kg_m3=round(mean_bulk, 3),
        lithified_layers=int(lithified),
        compaction_monotonic_ok=bool(monotonic_ok),
        signature=signature,
    )


def _signature(total_layers: int, n_chunks: int, mean_por: float,
               max_eff: float, mean_bulk: float, lithified: int,
               monotonic: bool) -> str:
    canonical = (
        f"{total_layers}|{n_chunks}|{round(mean_por, 6)}|"
        f"{round(max_eff, 4)}|{round(mean_bulk, 3)}|{lithified}|"
        f"{int(monotonic)}"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Sim integration (idempotent observer install)
# ---------------------------------------------------------------------------

def _geology_state(sim) -> Any:
    return getattr(sim, "_geology_state", None)


def install_compaction_observer(sim,
                                cfg: Optional[CompactionConfig] = None,
                                ) -> CompactionState:
    """Idempotent. Wraps ``sim.step`` to capture a snapshot every
    ``snapshot_every`` ticks. Read-only: it never touches world arrays."""
    existing: Optional[CompactionState] = getattr(
        sim, "_compaction_state", None)
    if existing is not None:
        return existing
    cfg = cfg or CompactionConfig()
    state = CompactionState(cfg=cfg)
    state._orig_step = sim.step

    def _wrapped_step(*args, **kwargs):
        out = state._orig_step(*args, **kwargs)
        tick = int(getattr(sim, "tick", 0))
        if cfg.snapshot_every > 0 and tick % cfg.snapshot_every == 0:
            gs = _geology_state(sim)
            if gs is not None:
                snap = observe_compaction(gs, cfg, tick=tick)
                state.history.snapshots.append(snap)
                state.last = snap
        return out

    sim.step = _wrapped_step
    sim._compaction_state = state
    return state


def uninstall_compaction_observer(sim) -> None:
    """Restore the original ``sim.step`` and drop observer state."""
    state: Optional[CompactionState] = getattr(
        sim, "_compaction_state", None)
    if state is None:
        return
    if state._orig_step is not None:
        sim.step = state._orig_step
    try:
        delattr(sim, "_compaction_state")
    except AttributeError:
        sim._compaction_state = None


def compaction_summary(sim) -> Dict[str, object]:
    """Diagnostic dict for dashboards. Computes a fresh snapshot from the
    current geology state if the observer has not captured one yet."""
    gs = _geology_state(sim)
    if gs is None:
        return {"installed": False, "reason": "no geology state"}
    state: Optional[CompactionState] = getattr(
        sim, "_compaction_state", None)
    cfg = state.cfg if state is not None else CompactionConfig()
    snap = (state.last if (state is not None and state.last is not None)
            else observe_compaction(gs, cfg, tick=int(getattr(sim, "tick", 0))))
    return {
        "installed": state is not None,
        "snapshots": (len(state.history.snapshots) if state else 0),
        "tick": snap.tick,
        "total_layers": snap.total_layers,
        "n_chunks": snap.n_chunks,
        "mean_porosity": snap.mean_porosity,
        "shallow_porosity": snap.shallow_porosity,
        "deep_porosity": snap.deep_porosity,
        "max_overburden_mpa": snap.max_overburden_mpa,
        "max_effective_stress_mpa": snap.max_effective_stress_mpa,
        "mean_bulk_density_kg_m3": snap.mean_bulk_density_kg_m3,
        "lithified_layers": snap.lithified_layers,
        "compaction_monotonic_ok": snap.compaction_monotonic_ok,
        "signature": snap.signature,
    }


__all__ = [
    "GRAVITY", "WATER_DENSITY",
    "CompactionConfig", "LayerCompaction", "CompactionSnapshot",
    "CompactionHistory", "CompactionState",
    "porosity_from_stress", "compute_column", "column_compaction_monotonic",
    "observe_compaction",
    "install_compaction_observer", "uninstall_compaction_observer",
    "compaction_summary",
]
