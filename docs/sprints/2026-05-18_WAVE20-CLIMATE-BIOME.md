# Wave 20 — Climate-Biome Coupling

**Date :** 2026-05-18 (session 35)
**Module livré :** `engine.climate_biome`
**Smoke :** `scripts/p49_climate_biome_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Levier #3 de l'audit Wave 18 (5 candidats classés). Le problème
identifié : avant Wave 20, **la carte de biomes était figée à la
génération du chunk**.

Concrètement, `engine.world.generate_chunk(...)` appelait
`classify_biome_array(temp, precip, elev)` une fois, stockait le
résultat dans `chunk.biome`, puis ne le rouvrait jamais. Une simulation
qui tournait 5 000+ ticks (équivalent à des décennies sim-temps
accélérées via `drive_accel=1500`) ne voyait **aucun changement
climatique au niveau visible** : la toundra restait toundra, les forêts
boréales restaient boréales, etc.

C'était d'autant plus dommage qu'on avait depuis Wave 19 :

- Un champ `temp_c[R, R]` macro cohérent (latitude + lapse + continentalité).
- Un champ `precip_mm[R, R]` macro cohérent (Hadley + orographique).
- Un mécanisme `Atmosphere` (in `ecology.py`) qui suivait l'anomalie CO2
  → température mais qui se contentait de réduire `food_capacity` via
  `apply_climate_feedback` — sans jamais migrer les biomes.

Wave 20 ajoute la **migration dynamique** : à chaque tick, pour
chaque cellule de chaque chunk caché, un tirage déterministe
(`prf_rng(seed, ['climate_biome','transition'], [tick, cx, cy, cz])`)
décide si la cellule progresse d'un cran dans l'échelle de Whittaker
(toundra → boréal → tempéré → tropical sec/humide → désert chaud
ou forêt tropicale humide), en fonction de l'anomalie de
température courante.

Le changement climatique devient ainsi **visible directement au
niveau du moteur** : un agent en bordure de toundra peut littéralement
voir sa cellule basculer en forêt boréale au-dessus d'un seuil de
+2 K, ce qui change `food_capacity`, `wood` (via le rendu suivant) et
les masques de ressources consommés par `cognition._scan_chunk`.

---

## Architecture

```
GenesisWorld (Wave 16)
    └─ temp_c[R, R], precip_mm[R, R]   °C / mm/yr
                                       baseline climatique macro

ChunkAnchor (Wave 16b)
    └─ sim_origin_macro_km             sim mètres ↔ macro km

install_climate_biome(sim, anchor, *, anomaly_source, warming_rate_c_per_year,
                                       temperature_jitter_amplitude,
                                       transition_speed)
    ├─ snapshot baseline_temp_c[coord] pour chaque chunk déjà caché
    ├─ snapshot chunk_precip_proxy[coord] (pour les transitions
    │   conditionnelles à la pluie)
    └─ monkey-patch sim.step()
            └─ après l'original, appelle apply_climate_biome_step(sim)

apply_climate_biome_step(sim):
    global_dT = anomaly_source ∈ {'linear_warming','macro'}
        linear_warming → warming_rate * sim_years
                         sim_years = tick * drive_accel / (86400*365)
        macro          → 0.0 (placeholder, prêt à hooker dans une future Wave
                          de dynamisme macro)

    for coord, chunk in sim.streamer.cache.items():
        local_dT = global_dT + jitter[coord]      # déterministe via PRF
        if |local_dT| < 0.05 °C: skip
        amp = min(MAX_MULT, |local_dT| / SCALE_C)        # 0..6
        p_shift = clip(transition_speed * amp, 0, 1)
        probs = prf_rng(seed, ['climate_biome','transition'],
                         [tick, cx, cy, cz]).random((64, 64))
        shift_mask = probs < p_shift
        warming = local_dT > 0
        target_biome = _shift_biomes_array(chunk.biome, warming, precip_proxy)
        chunk.biome = where(shift_mask & (target != biome), target, biome)
        chunk.food_capacity = _NPP_BY_BIOME[chunk.biome] * 500.0
        chunk.food_kcal     = min(chunk.food_kcal, chunk.food_capacity)
        invalidate_resource_masks(chunk)
