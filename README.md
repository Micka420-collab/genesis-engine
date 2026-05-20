<div align="center">

# Genesis Engine

**Laboratoire de simulation civilisationnelle autonome** — mondes déterministes, agents IA, émergence observée.

🌐 [Français](README.md) · [English](README.en.md) · [Español](README.es.md) · [中文](README.zh-CN.md) · [العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Earth realism ~76%](https://img.shields.io/badge/r%C3%A9alisme_Terre-~76%25-orange.svg)](docs/ROADMAP-REALISME-TERRE.md)
[![Deterministic](https://img.shields.io/badge/deterministic-PRF-purple.svg)](#déterminisme)
[![CI](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml)

[EMERGENCE SIM v2](docs/EMERGENCE-SIM-v2.md) · [Master prompt](docs/MASTER-SCALE-PROMPT-v2.md) · [État du projet](PROJECT-STATUS.md) · [Earth Console](docs/EARTH-CONSOLE.md) · [Runtime](runtime/README.md) · [Rust](native/world-engine/README.md)

</div>

---

## Vision — EMERGENCE SIM v2.0

**ZERO PRE-SCRIPT** : seules les lois physiques sont hardcodées. Langage, outils, civilisation et terraformation doivent **émerger** des agents — jamais être des quêtes scriptées.

Manifeste complet : **[`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md)**

| Layer | Contenu |
|-------|---------|
| **L0** Physics | Thermo, gravité, hydrologie, érosion |
| **L1** World | Genesis, climat, biomes, ressources |
| **L2** Biology | ADN 256-D, métabolisme, sélection |
| **L3** Cognition | Perception locale, plasticité (NEAT = cible) |
| **L4** Civilization | Commerce, construction, polity, langage |

**Observer :** `.\earth-console.ps1` → http://127.0.0.1:8090/ · KPIs : `/api/emergence_metrics`

Implémentation : tout émerge de `Simulation.step()` + `sim_emergence.py` — pas de pipeline orchestrateur. Voir [`PROJECT-STATUS.md`](PROJECT-STATUS.md).

---

## Où en est le projet ?

| Axe | Statut | Détail |
|-----|--------|--------|
| Phases 0–2 (vie, société) | ✅ | Cognition, reproduction, lexique |
| Phase 4 (émergence civ.) | ✅ | Agriculture, écriture, polity, métallurgie |
| Phase 5 (Genesis-α) | ⏳ | Long-run 10k sim-yr en cours |
| **Waves 16–41** (monde réaliste) | ✅ | Genesis → climat → settlements → render → atmosphère → observateurs |
| **Réalisme Terre (global)** | **~76 %** | Moyenne 7 dimensions → [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) (objectif **80 %**) |

Synthèse maintenue : **[`PROJECT-STATUS.md`](PROJECT-STATUS.md)** · file de travail : **[`NEXT-SPRINT.md`](NEXT-SPRINT.md)**.

### Capacités phares (runtime Python)

| Domaine | Exemples livrés |
|---------|-----------------|
| Substrat | Earth-anchored (Copernicus + WorldCover), géologie 36 minéraux, hydrologie D8 |
| Bio | Photosynthèse Farquhar, 39 clades végétaux, 47 espèces Lotka-Volterra |
| **Biosphère émergente** | Protocellules → microbes → faune → sapients ([`docs/BIOSPHERE-EMERGENCE.md`](docs/BIOSPHERE-EMERGENCE.md)) |
| Civilisation | Métallurgie émergente, bâtiments par statics, écriture sur matériaux vieillissants |
| Monde & rendu | `GenesisWorld` (W16+), hillshade / iso (W27/36), atmosphère jour/nuit (W41) |
| Infra | Persistance SHA-256, time-warp, dashboard `/api/*`, exports GeoTIFF/PNG/OBJ |

---

## Architecture

```mermaid
flowchart TB
  subgraph L1["L1 — Substrat"]
    Earth[earth_loader / genesis]
    Geo[geology / tectonics]
    Hydro[hydrology / climate]
  end
  subgraph L2["L2 — Dynamiques"]
    SimLift[sim_lift / erosion]
    Bio[plant / animal evolution]
    Meteo[meteorology / atmosphere]
  end
  subgraph L3["L3 — Agents"]
    Sim[sim + cognition]
    Agents[agent registry PRF]
  end
  subgraph L4["L4 — Civilisation"]
    Agri[agriculture / metallurgy]
    Soc[polity / trade / roads]
    Obs[observers: epidemic / lineage / vision]
  end
  subgraph Native["Rust — native/world-engine"]
    WG[WorldGraph + Köppen]
    Stream[streaming / GPU]
  end
  L1 --> L2 --> L3 --> L4
  Native -.->|rust_bridge / PyO3| L1
  L4 --> Render[world_render + dashboard]
```

- **Spec contractuelle** : [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx) (53 sections)
- **ADR & specs** : [`adr/`](adr/), [`architecture/`](architecture/), [`specs/`](specs/)
- **Rust détaillé** : [`architecture/world-engine-rust.md`](architecture/world-engine-rust.md)

---

## Démarrage rapide

### Prérequis

- **Python 3.12+** (3.13 recommandé)
- **Optionnel** : Rust 1.85+ (`rustup`) pour `native/world-engine`
- **Optionnel** : `rasterio` + `pyproj` pour Terre réelle (`pip install -e ".[earth]"`)

### Installation

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
# Terre réelle :
# python -m pip install -e ".[earth,dev]"

make doctor
make smoke          # p0 — doit finir par PASSED
make test-python
```

`PYTHONPATH` : le package `engine` vit sous `runtime/`. Les commandes `make` et `pytest` le configurent ; en manuel :

```bash
# Windows PowerShell
$env:PYTHONPATH = "runtime"
python runtime/scripts/p0_smoke.py

# Linux/macOS
PYTHONPATH=runtime python runtime/scripts/p0_smoke.py
```

### Hello World (30 s)

```python
from engine.world_builder import WorldBuilder

world = (
    WorldBuilder("demo")
    .anchor(46.51, 6.63)
    .size_km(2.0)
    .founders(20)
    .with_realism()
    .build()
)
world.run(500)
print(world.summary())
```

### Philosophie : émergence civilisationnelle

Rien de « scripté » en fin de partie : climat Köppen, hydrologie des chunks,
graphe de contacts épidémiques et exports observables doivent **émerger du
même monde** que les agents (`bootstrap_genesis_sim` → ticks → observers).
Le pipeline déterministe `runtime/scripts/civilization_pipeline.py`
(`make civilization`) enchaîne bootstrap, coupler multi-taux, simulation et
manifeste FAIR — pas de grille macro factice sauf opt-in `--synthetic-only`.

### Biosphère 100 % émergente (`origins`)

```bash
cd runtime
python run.py origins
```

Pas de fondateurs scriptés : substrat → protocellules → cyanobactéries → O₂ → faune
→ primates → ≤2 sapients. Documentation : [`docs/BIOSPHERE-EMERGENCE.md`](docs/BIOSPHERE-EMERGENCE.md).

### Smokes récents (réalisme session mai 2026)

```bash
make civilization          # pipeline complet + artifacts/
make validate-fair         # Köppen FAIR + checksums
make observe               # dashboard + SSE
cd runtime && python scripts/p82_civilization_pipeline_smoke.py
PYTHONPATH=runtime python -m pytest runtime/tests/test_life_emergence.py -q
```

### Rust (world-engine)

```bash
cd native/world-engine
cargo test
cargo run --release -p genesis-streaming --example demo_world
```

Voir [`native/world-engine/README.md`](native/world-engine/README.md).

---

## Structure du dépôt

```
genesis-engine/
├── runtime/                 # Simulation Python (package engine)
│   ├── engine/              # Modules sim, monde, civilisation, rendu
│   ├── scripts/             # Smokes p0 … p79, démos
│   └── tests/               # pytest
├── native/world-engine/     # Moteur Rust (WorldGraph, biome, streaming)
├── scaffolding/             # Crates Rust historiques (ECS proto)
├── docs/                    # Index doc, sprints, renders, roadmap réalisme
├── architecture/ adr/ specs/ ethics/ ops/   # Specs & gouvernance
├── PROJECT-STATUS.md        # Synthèse statut (ce qu’il faut lire en premier)
├── NEXT-SPRINT.md           # Journal de priorités détaillé
├── CONTRIBUTING.md          # Guide contributeur
└── README.md                # Ce fichier
```

**Arborescence détaillée runtime** : [`runtime/README.md`](runtime/README.md).

---

## Documentation

| Document | Rôle |
|----------|------|
| [`docs/README.md`](docs/README.md) | Index de toute la documentation |
| [`docs/sprints/README.md`](docs/sprints/README.md) | Historique des sessions (Waves, phases) |
| [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) | Grille réalisme **~76 %** (source de vérité) + commandes vérif |
| [`ROADMAP.md`](ROADMAP.md) | Phases produit 0–5 |
| [`ETHICS.md`](ETHICS.md) · [`SECURITY.md`](SECURITY.md) | Gouvernance |

**Renders** (ne pas supprimer sans accord) : [`docs/compliance/renders/`](docs/compliance/renders/), [`docs/renders/`](docs/renders/).

---

## Contribuer

Le projet accueille chercheurs alife, ingénieurs Python/Rust, géographes et contributeurs doc.

1. Lire **[`CONTRIBUTING.md`](CONTRIBUTING.md)** (premier jour, matrice « où coder », déterminisme PRF).
2. Fork → branche `feature/...` ou `fix/...`.
3. `make smoke` + smokes liés à ton domaine.
4. Pull Request (template dans [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md)).

**Règle d’or** : pas de `random.*` non seedé — uniquement `engine.core.prf_rng`. Pas d’imports inline en milieu de fichier.

---

## Déterminisme

Même `(seed, config, région)` → même monde et même trajectoire. Validation par SHA-256 sur états agents ; smokes `p0`, `p12`, et vagues `p44+` vérifient la reproductibilité.

---

## Licence

[AGPL-3.0](LICENSE) — utilisation, modification et redistribution libres ; obligation de partager les sources si vous hébergez le moteur en service.

---

## Crédits

Conçu et maintenu par [Micka Delcato](https://github.com/Micka420-collab). Architecture mai 2026.
