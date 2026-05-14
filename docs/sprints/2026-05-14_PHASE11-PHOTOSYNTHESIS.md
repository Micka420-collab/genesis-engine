# SPRINT 2026-05-14 — Wave 4 photosynthèse + vieillissement matériaux + overlays visuels

**Priorité attaquée**: biologie ultra-réaliste — photosynthèse
scientifiquement identique à notre monde, évolution (vieillissement)
des matériaux, détails visuels live pour observer la civilisation.

**Statut**: ✅ livré
**Cible**: GPP émergente du climat + dégradation matérielle observable
+ overlays NDVI/GPP/food/elev dans le dashboard.

---

## Pourquoi ce sprint

Le tick `regenerate_chunk_resources` actuel utilisait une règle
arbitraire : "food regrow vers food_capacity à taux fixe (3 jours)".
Aucun lien avec la lumière, la température, le CO2 atmosphérique, ni
la diversité C3/C4/CAM réellement présente. Conséquence : la nourriture
restait disponible identiquement de jour comme de nuit, en été comme en
hiver, à 280 ppm ou 800 ppm de CO2. Impossible de raconter une histoire
de civilisation qui s'adapte à son environnement.

Wave 4 substitue **le modèle Farquhar-von Caemmerer-Berry (1980)** —
le standard mondial publié pour la photosynthèse C3 — couplé au modèle
Collatz (1992) pour C4 et une approximation CAM, en intégrant :

- la **lumière** (PAR via cycle jour/nuit + couverture nuageuse)
- la **température foliaire** (réponse en cloche par voie)
- le **CO2 atmosphérique** (lien direct avec `ecology.Atmosphere`)
- l'**humidité du sol** (facteur stomatique par cellule)
- la **distribution C3/C4/CAM par biome** (Sage 2004, Still 2003)

Les matériaux fabriqués par Wave 1/2 deviennent **mortels** :
corrosion, rouille, pourriture, fatigue. Les civilisations qui veulent
préserver leur capital matériel doivent inventer des techniques
(huiler, sécher, saler, vernir).

Le dashboard reçoit **4 overlays visuels** consommables en direct,
empilables (NDVI + water par exemple) sur l'endpoint `/api/render`.

---

## Photosynthèse — `engine/photosynthesis.py` (~390 LOC)

### Voies physiologiques

| Voie | Type | Optimum T | V_cmax (μmol/m²/s) | Biomes |
|---|---|---|---|---|
| **C3** | Farquhar-von Caemmerer-Berry (1980) | 22 °C | 60 | forêts, toundra, blé, riz |
| **C4** | Collatz (1992) — PEP-carboxylase | 30 °C | 40 | savane, maïs, canne |
| **CAM** | Simplification (nocturne) | 28 °C | 8 | cactées, agaves |

### Équations C3 implémentées

```
A_c (Rubisco-limited) = V_cmax × (C_i - Γ*) / (C_i + K_c × (1 + O / K_o))
A_j (light-limited)   = α × PAR × (C_i - Γ*) / (4 × C_i + 8 × Γ*)
A_net = min(A_c, A_j) - R_d

Paramètres à 25 °C (Sharkey 2007, Bernacchi 2001) :
  V_cmax_25 = 60 μmol/m²/s
  K_c_25    = 404 ppm    (E_a = 79430 J/mol Arrhenius scaling)
  K_o_25    = 278e3 ppm  (E_a = 36380)
  Γ*_25     = 42 ppm     (E_a = 37830)
  R_d_25    = 1.5        (E_a = 46390)
  α         = 0.24 mol e⁻ / mol photons
  C_i / C_a = 0.70 (stomatal proxy when unstressed)
```

### Biome → mélange C3/C4/CAM (Sage 2004)

| Biome | C3 | C4 | CAM |
|---|---|---|---|
| BOREAL_FOREST / TEMPERATE_FOREST / TROPICAL_RAINFOREST | 1.00 | 0 | 0 |
| GRASSLAND | 0.45 | 0.55 | 0 |
| SAVANNA | 0.10 | 0.90 | 0 |
| HOT_DESERT | 0.10 | 0.35 | 0.55 |
| COLD_DESERT | 0.85 | 0.10 | 0.05 |
| TUNDRA | 0.98 | 0.02 | 0 |
| OCEAN / ICE | 0 | 0 | 0 |

