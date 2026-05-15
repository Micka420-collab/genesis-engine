# WORLD_VEILLE_REPORT — 2026-05-15

**Cron task**: `genesis-engine--world-realism-system-v20`
**Mode**: autonome, veille-first.
**Couche ciblée**: **Substrate physique** — érosion hydraulique, infiltration sol, météo neuronale, fire spread Rothermel.
**Durée recherche**: 5 requêtes parallèles + lecture de papers/repos.

---

## Contexte de cette veille

La veille d'hier (`2026-05-14_WORLD-VEILLE-REPORT.md`) a posé la
fondation : ADR-0006 + nouveau crate `ge-substrate` avec types
voxel `#[repr(C)]` et un pas Saint-Venant CPU bit-exact (6 tests
verts, conservation de masse < 1e-3).

Aujourd'hui on **étend le substrat** vers les systèmes B (érosion)
et A.2 (infiltration sol), qui dépendent tous deux du pas Saint-Venant
opérationnel. Pas de touche aux composants Python (déjà mûrs : Wave 10
géologie 36 minéraux, Wave 10c métallurgie complète).

---

## decouvertes

### D7 — InfiniteDiffusion (arXiv 2512.08309)

- **techno**: Premier diffusion model pratique pour génération de
  terrain en streaming planète-entière temps réel sur GPU consumer.
  Stack hiérarchique : continental → mountains → local relief.
  Encoding d'altitude novateur, stable sur toute la dynamique
  terrestre.
- **source**: https://arxiv.org/abs/2512.08309 (HTML : 2512.08309)
- **telecharge**: non (poids ML, infra GPU non disponible côté Genesis).
- **applicable_a**: **SYSTÈME G — World models** (NIVEAU 2/3, mêmes
  contraintes que D1 Cosmos et D2 GenCast).
- **gain_estime**: génération initiale de terrain géologiquement
  plausible sans simulation tectonique complète. Complémentaire à
  GenCast (météo) et Cosmos (multi-modalité).
- **action**: **BACKLOG_ROADMAP** (sprint dédié "neural-worldgen").
- **raison_si_rejet**: cycle d'intégration ML 5×-10× plus long que
  l'ajout d'un module d'érosion CPU.

### D8 — Efficient Debris-flow Simulation (TOG 2024, DOI 10.1145/3658213)

- **techno**: Nouvelle formulation mathématique pour l'érosion par
  coulées de débris dérivée de la géomorphologie, **unified GPU
  algorithm** pour érosion + déposition. Capture les interactions
  entre debris flow et érosion fluviale.
- **source**: https://dl.acm.org/doi/10.1145/3658213
- **telecharge**: lecture des concepts (sans accès institutionnel
  au PDF) — l'algorithme général est documenté dans les sources
  ouvertes (résumé + figures de la page produit).
- **applicable_a**: **SYSTÈME B — Érosion hydraulique** : extension
  du modèle Theobald avec une seconde phase pour les coulées de
  débris (montagnes raides, post-séisme, post-glissement de terrain).
- **gain_estime**: cônes de déjection émergents en pied de montagne,
  glissements de terrain réalistes après pluies torrentielles.
- **action**: **COMBO_RETENU** (mais en version simplifiée — phase 1 :
  érosion fluviale Theobald, phase 2 : debris flow comme extension
  future). Le sprint d'aujourd'hui implémente la phase 1 + un hook
  d'extension `apply_debris_flow_step`.

### D9 — fast-noise-lite-rs / noise-functions SIMD

- **techno**: `fast-noise-lite-rs` (port Rust de FastNoise Lite C++)
  et `noise-functions` (impl SIMD Perlin/Cell/Value). Perfs typiques
  **8-20× plus rapides** que le `noise = "0.8"` actuellement déclaré
  dans `ge-world`.
- **source**:
  - https://github.com/engusmaze/fast-noise-lite-rs
  - https://lib.rs/crates/noise-functions
- **telecharge**: non aujourd'hui (la couche `ge-world` heightmap
  fonctionne, pas de besoin urgent).
- **applicable_a**: optimisation future de `ge-world::sampler` et
  des bruits stratigraphiques de la géologie procédurale 3D.
- **gain_estime**: -50% à -90% latence sur les bruits multi-octaves.
- **action**: **BACKLOG_ROADMAP** (à intégrer quand on chunkifie
  `ge-world` en 3D).

### D10 — Green-Ampt Modifié pour Profil de Mouillage Évolutif (2020)

- **techno**: Article Taylor & Francis (10.1080/02626667.2020.1790567)
  modifiant le modèle classique Green-Ampt pour mieux décrire le
  *front d'infiltration évolutif* dans les sols structurés.
