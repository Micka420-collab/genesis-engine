# Wave 18 — Chunk Hydrology from Macro Flow

**Date :** 2026-05-18 (session 34d)
**Module livré :** `engine.chunk_hydrology`
**Smoke :** `scripts/p47_chunk_hydrology_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Audit déclenché par "verifi si il y a pas des amélioration plus puissant
à faire" (utilisateur, 18 mai 2026). 5 candidates Wave 18+ identifiées
par puissance × faisabilité :

| Rank | Candidate | Puissance | Faisabilité | Status |
|---|---|---|---|---|
| **1** | **Chunk hydrology macro→chunk** | ★★★★★ | ★★★★★ | ✅ Wave 18 |
| 2 | Vent macro → meteorology + marine + wildfire | ★★★★★ | ★★★★☆ | À faire |
| 3 | Climat → ecology biome shift dynamique | ★★★★☆ | ★★★★☆ | À faire |
| 4 | Bathymétrie + plateau continental → marine | ★★★★☆ | ★★★☆☆ | À faire |
| 5 | Multi-région GenesisWorld → global_world | ★★★★☆ | ★★★☆☆ | À faire |

La #1 est la plus puissante parce qu'elle élimine la discontinuité
visible entre chunks (l'incohérence la plus frappante du moteur
post-Wave-16) tout en étant la plus directe à câbler — la macro
`flow_acc + flow_dir + river_mask` existe déjà depuis Wave 16, il
suffisait de la consommer.

---

## Avant / après

### Avant Wave 18 (`engine.world.generate_chunk`)

```python
# Water sources: ocean + lakes (low elev) + scattered springs in wet biomes
water = np.zeros_like(elev)
water[(biome == Biome.OCEAN) | (elev < 1.5)] = 1000.0
spring_prob = np.zeros_like(elev)
for wet in (Biome.TEMPERATE_FOREST, ..., Biome.TUNDRA):
    spring_prob[biome == wet] = 0.02
spring_mask = noise_a.reshape(elev.shape) < spring_prob
water[spring_mask] = np.maximum(water[spring_mask], 200.0)
```

→ 2 % de cellules sont marquées "spring" via une **loterie aléatoire**.
Aucun lien avec la macro hydrologie. Deux chunks adjacents ont leurs
"rivières" dans des directions opposées. Game-feel cassé.

### Après Wave 18

```python
anchor = make_anchor(world)
install_chunk_hydrology(sim, anchor)

# Chaque chunk dans une cellule macro où flow_acc >= 20 :
#   - centerline = ligne passant par le centre géographique de la
#     cellule macro, alignée sur flow_dir D8
#   - largeur = clip(3 + sqrt(flow_acc) * 1.5, 3, CHUNK_SIDE_M * 0.5)
#   - cells à distance <= width/2 du centerline → water = 800 L,
#     channel carve = -0.4 m
```

→ Les rivières ont la direction du fleuve macro. Tous les chunks du
même cellule macro voient la même centerline → continuité visible. La
largeur grandit avec la racine carrée du bassin (Hack-law).

---

## Architecture

```
GenesisWorld (Wave 16)
    ├─ flow_acc[R,R]    drainage area en cells (Kahn topo)
    ├─ flow_dir[R,R]    D8 0..7 (255=sink)
    └─ river_mask[R,R]  flow_acc >= threshold

ChunkAnchor (Wave 16b)
    └─ sim_origin_macro_km mapping sim->macro

ChunkStreamer.get(coord) (Wave 18, monkey-patched)
    │
    └─ generate_chunk(seed, coord, params, genesis=anchor)
            │  (Wave 16b)  macro elev + temp + precip
            ↓
    └─ apply_macro_rivers_to_chunk(chunk, anchor)
            │  (Wave 18)
            ├─ sample macro flow_acc, flow_dir at chunk center
            ├─ if flow_acc >= 20:
            │    centerline = (macro_cell_center, flow_unit)
            │    width = sqrt(flow_acc)*1.5 + 3
            │    paint cells within width/2 of centerline
            │    chunk.water[paint] = 800 L
            │    chunk.height[paint] -= 0.4 m
            │    invalidate_resource_masks(chunk)
