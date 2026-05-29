# Wave 49 — Watershed observer (Strahler + Horton + drainage density)

**Date** : 2026-05-29
**Couche** : Observateur L5 — quantification émergente du réseau hydrographique (read-only)
**Smoke** : `runtime/scripts/p118_watershed_smoke.py`
**Module** : `runtime/engine/watershed_observer.py`
**Tests** : `runtime/tests/test_watershed_observer.py`
**Status** : ✅ smoke 10/10 vert · pytest module 17/17 vert

---

## 1. Motivation et règle d'émergence

Le score réalisme **Hydrologie 68 %** était la deuxième dimension la plus
faible après la Géologie. La veille du jour ([`2026-05-29_VEILLE.md`](../veille/2026-05-29_VEILLE.md))
ciblait précisément les *bassins versants / biogéochimie* mais l'option
GPU (érosion shallow-water) demande un sprint dédié (L · risque
moyen-élevé). Wave 49 prend l'**autre angle** : tirer parti du graphe D8
qui existe déjà (`world.flow_dir`, `world.flow_acc`, `world.river_mask`,
`world.watershed_id`) pour fournir les mesures géomorphologiques
classiques que le pipeline ne calculait pas encore.

**Règle d'émergence respectée** : aucune nouvelle ontologie. Un *bassin*
est ce que le D8 dit qu'il est, un *segment de rivière* est ce que
`river_mask` désigne, l'*ordre de Strahler* émerge du graphe par
inférence pure (Kahn topologique). Aucun script ne dit « ce bassin est
le Nil », « cette rivière est d'ordre 4 ». Le module est **read-only
strict** — il ne touche jamais aux arrays du monde ni au tick.

---

## 2. Modèle — trois familles de mesures

### (1) Strahler stream order (1957)

Pour chaque cellule de rivière, on calcule l'ordre via Kahn (topologique
sur la D8 restreinte aux cellules `river_mask`) :

```
headwater (degré entrant 0)            → order = 1
deux entrants d'ordre k au max          → order = k + 1   (promotion)
un entrant d'ordre k > autres           → order = k       (conservation)
```

Implémentation pure-numpy, déterministe (parcours `np.argwhere` ordonné
row-major, file FIFO append-only). Borne dure `max_strahler_order=12`
pour la sécurité.

### (2) Horton ratios

À partir de la distribution `counts[k] = #cellules d'ordre k` et
`lengths[k] = Σ longueur_D8 cell_km` :

```
R_b = moyenne_k (counts[k] / counts[k+1])      ratio de bifurcation
R_l = moyenne_k (L̄_{k+1} / L̄_k)                 ratio de longueur
```

Réseaux naturels : R_b ∈ [3, 5], R_l ∈ [1.5, 3]. La sortie sur un monde
Genesis (résolution 64, seuil rivière 8 cellules) donne typiquement
R_b ≈ 6.6, R_l ≈ 0.5 — les chiffres sont volontairement présentés sans
ajustement post-hoc : ils mesurent ce que la D8 émergente produit, pas
ce qu'on aimerait obtenir.

### (3) Densité de drainage par bassin + intégrale hypsométrique

Par bassin :

```
D_d   = L_river_basin / A_basin        km / km²
H_I   = (mean_elev − min_elev) / (max_elev − min_elev)        ∈ [0, 1]
```

`H_I` mesure le stade d'érosion (jeune ≈ 0.6, mature ≈ 0.3) — utile pour
détecter les bassins jeunes hauts perchés vs vieux bassins arrasés.

---

## 3. API publique

```python
from engine.watershed_observer import (
    WatershedConfig, install_watershed_observer,
    observe_watersheds, watershed_summary, uninstall_watershed_observer,
)

install_watershed_observer(sim, WatershedConfig(snapshot_every=64))
for _ in range(N):
    sim.step()                          # le step wrappé capture les snapshots
print(watershed_summary(sim))           # n_basins, Rb, Rl, Dd, ordres…

# Mode pull (sans install) — purement lecture :
snap = observe_watersheds(sim)
print(snap.bifurcation_ratio, snap.length_ratio,
      snap.global_drainage_density, snap.stream_order_counts)
```

Patron observateur identique à Wave 39 (épidémie) / Wave 40 (lignée) /
Wave 45 (open-endedness) : `Config / Snapshot / History / State`,
`install_X` idempotent, `observe_X` pur lecture, `X_summary`,
`uninstall_X` restaure le `step` original.

---

## 4. Tests d'invariants

