# Genesis Engine — Reality Engine
**Date :** 14 mai 2026 (session 7)

Le Reality Engine ajoute par-dessus les couches L1 (Earth-Seed) + L2 (Sim-Lift)
**cinq subsystems** qui font passer Genesis Engine d'un "moteur de monde
réaliste" à un **moteur de monde vivant** — la différence entre une carte
topographique et un écosystème.

---

## Les 5 subsystems

### 1. Hydrology — Rivières émergentes
Algorithme D8 (8-directions) de flow accumulation sur le DEM Copernicus.
Chaque cellule trouve son voisin le plus bas, l'eau s'accumule selon la
topologie. Cellules avec `flow_acc > river_threshold` deviennent rivières.

**Plus** : les cellules marquées `water > 50` par L1 (lacs, étangs ESA WorldCover)
sont automatiquement classifiées rivières — pas besoin de gradient interne.

Pour Lausanne 1.5km × 1.5km : **8.06% cellules-rivière** (le lac Léman +
quelques drainages locaux).

### 2. Wildlife — Population Lotka-Volterra
Trois espèces avec dynamique prédateur-proie :
- **Deer** : croissance logistique dans biome forêt/grassland (proie)
- **Wolf** : prédateur — chasse deer, décline si pas de proie
- **Fish** : croissance logistique dans biome OCEAN/water (indépendant)

Spec : `wildlife={"deer": 60, "fish": 200, "wolf": 4}` = totaux sur la
carte entière, distribués proportionnellement aux chunks de biome compatible.

Pour Lausanne après 500 ticks : 93 deer + 30 fish + 5.6 wolves (équilibre atteint).

### 3. Trails — Sentiers émergents
Chaque agent qui marche dépose 0.05 d'intensité sur la cellule + 0.005 sur
les 8 voisines. Décroissance 0.5% / 5 ticks. Cellules > 0.1 sont
"well-trodden" — sentiers visibles.

Plus haute intensité atteinte 0.995/1.0, soit ~20+ passages.

### 4. Seasons — Calendrier Terre réel
`SeasonalClock(year=2026, day_of_year=120)` avance à `drive_accel` sim-seconds par tick.
Au accel=1500, 1 tick = 25 sim-minutes → ~58 ticks par sim-jour.
Expose `season_name` (winter/spring/summer/autumn nord-hémisphère) +
`hour_of_day`.

À 500 ticks : day_of_year 100→108 (8 sim-jours), 5h00 → 16h33.

### 5. Disease — Épidémie SIR
Utilise le champ `agents.infectious_until` ajouté par Phase 5cd. Tick
toutes les 10 ticks : pour chaque agent infectieux, query_disk 3m,
probabilité de transmission 0.5% par contact. Outbreak spontané 0.01%
quand 0 infecté. Durée infectieuse 200 ticks (~3 sim-heures).

---

## API utilisateur

### Via WorldBuilder

```python
from engine.world_builder import WorldBuilder

world = (WorldBuilder("alpha_centauri_b")
         .anchor(46.510, 6.633)
         .size_km(2.0)
         .founders(20).max_agents(1000)
         .with_realism(
             hydrology=True,
             wildlife={"deer": 80, "fish": 300, "wolf": 6},
             trails=True,
             seasons={"year": 2026, "day_of_year": 120},
             disease=True,
             river_threshold=8.0,
         )
         .build())
world.run(2000)
print(world.summary()["realism"])
```

### Via dashboard

```bash
python scripts/p4_leman_live.py --port 8765
# Ouvre http://localhost:8765/god_view_v2.html
```

Endpoints :
- `GET /api/realism_state` — hydrology + wildlife + trails + seasons + disease
- `GET /api/lift_state` — L2 (veg + slope + lake + walkability)
- `GET /api/demography` — pyramide démographique live
- `GET /api/state` — sim snapshot global

---

## Exemple `/api/realism_state` (Lausanne 500 ticks)

