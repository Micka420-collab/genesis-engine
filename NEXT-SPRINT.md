# Genesis Engine — Next Sprint Queue
**Dernière mise à jour :** 14 mai 2026 (session 14 — Wave 3 physiologie ultra-réaliste).

---

## ✅ Livré session 14 (2026-05-14) — Wave 3 physiologie ultra-réaliste

Nouveau module `engine/physiology.py` (~520 LOC) qui empile sur les
drives Phase-4 une physiologie humaine fidèle :

- **Excrétion** : `bladder` (4 h fill), `bowel` (14 h fill). Relief
  autonome dès urge ; **contamination de l'eau** (cholera shedding)
  si relief près d'un point d'eau.
- **Hygiène** : `hygiene` scalar, décay 5 jours, restauré par bain
  sur cellule water > 50 L. Sweat + parasites accélèrent le décay.
- **Maladies de peau** : `sunburn`, `frostbite`, `parasites` (lice),
  `dermatitis`. Pilotées par melanin × thermal × body_fat × hygiene.
- **Pathogènes contagieux** :
  - `cholera` (water-borne, ingéré via DRINK sur eau contaminée)
  - `flu` (airborne, transmission via spatial grid rayon 2 m)
  - `wound_infection` (entrée par injuries × dirty environment)
  - Croissance **logistique** `r·load·(1-load)`, clearance par
    immunité. Mémoire immunitaire post-infection.
- **Génome → traits** : melanin (loci 120-127), body_fat (128-135),
  immune_baseline (136-143) lus à l'install.

**Émergence observée** sur smoke 800 ticks Léman : **10/12 agents
survivants attrapent le choléra** par auto-contamination de leur eau
de boisson — le mécanisme historique du XIXe siècle reproduit sans
le programmer.

**Hookage** : `engine.cognition.apply_decision` wrappé **une fois par
processus** avec dispatch `id(agents)→(sim, fields)` (permet plusieurs
sims simultanés).

**Déterminisme** : SHA hash physio bit-identique entre 2 sims même seed
même processus (`27dff46e878183dc1aad3f92`). Tous les RNG via `prf_rng`.

**ADR-0005** : `engine.physiology` ajouté à `_REQUIRED_MODULES`, linter
CI passe 4/4.

**Endpoint** : `GET /api/physiology_state` + 2 lignes HUD dans
`#observatory-panel` (💧bld 💩bwl 🧼hyg ☀️sun ❄️frz 🐛par 🩹der + 🦠
cho/flu/wnd).

Voir `docs/sprints/2026-05-14_PHASE10-PHYSIOLOGY.md`.

### Wave 4 (R&D future)
Wounds localisées (jambe/bras), grossesse+lactation, remèdes culturels
(invention.py × MaterialRegistry = pharmacopée), mémoire trauma
adaptative (éviter chunks contaminés).

---

---

## ✅ Livré session 13 (2026-05-14) — FUTURE-VISION Wave 2

Pilier 2 ("Invention émergente de matériaux") élargi : alliages
ternaires + **dopage non-linéaire** + registre par culture +
transmission de recettes.

**Mécanisme neuf** : `_detect_doping(composition)` identifie un pattern
host (≥80 %) + dopants (<10 %). `_doping_hardness_boost` ajoute un
delta non-linéaire en Mohs (6× pour interstitiels C/N/B/H, 2× pour
substitutionnels, saturation sqrt à ~5 %, cap +5 Mohs).

**Effet** : Fe pur 1.79 Mohs → acier (Fe + 1.5 % C + 1.5 % Mn) **6.17
Mohs** (+4.4 du dopage). Bronze Cu70Sn30 (binaire) reste sous la règle
linéaire Wave 1 (1.79 Mohs), phosphor bronze Cu94Sn5P1 (host+dopants)
gagne +2.89 Mohs. Le pattern discrimine correctement solution solide
vs dopage interstitiel.

`scripts/p19_wave2_integration.py` (6/6 PASS) valide ternaire +
dopage + isolation per-culture + transmission de recettes. Wave 1
(`p15`, `p17`) sans régression.

Voir `docs/sprints/2026-05-14_PHASE9-WAVE2.md`.

### Wave 3 (R&D future)
Composites bois-céramique, matrices fibre-renforcée, chimie hors
lithosphère (atmosphères CO2-rich, températures extrêmes). Cible :
permettre les matériaux que notre histoire a négligés.

---

---

