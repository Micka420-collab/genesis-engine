# Wave 22 — Global Genesis (monde planétaire partagé)

**Date :** 2026-05-18
**Module livré :** `engine.world_genesis_global`
**Smoke :** `scripts/p51_world_genesis_global_smoke.py` — **9/9 PASS**
**Status :** Livré

---

## Pourquoi

Levier #5 de l'audit Wave 18 (voir `2026-05-18_WAVE19-MACRO-CLIMATE.md`,
table « Branchements futurs »). Avant Wave 22, chaque sim qui voulait
un macro continent appelait
:func:`engine.world_genesis.generate_world` indépendamment.

| Sim       | Macro world   | Plaques    | Fleuves   | Climat    |
|-----------|---------------|------------|-----------|-----------|
| Amazon    | World_amazon  | indép.     | indép.    | indép.    |
| Sahara    | World_sahara  | indép.     | indép.    | indép.    |
| Lausanne  | World_lausanne| indép.     | indép.    | indép.    |
| Reykjavik | World_reykja. | indép.     | indép.    | indép.    |

Conséquences directes :

- Aucune plaque ne traverse une frontière entre régions — chaque
  continent croit être seul sur Terre.
- Aucun bassin versant ne se partage : un fleuve qui coule de l'Amazon
  vers le Sahara dans la réalité n'a aucun sens ici.
- Le climat est *par îlot* : impossible d'avoir une circulation
  Hadley/Ferrel cohérente entre les régions.

Wave 22 corrige cela : **un seul** :class:`GenesisWorld` continental
est généré, et chaque région-sim s'y ancre par son
`sim_origin_macro_km`. Les plaques, fleuves, bandes climatiques et
biomes sont désormais cohérents *inter-régions*.

---

## Architecture

```
                +-----------------------------+
                |  GlobalGenesisConfig        |
                |  (seed, map_size, n_plates) |
                +-------------+---------------+
                              |
                              v
                +-----------------------------+
                |  generate_world() (Wave 16) |
                +-------------+---------------+
                              |
                              v
                +-----------------------------+
                |  GenesisWorld (UNIQUE)      |
                |  - plate_id, flow_acc, etc. |
                +-------------+---------------+
                              |
        +---------------------+----------------------+
        | register_region("alpha", origin_km, ...)   |
        | register_region("beta",  origin_km, ...)   |
        | register_region("gamma", origin_km, ...)   |
        +-------------+----------------+-------------+
                      |                |
                      v                v
              +---------------+ +---------------+
              | RegionAnchor  | | RegionAnchor  |
              | "alpha"       | | "beta"        |
              +-------+-------+ +-------+-------+
                      |                 |
   attach_region_to_sim(state, sim_a, "alpha")
   attach_region_to_sim(state, sim_b, "beta")
                      |                 |
                      v                 v
              +---------------+ +---------------+
              | GenesisAnchor | | GenesisAnchor |
              | sim_a.streamer| | sim_b.streamer|
              +-------+-------+ +-------+-------+
                      |                 |
                      +--------+--------+
                               |
                               v
                pointent toutes vers la MÊME GenesisWorld
                (id(state.world) == id(anchor_a.world)
                                  == id(anchor_b.world))
```

### Pureté

- :func:`build_or_load_global_world` est pure dans son comportement
  observable : RNG entièrement encapsulée dans
  :func:`engine.world_genesis.generate_world` qui route via
  :func:`engine.core.prf_rng`. Même config → même
  ``world_signature``.
- :func:`register_region` n'a aucune RNG, juste validation +
  enregistrement dans le state.
- :func:`attach_region_to_sim` crée l'anchor via
  :func:`engine.world_genesis.make_anchor` (pure) puis branche sur le
  streamer via `set_genesis` + `clear_cache` (déjà testé Wave 16b).
- :func:`find_inter_region_rivers` est un balayage O(R²) déterministe
  sans RNG.

### Cache filesystem

Si `config.cache_path` est fourni :

  1. Le fichier n'existe pas → `generate_world` puis `save_world`
     (npz, round-trip testé Wave 16 step 9).
  2. Le fichier existe → `load_world` directement.

