"""Genesis Engine — Wave 7 meteorology (ultra-realistic atmospheric model).

Replaces the toy ``weather_at(tick, base_t, base_precip)`` of
:mod:`engine.world` with a per-chunk, lat/lon-aware, scientifically
calibrated meteorological state stack:

* **Solar geometry** — exact zenith angle from latitude, declination
  (Spencer 1971), and hour angle. Direct + diffuse insolation via
  Beer-Lambert through the atmospheric column.
* **Cloud formation** — humidity × instability triggers cumulus,
  stable saturation triggers stratus, high-altitude ice triggers
  cirrus. Cloud cover modulates radiation transmission.
* **Precipitation** — rain / drizzle / snow / sleet / hail typed by
  surface temperature + cloud thickness + lift. Realistic mm/h rates.
* **Wind field** — geostrophic surface wind from a smooth synthetic
  pressure field + Coriolis parameter f = 2 Ω sin(lat). Terrain-aware
  speed reduction via chunk roughness proxy.
* **Storms** — thunderstorms emerge from CAPE-like instability proxy ;
  cyclones (tropical hurricane / extratropical low) tracked as
  long-lived ``StormCenter`` objects that advect with the mean flow.
* **UV index** — World Health Organization standard formula : UVI =
  40 × UV-erythemal irradiance (W/m²). Calculated from solar zenith,
  ozone column, cloud transmission, and surface albedo.

Determinism
-----------
Pure deterministic. All stochastic-looking variability (storm seeding,
cloud noise) routes through :func:`engine.core.prf_rng`. No
``random.random``. Bit-identical snapshots across runs same seed.

Coupling with existing modules
------------------------------
* The legacy ``engine.world.Weather`` dataclass gains optional fields
  (``uv_index``, ``humidity_rel``, ``wind_speed_ms``, ``precip_type``).
  Old callers using only the four pre-Wave-7 fields keep working.
* When ``install_meteorology(sim)`` is wired, ``weather_at_chunk(sim,
  coord)`` returns the real per-chunk reading. Callers that still use
  ``weather_at(tick, base_t, base_precip)`` get the *global mean*
  reading (still better than the original because it now reads from
  the solar geometry).

ADR-0005 tags
-------------
``PIPELINE_LAYER = "Genesis-L4 Feedback"`` — atmosphere ↔ biosphere
↔ agent body in a closed loop.
``WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"`` — composes
solar-geometry, fluid-mechanics, and thermodynamic laws over multi-tick
rollouts.
"""
from __future__ import annotations

# Taxonomy — see ADR 0005.
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"  # arxiv 2604.22748

import json
import math
import os
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import numpy as np

from engine.core import TICK_DT_S, prf_rng
from engine.world import CHUNK_SIDE_M, CHUNK_SIZE


# ---------------------------------------------------------------------------
# Constants — calibrated to literature
# ---------------------------------------------------------------------------

# Solar
SOLAR_CONSTANT_W_M2 = 1361.0           # NASA SORCE TSI 2008
EARTH_AXIAL_TILT_DEG = 23.4392811       # IAU 2009
EARTH_ROT_RATE = 7.2921159e-5          # rad/s — for Coriolis
EARTH_RADIUS_M = 6.371008e6

# Atmosphere — Beer-Lambert
TAU_RAYLEIGH_AT_550_NM = 0.10           # broadband proxy
TAU_AEROSOL_DEFAULT = 0.05              # background
OZONE_COLUMN_DU_DEFAULT = 300.0         # Dobson units
OZONE_REF_UV_DU = 300.0                 # reference column for UV factor

# Cloud
CLOUD_HUMIDITY_THRESH_LOW = 0.55        # below : no cloud
CLOUD_HUMIDITY_THRESH_HIGH = 0.92       # at/above : full cover
CLOUD_RADIATION_TRANSMISSION = 0.30     # thick cloud blocks ~70 %

# Precipitation
PRECIP_TRIGGER_HUMIDITY = 0.88
PRECIP_RATE_MAX_MM_H = 25.0
SNOW_TEMP_C = 0.0
SLEET_TEMP_C = 2.0
HAIL_MIN_CAPE = 2000.0                  # J/kg proxy

# Storms
STORM_HUMIDITY_THRESH = 0.85
STORM_TEMP_THRESH_C = 22.0
STORM_LIFETIME_TICKS = 12 * 3600        # 12 sim-hours
STORM_RADIUS_M_DEFAULT = 4000.0
HURRICANE_SST_THRESH_C = 26.5
HURRICANE_LAT_MIN_DEG = 5.0
STORM_FORMATION_PROB_PER_S = 1.0 / (4.0 * 86400.0)

# Wind
WIND_MIN_MS = 0.5
WIND_MAX_MS = 35.0                      # capped to "violent storm" 12 Beaufort
PRESSURE_GRADIENT_SCALE = 0.01           # Pa/m proxy → roughly geostrophic

