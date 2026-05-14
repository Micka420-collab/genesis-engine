"""Genesis Engine — Wave 4 material aging.

Materials in the world degrade over time. This module turns the static
:class:`engine.material_synthesis.SynthesizedMaterial` registry into a
**living catalogue** : per-class corrosion / weathering / wear rates,
exposure-dependent, with measurable property loss (hardness, density,
structural integrity).

Calibration (annual fractional loss in mass / hardness, average humid
temperate climate)
------------------------------------------------------------------
* Iron / steel — 0.5 to 5 %/yr rust (Brunbjerg 2017). Salt water 10×.
* Bronze — 0.05 to 0.5 %/yr patination, very low loss.
* Wood — 5 to 20 %/yr biological decay if humid + ground contact.
* Stone (limestone) — <0.1 %/yr weathering at standard pH.
* Stone (granite) — negligible at human timescales.
* Ceramic — <0.1 %/yr, weathers via thermal cycling.
* Bone / leather — 10 to 30 %/yr untreated.

Per-instance vs per-class
-------------------------
The :mod:`material_synthesis` registry stores **classes** of materials
(one Cu70Sn30 entry shared across the world). Aging happens to
**instances** (a specific sword, a specific tool). We therefore add a
new lightweight :class:`MaterialInstance` carrying:

* a back-reference to the material id
* spawn tick + total exposure ticks
* environment exposure totals (humidity, salt, UV, mechanical wear)
* current property modifiers (1.0 = fresh, 0.0 = destroyed)

Cultural pressure
-----------------
Material aging creates ongoing maintenance demand : civilisations that
discover **anti-corrosion** techniques (drying, oiling, alloying, salt
washing) preserve their material capital. The simulation surfaces this
as a per-culture *maintenance practice* set, expanded over time by
invention.

Taxonomy tags (ADR 0005)
------------------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — material decay drives
back into civilisational tech preferences.
``WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"`` — one-step degradation
prediction per tick ; not yet a multi-step rollout (no chain reactions
between instances).
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"  # arxiv 2604.22748

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from engine.core import TICK_DT_S


# ---------------------------------------------------------------------------
# Calibrated annual loss rates (mass-fraction / year)
# ---------------------------------------------------------------------------
# Multiplied by exposure factor (humidity, salt, UV, mechanical) per tick.

ANNUAL_LOSS_FRACTION = {
    # canonical-name prefixes -> per-year fractional loss in air @ 60 % humidity
    "alloy_Fe":        0.030,   # ferrous alloys — rust
    "alloy_Cu":        0.0035,  # Cu / bronze — patination
    "alloy_Sn":        0.005,
    "alloy_Au":        0.00005, # noble — negligible
    "alloy_Ag":        0.0008,
    "alloy_Pb":        0.001,
    "alloy_Al":        0.001,
    "compound_Fe":     0.030,   # steel, cast iron
    "compound_Cu":     0.004,
    "ceramic":         0.0008,  # fired pottery
    "compound_C":      0.001,   # charcoal etc. (slow)
    "compound_Si":     0.0005,  # silicon-based
    # Organic (back-stop)
    "wood":            0.18,
    "fiber":           0.25,
    "leather":         0.20,
    "bone":            0.10,
    # Geological
    "stone_limestone": 0.0008,
    "stone_granite":   0.00005,
    "stone":           0.0003,  # generic stone
}

# Maintenance practices : if a culture knows the practice, multiply the
# loss rate by the practice's protective factor (< 1.0). Stackable.
MAINTENANCE_FACTORS = {
    "oiling":      0.40,   # cuts rust on iron, bronze
    "drying":      0.55,   # cuts wood + leather decay
    "salting":     0.65,   # cuts bone decay (also food preservation)
    "varnish":     0.30,   # cuts wood + ceramic loss
    "alloying":    0.50,   # if material already named alloy_/compound_
    "salt_wash":   0.70,   # cuts marine iron corrosion (rinses chlorides)
    "annealing":   0.80,   # cuts metal fatigue
}


# Exposure mode multipliers vs neutral "air @ 60 % humidity".
EXPOSURE_FACTORS = {
    "dry_indoor":  0.20,
    "humid_air":   1.00,
    "wet_soil":    2.50,
    "salt_water":  6.00,
    "open_fire":   3.00,   # short-term thermal cycling damage
    "buried":      0.50,   # underground often dry + stable
}


# ---------------------------------------------------------------------------
# Material instance
# ---------------------------------------------------------------------------

@dataclass
class MaterialInstance:
    """One physical object built from a known SynthesizedMaterial class.

    ``integrity`` collapses corrosion + wear + thermal damage into a
    single 0..1 scalar. Property modifiers below are derived from it
    at read time so the registry doesn't need to recompute everything.
    """
    instance_id: int
    material_id: int                # → MaterialRegistry
    material_name: str              # cached for fast log/queries
    spawned_tick: int
    owner_culture: int
    exposure_mode: str = "humid_air"
    integrity: float = 1.00          # decays over time
    ticks_exposed: int = 0
    last_aged_tick: int = 0
    destroyed: bool = False

    def hardness_modifier(self) -> float:
        """Multiplier on the material's nominal hardness."""
        return 0.30 + 0.70 * self.integrity

    def structural_modifier(self) -> float:
        """Multiplier on load-bearing capacity (statics integration)."""
        return self.integrity * self.integrity   # nonlinear collapse


# ---------------------------------------------------------------------------
# Aging registry
# ---------------------------------------------------------------------------

