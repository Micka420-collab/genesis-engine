# Wave 17 — Tectonic-Aware Geology

**Date :** 2026-05-18 (session 34c)
**Module livré :** `engine.tectonic_geology`
**Smoke :** `scripts/p46_tectonic_geology_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Après Wave 16 (`world_genesis` continental) et Wave 16b (chunk anchor),
la macro-carte tectonique est disponible mais la géologie ne l'utilise
pas encore. La sélection d'`ore_mix` ne consulte que `biome` +
`elevation_m` → un continent post-Wave 16 a sa tectonique réaliste
côté topographie mais des gisements répartis uniformément, ce qui
contredit toute la géologie économique réelle :

- les **porphyries de cuivre** se forment sur les marges
  convergentes océan/continent (Andes, Indonésie, Philippines) ;
- les **VMS (volcanogenic massive sulfides)** apparaissent aux
  dorsales médio-océaniques (Chypre, Oman) ;
- les **évaporites** se déposent dans les bassins de rift confiné
  (Mer Rouge naissante, Rift Est-Africain) ;
- les **systèmes hydrothermaux** dépendent de la vigueur de la
  convergence (uplift rate).

Wave 17 ajoute cette couche.

---

## Architecture

Le module est un **post-pass overlay** sur la géologie de base. Le
pipeline complet devient :

```
1. world_genesis.generate_world(params)           [Wave 16]
2. world.generate_chunk(..., genesis=anchor)      [Wave 16b]
3. geology.generate_chunk_geology(sim, chunk)     [Wave 10 base]
   └─ biome + elevation → ore_mix de base
4. tectonic_geology.apply_overlay_to_chunk(...)   [Wave 17, NEW]
   └─ macro context → boost minéraux par province
```

### Provinces minéralisées

| Province | boundary_kind | plate_kind | neighbour | Minéraux additifs |
|---|---|---|---|---|
| **Andean** | CONVERGENT | OC ou CO | opposé | chalcopyrite, native_gold, cassiterite, pyrite, magnetite |
| **Himalayan** | CONVERGENT | CO | CO | graphite, pyrite, quartz, mica |
| **Island arc** | CONVERGENT | OC | OC | chalcopyrite, native_gold, pyrite |
| **Mid-ocean ridge** | DIVERGENT | OC | * | chalcopyrite, sphalerite, galena, pyrite |
| **Continental rift** | DIVERGENT | CO | * | halite, sylvite, gypsum |
| **Transform fault** | TRANSFORM | * | * | quartz |
| **Passive** | NONE | * | * | (aucun) |

### Fonction de boost

Pour chaque couche `L` à profondeur `d_top` ≥ 5 m :

```
boost(mineral, layer) = base_frac
                       × depth_atten(d_top)
                       × uplift_atten(uplift_rate)
                       × jitter(prf_rng, mineral_index)

depth_atten(d)    = 0.3 si 5 ≤ d < 30
                   0.7 si 30 ≤ d < 200
                   1.0 si d ≥ 200

uplift_atten(u)   = 0.5 + min(u / 300, 1.0)   ∈ [0.5, 1.5]

jitter            = 0.5 + rng.random()         ∈ [0.5, 1.5]
```

Topsoil + regolith (< 5 m) ne reçoivent jamais l'overlay : c'est la zone
de weathering, pas l'hydrothermalisme primaire.

Après injection : renormalisation à `≤ 0.30` (cap par couche, hérité
de `engine.geology._select_ore_mix`).

### Sample tectonic context

`sample_tectonic_context(anchor, x_m, y_m)` :

1. Convertit `x_m, y_m` en coordonnées macro `(x_km, y_km)` via
   `anchor.sim_origin_macro_km`.
2. Snap à la cellule macro la plus proche.
3. Lit `plate_id[iy, ix]`, `boundary_kind[iy, ix]`, `uplift_rate[iy, ix]`.
4. Si boundary ≠ NONE : scan des 4 voisins, le premier voisin avec
   un `plate_id` différent donne `neighbour_plate_kind`.

Cela permet de distinguer subduction (oc/co) de collision (co/co)
sans logique scénarisée.

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique exposée (`sample_*`, `apply_*`, `install_*`, `uninstall_*`) | OK |
| 2 | `sample_tectonic_context` dispatche les 5 provinces (passive, andean, himalayan, mid_ocean_ridge, continental_rift) trouvées sur la carte de test | OK |
| 3 | Andean overlay → Cu 0.002 → 0.0139 (×7), Au 0 → 0.0042 | OK |
| 4 | Andean total Cu 0.0683 strictement > passive Cu 0.0020 (×34) | OK |
| 5 | Mid-ocean ridge boost Zn (sphalerite=0.0245) + Pb (galena=0.0125) | OK |
| 6 | Continental rift boost halite (0.0901) + gypsum (0.0453) | OK |
| 7 | `install_tectonic_overlay` idempotent — second appel renvoie le même state object | OK |
| 8 | Overlay s'exécute réellement (chunks_overlaid=1) + déterminisme inter-sims (snapshots bit-identiques) | OK |
| 9 | `uninstall_tectonic_overlay` restaure `engine.geology.chunk_geology` original et n'laisse aucun hook résiduel | OK |

---

## API publique

```python
from engine.tectonic_geology import (
    # Data classes
    TectonicContext,

    # Sampling
    sample_tectonic_context,    # anchor, x_m, y_m -> TectonicContext

    # Overlay application
    apply_overlay_to_chunk,     # geology, ctx, world_seed -> (n, province)

    # Sim integration
    install_tectonic_overlay,   # sim, anchor -> state (idempotent)
    apply_to_existing,          # sim -> n_overlaid (rescue cached chunks)
    tectonic_state,             # sim -> {chunks_overlaid, provinces, ...}
    uninstall_tectonic_overlay, # sim -> bool

    # Boundary / plate kind constants are re-exported from world_genesis.
)
```

### Usage type

```python
from engine.world_genesis import generate_world, make_anchor, GenesisParams
from engine.tectonic_geology import install_tectonic_overlay, tectonic_state
from engine.geology import install_geology

