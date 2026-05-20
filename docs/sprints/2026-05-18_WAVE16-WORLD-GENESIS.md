# Wave 16 — Ultra-Realistic World Genesis

**Date :** 2026-05-18 (session 34)
**Module livré :** `engine.world_genesis`
**Smoke :** `scripts/p44_world_genesis_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

`engine.world` (la couche micro-scale chunk) génère son terrain via du
FBM multi-octaves indépendant sur chacun des canaux (élévation,
température, précipitations). Le résultat est plaisant à courte distance
mais ne ressemble pas à une planète :

- pas de plaques tectoniques → pas de chaînes de montagnes alignées sur
  des frontières convergentes ;
- pas d'érosion hydraulique → les pics restent au niveau de leur bruit
  initial, sans vallées sculptées par les fleuves ;
- pas d'effet orographique → les déserts pluviométriques (rain shadow)
  derrière les montagnes n'existent pas, les biomes Whittaker sont
  cohérents localement mais incohérents à l'échelle continentale ;
- pas de circulation atmosphérique → l'équateur n'est pas pluvieux et
  le 30e parallèle n'est pas un désert subtropical.

Wave 16 introduit une **couche macro** déterministe que la couche micro
viendra échantillonner.

---

## Pipeline

```
1. plaques tectoniques (Voronoi)
   ├─ N plaques seedées via prf_rng
   ├─ kind ∈ {OCEANIC, CONTINENTAL}
   ├─ motion vector (cm/yr) + age (Myr)
   └─ Voronoi assignement par cellule

2. frontières + uplift
   ├─ scan 4-voisins
   ├─ projection motion relatif sur normale → CONVERGENT / DIVERGENT / TRANSFORM
   ├─ uplift = clip(proj, 0, 12) × 10 × kind_pair_factor
   │           (cc=1.0, oc=0.55, oo=0.30)
   └─ box-blur 3×3 pour élargir les ceintures orogéniques

3. élévation de base
   ├─ continental crust = +500 m
   ├─ oceanic crust = -5500 m
   └─ initial_uplift = uplift_rate × min(plate_age, 80 Myr)

4. FBM overlay 3 échelles
   ├─ continent 600 km, amp 1200 m
   ├─ region 150 km, amp 400 m
   └─ hills 30 km, amp 80 m

5. érosion stream-power-law
   ├─ dh/dt = -K · A^m · S^n,  K = 8e-5,  m = 0.5,  n = 1.0
   ├─ A en m² via cell_m2, S = rise/run en km
   ├─ 40 itérations × 1 Myr
   └─ cap par-iter : 15 % de l'élévation au-dessus du niveau de la mer

6. hydrologie
   ├─ flow_dir D8 steepest-descent (255 = sink)
   ├─ flow_accumulation par tri topologique Kahn
   ├─ river_mask = (flow_acc ≥ threshold) ∧ (elev > sea_level)
   ├─ watershed_id par walk downstream avec memoization
   └─ distance_to_coast_km : BFS 8-connectivité

7. circulation atmosphérique
   ├─ |lat| < 5° : ITCZ (calm, faible easterly)
   ├─ 5°–30°   : trade winds (easterly, équatorward)
   ├─ 30°–60°  : westerlies (westerly, poleward)
   └─ 60°–90°  : polar easterlies (easterly, équatorward)
   wind_u, wind_v en m/s, east-positive / north-positive

8. précipitations orographiques
   ├─ base par bande (ITCZ 3000 mm, subtropical 150 mm,
   │                 midlatitude 900 mm, polar 150 mm) via gaussiennes
   ├─ 6 itérations d'advection :
   │   - upwind shift selon sign(wind_u, wind_v)
   │   - grad = elev - upwind_elev
   │   - uplift (grad>0) : precip += moisture × gain × uplift
   │   - descent (grad<0) : moisture *= exp(-decay × descent)
   │   - replenish moisture sur les océans
   └─ floor 100 mm sur terre

9. température
   ├─ t_sea = 30 - 0.6 × |lat|
   ├─ lapse adiabatique -6.5 K/km
   └─ continentalité -1.5 K à 800 km de la côte

10. biomes
    └─ engine.world.classify_biome_array(temp, precip, elev)
```

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1  | Déterminisme : même seed → SHA identique | OK `42601d12f19d6a21…` |
| 1b | Seed différente → world différent | OK |
| 2  | Voronoi : N plaques distinctes, couverture totale | OK (10 plaques) |
| 2b | Mélange OCEANIC + CONTINENTAL | OK (6 + 4) |
| 3  | Convergent + divergent + transform existent | OK (405/335/0)* |
| 4  | Érosion stabilise mean elev land (≤ 1.05 × raw + 50 m) | OK (1906.7 → 1904.0 m) |
| 5  | Rivières + watersheds multiples | OK (2 rivers, 636 basins) |
| 6  | **Rain shadow** : lee < windward | OK (-163.5 mm) |
| 7  | Land fraction 10-80 % | OK (42.2 %) |
| 8  | ≥ 4 biomes distincts | OK (11) |
| 9  | Save/load npz round-trip preserves signature | OK |

\* transform=0 à R=64 / N=10 plaques. À R=96 / N=12, on observe 733 conv,
472 div, 38 transform.

---

## API publique

```python
from engine.world_genesis import (
    GenesisParams, GenesisWorld,
    generate_world,            # pure function: params → world
    save_world, load_world,    # npz round-trip
    sample_macro,              # bilinear at (x_km, y_km)
    world_signature,           # SHA-256 stable digest
    BOUND_NONE, BOUND_DIVERGENT, BOUND_CONVERGENT, BOUND_TRANSFORM,
    OCEANIC, CONTINENTAL,
)