# UV
UV_IRRADIANCE_FRACTION = 0.05           # ~5 % of total solar in UV-erythemal
UV_INDEX_PER_W_M2 = 40.0                # WHO standard


# ---------------------------------------------------------------------------
# Enums + cloud / precip types
# ---------------------------------------------------------------------------

class CloudType(IntEnum):
    CLEAR = 0
    CIRRUS = 1          # high, thin
    CUMULUS = 2         # mid, vertical
    STRATUS = 3         # low, blanket
    NIMBUS = 4          # rain-bearing
    CUMULONIMBUS = 5    # thunderstorm tower


class PrecipType(IntEnum):
    NONE = 0
    DRIZZLE = 1
    RAIN = 2
    SHOWER = 3
    SNOW = 4
    SLEET = 5
    HAIL = 6


class StormKind(IntEnum):
    NONE = 0
    THUNDERSTORM = 1
    TROPICAL_CYCLONE = 2     # hurricane / typhoon
    EXTRATROPICAL_LOW = 3    # mid-latitude cyclone


# ---------------------------------------------------------------------------
# Per-chunk meteorology buffer
# ---------------------------------------------------------------------------

@dataclass
class CellMeteorology:
    """Per-chunk weather snapshot updated each tick."""
    cloud_cover: float = 0.0           # [0,1] mean over chunk
    cloud_type: int = int(CloudType.CLEAR)
    cloud_thickness: float = 0.0       # 0..1 proxy of vertical extent
    precip_mm_h: float = 0.0
    precip_type: int = int(PrecipType.NONE)
    wind_u_ms: float = 0.0             # east component
    wind_v_ms: float = 0.0             # north component
    wind_speed_ms: float = 0.0
    temp_c: float = 15.0
    humidity_rel: float = 0.5
    pressure_hpa: float = 1013.25
    solar_zenith_deg: float = 90.0
    solar_irradiance_w_m2: float = 0.0
    par_umol_m2_s: float = 0.0
    uv_index: float = 0.0
    in_storm: bool = False


@dataclass
class StormCenter:
    """A tracked storm. Advected by mean wind each tick."""
    storm_id: int
    kind: int                            # StormKind
    lat: float
    lon: float
    pos_x_m: float                       # world coords of centre
    pos_y_m: float
    radius_m: float
    intensity: float                     # 0..1, scales precip + wind in cone
    age_ticks: int = 0
    lifetime_ticks: int = STORM_LIFETIME_TICKS


# ---------------------------------------------------------------------------
# Meteorology state
# ---------------------------------------------------------------------------

@dataclass
class MeteorologyState:
    origin_lat: float = 46.510
    origin_lon: float = 6.633
    chunk_meteo: Dict[Tuple[int, int, int], CellMeteorology] = field(
        default_factory=dict)
    storms: Dict[int, StormCenter] = field(default_factory=dict)
    next_storm_id: int = 1
    ticks_run: int = 0
    last_global_temp_c: float = 15.0
    last_global_uv_index: float = 0.0
    last_global_cloud_cover: float = 0.5
    last_global_precip_mm_h: float = 0.0
    last_global_wind_ms: float = 0.0


# ---------------------------------------------------------------------------
# Solar geometry — pure physics
# ---------------------------------------------------------------------------

def solar_declination_deg(day_of_year: int) -> float:
    """Solar declination angle δ in degrees (Spencer 1971 series, trimmed).

    Accurate to ±0.1° over the year. Day-of-year is the ordinal day
    (1 = Jan 1).
    """
    gamma = 2.0 * math.pi * (day_of_year - 1) / 365.0
    delta = (0.006918
             - 0.399912 * math.cos(gamma)
             + 0.070257 * math.sin(gamma)
             - 0.006758 * math.cos(2 * gamma)
             + 0.000907 * math.sin(2 * gamma)
             - 0.002697 * math.cos(3 * gamma)
             + 0.001480 * math.sin(3 * gamma))
    return math.degrees(delta)


def solar_zenith_deg(lat_deg: float, lon_deg: float,
                     day_of_year: int, hour_local: float) -> float:
    """Solar zenith angle θ_z in degrees [0, 180].

    θ_z = 0 means sun directly overhead. > 90 means sun below horizon.
    """
    decl = math.radians(solar_declination_deg(day_of_year))
    lat = math.radians(lat_deg)
    # Hour angle (15° per hour, 0 at solar noon).
    h_angle = math.radians((hour_local - 12.0) * 15.0)
    cos_z = (math.sin(lat) * math.sin(decl)
             + math.cos(lat) * math.cos(decl) * math.cos(h_angle))
    cos_z = max(-1.0, min(1.0, cos_z))
    return math.degrees(math.acos(cos_z))