```json
{
  "hydrology": {
    "chunks_indexed": 240,
    "river_cells_pct": 0.0806,
    "river_threshold": 8.0
  },
  "wildlife": {
    "chunks_indexed": 240,
    "deer_total": 93.5,
    "fish_total": 30.2,
    "wolf_total": 5.6
  },
  "trails": {
    "chunks_indexed": 16,
    "max_intensity": 0.995,
    "well_trodden_cells": 181
  },
  "seasons": {
    "year": 2026,
    "day_of_year": 108,
    "hour_of_day": 16.33,
    "season": "spring"
  },
  "disease": {
    "infected_now": 0
  }
}
```

---

## Architecture des 5 couches actives

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 5cd  : agents, construction, invention, atmosphere   │
│              speech, foraging, value override               │
├─────────────────────────────────────────────────────────────┤
│  Reality Engine  : hydrology, wildlife, trails, seasons,    │
│                    disease                                   │
├─────────────────────────────────────────────────────────────┤
│  L2 Sim-Lift     : vegetation succession, foot-erosion,     │
│                    slope, lake distinction, walkability     │
├─────────────────────────────────────────────────────────────┤
│  L1 Earth-Seed   : Copernicus DEM + ESA WorldCover          │
│                    via /vsis3 AWS Open Data                 │
├─────────────────────────────────────────────────────────────┤
│  Procedural      : sample_terrain + classify_biome_array    │
│  fallback        : (when L1 unavailable)                    │
└─────────────────────────────────────────────────────────────┘
```

Toutes les couches sont **opt-in**, **déterministes** via `prf_rng`, et
exposées au dashboard live.

---

## Comparaison avec d'autres simulateurs 2026

| Capacité | Stable Diffusion world | DreamerV3 | NVIDIA Earth-2 | **Genesis Engine** |
|---|---|---|---|---|
| Earth-anchored terrain | ❌ | ❌ | ✅ | **✅ Copernicus DEM** |
| Procedural detail | ❌ | ❌ | ✅ | **✅ L2 succession** |
| Live wildlife | ❌ | ❌ | ❌ | **✅ Lotka-Volterra** |
| Emergent trails | ❌ | ❌ | ❌ | **✅ foot-prints** |
| Real seasons sync | ❌ | ❌ | ✅ | **✅ SeasonalClock** |
| Disease epidemics | ❌ | ❌ | ❌ | **✅ SIR overlay** |
| Multi-generation civilization | ❌ | partiel | ❌ | **✅ 23 générations** |
| Live dashboard | ❌ | ❌ | partiel | **✅ /api/*** |
| Save/load/branch | ❌ | partiel | partiel | **✅ library** |
| Determinism | ❌ | ✅ | partiel | **✅ prf_rng** |
| **Open-source / local** | ✅ | ✅ | ❌ | **✅** |

---

## Modules ce sprint

- `runtime/engine/realism.py` (~430 lignes) — 5 subsystems opt-in
- `runtime/engine/world_builder.py` — `.with_realism()` method
- `runtime/engine/dashboard.py` — `/api/realism_state` endpoint

## Modules existants utilisés

- `engine.core.prf_rng` pour déterminisme
- `engine.world` pour Biome enum + chunk geometry
- `engine.agent_5cd_fields.infectious_until` pour disease state
- `engine.spatial.SpatialGrid` pour query_disk dans disease tick

## Reste à faire (futures sessions)

- **Réintégrer la wildlife dans les drives agents** : agents devraient
  FORAGE/HUNT les deer et fish, pas seulement le `food_kcal` abstrait.
- **Trails affectent walkability live** : utiliser `trail_intensity` pour
  modifier `walkability` à chaque tick (paths boostent passage).
- **Hydrology cross-chunk** : aujourd'hui D8 est intra-chunk. Pour un vrai
  réseau de rivières il faut faire passer le flow d'un chunk à l'autre.
- **Climate events** : sécheresses / inondations / canicules superposées.
- **Migration animale** : deer migrent vers food chunks, fuient wolves.
- **HUD widget realism** : panel dashboard temps réel.