### Intégration chunk

`tick_photosynthesis(sim)` parcourt `sim.streamer.cache`, calcule par
chunk un `last_gpp_umol[64×64]` (μmol/m²/s par cellule), convertit en
kcal/tick :

```
1 μmol CO2 / m² / s
  × 0.25 m² (cell area)
  × 1e-6 × 30 g glucose / mol CO2
  × 3.74 kcal / g glucose
  × TICK_DT_S × drive_accel
```

Et **incrémente** `chunk.food_kcal` (clipped at `food_capacity`).
`invalidate_resource_masks(chunk)` est appelé pour préserver la
cohérence des caches de cognition.

### Smoke `p21_photosynthesis_smoke.py` — 7/7 PASS

```
[OK] step 1 — C3 noon 25°C 280 ppm in [5, 18] μmol/m²/s   A=8.61
[OK] step 2 — CO2 fertilization 280→560 ratio [1.4,2.3]   ratio=2.020
[OK] step 3 — C4 > C3 at 35°C high light                  C3=5.02 C4=10.88
[OK] step 4 — C3 at night negative (respiration only)     A=-0.78
[OK] step 5 — drought drops C3 to respiration-only        A=-1.48
[OK] step 6 — sim integration produces positive GPP       chunks=191 global=14061 kcal/tick
[OK] step 7 — ADR-0005 audit clean                        required-tagged=6
```

**Émergence sur sim Léman 150 ticks** : 191 chunks, **14 061 kcal/tick
global GPP** au CO2 pré-industriel 280 ppm, PAR 1329 (jour), 8 °C. Toutes
les boucles photosynthétiques C3 fonctionnent.

---

## Vieillissement matériaux — `engine/material_aging.py` (~250 LOC)

### Taux annuels calibrés (humide neutre 60 %)

| Préfixe matériel | Loss/an | Référence |
|---|---|---|
| `alloy_Fe…` (fer/acier) | 3.0 % | Brunbjerg 2017 |
| `alloy_Cu…` (bronze) | 0.35 % | patination |
| `alloy_Au` (or) | 0.005 % | noble |
| `alloy_Ag` (argent) | 0.08 % | |
| `ceramic_…` | 0.08 % | thermal cycling |
| `wood_…` | 18 % | biological decay |
| `leather` | 20 % | |
| `bone` | 10 % | |
| `stone_granite` | 0.005 % | géologique |

### Facteurs d'exposition (multiplicatifs)

| Mode | × |
|---|---|
| `dry_indoor` | 0.20 |
| `humid_air` | 1.00 |
| `wet_soil` | 2.50 |
| `salt_water` | 6.00 |
| `open_fire` | 3.00 |
| `buried` | 0.50 |

### Pratiques de maintenance par culture

| Pratique | Facteur (×) | Application |
|---|---|---|
| `oiling` | 0.40 | métaux |
| `drying` | 0.55 | bois, cuir |
| `salting` | 0.65 | os, cuir |
| `varnish` | 0.30 | bois, céramique |
| `alloying` | 0.50 | alliages |
| `salt_wash` | 0.70 | marin |
| `annealing` | 0.80 | fatigue métaux |

Stackables. Une culture qui pratique `oiling + annealing` sur un fer
réduit la décroissance à 0.40 × 0.80 = 32 % du taux nu.

### Smoke `p22_material_aging_smoke.py` — 6/6 PASS

```
[OK] step 1 — iron > 5× bronze decay (humid, 1 yr)    ratio=8.6
[OK] step 2 — salt water ≈ 6× humid for iron          ratio=6.0
[OK] step 3 — oiling drops iron decay to ~0.4× plain  ratio=0.4
[OK] step 4 — wet wood lost > 70 % integrity in 5 yr  integrity=0.000
[OK] step 5 — granite loses < 0.001 in 1 yr           loss=0.00005
[OK] step 6 — ADR-0005 lists material_aging OK
```

---

## Overlays visuels — `dashboard.py:render_bbox_png`

