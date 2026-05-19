# Genesis Engine — État du projet

**Dernière mise à jour :** 19 mai 2026  
**Synthèse courte** pour contributeurs et reviewers GitHub. Pour le détail session par session, voir [`NEXT-SPRINT.md`](NEXT-SPRINT.md).

---

## En une phrase

Laboratoire open-source d’**artificial life** : monde physique déterministe (Terre ou procédural) + agents autonomes + civilisations émergentes, observable via smokes, dashboard et exports GIS.

### Philosophie — émergence civilisationnelle

Les phénomènes (climat Köppen, hydrologie, épidémies, commerce, culture, observation) **émergent du cycle `Simulation.step()`** et des interactions agents ↔ monde — pas d’un orchestrateur de scripts qui enchaîne des étapes. Les smokes (`scripts/p*.py`) et `make smoke` **valident** le comportement ; le cœur exécutable est `python runtime/run.py` ou une boucle `sim.step()`. Voir `engine/sim_emergence.py`.

---

## Avancement par phase (roadmap produit)

| Phase | Intitulé | Statut | Notes |
|-------|----------|--------|-------|
| **0** | Foundations (ECS, monorepo, observabilité) | ✅ | ADR-0005, PRF, CI |
| **1** | MVP Vie (cognition, mort biologique) | ✅ | Boucle perceive → decide → act |
| **2** | MVP Société (reproduction, mémoire, lexique) | ✅ | Multi-générations, vocalisations |
| **3** | MVP Civilisation (construction, troc, conflits) | 🟡 | Partiel ; Waves 28–32 enrichissent |
| **4** | Émergence civilisationnelle | ✅ | Agriculture, écriture, polity, métallurgie |
| **5** | Genesis-α public (long-run, LLM tier-2) | ⏳ | 9/10 prérequis livrés |
| **Waves 16–41** | Monde réaliste intégré au tick | ✅ | Genesis, climat, hydrologie, observateurs dans `sim.step()` |
| **Biosphère émergente** | Protocellules → sapients | ✅ | [`docs/BIOSPHERE-EMERGENCE.md`](docs/BIOSPHERE-EMERGENCE.md) · `run.py origins` |

Détail des **Waves 16–41** (genesis, tectonique, climat, NCA, settlements, routes, épidémie, iso, atmosphère…) : index dans [`docs/sprints/README.md`](docs/sprints/README.md) (fichiers `2026-05-18_WAVE*.md`).

---

## Réalisme Terre (grille scientifique)

Estimation **globale ~68 %** vers une simulation « publication-grade » type Terre.

| Dimension | ~% | Piste principale |
|-----------|-----|------------------|
| Climat / biomes | 76 | Köppen FAIR + bootstrap Genesis (p80) |
| Rendu visuel | 73 | PBR-lite, Rayleigh, HG + ray-march colonne |
| Observation IA | 78 | Vision JSONL, dashboard SSE (p82) |
| Sociétés / agents | 70 | Épidémie R0 réseau vs SIR (exp4) |
| Géologie / relief | 55 | Tectonique, stratigraphie légère |
| Écologie / hydrologie | 58 | Saint-Venant + LBM cross-chunk (p81) |
| Pont Python ↔ Rust | 55 | maturin CI + `genesis_world` / mock p73 |

**Référence complète :** [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md)  
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

`runtime/scripts/civilization_pipeline.py` enchaîne bootstrap Genesis, coupler
multi-taux, ticks agents et exports (observable, Köppen FAIR, épidémie).
Entrée Makefile : **`make civilization`** · smoke : **p82**.

## Smokes de référence (dernière vague)

Depuis la racine du repo (`PYTHONPATH=runtime` implicite via `make` ou `cd runtime`) :

```bash
make smoke                    # p0 — sanity
make civilization             # pipeline émergence + manifest
make validate-all             # pytest + p72–p82
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