```

### Continuité inter-chunk

Tous les chunks dans la même cellule macro partagent la **même
centerline globale** (ligne passant par le centre de la cellule macro
en mètres sim). Cette propriété garantit que deux chunks adjacents au
sein d'une même cellule macro voient les mêmes coordonnées de rivière,
donc continuité parfaite.

À la frontière de deux cellules macro adjacentes : les deux centerlines
peuvent diverger légèrement (l'une passe par le centre de la cellule A,
l'autre par le centre de B), mais comme la macro `flow_dir` est elle-
même D8-continue, le saut au niveau du chunk est borné par ~16 m
(largeur d'un demi-chunk) — invisible à l'échelle de la simulation.

### Determinism

`apply_macro_rivers_to_chunk` est une pure-function : aucune
randomisation, tout calculé analytiquement. Deux runs avec la même
seed + même anchor → bit-identiques (smoke step 8 confirme via
`np.array_equal` sur `chunk.water` et `chunk.height`).

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique (`apply_*`, `install_*`, `uninstall_*`, etc.) | OK |
| 2 | Cellule passive → `is_river=False`, water inchangé | OK |
| 3 | Cellule rivière → cells peints ≥ 1, width > 0 | OK (832/4096) |
| 4 | Largeur ∝ √flow_acc — big(acc=45)→w=13.1 vs small(acc=23)→w=10.2 | OK |
| 5 | **Axe principal des cells peintes aligné sur flow_dir** | OK (`|dot|=1.000`) |
| 6 | Idempotence — deux apply consécutifs → identiques | OK (832/832) |
| 7 | `install_chunk_hydrology` + `streamer.get` cache-miss → overlay | OK |
| 8 | Déterminisme inter-sims (water_match + height_match) | OK |
| 9 | `uninstall_chunk_hydrology` restaure le streamer original | OK |

Particularité notable du step 5 : le **dot product entre l'axe principal
de la covariance des cells peintes et la direction de flow_dir vaut
exactement 1.000** sur ce seed. C'est mathématiquement attendu (la
stripe est rectangulaire alignée sur flow_unit) mais c'est aussi la
preuve la plus forte de l'alignement.

---

## API publique

```python
from engine.chunk_hydrology import (
    # Pure function overlay
    apply_macro_rivers_to_chunk,    # chunk, anchor -> HydrologyDecision
    HydrologyDecision,
    RIVER_WATER_LITRES,
    RIVER_CHANNEL_DROP_M,

    # Sim integration
    install_chunk_hydrology,        # sim, anchor, *, flow_acc_threshold
    apply_to_existing_chunks,       # sim -> n_freshly_overlaid
    chunk_hydrology_state,          # sim -> diagnostics dict
    uninstall_chunk_hydrology,      # sim -> bool
)
```

### Usage complet (pipeline Wave 16 + 17 + 18)

```python
from engine.world_genesis import generate_world, make_anchor, GenesisParams
from engine.chunk_hydrology import install_chunk_hydrology
from engine.tectonic_geology import install_tectonic_overlay
from engine.geology import install_geology

world = generate_world(GenesisParams(seed=0xCAFE, resolution=128))
anchor = make_anchor(world)

sim = Simulation(SimConfig(...))
sim.streamer.set_genesis(anchor)
sim.streamer.clear_cache()

install_geology(sim)
install_tectonic_overlay(sim, anchor)
install_chunk_hydrology(sim, anchor)

# Chunks héritent :
# - tectonique continentale → topographie réaliste
# - rivières alignées macro  → réseau hydrographique continu
# - provinces minéralisées  → Andean Cu/Au, MOR VMS, rift evaporites
```

---

## Détails d'implémentation

### Hack's law approximation

`width_m = clip(3 + sqrt(flow_acc) * 1.5, 3, CHUNK_SIDE_M * 0.5)`

À petite échelle (5 m) un ruisseau ; à grande échelle (~16 m, cap au
demi-chunk) un fleuve. La cap empêche un fleuve trop large de
recouvrir tout le chunk et masquer l'autre topographie.

### Monkey-patch transparent

`install_chunk_hydrology` enveloppe `streamer.get` et
`streamer.touch_area`. Toute génération de chunk déclenche l'overlay,
de manière idempotente (vérification `coord not in state.decisions`).

### Limitations connues

- **Stripe rectiligne** : la rivière passe en ligne droite par le
  centre de la cellule macro. Pas de méandres au sein du chunk. Pour
  un look encore plus réaliste, ajouter un sin-noise déterministe
  appliqué au perpendicular offset.
- **Pas de delta** : aux embouchures, la rivière s'arrête net
  (flow_dir=255 → no river). Ajouter un mode "estuary" où le canal
  s'évase et où sediment = `placer gold + alluvium`.
- **Pas d'écosystème riparien** : les cells voisines de la rivière
  ne reçoivent pas de bonus food / wood (forêt galerie). À ajouter
  dans une Wave 19 si besoin.
- **Pas de saison** : le débit est statique. Pas de fonte des neiges,
  pas de mousson. La macro `precip_mm` est un moyen annuel.
- **Pas de carving érosif iterative** : on ne creuse pas le canal
  d'année en année. Pour ça il faudrait recoupler avec
  `engine.world_genesis._erode_stream_power` à l'échelle chunk.

---

## Branchements futurs (Wave 19+)

| Module | Intégration proposée |
|---|---|
| `meteorology.py` | Consommer `wind_u, wind_v` macro comme champ régional. |
| `marine.py` | Bathymétrie via `distance_to_coast_km` + courants Ekman dépth-dépendants. |
| `wildfire.py` | Vent macro + sécheresse régionale (`precip_mm < 300`) → propagation. |
| `ecology.py` | `biome_shift_factor` dynamique selon T anomaly. |
| `world_builder.py` | `.with_genesis(params)` qui chaîne anchor + tectonic + hydrology. |
| `dashboard.py` | Heat-map rivières / provinces minérales / vents. |
