"""Genesis Engine — Wave 3 physiology (ultra-realistic human agents).

Layers a high-fidelity bodily-function model on top of the Phase-4 drives
(hunger / thirst / sleep / fatigue / thermal / pain / stress / loneliness)
already maintained in :class:`engine.agent.AgentRegistry`. Wave 3 adds:

  * **Excretion** — bladder + bowel fill from drinking and eating, must
    be relieved. Unrelieved bladder/bowel inflates ``pain`` and ``stress``.
    Relieving on a cell near a settlement contaminates that cell's water.
  * **Hygiene** — body cleanliness in [0, 1]. Decays slowly with time,
    faster with sweating (high thermal load), faster still with
    excretion close to the body. Restored by bathing on water cells.
    Low hygiene gates several skin / disease branches.
  * **Skin conditions** — sunburn (sun exposure × (1 - melanin)),
    frostbite (cold exposure × (1 - body fat)), parasites
    (low hygiene + agent proximity), dermatitis (allergens × biome).
    Each is a [0, 1] severity scalar with its own decay term.
  * **Communicable diseases** — three pathogens with realistic R0 and
    transmission vectors :
        - ``cholera``  — waterborne. DRINK on a contaminated cell
          (excretion or wound runoff) injects bacterial load.
        - ``flu``      — airborne. Spreads via near-agent proximity in
          enclosed thermal envelopes.
        - ``wound_infection`` — bacterial entry through unhealed
          ``injuries``, multiplied by environmental dirtiness.
  * **Immune system** — strength scalar derived from genome locus +
    age (LifeStage cognitive multiplier as proxy) + nutrition
    (1 - hunger). High immune strength decreases pathogen growth and
    increases clearance. Survivors carry a low-grade persistent
    memory boost (mild immunity) for the same pathogen.

Determinism
-----------
All RNG sampled via :func:`engine.core.prf_rng` keyed on
``["physiology", subsystem, tick, row]``. No ``random.random()``.

Idempotency
-----------
``install_physiology(sim)`` is idempotent. It wraps ``sim.step`` once,
attaches ``sim._physio_fields`` (an instance of
:class:`PhysioFields`), and patches the relevant action handlers so
DRINK / FORAGE / EAT / SEEK_SHELTER feed into the model. Calling it a
second time is a no-op.

Taxonomy tags (per ADR 0005)
----------------------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — physiology is the body
emerging from the world's microclimate, hydrology, diet, etc.
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — multi-step rollouts
respecting domain laws (mass balance on excretion, energy balance on
sunburn, ODE-like growth of pathogen loads).
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"  # arxiv 2604.22748

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import TICK_DT_S, prf_rng
from engine.world import (Biome, CHUNK_SIDE_M, CHUNK_SIZE,
                          invalidate_resource_masks, world_to_cell,
                          world_to_chunk)


# ---------------------------------------------------------------------------
# Calibrated rates (per second of sim time; ticks @ drive_accel scale them)
# ---------------------------------------------------------------------------
# Bladder: average human bladder fills ~250–500 mL over 4–8 h. We pick a
# 4 h fill, so the bladder saturates in 4 × 3600 = 14400 sim-seconds.
BLADDER_FILL_PER_S = 1.0 / (4.0 * 3600.0)
# Bowel: typical 1–2 relief events per day. We pick a 14 h fill.
BOWEL_FILL_PER_S = 1.0 / (14.0 * 3600.0)
# Hygiene decays in ~5 days without bathing.
HYGIENE_DECAY_PER_S = 1.0 / (5.0 * 86400.0)
# Skin: sunburn under unprotected sun on fair skin in ~1 hour real ≈ 3600 s.
SUNBURN_PER_S = 1.0 / 3600.0
SUNBURN_HEAL_PER_S = 1.0 / (7.0 * 86400.0)
# Frostbite: severe in ~30 min at -10 °C for low-fat skin.
FROSTBITE_PER_S = 1.0 / 1800.0
FROSTBITE_HEAL_PER_S = 1.0 / (3.0 * 86400.0)
# Parasites: lice life cycle ~30 days. Grow slow if hygiene < 0.4.
PARASITE_GROWTH_PER_S = 1.0 / (30.0 * 86400.0)
PARASITE_DECAY_PER_S = 1.0 / (10.0 * 86400.0)  # cleared by hygiene
# Dermatitis: 1 week onset under sustained allergen exposure.
DERMATITIS_PER_S = 1.0 / (7.0 * 86400.0)
DERMATITIS_HEAL_PER_S = 1.0 / (14.0 * 86400.0)
# Pathogen growth: cholera doubles in ~3 h in a naive host with no
# immune response. Flu doubles in ~6 h. Wound infection in ~12 h.
PATHOGEN_GROWTH = {
    "cholera": 1.0 / (3.0 * 3600.0),
    "flu":      1.0 / (6.0 * 3600.0),
    "wound":    1.0 / (12.0 * 3600.0),
}
PATHOGEN_CLEAR_BASE_PER_S = 1.0 / (5.0 * 86400.0)
# Transmission radius for airborne (flu) — close proximity, ~2 m.
AIRBORNE_RADIUS_M = 2.0
AIRBORNE_TRANSMISSION_RATE = 0.10
# Cholera shed-into-water per relief event.
CHOLERA_SHED_PER_EVENT = 0.15

# Default fractions consumed per relief action.
BLADDER_RELIEF_FRAC = 0.95
BOWEL_RELIEF_FRAC = 0.92
# Bathing replenishes hygiene up to this cap per tick.
BATHE_GAIN_PER_TICK = 0.20

# Thresholds.
RELIEF_URGE_BLADDER = 0.80
RELIEF_URGE_BOWEL = 0.85
BATHE_TRIGGER = 0.40  # hygiene falls below -> bathe at first opportunity


PATHOGEN_NAMES: Tuple[str, ...] = ("cholera", "flu", "wound")


# ---------------------------------------------------------------------------
# State container
# ---------------------------------------------------------------------------

@dataclass
class PhysioFields:
    """Per-agent physiology side-table. Sized like AgentRegistry.capacity.

    All arrays are ``np.float32`` in [0, 1] (or non-negative scalars
    where noted). Allocated once at install time, indexed by agent row.
    """
    capacity: int

    # Excretion
    bladder: np.ndarray = field(default=None)
    bowel: np.ndarray = field(default=None)
    # Hygiene
    hygiene: np.ndarray = field(default=None)
    # Skin conditions (severity 0-1)
    sunburn: np.ndarray = field(default=None)
    frostbite: np.ndarray = field(default=None)
    parasites: np.ndarray = field(default=None)
    dermatitis: np.ndarray = field(default=None)
    # Pathogen loads
    cholera_load: np.ndarray = field(default=None)
    flu_load: np.ndarray = field(default=None)
    wound_load: np.ndarray = field(default=None)
    # Immune memory (per pathogen, 0 = naive, 1 = sterilising immunity).
    immune_cholera: np.ndarray = field(default=None)
    immune_flu: np.ndarray = field(default=None)
    immune_wound: np.ndarray = field(default=None)
    # Genome-derived traits (rolled at agent registration).
    melanin: np.ndarray = field(default=None)        # 0=fair, 1=very dark
    body_fat: np.ndarray = field(default=None)       # 0..1 normalised
    immune_baseline: np.ndarray = field(default=None)  # innate strength
    # Wave 7 — epidermal melanin response to UV (tanning, days-scale).
    tan_level: np.ndarray = field(default=None)        # [0,1] epidermal
    uv_dose_lifetime: np.ndarray = field(default=None)  # cumulative UV-day units
    # Cumulative counters (diagnostic, no semantic effect).
    relief_events: np.ndarray = field(default=None)
    bathe_events: np.ndarray = field(default=None)
    diseases_caught: np.ndarray = field(default=None)

    # Chunk-level contamination side-table : maps coord -> 0-1 contamination
    # scalar that decays per tick. Populated by relief events near water.
    water_contamination: Dict[Tuple[int, int, int], float] = field(default_factory=dict)

    def __post_init__(self):
        N = self.capacity
        z = lambda: np.zeros(N, dtype=np.float32)
        self.bladder = z(); self.bowel = z()
        self.hygiene = np.full(N, 0.85, dtype=np.float32)
        self.sunburn = z(); self.frostbite = z()
        self.parasites = z(); self.dermatitis = z()
        self.cholera_load = z(); self.flu_load = z(); self.wound_load = z()
        self.immune_cholera = z(); self.immune_flu = z(); self.immune_wound = z()
        # Defaults derived from genome at agent spawn; fallback values here.
        self.melanin = np.full(N, 0.50, dtype=np.float32)
        self.body_fat = np.full(N, 0.20, dtype=np.float32)
        self.immune_baseline = np.full(N, 0.50, dtype=np.float32)
        # Wave 7 — epidermal tan (acquired) + cumulative UV dose.
        self.tan_level = z()
        self.uv_dose_lifetime = z()
        self.relief_events = np.zeros(N, dtype=np.int32)
        self.bathe_events = np.zeros(N, dtype=np.int32)
        self.diseases_caught = np.zeros(N, dtype=np.int32)


# ---------------------------------------------------------------------------
# Genome → trait mapping (called once at install)
# ---------------------------------------------------------------------------

def _seed_traits_from_genome(sim, fields: PhysioFields) -> None:
    """Derive melanin / body fat / immune baseline from each agent's genome.

    Falls back to deterministic prf_rng samples (UUID-based) when no
    ``engine.genome`` data is attached. Pure function over sim state.
    """
    n = sim.agents.n_active
    capacity = sim.agents.capacity
    # Try genome first.
    genome = getattr(sim.agents, "genome", None)
    if genome is not None and hasattr(genome, "values"):
        # Genome is a (capacity, 256) np.ndarray of float32.
        # Map 4 distinct loci to 4 traits (locus ranges chosen to avoid
        # collision with existing personality/lifestage decoders).
        # Locus 120-127 -> melanin; 128-135 -> body_fat; 136-143 -> immune.
        try:
            G = genome.values
            fields.melanin[:n] = np.clip(G[:n, 120:128].mean(axis=1), 0.0, 1.0)
            fields.body_fat[:n] = np.clip(G[:n, 128:136].mean(axis=1), 0.0, 1.0)
            fields.immune_baseline[:n] = np.clip(
                G[:n, 136:144].mean(axis=1), 0.0, 1.0)
            return
        except Exception:
            pass
    # Fallback: prf_rng per row.
    for r in range(n):
        rng = prf_rng(sim.cfg.seed,
                      ["physiology", "init_traits"], [int(r)])
        fields.melanin[r] = float(rng.random())
        fields.body_fat[r] = 0.10 + 0.30 * float(rng.random())
        fields.immune_baseline[r] = 0.30 + 0.50 * float(rng.random())


# ---------------------------------------------------------------------------
# Per-tick subsystems
# ---------------------------------------------------------------------------

def _tick_excretion(sim, fields: PhysioFields) -> None:
    """Bladder + bowel slowly fill independently of agent action.

    Drinking has already injected an additional pulse (see
    ``patch_actions``); this tick advances baseline metabolism.
    """
    n = sim.agents.n_active
    if n == 0:
        return
    accel = float(sim.cfg.drive_accel)
    m = sim.agents.alive[:n]
    fields.bladder[:n][m] = np.clip(
        fields.bladder[:n][m] + BLADDER_FILL_PER_S * accel, 0.0, 1.5)
    fields.bowel[:n][m] = np.clip(
        fields.bowel[:n][m] + BOWEL_FILL_PER_S * accel, 0.0, 1.5)
    # Over-full bladder/bowel feeds pain and stress.
    overflow_b = np.maximum(fields.bladder[:n][m] - 1.0, 0.0)
    overflow_w = np.maximum(fields.bowel[:n][m] - 1.0, 0.0)
    sim.agents.pain[:n][m] = np.clip(
        sim.agents.pain[:n][m] + (overflow_b + overflow_w) * 0.01, 0.0, 1.5)
    sim.agents.stress[:n][m] = np.clip(
        sim.agents.stress[:n][m] + (overflow_b + overflow_w) * 0.005, 0.0, 1.5)


def _tick_hygiene(sim, fields: PhysioFields) -> None:
    """Hygiene decays with time; sweat (thermal) and parasites accelerate."""
    n = sim.agents.n_active
    if n == 0:
        return
    accel = float(sim.cfg.drive_accel)
    m = sim.agents.alive[:n]
    base = HYGIENE_DECAY_PER_S * accel
    extra = (sim.agents.thermal[:n][m] * 0.5
             + fields.parasites[:n][m] * 0.3) * base
    fields.hygiene[:n][m] = np.clip(
        fields.hygiene[:n][m] - (base + extra), 0.0, 1.0)


def _tick_skin(sim, fields: PhysioFields) -> None:
    """Sunburn from prolonged outdoor exposure × low melanin; frostbite
    from cold stress × low body fat; parasites from low hygiene;
    dermatitis from allergens × biome.

    Heat / cold stress are read directly from ``agents.thermal`` (the
    Phase-4 drive already calibrated by ``sim._tick_thermal`` using the
    real ``weather_at`` against the agent's chunk). This avoids a
    bespoke weather probe that risked desync with the sim's clock.
    """
    n = sim.agents.n_active
    if n == 0:
        return
    accel = float(sim.cfg.drive_accel)
    m_alive = sim.agents.alive[:n]
    thermal = sim.agents.thermal[:n]

    # ``thermal`` is in [0, 1] where 0 is comfortable and 1 is critical.
    # Phase-4 makes no distinction between hot- and cold-driven stress,
    # so we use the sign of the agent's chunk weather as a coarse tag.
    # Cheap heuristic : if the world is freezing, treat thermal as cold;
    # otherwise as hot. We sample one weather call via the sim helper
    # below; if it fails, fall back to "warm climate" defaults.
    is_freezing = False
    try:
        thermal_field = getattr(sim, "_realism_thermal_field", None)
        if thermal_field is not None:
            # Reality Engine seasons are best source when installed.
            season = getattr(thermal_field, "current_season_temp_c", None)
            if season is not None:
                is_freezing = float(season) < 0.0
    except Exception:
        pass

    # --- Sample per-agent UV index from meteorology (Wave 7). If absent,
    # fall back to thermal-proxy logic. UV is read from the agent's
    # current chunk's CellMeteorology.
    from engine.world import world_to_chunk
    meteo_state = getattr(sim, "_meteo_state", None)
    uv_per_agent = np.zeros(n, dtype=np.float32)
    if meteo_state is not None:
        meteo_chunks = meteo_state.chunk_meteo
        for r in np.flatnonzero(m_alive):
            px = float(sim.agents.pos[r, 0])
            py = float(sim.agents.pos[r, 1])
            ccoord = world_to_chunk(px, py)
            cell = meteo_chunks.get(ccoord)
            if cell is not None:
                uv_per_agent[r] = cell.uv_index

    # --- Tanning (Wave 7) : epidermal melanin response to UV exposure.
    # Real biology : melanocyte stimulation at UVI > ~3 produces visible
    # tan over days. Decays with weeks of low exposure. Tan reduces
    # sunburn susceptibility (effective melanin = melanin + 0.4 * tan).
    if meteo_state is not None:
        # Growth where UV > 3.
        uv_gain = np.where(uv_per_agent > 3.0,
                           (uv_per_agent - 3.0) / 8.0, 0.0).astype(np.float32)
        tan_grow_rate = 1.0 / (5.0 * 86400.0) * accel  # 5-day tan-up
        tan_decay_rate = 1.0 / (30.0 * 86400.0) * accel  # 30-day fade
        delta_tan = uv_gain * tan_grow_rate - tan_decay_rate
        fields.tan_level[:n][m_alive] = np.clip(
            fields.tan_level[:n][m_alive] + delta_tan[m_alive], 0.0, 1.0)
        # Cumulative dose tracking (UVI-day units).
        fields.uv_dose_lifetime[:n][m_alive] += (
            uv_per_agent[m_alive] * accel * TICK_DT_S / 86400.0)
        effective_melanin = fields.melanin[:n] + 0.4 * fields.tan_level[:n]
    else:
        effective_melanin = fields.melanin[:n]

    # --- Sunburn — driven by UV when meteo installed, otherwise thermal proxy.
    if meteo_state is not None:
        # UV > 6 burns fair skin within an hour outdoor.
        susceptibility = (1.0 - effective_melanin) * SUNBURN_PER_S * accel * 0.10
        # 0 below UVI 1, linear ramp to 1 above UVI 8.
        uv_factor = np.clip((uv_per_agent - 1.0) / 7.0, 0.0, 1.5)
        delta = susceptibility * uv_factor
    else:
        hot_factor = np.clip(thermal, 0.0, 1.0) * (0.0 if is_freezing else 1.0)
        susceptibility = (1.0 - effective_melanin) * SUNBURN_PER_S * accel * 0.10
        delta = susceptibility * hot_factor
    fields.sunburn[:n][m_alive] = np.clip(
        fields.sunburn[:n][m_alive] + delta[m_alive], 0.0, 1.0)
    fields.sunburn[:n][m_alive] = np.maximum(
        fields.sunburn[:n][m_alive] - SUNBURN_HEAL_PER_S * accel, 0.0)
    sim.agents.pain[:n][m_alive] = np.clip(
        sim.agents.pain[:n][m_alive] + fields.sunburn[:n][m_alive] * 0.001 * accel,
        0.0, 1.5)

    # --- Frostbite — only when world flagged cold + thermal > 0.5.
    if is_freezing:
        cold_factor = np.clip(thermal - 0.5, 0.0, 0.5) * 2.0
        susceptibility = (1.0 - fields.body_fat[:n]) * FROSTBITE_PER_S * accel * 0.10
        fields.frostbite[:n][m_alive] = np.clip(
            fields.frostbite[:n][m_alive]
            + (susceptibility * cold_factor)[m_alive], 0.0, 1.0)
    fields.frostbite[:n][m_alive] = np.maximum(
        fields.frostbite[:n][m_alive] - FROSTBITE_HEAL_PER_S * accel, 0.0)
    sim.agents.pain[:n][m_alive] = np.clip(
        sim.agents.pain[:n][m_alive] + fields.frostbite[:n][m_alive] * 0.002 * accel,
        0.0, 1.5)

    # --- Parasites — grow if hygiene < 0.4, decay otherwise.
    low_hyg = fields.hygiene[:n] < 0.4
    grow = m_alive & low_hyg
    clean = m_alive & ~low_hyg
    fields.parasites[:n][grow] = np.clip(
        fields.parasites[:n][grow] + PARASITE_GROWTH_PER_S * accel, 0.0, 1.0)
    fields.parasites[:n][clean] = np.maximum(
        fields.parasites[:n][clean] - PARASITE_DECAY_PER_S * accel, 0.0)
    sim.agents.stress[:n][m_alive] = np.clip(
        sim.agents.stress[:n][m_alive] + fields.parasites[:n][m_alive] * 0.001 * accel,
        0.0, 1.5)

    # --- Dermatitis — proxy: agents in dense vegetation chunks accumulate
    # allergens. We can't poll each agent's chunk cheaply here; instead we
    # tie it loosely to high parasites/low hygiene as a stand-in for
    # "exposed irritated skin". Cheap and useful as a proxy.
    aggravator = (1.0 - fields.hygiene[:n]) * fields.parasites[:n]
    fields.dermatitis[:n][m_alive] = np.clip(
        fields.dermatitis[:n][m_alive]
        + aggravator[m_alive] * DERMATITIS_PER_S * accel,
        0.0, 1.0)
    fields.dermatitis[:n][m_alive] = np.maximum(
        fields.dermatitis[:n][m_alive] - DERMATITIS_HEAL_PER_S * accel, 0.0)


def _tick_pathogens(sim, fields: PhysioFields) -> None:
    """Pathogen loads grow per Arrhenius-like ODE, immune clears them.

    Pure-numpy per-pathogen loop. Each agent's effective immune strength
    is ``immune_baseline + memory_for_this_pathogen + (1 - hunger) * 0.3``.
    """
    n = sim.agents.n_active
    if n == 0:
        return
    accel = float(sim.cfg.drive_accel)
    m = sim.agents.alive[:n]

    base_immune = (
        fields.immune_baseline[:n]
        + (1.0 - sim.agents.hunger[:n]) * 0.3
        - sim.agents.stress[:n] * 0.2
    )
    base_immune = np.clip(base_immune, 0.0, 1.5)

    loads = {
        "cholera": fields.cholera_load,
        "flu":     fields.flu_load,
        "wound":   fields.wound_load,
    }
    memory = {
        "cholera": fields.immune_cholera,
        "flu":     fields.immune_flu,
        "wound":   fields.immune_wound,
    }
    for name, arr in loads.items():
        growth = PATHOGEN_GROWTH[name] * accel
        mem = memory[name][:n]
        load = arr[:n]
        # Logistic growth: load' = r * load * (1 - load) - clear * load.
        # If load == 0 (no infection), nothing happens — pathogens require
        # a seed event (ingestion, airborne contact, wound).
        susceptibility = np.maximum(0.0, 1.2 - base_immune - mem)
        eff_g = growth * susceptibility * load * (1.0 - load)
        eff_clear = PATHOGEN_CLEAR_BASE_PER_S * accel * (
            0.5 + base_immune + mem) * load
        new = load + eff_g - eff_clear
        new = np.maximum(new, 0.0)
        arr[:n][m] = new[m]

        # Survivors gain immune memory proportional to load (saturating).
        gain = np.minimum(load * 0.0005 * accel, 0.02)
        memory[name][:n][m] = np.clip(memory[name][:n][m] + gain[m], 0.0, 1.0)

    # Pathogen load contributes to pain, stress, and reduces vitality
    # for the heaviest infection. Coefficients tuned so a load of 0.5
    # costs about 0.05 vitality per tick at accel=1500 (~20 ticks TTD).
    worst = np.maximum.reduce([
        fields.cholera_load[:n],
        fields.flu_load[:n],
        fields.wound_load[:n],
    ])
    sim.agents.pain[:n][m] = np.clip(
        sim.agents.pain[:n][m] + worst[m] * 0.0008 * accel, 0.0, 1.5)
    sim.agents.vitality[:n][m] = np.clip(
        sim.agents.vitality[:n][m] - worst[m] * 0.00005 * accel, 0.0, 1.0)


def _tick_airborne_transmission(sim, fields: PhysioFields) -> None:
    """Flu spreads to near agents (within AIRBORNE_RADIUS_M).

    O(n × k) where k = average near-agent count. Uses the spatial grid
    attached to ``sim`` when available; otherwise skipped silently.
    """
    n = sim.agents.n_active
    if n < 2:
        return
    grid = getattr(sim, "spatial_grid", None) or getattr(sim, "_grid", None)
    if grid is None:
        return
    alive = sim.agents.alive[:n]
    flu = fields.flu_load[:n]
    immune = fields.immune_flu[:n]
    base_imm = fields.immune_baseline[:n]
    accel = float(sim.cfg.drive_accel)
    rate = AIRBORNE_TRANSMISSION_RATE * accel

    for row in np.flatnonzero(alive & (flu > 0.1)):
        px = float(sim.agents.pos[row, 0])
        py = float(sim.agents.pos[row, 1])
        try:
            cands = grid.query_disk(px, py, AIRBORNE_RADIUS_M, exclude_row=int(row))
        except Exception:
            continue
        for j in cands:
            if not alive[j]:
                continue
            # Receiver susceptibility.
            sus = max(0.0, 1.0 - base_imm[j] - immune[j])
            transmit = flu[row] * sus * rate
            if transmit > 1e-4:
                gained = min(transmit, 0.05)
                fields.flu_load[j] = float(min(1.0, fields.flu_load[j] + gained))
                if fields.flu_load[j] >= 0.1:
                    fields.diseases_caught[j] += 1


def _tick_contamination_decay(sim, fields: PhysioFields) -> None:
    """Decay any per-chunk water contamination so old pollution fades."""
    accel = float(sim.cfg.drive_accel)
    decay = 1.0 / (3.0 * 86400.0) * accel  # 3-day half-life-ish
    keys_to_drop = []
    for coord, level in fields.water_contamination.items():
        new = level - decay
        if new <= 1e-3:
            keys_to_drop.append(coord)
        else:
            fields.water_contamination[coord] = new
    for k in keys_to_drop:
        fields.water_contamination.pop(k, None)


def _tick_auto_relief_and_bathe(sim, fields: PhysioFields) -> None:
    """Autonomous bathroom + bath behaviour.

    Determinism: every effect routes through prf_rng keyed on tick + row.
    No random.random(). The decision is gated on need + opportunity:

      - Bladder >= RELIEF_URGE_BLADDER ➜ excrete urine. If the current
        chunk has water > 5 within 1 cell, contaminate it (cholera).
        Otherwise no contamination.
      - Bowel >= RELIEF_URGE_BOWEL    ➜ excrete feces. Same logic but
        with a stronger contamination yield.
      - Hygiene < BATHE_TRIGGER and the agent's current cell has water
        > 50 ➜ bathe. Reset hygiene to 0.95 and reduce parasites by 40 %.
    """
    n = sim.agents.n_active
    if n == 0:
        return
    streamer = sim.streamer
    for row in np.flatnonzero(sim.agents.alive[:n]):
        px = float(sim.agents.pos[row, 0])
        py = float(sim.agents.pos[row, 1])
        chunk_c = world_to_chunk(px, py)
        chunk = streamer.cache.get(chunk_c)
        if chunk is None:
            continue
        cx, cy = world_to_cell(px, py, chunk_c)

        # --- Bladder relief
        if fields.bladder[row] >= RELIEF_URGE_BLADDER:
            fields.bladder[row] = float(fields.bladder[row]) * (1.0 - BLADDER_RELIEF_FRAC)
            fields.relief_events[row] += 1
            # Contaminate if relief happens near water (within 2 cells).
            y0 = max(0, cy - 2); y1 = min(CHUNK_SIZE, cy + 3)
            x0 = max(0, cx - 2); x1 = min(CHUNK_SIZE, cx + 3)
            if chunk.water[y0:y1, x0:x1].max() > 5.0:
                prev = fields.water_contamination.get(chunk_c, 0.0)
                new_c = min(1.0, prev + CHOLERA_SHED_PER_EVENT * 0.5)
                fields.water_contamination[chunk_c] = new_c

        # --- Bowel relief
        if fields.bowel[row] >= RELIEF_URGE_BOWEL:
            fields.bowel[row] = float(fields.bowel[row]) * (1.0 - BOWEL_RELIEF_FRAC)
            fields.relief_events[row] += 1
            y0 = max(0, cy - 2); y1 = min(CHUNK_SIZE, cy + 3)
            x0 = max(0, cx - 2); x1 = min(CHUNK_SIZE, cx + 3)
            if chunk.water[y0:y1, x0:x1].max() > 5.0:
                prev = fields.water_contamination.get(chunk_c, 0.0)
                new_c = min(1.0, prev + CHOLERA_SHED_PER_EVENT)
                fields.water_contamination[chunk_c] = new_c

        # --- Bathe — only on cells that are deeply watery (lake / river).
        if (fields.hygiene[row] < BATHE_TRIGGER
                and float(chunk.water[cy, cx]) > 50.0):
            fields.hygiene[row] = min(
                1.0, float(fields.hygiene[row]) + BATHE_GAIN_PER_TICK)
            fields.parasites[row] = float(fields.parasites[row]) * 0.6
            fields.bathe_events[row] += 1


# ---------------------------------------------------------------------------
# Action hooks (DRINK / FORAGE / EAT) — patched at install time
# ---------------------------------------------------------------------------

# Module-level dispatch table : id(agents) -> (sim, fields). The patch
# applied to ``engine.cognition.apply_decision`` is **installed exactly
# once** for the lifetime of the Python process and routes each call to
# the side-table that matches the ``agents`` argument. This allows
# multiple Simulation instances to live in the same interpreter (the
# smoke test builds two for determinism comparison) without
# cross-contaminating their physiology state.
_PHYSIO_DISPATCH: Dict[int, Tuple[object, "PhysioFields"]] = {}


def _physio_global_wrapper(agents, row, decision, streamer, tick):
    """Stacked wrapper around the previous ``apply_decision``.

    Reads the ``id(agents)`` and looks up the appropriate sim/fields
    pair in :data:`_PHYSIO_DISPATCH`. Updates physiology side-state
    after delegating to the original (or previously wrapped) handler.
    """
    import engine.cognition as _cog
    from engine.agent import ActionKind

    inner = getattr(_cog, "_physio_inner_apply_decision", None)
    if inner is None:
        return None
    pair = _PHYSIO_DISPATCH.get(id(agents))
    if pair is None:
        # No physiology attached to this AgentRegistry — pass through.
        return inner(agents, row, decision, streamer, tick)
    sim, fields = pair
    prev_thirst = float(agents.thirst[row])
    prev_hunger = float(agents.hunger[row])
    prev_injuries = float(agents.injuries[row])
    events = inner(agents, row, decision, streamer, tick)
    post_thirst = float(agents.thirst[row])
    post_hunger = float(agents.hunger[row])
    post_injuries = float(agents.injuries[row])
    act = int(decision.action)
    if act == int(ActionKind.DRINK) and post_thirst < prev_thirst:
        delta = prev_thirst - post_thirst
        fields.bladder[row] = min(
            1.2, float(fields.bladder[row]) + delta * 0.6)
        px = float(agents.pos[row, 0])
        py = float(agents.pos[row, 1])
        chunk_c = world_to_chunk(px, py)
        cont = fields.water_contamination.get(chunk_c, 0.0)
        if cont > 0.05:
            rng = prf_rng(sim.cfg.seed,
                          ["physiology", "cholera_ingest"],
                          [int(tick), int(row)])
            if rng.random() < cont * 0.5:
                fields.cholera_load[row] = float(min(
                    1.0, fields.cholera_load[row] + cont * 0.2))
    if act in (int(ActionKind.FORAGE), int(ActionKind.EAT)):
        if post_hunger < prev_hunger:
            delta = prev_hunger - post_hunger
            fields.bowel[row] = min(
                1.2, float(fields.bowel[row]) + delta * 0.5)
    if post_injuries > prev_injuries + 0.01:
        seed = (1.0 - fields.hygiene[row]) * 0.10
        if seed > 0.0:
            fields.wound_load[row] = float(min(
                1.0, fields.wound_load[row] + seed))
    return events


def _patch_drink_and_eat(sim, fields: PhysioFields) -> None:
    """Register ``(sim, fields)`` in the dispatch table and install the
    global wrapper exactly once.

    Phase-4 sims dispatch actions through ``engine.cognition.apply_decision``;
    earlier integrations (``sim_5cd_integration``) already wrap that name.
    We install one process-wide wrapper that reads ``id(agents)`` to
    route updates to the correct physiology side-table — safe across
    multiple sims in the same process.
    """
    import engine.cognition as _cog
    import engine.sim as _sim_mod

    _PHYSIO_DISPATCH[id(sim.agents)] = (sim, fields)

    if getattr(_cog, "_physio_inner_apply_decision", None) is None:
        # First installation — capture the *current* apply_decision (which
        # may itself be a sim_5cd_integration wrapper) as the inner.
        _cog._physio_inner_apply_decision = _cog.apply_decision
        _cog.apply_decision = _physio_global_wrapper
        if hasattr(_sim_mod, "apply_decision"):
            _sim_mod.apply_decision = _physio_global_wrapper


# ---------------------------------------------------------------------------
# Public reporter
# ---------------------------------------------------------------------------

def physiology_state(sim) -> Dict[str, object]:
    """Snapshot consumed by ``/api/physiology_state`` and HUD."""
    fields: Optional[PhysioFields] = getattr(sim, "_physio_fields", None)
    if fields is None:
        return {}
    n = sim.agents.n_active
    if n == 0:
        return {
            "n_active": 0,
            "means": {},
            "disease": {},
            "events": {},
        }
    alive = sim.agents.alive[:n]
    n_alive = int(alive.sum())
    if n_alive == 0:
        return {"n_active": n, "alive": 0}

    def _mean(arr):
        return float(arr[:n][alive].mean()) if n_alive else 0.0

    def _max(arr):
        return float(arr[:n][alive].max()) if n_alive else 0.0

    # Effective melanin = genetic baseline + 0.4 * tan_level. Visual skin
    # tone of agents = effective_melanin in [0..1].
    eff_melanin_arr = fields.melanin[:n] + 0.4 * fields.tan_level[:n]
    eff_mean = float(eff_melanin_arr[alive].mean()) if n_alive else 0.0
    return {
        "n_active": int(n),
        "alive": int(n_alive),
        "means": {
            "bladder":   _mean(fields.bladder),
            "bowel":     _mean(fields.bowel),
            "hygiene":   _mean(fields.hygiene),
            "sunburn":   _mean(fields.sunburn),
            "frostbite": _mean(fields.frostbite),
            "parasites": _mean(fields.parasites),
            "dermatitis": _mean(fields.dermatitis),
            "melanin":   _mean(fields.melanin),
            "tan_level": _mean(fields.tan_level),
            "effective_melanin": round(eff_mean, 4),
            "uv_dose_lifetime": _mean(fields.uv_dose_lifetime),
            "body_fat":  _mean(fields.body_fat),
        },
        "disease": {
            "cholera_mean": _mean(fields.cholera_load),
            "cholera_max":  _max(fields.cholera_load),
            "flu_mean":     _mean(fields.flu_load),
            "flu_max":      _max(fields.flu_load),
            "wound_mean":   _mean(fields.wound_load),
            "wound_max":    _max(fields.wound_load),
            "infected_cholera": int(
                ((fields.cholera_load[:n] > 0.1) & alive).sum()),
            "infected_flu": int(
                ((fields.flu_load[:n] > 0.1) & alive).sum()),
            "infected_wound": int(
                ((fields.wound_load[:n] > 0.1) & alive).sum()),
        },
        "events": {
            "relief_total": int(fields.relief_events[:n][alive].sum()),
            "bathe_total":  int(fields.bathe_events[:n][alive].sum()),
            "diseases_caught_total": int(
                fields.diseases_caught[:n][alive].sum()),
        },
        "contamination_chunks": len(fields.water_contamination),
    }


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------

def install_physiology(sim) -> PhysioFields:
    """Attach Wave 3 physiology to a Simulation. Idempotent.

    Returns the side-table for caller introspection.
    """
    existing: Optional[PhysioFields] = getattr(sim, "_physio_fields", None)
    if existing is not None:
        return existing

    fields = PhysioFields(capacity=sim.agents.capacity)
    sim._physio_fields = fields
    _seed_traits_from_genome(sim, fields)
    _patch_drink_and_eat(sim, fields)

    orig_step = sim.step

    def wrapped_step():
        orig_step()
        _tick_excretion(sim, fields)
        _tick_hygiene(sim, fields)
        _tick_skin(sim, fields)
        _tick_pathogens(sim, fields)
        _tick_airborne_transmission(sim, fields)
        _tick_contamination_decay(sim, fields)
        _tick_auto_relief_and_bathe(sim, fields)

    sim.step = wrapped_step  # type: ignore[assignment]
    return fields


# ---------------------------------------------------------------------------
# Persistence — P1 save / load round-trip support
# ---------------------------------------------------------------------------

_PHYSIO_ARRAY_FIELDS = (
    "bladder", "bowel", "hygiene",
    "sunburn", "frostbite", "parasites", "dermatitis",
    "cholera_load", "flu_load", "wound_load",
    "immune_cholera", "immune_flu", "immune_wound",
    "melanin", "body_fat", "immune_baseline",
    "tan_level", "uv_dose_lifetime",          # Wave 7 — epidermal + cumulative UV
    "relief_events", "bathe_events", "diseases_caught",
)


def save_physio_state(sim, target_dir: str) -> bool:
    """Persist :class:`PhysioFields` to ``target_dir/physiology.npz``.

    Returns ``True`` if state was written. Stays silent when no physiology
    has been installed on the sim (just returns False).
    """
    import os
    fields = getattr(sim, "_physio_fields", None)
    if fields is None:
        return False
    n = sim.agents.n_active
    payload = {"n_active": np.array([n], dtype=np.int64),
               "capacity": np.array([fields.capacity], dtype=np.int64)}
    for f in _PHYSIO_ARRAY_FIELDS:
        arr = getattr(fields, f, None)
        if arr is not None:
            payload[f] = np.asarray(arr)
    # water_contamination is a Dict[(int,int,int) → float]. Flatten to two
    # parallel arrays for safe serialisation.
    if fields.water_contamination:
        keys = list(fields.water_contamination.keys())
        coords = np.array(keys, dtype=np.int32)
        vals = np.array(
            [fields.water_contamination[k] for k in keys], dtype=np.float32)
        payload["contam_coords"] = coords
        payload["contam_values"] = vals
    np.savez_compressed(os.path.join(target_dir, "physiology.npz"), **payload)
    return True


def load_physio_state(sim, target_dir: str) -> bool:
    """Reinstate :class:`PhysioFields` from ``target_dir/physiology.npz``.

    Calls ``install_physiology(sim)`` if not already done, then restores
    every per-agent array. ``True`` on success, ``False`` if no file.
    """
    import os
    path = os.path.join(target_dir, "physiology.npz")
    if not os.path.isfile(path):
        return False
    fields = install_physiology(sim)
    data = np.load(path, allow_pickle=False)
    for f in _PHYSIO_ARRAY_FIELDS:
        if f in data.files:
            arr = getattr(fields, f, None)
            if arr is None:
                continue
            src = data[f]
            try:
                arr[:src.shape[0]] = src
            except Exception:
                pass
    if "contam_coords" in data.files and "contam_values" in data.files:
        coords = data["contam_coords"]
        vals = data["contam_values"]
        fields.water_contamination = {
            tuple(int(c) for c in coords[i]): float(vals[i])
            for i in range(len(vals))
        }
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "PhysioFields",
    "install_physiology",
    "physiology_state",
    "save_physio_state",
    "load_physio_state",
    "PATHOGEN_NAMES",
]
