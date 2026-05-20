# Wave 26 — Wave Function Collapse Vegetation Distribution

**Date :** 2026-05-18 (session 34j)
**Module livré :** `engine.wfc_vegetation`
**Smoke :** `scripts/p56_wfc_vegetation_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Jusqu'à Wave 25, `chunk.wood` est uniforme par biome — un blob constant
de 80 kg/m² sur tout chunk TEMPERATE_FOREST, 0 partout sur HOT_DESERT.
Aucun pattern visible : pas de clairière, pas de lisière, pas de
ripisylve. Le fauna et l'agent ne peuvent pas distinguer la forêt
dense de l'orée.

Wave 26 livre l'autre grande technologie IA/PCG du survey (Wave 23-25 =
NCA Mordvintsev) : **Wave Function Collapse** de Maxim Gumin (2016).

WFC est un algorithme de satisfaction de contraintes inspiré de la
mécanique quantique :

```
1. Chaque cellule = "superposition" sur tous les tiles possibles
2. Pick lowest-entropy cell, collapse via choix pondéré aléatoire
3. Propage la contrainte d'adjacence aux 4-voisins
4. Repeat jusqu'à toutes collapsed
```

Distinct des Waves 23-25 :
- **NCA** : évolution différentielle d'un state continu (height/sed/water).
- **WFC** : propagation de contraintes discrètes sur un tileset.

Les deux sont des techniques IA légitimes. Ils se complètent : NCA
sculpte le relief, WFC peuple la surface.

---

## Architecture

### Tileset (8 tiles)

| ID | Tile | Wood kg/m² | Adjacents (4-conn) |
|---:|---|---:|---|
| 0 | `ocean` | 0 | shore, water_edge |
| 1 | `shore` | 0 | ocean, bare, grass |
| 2 | `bare` | 0 | shore, grass, shrub |
| 3 | `grass` | 3 | shore, bare, shrub, edge, water_edge |
| 4 | `shrub` | 10 | bare, grass, edge, water_edge |
| 5 | `forest_edge` | 40 | grass, shrub, forest, water_edge |
| 6 | `forest` | 80 | edge, water_edge |
| 7 | `water_edge` | 25 | ocean, grass, shrub, edge, forest |

Règles d'adjacence symétriques + reflexives. Encode des **lois physiques
de succession écologique** :

- Forêt dense ne touche jamais le sol nu (transit obligatoire par lisière).
- Océan ne touche jamais le sol nu (transit par plage ou ripisylve).
- Self-adjacent : tile peut clustering avec lui-même.

### Biome priors

Vecteur de probas sur 8 tiles par biome (rows sum to 1). Exemple :

| Biome | bare | grass | shrub | edge | forest | water_edge |
|---|---:|---:|---:|---:|---:|---:|
| TEMPERATE_FOREST | 0 | 0.05 | 0.12 | 0.22 | 0.56 | 0.05 |
| HOT_DESERT | 0.80 | 0.15 | 0.05 | 0 | 0 | 0 |
| TROPICAL_RAINFOREST | 0 | 0.02 | 0.06 | 0.16 | 0.70 | 0.06 |
| GRASSLAND | 0.05 | 0.62 | 0.18 | 0.10 | 0.02 | 0.03 |

Toutes 12 biomes Whittaker couvertes dans `BIOME_TILE_PRIORS`.

### Résolution

WFC tourne à **16×16 cells par chunk** (chaque cellule WFC = 4×4 pixels
de `chunk.wood`). 256 cells × ~8 ops par cellule = ~2k ops. Très
rapide.

### Forçage d'eau

Pour les cellules avec `chunk.water ≥ 100 L` (rivières + lacs +
springs), le prior est remplacé : `water_edge` 70 % + `ocean` 30 %.
Ainsi les rivières Wave 18 + océans cohabitent avec le WFC sans
casser sa propagation.

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique | OK |
| 2 | Adjacency table symétrique + réflexive | OK |
| 3 | Déterminisme : 2 runs identiques → tile grids bit-identiques | OK |
| 4 | TEMPERATE_FOREST → 89.1 % forest+edge tiles (seuil 60 %) | OK |
| 5 | HOT_DESERT → 95.3 % bare+grass tiles (seuil 85 %) | OK |
| 6 | **0 violations d'adjacence** sur les 2 chunks testés | OK |
| 7 | `chunk.wood` patterné (variance 397, range [3, 80]) | OK |
| 8 | Install idempotent + streamer wrap fires on cache miss | OK |
| 9 | Uninstall restaure le streamer | OK |

### Détail des compositions émergentes

**Forêt tempérée (256 cells) :**
```
forest          160  (62.5 %)
forest_edge      68  (26.6 %)
water_edge       18  ( 7.0 %)
shrub             6  ( 2.3 %)
grass             4  ( 1.6 %)
```

→ Canopée dense au cœur, lisières autour, clairières herbeuses
ponctuelles, quelques mares riveraines.

**Désert chaud (256 cells) :**
```
bare            211  (82.4 %)
grass            33  (12.9 %)
shrub            12  ( 4.7 %)
```

→ Sol minéral majoritaire avec touffes éparses (oasis-style),
arbustes accidentels.

---

## API publique

```python
from engine.wfc_vegetation import (
    # Tileset constants
    T_OCEAN, T_SHORE, T_BARE, T_GRASS, T_SHRUB,
    T_EDGE, T_FOREST, T_WATER_EDGE,
    TILE_NAMES, WOOD_PER_TILE, N_TILES,
    ADJ, BIOME_TILE_PRIORS,

    # Pure function
    run_wfc_on_chunk,           # chunk, sim_seed, cfg → WFCDecision
    count_adjacency_violations, # tiles_grid → int

    # Configuration
    WFCVegetationConfig,
    WFCVegetationState,
    WFCDecision,

    # Sim integration
    install_wfc_vegetation,
    apply_to_existing_chunks,
    wfc_vegetation_state,
    uninstall_wfc_vegetation,
)
```

### Usage type

```python
from engine.wfc_vegetation import install_wfc_vegetation, WFCVegetationConfig

