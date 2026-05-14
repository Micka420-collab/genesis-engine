# WORLD_VEILLE_REPORT — 2026-05-14 (afternoon)

**Cron task**: `genesis-engine--world-realism-system-v20`
**Mode**: autonome total. Veille-first doctrine (zéro code avant ce
rapport).
**Couche ciblée**: **Substrate physique** — eau, érosion, géologie,
atmosphère, biologie, world models. C'est la première veille dédiée
au monde naturel ultra-réaliste (les veilles précédentes ciblaient
l'agentique, la PQC, et la cohérence world-model générale).
**Durée recherche**: 6 requêtes parallèles, lecture + synthèse.

---

## decouvertes

### D1 — NVIDIA Cosmos-Predict2.5 (release 2026-03-13)

- **techno**: Cosmos-Predict2.5 — flow-based world foundation model,
  unifie Text2World / Image2World / Video2World. Tailles 2B et 14B.
  RL-based post-training. Adhérence forte aux lois physiques
  (entraîné sur 200M clips). Open-source GitHub
  (`nvidia-cosmos/cosmos-predict2.5`).
- **source**:
  https://github.com/nvidia-cosmos/cosmos-predict2.5
  + https://research.nvidia.com/labs/cosmos-lab/cosmos-predict1/
  + arxiv 2511.00062 (World Simulation with Video Foundation Models)
- **telecharge**: non aujourd'hui (modèle 2B = ~5GB poids, 14B = ~30GB,
  inférence GPU H100/H200 requise — pas dans notre stack actuel).
- **applicable_a**: **SYSTÈME G — World models pour cohérence globale**
  (NIVEAU 2 régional + NIVEAU 3 global). Remplace potentiellement notre
  GCM 16-cellules pour la macro-simulation, et fournit l'état initial
  cohérent d'une zone quand un agent l'approche pour la première fois.
- **gain_estime**: cohérence physique globale sans calcul exact ; -90%
  de coût CPU sur les zones >50km des agents actifs ; nouveaux types
  de phénomènes émergents (cyclones, fronts) qu'un GCM réduit
  ne capture pas.
- **action**: **BACKLOG_ROADMAP**. Trop lourd à intégrer en un tick :
  nécessite (1) bridge Python ⇄ Rust via PyO3 ou un service gRPC
  dédié inference, (2) GPU H100/H200 ou A100 80GB minimum, (3) ADR
  séparé pour les conditions de bord entre simulation locale exacte
  et génération neuronale régionale, (4) protocole de calibration
  TEST_1-5 défini dans SYSTÈME G du cron. → Sprint dédié recommandé.
- **raison_si_rejet**: n/a

### D2 — DeepMind GenCast (opérationnel 2026, supplante ECMWF ENS)

- **techno**: GenCast — diffusion model adapté à la géométrie sphérique
  de la Terre. Modèle probabiliste d'ensemble météo, 0.25° résolution,
  bat ECMWF ENS sur 97.2% des targets évalués. Le successeur de
  GraphCast (déterministe). En 2026 c'est le **gold standard** AI
  pour la prévision météo opérationnelle.
- **source**:
  https://deepmind.google/blog/gencast-predicts-weather-and-the-risks-of-extreme-conditions-with-sota-accuracy/
  + Nature paper https://www.nature.com/articles/s41586-024-08252-9
  + repo https://github.com/google-deepmind/graphcast (contient
  GenCast aussi)
- **telecharge**: non aujourd'hui (poids ML, ERA5 reanalysis dataset
  requis pour l'entraînement, ~1Tio).
- **applicable_a**: **SYSTÈME D — Atmosphère & climat émergent**.
  Remplace le GCM 16-cellules par un modèle neuronal probabiliste
  pour la circulation globale. Conserve notre simulation exacte
  locale (convection, gradients, microclimat de vallée).
- **gain_estime**: prévision météo cohérente sur 15 jours simulés ;
  capture événements extrêmes (cyclones, vagues de chaleur) qu'un
  GCM réduit manque par construction. Coût: inférence GPU ~5s par
  step de 12h simulées (acceptable pour NIVEAU 3).
