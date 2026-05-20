# Wave 41 — World Atmosphere : Day/Night + Seasons + Weather

**Date :** 2026-05-18 (session 34z)
**Module livré :** `engine.world_atmosphere`
**Smoke :** `scripts/p72_world_atmosphere_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré (réalisme visuel +++)

---

## Pourquoi

L'utilisateur demande "plus de réaliste sur les détails du monde".
Les renders Wave 27 / 36 étaient figés dans une lumière de midi
permanente — c'est l'incohérence visuelle la plus frappante.

Wave 41 ajoute la couche **atmosphère temporelle** par-dessus
n'importe quel renderer existant :

- Cycle jour / nuit complet (équation astronomique standard)
- Saisons (4 phases via day_of_year)
- Couleurs ciel (day-bleu / sunset-orange / twilight / night)
- Snow accumulation sur cells froides + humides
- Cloud overlay depuis précipitations macro

Pas de scripting — tout dérive analytiquement de `sim.tick × drive_accel`.

---

## Architecture (pure-function, read-only)

### Équations astronomiques

```
sim_seconds = sim_tick × drive_accel
day_of_year = (sim_seconds // 86400) % 365
hour_of_day = (sim_seconds % 86400) / 3600

declination_deg = 23.44 × sin(2π × (day - 80) / 365)
hour_angle_deg  = (hour - 12) × 15

sin(altitude) = sin(lat) × sin(decl)
              + cos(lat) × cos(decl) × cos(hour_angle)
azimuth = atan2(sin(ha), cos(ha) × sin(lat) - tan(decl) × cos(lat))
```

Calibration Terre : tilt 23.44°, jour 80 = équinoxe printemps.

### Couleurs ciel

```
altitude > 30   : day      (135, 180, 220)
altitude 5..30  : late day (190, 175, 165)
altitude 0..5   : sunset   (240, 130,  80)
altitude -6..0  : dusk     ( 90,  75, 110)
altitude < -6   : night    ( 15,  18,  35)
```

### Light intensity (multiplicateur global RGB)

```
altitude > 30  : 1.0-1.05  (full daylight)
altitude > 0   : 0.5-1.0   (low day)
altitude > -6  : 0.25-0.5  (twilight)
altitude < -6  : 0.15      (night floor)
```

### Tint saisonnier (season_factor ∈ [-1, +1])

```
summer (+1) :  (R×1.08, G×1.05, B×0.96)  ← saturé chaud
neutral ( 0) :  (1.00, 1.00, 1.00)
winter (-1) :  (R×0.95, G×0.90, B×1.06)  ← gris bleuté
```

### Snow + cloud fields

```
snow[i,j]  = (temp_c[i,j] < -2°C) AND (precip_mm[i,j] > 200)
cloud[i,j] = clip(precip_mm[i,j] / 2000, 0, 1)
```

### Pipeline render

```python
enhanced = enhance_render(rgb,
    solar=compute_solar_state(sim_tick, latitude_deg, drive_accel),
    snow_field=compute_snow_field(world),
    cloud_field=compute_cloud_field(world),
    options=AtmosphereOptions(...))
# 1. Seasonal tint (RGB multiply)
# 2. Solar lighting (dimming)
# 3. Sky blend (twilight/night tint)
# 4. Snow overlay (where snow_field)
# 5. Cloud overlay (alpha-blended)
```

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique | OK |
| 2 | Noon équateur été : altitude = **66.6°** | OK (max possible) |
| 3 | Midnight : altitude = **-66.5°** (inversion parfaite) | OK |
| 4 | Sky day=(135,180,220) ≠ sunset=(220,148,114) ≠ night=(15,18,35) | OK |
| 5 | Summer tint=(1.08,1.05,0.96) vs winter=(0.95,0.90,1.06) | OK |
| 6 | snow=404 cells / 2304 (cold+wet), cloud range [0, 1] | OK |
| 7 | **Night mean RGB=25 vs day=131 → ratio 5×** dimming | OK |
| 8 | Déterminisme : 2 enhance_render → bit-identiques | OK |
| 9 | render_macro_with_atmosphere day_PNG ≠ night_PNG | OK |

---

## Renders générés (4 phases temporelles)

`docs/renders/wave41_atm_*.png` — même monde, 4 instants différents :

| Phase | Heure | Solar alt | Couleurs |
|---|---|---:|---|
| **sunrise** | jour 80, 6h | -1.7° | Gris-bleu d'aube |
| **noon** | jour 172 (été), 12h | +66.9° | Vives, ciel bleu, biomes saturés |
| **sunset** | jour 264, 18h | +2.1° | Orange-brun amber |
| **winternight** | jour 355, 23h | -63.5° | Bleu-noir, tint hivernal froid |

Le même monde Genesis se transforme visuellement selon l'heure
**sans aucune ré-génération** — pure post-processing.

---

## API publique

```python
from engine.world_atmosphere import (
    # Data
    SolarState,                       # day_of_year, hour, altitude, azimuth, season
    AtmosphereOptions,                # 9 toggles + strengths

    # Astronomical
    compute_solar_state,              # sim_tick, lat, accel → SolarState
    sky_color_from_solar,             # → (R, G, B)
    light_intensity_from_solar,       # → float [0.15, 1.05]
    seasonal_tint,                    # season_factor → (mr, mg, mb)

    # Field computation
    compute_snow_field,               # world → (R, R) bool
    compute_cloud_field,              # world → (R, R) float [0, 1]

    # Renderer enhancer (post-processor)
    enhance_render,                   # rgb, solar, snow, cloud → enhanced rgb
    render_macro_with_atmosphere,     # convenience full pipeline + PNG

    # Reporter
    atmosphere_summary,
)
```

### Usage type minimal

```python
from engine.world_atmosphere import render_macro_with_atmosphere

# Rendu macro à midi été
render_macro_with_atmosphere(world, sim_tick=10000, latitude_deg=46.5,
                                path="midday.png")

# Rendu macro à minuit hiver
render_macro_with_atmosphere(world, sim_tick=600000, latitude_deg=46.5,
                                path="winter_night.png")
```

### Usage type avancé (chain avec Wave 36 iso renderer)

```python
from engine.world_render_isometric import render_sim_isometric
from engine.world_atmosphere import (compute_solar_state, enhance_render,
                                       compute_cloud_field)

rgb_iso = render_sim_isometric(sim, options=...)
solar = compute_solar_state(sim.tick, latitude_deg=46.5)
enhanced = enhance_render(rgb_iso,
                            solar=solar,
                            cloud_field=compute_cloud_field(world))
# Iso rendering + atmosphere overlay → cinematic frame.
```

---

## Limitations connues

- **Pas d'ombres portées dynamiques** : le hillshade Wave 27 est fixe
  (sun @ 315°/45°). Wave 41 ajoute le tint global mais ne recalcule
  pas les ombres à la position solaire courante. Pour cinematic ombres
  longues à sunset, ré-render avec `sun_azimuth_deg = solar.azimuth_deg`,
  `sun_altitude_deg = solar.altitude_deg`.
- **Snow statique** : `compute_snow_field` est un snapshot
  thermodynamique (cells froides + humides). Pas de fonte saisonnière
  réactive (winter→spring melt). À ajouter Wave 42+ avec
  `engine.material_aging`.
- **Pas de météo dynamique visible** : pas de pluie animée ni de
  tempête localisée — seulement opacité nuage statique.
- **Pas de pollution atmosphérique** : volcanic ash, smog post-industriel
  hors scope.
- **1 latitude par render** : si tu rends une grosse carte couvrant
  plusieurs latitudes (e.g. multi-région Wave 22), Wave 41 utilise
  la lat moyenne. Pour gradient lat, ré-render par bande.

---

## Branchements futurs

| Module | Intégration |
|---|---|
| `world_render` | Réutiliser solar.altitude/azimuth pour hillshade dynamique. |
| `world_render_isometric` (Wave 36) | Idem + ombres portées par tile. |
| `animation_timelapse` (Wave 37) | Cycle jour/nuit dans le GIF (capture toutes les 1-2h sim). |
| **Wave 42+** | Météo dynamique : nuages qui bougent avec vent macro, pluie animée. |
| **Wave 43+** | Étoiles + lune au-dessus de night sky. |
| **Wave 44+** | Surfaces texturées (sand, grass, snow) au lieu d'aplats. |
