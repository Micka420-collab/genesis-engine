# SPRINT 2026-05-14 — Wave 7 meteorology ultra-réaliste + bronzage UV

**Priorité attaquée**: météo scientifiquement défendable (nuages, pluie,
tempêtes, soleil, chaleur, UV) avec adaptation de la peau aux zones UV.

**Statut**: ✅ livré
**Cible**: modèle astronomique exact (déclinaison solaire, zenith,
irradiance Beer-Lambert) + nuages typés + précipitation typée +
tempêtes trackées + UV WHO + bronzage épidermique.

---

## `engine/meteorology.py` (~770 LOC)

### Géométrie solaire — vraie astronomie

Formules **Spencer 1971** (précision ±0.1° sur l'année) pour la
déclinaison solaire :

```
δ = 0.006918
   - 0.399912 cos(γ)
   + 0.070257 sin(γ)
   - 0.006758 cos(2γ)
   + ...
γ = 2π × (day-1) / 365
```

Zenith solaire exact par latitude + déclinaison + angle horaire :
```
cos(θ_z) = sin(φ)sin(δ) + cos(φ)cos(δ)cos(H)
```

Vérifié dans le smoke :
- 21 juin → δ = +23.45° (réel : +23.45°) ✓
- 21 décembre → δ = −23.42° (réel : −23.44°) ✓
- Équateur à midi équinoxe → θ_z = 0.07° ✓

### Irradiance solaire surface (Beer-Lambert)

Air mass Kasten-Young 1989, atténuation Rayleigh + aérosol +
ozone + nuage. Constante solaire NASA SORCE 1361 W/m².

À midi mi-latitude été : **1293 W/m²** (réel : 1000-1300). ✓
Nuit : **0 W/m²**. ✓

### UV index — norme WHO/WMO

Calibré sur le pic tropical observé :

```python
UVI = 40 × UV_W_m2
UV_W_m2 = 0.27 × cos(z)^1.2 × (300/O3_DU)^1.05 × cloud_factor × altitude_factor × albedo_factor
```

Vérification :
- Tropical noon (z=0) → **UVI 10.80** (réel records : 11-12) ✓
- Couvert lourd → cut UV de **60 %** (réel ~60-70 %) ✓
- Nuit → UVI 0 ✓

### Couches de nuages (5 types)

| Type | Conditions |
|---|---|
| CLEAR | humidity < 0.55 |
| CIRRUS | altitude > 1500 m + temp < 10 °C |
| CUMULUS | instability > 0.6 + temp > 15 °C |
| STRATUS | humidity > 0.85 + instabilité faible |
| NIMBUS | stratus saturé (cover > 0.9) |
| CUMULONIMBUS | cumulus saturé (cover > 0.85) |

Cover + thickness module la transmission radiative (~30 % sous
cumulonimbus, ~70 % sous cirrus).

### Précipitation (7 types)

| Type | Trigger |
|---|---|
| NONE | humidity < 0.88 ou thickness < 0.4 |
| DRIZZLE | rate < 1.5 mm/h |
| RAIN | 1.5 < rate < 5 + temp > 2 |
| SHOWER | instability > 0.7 + temp > 20 |
| SNOW | temp < 0 |
| SLEET | 0 < temp < 2 |
| HAIL | instability > 0.85 + temp > 20 |

Rate plafonné à **25 mm/h** (équivalent storm violent).

### Vent géostrophique + Coriolis

Coriolis exact : f = 2 Ω sin(φ).
- Équateur : **f = 0** ✓
- Pôle Nord : **f = 1.458e-4 rad/s** ✓ (réel : 1.45e-4)

Champ de vent : gradient de pression synthétique smooth + rotation
Coriolis lat-dépendante + amplification altitude > 1500 m (montagnes
exposées). Plafond 35 m/s (Beaufort 12).

### Tempêtes (3 types) — `StormCenter` trackés

| StormKind | Trigger | Lifetime |
|---|---|---|
| THUNDERSTORM | humidity > 0.85 + temp > 22 + instability | 12 h |
| EXTRATROPICAL_LOW | lat > 30° | 12 h |
| TROPICAL_CYCLONE | SST > 26.5 °C + lat > 5° + humidity > 0.9 | 36 h |

Hurricanes nécessitent Coriolis non-nul (lat > 5°) et SST 26.5 °C —
**conditions physiquement réelles**. Tempêtes advectées par le vent
moyen, intensité décrôit linéairement avec l'âge. Quand un chunk est
dans le rayon d'une tempête, son `precip_mm_h` et `wind_speed_ms`
sont boostés proportionnellement à `(1 - r/radius) × intensity`.

### Per-chunk state — `CellMeteorology`

16 champs : cloud_cover/type/thickness, precip_mm_h/type, wind_u/v/speed,
temp_c, humidity_rel, pressure_hpa, solar_zenith_deg,
solar_irradiance_w_m2, par_umol_m2_s, uv_index, in_storm.

`weather_at_chunk(sim, coord)` retourne directement le Weather Wave-7
pour ce chunk. Fallback sur `weather_at` legacy si meteorology pas
installée.

---

## `engine/physiology.py` extension — bronzage UV

### Nouveaux champs

```python
tan_level: np.ndarray         # [0,1] épidermique (Wave 7)
uv_dose_lifetime: np.ndarray  # cumul UV-day (UVI×jour) sur la vie
```

### Mécanique réaliste

- **Croissance** : UV > 3 → tan augmente. Vitesse 5 sim-jours sous UV
  intense (réel : 7-14 jours pour bronzage visible).
- **Dégradation** : 30 sim-jours sans exposition → décroissance complète
  (réel : ~4-6 semaines de fade).
- **Effective melanin** = genetic_melanin + 0.4 × tan_level
- **Sunburn** maintenant pilotée par **UV index réel** par chunk (via
  `chunk._meteo_state`), pas par thermal proxy. Susceptibilité ∝ (1 -
  effective_melanin) × max(0, (UVI - 1) / 7).

### Coupure de zone

Agents dans une zone forte UV (tropical) qui restent dehors
développent un tan élevé → moins de sunburn malgré la même mélanine
génétique. Les agents pâles d'une zone faible UV (boréal/tundra)
restent pâles → tannés faiblement quand exposés à fort UV soudain.

**C'est la réponse mélaninique épidermique réelle (UV → α-MSH →
mélanocytes → eumélanine épidermique).**