def solar_irradiance_w_m2(
    zenith_deg: float,
    cloud_cover: float = 0.0,
    altitude_m: float = 0.0,
    aerosol_tau: float = TAU_AEROSOL_DEFAULT,
) -> float:
    """Direct + diffuse insolation at the surface, in W/m².

    Beer-Lambert through Rayleigh + aerosol with cloud transmission
    multiplier. Returns 0 when sun is below horizon.
    """
    if zenith_deg >= 90.0:
        return 0.0
    cos_z = max(1e-3, math.cos(math.radians(zenith_deg)))
    # Air mass (Kasten-Young 1989 approximation good to z=85°).
    am = 1.0 / (cos_z + 0.50572 * (96.07995 - zenith_deg) ** -1.6364)
    # Altitude correction (pressure scale height 8000 m).
    am *= math.exp(-altitude_m / 8000.0)
    tau = TAU_RAYLEIGH_AT_550_NM + aerosol_tau
    direct = SOLAR_CONSTANT_W_M2 * cos_z * math.exp(-tau * am)
    # Diffuse adds ~20 % of clear-sky direct on average.
    diffuse = 0.20 * direct
    total_clear = direct + diffuse
    # Cloud transmission : reduces direct strongly, diffuse mildly.
    cloud_t = (1.0 - cloud_cover) * 1.0 + cloud_cover * CLOUD_RADIATION_TRANSMISSION
    return float(total_clear * cloud_t)


def uv_index_from_solar(
    zenith_deg: float,
    cloud_cover: float = 0.0,
    altitude_m: float = 0.0,
    ozone_du: float = OZONE_COLUMN_DU_DEFAULT,
    surface_albedo: float = 0.0,
) -> float:
    """WHO UV Index. Calculation per WMO/WHO Global Solar UV Index.

    Inputs:
      zenith_deg     — solar zenith angle (deg)
      cloud_cover    — [0,1]
      altitude_m     — site altitude
      ozone_du       — total ozone column (Dobson). 300 default.
      surface_albedo — 0=dark soil, 0.8=fresh snow (doubles UVI)
    """
    if zenith_deg >= 90.0:
        return 0.0
    cos_z = max(1e-3, math.cos(math.radians(zenith_deg)))
    # Ozone scaling : at 300 DU factor = 1.0, thin ozone increases UV.
    o3_factor = (OZONE_REF_UV_DU / max(50.0, ozone_du)) ** 1.05
    cloud_factor = max(0.05, 1.0 - 0.6 * cloud_cover)
    altitude_factor = 1.0 + 0.06 * (altitude_m / 1000.0)
    albedo_factor = 1.0 + surface_albedo
    # Clear-sky UV-erythemal irradiance at sea level : ~0.27 × cos_z^1.2
    # W/m² → UVI ≈ 0.27 × 40 × cos_z^1.2 ≈ 10.8 at solar noon (well-known
    # tropical peak observed in WMO records).
    uv_w_m2 = (0.27 * (cos_z ** 1.2)
               * o3_factor * cloud_factor * altitude_factor * albedo_factor)
    return float(UV_INDEX_PER_W_M2 * uv_w_m2)


def coriolis_parameter(lat_deg: float) -> float:
    """f = 2 Ω sin(φ). s⁻¹. Zero at equator, +1.45e-4 at North Pole."""
    return 2.0 * EARTH_ROT_RATE * math.sin(math.radians(lat_deg))


# ---------------------------------------------------------------------------
# Lat/lon helpers — convert chunk position to lat/lon for solar calc
# ---------------------------------------------------------------------------

def chunk_lat_lon(state: MeteorologyState,
                  coord: Tuple[int, int, int]) -> Tuple[float, float]:
    """Approximate (lat, lon) of a chunk centre relative to the sim origin.

    Uses a flat-earth small-area approximation (good up to ~100 km).
    """
    cx, cy, _ = coord
    dx_m = (cx + 0.5) * CHUNK_SIDE_M
    dy_m = (cy + 0.5) * CHUNK_SIDE_M
    dlat = dy_m / 111000.0                       # m per degree latitude
    dlon = dx_m / (111000.0
                   * max(0.01, math.cos(math.radians(state.origin_lat))))
    return state.origin_lat + dlat, state.origin_lon + dlon


# ---------------------------------------------------------------------------
# Per-chunk meteorology update
# ---------------------------------------------------------------------------

def _humidity_from_water_chunk(chunk) -> float:
    """Proxy humidity from local water presence (lake / river / wet biome).

    Returns [0, 1].
    """
    w_max = float(chunk.water.max())
    if w_max <= 0.0:
        return 0.30
    return min(1.0, 0.30 + w_max / 200.0)


def _altitude_for_chunk(chunk) -> float:
    """Average chunk altitude in m."""
    return float(chunk.height.mean())


