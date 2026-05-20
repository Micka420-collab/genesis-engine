# Documentation Genesis Engine

**Source de vérité vision :** [`EMERGENCE-SIM-v2.md`](EMERGENCE-SIM-v2.md) — ZERO PRE-SCRIPT · layers L0–L4 · observateur dieu silencieux.

**Onboarding agents / contributeurs :** [`MASTER-SCALE-PROMPT-v2.md`](MASTER-SCALE-PROMPT-v2.md) — prompt condensé v2.0 (mai 2026).

**README multilingues (14 langues, score ~76 % aligné) :**

| Fichier | Langue |
|---------|--------|
| [`README.md`](../README.md) | Français |
| [`README.en.md`](../README.en.md) | English |
| [`README.es.md`](../README.es.md) | Español |
| [`README.de.md`](../README.de.md) | Deutsch |
| [`README.pt.md`](../README.pt.md) | Português |
| [`README.it.md`](../README.it.md) | Italiano |
| [`README.zh-CN.md`](../README.zh-CN.md) | 中文 |
| [`README.ja.md`](../README.ja.md) | 日本語 |
| [`README.ru.md`](../README.ru.md) | Русский |
| [`README.ko.md`](../README.ko.md) | 한국어 |
| [`README.hi.md`](../README.hi.md) | हिन्दी |
| [`README.nl.md`](../README.nl.md) | Nederlands |
| [`README.pl.md`](../README.pl.md) | Polski |
| [`README.ar.md`](../README.ar.md) | العربية |

---

## Démarrer

| Action | Commande |
|--------|----------|
| **Observer la Terre (live)** | `.\earth-console.ps1` → http://127.0.0.1:8090/ |
| Preset long-run | `python runtime/run.py terre --ticks 2000` |
| Tests | `cd runtime && python -m pytest tests/ -q` |

Windows : pas de `make` requis — voir [`EARTH-CONSOLE.md`](EARTH-CONSOLE.md).

---

## Documents actifs (à jour)

| Document | Rôle |
|----------|------|
| [`MASTER-SCALE-PROMPT-v2.md`](MASTER-SCALE-PROMPT-v2.md) | **Prompt master** copier-coller (identité, L0–L4, réalisme **~76 %**, contraintes) |
| [`EMERGENCE-SIM-v2.md`](EMERGENCE-SIM-v2.md) | **Manifeste** prompt architecturé + mapping code |
| [`../PROJECT-STATUS.md`](../PROJECT-STATUS.md) | État livré, tests, presets |
| [`ROADMAP-REALISME-TERRE.md`](ROADMAP-REALISME-TERRE.md) | **Source de vérité** réalisme (~76 % global, objectif 80 %) |
| [`GOD-ENGINE-ARCHITECTURE.md`](GOD-ENGINE-ARCHITECTURE.md) | Rust Terre unique, GENM, mutations |
| [`LAYERS-STACK.md`](LAYERS-STACK.md) | Physics / chemistry / architecture / social |
| [`EARTH-CONSOLE.md`](EARTH-CONSOLE.md) | UI observateur live |
| [`DEEPMIND-WORLD-PRIOR.md`](DEEPMIND-WORLD-PRIOR.md) | GraphCast-lite + NCA + colonne 3D (CPU, sans API) |
| [`ALGORITHM-EVOLUTION-LAB.md`](ALGORITHM-EVOLUTION-LAB.md) | Générer → tester → sélectionner → améliorer (4 opérateurs nouveaux) |
| [`AUTONOMOUS-WORLD.md`](AUTONOMOUS-WORLD.md) | Noyau Terre, plaques mobiles, transform matériaux → objets |
| [`BIOSPHERE-EMERGENCE.md`](BIOSPHERE-EMERGENCE.md) | Protocellules → sapients |
| [`../runtime/README.md`](../runtime/README.md) | Smokes, API, modules |

---

## Architecture émergence (résumé)

```
L0 PHYSICS  → thermo, gravité, hydrologie, érosion
L1 WORLD    → genesis, climat, biomes, ressources
L2 BIOLOGY  → genome 256-D, physiologie, vie
L3 COGNITION → neat_brain, emergent_action, wire_emergence_v2
L4 CIVILIZATION → commerce, polity, construction, langage
```

**Code cœur :** `runtime/engine/sim.py` + `sim_emergence.py` + `emergence_metrics.py`  
**KPIs émergence :** `GET /api/emergence_metrics`

---

## Historique (archive)

Les sprints datés (`docs/sprints/2026-05-*.md`) sont un **journal** — ne pas les traiter comme spec active. Index : [`sprints/README.md`](sprints/README.md).

Documents **obsolètes / fusionnés** : voir [`OBSOLETE.md`](OBSOLETE.md).

---

## Specs numérotées (référence)

| Fichier | Statut |
|---------|--------|
| [`01-vision-and-philosophy.md`](01-vision-and-philosophy.md) | Anti-patterns ; vision → EMERGENCE-SIM-v2 |
| [`02-system-overview.md`](02-system-overview.md) | Vue système (compléter vs v2) |
| [`03-agent-cognition.md`](03-agent-cognition.md) | Cognition PIANO |
| [`04-world-engine.md`](04-world-engine.md) | Moteur monde |
| [`05-emergent-systems.md`](05-emergent-systems.md) | Langage, économie |
| [`06-observation-and-tooling.md`](06-observation-and-tooling.md) | Observatoire |
| [`07-glossary-and-conventions.md`](07-glossary-and-conventions.md) | Glossaire |

---

## Renders & conformité

- [`compliance/renders/`](compliance/renders/) — preuves visuelles waves 27–37
- [`renders/`](renders/) — sorties récentes

---

## Contribuer

[`../CONTRIBUTING.md`](../CONTRIBUTING.md)
