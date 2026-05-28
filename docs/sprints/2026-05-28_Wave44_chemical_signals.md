# Wave 44 — Signaux chimiques (canal olfactif géologique)

**Date** : 2026-05-28 (même jour, suite de Wave 43)
**Couche** : Substrate · Géologie · Atmosphère (interface)
**Smoke** : `runtime/scripts/p114_chemical_signals_smoke.py`
**Module** : `native/world-engine/crates/geology/src/chemical.rs`
**Status** : ✅ smoke 9/9 vert

---

## 1. Objectif et règle d'émergence

Wave 43 a doté chaque voxel d'un **canal visuel** (RGB). Wave 44 ouvre le
**canal olfactif** : certains minerais — sulfur, coal, salt — émettent un
signal chimique que l'atmosphère transporte avec le vent. L'agent reçoit
une **intensité** dans `[0,1]`, jamais l'identité de la source.

Conséquence directe : un agent perdu dans un désert qui sent une odeur
piquante (Pungent) peut **remonter le vent** pour atteindre la fumerolle
de soufre — exactement le comportement attendu (cf. skill, Système F :
« agent détecte l'odeur dans son rayon olfactif »).

---

## 2. Modèle physique

Plume gaussien simplifié, fermé, ~10 FLOPs par requête :

```
intensity(d, wind, src_strength) =
    src_strength · exp(-d / λ_chem) · upwind_factor(wind, direction)
```

| Paramètre        | Pungent (Sulfur) | Acrid (Coal) | Saline (Salt) |
|------------------|------------------|--------------|---------------|
| `decay_length_m` | 240              | 180          | 40            |
| `base_strength`  | 0.95             | 0.70         | 0.35          |

Le facteur upwind est `clamp(0.55 + 0.45·cos(θ), 0.1, 1.0)` où `θ` est
l'angle entre `(observer − source)` et le vecteur vent. Un observateur
sous le vent reçoit donc jusqu'à 1.0× la plume ; un observateur contre
le vent reçoit toujours 0.1× (diffusion résiduelle).

Le cas `wind_speed < 0.1 m/s` collapse à 0.5 isotrope — c'est le test
`calm_wind_is_isotropic`, garde-fou contre les NaN.

---

## 3. API publique

```rust
use genesis_geology::{emission_at, intensity_at, RockType};
use genesis_core::Prf;

let prf = Prf::new(world_seed);
let src = (sx, sy, sz);

if let Some(em) = emission_at(prf, src.0, src.1, src.2, RockType::Basalt) {
    let intensity = intensity_at(
        em, src.0, src.1, src.2, ox, oy, oz, wind_xy,
    );
    // agent observed intensity ∈ [0, 1]
}
```

Comme Wave 43, l'agent stocke l'intensité + un `SignalKind` opaque dans
sa mémoire. Le mapping `SignalKind → Mineral` reste **côté monde** et
n'est jamais exposé à la cognition agent.

---

## 4. Tests d'invariants (Rust)

| Test                                  | Garantit                                       |
|---------------------------------------|------------------------------------------------|
| `only_smelly_minerals_emit`           | Gold/Iron/Malachite restent silencieux         |
| `intensity_decays_with_distance`      | Plume converge vers 0 à grande distance        |
| `downwind_gets_more_than_upwind`      | Asymétrie vent obligatoire                     |
| `calm_wind_is_isotropic`              | Pas de NaN ni biais directionnel quand wind=0 |
| `at_source_returns_full_strength`     | Continuité au point source                     |
| `determinism_of_emission_sampling`    | (seed, coord, host) ⇒ même émission            |
| `coal_seam_emits_acrid_signal`        | Une fosse de charbon « sent » au moins qqpart  |
| `decay_lengths_are_ordered`           | Pungent > Acrid > Saline (réalisme physique)   |

---

## 5. Conformité STONE-AGE

L'agent ne reçoit qu'une intensité scalaire et un tag opaque
(`SignalKind` n'est jamais nommé dans la cognition). Aucune affordance
type « ramasser soufre quand intensité > X » n'est codée — l'utilisation
des signaux reste à découvrir par l'agent.

---

## 6. WORLD_VEILLE_COMBO

Identique Wave 43 : aucun combo externe intégré (la veille du jour est
focus Agentic). Wave 44 est un **comblement de gap** Système F (canal
olfactif manquant dans le percept agent).

> **WORLD_VEILLE_COMBO** : aucun (combo interne — comblement gap émergence)

---

## 7. Métriques Wave 44

```
PHYSICAL_SYSTEMS:
  eau:         ✓
  erosion:     ✓
  geologie:    ⚙ Wave 43+44 — visuel + olfactif
  atmosphere:  ✓ (vent maintenant utilisé pour la dispersion chimique)
  biologie:    ⚙ WIP
  decouverte:  ⚙ Wave 43 RGB + Wave 44 plumes chimiques
  world_model: ○ TODO

EMERGENCE_OBSERVED:
  signal_kinds:           3 (Pungent, Acrid, Saline)
  emitters:               3 minéraux (Sulfur, Coal, Salt)
  silent_minerals:        12 (Gold/Iron/Malachite/etc.)
  decay_lengths_m:        240/180/40
  tests_added:            8 unit + 9 smoke checks

INVARIANTS: ✓ tous déclarés
```
