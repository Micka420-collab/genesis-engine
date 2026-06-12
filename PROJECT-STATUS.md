# Genesis Engine — État du projet

**Dernière mise à jour :** 10 juin 2026 (Wave 63 — concavité de chenal / χ-steepness : **loi de Flint** pente–aire `S = k_s·A^−θ` (régression log-log → concavité θ = m/n + raideur k_s) + **méthode χ intégrale** de Perron & Royden 2013 sur le réseau D8 émergent (`flow_dir` + `flow_acc` + `elevation_m`) ; invariant pivot **récupération exacte de la loi de puissance** (θ, k_s à <1e-9, R²=1) + linéarité χ–z (ksn, R²=1) + invariance d'échelle de θ ; pur observateur read-only. Antérieur : Wave 62 hypsométrie / maturité de paysage Strahler 1952, identité de Pike-Wilson ; Wave 61 flexure lithosphérique élastique Vening-Meinesz)  
**Synthèse courte** pour contributeurs et reviewers GitHub. Pour le détail session par session, voir [`NEXT-SPRINT.md`](NEXT-SPRINT.md).

---

## En une phrase

**EMERGENCE SIM v2** — laboratoire ZERO PRE-SCRIPT : lois physiques L0–L4, agents autonomes, civilisation **non scriptée**, observable via Earth Console et métriques d'émergence.

**Tests :** `pytest runtime/tests` — **441** tests · smokes **p72–p135** (+ `p87` observer) dans `validate-all`.  

> **Session 2026-06-12 (suite) — 3ᵉ _capacité_ agent : potabilité de l'eau.** `engine.water_potability` (Cap. C3). La ressource **la plus fondamentale de toutes** — l'eau potable (on meurt de soif avant la faim, avant l'outil) — restait muette **d'une façon physiquement fausse** : `engine.physiology` (action `DRINK`) réduit la soif pour **n'importe quelle** cellule d'eau, **y compris l'eau de mer** → le monde laissait un agent « boire l'océan » et être hydraté. Ajout de la lecture de **salinité** par le goût (bandes WHO/EPA : douce < 0,5 ppt / saumâtre / mer 35 ppt / saumure), dérivée de **vérités indépendantes** : biome `OCEAN` (mer), **halite** peu profonde en `chunk_geology` (saumure — la *même* couche que la croûte de sel de C1), basse élévation (mélange estuarien côtier), sinon eau douce (dureté carbonatée). Invariant **« le monde ne ment jamais »** (potable ⇒ ≠ OCEAN & pas de saumure & ppt ≤ seuil ; mer ⇒ OCEAN ; saumure ⇒ halite) prouvé sur monde Genesis (seed `0xFACE`, 0 violation) + boucle **goûter douce → `drink_at` hydrate** / **océan injecté → perçu salé → n'hydrate pas** (aperçu non mutant, le mensonge rendu visible). **Émergence absolue** (on rend la salinité détectable, jamais « ne bois pas »). **Capacité, pas observateur** : aucun hook `sim.step`, coût tick nul → conforme au moratoire. **Perception-seule** : on n'altère pas `DRINK` (changement comportemental hors moratoire). 15 tests + smoke `p135` (7/7), ADR-0005 audité `ok`, pytest **441/441**. **Gap honnête :** la nappe phréatique (groundwater/Darcy) n'est pas modélisée (eau = champ de surface) ; ne ferme aucun item Rust Phase A/B. Détail : [`docs/sprints/2026-06-12_CAP-C3_water_potability.md`](docs/sprints/2026-06-12_CAP-C3_water_potability.md) · veille : [`docs/veille/2026-06-12_VEILLE_water_potability.md`](docs/veille/2026-06-12_VEILLE_water_potability.md).
>
> **Session 2026-06-12 — 2ᵉ _capacité_ agent (anti-treadmill) : pierre taillable.** `engine.lithic_outcrop` (Cap. C2). Pendant de C1, technologie **plus fondamentale encore** : la géologie portait la lithologie (`StrataLayer.rock_type`) et les silicates taillables (`obsidian`/`quartz` dans `ore_mix`) mais restait **muette** — aucun signal ne disait *où trouver une pierre qui fait des lames tranchantes*. Ajout de la lecture d'**affleurement** que tout tailleur paléolithique sait faire : classe de fracture (`CONCHOIDAL`/`TABULAR`/`GROUND`/`SOFT`), hiérarchie archéologique **obsidienne > silex(chert) > quartzite > basalte > granite**, silex modélisé comme `quartz` bonifié en hôte carbonaté, affleurement vs enfouissement (socle ≤ 6 m). Invariant **« le monde ne ment jamais »** (cue ⇒ pierre réelle dans la même colonne que `mine_at`) prouvé sur monde Genesis (seed `0xFACE`, 0 violation) + boucle **voir verre → débiter → obsidienne** end-to-end. **Émergence absolue** (on rend l'affleurement détectable, jamais « ceci taille bien »). **Capacité, pas observateur** : aucun hook `sim.step`, coût tick nul → conforme au moratoire. 15 tests + smoke `p134` (7/7), ADR-0005 lint vert, pytest **426/426**. **Gap honnête :** la provenance volcanique de l'obsidienne n'est pas verrouillée (à traiter côté `engine.geology`) ; ne ferme aucun item Rust Phase A/B. Détail : [`docs/sprints/2026-06-12_CAP-C2_lithic_outcrop.md`](docs/sprints/2026-06-12_CAP-C2_lithic_outcrop.md).
>
> **Session 2026-06-11 (suite) — 1ʳᵉ _capacité_ agent depuis 25 j (anti-treadmill, audit §D1/§3) :** `engine.surface_mineralization`. La géologie semait des minerais en profondeur mais le monde restait **muet** : aucun signal de surface ne permettait à un agent de *découvrir par la vue* un gisement (l'action `MINE` partait d'une profondeur par défaut, à l'aveugle). Ajout du **chapeau de fer / tache d'altération** des prospecteurs (gossan limonite-brun, malachite-vert cuivre, soufre-jaune, sel-blanc, placer-doré), **dérivé de la même colonne `chunk_geology` que `mine_at`** → invariant **« le monde ne ment jamais »** (cue ⇒ minerai peu profond réel) prouvé sur monde Genesis réel (seed `0xFACE`, 100 % chunks, 0 violation) ; boucle de découverte **voir vert → creuser → cuivre** vérifiée end-to-end. **Émergence absolue respectée** (on rend la couleur détectable, on ne dit jamais « c'est du cuivre »). **Capacité, pas observateur** : aucun hook `sim.step`, coût tick nul → conforme au moratoire. 15 tests + smoke `p133` (7/7), ADR-0005 lint strict vert. **NB honnêteté audit :** ne ferme **aucun** item Rust Phase A/B (A3/A4/A5/B1–B8 restent ouverts, `cargo` absent de l'env → CI = vérité) ; c'est une capacité du **runtime Python live**, distincte du backlog moteur Rust.
>
> **Session 2026-06-11 (antérieur) — rupture du « treadmill d'observateurs » (audit §D1) :** aucune Wave 64. (1) **Pont Python↔Rust réactivé** — le contrat trop strict (`is_canonical_pyworld` seul) rejetait silencieusement le wheel `ge-py` (surface *terrain*) vers `MockPyWorld` → backend natif inactif depuis Wave 42. Fix `rust_bridge.py` (`is_terrain_pyworld` / `is_native_pyworld`) **vérifié en live** : `bridge_status()` → `{native: True, backend: "terrain"}`. (2) **Garde D1** `engine/observer_budget.py` + `tests/test_observer_budget.py` (idempotence cross-observer prouvée, budget tick < 10 % instrumenté) + moratoire formalisé dans `CONTRIBUTING.md`. Diffs Rust moteur (`manager.rs` fix course mutation/éviction, `scenario` dép `worldgraph`, `-D warnings`) validés par inspection — **cargo absent de l'environnement**, CI = source de vérité.  
**CI :** le job Python exécute `make doctor`, `compile-python`, `test-python`, puis les smokes réalisme dans le **même ordre que `make validate-all`**, puis `p82_observation_sse_smoke.py` (observation SSE).

### Philosophie — émergence civilisationnelle

Les phénomènes (climat Köppen, hydrologie, épidémies, commerce, culture, observation) **émergent du cycle `Simulation.step()`** et des interactions agents ↔ monde — pas d’un orchestrateur de scripts qui enchaîne des étapes. Les smokes (`scripts/p*.py`) et `make smoke` **valident** le comportement ; le cœur exécutable est `python runtime/run.py` ou une boucle `sim.step()`.

**Manifeste (source de vérité) :** [`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md) · **Master prompt agents :** [`docs/MASTER-SCALE-PROMPT-v2.md`](docs/MASTER-SCALE-PROMPT-v2.md) · KPIs : `engine/emergence_metrics.py` · `/api/emergence_metrics`

**Presets :**
- **`python runtime/run.py realism`** — biosphère + knowledge layers + hydrologie sv1d + genesis + rust WorldGraph tick + 5cd (`engine/full_stack.py`).
- **`python runtime/run.py terre`** — fusion **origins** + **realism** (founders émergents, 2000 ticks par défaut).

---

## Avancement par phase (roadmap produit)

| Phase | Intitulé | Statut | Notes |
|-------|----------|--------|-------|
| **0** | Foundations (ECS, monorepo, observabilité) | ✅ | ADR-0005, PRF, CI (smokes alignés `validate-all`) |
| **1** | MVP Vie (cognition, mort biologique) | ✅ | Boucle perceive → decide → act |
| **2** | MVP Société (reproduction, mémoire, lexique) | ✅ | Multi-générations, vocalisations |
| **3** | MVP Civilisation (construction, troc, conflits) | 🟡 | Partiel ; Waves 28–32 enrichissent |
| **4** | Émergence civilisationnelle | ✅ | Agriculture, écriture, polity, métallurgie |
| **5** | Genesis-α public (long-run, LLM tier-2) | ⏳ | 9/10 prérequis livrés — **plan d'unlock Wave 12 figé le 2026-05-23** (cf. `../Genesis_Engine_2026-05-23_Phase5_Unlock_Brief.md`, GO/NO-GO J+10 = 2026-06-02) |
| **Waves 16–41** | Monde réaliste intégré au tick | ✅ | Genesis, climat, hydrologie, observateurs dans `sim.step()` |
| **Biosphère émergente** | Protocellules → sapients | ✅ | [`docs/BIOSPHERE-EMERGENCE.md`](docs/BIOSPHERE-EMERGENCE.md) · `run.py origins` |

Détail des **Waves 16–41** (genesis, tectonique, climat, NCA, settlements, routes, épidémie, iso, atmosphère…) : index dans [`docs/sprints/README.md`](docs/sprints/README.md) (fichiers `2026-05-18_WAVE*.md`).

---

## Réalisme Terre (grille scientifique)

**Score global : ~79,4 %** (moyenne 7 dimensions = (80+75+74+77+82+86+82)/7 = 79,4 % — Écologie/hydrologie 73→74 via **Cap. C3 potabilité de l'eau** : première _capacité_ de découverte d'**eau potable** émergente — la salinité (douce/saumâtre/mer) devient perceptible et véridique, comblant une muette physiquement fausse de `physiology.DRINK` ; antérieur 79,3 % Cap. C2 Sociétés 76→77 affleurements de pierre taillable ; 79,1 % Cap. C1 géologie 74→75 indices de surface minéralisée). **Objectif cible : 80 %**. _NB (audit §3) : ce score mesure le réalisme **observé** ; le sous-score « capacité moteur Rust » (A3/A4/A5/B1–B8) reste à **0/7** — non touché par cette capacité Python.

| Dimension | % | Piste principale |
|-----------|---|------------------|
| Climat / biomes | 80 | GraphCast-lite + colonne 3D + circulation L1 + vent 2D |
| Géologie / relief | 75 | Tectonique live, stratigraphie + datation relative + absolue (Wave 51) + cryoclastie (Wave 50) + compaction diagénétique (Wave 54) + géotherme/faciès métamorphiques (Wave 56) + lit mobile Exner (Wave 57) + isostasie d'Airy (Wave 59) + flexure lithosphérique élastique (Wave 61) + hypsométrie / maturité de paysage Strahler 1952 (Wave 62) + Wave 63 concavité de chenal / χ-steepness ; **Cap. C1 — indices de surface minéralisée** (gossan/malachite/jarosite/placer/sel, oxydation supergène, découverte visuelle émergente, invariant « le monde ne ment jamais ») (loi de Flint pente–aire `S = k_s·A^−θ`, méthode χ intégrale de Perron & Royden 2013, invariant pivot = récupération exacte de la loi de puissance + linéarité χ–z, bande gradée θ∈[0,40 ; 0,60]) |
| Écologie / hydrologie | 74 | `hydrology_mode` sv1d ; Earth Console overlay flux ; Wave 49 quantification réseau (Strahler + Horton + drainage density) ; Wave 53 routage de débit LTI ; **Wave 57 boucle eau→sédiment→relief fermée** (Exner sur graphe D8) ; **Cap. C3 — potabilité de l'eau** (salinité douce/saumâtre/mer perçue par le goût, dérivée de biome OCEAN + halite peu profonde + élévation côtière, invariant « le monde ne ment jamais ») |
| Sociétés / agents | 77 | NEAT + construction émergente + memetic + `/api/audio` ; **Cap. C2 — affleurements de pierre taillable** (obsidienne/silex/quartzite/basalte, classe de fracture, hiérarchie archéologique, découverte d'outil émergente, invariant « le monde ne ment jamais ») |
| Rendu visuel | 82 | Globe + iso 2.5D + humains + ombres + 2D lite |
| Observation IA | 86 | Earth Console SSE, replay, observer_feed, WebGPU |
| Pont Python ↔ Rust | 82 | GENM + mutations write-back + snapshot |

**Référence unique (source de vérité) :** [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md)  
**Architecture God-Engine (audit next-level) :** [`docs/GOD-ENGINE-ARCHITECTURE.md`](docs/GOD-ENGINE-ARCHITECTURE.md) · P0 **GENM + align_heightmap** livré (`macro_grid_export.py`, `genesis-macro-bridge`)  
**Prochain sprint réalisme :** section « Prochain sprint » dans ce fichier roadmap.

---

## Stacks actives

| Stack | Chemin | Rôle |
|-------|--------|------|
| **Runtime Python** | [`runtime/`](runtime/README.md) | Simulation agents, civilisation, rendu, smokes `p0`–`p79` |
| **World Engine Rust** | [`native/world-engine/`](native/world-engine/README.md) | WorldGraph, biome Köppen, streaming, GPU érosion (parallèle, pas remplacement) |
| **Scaffolding Rust** | `scaffolding/` | Crates historiques ECS / proto (CI `make rust-check`) |
| **Docs & preuves** | [`docs/`](docs/README.md) | Sprints, compliance renders, roadmap |

---

## Pipeline civilisation (orchestration)

`runtime/scripts/civilization_pipeline.py` enchaîne bootstrap Genesis (**via `wire_full_stack`** :
genesis, rust WorldGraph, 5cd), coupler multi-taux, ticks agents et exports
(observable, Köppen FAIR, épidémie).
Entrée Makefile : **`make civilization`** · smoke : **p82**.

## Smokes de référence (dernière vague)

Depuis la racine du repo (`PYTHONPATH=runtime` implicite via `make` ou `cd runtime`) :

```bash
make smoke                    # p0 — sanity
make civilization             # pipeline émergence + manifest
make validate-all             # pytest (157 tests) + smokes p72–p87 + SSE
make earth-console            # Terre live UI (8090)
make terre-long               # preset terre 2000 ticks + artifact enrichi
python run.py terre --ticks 500
cd runtime && python scripts/p82_civilization_pipeline_smoke.py
```

Liste complète : [`runtime/README.md`](runtime/README.md#smoke-tests).

---

## Fichiers « source de vérité »

| Besoin | Fichier |
|--------|---------|
| File de travail vivante | [`NEXT-SPRINT.md`](NEXT-SPRINT.md) |
| Roadmap phases 0–5 | [`ROADMAP.md`](ROADMAP.md) |
| Réalisme Terre chiffré | [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) |
| Spec contractuelle | [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx) |
| Vision long terme | [`FUTURE-VISION.md`](FUTURE-VISION.md) |
| Contribuer | [`CONTRIBUTING.md`](CONTRIBUTING.md) |

---

## Renders & conformité visuelle

Les captures PNG/GIF de preuve vivent sous :

- [`docs/compliance/renders/`](docs/compliance/renders/) — jeux de tests waves 27–37 (compliance)
- [`docs/renders/`](docs/renders/) — sorties récentes (ex. wave 41 atmosphère, iso 36)

Ne pas dupliquer les assets sans besoin ; les README pointent vers ces dossiers.