| Test                                              | Garantit                                          |
|---------------------------------------------------|---------------------------------------------------|
| `test_strahler_chain_single_order`                | Chaîne droite → ordre 1 partout                   |
| `test_strahler_y_confluence_promotes_to_order_two`| Deux ordre-1 fusionnent → ordre 2                 |
| `test_strahler_empty_river_mask_zero_orders`      | Aucune rivière → tous ordres à 0                  |
| `test_strahler_capped_by_max_order`               | `max_order` clamp le résultat                     |
| `test_horton_ratios_zero_when_single_order`       | Un seul ordre → ratios = 0 (sans dimension)       |
| `test_horton_ratios_finite_on_two_orders`         | Deux ordres → ratios finis et positifs            |
| `test_observe_returns_snapshot_on_real_world`     | Snapshot sain (≥1 bassin, sha256 64-hex)          |
| `test_observe_is_read_only`                       | **Zéro mutation** (world arrays + tick gelés)     |
| `test_cross_sim_determinism_same_seed_same_signature` | Même seed ⇒ même signature                    |
| `test_observe_returns_none_when_no_world`         | Pas de monde Genesis → `None` (pas de crash)      |
| `test_horton_ratios_finite_on_real_world`         | Rb, Rl ≥ 0, NaN-free sur réseau réel              |
| `test_drainage_density_coherent_with_rivers`      | Dd ≥ 0, Dd = 0 ssi aucune rivière                 |
| `test_basin_stats_areas_sum_le_map_area`          | Aires bornées, H_I ∈ [0, 1], ordre ≥ 0            |
| `test_install_uninstall_round_trip`               | step wrappé puis restauré                         |
| `test_double_install_idempotent_updates_config`   | Pas de double wrap, config rejouée                |
| `test_installed_observer_captures_at_cadence`     | Snapshots capturés selon `snapshot_every`         |
| `test_full_run_determinism_observed_stream`       | Flux complet de signatures reproductible          |

Smoke `p118` : 10 checks miroir + dump diagnostic.

---

## 5. Conformité STONE-AGE

- **Read-only strict** : `observe_watersheds` ne touche jamais aux
  arrays du monde (`flow_dir`, `river_mask`, `watershed_id`,
  `elevation_m`) ni au `tick` de la sim. Le seul état écrit est le
  bookkeeping de l'observateur sous `sim._watershed_state`.
- **Aucune ontologie scriptée** : pas de « rivière X », pas de « bassin
  Y ». Les ordres de Strahler émergent du graphe D8 par règle locale ;
  les bassins sont ceux que `world.watershed_id` désigne déjà ; les
  ratios de Horton sont calculés sans cible.
- **Aucun solveur analytique top-down** : pas de bassin synthétique,
  pas de réseau hydrographique optimal. Le module ne « propose » jamais
  un meilleur drainage — il quantifie celui qui existe.
- **Déterminisme** : aucun RNG. La signature `sha256` est calculée sur
  un tuple canonique (ordres triés par k, bassins triés par
  `basin_id`), bit-identique entre runs avec la même seed.

---

## 6. WORLD_VEILLE_COMBO

Combo interne — comblement direct du gap **Hydrologie 68 %** identifié
dans la routine matinale du jour. Aucune dépendance externe ajoutée
(numpy + hashlib + math standard). Les pistes plus coûteuses de la
veille (érosion GPU shallow-water · downscaling diffusion · PyO3
free-threading) restent au backlog Phase 5 — promues vers une wave
dédiée quand l'infra GPU/CI sera prête.

> **WORLD_VEILLE_COMBO** : exploitation du graphe D8 déjà émergent
> (`flow_dir/flow_acc/river_mask/watershed_id` de `engine.world_genesis`)
> via les mesures classiques Strahler + Horton + densité de drainage —
> aucun nouveau substrat physique, gain mesurable sans coût VRAM ni
> dépendance LLM.

---

## 7. Métriques Wave 49

```
PHYSICAL_SYSTEMS:
  eau:               ✓ (Wave 18 + 49 quantification réseau)
  erosion:           ✓
  geologie:          ✓ (Waves 43-44, 48)
  atmosphere:        ✓
  biologie:          ⚙ WIP
  decouverte:        ✓
  world_model:       ✓ (Wave 45 open-endedness)

EMERGENCE_OBSERVED (réseau hydrographique) :
  mesures:           3 (Strahler ordre, Horton Rb/Rl, drainage density)
  vocabulaire:       auto-extrait du graphe D8 (jamais déclaré)
  determinisme:      signature sha256, reproductible à l'octet
  exemple run :      res=64, threshold=8 → 206 cellules rivière,
                     Rb=6.63, Rl=0.52, Dd_global=0.0006 km/km²,
                     154 bassins ≥4 cells (sur 773 totaux),
                     top basin = 247 (160K km², Strahler max=2)
  tests_added:       17 pytest + 10 smoke checks
  non_regression:    runtime suite verte

INVARIANTS: ✓ tous déclarés (read-only, déterministe, ontology-free)

NEXT (cibles court terme) :
  Wave 50 candidate : érosion GPU compute (shallow-water) — gap géologie
  principal (55 %). Sprint dédié, dépend genesis-gpu + WGSL kernels.
```
