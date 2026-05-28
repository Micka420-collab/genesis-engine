# Wave 43 — Indices visuels minéraux (Substrate physique)

**Date** : 2026-05-28
**Couche** : Substrate · Géologie
**Smoke** : `runtime/scripts/p113_mineral_visual_cues_smoke.py`
**Crate** : `native/world-engine/crates/geology/`
**Status** : ✅ smoke 10/10 vert

---

## 1. Objectif et règle d'émergence

Un agent doit pouvoir **découvrir** un minerai (cuivre, fer, charbon, sel, etc.)
sans qu'aucun code ne lui dise « il y a du cuivre ici ». La condition rendue
opérationnelle par cette wave : **chaque voxel de surface renvoie une couleur
RGB reproductible**, et cette couleur encode la présence éventuelle d'un dépôt.

L'agent voit donc un **vert vif** (malachite, `[80, 140, 70]`) au pied d'une
falaise grise → mémorise la couleur + lieu → revient avec un outil → creuse →
trouve du cuivre. À aucun moment le runtime ne lui révèle l'identité du minerai.

Référence dans la skill v2.0 (Système F, « Découverte agent ») :

> Les agents ne SAVENT PAS que les ressources existent. Ils les TROUVENT par
> observation, accident, déduction ou transmission culturelle.

---

## 2. Architecture du crate `genesis-geology`

| Fichier      | Rôle                                                                 |
|--------------|----------------------------------------------------------------------|
| `lib.rs`     | Ré-exports publics. Pas de logique.                                  |
| `rock.rs`    | `RockType` (12 variants : Air, Regolith, Clay, …, CoalSeam).         |
| `mineral.rs` | `Mineral` (16 variants), `MineralDeposit`, fonction `affinity()`.    |
| `visual.rs`  | `sample_surface()`, `SurfaceColorHint`, `DISCOVERY_THRESHOLD`.       |

Le crate dépend uniquement de `genesis-core` (pour la `Prf` déterministe) et
de `serde`. Aucun appel `rand::thread_rng`, aucun `Instant::now()` —
contrainte respectée pour la wave discipline `prf_rng-only` (cf.
[memory feedback_wave_discipline]).

---

## 3. Règles de distribution minérale

Les paires `(Mineral, RockType)` autorisées et leurs profondeurs optimales
sont scientifiquement fondées. Extrait du tableau de `mineral.rs::affinity` :

| Mineral        | Host(s)              | Profondeur optimale | Justification géologique             |
|----------------|----------------------|---------------------|--------------------------------------|
| Flint          | Limestone            | 8 m                 | Nodules silicifiés dans carbonate    |
| Copper         | Schist, Granite      | 60–80 m             | Porphyre cuprifère, contact pluton   |
| Tin            | Granite              | 70 m                | Pegmatite granitique                 |
| Iron           | Sandstone, Schist    | 200–250 m           | BIF (banded iron formation)          |
| Gold           | Quartzite, Granite   | 150–200 m           | Filon quartz + cisaillement          |
| Coal           | CoalSeam             | 40 m                | Couche organique compressée          |
| Salt           | Clay                 | 20 m                | Évaporite paléo-marine               |
| Sulfur         | Basalt               | 5 m                 | Volcanique / fumerolle               |
| Obsidian       | Basalt               | surface             | Coulée volcanique vitreuse           |
| Malachite      | Schist, Granite      | 4 m                 | **Cap rock oxydé du cuivre** (tell)  |

Toutes les paires non listées renvoient `affinity = 0.0` → **interdit**. Les
tests `forbidden_pairings_are_zero` et `gold_never_appears_in_clay` verrouillent
les invariants critiques.

### Effet émergent attendu : malachite = signal de cuivre

`affinity(Malachite)` pique près de la surface (depth_opt = 4 m),
`affinity(Copper)` pique plus profond (depth_opt = 60–80 m). Conséquence
sans code dédié : **les patchs de malachite poussent au-dessus des poches
de cuivre**, comme dans la nature. L'agent voit le vert → creuse → tombe
sur le cuivre. Test `malachite_is_surface_marker_for_copper`.

