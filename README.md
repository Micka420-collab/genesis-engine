<div align="center">

# 🌍 Genesis Engine

### Plateforme de Simulation Civilisationnelle Autonome
**An Artificial-Life Laboratory for Emergent Civilizations**

🌐 **Languages** :
[🇫🇷 Français](README.md) ·
[🇬🇧 English](README.en.md) ·
[🇪🇸 Español](README.es.md) ·
[🇨🇳 中文](README.zh-CN.md) ·
[🇸🇦 العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/release/python-3140/)
[![Status: Phase 4 complete](https://img.shields.io/badge/status-Phase_4_complete-green.svg)](#-roadmap)
[![Modules: 18/18](https://img.shields.io/badge/ADR--0005_modules-18%2F18-brightgreen.svg)](#-architecture-stratifi%C3%A9e)
[![Earth-anchored](https://img.shields.io/badge/Earth-anchored-green.svg)](#-earth-anchored-anywhere-on-earth)
[![Deterministic](https://img.shields.io/badge/deterministic-✓-purple.svg)](#-d%C3%A9terminisme)

*Construire un univers numérique persistant dans lequel des agents IA véritablement autonomes naissent, évoluent, se reproduisent, façonnent leur propre histoire et permettent l'observation scientifique de civilisations artificielles émergentes.*

[Vision](#-vision-en-une-phrase) ·
[Architecture](#-architecture-stratifi%C3%A9e) ·
[Démarrage](#-d%C3%A9marrage-rapide) ·
[Roadmap](#-roadmap) ·
[Contribuer](#-comment-contribuer) ·
[Doc complète](Genesis_Engine_Architecture_v1.0.docx)

</div>

---

## 🎯 Vision en une phrase

> **Étant donné un environnement physique cohérent et un ensemble minimal de règles fondamentales, la complexité civilisationnelle — langage, économie, religion, science, conflits, gouvernance — peut-elle émerger spontanément à partir d'agents IA autonomes ?**

Hypothèse falsifiable et reproductible inspirée de Conway (Game of Life), Ray (Tierra), Generative Agents (Park 2023), Project Sid (PIANO 2024), et des world models 2025-2026 (Genie 3, Cosmos, V-JEPA-2, Marble).

### 🔭 Vision long-terme — Counterfactual humanity

> **L'objectif ultime** : donner aux agents IA toutes les bases du monde réel (physique, chimie, matériaux, biologie, géographie), puis les laisser explorer **d'autres styles de construction, d'autres styles de société**, pour voir **ce que l'humanité aurait pu faire**. Les IA peuvent **inventer de nouveaux matériaux** — mais tout en **respectant les lois de la nature** (conservation masse-énergie, énergies de liaison, thermodynamique).

L'histoire humaine est un seul tirage parmi des milliards de possibles. Genesis Engine veut servir de **laboratoire de contrefactuelle** : si on rejoue l'histoire de la Terre 1000 fois avec les mêmes lois physiques, combien de civilisations ressemblent à la nôtre ?

📖 **Lire la vision complète** : [`FUTURE-VISION.md`](FUTURE-VISION.md) — 4 piliers, roadmap 4 vagues, critères de succès, références scientifiques.

---

## ✨ Ce qui marche aujourd'hui

**18 modules ADR-0005 taggés** orchestrés en pipeline cohérent
(Earth → minerals → metallurgy → buildings → cultural transmission).

### 🌍 Substrat physique

| Capacité | Statut | Détail |
|---|---|---|
| 🛰️ **Earth-anchored** (Copernicus DEM + ESA WorldCover) | ✅ | 100% hit ratio AWS Open Data, n'importe où sur Terre |
| 🪨 **Géologie / strates** (36 minéraux réels, 4-5 couches/chunk) | ✅ | hématite, cassitérite, native_gold, granite, marble, … |
| 🏔️ **Slope/lake/walkability** (L2 sim-lift) | ✅ | 0-100m, falaises 84°, lacs 12.9% Léman |
| 🌲 **Succession végétale** (Markov 5 états) | ✅ | Prairie → forêt vieille, 100+ sim-yr |
| 🌊 **Hydrologie D8** (flow accumulation + rivers) | ✅ | Rivières émergentes |
| ☁️ **Météorologie Spencer 1971** (zenith exact + UV WHO) | ✅ | 5 types nuages, 7 précip, 3 tempêtes, UVI 10.8 tropical noon |

### 🌱 Biologie

| Capacité | Statut | Détail |
|---|---|---|
| 🌿 **Photosynthèse Farquhar-von Caemmerer-Berry** | ✅ | C3/C4/CAM, V_cmax 60, K_c 404 ppm, calibrée Sharkey 2007 |
| 🪴 **39 clades végétaux** (Sage 2004 / Magallón 2015) | ✅ | Cyanobactéries → angiospermes, divergence par CO2/O2/biome |
| 🐺 **47 espèces animales** (Lotka-Volterra + plant-animal coevolution) | ✅ | Arthropodes, fish, oiseaux, mammifères (lions, baleines, …) |
| 🦠 **Pathogènes contagieux** (cholera, flu, wound infection) | ✅ | Immune memory + transmission via DRINK/proximity |
| 🧴 **Bronzage UV épidermique** (réponse mélaninique réelle) | ✅ | Tan grows 5j sous UV>3, fade 30j ; effective_melanin |
| 💩 **Excrétion + hygiène** (bladder, bowel, contamination eau) | ✅ | Cholera émergent par auto-contamination (Snow 1854) |

### 🛠️ Civilisation

| Capacité | Statut | Détail |
|---|---|---|
| 🧬 **Génome 256-gènes** + 8 stades de vie | ✅ | Crossover + mutation 1e-4 + cognitive efficiency |
| 👥 **Démographie multi-générations** | ✅ | 23 générations observées en 5K ticks |
| 🗣️ **Proto-langage émergent** | ✅ | 95k vocalisations / 5K ticks |
| ⚗️ **Material synthesis Wave 1+2** (39 clades + dopage non-linéaire) | ✅ | Cu+Sn→bronze, Fe+1.5%C→acier 6.17 Mohs |
| ⛏️ **Mining** (ActionKind.MINE depth-driven) | ✅ | Extrait ore via stratigraphy, alimente synthesis |
| 🔥 **Métallurgie réelle** (smelt: ore+fuel+furnace+practices) | ✅ | bloomery, charcoal, bellows ×1.15, blast_furnace ×0.85 |
| 🌾 **Agriculture** (PLANT/HARVEST + per-culture seed library) | ✅ | Cultures découvrent seeds via FORAGE |
| 📜 **Writing** (inscriptions sur material_aging instances) | ✅ | Argile 6000 ans, granite immortel, transmission inter-gen |
| 🏛️ **Polity émergent** (taxation 5% + redistribution + lois) | ✅ | Leader élu par offspring + age + inscriptions authored |
| 🏚️ **Discovery-driven buildings** (statics + auto-naming per culture) | ✅ | **Zéro recette scriptée** — archetypes émergent par expérimentation |
| 🌐 **GlobalWorld** (atmosphère + horloge partagées + migration agents) | ✅ | N régions cohérentes, agents traversent frontières |

### 🛡️ Infrastructure

| Capacité | Statut | Détail |
|---|---|---|
| 🪙 **Material aging** (corrosion/rot/wear per-instance) | ✅ | Fer 3%/an, granite 0.005%/an ; maintenance practices |
| ⏱️ **Time-warp x10/x100/x1000** | ✅ | 38×/84× speedup mesuré, déterminisme préservé |
| 💾 **Persistence bit-identique** (P1 round-trip + SHA-256) | ✅ | 18 modules sauvegardés ; integrity manifest |
| 🔬 **Long-run stability** (100K ticks validés) | ✅ | Mémoire stable, déterminisme `143ba17ef510a024` |
| 👁️ **Live dashboard** (`/api/*` ~20 endpoints + overlays) | ✅ | clouds, uv, wind, gpp, ndvi, marine, precip, … |
| 📤 **Export GIS** | ✅ | GeoTIFF, PNG carto, OBJ heightfield, JSON |

---

## 🌐 Earth-anchored anywhere on Earth

Genesis Engine charge **directement les données Copernicus DEM + ESA WorldCover via AWS Open Data** (zéro credentials, zéro téléchargement, streamé via `/vsis3` rasterio). Validé sur 4 continents :

| Région | Lat / Lon | L1 Hit | Bio dominant | Particularité |
|---|---|---|---|---|
| 🇨🇭 **Lausanne** | 46.51 / 6.63 | 480/480 | GARRIGUE 60% | lac Léman 10.8%, slope 1.43° |
| 🇪🇬 **Sahara** | 25.70 / 29.00 | 453/453 | PRAIRIE 100% | désert plat |
| 🇧🇷 **Amazon** | -3.11 / -60.02 | 485/485 | GARRIGUE 89% | forêt tropicale |
| 🇮🇸 **Reykjavík** | 64.14 / -21.94 | 468/468 | GARRIGUE 72% | subarctique côtier |

---

## 🏗️ Architecture stratifiée

**18 modules orthogonaux** validés par [ADR-0005](adr/0005-world-model-taxonomy.md) selon deux axes :

| Module | Pipeline (origine de l'état) | Capability (arxiv 2604.22748) |
|---|---|---|
| `earth_loader` | Genesis-L1 Earth-Seed | paper-L1 Predictor |
| `geology` | Genesis-L1 Earth-Seed | paper-L1 Predictor |
| `sim_lift` | Genesis-L2 Sim-Lift | paper-L2 Simulator |
| `realism` | Genesis-L4 Feedback | paper-L2 Simulator |
| `physiology` | Genesis-L4 Feedback | paper-L2 Simulator |
| `photosynthesis` | Genesis-L4 Feedback | paper-L2 Simulator |
| `material_aging` | Genesis-L4 Feedback | paper-L1 Predictor |
| `marine` | Genesis-L4 Feedback | paper-L2 Simulator |
| `global_world` | Genesis-L4 Feedback | paper-L2 Simulator |
| `plant_evolution` | Genesis-L4 Feedback | paper-L2 Simulator |
| `meteorology` | Genesis-L4 Feedback | paper-L2 Simulator |
| `animal_evolution` | Genesis-L4 Feedback | paper-L2 Simulator |
| `agriculture` | Genesis-L4 Feedback | paper-L2 Simulator |
| `writing` | Genesis-L4 Feedback | paper-L2 Simulator |
| `polity` | Genesis-L4 Feedback | paper-L2 Simulator |
| `metallurgy` | Genesis-L4 Feedback | paper-L2 Simulator |
| `realistic_construction` | Genesis-L4 Feedback | paper-L2 Simulator |
| `building_discovery` | Genesis-L4 Feedback | paper-L2 Simulator |

```
┌─ Phase 4 émergence : agriculture, writing, polity, building discovery
├─ Wave 10 métallurgie : geology strata + mining + smelt + construction
├─ Wave 6-8 biologie  : plant evolution + animal evolution + meteorology
├─ Wave 3-5 vie       : physiology + photosynthesis + material_aging + marine
├─ Wave 1-2 chimie    : 50 elements + material_synthesis (Farquhar/doping)
├─ Phase 5cd          : agents PIANO, invention, atmosphère, langage
├─ Reality Engine     : hydrologie + faune + sentiers + saisons + maladies
├─ L2 Sim-Lift        : succession végétale + érosion + slope + walkability
├─ L1 Earth-Seed      : Copernicus DEM + ESA WorldCover + geology strata
└─ Procedural         : Whittaker biomes (fallback déterministe)
```

### 🔬 Règle invariante du projet

> **Rien n'est scripté. Les agents découvrent par eux-mêmes.**

Aucune table de recettes pour les alliages, les semences, les bâtiments,
les pathogènes, les espèces. Tout émerge des lois physiques + des
décisions agents :
- `material_synthesis.synthesize(elements, conditions)` — chimie réelle
- `building_discovery.complete_structure(blocks)` — statics + naming auto
- `agriculture.discover_seed(culture, clade)` — via FORAGE
- `plant_evolution` émerge des conditions CO2/O2/biome
- `writing` propage les découvertes inter-générations

Pour la vue d'ensemble complète des 7 couches logiques, voir [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx).

---

## 🚀 Démarrage rapide

### Prérequis

- **Python 3.13+** (testé sur 3.14 Windows)
- **rasterio + pyproj** pour l'Earth-anchored (sinon fallback procédural)
- **Connexion internet** (uniquement pour Copernicus DEM + ESA WorldCover, sinon mode offline)

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine
pip install numpy rasterio pyproj
```

### Hello, World — 30 secondes

```python
from engine.world_builder import WorldBuilder

# Construire un monde à Lausanne, rive nord du Léman
world = (WorldBuilder("hello_lausanne")
         .anchor(46.510, 6.633)   # Lausanne-Ouchy
         .size_km(2.0)
         .founders(20)
         .max_agents(1000)
         .with_realism()           # hydrology + wildlife + trails + seasons + disease
         .build())

world.run(2000)                    # ~6 minutes wall-clock
print(world.summary())
```

### Observer en direct (dashboard god view)

```bash
python runtime/scripts/p4_leman_live.py --port 8765
# Puis ouvrir http://localhost:8765/god_view_v2.html
```

Tu vois en temps réel : agents qui bougent, succession végétale, démographie multi-générations, lignées, top progéniteurs, distribution biome, météo, faune.

### Multi-régions demo

```bash
python runtime/scripts/multi_region_demo.py
# Génère 4 mondes (Lausanne + Sahara + Amazon + Reykjavík)
# Exporte 4× PNG carto + 12× GeoTIFF + 4× JSON + 4× library entries
```

### Exporter pour QGIS / ArcGIS / Mapbox / Blender

```python
from engine.world_export import export_geotiff, export_png_map, export_obj_heightfield

export_geotiff(world, "height", "out/dem.tif")        # → QGIS, ArcGIS, Mapbox
export_geotiff(world, "biome",  "out/biome.tif")      # → categorical raster
export_geotiff(world, "slope_deg", "out/slope.tif")
export_png_map(world, "out/map.png")                  # → carte cartographique
export_obj_heightfield(world, "out/mesh.obj", xy_step=4)  # → Blender / Three.js
```

### Sauvegarder / charger / brancher

```python
from engine.world_library import save_world, load_world, branch_world

save_world(world, name="experiment_42")
world2 = load_world("experiment_42")     # demain, dans une autre session
branch_world("experiment_42", "fork_with_catastrophe")  # what-if scenarios
```

### Time-warp pour observer des millénaires

```python
world.set_time_warp("x100")              # 84× speedup mesuré
world.run(10_000)                        # ~12s wall-clock pour 10K ticks
world.set_time_warp("realtime")
```

---

## 🆚 Comparaison avec les outils 2026

| Capacité | World Machine | Gaea | NVIDIA Earth-2 | Project Sid | **Genesis Engine** |
|---|---|---|---|---|---|
| Earth-anchored DEM | ❌ | ❌ | ✅ | ❌ | **✅** |
| Civilisation multi-gen | ❌ | ❌ | ❌ | ✅ | **✅ 23 gen** |
| Wildlife Lotka-Volterra | ❌ | ❌ | ❌ | ❌ | **✅** |
| Trails émergents | ❌ | ❌ | ❌ | ❌ | **✅** |
| Seasons sync Earth | ❌ | ❌ | ✅ | ❌ | **✅** |
| SIR epidemic | ❌ | ❌ | ❌ | ❌ | **✅** |
| Live dashboard | ❌ | ❌ | partiel | ✅ | **✅** |
| Save/load/branch | ✅ | ✅ | partiel | partiel | **✅** |
| Export GeoTIFF | ✅ | ✅ | ✅ | ❌ | **✅** |
| Déterminisme bit-perfect | partiel | partiel | partiel | partiel | **✅** |
| Open-source local | ❌ | ❌ | ❌ | partiel | **✅ (AGPL-3)** |

Genesis Engine est **le seul** outil 2026 qui combine **vraie géographie planétaire** + **civilisation vivante** + **persistance** + **exports GIS standards** en stack 100% open-source déterministe.

---

## 🗺️ Roadmap

Le projet suit la roadmap phasée de [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx) §44-49.

- **Phase 0** — Foundations (substrat ECS, monorepo, observability) — ✅
- **Phase 1** — MVP Vie (boucle cognitive, mort biologique) — ✅
- **Phase 2** — MVP Société (reproduction, mémoire, lexique) — ✅
- **Phase 3** — MVP Civilisation (construction, troc, métiers, conflits) — 🟡 partiel
- **Phase 4** — Émergence Civilisationnelle (agriculture ✅ + écriture ✅ + État ✅) — ✅ **COMPLÈTE**
- **Phase 5** — Genesis-α Public (2 fondateurs, 10 ans réels = 10000 ans sim) — ⏳ **9/10 pré-requis livrés**

### 🎯 Pré-requis Phase 5

| # | Pré-req | État |
|---|---|---|
| 1 | 19 modules ADR-0005 taggés (earth_loader → art_discovery) | ✅ |
| 2 | P-NEW.22 cholera bloquant corrigé | ✅ |
| 3 | P-NEW.24 photo cache LRU 4096 | ✅ |
| 4 | Wave 9d cognition wiring (PLANT/HARVEST/FORAGE) | ✅ |
| 5 | Wave 10b MINE wiring | ✅ |
| 6 | Wave 10c SMELT chain | ✅ |
| 7 | Wave 10d realistic construction | ✅ |
| 8 | Wave 10e discovery-driven buildings | ✅ |
| 9 | Wave 11 personality drives politics | ✅ |
| 10 | Wave 12 long-run 10K sim-yr stable | ⏳ |

### Pipeline complet vérifié end-to-end

```
Earth (Wave L1)
  ↓ MINE depth=50m → ore in inv_metal
🪨 Geology strata (36 minerals)
  ↓ SMELT hematite + charcoal in bloomery
🔥 Metallurgy (yield 65 % × fuel × skill × practices)
  ↓ pure Fe, Cu, Sn, Au, …
⚗️ Material synthesis (Cu70Sn30 → bronze ; Fe+1.5%C → steel 6.17 Mohs)
  ↓ SynthesizedMaterial
🪙 Material aging (Fe 3 %/yr, granite 0.005 %/yr, bronze 0.35 %/yr)
  ↓ place_block × N
🏚️ Building discovery (statics validation + auto-naming per culture)
  ↓ Inscribe RECIPE/SEED/LAW on clay tablet
📜 Writing (clay 6000 yr lifespan)
  ↓ future generation READ inscription
🌾 Agriculture seed_library + 🏛️ Polity treasury
```

23/23 smokes p15→p38 PASS. Bit-perfect determinism confirmé.

Voir [`NEXT-SPRINT.md`](NEXT-SPRINT.md) pour la file de travail vivante et [`docs/sprints/`](docs/sprints/) pour les ~25 logs de sessions.

---

## 🎲 Déterminisme

Genesis Engine est **bit-perfect déterministe** sur tous ses sub-systems via `engine.core.prf_rng`. Même `(seed, region, config)` → même monde, même trajectoire civilisationnelle, mêmes inventions.

> Aucun `random.random()`. Aucun `np.random` non-seedé. Aucun `time.time()` dans la logique.

Validé par SHA-256 sur (alive + pos + drives) après N ticks : 2 runs identiques.

---

## 📂 Structure du repo

```
genesis-engine/
├── runtime/
│   ├── engine/                          # 35+ modules
│   │   # ─ Core boucle sim ─
│   │   ├── sim.py                       # Simulation step loop
│   │   ├── agent.py                     # AgentRegistry + ActionKind (18 actions)
│   │   ├── cognition.py                 # perceive / decide / apply_decision
│   │   ├── world.py                     # procedural worldgen (Whittaker biomes)
│   │   # ─ Wave L1 — substrat Earth ─
│   │   ├── earth_loader.py              # Copernicus DEM + ESA WorldCover
│   │   ├── earth_streamer.py            # bridge L1 → ChunkStreamer
│   │   ├── geology.py                   # strates + extraction (36 minerals)
│   │   ├── mineral_catalog.py           # 36 minéraux réels + yields
│   │   # ─ Wave L2 — terrain dynamics ─
│   │   ├── sim_lift.py                  # vegetation + erosion + slope
│   │   # ─ Wave L4 — Reality Engine + bio ─
│   │   ├── realism.py                   # hydrology + wildlife + trails + seasons
│   │   ├── physiology.py                # Wave 3 excretion / disease / UV tan
│   │   ├── photosynthesis.py            # Wave 4 Farquhar C3/C4/CAM
│   │   ├── material_aging.py            # corrosion / rot / wear
│   │   ├── marine.py                    # Wave 5 currents / tides / fish
│   │   ├── global_world.py              # Phase 15 multi-region shared atm
│   │   ├── plant_evolution.py           # Wave 6 — 39 clades emergent
│   │   ├── plant_catalog.py             # 39 plant clades (Sage / Magallón)
│   │   ├── meteorology.py               # Wave 7 — Spencer 1971 + UV WHO
│   │   ├── animal_evolution.py          # Wave 8 — 47 species + LV
│   │   ├── animal_catalog.py            # 47 animal species (NCBI / IUCN)
│   │   ├── elite_metrics.py             # Wave 11 — Gini / Hill alpha
│   │   # ─ Phase 4 émergence civilisationnelle ─
│   │   ├── agriculture.py               # PLANT/HARVEST + seed_library
│   │   ├── writing.py                   # Inscriptions on aging materials
│   │   ├── polity.py                    # Proto-government + Wave 11 Big-Five wiring
│   │   ├── metallurgy.py                # Wave 10c — smelt ore + fuel
│   │   ├── realistic_construction.py    # Wave 10d — real materials
│   │   ├── building_discovery.py        # Wave 10e — emergent via statics
│   │   ├── art_discovery.py             # Wave 13 — emergent drawings (Lascaux/Altamira pattern)
│   │   # ─ Wave 1-2 — chimie / matériaux ─
│   │   ├── physics.py / chemistry.py / material_synthesis.py / statics.py
│   │   # ─ Infrastructure ─
│   │   ├── timewarp.py                  # x10/x100/x1000/milestone
│   │   ├── genome.py                    # 256-gene + 8 LifeStages
│   │   ├── world_builder.py             # fluent builder API
│   │   ├── world_export.py              # GeoTIFF / PNG / JSON / OBJ
│   │   ├── world_library.py             # save / load / branch + SHA-256
│   │   ├── world_model_capabilities.py  # ADR-0005 agregator + lint
│   │   ├── dashboard.py                 # HTTP god view + ~20 endpoints
│   │   └── god_view_v2.html             # multi-panel observatory UI
│   ├── scripts/                         # smoke tests (p0 → p38, 23 PASS)
│   └── tests/
├── architecture/                # ADRs + tech specs
├── *.md                         # SPRINT logs + phase progress
├── Genesis_Engine_Architecture_v1.0.docx  # spec contractuelle (53 sections)
├── ETHICS.md / SECURITY.md / ROADMAP.md
├── CONTRIBUTING.md              # comment contribuer
└── README.md                    # ce fichier
```

---

## 🤝 Comment contribuer

**Genesis Engine est un projet open-source de recherche en artificial life.** Tu es bienvenu·e que tu sois :

- 🧪 **Chercheur·se** (alife, complex systems, agent-based modeling)
- 💻 **Ingénieur·e** (Python, NumPy, simulation, optim perf)
- 🎨 **Créateur·rice** (3D rendering, dashboard UI, dataviz)
- 🌍 **Géographe / Géologue** (validation L1 Earth data, hydrologie)
- 📜 **Linguiste / Anthropologue** (émergence linguistique, dynamiques sociales)
- 🤖 **ML / LLM engineer** (Phase 5 LLM cognition tier-2)
- 📖 **Éthicien·ne** (Conseil Éthique externe — voir [ETHICS.md](ETHICS.md))

### En 4 étapes

```bash
# 1. Fork + clone
git clone https://github.com/<ton-handle>/genesis-engine.git
cd genesis-engine

# 2. Crée une branche
git checkout -b feature/ma-contribution

# 3. Lance les smoke tests (vérifie que rien ne casse)
cd runtime
python scripts/p0_smoke.py        # 200-tick sanity check
python scripts/p12_integration_full.py  # intégration 5-en-1

# 4. Commit + push + PR
git commit -am "feat: short imperative description"
git push origin feature/ma-contribution
# Ouvre une Pull Request sur GitHub
```

### Conventions de code

- **Python 3.13+**, PEP 8, type hints recommandés mais pas requis.
- **Déterminisme obligatoire** : pas de `random.*` ni `np.random.*` non-seedé. Utilise `engine.core.prf_rng(seed, namespace, params)`.
- **No-rewrite rule** : préfère l'extension modulaire à la réécriture des fichiers existants. Les patches minimaux (Edit ciblé) sont préférés.
- **Tests smoke** : tout nouveau sub-system doit livrer un script `runtime/scripts/pN_<name>_smoke.py` avec UTF-8 stdout forcé.
- **UTF-8 stdout** : sur Windows, les emojis cassent cp1252 — voir le pattern de `p0_smoke.py` lignes 1-15.

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour plus de détails (gouvernance, code review, branch naming, conventions de commit).

### Priorités où contribuer en ce moment

| Chantier | Difficulté | Impact |
|---|---|---|
| Calibrer wolf attack threshold | facile | moyen |
| HUD widget pour `/api/realism_state` | facile | moyen |
| Génome → personnalité au spawn | moyen | élevé |
| Cross-chunk hydrology | moyen | élevé |
| Spécialisation métiers (§17) | moyen | très élevé |
| LLM cognition tier-2 (§10) — vLLM + Llama/Mistral local | difficile | game-changer |
| PQC crypto hybride (§37) — ML-KEM-768 + X25519 | difficile | sécurité prod |

---

## 🛡️ Éthique & sécurité

Genesis Engine simule des entités cognitives complexes à grande échelle. Avant toute contribution majeure, lis :

- [`ETHICS.md`](ETHICS.md) — statut moral des agents, limites de "souffrance" simulée, Conseil Éthique externe
- [`SECURITY.md`](SECURITY.md) — modèle de menace, PQC, signalement de vulnérabilité
- **Avatars humains** : opt-in explicite, watermark cryptographique, droit à l'oubli RGPD

**Signaler une vulnérabilité** : ouvrir une issue privée via GitHub Security Advisories ou contacter `micka.delcato.rp@gmail.com`.

---

## 📚 Références scientifiques

Les bases théoriques sont détaillées dans [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx) Annexe B :

- Park, J.S. et al. (2023). *Generative Agents: Interactive Simulacra of Human Behavior*
- Altera (2024). *Project Sid: Many-agent simulations toward AI civilization (PIANO)*
- Wang, G. et al. (2023). *Voyager: An Open-Ended Embodied Agent with LLMs*
- DeepMind (2025). *Genie 3: A new frontier for world models*
- Conway, J.H. (1970). *Game of Life*
- Ray, T.S. (1991). *An approach to the synthesis of life*
- NIST FIPS 203/204/205 (2024) — standards post-quantique

---

## 📜 Licence

[AGPL-3.0](LICENSE) — voir `Genesis_Engine_Architecture_v1.0.docx` §30 *"code core open-source sous licence AGPL après stabilisation; datasets sous CC-BY-SA"*.

Tu peux utiliser, modifier, redistribuer librement. Si tu héberges Genesis Engine comme service (SaaS), tu dois rendre le code source modifié accessible aux utilisateurs.

---

## 🙏 Crédits

Conçu et maintenu par [Micka Delcato](https://github.com/Micka420-collab).
Architecture rédigée mai 2026. Code core écrit en Python 3.13+, NumPy.

---

<div align="center">

*"Construire un univers numérique persistant, scalable et sécurisé dans lequel des agents IA véritablement autonomes naissent, évoluent, se reproduisent, façonnent leur propre histoire et permettent l'observation scientifique de civilisations artificielles émergentes."*

[⬆ Retour en haut](#-genesis-engine)

</div>
