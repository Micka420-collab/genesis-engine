# ADR 0006 — Substrate physical layer foundation

- **Statut** : Accepted
- **Date** : 2026-05-14
- **Décideurs** : agent autonome cron `genesis-engine--world-realism-system-v20`
- **Veille déclencheur** : `WORLD_VEILLE_REPORT-2026-05-14b.md`

## Contexte

La doctrine Genesis ("Reality Engine", "World Creation Software")
exige un monde physique ultra-réaliste où chaque phénomène naturel
est *calculé* et non scripté — l'eau coule vraiment, la roche s'érode
vraiment, les minéraux apparaissent là où une histoire géologique
cohérente les place.

À ce jour le crate `ge-world` ne contient qu'un échantillonneur 2D
(heightmap + climat + biome) basé sur du bruit FBM. Pas de voxel
volumique 3D, pas de simulation hydraulique, pas de géologie en
couches, pas de fertilité du sol. C'est suffisant pour générer une
carte ; ça ne l'est pas pour faire émerger des vallées, des deltas,
des sources, ou des filons de cuivre.

Le cron task `world-realism-system-v20` définit 7 systèmes physiques
à implémenter (A water, B erosion, C geology, D atmosphere, E biology,
F discovery, G world-model). Tous dépendent d'un **substrat de
données voxel commun**. Ce substrat n'existe pas encore.

Deux options ont été examinées :

1. **Étendre `ge-world`** avec un sous-module `physical/` et y ajouter
   les voxels 3D.
2. **Créer un crate dédié `ge-substrate`** isolant la couche physique
   du générateur de monde (qui reste en 2D pour le worldgen initial).

La veille du jour a également identifié `bevy_voxel_world` comme
candidat d'intégration future (meshing, chunk LOD plug-and-play) mais
*pas pour ce sprint* — on a besoin d'une référence CPU bit-exact
avant tout port GPU.

## Décision

**Créer un nouveau crate `scaffolding/crates/ge-substrate`** qui :

1. **Définit les types voxel fondamentaux** en `#[repr(C)]` avec
   alignement GPU :
   - `WaterVoxel` (volume, vélocité, sédiment, T°, salinité, turbidité)
   - `SoilHydro` (water_content, porosity, permeability, field_capacity,
     wilting_point, organic_matter)
   - `GeoVoxel` (rock_type, mineral_id, mineral_pct, hardness, porosity,
     permeability, temperature, age_strat, color_hint)

2. **Fournit une implémentation CPU de référence** du pas Saint-Venant
   (équations en eau peu profonde) — la cible WGSL viendra dans un
   sprint ultérieur, *après* validation bit-exact CPU.

3. **Garantit les invariants physiques** dès aujourd'hui :
   - Conservation de masse d'eau (delta < 1e-4 sur 1000 pas).
   - Déterminisme (même seed + même grille → même résultat bit-exact).
   - Localité (un voxel n'est affecté que par ses 4 voisins
     immédiats).

4. **N'introduit aucune dépendance lourde aujourd'hui** :
   - PAS de `bevy_voxel_world` (réservé pour un sprint dédié quand le
     meshing sera utile).
   - PAS de `wgpu` (port GPU dans un sprint séparé).
   - PAS de bridge Python pour Cosmos/GenCast (sprint
     "neural-climate-integration" prévu en backlog).

## Conséquences

### Positives

- **Unblock immédiat** de SYSTÈME A (eau) du cron task. Les SYSTÈMES
  B (érosion), C (géologie), E (biologie sol) peuvent alors démarrer
  car ils dépendent du substrat voxel.
- **Test-first appliqué au GPU** : la référence CPU permettra de
  *valider* la future implémentation WGSL par comparaison bit-exact
  sur de petites grilles. C'est la seule façon raisonnable de
  débugger un compute shader.
- **Pas de couplage prématuré** au runtime Bevy/wgpu : le crate
  reste utilisable depuis n'importe quel hôte (CLI, tests, bench,
  futur service Rust headless).
- **Documentation des invariants physiques** explicite dans les
  `debug_assert!` — ils survivent au release build pour les
  vérifications critiques.

### Négatives

- **Perf CPU non production** : Saint-Venant sur CPU à 256×256
  prendra ~10–50ms par step (vs <2ms en WGSL cible). C'est
  acceptable pour les tests, pas pour le runtime live.
- **Duplication temporaire** : il faudra réimplémenter la même logique
  en WGSL plus tard. Mais c'est *voulu* : la version CPU sert d'oracle.
- **Pas encore d'intégration ECS** : le crate ne déclare pas de
  `Component` Bevy aujourd'hui — on l'ajoutera quand le pipeline ECS
  substrate sera défini (probablement quand `bevy_voxel_world` arrivera).

## Alternatives considérées

- **Étendre `ge-world`** : rejeté. Le générateur de monde 2D et la
  simulation physique 3D ont des cycles de vie, des consommateurs et
  des contraintes de perf très différents. Mélanger les deux dans un
  même crate alourdirait `ge-world` et compliquerait le port GPU
  ultérieur.
- **Implémenter directement en WGSL** : rejeté. Sans oracle CPU, le
  débogage d'un compute shader hydraulique est une perte de temps
  garantie. La référence CPU se rentabilise dès le premier bug GPU.
- **Adopter `bevy_voxel_world` comme fondation** : rejeté pour
  *aujourd'hui*. Le crate gère le meshing et le rendu, pas la physique
  du contenu des voxels — c'est complémentaire mais pas un substitut.
  On l'ajoutera dans un sprint dédié rendu/visualisation.
- **Bridge Python pour Cosmos-Predict2.5 / GenCast** : rejeté pour
  *aujourd'hui*. Découvertes majeures de la veille mais nécessitent
  GPU H100/A100 et un sprint dédié (3-4 semaines). Inscrites dans
  `COMBO_BACKLOG`.

## Validation

Métriques de succès, vérifiables au commit :

1. `cargo check -p ge-substrate` → OK
2. `cargo test -p ge-substrate` → tous les tests verts incluant :
   - `test water_step_conserves_mass_property` (10 itérations
     randomisées, delta absolu < 1e-4 sur 100 steps).
   - `test water_flows_downhill` (sur une pente simple, le volume
     se déplace vers la cellule la plus basse).
   - `test voxel_layout_matches_repr_c` (taille et alignement
     stables — futur-proof pour port GPU).
3. Aucun `unsafe` ajouté (le crate hérite de `#![forbid(unsafe_code)]`
   comme `ge-core`).
4. `cargo clippy -p ge-substrate -- -D warnings` → 0 warning.

**Échéance révision** : 2026-06-15. Si à cette date aucun port GPU
n'a été tenté, ré-évaluer la pertinence de garder la version CPU
comme oracle ou la simplifier en seuls tests d'invariants.
