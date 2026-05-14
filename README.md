<div align="center">

# 🌍 Genesis Engine

### Plateforme de Simulation Civilisationnelle Autonome
**An Artificial-Life Laboratory for Emergent Civilizations**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/release/python-3140/)
[![Status: Phase 5g](https://img.shields.io/badge/status-Phase_5g_alpha-orange.svg)](#-roadmap)
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

---

## ✨ Ce qui marche aujourd'hui

| Capacité | Statut | Démo |
|---|---|---|
| 🌍 **Terrain Earth-anchored** (Copernicus DEM + ESA WorldCover) | ✅ | 100% hit ratio depuis AWS Open Data, n'importe où sur Terre |
| 🌲 **Succession végétale** (Markov 5 états, 100+ ans sim-time) | ✅ | Prairie → garrigue → bois jeune → forêt mature → forêt vieille |
| 🌊 **Hydrologie** (D8 flow accumulation + L1 water union) | ✅ | Lacs/rivières détectés, 8% Léman = OCEAN |
| 🦌 **Faune Lotka-Volterra** (deer/wolf/fish dynamics) | ✅ | Équilibre prédateur-proie stable |
| 🏹 **Chasse** (ActionKind.HUNT, 800 kcal/deer) | ✅ | Agents foragent ET chassent |
| 🐾 **Sentiers émergents** (foot-prints boost walkability) | ✅ | +0.3 walkability sur paths fréquentés |
| 📅 **Calendrier réel** (Earth seasons + day/night) | ✅ | Année/jour/heure synced |
| 🧬 **Génome 256-gènes** + 8 stades de vie | ✅ | Crossover + mutation 1e-4 + cognitive efficiency |
| 👥 **Démographie multi-générations** | ✅ | **23 générations** observées en 5K ticks |
| 🗣️ **Proto-langage émergent** (lexical signatures par culture) | ✅ | 95k vocalisations / 5K ticks |
| 🛠️ **Invention organique** (artefacts composites) | ✅ | `clay_stone_contain`, `flint_stone_grind`, etc. |
| 🏘️ **Construction** (HEARTH, BUILD, multi-cultures) | ✅ | 1 HEARTH complété en 5K ticks |
| ⚡ **Time-warp x10/x100/x1000** | ✅ | **38× / 84× speedup** mesuré, déterminisme préservé |
| 🦠 **Épidémies SIR** | ✅ | Infectious_until + transmission radius |
| 👁️ **God Mode dashboard** | ✅ | HTTP `/api/state`, `/api/realism_state`, `/api/demography`, `/api/lift_state` |
| 💾 **Save / Load / Branch** | ✅ | World library, format ouvert |
| 📤 **Export GIS** | ✅ | GeoTIFF (12 layers), PNG cartographique, OBJ heightfield, JSON |

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

```
┌─ Phase 5cd      : agents PIANO, construction, invention, atmosphère, langage
├─ Reality Engine : hydrologie + faune + sentiers + saisons + maladies          ⭐
├─ L2 Sim-Lift    : succession végétale + érosion + slope + walkability + lake
├─ L1 Earth-Seed  : Copernicus DEM GLO-30 + ESA WorldCover 10m (via /vsis3 AWS)
└─ Procedural     : Whittaker biomes (fallback déterministe)
```

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

- **Phase 0** — Foundations (substrat ECS, monorepo, observability) — ✅ structure
- **Phase 1** — MVP Vie (boucle cognitive, mort biologique) — ✅
- **Phase 2** — MVP Société (reproduction, mémoire, lexique) — ✅
- **Phase 3** — MVP Civilisation (construction, troc, métiers, conflits) — 🟡 partiel
- **Phase 4** — Émergence Civilisationnelle (agriculture, écriture, État) — ⏳
- **Phase 5** — Genesis-α Public (2 fondateurs, 10 ans réels = 10000 ans sim) — ⏳

### Prochaines priorités queueées

Voir [`NEXT-SPRINT.md`](NEXT-SPRINT.md) pour la file de travail vivante.

1. **§15 Émergence monnaie référence** — sel/coquillages → unité de compte
2. **§17 Spécialisation métiers** — chasseur/paysan/artisan stables
3. **§18 Compositionnalité linguistique** — combiner phonèmes pour concepts
4. **§19 Chefferie émergente** — leader élu/héréditaire avec autorité
5. **§22 Religion / animisme** — esprits → panthéon → cosmogonie
6. **§10 LLM cognition tier-2** — Llama 4 / Mistral / Qwen 3 via vLLM pour agents saillants
7. **§37-43 PQC crypto** — ML-KEM-768 + ML-DSA-65 hybride

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
│   ├── engine/                  # core engine (~25 modules)
│   │   ├── sim.py               # Phase 4 simulation loop
│   │   ├── agent.py             # AgentRegistry + ActionKind
│   │   ├── cognition.py         # perceive / decide / apply_decision
│   │   ├── world.py             # procedural worldgen (Whittaker biomes)
│   │   ├── earth_loader.py      # L1 Copernicus DEM + ESA WorldCover
│   │   ├── earth_streamer.py    # bridge L1 → ChunkStreamer
│   │   ├── sim_lift.py          # L2 vegetation + erosion + slope + lake
│   │   ├── realism.py           # Reality Engine (5 subsystems)
│   │   ├── timewarp.py          # x10/x100/x1000/milestone modes
│   │   ├── genome.py            # 256-gene + 8 LifeStages
│   │   ├── sim_5cd_integration.py  # Phase 5cd wiring
│   │   ├── world_builder.py     # fluent builder API
│   │   ├── world_export.py      # GeoTIFF / PNG / JSON / OBJ
│   │   ├── world_library.py     # save / load / branch
│   │   ├── dashboard.py         # HTTP god view server
│   │   └── god_view_v2.html     # multi-panel observatory UI
│   ├── scripts/                 # smoke tests + demos (p0..p12 + multi_region)
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