- **source**: https://www.tandfonline.com/doi/full/10.1080/02626667.2020.1790567
- **telecharge**: lecture du résumé — modèle décrit mais paramètres
  hors scope pour Genesis (qui n'a pas de stratigraphie sol multi-couches
  à ce niveau de finesse).
- **applicable_a**: **SYSTÈME A.2 — Infiltration sol** : amorce, mais
  on reste sur la formulation Green-Ampt classique pour le sprint
  d'aujourd'hui (paramètres calibrables, déterminisme garanti).
- **gain_estime**: réalisme +5–10% sur sols argileux. Insuffisant pour
  justifier la complexité de l'implémentation modifiée maintenant.
- **action**: **COMBO_RETENU** (en version classique : 4 paramètres
  K_sat, suction head, porosity, initial moisture).

### D11 — bshishov/UnityTerrainErosionGPU (référence pédagogique)

- **techno**: Implémentation Unity HLSL de l'érosion hydraulique +
  thermique avec équations en eau peu profonde (shallow water). Très
  bien documenté, structure proche de Theobald.
- **source**: https://github.com/bshishov/UnityTerrainErosionGPU
- **telecharge**: lecture de la structure (4 passes : flux → vitesse
  → transport sédiment → érosion thermique). Référence d'algorithme,
  pas une dépendance.
- **applicable_a**: **SYSTÈME B — Érosion hydraulique** : structure
  des 4 passes adoptée pour le `ErosionGrid::step` ci-dessous.
- **gain_estime**: gagne ~6h de dev de re-derivation de l'algo
  par rapport à zero.
- **action**: **COMBO_RETENU** (algorithme reproduit, code adapté
  Rust + types voxel Genesis).

### D12 — Rothermel — pas d'implémentation Rust open-source trouvée

- **techno**: Modèle Rothermel fire spread — implémentations en R,
  JavaScript (emxsys/behave), Python. **Aucune crate Rust** trouvée.
- **source**: https://github.com/emxsys/behave (référence JavaScript)
- **telecharge**: non — on implémentera depuis les équations canoniques.
- **applicable_a**: **SYSTÈME E — Biologie & écosystème** (propagation
  du feu). Hors scope sprint actuel ; documenté ici pour roadmap.
- **action**: **BACKLOG_ROADMAP** (sprint dédié "fire-spread", après
  l'érosion sol-eau opérationnelle qui le conditionne — un feu modifie
  l'hydrologie, l'érosion et la composition organique du sol).

---

## cve_stack

aucune CVE critique sur le stack Rust actuel (rust-toolchain 1.84.0,
serde 1, rkyv 0.8, glam 0.29) aux dépôts publics consultés.

---

## paper_du_jour

- **titre**: "Efficient Debris-flow Simulation for Steep Terrain
  Erosion" (TOG 2024 / DOI 10.1145/3658213)
- **url**: https://dl.acm.org/doi/10.1145/3658213
- **technique**: formulation unifiée debris-flow + fluvial erosion,
  exécution GPU monolithe.
- **effort**: ~4–6 heures pour la phase fluvial (aujourd'hui) ;
  +12 heures pour le debris flow proprement dit (sprint séparé).

---

## world_model_updates

- **cosmos**: aucune nouveauté depuis 2026-03-13 (Cosmos-Predict2.5).
- **genie3**: aucune nouveauté significative repérée.
- **gencast**: confirmé comme gold standard météo opérationnel 2026.
  Backlog (D2 d'hier toujours valide).
- **autre**: InfiniteDiffusion (D7) — première intégration possible
  d'un diffusion model planétaire en consumer GPU.

---

## combo_retenu

### Combo principal : Theobald + bshishov (D11) + extension hook debris-flow (D8)

- **techno**: érosion hydraulique 4-passes (flux Saint-Venant déjà
  fait → transport sédiment → érosion-déposition → érosion thermique
  voxel-aware). Hook prêt pour debris flow futur.
- **cible**: nouveau module `scaffolding/crates/ge-substrate/src/erosion.rs`.
- **gain**: terrain qui s'érode physiquement (vallées en V, méandres
  en chaîne avec assez de pas, dépôts en aval, érosion gel-dégel).
- **adr_requis**: non — extension purement additive du substrat
  défini par ADR-0006.

### Combo secondaire : Green-Ampt classique (D10)

- **techno**: infiltration 1D vers le voxel `SoilHydro`. 4 paramètres :
  K_sat, suction head ψ, porosity φ, initial moisture θ_i.
- **cible**: nouveau module `scaffolding/crates/ge-substrate/src/soil.rs`.
- **gain**: nappe phréatique alimentée par l'eau de surface, qui à son
  tour module la végétation (Liebig) et le risque de feu.
- **adr_requis**: non — extension du substrat.