## ✅ Livré session 12 (2026-05-14) — P-NEW.21 path (b) mask cache + flag cache

`_scan_chunk` descend de **54 µs → 40 µs per-call** (−26 %). Total 300
ticks à pop=175 : **63.1 s** (vs 69.3 s post optim #3b, −9 %). Vs
baseline pré-optim 72.0 s : **−12.4 %**. Cible <60 s manquée de 3.1 s
mais on touche le plancher numpy pratique.

**Mécanisme** : cache de 3 masques bool par chunk (`water > 5`,
`food > 5`, `shelter`) + 3 flags `has_*` (bool Python cachés), avec
invalidation explicite via `invalidate_resource_masks(chunk)` aux 10
sites de mutation (DRINK/FORAGE, regen, sim_lift veg/erosion,
sim_5cd wood/stone harvest, ecology flood, realism river inject).

**Déterminisme** : SHA-256 bit-identique avec la version pré-cache
(`5ea89da1466e4c318766e74e81a2ef2a`).

Voir `docs/sprints/2026-05-14_PHASE8-MASK-CACHE.md`.

### ~~P-NEW.21 path (b) ✅~~ Mask cache + flag cache — livré.

### P-NEW.21 path (a) (toujours actif) — Batch perceive
Partager `d2` entre les agents d'un même chunk pour gagner ~5s
supplémentaires. Plancher restant à briser pour <60s.

### P-NEW.21 path (c) (R&D) — Réécriture cython/numba de `_scan_chunk`
Demande l'ajout d'une toolchain. Gain estimé −15s, mais coût build.

---

---

## ✅ Livré session 11 (2026-05-14) — P-NEW.17 re-profile + optim #3b

Première mesure après optim #3 : **114.3 s** — régression de +59 % vs
baseline 72.0 s. Diagnostic : la version sparse (`np.nonzero` + fancy
indexing) cumule (a) 3× nonzero par cache-miss, (b) fancy indexing
alloué par ressource, (c) `d2` recalculé 3 fois par chunk.

**Correctif (optim #3b)** : `_scan_chunk` réécrit en chemin dense
bool-mask avec `d2` partagé entre les 3 ressources. `_chunk_resource_indices`
supprimé. Argument `tick=` conservé pour la compat mais ignoré.

Re-profile : **69.3 s**. Gain net −2.7 s (−3.8 %) vs baseline. Cible
<60 s manquée de 9.3 s — `_scan_chunk` reste 44 % du frame, plus de
sub-optim possible sans changement de structure → escalade en P-NEW.21.

**Déterminisme préservé** : SHA-256 bit-identique sur 2 runs même seed.

Voir `docs/sprints/2026-05-14_PHASE7-PROFILE-OPTIM3b.md`.

### ~~P-NEW.17 ✅~~ Re-profile post optim #3 — livré (avec correctif optim #3b inclus).

### P-NEW.21 (nouveau) — Descendre `_scan_chunk` sous 30 µs/call
Pistes ordonnées :
- (a) batch `perceive()` pour les agents partageant un chunk →
  partager `d2` sur tout le batch. Gain estimé 2× sur les chunks denses.
- (b) max-resource map par chunk → cull précoce avant `_chunk_cell_world_xy`.
- (c) ré-écriture cython/numba de `_scan_chunk`. Gain estimé 2-3× supp.

Objectif final : 300 ticks à pop=175 en <40 s.

---

Ce fichier est la **source de vérité** pour la prochaine session de travail
(planifiée ou manuelle). À chaque sprint, on prend la PREMIÈRE priorité
non terminée, on livre, on coche, on actualise.

---

## ✅ Livré session 10 (2026-05-14) — P-NEW.20 capabilities endpoint

ADR-0005 horizon 30j (cible 2026-06-13) **atteint en J0**.

- **`engine/world_model_capabilities.py`** — agrégateur introspectif des
  constantes `PIPELINE_LAYER` + `WORLD_MODEL_CAPABILITY` publiées par
  chaque module layer. Expose `world_model_capabilities()` (table
  API-ready) + `audit_modules(strict=False)` (hook CI).
- **`/api/world_model_capabilities`** dans `dashboard.py` — retourne la
  table en <5 ms (3 tagged, 2 missing R&D, 0 untagged, 0 invalid).
- **HUD widget** dans `god_view_v2.html` sous `#observatory-panel` —
  code couleur ●=tagged ○=R&D ✕=invalid, tooltip avec l'erreur.
- **`scripts/p18_capabilities_lint.py`** — linter CLI. Fail-cases
  vérifiés : tags absents → failure ; capability hors allow-list →
  failure. Flag `--strict` pour étendre aux modules R&D présents.
- **`.github/workflows/capabilities-lint.yml`** — workflow GitHub Actions
  trigger sur changement de `runtime/engine/*.py` ou ADR.

Voir `docs/sprints/2026-05-14_PHASE6-CAPABILITIES.md`.

### ~~P-NEW.20 ✅~~ Endpoint `/api/world_model_capabilities` — livré.

---

## ✅ Livré session 9 (2026-05-14) — FUTURE-VISION Wave 1 (5 agents parallèles)

Première vague de la vision long-terme (`FUTURE-VISION.md` Pilier 1 — *Bases
du monde réel*). 4 modules de connaissance livrés en parallèle + intégration
+ doc, exécution simultanée par 5 agents (B1–B5).

- **B1 — `engine/physics.py`** : constantes CODATA (`G_EARTH`, `R_GAS`,
  `SIGMA_SB`, …), mécanique (`weight`, `kinetic_energy`,
  `compute_acceleration`, `compute_terminal_velocity`,
  `compute_orbital_period`), friction tables (`MU_STATIC`, `MU_KINETIC`),
  thermodynamique (`gibbs_free_energy`, `is_thermodynamically_favorable`,
  `arrhenius_rate`, `heat_transfer_conduction`, `heat_transfer_radiation`).
  Pures fonctions, vectorisables numpy.
- **B2 — `engine/chemistry.py`** : `PERIODIC_TABLE` (50 éléments, IUPAC 2021
  + PubChem 2024) avec dataclass `Element`, `BOND_ENERGY` table (kJ/mol),
  helpers `bond_energy`, `electronegativity_difference`, `is_metal`,
  `density_alloy` (Wilke), `melting_point_estimate`, `molar_mass`.
  Zero dépendance hors stdlib.
- **B3 — `engine/material_synthesis.py`** : `SynthesisConditions`,
  `SynthesizedMaterial`, `synthesize(composition, conditions, tools_available)`
  + `check_physical_validity()` (Δ G, conservation, Ea atteignable).
- **B4 — `engine/statics.py`** : `Block`, `Structure`, `STRENGTH_TABLE`,
  `Structure.is_structurally_stable()` (compression, support area, moment).
- **B5 (cette tâche)** :
  - `runtime/scripts/p17_wave1_integration.py` — Bronze Age end-to-end
    (gibbs → Cu/Sn alliage → synthesize bronze → mur 5×2 stable).
  - `engine/__init__.py` — `__all__` pour discoverability Wave 1.
  - `WAVE1-KNOWLEDGE-BASE.md` au root : pourquoi cette vague, table modules,
    exemple copy-paste, limites actuelles, prochaine vague.

**Prochaine étape** : Vague 2 — alliages ternaires + dopage + emergent
registry par culture + transmission de recettes stœchiométriques.

---

## ✅ Livré session 4 (2026-05-15) — Première civilisation multi-générations

- **P-NEW.4** : `_install_fertility_patch` seuils hunger/thirst 0.7→0.85.
- **Critical bug** : `apply_decision(MATE)` n'émettait pas `mate_attempt` event. Patch dans `patched_apply` → `_resolve_matings` reçoit enfin les intents.
- **P-NEW.7** : `_seed_initial_project` seed 1 HEARTH par culture (au lieu d'un seul global).
- **P-NEW.5** : `install_lift(sim)` branché dans `p4_leman.py` + `lift_state` dans summary.
- **P-NEW.6** : `/api/lift_state` endpoint + widget HUD dans `god_view_v2.html` (sous-agent).
- **Perf L2** : `tick_vegetation` throttled à 1/50 ticks + vectorisé via lookup tables → 30-50× plus rapide.
- **Counter fix** : `p4_leman.py` compte maintenant `births=`/`deaths=` (passaient hors raw_events).
- **`/api/demography`** : endpoint live de pyramide démographique (générations + cultures + top progéniteurs).
- **`scripts/analyse_lineage.py`** : CLI d'analyse de journaux .jsonl (top parents, timeline inventions, causes morts, distribution L1+L2).
- **Run 5K Léman complet (701s wall-clock)** :
  - 180 naissances / 179 morts / 21 vivants / 200 spawned
  - 95 323 vocalizations, 127 innovations, **10 artefacts inventés**, 2136 tech transmissions, 83 artefacts transmis
  - 24 groupes formés / 21 dissous
  - 1 HEARTH complété (premier bâtiment construit)
  - Top progéniteurs : 14, 13, 12, 10, 10, 10... enfants par fondateur

Journaux : `runtime/journals/{phase5a_leman,p5_lift_smoke}.jsonl`.

---

## ✅ Livré session 3 (2026-05-14)

- **P-NEW.2** : `earth_streamer.py` — EarthLoader branché sur ChunkStreamer + `attach_land_filter`. **504 hits / 0 misses sur Copernicus DEM + ESA WorldCover** via AWS Open Data /vsis3.
- **Auto-config GDAL** : `AWS_NO_SIGN_REQUEST=YES` au load — sans ça, les fetches publics échouent silencieusement.
- **rasterio + pyproj installés** sur Python 3.14 Windows (rasterio 1.5.0, pyproj 3.7.2).
- **P-NEW.1a** : spawn Léman corrigé (origin Lausanne 46.510N/6.633E + biome filter exclut OCEAN).
- **P-NEW.1b** : **run 5K ticks** — 20/20 alive, 24 898 vocalizations, 91 innovations, **3 artefacts inventés** (`clay_contain`, `stone_pierce`, `wood_clay_project`), 59 tech transmissions + 1 artefact transmis.
- **P-NEW.3** : `p4_leman_live.py` — dashboard live sur sim Léman, accès `http://localhost:8765/god_view_v2.html`.
- **Bug fix dashboard** : `/api/state` retournait body vide → `Annalist.wall_clock_s()` manquait. Fix + `_json_default` numpy-aware. Tous les endpoints OK.
- **P5 (L2)** : `sim_lift.py` — succession végétale Markov 5-états + érosion par foot traffic. Smoke 300 ticks PASSED — 500 chunks tracked, distribution réaliste (54% garrigue, 28% mature, 3% old growth).

Journaux : `runtime/journals/{phase5a_leman,p3_earth_smoke,p5_lift_smoke}.jsonl`.

---

## ✅ Livré session 2 (2026-05-13 PM)

- **P0** smoke pass (492 vocalizations, 7 innovations, 30/30 alive)
- **P0.1+P0.2** : sub-ticks `tick_speech` + `tick_material_forage` ajoutés à `sim_5cd_integration`. Bug import-binding sur `sim.apply_decision` corrigé.
- **Fix** : `_inventory_mass` manquant dans `cognition.py` (NameError sur FORAGE) — helper ajouté + 17 inventory fields tolérés.
- **P1** + **P2** + **P3** : terminés par sous-agents en parallèle (god avatar wiring, audio wiring, earth_loader offline smoke).
- **P4 Léman ✅** : premier vrai run sur 46.40°N/6.45°E, 2 km, 20 fondateurs, 1000 ticks. **4922 vocalizations**, **32 innovations**, **1 artefact inventé ("fiber_bind")**, matériaux ramassés organiquement (10.7 kg bois, 15.5 kg pierre, 19.4 kg argile, 5 kg silex, 7.8 kg fibre).

Journaux : `runtime/journals/{p0_smoke,p3_earth_smoke,phase5a_leman}.jsonl`.

---

## ✅ Livré session 7 (2026-05-14) — Architecture v1.0 conformity (5 agents parallèles)

Sprint où **5 agents en parallèle** ont corrigé les gaps majeurs entre l'implémentation et `Genesis_Engine_Architecture_v1.0.docx`. Voir `SPRINT-architecture-fixes.md` pour détails.

- **A1 HUNT (§14)** : `ActionKind.HUNT` + perception game + handler 800 kcal/deer + wolf predation. 37 hunts en smoke, deer -36% reachable.
- **A2 Trails (§16)** : `LiftField.base_walkability` immutable + `tick_walkability_from_trails` boost +0.3 max. Cognition `WALK_TO` consomme walkability vivante.
- **A3 Time-warp (§25)** : `engine/timewarp.py` + 5 modes (realtime/x10/x100/x1000/milestone) + `POST /api/timewarp`. **x10 = 38× speedup, x100 = 84×**, déterminisme préservé.
- **A4 Genome (§11+§12)** : `engine/genome.py` — 256-d genome, 4 groupes × 64 gènes, crossover + mutation 1e-4 + **8 LifeStage** (INFANT→ANCIENT) avec cognitive efficiency table. Hook dans `_resolve_matings`.
- **A5 Observatory (§23)** : `#observatory-panel` HUD top-left, poll 4 endpoints en parallèle, 7 sections (header/time/climate/wildlife/population/generations/top progenitors).

**Conformity matrix** : §11/12/13/14/16/23/25 désormais ✅. Reste : §15 (économie référence-good), §18 (langage compositionnel avancé), §19 (régimes politiques).

---

## ✅ Livré session 6 (2026-05-14) — World Creation Software v1

**Transformation** : Genesis Engine passe de "simulateur Léman" à **vrai logiciel de création de monde** générique. Voir `WORLD-CREATION-SOFTWARE.md` pour l'architecture détaillée.

- **`engine/world_builder.py`** — `WorldBuilder` fluide. Ergonomic API : `WorldBuilder(name).anchor(lat,lon).size_km(km).founders(n).build()`. Compose L1+L2+5cd en un seul appel. Réutilisable n'importe où sur Terre.
- **`engine/world_export.py`** — Exports vers formats standards :
  - GeoTIFF (12 layers : height, biome, slope, water, wood, walkability, is_lake...) via rasterio → GIS-compatible.
  - PNG cartographique avec palette biome + ombrage altitude + overlay lac/walkability.
  - JSON snapshot complet (agents + summary + chunks optionnel).
  - OBJ heightfield mesh → Blender / Three.js / Unity.
- **`engine/world_library.py`** — Persistance : `save_world(world, name)`, `load_world(name)`, `branch_world(src, dst)`, `list_worlds()`, `delete_world(name)`. Library racine via env `GENESIS_LIBRARY_ROOT` (défaut `<project>/worlds/`).
- **`scripts/multi_region_demo.py`** — 4 régions construites en parallèle (Lausanne / Sahara / Amazon / Reykjavík), 400 ticks chacune, **20 fichiers GIS générés** (PNG + 3 GeoTIFF + JSON par région), 4 entrées library. 100% L1 hit ratio sur tous les continents.

**Cron `1f80a1f5` annulé.**

---

## ✅ Livré session 5 (2026-05-16) — Cognition perf #3

- **Optim #3** : `r_chunks` resserré (49→25 chunks dans la fenêtre `chunks_around`) + cache d'indices clairsemés `_chunk_resource_indices` par (chunk, tick) attaché à l'instance de `Chunk`. Sparse `np.nonzero` au lieu de bool-mask 4096-cells alloué à chaque appel.
- **Tick threadé** : `perceive(... tick=None)` ajouté ; `Simulation.step` passe `tick=self.tick`.
- **Détermisme bit-perfect** vérifié (SHA-256 sur alive+pos+hunger+thirst, A==B sur 2 runs même seed).
- **Smoke 100 ticks** OK (30 agents, 0.5km², 144 ms/tick, alive=30/30).
- Fichiers : `engine/cognition.py` (re-écrit compact), `engine/sim.py` (perceive call).

Voir `SPRINT-2026-05-16.md`.

---

## Priorités actives (ordonnées) pour la prochaine session

### P-NEW.17 (nouveau) — Re-measure profile_tick.py à pop=175
Re-run `scripts/profile_tick.py` (warm-up 800 + profile 300 ticks) après l'optim #3. Baseline post optim #2 : 72.0 s. Attente : <60 s (~200 ms/tick à pop=175). Si confirmé, retirer `cognition.perceive` du top 5 du profile.

### P-NEW.18 (nouveau) — Cache invalidation explicite sur chunk writes
Le cache `_scan_idx` est strictement per-tick. Ajouter `chunk._gen` (compteur incrémenté par DRINK/FORAGE/build/lift) à la clé du cache pour autoriser des mises à jour mid-tick. Bénéfice si l'on monte le agent_step à sub-tick.

### ~~P-NEW.10 ✅~~ Death cause tracking — fix dans analyse_lineage (cause était dans metadata.cause). 100% EXHAUSTION confirmé, mean lifespan 900 ticks.

### ~~P-NEW.11 ✅~~ Profile perf — fait, `scripts/profile_tick.py`. Bottleneck = `cognition._scan_chunk` (61% du frame).

### ~~P-NEW.13 ✅~~ HUD demography widget — livré par sous-agent.

### ~~P-NEW.15+16 ✅~~ max_agents 200→1000 + SLEEP_RELIEF 0.40→0.60 + FATIGUE_PER_S halved
Run 2K validé : 980 births (vs 180 en 5K), 23 générations (vs 13), 1384 artefact transmissions (vs 83). Civilisation multi-générations stable.

### ~~Optim #2/#3/#4/#5/#6 ✅~~ Worldgen + perf
- Optim #2 : bbox prefilter `cognition.perceive` → 295ms→240ms (-19% cumul).
- Optim #3 : `classify_biome` vectorisé → 4096-loop éliminée au bootstrap.
- Worldgen #4 : `slope_deg` depuis gradient DEM → falaises 84.56° détectées.
- Worldgen #5 : `is_lake` distingue Léman (12.91% cellules) vs océan.
- Worldgen #6 : `walkability` composite (slope+ravine+ocean) → 14.8% impassable.

### Optimisation perf #2 — Réduire `cognition._scan_chunk` (61% frame)
Solutions candidates : (a) cap r_chunks à 2 (49→25 chunks/agent, gain 2×), (b) cache `chunk.water>5` mask, (c) skip chunks dont centre > radius+CHUNK_SIDE de l'agent. Cible : passer de 269ms/tick à <150ms/tick à pop=175.

### P-NEW.12 — Pourquoi un seul HEARTH complété sur 2 ?
Deux hearths seedés (1 par culture), mais le second reste `active_projects: 1` après 5K. Hypothèse : la culture 2 est plus dispersée et les builders ne convergent jamais. Investiguer : ajouter logging du `labor_committed` par projet.

### P-NEW.15 — `max_agents` 200 → 1000+
180 naissances bouchées dès tick ~500 (cap atteint). Pour vraie démographie multi-générationnelle, scaler à 1000+. Tester impact perf (probablement 5× plus lent par tick).

### P-NEW.16 — Équilibre fatigue/sleep (100% morts par EXHAUSTION)
Tous les agents meurent par épuisement (fatigue+sleep saturés). Pas une seule mort par soif/faim/froid/vieillesse. Tuning candidat : SLEEP_RELIEF +50%, ou abaisser FATIGUE_PER_S, ou allonger lifespan_ticks. Cible : distribution diversifiée des causes (au moins 3 catégories visibles).

### P6 — Module L3 `ai_detail.py` (NCA inférence-CPU)
Référence : `PHASE5G-HYBRID-WORLDGEN.md` section L3. Module Neural Cellular Automaton léger (50-200k paramètres). Inférence CPU. Output structuré (densité d'arbres / type d'herbes). Phase R&D — premier objectif : entraînement offline reproductible.

### P-NEW.9 — Téléchargement local CHELSA bio1/bio12 + HydroSHEDS
Pour activer pleinement L1. Volume : ~3 GB CHELSA Europe, ~500 MB HydroSHEDS. Stamp le Rhône en eau réelle, climat précis vs. fallback latitude.

### P8 — Module L5 `world_model.py` (DreamerV3 par culture)
R&D. DreamerV3 entrainé sur l'état bas-dim de la sim, donne aux agents la capacité de "rêver" des trajectoires avant d'agir.

### P-NEW.14 — Cause-stratified death stats
Stats vitales : âge moyen au décès, taux mortalité infantile, taux mortalité par cause. Nécessite P-NEW.10 d'abord.

### ~~Priorités précédentes archivées~~

### P-NEW.4 — Fix fertilité (drives → 1ère naissance possible)
Sur 5K ticks Lausanne : 20/20 alive mais 0 mating_success. Cause : `_is_fertile` requiert hunger < 0.7 AND thirst < 0.7, mais avec `drive_accel=1500` la thirst dépasse 0.7 en ~120 ticks et ne redescend que si l'agent DRINK. Trop souvent les agents sont en MATE loop sans drink. Fix candidat A : relâcher le gate à 0.85 (au seuil critique seulement). Fix B : forcer DRINK plus systématiquement quand l'eau est en perception. Pour valider : run 2K ticks avec fix, viser ≥ 1 mating_success + ≥ 1 birth. Délivrable : `scripts/p4_leman_birth_test.py` + `SPRINT-2026-05-15.md`.

### P-NEW.5 — Brancher L2 sim_lift dans p4_leman.py
Aujourd'hui sim_lift est testé via `p5_lift_smoke.py` mais pas activé dans le run principal. Ajouter `install_lift(sim)` après `install(sim)` dans `p4_leman.py` et `p4_leman_live.py`. Exposer `lift_state(sim)` dans le summary final. Effet attendu : forêts coupées par les agents repoussent dans le run long → premier feedback agents→monde→agents observable.

### P-NEW.6 — Dashboard endpoint `/api/lift_state`
Ajouter une route GET `/api/lift_state` qui retourne `lift_state(sim)` (déjà implémenté). Mettre à jour `god_view_v2.html` pour afficher un widget "succession végétation" (% par état) + sentinel ravine_depth max. Permet à l'observateur de voir la couche L2 en live.

### P-NEW.7 — Plusieurs hearths seeded au lieu d'un
Aujourd'hui `_seed_initial_project` ne place qu'un seul HEARTH. Sur Léman 5K, 0 build complet car les builders ne se concentrent jamais. Fix : seed N=cultures hearths (un par cluster culture-bearing) ou N=founders/5 hearths. Délivrable : ≥1 build complet en 5K ticks.

### P-NEW.8 — Run "10K + L1+L2 + multi-hearths + fertility-fix" sur Léman
Une fois P-NEW.4/5/7 livrés : lancer un vrai run 10K complet avec toutes les améliorations. Critères de succès : ≥3 builds complets, ≥1 birth, ≥3 lineages, succession végétation visible (>5% bois jeune apparu dans cellules forêt mature coupées).

### P6 — Module L3 ai_detail.py (NCA inférence-CPU)
Référence : `PHASE5G-HYBRID-WORLDGEN.md` section L3. Module Neural Cellular Automaton léger (50-200k paramètres) entraîné offline sur bruit conditionné par biome. Inférence CPU. Output structuré (densité d'arbres / type d'herbes) plutôt que pixels — sortie consumée par le dashboard pour rendu détaillé.

### P-NEW.9 — Téléchargement local CHELSA bio1/bio12 + HydroSHEDS
Pour activer pleinement L1 : télécharger les fichiers CHELSA (climatologie 1981-2010) et HydroSHEDS (rivers + lakes) localement, paramètres `chelsa_bio1_path` / `hydrosheds_rivers_path` dans `EarthLoaderConfig`. Améliore la précision climat (vs. fallback latitude) et stamp le Rhône en eau réelle. Volume : ~3 GB pour CHELSA Europe, ~500 MB HydroSHEDS.

### ~~P0/P1/P2/P3/P4/P-NEW.1/2/3~~ ✅ tous livrés (voir SPRINT-2026-05-13b.md + SPRINT-2026-05-14.md).

(Référence original ci-dessous, conservé pour mémoire :)
Modifier `runtime/engine/dashboard.py` ou écrire un wrapper qui appelle :
```python
from engine.god_avatar import GodObserver, GodInterventionLog
from engine.god_endpoints import register_god_endpoints
god, god_log = GodObserver(), GodInterventionLog()
register_god_endpoints(_Handler, god, god_log)
```
Tester `GET /api/god/state` puis `POST /api/god/teleport`, `POST /api/god/visibility`.

### P2 — Brancher Audio endpoints + overlay
Wirer `audio_endpoints.register_audio_endpoints()` dans dashboard.py. Référencer `audio_overlay.js` depuis `god_view.html` ou `god_view_v2.html`. Tester `GET /api/audio?listener_x=0&listener_y=0`.

### P3 — Smoke-test earth_loader (offline)
```python
from engine.earth_loader import EarthLoader
loader = EarthLoader(origin_lat=46.40, origin_lon=6.45, bounds_km=2.0, cache_dir="/tmp/earth")
data = loader.chunk_data((0, 0, 0))  # None acceptable si offline
```
Si None, le fallback procédural fonctionne. Si non-None, vérifier les shapes.

### P4 — Premier vrai run Earth-anchored
Lancer une sim de 20 fondateurs sur le Léman avec `world_loader=EarthLoader(46.40, 6.45, 2.0)`. Logger `phase5a_leman.jsonl`. Comparer la topologie avec une carte du Léman pour valider que les agents bougent sur de la vraie géo.

### P5 — Module L2 : `engine/sim_lift.py`
Érosion hydraulique live + succession végétale. Algos publics (drop simulation pour érosion ; modèle de Markov 5-états pour la végétation : prairie → garrigue → bois jeune → forêt mature → forêt vieille). Tick une fois par "jour-sim".

### P6 — Module L3 : `engine/ai_detail.py`
NCA léger (50–200k paramètres) entraîné offline sur du bruit conditionné par biome. Inférence CPU-only. Output structuré (densité d'arbres, type d'herbes) plutôt que pixels.

### P7 — Mode `--science-mode` global
Flag CLI qui désactive god avatar (lecture seule), gèle les modèles génératifs (déterminisme absolu), et émet un manifest de run pour reproductibilité scientifique.

### P8 — Module L5 : `engine/world_model.py`
DreamerV3 par culture (pas par agent — trop cher). Trained sur l'état bas-dim de la sim, donne aux agents la capacité de "rêver" des trajectoires avant d'agir. R&D — premier objectif est juste de l'entraîner, pas de l'intégrer.

### P9 — Phase 5b : LLM cognition tier-2
Brancher un petit LLM local (Phi-4-mini ou Llama-3.2-3B via vLLM) en mode PIANO pour les agents qui dépassent un seuil de saillance. Voir `PHASE5-RESEARCH-DOSSIER`.

---

## Tâches livrées (archive)

- Phase 1–4 : monde procédural, agents, perception, mémoire, drives, reproduction, lignée, groupes, proto-langage, compétition. Voir `PHASE4-PROGRESS-2026-05-13.md`.
- Phase 5a recherche + plan : `PHASE5-RESEARCH-DOSSIER-2026-05-13.md`, `PHASE5A-PLAN.md`.
- Phase 5c+5d fondations : modules `materials`, `construction`, `tech_tree`, `ecology`, `invention`, `values`, `agent_5cd_fields`. Voir `PHASE5CD-STATUS-2026-05-13.md`.
- Phase 5e plan : `PHASE5EF-PLAN.md`, `PHASE5G-HYBRID-WORLDGEN.md`.
- Phase 5g audio : `communication.py`, `knowledge_artifacts.py`.
- Fleet livré 13 mai (5 modules supplémentaires en parallèle) : `earth_loader`, `god_avatar` + `god_endpoints`, `sim_5cd_integration`, `god_view_v2.html`, `audio_endpoints` + `audio_overlay.js`.
- God view interactive : `dashboard.py` patché, `god_view.html`, `scripts/run_god_view.py`.

---

## Règles invariantes

1. **Pas de rewrite** de fichiers existants — préférer extension modulaire (le mount tronque parfois les Edit/Write).
2. **Préserver le déterminisme** via `engine.core.prf_rng`. Pas de `random.random()`.
3. **CO2 baseline 280 ppm** pré-industriel. Toute émission doit passer par `ecology.atmosphere.emit()`.
4. **Un sprint = un livrable concret + test**. Ne pas escalader le scope mid-sprint.
5. **Journaliser** chaque session dans `SPRINT-<YYYY-MM-DD>.md` au root du projet.

---

## Prompt prêt-à-coller pour `create_scheduled_task`

Si tu veux automatiser, crée une tâche hebdomadaire avec :

- **taskId** : `genesis-engine-weekly-progress`
- **cronExpression** : `0 9 * * 1` (chaque lundi 9 h)
- **description** : `Weekly progress sprint on Genesis Engine — pick one priority and ship tangible code.`
- **prompt** : voir le bloc ci-dessous

```
Genesis Engine — sprint hebdomadaire automatique.

Lis F:\DEvOps\projet alpha\genesis-engine\NEXT-SPRINT.md pour la file de
priorités actuelle. Prends la PREMIÈRE non terminée. Ne traite qu'elle.

Méthodologie :
- Pour un bug : reproduire, isoler, corriger, re-tester.
- Pour du nouveau code : écrire le module + test, sync vers le workspace
  via bash si l'écriture passe par un overlay.

Livrable obligatoire : F:\DEvOps\projet alpha\genesis-engine\SPRINT-<date>.md
qui résume priorité attaquée, fichiers modifiés, tests passés/échoués,
état restant.

Contraintes :
- Pas de rewrite, préférer extension modulaire.
- Déterminisme via engine.core.prf_rng.
- CO2 baseline 280 ppm.
- Une heure focalisée > cinq dispersées.
```

---

## Sessions de travail

| Date | Priorité attaquée | Livrable | Fichier sprint |
|------|-------------------|----------|----------------|
| 2026-05-13 | Phase 4 audit + Phase 5 recherche + Phase 5c+5d+5e+5g foundations + fleet parallel | 16 modules, 6 docs de plan, 5 modules fleet | (cette session) |
| 2026-05-13 (PM) | P0 — Smoke 5c+5d | 200 ticks ok, 7 innovations, 1 projet, journal écrit | SPRINT-2026-05-13.md |
| 2026-05-13 (PM2) | P1 — God Avatar wiring | 11/11 checks, 3 endpoints OK, fall-through OK | SPRINT-2026-05-13.md |