```

### Matrice de transition (réchauffement)

| Avant | Après (dry < 1500 mm) | Après (wet ≥ 1500 mm) |
|---|---|---|
| OCEAN | OCEAN | OCEAN |
| ICE | TUNDRA | TUNDRA |
| TUNDRA | BOREAL_FOREST | BOREAL_FOREST |
| BOREAL_FOREST | TEMPERATE_FOREST | TEMPERATE_FOREST |
| TEMPERATE_FOREST | TROPICAL_DRY_FOREST | TROPICAL_RAINFOREST |
| TEMPERATE_RAINFOREST | TROPICAL_RAINFOREST | TROPICAL_RAINFOREST |
| GRASSLAND | SAVANNA | SAVANNA |
| HOT_DESERT | (terminal) | (terminal) |
| COLD_DESERT | GRASSLAND | GRASSLAND |
| SAVANNA (precip < 500) | HOT_DESERT | — |
| SAVANNA (precip ≥ 500) | — | TROPICAL_DRY_FOREST |
| TROPICAL_DRY_FOREST | TROPICAL_RAINFOREST | TROPICAL_RAINFOREST |
| TROPICAL_RAINFOREST | (terminal) | (terminal) |

### Matrice de transition (refroidissement)

Effet miroir : TUNDRA → ICE, BOREAL_FOREST → TUNDRA,
TEMPERATE_FOREST → BOREAL, GRASSLAND → COLD_DESERT, HOT_DESERT →
SAVANNA, etc. (Terminal : ICE et OCEAN.)

### Déterminisme strict

Toutes les RNG flow via `engine.core.prf_rng` clé par
`(seed, ['climate_biome', 'transition'], [tick, cx, cy, cz])`. Un seul
`rng.random((64, 64))` par chunk-par-tick → ordre de consommation
fixé par numpy. Deux sims avec la même seed produisent des cartes
de biomes finales bit-identiques après le même nombre de ticks (vérifié
step 7).

### Read-only sur GenesisWorld

Aucune mutation de `anchor.world.*` arrays. Seuls `chunk.biome` et
`chunk.food_capacity` (et `chunk.food_kcal` plafonné) sont modifiés
in place sur les chunks du cache de `sim.streamer`.

### Idempotence

`install_climate_biome` détecte un `sim._climate_biome_state` existant
et se contente de mettre à jour ses paramètres (anchor, source, taux,
seuils). `sim.step` n'est patché qu'une seule fois (premier install).

---

## API publique

```python
@dataclass
class ClimateBiomeState:
    anchor: GenesisAnchor
    anomaly_source: str
    warming_rate_c_per_year: float
    temperature_jitter_amplitude: float
    transition_speed: float
    baseline_temp_c: Dict[Tuple[int,int,int], float]
    current_anomaly_c: Dict[Tuple[int,int,int], float]
    chunk_biome_shifted: Dict[Tuple[int,int,int], int]
    chunk_precip_proxy: Dict[Tuple[int,int,int], float]
    global_anomaly_c: float
    transitions_total: int
    last_apply_tick: int

def install_climate_biome(sim, anchor, *,
                          anomaly_source: str = "linear_warming",
                          warming_rate_c_per_year: float = 0.02,
                          temperature_jitter_amplitude: float = 0.0,
                          transition_speed: float = 0.001
                          ) -> ClimateBiomeState

def apply_climate_biome_step(sim) -> Dict[str, float]
    # → {'cells_shifted_this_step': N, 'global_anomaly_c': X}

def climate_biome_state(sim) -> Dict[str, object]
    # rapport diagnostic complet