world = generate_world(GenesisParams(seed=0xCAFE, resolution=128))
anchor = make_anchor(world)

sim = Simulation(SimConfig(name="andes_demo", seed=0xCAFE, founders=20, ...))
sim.streamer.set_genesis(anchor)
sim.streamer.clear_cache()
install_geology(sim)
install_tectonic_overlay(sim, anchor)

for _ in range(500):
    sim.step()

print(tectonic_state(sim))
# {'installed': True, 'chunks_overlaid': 145, 'layers_modified': 580,
#  'provinces': {'passive': 110, 'andean': 18, 'island_arc': 10,
#                'mid_ocean_ridge': 5, 'transform_fault': 2}}
```

---

## Détails d'implémentation

### Monkey-patch transparent

`install_tectonic_overlay` remplace `engine.geology.chunk_geology` par
un wrapper. Le wrapper :

1. Appelle l'original (`_tectonic_inner_chunk_geology`) pour obtenir la
   géologie de base.
2. Vérifie si ce coord a déjà été overlaid (idempotent par chunk).
3. Sample le tectonic_context au centre du chunk.
4. Applique l'overlay en place.

Conséquence : tout code interne à `engine.geology` (notamment `mine_at`
qui appelle `chunk_geology` localement) bénéficie automatiquement de
l'overlay. Le smoke confirme via `chunks_overlaid=1` que le wrapper
s'exécute bien (piège classique : les `from engine.geology import
chunk_geology` au-dessus capturent le binding original ; il faut passer
par `_geo_mod.chunk_geology` pour traverser le patch).

### Déterminisme

`prf_rng(world_seed, ["tectonic_geo", "boost"], [cx, cy, cz])` est
appelé une fois par chunk. Les `rng.random()` consommés à l'intérieur
de l'overlay sont déterministes en nombre (table de minéraux par
province fixée). Deux runs avec la même seed produisent des
`ore_mix` bit-identiques (smoke step 8).

### Limitations connues

- **Pas de hot-spots** : les chaînes de volcans intra-plaques
  (Hawaii, Yellowstone) n'ont pas leur signature minéralisée (Ni-Cu
  d'olivine, kimberlite à diamants). À ajouter dans une Wave 18 si
  besoin.
- **Pas de migration historique** : la signature actuelle reflète la
  position des frontières au temps `t=0` du monde. Une plaque
  continentale qui glisse au-dessus d'un ancien arc volcanique conserve
  son sous-sol Cu/Au IRL — non modélisé ici (la macro est statique
  au tick courant).
- **Pas de zoning vertical fin** : la boost s'applique uniformément à
  toutes les couches ≥ 5 m. En réalité, le porphyre se concentre
  300–1500 m sous la surface, les épithermaux 0–500 m. Possibilité
  d'affiner avec un profil de profondeur par mineral.
- **Pas de couplage temporel** : le système hydrothermal s'épuise sur
  10⁵-10⁶ ans. Ici, la province ne s'épuise pas (les mineral fractions
  restent stables ; seul l'extraction par `mine_at` les diminue).

---

## Branchements futurs (Wave 18+)

| Module | Intégration proposée |
|---|---|
| `meteorology.py` | Consommer `wind_u, wind_v, precip_mm` macro comme champ de forçage régional. |
| `world_builder.py` | `.with_genesis(params)` au moment de `.build()`. |
| `dashboard.py` | Overlay carte tectonique + provinces (heatmap chalcopyrite, halite…). |
| `god_view.html` | Layer "tectonic" : plaques + frontières + provinces. |
| Hot-spot extension | Ajouter un test "is intra-plate volcanic" → kimberlite / Ni-Cu. |