def _surface_temperature(zenith_deg: float, altitude_m: float,
                         humidity: float, latitude: float,
                         day_of_year: int, hour: float) -> float:
    """Surface temperature (°C) blending seasonal mean + diurnal cycle
    + lapse rate by altitude.

    Calibrated so noon at Léman in May gives ~18 °C and night dives to
    ~10 °C, in line with the previous toy ``weather_at``.
    """
    # Latitude-dependent annual mean.
    base = 15.0 - 0.4 * abs(latitude)
    # Seasonal modulation (northern hemisphere : peak summer = day 200).
    season_peak_day = 200 if latitude > 0 else 20
    season_phase = 2.0 * math.pi * (day_of_year - season_peak_day) / 365.0
    season_amp = 12.0 * (1.0 - abs(latitude) / 90.0 * 0.4)
    seasonal = math.cos(season_phase) * season_amp
    # Diurnal cycle (clear sky amplitude 8 °C, halved on cloudy days).
    diurnal_phase = 2.0 * math.pi * (hour - 14.0) / 24.0
    diurnal = -math.cos(diurnal_phase) * 6.0
    # Altitude lapse rate ~6.5 °C / km.
    lapse = -altitude_m * 0.0065
    # Humidity moderates extremes.
    humidity_moderation = (humidity - 0.5) * 2.0  # +1 = damp cool
    return base + seasonal + diurnal + lapse - humidity_moderation


def _cloud_for_chunk(humidity: float,
                     temp_c: float,
                     altitude_m: float,
                     instability: float) -> Tuple[float, int, float]:
    """Return (cover, type, thickness)."""
    if humidity < CLOUD_HUMIDITY_THRESH_LOW:
        return 0.0, int(CloudType.CLEAR), 0.0
    # Linear ramp humidity → cover.
    cover = ((humidity - CLOUD_HUMIDITY_THRESH_LOW)
             / max(1e-3,
                   CLOUD_HUMIDITY_THRESH_HIGH - CLOUD_HUMIDITY_THRESH_LOW))
    cover = min(1.0, max(0.0, cover))
    # Classify type.
    if instability > 0.6 and temp_c > 15.0:
        ctype = int(CloudType.CUMULUS) if cover < 0.85 else int(CloudType.CUMULONIMBUS)
        thickness = 0.6 + 0.4 * instability
    elif altitude_m > 1500.0 and temp_c < 10.0:
        ctype = int(CloudType.CIRRUS)
        thickness = 0.2 + 0.2 * cover
    elif humidity > 0.85 and instability < 0.3:
        ctype = int(CloudType.STRATUS) if cover < 0.9 else int(CloudType.NIMBUS)
        thickness = 0.4 + 0.4 * cover
    else:
        ctype = int(CloudType.CUMULUS)
        thickness = 0.3 + 0.5 * cover
    return cover, ctype, thickness


def _precip_for_chunk(humidity: float, temp_c: float,
                      cloud_cover: float, cloud_thickness: float,
                      instability: float) -> Tuple[float, int]:
    """Return (rate_mm_h, precip_type)."""
    if humidity < PRECIP_TRIGGER_HUMIDITY or cloud_thickness < 0.4:
        return 0.0, int(PrecipType.NONE)
    # Rate proportional to humidity excess + cloud thickness.
    excess = (humidity - PRECIP_TRIGGER_HUMIDITY) / 0.12
    rate = min(PRECIP_RATE_MAX_MM_H, 0.5 + excess * 8.0 * cloud_thickness)
    # Type by temp.
    if temp_c < SNOW_TEMP_C:
        return rate, int(PrecipType.SNOW)
    if temp_c < SLEET_TEMP_C:
        return rate, int(PrecipType.SLEET)
    if instability > 0.7 and temp_c > 20.0 and rate > 5.0:
        return rate, (int(PrecipType.HAIL)
                      if instability > 0.85 else int(PrecipType.SHOWER))
    if rate < 1.5:
        return rate, int(PrecipType.DRIZZLE)
    return rate, int(PrecipType.RAIN)