L'endpoint `GET /api/render?xmin&ymin&xmax&ymax&w&h&overlay=` accepte
une **liste séparée par virgules** d'overlays empilables :

| Token | Effet |
|---|---|
| (default) | biome × elevation + water tint |
| `ndvi` | vert pour `food_capacity` + `wood` élevés, brun sinon |
| `gpp` | jaune-vert pour GPP **live** depuis `_photo_state.chunk_caches` |
| `food` | orangé pour `food_kcal` standing |
| `elev` | greyscale altitude contrasté |

Exemples :
- `/api/render?overlay=ndvi` — santé végétation
- `/api/render?overlay=gpp,water` — GPP + lacs/rivières live
- `/api/render?overlay=food,elev` — calories disponibles + relief

---

## Endpoints

| Route | Description |
|---|---|
| `GET /api/photosynthesis_state` | global_gpp_kcal_per_tick, per_biome, Ca_ppm, PAR, T, chunks_tracked |
| `GET /api/material_aging_state` | alive_instances, destroyed_total, integrity_mean/min, culture_practices |

### HUD `#observatory-panel`

Nouvelle section **BIOSPHERE** sous PHYSIOLOGY :

```
🌱 14061.3 kcal/tk · ☀️ 1329 PAR · 🌡️ 8.4°C · CO₂ 280ppm
TEMPER 8730.4 · BOREAL 2890.1 · TROPIC 1255.7
🪙 alive 42 · ☠️ dead 0 · int 0.97/0.81min
practices: 2 cult
```

---

## ADR-0005

`_REQUIRED_MODULES` agrandie à **6** : earth_loader, sim_lift, realism,
physiology, **photosynthesis**, **material_aging**. Le linter CI
`p18_capabilities_lint` passe **6/6** modules requis taggés OK.

| Module | Pipeline | Capability |
|---|---|---|
| `photosynthesis` | Genesis-L4 Feedback | paper-L2 Simulator |
| `material_aging` | Genesis-L4 Feedback | paper-L1 Predictor |

Photosynthèse est un **simulator** (rollouts multi-step respectant les
lois Farquhar). Aging est un **predictor** (one-step degradation par tick).

---

## Non-régression

- `p17_wave1_integration` (Bronze Age) → 4/4 PASS
- `p19_wave2_integration` (steel + doping + recipe transmission) → 6/6 PASS
- `p20_physiology_smoke` (excretion + cholera) → 7/7 PASS
- `p18_capabilities_lint` (ADR-0005) → 6/6 modules requis OK

Tous les sprints précédents continuent de marcher.

---

## Fichiers touchés

```
runtime/engine/photosynthesis.py                    (nouveau, ~390 LOC)
runtime/engine/material_aging.py                    (nouveau, ~245 LOC)
runtime/engine/dashboard.py                         (+50 LOC : overlays + 2 endpoints)
runtime/engine/god_view_v2.html                     (+50 LOC : BIOSPHERE HUD)
runtime/engine/world_model_capabilities.py          (+2 LOC : required modules)
runtime/scripts/p21_photosynthesis_smoke.py         (nouveau, ~155 LOC, 7/7 PASS)
runtime/scripts/p22_material_aging_smoke.py         (nouveau, ~150 LOC, 6/6 PASS)
docs/sprints/2026-05-14_PHASE11-PHOTOSYNTHESIS.md   (ce fichier)
NEXT-SPRINT.md                                      (Wave 4 archivé)
```

---

## Pistes Wave 5

- **Évapotranspiration** : eau perdue par les stomates ↔ humidité chunk.
- **NPP réelle** (Net Primary Production) : déduire respiration
  autotrophique 50 % de GPP pour donner la biomasse nette.
- **Cycle de l'azote** : limitation N pour calibrer l'effet long-terme
  d'augmentation CO2 (acclimatation FACE).
- **Maladies végétales** : pathogènes spécifiques à un biome, peuvent
  s'étendre dans une monoculture cultivée par les agents.
- **Outils de visualisation** : agent inspector cliquable (popup avec
  toute la physio + génome + lineage), heatmap historique GPP, slider
  temporel pour rewind.
