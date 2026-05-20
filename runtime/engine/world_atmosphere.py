"""Genesis Engine — Wave 41 world atmosphere (day/night + seasons + weather).

Ajoute la couche visuelle ATMOSPHÈRE par-dessus les renderers existants
(Wave 27 top-down + Wave 36 isometric). Calcule :

- **Cycle jour/nuit** : solar altitude/azimuth depuis `sim.tick × accel`
  + latitude → équation astronomique standard. Couleurs ciel
  sunset/day/twilight/night.
- **Saisons** : day_of_year depuis sim.tick → coefficient saisonnier
  (été = saturé, hiver = grisé bleuté).
- **Neige accumulée** : cells où T moyen < -2 °C + précip > seuil →
  overlay blanc.
- **Couverture nuageuse** : lue depuis `engine.meteorology` si présent.
- **Brouillard** : haute humidité + faible vent.

Post-processeur stateless : reçoit un RGB d'un renderer existant et
le modifie en place selon l'état atmosphérique calculé à partir de
`sim.tick`. Aucune mutation de sim, pure-function over (rgb, atmosphere).

Equations astronomiques (calibrées à la Terre)
----------------------------------------------

```
day_of_year(sim_seconds)  = (sim_seconds // 86400) % 365
hour_of_day(sim_seconds)  = (sim_seconds % 86400) / 3600

declination_deg ≈ 23.44 × sin(2π × (day - 80) / 365)
hour_angle_deg  = (hour - 12) × 15
solar_alt_deg   = asin(sin(lat)·sin(decl) + cos(lat)·cos(decl)·cos(hour_angle))
solar_azim_deg  = atan2(sin(hour_angle), cos(hour_angle)·sin(lat) - tan(decl)·cos(lat))
```

Determinism
-----------

Aucun RNG. Tout dérive analytiquement de `sim.tick` + `lat` + `drive_accel`.
Bit-identique pour les mêmes args.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np


PIPELINE_LAYER = "Genesis-L5 Observer"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


# ---------------------------------------------------------------------------
# Solar state
# ---------------------------------------------------------------------------

@dataclass
class SolarState:
    """Astronomical solar position at a given sim tick + latitude.

    All angles in degrees. ``altitude_deg`` < 0 = sun below horizon
    (night).
    """
    day_of_year: int = 0
    hour_of_day: float = 12.0
    declination_deg: float = 0.0
    altitude_deg: float = 90.0
    azimuth_deg: float = 180.0
    is_day: bool = True
    is_twilight: bool = False        # -6° < altitude < 0°
    season_factor: float = 0.0       # -1 (mi-hiver) → +1 (mi-été)


def compute_solar_state(sim_tick: int,
                          *,
                          latitude_deg: float = 46.5,
                          drive_accel: float = 1500.0
                          ) -> SolarState:
    """Compute solar position at a sim tick.

    ``drive_accel`` is sim-seconds per real tick (Genesis default 1500).
    1 sim-year = 365 × 86400 sim-seconds = 31_536_000.

    Pure-function — same args → same output.
    """
    sim_seconds = int(sim_tick) * float(drive_accel)
    day_of_year = int((sim_seconds // 86400.0) % 365.0)
    hour_of_day = float((sim_seconds % 86400.0) / 3600.0)
    # Declination : 23.44° tilt × sin(2π × (day - 80) / 365).
    decl = 23.44 * math.sin(2.0 * math.pi * (day_of_year - 80) / 365.0)
    # Hour angle : 15° per hour from noon.
    hour_angle = (hour_of_day - 12.0) * 15.0
    lat_rad = math.radians(latitude_deg)
    decl_rad = math.radians(decl)
    ha_rad = math.radians(hour_angle)
    sin_alt = (math.sin(lat_rad) * math.sin(decl_rad)
                + math.cos(lat_rad) * math.cos(decl_rad) * math.cos(ha_rad))
    sin_alt = max(-1.0, min(1.0, sin_alt))
    alt = math.degrees(math.asin(sin_alt))
    # Azimuth.
    cos_lat = math.cos(lat_rad)
    azim_y = math.sin(ha_rad)
    azim_x = (math.cos(ha_rad) * math.sin(lat_rad)
                - math.tan(decl_rad) * cos_lat)
    azim = math.degrees(math.atan2(azim_y, azim_x))
    azim = (azim + 360.0) % 360.0
    is_day = alt > 0.0
    is_twilight = -6.0 < alt <= 0.0
    # Season factor : +1 at midsummer (day ~172), -1 at midwinter (day ~355).
    season_factor = math.sin(2.0 * math.pi * (day_of_year - 80) / 365.0)
    return SolarState(
        day_of_year=day_of_year,
        hour_of_day=hour_of_day,
        declination_deg=decl,
        altitude_deg=alt,
        azimuth_deg=azim,
        is_day=is_day,
        is_twilight=is_twilight,
        season_factor=season_factor,
    )


# ---------------------------------------------------------------------------
# Sky color (per-pixel ambient)
# ---------------------------------------------------------------------------

def rayleigh_sky_rgb(solar: SolarState) -> Tuple[int, int, int]:
    """Physically motivated sky colour (Rayleigh scattering approximation).

    Blue dominates at high solar elevation; red/orange at low sun; dark
    blue-black at night. Complements the piecewise ``sky_color_from_solar``.
    """
    alt = solar.altitude_deg
    if alt < -6.0:
        return (12, 16, 40)
    # Air mass ~ 1/sin(alt) capped.
    sin_alt = max(0.05, math.sin(math.radians(max(alt, 0.1))))
    air_mass = min(12.0, 1.0 / sin_alt)
    # Rayleigh: I_blue / I_red ~ (lambda_red/lambda_blue)^4 ≈ (700/475)^4 ≈ 5.5
    tau = 0.12 * air_mass
    trans_b = math.exp(-tau * 1.0)
    trans_r = math.exp(-tau * 5.5)
    if alt <= 0.0:
        tw = max(0.0, (alt + 6.0) / 6.0)
        base = (12, 16, 40)
        dusk = (90, 75, 110)
        return (
            int(round(base[0] + (dusk[0] - base[0]) * tw)),
            int(round(base[1] + (dusk[1] - base[1]) * tw)),
            int(round(base[2] + (dusk[2] - base[2]) * tw)),
        )
    r = int(round(135 * trans_r + 80 * (1 - trans_r)))
    g = int(round(160 * trans_r + 100 * (1 - trans_r)))
    b = int(round(220 * trans_b + 140 * (1 - trans_b)))
    return (min(255, r), min(255, g), min(255, b))


def aces_tone_map(rgb: np.ndarray, exposure: float = 1.0) -> np.ndarray:
    """Approximate ACES filmic tone mapping on float RGB in [0, 255].

    No external deps — Narkowicz fit of ACES RRT+ODT.
    """
    x = np.clip(rgb.astype(np.float32) * (exposure / 255.0), 0.0, None)
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    mapped = np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0)
    return (mapped * 255.0).astype(np.float32)


def henyey_greenstein_phase(cos_theta: float, g: float = 0.76) -> float:
    """Henyey-Greenstein phase function P(cos θ) for aerosol scattering.

    ``g`` ≈ 0.76 forward-scatters sunlight (typical haze). Deterministic.
    """
    g = float(np.clip(g, -0.99, 0.99))
    denom = (1.0 + g * g - 2.0 * g * cos_theta) ** 1.5
    return (1.0 - g * g) / (4.0 * math.pi * max(denom, 1e-6))


def column_ray_march_transmittance(
        solar: SolarState,
        *,
        column_steps: int = 8,
        optical_depth_scale: float = 0.35,
        asymmetry_g: float = 0.76,
        humidity: float = 0.5,
) -> float:
    """Light transmittance along a vertical column (cheap multi-scatter proxy).

    Integrates Beer-Lambert extinction with HG-weighted forward scatter.
    Returns transmittance in [0.05, 1.0]. Same inputs → same output.
    """
    steps = max(2, int(column_steps))
    alt_rad = math.radians(max(solar.altitude_deg, -6.0))
    mu = max(0.05, math.sin(alt_rad))
    tau_base = optical_depth_scale * (1.0 + float(humidity))
    trans = 1.0
    for k in range(1, steps + 1):
        z_frac = k / steps
        tau_layer = tau_base * z_frac / mu
        cos_theta = mu * (1.0 - 0.15 * z_frac)
        phase = henyey_greenstein_phase(cos_theta, g=asymmetry_g)
        trans *= math.exp(-tau_layer) * (0.85 + 0.15 * phase)
    return float(np.clip(trans, 0.05, 1.0))


def atmospheric_fog_factor(solar: SolarState,
                             *,
                             humidity: float = 0.5,
                             altitude_m: float = 200.0) -> float:
    """Fog strength in [0, 1] from humidity, elevation, solar angle."""
    h = float(np.clip(humidity, 0.0, 1.0))
    # Higher humidity + low sun → more fog.
    sun = max(0.0, min(1.0, solar.altitude_deg / 30.0))
    elev = float(np.clip(1.0 - altitude_m / 3000.0, 0.0, 1.0))
    # Exponential falloff with altitude (scale height ~1.2 km).
    elev_factor = float(np.exp(-altitude_m / 1200.0))
    return float(np.clip(h * (1.0 - sun) * 0.55 * elev_factor + elev * 0.12,
                        0.0, 0.62))


def sky_color_from_solar(solar: SolarState, *, physical: bool = True) -> Tuple[int, int, int]:
    """Return the dominant sky colour for the current solar altitude.

    Mapping :
      altitude > 30  : day sky    (135, 180, 220)
      altitude 5..30 : late day   (190, 175, 165)
      altitude 0..5  : sunset     (240, 130, 80)
      altitude -6..0 : civil dusk (90, 75, 110)
      altitude < -6  : night      (15, 18, 35)

    If ``physical=True`` (default), blends with :func:`rayleigh_sky_rgb`.
    """
    if physical:
        rx, ry, rz = rayleigh_sky_rgb(solar)
        px, py, pz = _sky_color_piecewise(solar)
        # Blend: more physical at day, piecewise at extreme sunset.
        w = 0.65 if solar.altitude_deg > 0.0 else 0.4
        return (
            int(round(rx * w + px * (1 - w))),
            int(round(ry * w + py * (1 - w))),
            int(round(rz * w + pz * (1 - w))),
        )
    return _sky_color_piecewise(solar)


def _sky_color_piecewise(solar: SolarState) -> Tuple[int, int, int]:
    a = solar.altitude_deg
    if a > 30.0:
        return (135, 180, 220)
    if a > 5.0:
        t = (a - 5.0) / 25.0  # 0..1
        # Linear blend late day → day.
        return (int(round(190 + (135 - 190) * t)),
                int(round(175 + (180 - 175) * t)),
                int(round(165 + (220 - 165) * t)))
    if a > 0.0:
        t = a / 5.0
        return (int(round(240 + (190 - 240) * t)),
                int(round(130 + (175 - 130) * t)),
                int(round(80 + (165 - 80) * t)))
    if a > -6.0:
        t = (a + 6.0) / 6.0  # 0..1
        return (int(round(15 + (90 - 15) * t)),
                int(round(18 + (75 - 18) * t)),
                int(round(35 + (110 - 35) * t)))
    return (15, 18, 35)


def light_intensity_from_solar(solar: SolarState) -> float:
    """Global ambient light multiplier in [0.15, 1.05].

    Night : 0.15 (moonlight). Sunset : 0.5. Noon : 1.05.
    """
    a = solar.altitude_deg
    if a > 30.0:
        return 1.0 + 0.05 * (1.0 - max(0.0, (90.0 - a) / 60.0))
    if a > 0.0:
        return 0.5 + 0.5 * (a / 30.0)
    if a > -6.0:
        return 0.25 + 0.25 * ((a + 6.0) / 6.0)
    return 0.15


# ---------------------------------------------------------------------------
# Seasonal tint
# ---------------------------------------------------------------------------

def seasonal_tint(season_factor: float) -> Tuple[float, float, float]:
    """Per-channel multiplier applied to biome RGB.

    season_factor =  1.0 → summer (saturated greens/yellows, slight warm)
    season_factor =  0.0 → spring/fall (neutral)
    season_factor = -1.0 → winter (desaturated, blueish, dimmer greens)
    """
    s = float(np.clip(season_factor, -1.0, 1.0))
    if s >= 0.0:
        # Summer : boost R+G, slight blue down.
        return (1.0 + 0.08 * s, 1.0 + 0.05 * s, 1.0 - 0.04 * s)
    # Winter : desaturate, cool tint.
    return (1.0 + 0.05 * s,    # R goes down (warm leaves gone)
            1.0 + 0.10 * s,    # G goes down (greens fade)
            1.0 - 0.06 * s)    # B goes up (cooler hue)


# ---------------------------------------------------------------------------
# Snow accumulation
# ---------------------------------------------------------------------------

def compute_snow_field(world,
                          *,
                          temp_threshold_c: float = -2.0,
                          precip_threshold_mm: float = 200.0
                          ) -> np.ndarray:
    """Per-macro-cell bool : True if conditions favor accumulated snow.

    Heuristic statique (pas de simulation snowfall dynamique) : cells
    with mean temp_c < threshold AND precip_mm > threshold get snow.

    Returns (R, R) bool.
    """
    if not hasattr(world, "temp_c") or not hasattr(world, "precip_mm"):
        return np.zeros((1, 1), dtype=bool)
    t = world.temp_c
    p = world.precip_mm
    return ((t < temp_threshold_c) & (p > precip_threshold_mm)).astype(bool)


# ---------------------------------------------------------------------------
# Cloud cover
# ---------------------------------------------------------------------------

def compute_cloud_field(world) -> np.ndarray:
    """Per-macro-cell cloud cover [0, 1] from precip + humidity proxy.

    cloud = clip(precip / 2000, 0, 1) is a coarse proxy. Real
    meteorology in `engine.meteorology` would give more accurate
    cloud_cover per chunk but here we operate at macro scale.
    """
    if not hasattr(world, "precip_mm"):
        return np.zeros((1, 1), dtype=np.float32)
    p = world.precip_mm.astype(np.float32)
    return np.clip(p / 2000.0, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Renderer enhancer (post-processor)
# ---------------------------------------------------------------------------

@dataclass
class AtmosphereOptions:
    apply_solar_lighting: bool = True
    apply_seasonal_tint: bool = True
    apply_sky_blend: bool = True
    sky_blend_strength: float = 0.15      # 0 = no sky tint on land, 1 = full sky
    apply_snow_overlay: bool = True
    snow_alpha: float = 0.55
    apply_cloud_overlay: bool = True
    cloud_alpha: float = 0.30
    cloud_rgb: Tuple[int, int, int] = (220, 220, 220)
    night_dim_floor: float = 0.20         # don't go below this in pure night
    apply_aces_tone_map: bool = True
    aces_exposure: float = 1.05
    apply_atmospheric_fog: bool = True
    fog_humidity: float = 0.45
    fog_altitude_m: float = 300.0
    apply_column_ray_march: bool = True
    ray_march_steps: int = 8
    ray_march_humidity: float = 0.5


def enhance_render(rgb: np.ndarray,
                     *,
                     solar: SolarState,
                     snow_field: Optional[np.ndarray] = None,
                     cloud_field: Optional[np.ndarray] = None,
                     options: Optional[AtmosphereOptions] = None
                     ) -> np.ndarray:
    """Apply atmospheric post-processing to an RGB image.

    Inputs :
      - ``rgb`` : (H, W, 3) uint8 image from any renderer.
      - ``solar`` : SolarState (from compute_solar_state).
      - ``snow_field`` : (H', W') bool, broadcastable to image shape
        via nearest-neighbour scale. Optional.
      - ``cloud_field`` : (H', W') float [0, 1], broadcastable. Optional.
      - ``options`` : tuning dataclass.

    Returns a new (H, W, 3) uint8 array. Pure-function over inputs.
    Determinist.
    """
    opts = options or AtmosphereOptions()
    img = rgb.astype(np.float32, copy=True)

    # 1. Seasonal tint multiplies the image colours.
    if opts.apply_seasonal_tint:
        tint = seasonal_tint(solar.season_factor)
        img[..., 0] *= tint[0]
        img[..., 1] *= tint[1]
        img[..., 2] *= tint[2]

    # 2. Solar lighting + optional column transmittance (volumetric proxy).
    if opts.apply_solar_lighting:
        intensity = light_intensity_from_solar(solar)
        if opts.apply_column_ray_march and solar.is_day:
            intensity *= column_ray_march_transmittance(
                solar,
                column_steps=opts.ray_march_steps,
                humidity=opts.ray_march_humidity,
            )
        intensity = max(intensity, opts.night_dim_floor)
        img *= intensity

    # 3. Sky blend : at night/sunset, blend toward sky color.
    if opts.apply_sky_blend:
        sky = np.array(sky_color_from_solar(solar), dtype=np.float32)
        # Stronger blend at low altitudes; near zero during full day.
        # Strength = (1 - clip(altitude / 30, 0, 1)) × sky_blend_strength.
        alt_norm = max(0.0, min(1.0, solar.altitude_deg / 30.0))
        blend = (1.0 - alt_norm) * opts.sky_blend_strength
        if blend > 0.0:
            img = img * (1.0 - blend) + sky[None, None, :] * blend

    # 4. Snow overlay (nearest-neighbour broadcast to image shape).
    if opts.apply_snow_overlay and snow_field is not None and snow_field.any():
        snow_rgb = np.array([245, 248, 252], dtype=np.float32)
        snow_resized = _nearest_resize(snow_field.astype(np.float32),
                                          img.shape[:2]).astype(np.float32)
        snow_mask = snow_resized > 0.5
        if snow_mask.any():
            img[snow_mask] = (img[snow_mask] * (1 - opts.snow_alpha)
                                + snow_rgb[None, :] * opts.snow_alpha)

    # 5. Cloud overlay.
    if opts.apply_cloud_overlay and cloud_field is not None:
        cloud_rgb = np.array(opts.cloud_rgb, dtype=np.float32)
        cloud_resized = _nearest_resize(cloud_field.astype(np.float32),
                                           img.shape[:2]).astype(np.float32)
        # Alpha per-pixel = cloud_density × cloud_alpha.
        alpha = np.clip(cloud_resized * opts.cloud_alpha, 0.0, 1.0)
        img[..., 0] = img[..., 0] * (1 - alpha) + cloud_rgb[0] * alpha
        img[..., 1] = img[..., 1] * (1 - alpha) + cloud_rgb[1] * alpha
        img[..., 2] = img[..., 2] * (1 - alpha) + cloud_rgb[2] * alpha

    # 6. Atmospheric fog (uniform haze toward sky).
    if opts.apply_atmospheric_fog:
        fog = atmospheric_fog_factor(
            solar, humidity=opts.fog_humidity, altitude_m=opts.fog_altitude_m)
        if fog > 0.01:
            sky = np.array(sky_color_from_solar(solar), dtype=np.float32)
            img = img * (1.0 - fog) + sky[None, None, :] * fog

    # 7. ACES tone mapping (HDR-ish compression).
    if opts.apply_aces_tone_map:
        img = aces_tone_map(img, exposure=opts.aces_exposure)

    return np.clip(img, 0.0, 255.0).astype(np.uint8)


def _nearest_resize(arr: np.ndarray,
                      target_shape: Tuple[int, int]) -> np.ndarray:
    """Nearest-neighbour resize of a 2D array to ``target_shape``."""
    H, W = target_shape
    src_h, src_w = arr.shape
    if src_h == H and src_w == W:
        return arr
    ys = np.clip((np.arange(H) * src_h // max(H, 1)), 0, src_h - 1)
    xs = np.clip((np.arange(W) * src_w // max(W, 1)), 0, src_w - 1)
    return arr[ys[:, None], xs[None, :]]


# ---------------------------------------------------------------------------
# Convenience : full pipeline render with atmosphere
# ---------------------------------------------------------------------------

def render_macro_with_atmosphere(world,
                                    sim_tick: int,
                                    *,
                                    latitude_deg: Optional[float] = None,
                                    drive_accel: float = 1500.0,
                                    options: Optional[AtmosphereOptions] = None,
                                    path: Optional[str] = None
                                    ) -> np.ndarray:
    """Render the macro world (Wave 27) + atmosphere overlay.

    Determines latitude from the world's equator_y_frac if not provided.
    Returns (R, R, 3) uint8.
    """
    from engine.world_render import render_macro_world, _save_png
    rgb = render_macro_world(world)
    if latitude_deg is None:
        # Pull lat from the world's grid centre if available.
        try:
            lat_field = world.latitude_deg
            latitude_deg = float(lat_field[lat_field.shape[0] // 2,
                                              lat_field.shape[1] // 2])
        except AttributeError:
            latitude_deg = 46.5
    solar = compute_solar_state(sim_tick,
                                   latitude_deg=latitude_deg,
                                   drive_accel=drive_accel)
    snow = compute_snow_field(world)
    cloud = compute_cloud_field(world)
    enhanced = enhance_render(rgb, solar=solar,
                                 snow_field=snow,
                                 cloud_field=cloud,
                                 options=options)
    if path is not None:
        _save_png(enhanced, path)
    return enhanced


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def atmosphere_summary(sim_tick: int,
                          *,
                          latitude_deg: float = 46.5,
                          drive_accel: float = 1500.0
                          ) -> Dict[str, object]:
    solar = compute_solar_state(sim_tick,
                                   latitude_deg=latitude_deg,
                                   drive_accel=drive_accel)
    return {
        "day_of_year": solar.day_of_year,
        "hour_of_day": round(solar.hour_of_day, 2),
        "solar_altitude_deg": round(solar.altitude_deg, 2),
        "solar_azimuth_deg": round(solar.azimuth_deg, 2),
        "is_day": solar.is_day,
        "is_twilight": solar.is_twilight,
        "season_factor": round(solar.season_factor, 3),
        "sky_rgb": sky_color_from_solar(solar),
        "light_intensity": round(light_intensity_from_solar(solar), 3),
        "seasonal_tint": tuple(round(v, 3)
                                  for v in seasonal_tint(solar.season_factor)),
    }


__all__ = [
    "SolarState", "AtmosphereOptions",
    "compute_solar_state",
    "sky_color_from_solar", "rayleigh_sky_rgb",
    "henyey_greenstein_phase", "column_ray_march_transmittance",
    "light_intensity_from_solar",
    "seasonal_tint", "aces_tone_map", "atmospheric_fog_factor",
    "compute_snow_field", "compute_cloud_field",
    "enhance_render", "render_macro_with_atmosphere",
    "atmosphere_summary",
]
