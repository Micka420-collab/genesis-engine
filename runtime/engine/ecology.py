"""Global atmospheric + climate model — pollution, CO2, warming feedback.

Tracks atmospheric CO2 in ppm, anthropogenic emissions (hearths, furnaces,
forest clearing), natural sinks (forests, oceans). When CO2 rises beyond
pre-industrial baseline, mean temperature anomaly accumulates which feeds
back into biome viability and food capacity.

Initial conditions match Earth's late paleolithic / pre-agricultural baseline:
~280 ppm CO2, 0 K anomaly, undisturbed primeval biomes.

Calibration is intentionally optimistic about how fast humans can change
the atmosphere — at the agent-counts and time-scales we run, a hunter-
gatherer band shouldn't move the dial. The feedback only becomes visible
if the civilization scales massively or industrializes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

import numpy as np

from engine.materials import MaterialKind, MATERIALS
from engine.world import invalidate_resource_masks


# Earth's pre-industrial baseline (Holocene mean).
CO2_BASELINE_PPM = 280.0
# Mass of atmosphere ~5.15e18 kg ; mass of CO2 per ppm = ~7.8 Gt.
# We work at a much smaller scale (Genesis Engine simulates km^2 not the
# planet), so we use a *local* concentration model normalised to per-km^2
# of simulated area — emissions are scaled accordingly.
CO2_KG_PER_PPM_LOCAL = 1.0e3   # 1 ppm change requires 1000 kg in our local model

# Climate sensitivity (K per doubling of CO2) — IPCC AR6 likely range 2.5–4.0.
CLIMATE_SENSITIVITY_K = 3.0
# Each doubling = +3 K mean warming. We use log2(co2/280) * sensitivity.

# Sink strengths (kg CO2 removed per simulated-second per km^2).
SINK_OCEAN_KG_S = 0.0005
SINK_FOREST_KG_S = 0.0008


@dataclass
class Atmosphere:
    """Global atmospheric and climate state for the simulation."""
    co2_kg: float = 0.0                      # anthropogenic delta in kg
    co2_ppm: float = CO2_BASELINE_PPM        # absolute, including baseline
    temp_anomaly_k: float = 0.0              # K above pre-industrial mean
    cum_emissions_kg: float = 0.0            # total ever emitted
    cum_absorbed_kg: float = 0.0             # total ever absorbed by sinks
    biome_shift_factor: float = 0.0          # 0..1, fraction of biomes shifted
    sea_level_rise_m: float = 0.0            # cumulative
    bounds_km2: float = 1.0                  # simulated area, for normalization
    forest_cells: int = 0                    # tracked at tick start
    ocean_cells: int = 0
    last_update_tick: int = 0

    # Per-tick stats for the dashboard
    last_emissions_kg: float = 0.0
    last_absorbed_kg: float = 0.0
    last_emission_sources: Dict[str, float] = field(default_factory=dict)

    def update_concentration(self) -> None:
        """Recompute co2_ppm from the running delta and bounds_km2.

        At baseline (co2_kg = 0), concentration sits at CO2_BASELINE_PPM.
        Above that, we add the local anthropogenic ppm-equivalent.
        """
        local_per_km2 = self.co2_kg / max(self.bounds_km2, 1e-3)
        delta_ppm = local_per_km2 / CO2_KG_PER_PPM_LOCAL
        self.co2_ppm = CO2_BASELINE_PPM + max(0.0, delta_ppm)
        # Climate response — log2 ratio times sensitivity.
        ratio = self.co2_ppm / CO2_BASELINE_PPM
        if ratio > 1.0:
            self.temp_anomaly_k = CLIMATE_SENSITIVITY_K * float(np.log2(ratio))
        else:
            self.temp_anomaly_k = 0.0
        # Coarse biome shift heuristic (real models are far more complex).
        self.biome_shift_factor = float(min(1.0, max(0.0,
            (self.temp_anomaly_k - 0.5) / 5.0)))
        # Coarse sea-level rise heuristic.
        if self.temp_anomaly_k > 0:
            self.sea_level_rise_m = float(0.2 * self.temp_anomaly_k ** 1.5)

    def emit(self, kg: float, source: str = "unknown") -> None:
        """Inject kg of CO2 into the atmosphere from a labeled source."""
        if kg <= 0:
            return
        self.co2_kg += kg
        self.cum_emissions_kg += kg
        self.last_emissions_kg += kg
        self.last_emission_sources[source] = self.last_emission_sources.get(source, 0.0) + kg

    def absorb(self, kg: float) -> None:
        """Remove kg of CO2 (forest + ocean sinks)."""
        if kg <= 0:
            return
        absorbed = min(kg, self.co2_kg)  # can't go below baseline
        self.co2_kg -= absorbed
        self.cum_absorbed_kg += absorbed
        self.last_absorbed_kg += absorbed

    def tick(self, dt_s: float, forest_cells: int, ocean_cells: int) -> None:
        """Per-tick natural absorption + concentration update."""
        # Sinks
        sink_kg = (SINK_FOREST_KG_S * forest_cells +
                   SINK_OCEAN_KG_S * ocean_cells) * dt_s
        self.absorb(sink_kg)
        self.forest_cells = int(forest_cells)
        self.ocean_cells = int(ocean_cells)
        self.update_concentration()

    def begin_tick(self) -> None:
        """Reset per-tick counters (called at start of each sim tick)."""
        self.last_emissions_kg = 0.0
        self.last_absorbed_kg = 0.0
        self.last_emission_sources = {}


# ---------------------------------------------------------------------------
# Emission helpers — combustion of fuels in hearths / furnaces.
# Stoichiometry: C + O2 -> CO2 ; for hydrocarbon fuels we use the carbon
# content of the fuel (~50% by mass for dry wood, ~80% for charcoal).
# ---------------------------------------------------------------------------

CARBON_FRACTION = {
    MaterialKind.WOOD: 0.50,
    MaterialKind.CHARCOAL: 0.85,
    MaterialKind.FIBER: 0.45,
    MaterialKind.LEATHER: 0.55,
    MaterialKind.BONE: 0.25,
    MaterialKind.GRAIN: 0.45,
}
CO2_PER_C = 44.0 / 12.0   # mass ratio CO2/C


def combustion_co2_kg(material: MaterialKind, fuel_kg: float) -> float:
    """Return kg of CO2 released by combusting `fuel_kg` of `material`."""
    frac = CARBON_FRACTION.get(material, 0.0)
    return fuel_kg * frac * CO2_PER_C


# ---------------------------------------------------------------------------
# Climate feedback into the world
# ---------------------------------------------------------------------------

def apply_climate_feedback(chunk, atm: Atmosphere) -> None:
    """Adjust a chunk's food_capacity and water based on the climate anomaly.

    Hot biomes shrink, deserts expand, food capacity drops in stressed zones.
    Cold-adapted biomes can briefly improve before collapsing too.
    """
    if atm.temp_anomaly_k <= 0.0:
        return
    anom = atm.temp_anomaly_k
    # Up to 1K: small reduction. Beyond 2K: severe biome stress.
    stress = min(1.0, anom / 5.0)
    chunk.food_capacity = chunk.food_capacity * (1.0 - 0.6 * stress)
    # Sea-level rise: a fraction of land cells below 5m become ocean-flooded.
    if atm.sea_level_rise_m > 1.0:
        flood_mask = chunk.height < (1.0 + atm.sea_level_rise_m)
        chunk.water[flood_mask] = np.maximum(chunk.water[flood_mask], 200.0)
        invalidate_resource_masks(chunk)