Le smoke step 2 vérifie la double sémantique : premier appel écrit
~210 Ko sur disque, deuxième appel charge sans regénérer et obtient
la *même* signature.

### Validation des bounds

`register_region` raise `ValueError` si `(origin ± size_km)` sort de
`[0, map_size_km]` sur l'un ou l'autre axe. Tolérance `1e-6` pour
absorber les arrondis float. **Pas** de check d'overlap — on autorise
les bandes côtières contiguës / chevauchantes (pour pouvoir simuler
deux régions partageant un même fleuve).

---

## Smoke test — 9 checks

| # | Vérification | Détails |
|---|---|---|
| 1 | API publique exposée | `GlobalGenesisConfig`, `GlobalGenesisState`, `RegionAnchor`, `build_or_load_global_world`, `register_region`, `attach_region_to_sim`, `find_inter_region_rivers`, `global_state_summary` |
| 2 | Cache write+load round-trip | Premier appel : génère + écrit ~210 KB ; second appel : charge avec signature identique |
| 3 | `register_region` bounds | Régions valides acceptées ; raise sur `x = map_size_km + 100`, raise sur `x = -50` |
| 4 | 2 sims ↔ 2 régions | `sim.streamer.genesis is not None` pour les deux, anchors distincts, `state.sim_to_region` tracking |
| 5 | Régions = champs macro distincts | `elev_diff ≈ 922 m`, `plate_diff=True`, `biome_diff=True` (régions sur plaques différentes) |
| 6 | Anchors partagent même `GenesisWorld` | `id(state.world) == id(anchor_a.world) == id(anchor_b.world)` |
| 7 | `find_inter_region_rivers` cohérent | 3 crossings détectés entre `delta_left` ↔ `delta_right`, tous les champs requis présents, `from_region != to_region` |
| 8 | Déterminisme | Deux `build_or_load_global_world(cfg)` → même `world_signature` (`50162e7f1dfa73df…`) |
| 9 | Reporter `global_state_summary` | Clés attendues, valeurs cohérentes (`n_regions=4`, `n_sims_registered=2`, etc.) |

---

## API publique

```python
from engine.world_genesis_global import (
    # Configuration
    GlobalGenesisConfig,
    # State
    GlobalGenesisState,
    RegionAnchor,
    # Build / load
    build_or_load_global_world,    # config -> state (cache-aware)
    # Régions
    register_region,                # state, name, origin_km, ...
    attach_region_to_sim,           # state, sim, region_name -> GenesisAnchor
    # Diagnostics
    find_inter_region_rivers,       # state -> List[Dict]
    global_state_summary,           # state -> Dict
)
```

### Usage type — 3 régions partageant un monde

```python
cfg = GlobalGenesisConfig(
    seed=0xCAFE,
    map_size_km=8000.0,
    resolution=128,
    n_plates=16,
    cache_path="cache/global_world.npz",
)
state = build_or_load_global_world(cfg)

# Région amazonienne au sud-ouest
register_region(state, "amazon",
                sim_origin_macro_km=(2000.0, 3000.0), size_km=4.0)
# Région saharienne au nord-est
register_region(state, "sahara",
                sim_origin_macro_km=(5000.0, 2500.0), size_km=4.0)
# Région alpine au centre
register_region(state, "lausanne",
                sim_origin_macro_km=(4500.0, 1500.0), size_km=4.0)

# Plus tard, à l'instanciation des sims :
sim_amazon = WorldBuilder("amazon").size_km(4.0).founders(20).build().sim
attach_region_to_sim(state, sim_amazon, "amazon")
sim_sahara = WorldBuilder("sahara").size_km(4.0).founders(20).build().sim
attach_region_to_sim(state, sim_sahara, "sahara")

# Les deux sims voient maintenant des chunks issus de la même
# GenesisWorld. Les fleuves macro qui traversent leur frontière
# inter-régions peuvent être listés :
crossings = find_inter_region_rivers(state)
for c in crossings:
    print(f"river {c['flow_acc']:.0f} flows from {c['from_region']} "
          f"to {c['to_region']} at ({c['macro_x_km']:.0f}, "
          f"{c['macro_y_km']:.0f}) km")
```