cfg = WFCVegetationConfig(
    wfc_grid_size=16,          # 16×16 = 256 tiles per chunk
    water_threshold_litres=100.0,
    smooth_block_fill=True,
)
install_wfc_vegetation(sim, cfg)

# Désormais chaque chunk fraîchement caché passe par WFC :
# - chunk.wood devient un champ patterné, pas un blob uniforme
# - tile_grid (16×16) accessible via state.decisions[coord].tiles_grid
```

---

## Comparaison avec les autres techniques IA world-gen

| Technique | Wave | Type | Coverage | Compute |
|---|---|---|---|---|
| Genie 3 (DeepMind) | ❌ | Transformer | Tout (image+motion+physique) | GPU farm |
| Terrain Diffusion | ❌ | Diffusion LDM | Heightmap+texture | GPU |
| NCA (Mordvintsev) | 23-25 | Cellular automaton | Heightmap detail | CPU numpy |
| **WFC (Gumin)** | **26** | **Constraint propagation** | **Vegetation distribution** | **CPU numpy** |

Wave 26 complète la palette : Genesis Engine couvre maintenant à la
fois les approches **continues** (NCA, multi-iter erosion) et
**discrètes** (WFC, tile-based PCG). Les deux 100 % pure numpy +
déterministes.

---

## Limitations connues

- **Pas de backtracking** : si la propagation conduit à une
  contradiction (cellule sans tile possible), on reset cette cellule au
  prior biome. Cap à 64 resets/run avant fallback au tile dominant.
  Pour des tilesets plus contraignants (40+ tiles, adjacency stricte),
  ajouter AC-3 / backtracking serait nécessaire.
- **WFC grid coarse** (16×16) : les patches sont blocky à 4×4 pixels.
  Le smooth Gaussien 3×3 atténue mais ne supprime pas. Pour grid 32×32
  il faudrait doubler le compute.
- **Pas de macro-coupling** : le WFC ne lit pas directement `flow_acc`
  ou `boundary_kind` macro. Seule `chunk.water` (qui dérive de Wave 18)
  influe via le forçage water_edge. Wave 27+ pourrait ajouter d'autres
  signaux macro.
- **Tileset fixe** : 8 tiles est volontairement minimal pour la clarté
  pédagogique. Un tileset agronomique réel aurait 30-50 tiles (e.g.
  conifer_dense, deciduous_edge, alpine_meadow, etc.). Hors scope
  Wave 26.

---

## Branchements futurs

| Module | Intégration |
|---|---|
| **Wave 27** | Étendre tileset à 16-24 tiles avec sous-types de forêts. |
| **Wave 28** | Coupler WFC avec `tectonic_geology` boundary_kind pour végétation distincte sur convergent/divergent. |
| `chunk_hydrology` | Lire les rivières Wave 18 pour seeder water_edge en suivant le centerline. |
| `agriculture` | Convertir tiles en `culture_seed_library` valides (forêt = bois récoltable, grass = poaceae). |
| `dashboard` | Rendu tile-grid 16×16 en couleurs (vert dégradé du forest → bare). |