@dataclass
class MaterialAgingRegistry:
    """Tracks every spawned :class:`MaterialInstance` + per-culture
    maintenance practices.

    Stays separate from :class:`engine.material_synthesis.MaterialRegistry`
    so a fresh sim build doesn't need to mutate Wave 1/2 code paths.
    """
    _by_id: Dict[int, MaterialInstance] = field(default_factory=dict)
    _next_id: int = 1
    # Maintenance practices known per culture.
    _culture_practices: Dict[int, Set[str]] = field(default_factory=dict)
    # Aggregate stats.
    cumulative_decay_units: float = 0.0
    destroyed_instances: int = 0

    # ---- writes ----
    def spawn(
        self,
        material_id: int,
        material_name: str,
        owner_culture: int,
        spawned_tick: int,
        exposure_mode: str = "humid_air",
    ) -> MaterialInstance:
        inst = MaterialInstance(
            instance_id=self._next_id,
            material_id=material_id,
            material_name=material_name,
            spawned_tick=spawned_tick,
            owner_culture=owner_culture,
            exposure_mode=exposure_mode,
            last_aged_tick=spawned_tick,
        )
        self._by_id[self._next_id] = inst
        self._next_id += 1
        return inst

    def teach_practice(self, culture_id: int, practice: str) -> None:
        if practice not in MAINTENANCE_FACTORS:
            return
        self._culture_practices.setdefault(culture_id, set()).add(practice)

    # ---- reads ----
    def instance(self, instance_id: int) -> Optional[MaterialInstance]:
        return self._by_id.get(instance_id)

    def all_alive(self) -> List[MaterialInstance]:
        return [m for m in self._by_id.values() if not m.destroyed]

    def practices(self, culture_id: int) -> Set[str]:
        return self._culture_practices.get(culture_id, set())

    # ---- aging ----
    def tick(self, current_tick: int, drive_accel: float = 1.0) -> None:
        """Advance every alive instance by ``current_tick - last_aged_tick``
        sim-ticks.

        Per-tick fractional loss = annual_rate × (ticks × accel /
        sim_seconds_per_year) × exposure × maintenance_factor.
        """
        SIM_SECONDS_PER_YEAR = 365.0 * 86400.0
        decayed = 0.0
        destroyed = 0
        for inst in list(self._by_id.values()):
            if inst.destroyed:
                continue
            dt_ticks = current_tick - inst.last_aged_tick
            if dt_ticks <= 0:
                continue
            base = _resolve_annual_rate(inst.material_name)
            exposure = EXPOSURE_FACTORS.get(inst.exposure_mode, 1.0)
            practices = self._culture_practices.get(inst.owner_culture, set())
            maint = 1.0
            for p in practices:
                maint *= MAINTENANCE_FACTORS.get(p, 1.0)
            # Effective fractional loss over the interval.
            dt_seconds_sim = float(dt_ticks) * TICK_DT_S * drive_accel
            loss = base * exposure * maint * (dt_seconds_sim / SIM_SECONDS_PER_YEAR)
            new_integrity = inst.integrity - loss
            inst.ticks_exposed += int(dt_ticks)
            inst.last_aged_tick = current_tick
            inst.integrity = max(0.0, new_integrity)
            decayed += min(loss, inst.integrity + loss)  # bookkeeping
            if inst.integrity <= 1e-3:
                inst.destroyed = True
                destroyed += 1
        self.cumulative_decay_units += decayed
        self.destroyed_instances += destroyed


def _resolve_annual_rate(material_name: str) -> float:
    """Best-match prefix lookup. Falls back to alloy generic 0.005."""
    if not material_name:
        return 0.005
    # Longest matching prefix wins.
    for prefix in sorted(ANNUAL_LOSS_FRACTION, key=len, reverse=True):
        if material_name.startswith(prefix):
            return ANNUAL_LOSS_FRACTION[prefix]
    if material_name.startswith("alloy_"):
        return 0.005
    if material_name.startswith("compound_"):
        return 0.003
    if material_name.startswith("ceramic"):
        return 0.0008
    return 0.005


# ---------------------------------------------------------------------------
# Public installer + reporter
# ---------------------------------------------------------------------------

def install_material_aging(sim) -> MaterialAgingRegistry:
    """Attach a :class:`MaterialAgingRegistry` to ``sim`` and wrap step.

    Idempotent. Returns the live registry.
    """
    reg: Optional[MaterialAgingRegistry] = getattr(sim, "_aging_registry", None)
    if reg is not None:
        return reg
    reg = MaterialAgingRegistry()
    sim._aging_registry = reg
    orig_step = sim.step

    def wrapped_step():
        orig_step()
        reg.tick(sim.tick, float(sim.cfg.drive_accel))

    sim.step = wrapped_step
    return reg


def material_aging_state(sim) -> Dict[str, object]:
    """Snapshot consumed by ``/api/material_aging_state``."""
    reg: Optional[MaterialAgingRegistry] = getattr(sim, "_aging_registry", None)
    if reg is None:
        return {}
    alive = reg.all_alive()
    n_alive = len(alive)
    if n_alive:
        integrity_mean = float(np.mean([m.integrity for m in alive]))
        integrity_min = float(min(m.integrity for m in alive))
    else:
        integrity_mean = 0.0
        integrity_min = 0.0
    # Per-culture practices count.
    practices = {k: sorted(v) for k, v in reg._culture_practices.items()}
    return {
        "alive_instances": n_alive,
        "destroyed_total": reg.destroyed_instances,
        "cumulative_decay_units": round(reg.cumulative_decay_units, 4),
        "integrity_mean": round(integrity_mean, 4),
        "integrity_min": round(integrity_min, 4),
        "culture_practices": practices,
    }


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "MaterialInstance",
    "MaterialAgingRegistry",
    "install_material_aging",
    "material_aging_state",
    "ANNUAL_LOSS_FRACTION",
    "EXPOSURE_FACTORS",
    "MAINTENANCE_FACTORS",
]
