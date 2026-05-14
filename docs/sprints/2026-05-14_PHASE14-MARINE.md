# Sprint Phase 14 — Marine (Wave 5)

**Date** : 2026-05-14
**Pilier FUTURE-VISION** : pilier 3 (biosphère vivante) — étendre la
biologie au domaine OCEAN qui jusqu'ici était de l'eau morte
(`chunk.water > 5` → flag binaire, rien d'autre).

## Cible

Donner au biome OCEAN trois sous-systèmes coopératifs :

1. **OceanCurrentField** — champ vectoriel de courant de surface par
   chunk, forcé par un vent synoptique déterministe.
2. **Tides** — phase tidale globale sur la période M2 lunaire
   (12 h 25 min) modulant l'épaisseur d'eau côtière.
3. **Marine biology** — Lotka-Volterra plancton → poissons → prédateurs,
   plancton alimenté par la photosynthèse OCEAN (qui avait été désactivée
   à `(0, 0, 0)` faute de modèle marin).

Tout cela en **Python pur** (au layer Genesis-L4 Feedback) sans toucher
au crate Rust `substrate/water` (Saint-Venant CPU reference, commit
`fc3d472`) — celui-ci reste R&D, la couche Python livre du physique
utilisable aujourd'hui avec un chemin d'évolution clair.

## Architecture livrée

### `runtime/engine/marine.py` (~530 LOC)

```python
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"
```

Trois dataclasses :

* `OceanCurrentField` — `(CHUNK_SIZE, CHUNK_SIZE) float32` × 2 (u, v) +
  `ocean_mask`. Initialisé via `prf_rng` (bruit zero-mean cellulaire) ;
  per-tick mis à jour par `tick_currents` (couplage vent + décay
  newtonien + cap à `CURRENT_MAX_MS = 1.5 m/s`).
* `MarineBiologyPool` — scalaires `plankton_kg`, `fish_kg`, `predator_kg`
  par chunk. ODE Lotka-Volterra Euler-forward, coefficients calibrés
  pour atteindre un quasi-équilibre en ~500 ticks à `drive_accel=1500`.
* `MarineState` — global, attaché à `sim._marine_state`. Expose
  `chunk_marine_fish_kg` (side-table consultable par n'importe quel
  consumer sans importer `marine`).

Vent par chunk : pure fonction de `sim.tick × drive_accel` et
de `(cx, cy)`. Période synoptique 6 sim-jours, phase chunk dérivée
d'un hash déterministe de la coord. Aucun appel `random.random()`.

Marée : phase = `(sim_seconds mod M2_PERIOD_S) / M2_PERIOD_S × 2π`,
hauteur = `amplitude × sin(phase)`. Au passage proche du shore (cellules
OCEAN avec voisin non-OCEAN détectées via dilatation 3×3 vectorisée),
on ajuste `chunk.water` de `±100 L/cell` par mètre de marée.

Plancton couplé à la photosynthèse : `_plankton_input_from_photo` lit
`sim._photo_state.chunk_caches[coord].last_kcal_per_tick[ocean]` et le
convertit en gain de biomasse via `PLANKTON_GPP_GAIN = 0.002 kg/kcal`.
Si la photosynthèse n'est pas installée → fallback à 0 (les seeds
plancton + intrinsic growth suffisent pour amorcer la LV).

### Updates connexes

| Fichier | Changement |
|---|---|
| `engine/photosynthesis.py` | `BIOME_PATHWAY_MIX[OCEAN] = (1.0, 0, 0)` — phytoplancton C3-like (Sage 2004) |
| `engine/world_model_capabilities.py` | `engine.marine` ajouté à `_REQUIRED_MODULES` (7/7 tagged) |
| `engine/dashboard.py` | `/api/marine_state` + overlay `marine` (gradient bleu profond → cyan vif sur la magnitude de courant) |
| `engine/world_library.py` | `marine` ajouté à `_PERSISTENT_MODULES` (round-trip save/load → `marine.json` + `marine.npz`) |

## Determinisme

Tous les RNG transitent par `engine.core.prf_rng`. Le test P25 vérifie
en step 5 que deux simulations seedées identiquement produisent un
hash SHA-256 de `marine_state(sim)` strictement bit-identique :

```
a=d50ff5d22ee288cafac79095 b=d50ff5d22ee288cafac79095
```

## Tests

### P25 — `runtime/scripts/p25_marine_smoke.py` (6/6 PASS)

```
ocean_chunks   : 20
current_chunks : 213
mean_current_ms: 1.5000
tide_height_m  : -0.4943
plankton_total : 3548.941 kg
fish_total     : 538.391 kg
predator_total : 3688.753 kg
```

* Step 1 OCEAN current fields are non-empty — 20 chunks
* Step 2 tide phase advanced — `phase=4.86 rad` après 500 ticks
* Step 3 plancton biomass > 0 — 3549 kg total
* Step 4 fish biomass > 0 — 538 kg total
* Step 5 déterminisme — hashs égaux
* Step 6 ADR-0005 audit clean — 7/7 modules tagged

### Régression

| Smoke | Avant | Après |
|---|---|---|
| `p18_capabilities_lint` | 6/6 | 7/7 (+marine) |
| `p20_physiology_smoke` | 7/7 PASS | 7/7 PASS |
| `p21_photosynthesis_smoke` | 7/7 PASS | 7/7 PASS |
| `p22_material_aging_smoke` | 6/6 PASS | 6/6 PASS |
| `p23_persistence_roundtrip` | 7/7 PASS | 7/7 PASS |

Aucune régression.

## Limites / scope non livré

* **Saint-Venant Rust** — pas wiring. La Python actuelle ne fait pas
  d'advection véritable, juste un forcing vent + décay. Le chemin
  d'évolution : remplacer le corps de `tick_currents` par un appel
  vers le crate Rust quand le binding sera prêt. Le shape de
  `OceanCurrentField` (u, v, ocean_mask) reste compatible.
* **Marée régionale** — la phase est globale (toute la planète marée
  en même temps). Un futur pas : décaler la phase par longitude /
  latitude lunaire.
* **Plancton spatial** — biomasse stockée par chunk, pas par cellule.
  Acceptable pour la première vague ; un pas futur pourrait répartir
  cellulairement comme `chunk.food_kcal`.
* **Pêche / agents** — les chunks publient `chunk_marine_fish_kg` mais
  aucun ActionKind FISH n'a été ajouté à `cognition`. C'est volontaire
  (scope du sprint) — le wiring agents↔fish biomass sera Phase 15.

## Prochaine étape (Phase 15 — R&D)

* Wirer un `ActionKind.FISH` qui consomme `MarineBiologyPool.fish_kg`
  et nourrit l'agent (équivalent FORAGE pour eau).
* Brancher le crate Rust `substrate/water` via un binding pyo3 pour
  remplacer la couche placeholder de `tick_currents`.
* Étendre les overlays HUD (carte des courants, prochaine marée).

## Fichiers modifiés / créés

* `runtime/engine/marine.py` (créé, ~530 LOC)
* `runtime/scripts/p25_marine_smoke.py` (créé, ~170 LOC)
* `runtime/engine/photosynthesis.py` (1 ligne : OCEAN pathway mix)
* `runtime/engine/world_model_capabilities.py` (1 ligne ajoutée au tuple)
* `runtime/engine/dashboard.py` (~30 lignes : import + endpoint + overlay)
* `runtime/engine/world_library.py` (2 ajouts : `_PERSISTENT_MODULES`
  + integrity hash list)
* `docs/sprints/2026-05-14_PHASE14-MARINE.md` (ce fichier)
