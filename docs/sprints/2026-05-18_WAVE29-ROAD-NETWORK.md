# Wave 29 — Road Network Emergence via Dijkstra + MST

**Date :** 2026-05-18 (session 34m)
**Module livré :** `engine.road_network`
**Smoke :** `scripts/p59_road_network_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Wave 28 fournit des sites de peuplement émergents. Sans réseau qui les
relie, ce sont des villes isolées. Wave 29 ajoute la **structure
routière émergente** : les routes suivent les vallées, évitent les
montagnes et les zones tectoniquement actives, et minimisent le coût
total via un MST (minimum spanning tree).

Aucune coordonnée hardcodée. Les routes sont entièrement déterminées
par :
- la topographie (Wave 16)
- les frontières tectoniques (Wave 17)
- les rivières (Wave 18)
- les biomes / NPP (Wave 16)
- la position des settlements (Wave 28)

---

## Architecture

### 1. Cost field (par cellule macro)

```
base                : 1.0
+ slope             : clip(|∇elev|, 0, 50) × 0.4
+ ocean             : 200.0   (cells sub sea level)
+ convergent border : +5.0    (Wave 17 hazard, 4-neighbour dilation)
+ river crossing    : +2.0    (bridge construction)
+ low-food          : (1 − biome_NPP) × 0.3   (no resupply)
+ cliff (slope>80)  : +20.0
```

Le coût est garanti ≥ 1.0 partout. Sur ce monde test : min 2.23, max
246.27. L'océan coûte ~200×, les plaines ~2.

### 2. Dijkstra 8-connectivity

Pure-function `dijkstra_path(cost, start, goal) -> (path, cost)` avec
heapq + matrices de distance et prédécesseurs. Diagonales coûtent
`cost[cell] × √2` (vrai coût géométrique).

### 3. Kruskal MST

Pour N settlements :
1. Pré-calcul Dijkstra entre toutes les N(N-1)/2 paires (O(N² × N²log N)).
2. Tri des paires par coût ascendant.
3. Union-find : pour chaque paire dans l'ordre, ajout au MST si elle
   relie deux composantes différentes.
4. Stop quand N-1 arêtes ajoutées (arbre couvrant complet).

Résultat : un arbre qui connecte TOUS les settlements en N-1 arêtes
avec le coût total **minimal possible** parmi tous les arbres
couvrants.

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique | OK |
| 2 | Cost field shape + min ≥ 1 | OK (min=2.23, max=246.27) |
| 3 | Océan ≥ 100 (drainage) | OK (ocean_min_cost=201.3) |
| 4 | Dijkstra trouve un chemin connexe | OK (len=69, cost=5331) |
| 5 | Chemin Dijkstra valide structurellement (8-conn + cost re-computed) | OK |
| 6 | MST = N-1 arêtes pour N settlements | OK (5 → 4) |
| 7 | Graphe MST connexe (BFS atteint tous les settlements) | OK |
| 8 | Déterminisme bit-identique inter-runs | OK |
| 9 | Render PNG paint roads + settlements | OK (67 road px, 25 sett px) |

---

## Résultats visibles

`docs/renders/wave29_road_network.png` :

- 12 settlements (dots roses) sur world 128×128 seed 0xC0FFEE_42
- 11 arêtes MST (lignes rouges)
- 217 cellules de route au total
- 8 689 km totaux, 789.9 km moyenne par arête
- Routes visiblement :
  - **suivent les vallées et corridors plats** (cost field minimal sur les plaines)
  - **évitent l'océan** (cost 200×)
  - **contournent les chaînes convergent** (+5 penalty)
  - **traversent les rivières au point le plus court** (river penalty +2)

---

## API publique

```python
from engine.road_network import (
    # Configuration
    RoadCostConfig,            # 8 weights for cost field
    RoadEdge,                  # one MST edge (from/to/path/length_km/cost)
    RoadNetwork,               # cost_field + road_mask + edges + totals

    # Core
    compute_cost_field,        # world, cfg → (R, R) float32
    dijkstra_path,             # cost, start, goal → (path, total_cost)
    build_road_network,        # world, settlements → RoadNetwork

    # Visualisation
    render_road_network,       # world, network, settlements → uint8 RGB + PNG

    # Summary
    network_summary,           # network → dict
)
```

### Usage type minimal

```python
from engine.world_genesis import generate_world, GenesisParams
from engine.settlement_emergence import find_settlement_candidates
from engine.road_network import build_road_network, render_road_network

world = generate_world(GenesisParams(seed=0xCAFE, resolution=128))
cands = find_settlement_candidates(world, n_candidates=12,
                                     min_spacing_km=300.0)
network = build_road_network(world, cands)

render_road_network(world, network, cands,
                     path="roads.png")

print(network_summary(network))
# {'n_settlements': 12, 'n_edges': 11, 'road_cells': 217,
#  'total_length_km': 8689.0, 'total_cost': 5238.9,
#  'mean_edge_length_km': 789.9}
```

### Tuning the cost field

```python
from engine.road_network import RoadCostConfig

# Roman-style : straight roads, mountain-tolerant
cfg = RoadCostConfig(
    slope_weight=0.1,      # tolerate slopes
    cliff_penalty=5.0,     # mild cliff penalty
    river_penalty=0.5,     # bridges are cheap
)
```

---

## Limitations connues

- **Pas de hub-spoke** : MST est *minimal* mais pas *robuste*. Une
  arête coupée déconnecte deux composantes. Pour des réseaux résilients
  ajouter k-shortest paths + Steiner trees.
- **Pas de niveau de service** : toutes les routes sont équivalentes
  (chemin/sentier/autoroute confondus). Ajouter un attribut `traffic`
  proportionnel au flux gravitationnel entre villes pour distinguer.
- **8-connectivity** : les routes apparaissent en "escalier" sur les
  grilles. Lissage post-traitement possible avec spline / Catmull-Rom.
- **N² Dijkstra** : pour N=50+ settlements, le pre-compute devient
  cher (50² = 2500 Dijkstra runs). Pour N grand utiliser Multi-source
  ou Johnson's algorithm.
- **Coûts heuristiques** : les pondérations dans `RoadCostConfig` sont
  empiriques. Pour ajuster sur des données réelles, faire un fitting
  sur un corpus de routes historiques + DEM (hors scope ici).

---

## Branchements futurs

| Module | Intégration |
|---|---|
| `polity` | Polities adjacentes via le road network → diplomatie/conflits. |
| **Wave 30** | Flux gravitationnel inter-cités → trade routes émergentes. |
| **Wave 31** | Chunk-level path : zoomer d'une route MST en sentier 32 m. |
| `dashboard` | Affichage interactif des chemins (highlight on hover). |
| Multi-region (Wave 22) | Inter-region MST via les "border outlets". |