### Combinaison avec les Waves précédentes

```python
# Wave 22 (cette wave) — monde global partagé
state = build_or_load_global_world(GlobalGenesisConfig(
    seed=0xCAFE, map_size_km=8000.0, cache_path="cache/global.npz"))
register_region(state, "leman", (3000.0, 4000.0))
register_region(state, "manaus", (1500.0, 2200.0))

# Pour chaque sim attaché, Waves 16-19 fonctionnent normalement :
anchor_leman = attach_region_to_sim(state, sim_leman, "leman")
install_tectonic_overlay(sim_leman, anchor_leman)      # Wave 17
install_chunk_hydrology(sim_leman, anchor_leman)       # Wave 18
install_macro_climate(sim_leman, anchor_leman)         # Wave 19

# Wave 15 (global_world inter-region coherence) reste compatible :
gw = GlobalWorld(seed=0xCAFE)
attach_to_global(sim_leman, gw, anchor_lat=46.5, anchor_lon=6.6, bounds_km=4.0)
attach_to_global(sim_manaus, gw, anchor_lat=-3.1, anchor_lon=-60.0, bounds_km=4.0)
```

---

## Limitations connues

- **Pas de migration auto via fleuves** : `find_inter_region_rivers`
  est diagnostique. La détection d'un fleuve traversant n'**injecte
  pas** automatiquement une migration vers la région avale (ce
  serait :class:`engine.global_world.MigrationCoordinator`). Une
  future Wave pourrait brancher les deux.
- **Pas de check d'overlap entre régions** : par design, deux régions
  peuvent partager un même pixel macro (utile pour bandes côtières
  contiguës). Le détecteur de crossings ignore d'office les cellules
  où une cellule réceptrice retomberait dans la *même* région que la
  source.
- **GenesisWorld unique par state** : on n'a *pas* (encore) la
  possibilité d'avoir plusieurs `GlobalGenesisState` qui coopèrent.
  Un state = un monde. Pour une fédération multi-mondes (planète +
  lune), il faudrait refactor.
- **Streaming inter-sim manuel** : Wave 22 garantit la cohérence du
  *terrain* à la frontière mais ne déplace pas physiquement les
  agents. Pour migrer un agent du `sim_amazon` vers le `sim_sahara`,
  il faut toujours appeler `GlobalWorld.request_migration(...)`.
- **Persistence des régions et sims attachés non encore implémentée**:
  seul le `GenesisWorld` est sauvegardé dans le cache npz. Les
  registres `regions` et `registered_sims` sont reconstruits à
  l'usage.

---

## Branchements futurs

| Levier | Module | Bénéfice attendu |
|---|---|---|
| Migration auto | `engine.global_world` | Branche les crossings de Wave 22 sur `MigrationCoordinator` pour qu'un agent qui descend un fleuve macro arrive automatiquement dans la région avale |
| Carte de tectonique partagée | `engine.tectonic_geology` | Faire en sorte que `install_tectonic_overlay` lise les provinces globales plutôt que régionales, pour cohérence des mines / volcans |
| Migration culturelle macro | `engine.polity` | Propagation de cultures le long des bassins versants inter-régions, via les crossings |
| Persistence complète | `engine.world_library` | Sauver `state.regions` + mapping `sim_to_region` dans une archive npz dédiée |

---

## Fichiers livrés

- `runtime/engine/world_genesis_global.py` — ~400 LOC, nouveau module
  (pure overlay sur `world_genesis`).
- `runtime/scripts/p51_world_genesis_global_smoke.py` — ~280 LOC,
  9 checks tous PASS.
- `docs/sprints/2026-05-18_WAVE22-GLOBAL-GENESIS.md` — ce fichier.

Aucun fichier existant modifié : Wave 22 est un overlay pur,
zero-régression sur p44/p45/p46/p47/p48 (tous confirmés 8-9/9 PASS
post-merge).