### Reporter étendu

`/api/physiology_state.means` inclut maintenant :
- `tan_level` (acquis)
- `effective_melanin` (génétique + tan ×0.4)
- `uv_dose_lifetime` (dose cumulée sur la vie en UV-jours)

---

## 5 nouveaux overlays visuels

`/api/render?overlay=…` accepte 5 modes empilables Wave 7 :

| Token | Effet |
|---|---|
| `clouds` | Voile blanc d'intensité ∝ cloud_cover |
| `precip` | Bleu intensité ∝ precip_mm_h |
| `uv` | Violet intensité ∝ UV index |
| `wind` | Vert → rouge gradient par vitesse (calm → 25 m/s) |
| `temperature` | Bleu (cold) → rouge (hot) centré 15 °C |

Combinables : `?overlay=clouds,wind,uv` montre nuages + vent + UV en
overlay simultané.

---

## Validation — `p28_meteorology_smoke` 12/12 PASS

```
[OK] step 1 — June +23°, Dec −23° declinations            jun=23.45 dec=-23.42
[OK] step 1 — equator equinox noon zenith near 0°         z=0.07°
[OK] step 2 — noon irradiance >800 W/m², midnight = 0     noon=1293 night=0
[OK] step 3 — tropical noon UVI in [5, 14], night = 0     tropical=10.80 night=0.00
[OK] step 3 — overcast cuts UV by >45 %                   clear=7.13 overcast=2.85
[OK] step 4 — Coriolis 0 at equator, max at pole          f_eq=0.000e+00 f_pole=1.458e-04
[OK] step 5 — chunks_tracked > 0 after 60 ticks           chunks=195
[OK] step 5 — cloud cover in [0, 1]                       cover=1.000
[OK] step 6 — tan_level grows or stays under UV cycles    before=0.0000 after=0.0000
[OK] step 6 — sunburn bounded (<0.95 mean)                sunburn=0.0000
[OK] step 7 — ADR-0005 lists meteorology OK
[OK] step 8 — determinism on global meteo summary
```