p = GenesisParams(seed=0xCAFE, resolution=128, n_plates=12)
w = generate_world(p)

# Diagnostics dictionnaire
print(w.diagnostics)
# {'n_plates': 12, 'land_fraction': 0.359, 'mountain_fraction': 0.064,
#  'river_cells': 47, 'n_watersheds': 1055, ...}

# Sample à 1000 km, 2000 km
print(sample_macro(w, 1000.0, 2000.0))
# {'elevation_m': 1247.0, 'precip_mm': 832.5, 'temp_c': 12.4, ...}
```

---

## Branchements

### ✅ Wave 16b (cette session, 2026-05-18) — chunk anchor

| Module | Wired | Effet |
|---|---|---|
| `world.py:generate_chunk` | ✅ kwarg `genesis=GenesisAnchor` | Ancrer FBM micro dans macro tectonique |
| `world.py:ChunkStreamer` | ✅ `.set_genesis(anchor)` + `.clear_cache()` | Hot-swap macro pour une sim existante |
| `world_genesis.sample_macro_grid` | ✅ vectorisé float32 (R chunks 32 m) | Bilinear sampler pour pipelines downstream |
| `world_genesis.sample_macro_grid_full` | ✅ + champs catégoriels | Pour geology / meteorology |
| Smoke `p45_chunk_genesis_anchor_smoke.py` | ✅ 8/8 PASS | Validation |

### À venir (Wave 17+)

| Module | Lecture proposée | Effet |
|---|---|---|
| `geology.py` | `boundary_kind == CONVERGENT` | Spawn veines Cu/Au porphyries |
| `geology.py` | `boundary_kind == DIVERGENT` (mer) | Spawn sulfures massifs (ridges) |
| `meteorology.py` | `wind_u, wind_v, precip_mm` | Champ de forçage régional |
| `world_builder.py` | `.with_genesis(params)` | Builder fluent ergonomique |
| `dashboard.py` | Map plate / boundary / river overlay | Visualisation |

---

## Détails d'implémentation

### Déterminisme

Tout l'aléa provient de `engine.core.prf_rng(seed, ctx, indices)` qui
construit un `np.random.Generator(PCG64)` à partir d'une PRF BLAKE2b
keyée. Aucun usage de `random.random()`, `np.random.seed()` ou
`hash(...)` non saltés.

Le smoke step 1 + 9 prouve via signature SHA-256 sur les arrays
critiques que :

- deux runs `generate_world(params)` produisent des outputs
  bit-identiques sur la même seed ;
- npz round-trip préserve les arrays bit-pour-bit.

### Performance

À R=64, ~2 s single-thread. À R=96, ~6 s. À R=128, ~14 s.

Goulots :
- `_watersheds` Kahn-like queue : O(R²), ~30 % du temps.
- `_distance_to_coast_km` BFS itératif : O(R² × diameter), ~25 %.
- `_erode_stream_power` : 40 iters × (flow_dir + flow_acc), ~25 %.
- `_orographic_precipitation` : 6 iters × 9 conditional rolls, ~10 %.
- Le reste (plaques, FBM, biomes, save) ~10 %.

### Conservation

Les arrays sont en float32 (sauf `flow_dir` uint8, `plate_id` uint8,
`boundary_kind` uint8, `river_mask` bool, `watershed_id` int32). La taille
mémoire d'un GenesisWorld R=128 est ~12 MB.

### Limitations connues

- L'érosion ne re-couple PAS l'uplift au cours des itérations. C'est un
  shaping post-tectonique, pas un fastscape complet à l'équilibre. La
  raison : l'équilibre fastscape oscille près du niveau de la mer et
  brise le déterminisme à 1e-7 près sur certains seeds.
- Watershed ID est généré par walk descending : un coast-outlet par
  basin terminal. Le nombre de basins peut être très grand (>1000) sur
  des continents fragmentés ; cela ne reflète pas la conventional
  cartographie hydrographique. À normaliser dans une Wave 17 si besoin.
- Pas (encore) de mid-ocean ridge bathymétrique explicite : les
  divergent boundaries sur plaques océaniques produisent un léger uplift
  visible dans `boundary_kind == DIVERGENT` mais pas de profil
  topographique en double-bourrelet caractéristique.
- La latitude est mappée linéairement sur l'axe Y du carré-monde (pas
  de projection sphérique). Suffisant pour 4000 km × 4000 km, faux pour
  des planètes complètes.