---

## 4. API publique

```rust
use genesis_core::Prf;
use genesis_geology::{sample_surface, RockType};

let prf = Prf::new(world_seed);
let sample = sample_surface(prf, world_x, world_y, world_z, host_rock);

// L'agent regarde le voxel
let rgb: [u8; 3] = sample.color_hint.rgb;
let metallic = sample.color_hint.lustrous;
```

Conformément au principe « ne pas exposer la sémantique », l'agent stocke
`rgb` comme percept opaque dans sa mémoire visuelle. Le mapping
`RGB → Mineral` reste **dans le runtime**, jamais dans l'agent.

---

## 5. Déterminisme

Tous les hachages passent par `Prf::unit_f32(GEOLOGY_LAYER_TAG, x, y, z, salt)`,
où `GEOLOGY_LAYER_TAG = 0x6E07_0643` (signature Wave 43 — ne pas changer sans
bumper la version sauvegardée). Tests :

- `determinism_same_seed_same_output` — 200 voxels relus identiques.
- `different_seeds_diverge` — deux PRF distinctes divergent > 50 %.

Effet bonus : clustering spatial via une seconde sonde `(x/4, y/4, z/4)` — les
dépôts forment des poches au lieu de specks isolés. Test
`deposits_cluster_spatially` exige ≥ 30 % de paires adjacentes de même minéral.

---

## 6. Conformité STONE-AGE

La feedback memory `feedback_stone_age_emergence` impose : **pas de solveurs
analytiques, civilisations émergent depuis Stone Age libre arbitre**. Cette
wave la respecte intégralement :

- Aucun agent n'est pré-informé des emplacements.
- Aucune affordance « ramasser cuivre » exposée.
- Seule donnée disponible : RGB perçu (canal visuel commun à toute la faune).
- L'outillage (frapper la roche, casser, fondre) reste émergent — non couvert
  ici.

---

## 7. Prochaines waves dépendantes

| Wave   | Dépend de Wave 43 ? | Pourquoi                                    |
|--------|---------------------|---------------------------------------------|
| 44     | oui                 | Brancher `sample_surface` sur le percept    |
|        |                     | visuel des agents (canal `visible_objects`) |
| 45     | optionnel           | Étendre aux smells (sulfur) et touch         |
|        |                     | (hardness via Mohs)                          |
| 46     | non                 | Volcanisme dynamique (orthogonal)            |

---

## 8. WORLD_VEILLE_COMBO

Le `WORLD_VEILLE_REPORT` du jour (`docs/veille/2026-05-28_VEILLE.md`) listait
5 combos en backlog Phase 5. Aucun n'était directement applicable au Substrate
aujourd'hui. **La wave 43 n'intègre pas de combo veille externe** — elle
comble un gap structurel identifié par audit interne (Système F « Découverte
agent » de la skill `genesis-engine--world-realism-system-v20`).

> **WORLD_VEILLE_COMBO** : aucun (combo interne — comblement gap émergence)

---

## 9. Métriques Wave 43

```
PHYSICAL_SYSTEMS:
  eau:         ✓ opérationnel (hydrology D8 + drainage)
  erosion:     ✓ (hydraulic + thermal)
  geologie:    ⚙ WIP (Wave 43 : minéraux + color_hint ajoutés)
  atmosphere:  ✓ (climate + weather)
  biologie:    ⚙ WIP (ecosystem)
  decouverte:  ⚙ Wave 43 : canal visuel branché côté monde
  world_model: ○ TODO (Phase 5)

EMERGENCE_OBSERVED:
  surface_color_hints_visible : 16 distinct RGB values
  forbidden_pairings_blocked  : 100 % (test green)
  deposit_clustering_ratio    : ≥ 30 % adjacent same-mineral

INVARIANTS: ✓ tous verts (determinism + gold_never_in_clay + spatial cluster)
```