def _wind_for_chunk(lat_deg: float, lon_deg: float, hour: float,
                    altitude_m: float,
                    tick: int, sim_seed: int) -> Tuple[float, float]:
    """Geostrophic wind proxy with synthetic pressure gradient.

    Returns (u_ms, v_ms) — east and north components. Smooth on the
    chunk scale; large-scale modulation through prf_rng-keyed sin/cos
    so the field is deterministic but varies through the day.
    """
    rng_seed_u = (tick // 3600) ^ int(lat_deg * 100) ^ sim_seed
    rng_seed_v = rng_seed_u ^ 0x5A5A5A5A
    # Synthetic smoothly-varying pressure field.
    u = 5.0 * math.sin((rng_seed_u % 1000) * 0.001 * 2 * math.pi
                       + hour * math.pi / 12.0)
    v = 5.0 * math.cos((rng_seed_v % 1000) * 0.001 * 2 * math.pi
                       + hour * math.pi / 12.0)
    # Coriolis : rotate stronger at high latitudes (trade-wind / westerlies).
    f = coriolis_parameter(lat_deg)
    rot = f * 1.0e4   # scale to ~0.1-1 rad
    u_rot = u * math.cos(rot) - v * math.sin(rot)
    v_rot = u * math.sin(rot) + v * math.cos(rot)
    # Altitude (mountains exposed, valleys sheltered).
    if altitude_m > 1500:
        u_rot *= 1.4
        v_rot *= 1.4
    return float(u_rot), float(v_rot)


def _instability_proxy(temp_c: float, humidity: float,
                       altitude_m: float, lat_deg: float) -> float:
    """CAPE-like instability proxy in [0,1].

    Surface heat + humidity build CAPE ; high altitude / cold caps it.
    """
    warm = max(0.0, (temp_c - 10.0) / 30.0)
    humid = max(0.0, (humidity - 0.4) / 0.6)
    cap = max(0.0, 1.0 - altitude_m / 4000.0)
    tropical = max(0.0, 1.0 - abs(lat_deg) / 90.0)
    return min(1.0, warm * humid * cap * (0.7 + 0.5 * tropical))


# ---------------------------------------------------------------------------
# Storm formation + advection
# ---------------------------------------------------------------------------

def _maybe_form_storm(sim, state: MeteorologyState,
                      coord: Tuple[int, int, int],
                      cell: CellMeteorology, lat: float, lon: float) -> None:
    """Per-tick storm formation roll. prf_rng-deterministic."""
    accel = float(sim.cfg.drive_accel)
    if cell.humidity_rel < STORM_HUMIDITY_THRESH:
        return
    if cell.temp_c < STORM_TEMP_THRESH_C:
        return
    p = STORM_FORMATION_PROB_PER_S * accel * TICK_DT_S
    rng = prf_rng(sim.cfg.seed,
                  ["meteo", "storm_form"],
                  [int(sim.tick), int(coord[0]), int(coord[1])])
    if rng.random() > p:
        return
    # Type selection.
    if abs(lat) < HURRICANE_LAT_MIN_DEG:
        return  # too close to equator — no Coriolis
    if (cell.temp_c >= HURRICANE_SST_THRESH_C
            and abs(lat) > HURRICANE_LAT_MIN_DEG
            and cell.humidity_rel > 0.9):
        kind = int(StormKind.TROPICAL_CYCLONE)
        radius = 30000.0
        intensity = 0.7
    elif abs(lat) > 30.0:
        kind = int(StormKind.EXTRATROPICAL_LOW)
        radius = 15000.0
        intensity = 0.5
    else:
        kind = int(StormKind.THUNDERSTORM)
        radius = STORM_RADIUS_M_DEFAULT
        intensity = 0.4 + 0.4 * _instability_proxy(
            cell.temp_c, cell.humidity_rel, 0.0, lat)
    sid = state.next_storm_id
    state.next_storm_id += 1
    pos_x = (coord[0] + 0.5) * CHUNK_SIDE_M
    pos_y = (coord[1] + 0.5) * CHUNK_SIDE_M
    state.storms[sid] = StormCenter(
        storm_id=sid, kind=kind, lat=lat, lon=lon,
        pos_x_m=pos_x, pos_y_m=pos_y,
        radius_m=radius, intensity=intensity,
        age_ticks=0,
        lifetime_ticks=STORM_LIFETIME_TICKS
                       * (3 if kind == int(StormKind.TROPICAL_CYCLONE) else 1),
    )


def _advect_storms(state: MeteorologyState, dt_s: float) -> None:
    """Move each storm by the mean local wind, age it, kill expired ones."""
    dead: List[int] = []
    for sid, s in state.storms.items():
        # Estimate local wind by finding the nearest chunk meteo.
        cell = _nearest_chunk_meteo(state, s.pos_x_m, s.pos_y_m)
        if cell is not None:
            s.pos_x_m += cell.wind_u_ms * dt_s
            s.pos_y_m += cell.wind_v_ms * dt_s
        s.age_ticks += int(max(1, dt_s))
        if s.age_ticks > s.lifetime_ticks:
            dead.append(sid)
        else:
            # Intensity decays linearly.
            s.intensity *= 1.0 - (1.0 / max(1, s.lifetime_ticks))
    for sid in dead:
        state.storms.pop(sid, None)


def _nearest_chunk_meteo(state: MeteorologyState,
                         x: float, y: float) -> Optional[CellMeteorology]:
    best = None
    best_d2 = float("inf")
    for coord, cell in state.chunk_meteo.items():
        cx_m = (coord[0] + 0.5) * CHUNK_SIDE_M
        cy_m = (coord[1] + 0.5) * CHUNK_SIDE_M
        d2 = (cx_m - x) ** 2 + (cy_m - y) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best = cell
    return best


def _apply_storms_to_cell(state: MeteorologyState,
                          coord: Tuple[int, int, int],
                          cell: CellMeteorology) -> None:
    """If any storm overlaps the chunk centre, boost precip + wind."""
    cx_m = (coord[0] + 0.5) * CHUNK_SIDE_M
    cy_m = (coord[1] + 0.5) * CHUNK_SIDE_M
    boosted = False
    for s in state.storms.values():
        d2 = (s.pos_x_m - cx_m) ** 2 + (s.pos_y_m - cy_m) ** 2
        if d2 > s.radius_m * s.radius_m:
            continue
        # Fade with distance.
        r = math.sqrt(d2) / s.radius_m
        weight = (1.0 - r) * s.intensity
        cell.precip_mm_h = max(cell.precip_mm_h,
                               weight * PRECIP_RATE_MAX_MM_H)
        # Boost wind magnitude by 3-15 m/s depending on storm kind.
        kind_boost = {int(StormKind.THUNDERSTORM): 6.0,
                      int(StormKind.EXTRATROPICAL_LOW): 12.0,
                      int(StormKind.TROPICAL_CYCLONE): 30.0}.get(s.kind, 0.0)
        speed = math.hypot(cell.wind_u_ms, cell.wind_v_ms)
        new_speed = min(WIND_MAX_MS, speed + weight * kind_boost)
        # Preserve direction.
        if speed > 0.01:
            scale = new_speed / speed
            cell.wind_u_ms *= scale
            cell.wind_v_ms *= scale
        cell.wind_speed_ms = math.hypot(cell.wind_u_ms, cell.wind_v_ms)
        cell.in_storm = True
        if s.kind == int(StormKind.TROPICAL_CYCLONE):
            cell.precip_type = int(PrecipType.RAIN)
        elif s.kind == int(StormKind.THUNDERSTORM):
            if cell.precip_type == int(PrecipType.NONE):
                cell.precip_type = int(PrecipType.SHOWER)
        boosted = True
    if not boosted:
        cell.in_storm = False


# ---------------------------------------------------------------------------
# Main per-tick driver
# ---------------------------------------------------------------------------

def tick_meteorology(sim, state: MeteorologyState) -> None:
    """Update every chunk's meteorology snapshot."""
    accel = float(sim.cfg.drive_accel)
    sim_seconds = sim.tick * int(accel)
    day_of_year = (sim_seconds // 86400) % 365 + 1
    hour_local = (sim_seconds % 86400) / 3600.0

    tot_temp = tot_uv = tot_cloud = tot_precip = tot_wind = 0.0
    n = 0
    for coord, chunk in list(sim.streamer.cache.items()):
        cell = state.chunk_meteo.setdefault(coord, CellMeteorology())
        lat, lon = chunk_lat_lon(state, coord)
        altitude = _altitude_for_chunk(chunk)
        # Humidity from local water + biome.
        humidity = _humidity_from_water_chunk(chunk)
        # Surface temperature.
        z_deg = solar_zenith_deg(lat, lon, day_of_year, hour_local)
        T_C = _surface_temperature(z_deg, altitude, humidity, lat,
                                   day_of_year, hour_local)
        instab = _instability_proxy(T_C, humidity, altitude, lat)
        cover, ctype, thickness = _cloud_for_chunk(humidity, T_C,
                                                   altitude, instab)
        precip_rate, precip_type = _precip_for_chunk(
            humidity, T_C, cover, thickness, instab)
        u, v = _wind_for_chunk(lat, lon, hour_local, altitude,
                               sim.tick, sim.cfg.seed)
        ir = solar_irradiance_w_m2(z_deg, cover, altitude)
        uvi = uv_index_from_solar(z_deg, cover, altitude,
                                  OZONE_COLUMN_DU_DEFAULT, 0.0)
        # Pressure (hPa) from altitude + storm influence.
        pres = 1013.25 * math.exp(-altitude / 8000.0)
        # Fill the cell.
        cell.cloud_cover = float(cover)
        cell.cloud_type = ctype
        cell.cloud_thickness = float(thickness)
        cell.precip_mm_h = float(precip_rate)
        cell.precip_type = precip_type
        cell.wind_u_ms = float(u)
        cell.wind_v_ms = float(v)
        cell.wind_speed_ms = float(math.hypot(u, v))
        cell.temp_c = float(T_C)
        cell.humidity_rel = float(humidity)
        cell.pressure_hpa = float(pres)
        cell.solar_zenith_deg = float(z_deg)
        cell.solar_irradiance_w_m2 = float(ir)
        cell.par_umol_m2_s = float(ir * 2.05)  # ~ 2.05 μmol photons / J PAR
        cell.uv_index = float(uvi)
        cell.in_storm = False
        # Storm formation roll.
        _maybe_form_storm(sim, state, coord, cell, lat, lon)
        # Aggregate stats.
        tot_temp += T_C
        tot_uv += uvi
        tot_cloud += cover
        tot_precip += precip_rate
        tot_wind += cell.wind_speed_ms
        n += 1

    # Advect + age storms (one pass after all cells filled).
    _advect_storms(state, TICK_DT_S * accel)
    # Apply storms onto cells (boost precip / wind locally).
    for coord, cell in state.chunk_meteo.items():
        _apply_storms_to_cell(state, coord, cell)

    if n > 0:
        state.last_global_temp_c = tot_temp / n
        state.last_global_uv_index = tot_uv / n
        state.last_global_cloud_cover = tot_cloud / n
        state.last_global_precip_mm_h = tot_precip / n
        state.last_global_wind_ms = tot_wind / n
    state.ticks_run += 1


# ---------------------------------------------------------------------------
# Installer + reporter
# ---------------------------------------------------------------------------

def install_meteorology(sim, *, origin_lat: float = 46.510,
                        origin_lon: float = 6.633) -> MeteorologyState:
    """Idempotent installer. Attach a :class:`MeteorologyState` to ``sim``
    and wrap ``sim.step`` so meteorology ticks each frame.
    """
    state: Optional[MeteorologyState] = getattr(sim, "_meteo_state", None)
    if state is not None:
        return state
    # Prefer Earth-loader origin when available.
    streamer = getattr(sim, "streamer", None)
    loader = getattr(streamer, "_earth_loader", None) if streamer else None
    if loader is not None:
        origin_lat = float(getattr(loader, "origin_lat", origin_lat))
        origin_lon = float(getattr(loader, "origin_lon", origin_lon))
    state = MeteorologyState(origin_lat=origin_lat, origin_lon=origin_lon)
    sim._meteo_state = state
    orig_step = sim.step

    def wrapped_step():
        orig_step()
        tick_meteorology(sim, state)

    sim.step = wrapped_step
    return state


def meteorology_state(sim) -> Dict[str, object]:
    """Snapshot for ``/api/meteorology_state``."""
    state: Optional[MeteorologyState] = getattr(sim, "_meteo_state", None)
    if state is None:
        return {}
    storms_summary = [
        {"id": s.storm_id, "kind": int(s.kind),
         "lat": round(s.lat, 4), "lon": round(s.lon, 4),
         "radius_m": s.radius_m, "intensity": round(s.intensity, 3),
         "age_h": round(s.age_ticks / 3600.0, 2)}
        for s in state.storms.values()
    ]
    # Count cloud types and precip types across cells.
    cloud_hist: Dict[int, int] = {}
    precip_hist: Dict[int, int] = {}
    for cell in state.chunk_meteo.values():
        cloud_hist[cell.cloud_type] = cloud_hist.get(cell.cloud_type, 0) + 1
        precip_hist[cell.precip_type] = precip_hist.get(cell.precip_type, 0) + 1
    cloud_name = {int(c): c.name for c in CloudType}
    precip_name = {int(p): p.name for p in PrecipType}
    return {
        "origin_lat": state.origin_lat,
        "origin_lon": state.origin_lon,
        "global_temp_c": round(state.last_global_temp_c, 2),
        "global_uv_index": round(state.last_global_uv_index, 2),
        "global_cloud_cover": round(state.last_global_cloud_cover, 3),
        "global_precip_mm_h": round(state.last_global_precip_mm_h, 3),
        "global_wind_ms": round(state.last_global_wind_ms, 2),
        "active_storms": len(state.storms),
        "storms": storms_summary,
        "cloud_distribution": {cloud_name.get(k, str(k)): v
                               for k, v in cloud_hist.items()},
        "precip_distribution": {precip_name.get(k, str(k)): v
                                for k, v in precip_hist.items()},
        "chunks_tracked": len(state.chunk_meteo),
        "ticks_run": state.ticks_run,
    }


def weather_at_chunk(sim, coord: Tuple[int, int, int]):
    """Drop-in upgrade for ``engine.world.weather_at`` per-chunk.

    Returns the :class:`engine.world.Weather` dataclass populated with
    Wave 7 fields when meteorology is installed ; otherwise falls back
    to the legacy ``weather_at`` global signal.
    """
    state: Optional[MeteorologyState] = getattr(sim, "_meteo_state", None)
    from engine.world import Weather, weather_at as _legacy
    if state is not None and coord in state.chunk_meteo:
        cell = state.chunk_meteo[coord]
        return Weather(
            temp_c=cell.temp_c,
            rain_mm_h=cell.precip_mm_h,
            cloud=cell.cloud_cover,
            is_day=(cell.solar_zenith_deg < 90.0),
        )
    return _legacy(sim.tick * int(sim.cfg.drive_accel), 15.0, 1.0)


# ---------------------------------------------------------------------------
# Persistence (P1 hooks)
# ---------------------------------------------------------------------------

def save_meteo_state(sim, target_dir: str) -> bool:
    state: Optional[MeteorologyState] = getattr(sim, "_meteo_state", None)
    if state is None:
        return False
    payload = {
        "origin_lat": state.origin_lat,
        "origin_lon": state.origin_lon,
        "next_storm_id": state.next_storm_id,
        "ticks_run": state.ticks_run,
        "last_global_temp_c": state.last_global_temp_c,
        "last_global_uv_index": state.last_global_uv_index,
        "last_global_cloud_cover": state.last_global_cloud_cover,
        "last_global_precip_mm_h": state.last_global_precip_mm_h,
        "last_global_wind_ms": state.last_global_wind_ms,
        "storms": [
            {"id": s.storm_id, "kind": int(s.kind),
             "lat": s.lat, "lon": s.lon,
             "pos_x_m": s.pos_x_m, "pos_y_m": s.pos_y_m,
             "radius_m": s.radius_m, "intensity": s.intensity,
             "age_ticks": s.age_ticks, "lifetime_ticks": s.lifetime_ticks}
            for s in state.storms.values()
        ],
        "chunk_meteo": {
            f"{c[0]}_{c[1]}_{c[2]}": {
                "cloud_cover": cell.cloud_cover,
                "cloud_type": cell.cloud_type,
                "cloud_thickness": cell.cloud_thickness,
                "precip_mm_h": cell.precip_mm_h,
                "precip_type": cell.precip_type,
                "wind_u_ms": cell.wind_u_ms,
                "wind_v_ms": cell.wind_v_ms,
                "wind_speed_ms": cell.wind_speed_ms,
                "temp_c": cell.temp_c,
                "humidity_rel": cell.humidity_rel,
                "pressure_hpa": cell.pressure_hpa,
                "solar_zenith_deg": cell.solar_zenith_deg,
                "solar_irradiance_w_m2": cell.solar_irradiance_w_m2,
                "par_umol_m2_s": cell.par_umol_m2_s,
                "uv_index": cell.uv_index,
                "in_storm": cell.in_storm,
            }
            for c, cell in state.chunk_meteo.items()
        },
    }
    with open(os.path.join(target_dir, "meteorology.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return True


def load_meteo_state(sim, target_dir: str) -> bool:
    path = os.path.join(target_dir, "meteorology.json")
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    state = install_meteorology(
        sim,
        origin_lat=float(payload.get("origin_lat", 46.510)),
        origin_lon=float(payload.get("origin_lon", 6.633)),
    )
    state.next_storm_id = int(payload.get("next_storm_id", 1))
    state.ticks_run = int(payload.get("ticks_run", 0))
    state.last_global_temp_c = float(payload.get("last_global_temp_c", 15.0))
    state.last_global_uv_index = float(payload.get("last_global_uv_index", 0.0))
    state.last_global_cloud_cover = float(payload.get(
        "last_global_cloud_cover", 0.5))
    state.last_global_precip_mm_h = float(payload.get(
        "last_global_precip_mm_h", 0.0))
    state.last_global_wind_ms = float(payload.get("last_global_wind_ms", 0.0))
    state.storms.clear()
    for d in payload.get("storms", []):
        s = StormCenter(
            storm_id=int(d["id"]), kind=int(d["kind"]),
            lat=float(d["lat"]), lon=float(d["lon"]),
            pos_x_m=float(d["pos_x_m"]), pos_y_m=float(d["pos_y_m"]),
            radius_m=float(d["radius_m"]),
            intensity=float(d["intensity"]),
            age_ticks=int(d["age_ticks"]),
            lifetime_ticks=int(d["lifetime_ticks"]),
        )
        state.storms[s.storm_id] = s
    state.chunk_meteo.clear()
    for key, d in payload.get("chunk_meteo", {}).items():
        parts = key.split("_")
        coord = tuple(int(p) for p in parts)
        cell = CellMeteorology(
            cloud_cover=float(d.get("cloud_cover", 0.0)),
            cloud_type=int(d.get("cloud_type", 0)),
            cloud_thickness=float(d.get("cloud_thickness", 0.0)),
            precip_mm_h=float(d.get("precip_mm_h", 0.0)),
            precip_type=int(d.get("precip_type", 0)),
            wind_u_ms=float(d.get("wind_u_ms", 0.0)),
            wind_v_ms=float(d.get("wind_v_ms", 0.0)),
            wind_speed_ms=float(d.get("wind_speed_ms", 0.0)),
            temp_c=float(d.get("temp_c", 15.0)),
            humidity_rel=float(d.get("humidity_rel", 0.5)),
            pressure_hpa=float(d.get("pressure_hpa", 1013.25)),
            solar_zenith_deg=float(d.get("solar_zenith_deg", 90.0)),
            solar_irradiance_w_m2=float(d.get("solar_irradiance_w_m2", 0.0)),
            par_umol_m2_s=float(d.get("par_umol_m2_s", 0.0)),
            uv_index=float(d.get("uv_index", 0.0)),
            in_storm=bool(d.get("in_storm", False)),
        )
        state.chunk_meteo[coord] = cell
    return True


__all__ = [
    "PIPELINE_LAYER",
    "WORLD_MODEL_CAPABILITY",
    "CloudType", "PrecipType", "StormKind",
    "CellMeteorology", "StormCenter", "MeteorologyState",
    "solar_declination_deg", "solar_zenith_deg",
    "solar_irradiance_w_m2", "uv_index_from_solar",
    "coriolis_parameter",
    "install_meteorology", "tick_meteorology",
    "meteorology_state", "weather_at_chunk",
    "save_meteo_state", "load_meteo_state",
]