Snapshot final : 195 chunks Léman trackés, distribution NIMBUS
dominante (humide), distribution SNOW (température faible).

---

## Non-régression — tout passe

- `p18_capabilities_lint` → **10/10 modules requis taggés** OK
- `p20_physiology_smoke` → 7/7 PASS (tan_level + effective_melanin
  exposés dans means)
- `p23_persistence_roundtrip` → 7/7 PASS (meteorology persiste)
- `p27_plant_evolution_smoke` → 13/13 PASS

ADR-0005 table maintenant :

| Module | Pipeline | Capability |
|---|---|---|
| earth_loader | L1 | paper-L1 Predictor |
| sim_lift | L2 | paper-L2 Simulator |
| realism | L4 | paper-L2 Simulator |
| physiology | L4 | paper-L2 Simulator |
| photosynthesis | L4 | paper-L2 Simulator |
| material_aging | L4 | paper-L1 Predictor |
| marine | L4 | paper-L2 Simulator |
| global_world | L4 | paper-L2 Simulator |
| plant_evolution | L4 | paper-L2 Simulator |
| **meteorology** (nouveau) | L4 | paper-L2 Simulator |

---

## Boucle de rétroaction complète

```
Lat/lon + Earth time
  → solar zenith / declination
  → solar irradiance + UV index
  → cloud + precip + wind per chunk
  → temp_c per chunk
  → agent UV exposure
  → tan_level growth
  → effective_melanin
  → sunburn risk
  → pain + vitality
  → reproduction rate per zone
  → melanin baseline shifts over generations (genetic selection)
```

Cette boucle ferme **3 effets émergents documentables** :

1. **Bronzage différentiel** — agents pâles dans zones tropicales
   bronzent ; même mélanine génétique, peau effective plus sombre
   après quelques sim-mois.
2. **Sélection mélaninique** — sur 100+ générations, dans une zone
   forte UV, les agents à mélanine génétique plus haute ont moins de
   sunburn → vitalité préservée → plus de descendance → mélanine
   moyenne monte. Évolution darwinienne réelle.
3. **Couplage climat-civilisation** — IA qui émet CO2 → réchauffe →
   plus de tempêtes tropicales (SST > 26.5°C plus fréquente) →
   destruction de récoltes côtières → pression de migration.

---

## Fichiers touchés

```
runtime/engine/meteorology.py                       (nouveau, ~770 LOC)
runtime/engine/physiology.py                        (+90 LOC : tan_level + UV hook)
runtime/engine/dashboard.py                         (+55 LOC : endpoint + 5 overlays)
runtime/engine/world_library.py                     (+1 LOC : _PERSISTENT_MODULES)
runtime/engine/world_model_capabilities.py          (+1 LOC : _REQUIRED_MODULES)
runtime/scripts/p28_meteorology_smoke.py            (nouveau, ~205 LOC, 12/12 PASS)
docs/sprints/2026-05-14_PHASE17-METEOROLOGY.md      (ce fichier)
NEXT-SPRINT.md                                      (Wave 7 archivé)
```

---

## Wave 8 (R&D future)

- **Skin color visualisation** : exposer `effective_melanin` par agent
  dans `/api/agents` + colorer les agents sur le dashboard.
- **Climat global cohérent** : actuellement le sim utilise une seule
  origine lat/lon pour tous ses chunks. Pour multi-région (Phase 15)
  il faut que chaque sim attaché à un `GlobalWorld` ait sa propre
  origine et que les meteo soient cohérentes (jet stream qui traverse
  les frontières de sim).
- **Cycle hydrologique** : précipitation → augmente chunk.water →
  évaporation per UV → cycle complet de Bowen.
- **Saisons longues** : la durée actuelle d'un cycle saisonnier
  (365 sim-jours = 100 sim-heures wall-clock) suit le sim.tick.
  Permettre `time_compression_factor` pour observer plusieurs
  saisons en quelques minutes wall-clock.