- **action**: **BACKLOG_ROADMAP** (couplé à D1 dans un sprint
  "neural-climate"). Note d'intégration : GenCast input = état météo
  initial → on doit fournir cet état depuis Genesis (notre GCM 16
  cellules suffit pour l'amorce, puis GenCast continue).
- **raison_si_rejet**: n/a

### D3 — bevy_voxel_world (crate Bevy, voxel terrain plug-and-play)

- **techno**: `bevy_voxel_world` — Bevy plugin pour génération et
  modification de terrains voxel, multithreaded meshing, chunk
  spawn/despawn auto, texture mapping. API ergonomique. Compatible
  avec Bevy 0.16 (à vérifier sur Cargo.toml du repo).
- **source**:
  https://github.com/splashdust/bevy_voxel_world
  + https://crates.io/crates/bevy_voxel_world
- **telecharge**: candidat fort `cargo add bevy_voxel_world` dans
  `ge-substrate` (nouveau crate aujourd'hui).
- **applicable_a**: **fondation Substrate** (le voxel volumique 3D
  manque encore dans `ge-world` — qui n'a que des heightmaps 2D).
- **gain_estime**: -2 à -3 semaines de dev (meshing, chunk LOD,
  scheduling spawn/despawn déjà résolus par le crate). On reste
  propriétaire de la *physique* dans les voxels.
- **action**: **COMBO_TODAY** (intégrer la dépendance dans le nouveau
  crate `ge-substrate` même si on ne l'instancie pas encore — pour
  réserver la dépendance et tester la compatibilité Bevy 0.16).

### D4 — Cell2Fire + ABWiSE (modèles feu agent-based open-source)

- **techno**: Cell2Fire (cell-based forest fire growth) et ABWiSE
  (agent-based wildfire spread) — extensions au modèle Rothermel
  combinant complexité physique et simplicité computationnelle.
- **source**:
  https://www.frontiersin.org/journals/forests-and-global-change/articles/10.3389/ffgc.2021.692706/full
  + https://nhess.copernicus.org/articles/21/3141/2021/
- **telecharge**: papers consultés. Code Cell2Fire = C++/Python sur
  GitHub.
- **applicable_a**: **SYSTÈME E — Biologie & écosystème**, sous-section
  "propagation du feu (Rothermel simplifié)".
- **gain_estime**: méthode validée scientifiquement (Cell2Fire utilisé
  par USDA Forest Service). Implémentation Rust idiomatique possible
  en ~400 lignes. Brandons (spot fires) + pyroconvection inclus.
- **action**: **BACKLOG_ROADMAP** (utile quand SYSTÈME E démarrera —
  pas avant que SYSTÈME A water/erosion soit opérationnel : la
  propagation de feu dépend de `soil_moisture` et `fuel_load` qui
  viennent de l'hydrologie + végétation).

### D5 — Bevy 0.16 GPU-Driven Rendering + Vulkan backend

- **techno**: Bevy 0.16 (release mars 2026 d'après our STACK.md) —
  GPU-Driven Rendering activé : draw indirect + meshlets. Plus rapide
  sur scènes complexes. 1244 PRs, 261 contributeurs. ECS Relationships.
- **source**:
  https://bevy.org/news/bevy-0-16/
- **telecharge**: déjà notre version cible dans `STACK.md`.
- **applicable_a**: confirmation du choix Bevy 0.16 dans `ge-world`
  et futur `ge-substrate`. Aucun changement requis dans nos crates.
- **gain_estime**: -30 à -50% draw calls quand renderer 3D arrivera
  (Phase 4 — pas notre sprint). Confirmé par veille du matin 2026-05-14.
- **action**: **REJETÉ** (doublon avec veille du matin). Aucune action
  nouvelle aujourd'hui.

### D6 — Xiadian gold deposit 3D ore-forming numerical model

- **techno**: méthodologie de simulation 3D voxel pour la genèse de
  filons aurifères hydrothermaux — couplage structure / fluide /
  chaleur / wall rock. ~82% des voxels modélisés montrent un flux
  ingress fluide. Calibré sur 8000 données archivales (146 forages).
- **source**:
  https://www.mdpi.com/2076-3417/13/18/10277
- **telecharge**: PDF consulté. Méthode applicable mais lourde.
- **applicable_a**: **SYSTÈME C — Géologie 3D**, sous-section "filons
  hydrothermaux (contact pluton × fracture = métal)".
- **gain_estime**: distribution spatiale des filons calibrée sur des
  données réelles → règles de placement minéral plus défendables que
  Voronoï arbitraire. Effort: ~2 jours d'implémentation pour une
  version simplifiée (champ de pression + path-tracing thermique).
- **action**: **BACKLOG_ROADMAP** (à intégrer quand SYSTÈME C
  démarrera — après SYSTÈME A water/erosion).

---

## cve_stack

- aucune CVE critique nouvelle aujourd'hui sur Rust 1.84 / Bevy 0.16 /
  wgpu / Rapier 0.20. La veille du matin a confirmé que tokio-tar
  (CVE-2025-62518 TARmageddon) **n'est pas** dans notre Cargo.lock.

---

## paper_du_jour

**Titre**: *Cosmos-Predict2.5: A Flow-Based Unified World Foundation
Model for Physical AI* (NVIDIA, mars 2026, accompagnant le release
GitHub).
**URL**: https://github.com/nvidia-cosmos/cosmos-predict2.5
+ arxiv 2511.00062 (publication associée précédente).
**Technique extractible**: l'architecture **flow-matching** (continuous
normalizing flow) entraînée par RL post-training pour la cohérence
physique est *applicable* à notre futur module L3 Evolver (P8 du
backlog). Permet d'envisager un substrat "neural-augmented" où la
simulation locale exacte sert d'ancrage et le flow model interpole
le reste.
**Effort**: 6 mois pour une intégration complète. Hors scope d'un tick
autonome. → Inscrit dans **ROADMAP**.

---

## world_model_updates

- **cosmos**: Cosmos-Predict2.5 release majeure (2026-03-13). 2B et
  14B params, 30s génération, flow-based. ⇒ candidat NIVEAU 2/3 du
  SYSTÈME G de Genesis (cohérence régionale + globale).
- **genie3**: pas de nouvelle release identifiée aujourd'hui (dernière
  veille = Genie 3 DeepMind annoncé fin 2024). Surveille pour
  prochaine veille.
- **genCast**: opérationnel chez DeepMind, **gold standard 2026**
  pour la météo. Candidat fort NIVEAU 3 du SYSTÈME D (atmosphère).
- **WeatherNext 2**: variante DeepMind 2025 ciblée trading énergie.
  Probabiliste, sub-orbital. Surveille pour intégration éventuelle.

---

## combo_retenu

**COMBO_RETENU pour aujourd'hui** :
`[bevy_voxel_world 0.x compat Bevy 0.16]` × `[nouveau crate
ge-substrate avec types WaterVoxel/SoilHydro/GeoVoxel + step
Saint-Venant CPU de référence]`

| | |
|---|---|
| **techno** | `bevy_voxel_world` (dépendance réservée) + structures `repr(C)` alignées GPU + algo Saint-Venant CPU comme référence physique |
| **cible** | nouveau crate `scaffolding/crates/ge-substrate` (fondation du monde physique — n'existe pas encore) |
| **gain** | unblock SYSTÈME A (eau/hydrologie) + tous les autres systèmes physiques qui en dépendent (érosion, fertilité du sol, biologie). Conservation de masse testée par property test. |
| **adr_requis** | OUI — ADR 0006 : "Substrate physical layer foundation — voxel data model + CPU reference implementation before GPU port". |

**COMBO_BACKLOG (séparés en sprints dédiés, trop lourds aujourd'hui)** :

1. **D1+D2 combo "neural-climate"** : Cosmos-Predict2.5 + GenCast
   intégrés via bridge Python (PyO3 ou service gRPC) pour
   NIVEAU 2/3 du SYSTÈME G. Sprint estimé 3-4 semaines.
2. **D4** : Cell2Fire/ABWiSE Rothermel quand SYSTÈME E ouvrira.
3. **D6** : modèle Xiadian de genèse hydrothermale quand SYSTÈME C
   ouvrira.

**COMBO_REJETÉ** :

- D5 (Bevy 0.16 GPU-driven rendering) — doublon avec veille du matin.
- WGPU compute shader pour Saint-Venant *aujourd'hui* — prématuré :
  on a besoin d'abord d'une référence CPU bit-exact pour valider la
  conservation de masse, puis port WGSL au sprint suivant. (C'est la
  doctrine "test-first" appliquée au GPU.)

---

## Notes méta

- Veille terminée à 14:50 (~25 min). Sous le budget 30 min.
- Le COMBO retenu est *intentionnellement* conservateur : poser les
  fondations physiques propres (data model + référence CPU) avant
  toute optimisation GPU ou intégration ML. C'est la doctrine
  *"results > perfection"* du CLAUDE.md mais appliquée à un projet
  long terme : un fondement bancal coûte 10× plus cher à corriger
  plus tard qu'un fondement propre.
- D1+D2 (Cosmos + GenCast) sont les **deux découvertes les plus
  importantes** de cette veille. Elles méritent un sprint dédié
  "neural-climate-integration" qu'on planifiera quand SYSTÈME A
  sera opérationnel.