def uninstall_climate_biome(sim) -> bool
```

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique exposée (`install_*`, `uninstall_*`, `apply_*`, `*_state`, `ClimateBiomeState`) | OK |
| 2 | `install_climate_biome` idempotent + baseline_temp capturé pour 96 chunks | OK |
| 3 | tick=0, anomaly=0 → 0 cells shifted, map identique | OK |
| 4 | warming_rate=2.0 K/yr + tick=50 000 → anom=+4.76 °C, 393 216 cells TUNDRA → BOREAL_FOREST | OK |
| 5 | Aucune transition warming→cooling (violations=0) | OK |
| 6 | Toutes les transitions TUNDRA mènent à BOREAL_FOREST (aucune cellule "saute" un cran) | OK |
| 7 | Déterminisme : sim1 et sim2 (même seed, même anchor) → mêmes biome arrays sur 96 chunks partagés | OK |
| 8 | `climate_biome_state(sim)` : `transitions_total=393 216`, `global_anom=+4.76`, `chunks_with_shifts=96` | OK |
| 9 | `uninstall_climate_biome` restaure `sim.step`, ne ré-shifte pas en arrière, `sim.step()` post-uninstall fonctionne | OK |

L'anchor sim est placé sur une cellule macro TUNDRA (interior, médiane
parmi les pixels TUNDRA détectés). Le warming_rate=2.0 K/yr est
exagéré (réalité ~0.02 K/yr) pour pousser l'anomalie à +4.76 °C en
50 000 ticks, dépasser le `ANOMALY_DEADBAND_C=0.05` et déclencher
les transitions. `transition_speed=0.5` combiné avec
`amp=clip(4.76/1.0, 0, 6) = 4.76` donne `p_shift=clip(0.5*4.76, 0, 1) = 1.0`
→ toutes les cellules TUNDRA basculent en BOREAL_FOREST dès le premier
pas (résultat attendu sur ces paramètres extrêmes). La calibration
production utilise des valeurs (`transition_speed=0.001`,
`warming_rate=0.02`) qui font évoluer le paysage sur des milliers
de ticks.

---

## Limitations

1. **Pas de transition spatiale** : la propagation se fait via tirage
   indépendant par cellule. Pas de random-walk / contagion depuis les
   bordures de biomes voisins. Une amélioration future pourrait ajouter
   une probabilité boostée si une cellule voisine appartient déjà au
   biome cible.

2. **Précipitations figées au snapshot** : `chunk_precip_proxy[coord]`
   est échantillonné une fois à l'install (depuis `world.precip_mm`).
   Si la pluviosité macro variait dans le temps (Wave future), il
   faudrait re-sampler. Pour l'instant, la macro Wave 16 est statique
   donc ce snapshot est exact.

3. **Anomalie globale uniforme** : `anomaly_source='linear_warming'`
   applique le même `dT` partout. Le paramètre
   `temperature_jitter_amplitude > 0` ajoute du bruit par-chunk via PRF,
   mais il n'y a pas de gradient latitudinal différentiel (l'Arctique
   se réchauffe ~2x plus vite que les tropiques dans la réalité —
   "Arctic amplification"). Une Wave future pourrait substituer
   `anomaly_source='macro'` à un vrai modèle dynamique.

4. **Pas de "succession écologique" intermédiaire** : la transition
   TEMPERATE_FOREST → TROPICAL_RAINFOREST est instantanée pour une
   cellule, sans état transitoire (forêt mixte, savane semi-aride…).
   Le moteur saute du biome A au biome B dès que le tirage tombe juste.

5. **`anomaly_source='macro'` est un placeholder** : pour l'instant
   renvoie 0.0. La hook est en place pour une Wave de dynamisme macro
   ultérieure (e.g. couplage avec `engine.ecology.Atmosphere` qui
   trackait déjà `temp_anomaly_k` côté global atmosphère/CO2).

6. **Réversibilité non garantie** : sous refroidissement, la matrice
   `_COOLING` est appliquée, mais comme la matrice de réchauffement
   peut amener TEMPERATE_FOREST → TROPICAL_RAINFOREST en un saut, le
   refroidissement passe par TEMP_RAINFOREST → TEMPERATE_FOREST. Une
   trajectoire warming-cooling-warming ne revient donc pas exactement
   sur ses pas (asymétrie matricielle volontaire pour modéliser
   l'hysteresis écologique).

---

## Branchements futurs

- **Agriculture (Wave PHASE19)** : le `chunk.food_capacity` mis à jour
  par Wave 20 est déjà lu par `engine.agriculture.tick_agriculture`.
  Une cellule qui passe SAVANNA → HOT_DESERT verra son rendement
  agricole chuter automatiquement.

- **Photosynthesis (Wave PHASE11)** : le `_BIOME_NPP` qu'on
  réutilise pilote la productivité primaire nette ; le couplage est
  immédiat.

- **Plant evolution** : si une population de plantes adaptée à
  TUNDRA se retrouve subitement dans un chunk BOREAL_FOREST, on peut
  imaginer hooker un signal "habitat shift" dans
  `engine.plant_evolution` pour déclencher une pression sélective.

- **Polity / migration humaine** : les agents peuvent percevoir le
  changement de `chunk.food_capacity` via `cognition._scan_chunk`, donc
  une famine émergente devrait spontanément pousser à la migration
  vers les zones nouvellement habitables.

- **Coupling avec `ecology.Atmosphere`** : l'`anomaly_source='macro'`
  est prêt à lire `sim.atmosphere.temp_anomaly_k` (déjà existant côté
  CO2 anthropogénique). On ferait coexister deux forcings : naturel
  (linear_warming, e.g. Holocène pré-industriel) + anthropogénique
  (CO2 → atmosphere.temp_anomaly_k).

---

## Fichiers livrés

- `runtime/engine/climate_biome.py` (création, ~340 LOC)
- `runtime/scripts/p49_climate_biome_smoke.py` (création, ~280 LOC, 9/9)
- `docs/sprints/2026-05-18_WAVE20-CLIMATE-BIOME.md` (cette doc)

Aucune modification d'`engine/world.py`, `engine/ecology.py`,
`engine/world_genesis.py`, etc. Pure overlay propre.

## Non-régression

| Smoke | Résultat |
|---|---|
| p44 (world_genesis) | 9/9 PASS |
| p45 (chunk_genesis_anchor) | 8/8 PASS |
| p46 (tectonic_geology) | 9/9 PASS |
| p47 (chunk_hydrology) | 9/9 PASS |
| p48 (macro_climate) | 9/9 PASS |
| p49 (climate_biome) | **9/9 PASS** |
