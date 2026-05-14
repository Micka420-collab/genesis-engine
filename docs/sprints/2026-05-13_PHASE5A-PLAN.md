# Phase 5a — Earth-anchored World (plan d'implémentation)
**Date:** 13 May 2026
**Objectif:** remplacer la génération procédurale fBm par un chargeur Earth
réel pour que les agents naissent à de vraies coordonnées GPS et explorent
la vraie Terre.

## Contrat de base — ce qui ne change pas

L'objet `Chunk` de `engine/world.py` reste le même : grilles numpy
`height`, `biome`, `water`, `food_kcal`, `stone`, `wood`, `metal`,
`food_capacity` à la même résolution (CHUNK_SIZE=64, VOXEL_SIZE_M=0.5).
Tout le reste de Phase 4 (perception, cognition, lexique, groupes)
fonctionne sans modification — c'est juste le contenu des chunks qui
devient réaliste.

## Nouveau module `engine/earth.py`

```python
# Pseudocode du contrat — implémentation en Phase 5a

class EarthDataLoader:
    """Charge des tuiles de données Terre réelles pour une bbox donnée.

    Données :
      - Copernicus DEM GLO-30   → height (élévation m)
      - ESA WorldCover 10m      → land cover → biome
      - CHELSA bio1, bio12      → température + précipitation annuelles
      - HydroRIVERS / HydroLAKES → water cells
      - SoilGrids 250m          → soil fertility → NPP modulation
    """

    def __init__(self, cache_dir, origin_lat, origin_lon, bounds_km):
        ...

    def chunk_data(self, chunk_coord) -> dict:
        """Retourne {'height', 'biome', 'water', 'food_capacity', 'stone',
                     'wood', 'metal'} alignés sur la grille Chunk."""
        ...
```

Le ChunkStreamer existant accepte un `EarthDataLoader` optionnel ; s'il est
fourni, `generate_chunk` consulte le loader avant de retomber sur la
génération procédurale (pour les chunks hors bounds réels).

## Conversion lat/lon ↔ coordonnées sim

Utiliser une projection métrique centrée sur `origin_lat, origin_lon`. Pour
les bounds < 100 km, une projection azimuthal-équidistante locale (ou
simplement equirectangular avec correction `cos(lat)`) suffit. Au-delà, on
passe à UTM zone matching ou à `pyproj.Transformer`.

Helper :
```python
import pyproj
PROJ_LOCAL = pyproj.Proj(proj="aeqd", lat_0=origin_lat, lon_0=origin_lon)
x_m, y_m = PROJ_LOCAL(lon, lat)
```

## Mapping land cover → Biome interne

ESA WorldCover 11 classes → enum `Biome` existant :

| WorldCover | → Biome |
|---|---|
| 10 Tree cover (latitude/climate-aware) | TROPICAL_RAINFOREST / TEMPERATE_FOREST / BOREAL_FOREST |
| 20 Shrubland | SAVANNA |
| 30 Grassland | GRASSLAND |
| 40 Cropland | GRASSLAND (Phase 5a) ; à séparer en Phase 5e |
| 50 Built-up | (skip — pas de bâti pour l'instant) |
| 60 Bare / sparse | HOT_DESERT ou COLD_DESERT selon temp |
| 70 Snow and ice | ICE |
| 80 Permanent water | OCEAN |
| 90 Herbaceous wetland | GRASSLAND (à enrichir Phase 5d) |
| 95 Mangroves | TROPICAL_RAINFOREST |
| 100 Moss and lichen | TUNDRA |

La classification fine (forêt boréale vs tempérée) utilise la valeur
CHELSA bio1 (mean annual temperature) à la cellule.

## Dépendances Python à ajouter

```
rasterio>=1.4
geopandas>=1.0
pyogrio>=0.8
pyproj>=3.6
xarray>=2025.0
boto3>=1.34   # pour AWS Open Data S3 (Copernicus DEM)
```

ERA5 / cdsapi est *optionnel* en 5a — la météo réelle horaire arrive en 5b.
En 5a on utilise juste les normales CHELSA pour calibrer climat de base
et seasonality.

## Cache disque

Les COG Copernicus DEM et WorldCover sont accessibles en stream depuis S3
sans téléchargement complet. Pour CHELSA, HydroRIVERS, SoilGrids on
télécharge les tuiles concernées localement dans
`runtime/data/earth_cache/<dataset>/<tile_id>.tif`. Taille typique pour
une bbox de 50×50 km :
- DEM : streamé depuis S3, jamais stocké en entier
- WorldCover : ~50 MB par tuile 3° × 3°
- CHELSA bio1+bio12 : ~5 MB par variable
- HydroRIVERS shapefile : déjà découpé par continent ~200 MB
- SoilGrids : ~20 MB par couche × profondeur

Budget total : ~500 MB de cache par région d'intérêt.

## Tests d'acceptation Phase 5a

1. **`test_earth_loader.py`** — charger une bbox connue (Lac Léman :
   `lat_min=46.30, lon_min=6.10, lat_max=46.55, lon_max=6.70`) et vérifier :
   - élévation moyenne ~600 m (niveau du lac à 372 m, mais le terrain alentour monte)
   - majorité de la zone OCEAN ou GRASSLAND/TEMPERATE_FOREST
   - rivière Rhône détectée dans les water cells

2. **Sim déterministe** — un même `(seed, origin_lat, origin_lon)` produit
   le même monde bit-à-bit entre deux exécutions.

3. **Phase 4 pass-through** — l'expérience `phase4_smoke_60` rejoué avec
   le loader Earth activé doit produire le même nombre de vocalisations
   / groupes / births (à 5 % près) qu'avec le worldgen procédural. Le
   changement de monde ne casse aucun chemin de code.

4. **Visualisation** — le dashboard HTML rend la même tile en biome view
   et en élévation view ; on doit reconnaître la carte au coup d'œil.

## Effort estimé

- Module `earth.py` complet + tests : **3–4 jours**
- Adaptation `world.py` + `world_to_chunk` : **1 jour**
- Téléchargement + cache des tuiles + scripts CLI : **1 jour**
- Doc + script de bootstrap (`scripts/fetch_earth_tile.py`) : **1 jour**
- Buffer pour calibration biome mapping + tests : **2 jours**

Total : ~1.5 semaine pour un dev seul.

## Out of scope pour 5a (reporté à 5b–5e)

- Espèces réelles / écosystème (Phase 5d via GBIF)
- Météo horaire ERA5 (Phase 5b)
- Calibration nutritionnelle USDA / BMR (Phase 5c)
- Couche culturelle anthropologique (Phase 5e)

## Premier livrable proposé

Un script :
```bash
python scripts/fetch_earth_tile.py --lat 46.40 --lon 6.45 --bounds-km 30
```
qui télécharge tout ce qu'il faut dans `runtime/data/earth_cache/`, suivi de :
```bash
python experiments/phase5a_leman.py
```
qui spawn 60 founders sur la rive nord du Léman et logge un journal
`journals/phase5a_leman.jsonl` — c'est la première fois que les agents
explorent réellement notre monde.
