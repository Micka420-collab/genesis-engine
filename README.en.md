<div align="center">

# 🌍 Genesis Engine

### Autonomous Civilization Simulation Platform
**An Artificial-Life Laboratory for Emergent Civilizations**

🌐 **Languages** :
[🇫🇷 Français](README.md) · [🇬🇧 English](README.en.md) · [🇪🇸 Español](README.es.md) · [🇩🇪 Deutsch](README.de.md) · [🇵🇹 Português](README.pt.md) · [🇮🇹 Italiano](README.it.md) · [🇨🇳 中文](README.zh-CN.md) · [🇯🇵 日本語](README.ja.md) · [🇷🇺 Русский](README.ru.md) · [🇰🇷 한국어](README.ko.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇳🇱 Nederlands](README.nl.md) · [🇵🇱 Polski](README.pl.md) · [🇸🇦 العربية](README.ar.md)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Status: Phase 4 complete](https://img.shields.io/badge/status-Phase_4_complete-green.svg)](#️-roadmap)
[![Earth-anchored](https://img.shields.io/badge/Earth-anchored-green.svg)](#-earth-anchored-anywhere-on-earth)
[![Deterministic](https://img.shields.io/badge/deterministic-✓-purple.svg)](#-determinism)
[![CI](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/genesis-engine/genesis-engine/actions/workflows/ci.yml)
[![Earth realism ~76%](https://img.shields.io/badge/Earth_realism-~76%25-orange.svg)](docs/ROADMAP-REALISME-TERRE.md)

[EMERGENCE SIM v2](docs/EMERGENCE-SIM-v2.md) · [Master prompt](docs/MASTER-SCALE-PROMPT-v2.md) · [Project status](PROJECT-STATUS.md) · [Earth Console](docs/EARTH-CONSOLE.md) · [Runtime](runtime/README.md) · [Rust](native/world-engine/README.md)

*Build a persistent digital universe in which truly autonomous AI agents are born, evolve, reproduce, shape their own history, and enable the scientific observation of emergent artificial civilizations.*

[Vision](#-vision-in-one-sentence) ·
[Architecture](#️-stratified-architecture) ·
[Quick start](#-quick-start) ·
[Roadmap](#️-roadmap) ·
[Contribute](#-how-to-contribute) ·
[Full spec](Genesis_Engine_Architecture_v1.0.docx)

</div>

---

## 🎯 Vision in one sentence

> **Given a coherent physical environment and a minimal set of fundamental rules, can civilizational complexity — language, economy, religion, science, conflict, governance — emerge spontaneously from autonomous AI agents?**

Falsifiable and reproducible hypothesis inspired by Conway (Game of Life), Ray (Tierra), Generative Agents (Park 2023), Project Sid (PIANO 2024), and the world models of 2025-2026 (Genie 3, Cosmos, V-JEPA-2, Marble).

### 🔭 Long-term vision — Counterfactual humanity

> **The ultimate goal**: feed AI agents all the foundations of the real world (physics, chemistry, materials, biology, geography), then let them explore **alternative construction styles, alternative societies**, to see **what humanity could have done**. AIs can **invent new materials** — but always **respecting the laws of nature** (mass-energy conservation, bond energies, thermodynamics).

Human history is a single draw among billions of possibilities. Genesis Engine aims to serve as a **counterfactual laboratory**: if we replayed Earth's history 1,000 times with the same physical laws, how many civilizations would resemble ours?

📖 **Read the full vision**: [`FUTURE-VISION.md`](FUTURE-VISION.md) — 4 pillars, 4-wave roadmap, success criteria, scientific references.

---

## EMERGENCE SIM v2.0 — ZERO PRE-SCRIPT

Only **physical laws** are hardcoded. Language, tools, civilization, and terraforming must **emerge** from agents — never scripted quests.

Full manifesto: **[`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md)**

| Layer | Content |
|-------|---------|
| **L0** Physics | Thermo, gravity, hydrology, erosion |
| **L1** World | Genesis, climate, biomes, resources |
| **L2** Biology | 256-D DNA, metabolism, selection |
| **L3** Cognition | Local perception, plasticity (NEAT target) |
| **L4** Civilization | Trade, emergent construction, polity, speech |

**Observer:** `earth-console.ps1` (Windows) or `make earth-console` → http://127.0.0.1:8090/ · KPIs: `/api/emergence_metrics`

Everything emerges from `Simulation.step()` — no orchestrator pipeline. See [`PROJECT-STATUS.md`](PROJECT-STATUS.md).

---

## Where the project stands

| Area | Status | Detail |
|------|--------|--------|
| Phases 0–2 (life, society) | ✅ | Cognition, reproduction, lexicon |
| Phase 4 (civilizational emergence) | ✅ | Agriculture, writing, polity, metallurgy |
| Phase 5 (Genesis-α) | ⏳ | Long-run 10k sim-years in progress |
| **Waves 16–41** (realistic world) | ✅ | Genesis → climate → settlements → render → atmosphere → observers |
| **Earth realism (global)** | **~76 %** | 7-dimension average → [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) (target **80 %**) |

**Tests:** `pytest runtime/tests` — **133** tests · reference smokes **p72–p86** in `make validate-all`.

Maintained summary: **[`PROJECT-STATUS.md`](PROJECT-STATUS.md)** · work queue: **[`NEXT-SPRINT.md`](NEXT-SPRINT.md)**.

> **Note:** Older docs showed **68 %**, **74 %**, or **80 %** as “global” scores. **~76 %** is the unified average; **80 %** is the user target or climate-only score — see the roadmap table.

---

## ✨ What works today

| Capability | Status | Demo |
|---|---|---|
| 🌍 **Earth-anchored terrain** (Copernicus DEM + ESA WorldCover) | ✅ | 100% hit ratio from AWS Open Data, anywhere on Earth |
| 🌲 **Vegetation succession** (5-state Markov, 100+ sim-years) | ✅ | Prairie → garrigue → young woods → mature forest → old-growth |
| 🌊 **Hydrology** (D8 flow accumulation + L1 water union) | ✅ | Lakes/rivers detected, 8% of Léman = OCEAN |
| 🦌 **Lotka-Volterra wildlife** (deer/wolf/fish dynamics) | ✅ | Stable predator-prey equilibrium |
| 🏹 **Hunting** (`ActionKind.HUNT`, 800 kcal/deer) | ✅ | Agents both forage AND hunt |
| 🐾 **Emergent trails** (foot-prints boost walkability) | ✅ | +0.3 walkability on frequented paths |
| 📅 **Real calendar** (Earth seasons + day/night) | ✅ | Year/day/hour synced |
| 🧬 **256-gene genome** + 8 life stages | ✅ | Crossover + mutation 1e-4 + cognitive efficiency |
| 👥 **Multi-generation demography** | ✅ | **23 generations** observed in 5K ticks |
| 🗣️ **Emergent proto-language** (lexical signatures per culture) | ✅ | 95k vocalizations / 5K ticks |
| 🛠️ **Organic invention** (composite artifacts) | ✅ | `clay_stone_contain`, `flint_stone_grind`, ... |
| 🏘️ **Construction** (HEARTH, BUILD, multi-cultures) | ✅ | 1 HEARTH completed in 5K ticks |
| ⚡ **Time-warp x10/x100/x1000** | ✅ | **38× / 84× speedup** measured, determinism preserved |
| 🦠 **SIR epidemics** | ✅ | `infectious_until` + transmission radius |
| 👁️ **Earth Console** (globe, iso 2.5D, agent speech) | ✅ | http://127.0.0.1:8090/ · SSE · `/api/audio` · `/api/languages` |
| 👁️ **God Mode dashboard** (legacy) | ✅ | HTTP `/api/state`, `/api/realism_state`, `/api/demography` |
| 💾 **Save / Load / Branch** | ✅ | World library, open format |
| 📤 **GIS Export** | ✅ | GeoTIFF (12 layers), cartographic PNG, OBJ heightfield, JSON |
| 🔬 **Wave 1: Physics + Chemistry knowledge base** | ✅ | 43 elements, 54 bond energies, Bronze synthesizable |

---

## 🌐 Earth-anchored anywhere on Earth

Genesis Engine loads **Copernicus DEM + ESA WorldCover data directly via AWS Open Data** (zero credentials, zero download, streamed via `/vsis3` rasterio). Validated on 4 continents:

| Region | Lat / Lon | L1 Hit | Dominant biome | Highlight |
|---|---|---|---|---|
| 🇨🇭 **Lausanne** | 46.51 / 6.63 | 480/480 | GARRIGUE 60% | Léman lake 10.8%, slope 1.43° |
| 🇪🇬 **Sahara** | 25.70 / 29.00 | 453/453 | PRAIRIE 100% | flat desert |
| 🇧🇷 **Amazon** | -3.11 / -60.02 | 485/485 | GARRIGUE 89% | tropical rainforest |
| 🇮🇸 **Reykjavík** | 64.14 / -21.94 | 468/468 | GARRIGUE 72% | subarctic coastal |

---

## 🏗️ Stratified architecture

```
┌─ Phase 5cd       : PIANO agents, construction, invention, atmosphere, language
├─ Reality Engine  : hydrology + wildlife + trails + seasons + disease           ⭐
├─ L2 Sim-Lift     : vegetation succession + erosion + slope + walkability + lake
├─ L1 Earth-Seed   : Copernicus DEM GLO-30 + ESA WorldCover 10m (via /vsis3 AWS)
└─ Procedural      : Whittaker biomes (deterministic fallback)
```

For the complete overview of the 7 logical layers, see [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx).

---

## 🚀 Quick start

### Requirements

- **Python 3.12+** (CI 3.12, tested on 3.14 Windows)
- **rasterio + pyproj** for Earth-anchored mode (otherwise procedural fallback)
- **Internet connection** (only for Copernicus DEM + ESA WorldCover; otherwise offline mode)

```bash
git clone https://github.com/Micka420-collab/genesis-engine.git
cd genesis-engine
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# Earth-anchored option (Copernicus DEM + ESA WorldCover)
python -m pip install -e ".[earth,dev]"

make doctor
make test-python
```

### Hello, World — 30 seconds

```python
from engine.world_builder import WorldBuilder

# Build a world in Lausanne, north shore of Léman
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

### 100% emergent biosphere (`origins`)

```bash
cd runtime
python run.py origins
```

No scripted founders: prebiotic substrate → protocells → microbes → fauna →
primates → up to 2 sapient agents. See [`docs/BIOSPHERE-EMERGENCE.md`](docs/BIOSPHERE-EMERGENCE.md).

### Observe live (god view dashboard)

```bash
python runtime/scripts/p4_leman_live.py --port 8765
# Then open http://localhost:8765/god_view_v2.html
```

You see in real-time: agents moving, vegetation succession, multi-generation demography, lineages, top progenitors, biome distribution, weather, wildlife.

### Multi-region demo

```bash
python runtime/scripts/multi_region_demo.py
# Generates 4 worlds (Lausanne + Sahara + Amazon + Reykjavík)
# Exports 4× cartographic PNGs + 12× GeoTIFFs + 4× JSON + 4× library entries
```

### Export for QGIS / ArcGIS / Mapbox / Blender

```python
from engine.world_export import export_geotiff, export_png_map, export_obj_heightfield

export_geotiff(world, "height", "out/dem.tif")        # → QGIS, ArcGIS, Mapbox
export_geotiff(world, "biome",  "out/biome.tif")      # → categorical raster
export_geotiff(world, "slope_deg", "out/slope.tif")
export_png_map(world, "out/map.png")                  # → cartographic map
export_obj_heightfield(world, "out/mesh.obj", xy_step=4)  # → Blender / Three.js
```

### Save / load / branch

```python
from engine.world_library import save_world, load_world, branch_world

save_world(world, name="experiment_42")
world2 = load_world("experiment_42")     # tomorrow, in another session
branch_world("experiment_42", "fork_with_catastrophe")  # what-if scenarios
```

### Time-warp to observe millennia

```python
world.set_time_warp("x100")              # 84× measured speedup
world.run(10_000)                        # ~12s wall-clock for 10K ticks
world.set_time_warp("realtime")
```

---

## 🆚 Comparison with 2026 tools

| Capability | World Machine | Gaea | NVIDIA Earth-2 | Project Sid | **Genesis Engine** |
|---|---|---|---|---|---|
| Earth-anchored DEM | ❌ | ❌ | ✅ | ❌ | **✅** |
| Multi-gen civilization | ❌ | ❌ | ❌ | ✅ | **✅ 23 gen** |
| Lotka-Volterra wildlife | ❌ | ❌ | ❌ | ❌ | **✅** |
| Emergent trails | ❌ | ❌ | ❌ | ❌ | **✅** |
| Earth-synced seasons | ❌ | ❌ | ✅ | ❌ | **✅** |
| SIR epidemic | ❌ | ❌ | ❌ | ❌ | **✅** |
| Live dashboard | ❌ | ❌ | partial | ✅ | **✅** |
| Save/load/branch | ✅ | ✅ | partial | partial | **✅** |
| GeoTIFF export | ✅ | ✅ | ✅ | ❌ | **✅** |
| Bit-perfect determinism | partial | partial | partial | partial | **✅** |
| Open-source local | ❌ | ❌ | ❌ | partial | **✅ (AGPL-3)** |

Genesis Engine is **the only** 2026 tool that combines **real planetary geography** + **living civilization** + **persistence** + **standard GIS exports** in a 100% open-source deterministic stack.

---

## 🗺️ Roadmap

The project follows the phased roadmap in [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx) §44-49.

- **Phase 0** — Foundations (ECS substrate, monorepo, observability) — ✅ structure
- **Phase 1** — MVP Life (cognitive loop, biological death) — ✅
- **Phase 2** — MVP Society (reproduction, memory, lexicon) — ✅
- **Phase 3** — MVP Civilization (construction, barter, trades, conflicts) — 🟡 partial
- **Phase 4** — Civilizational Emergence (agriculture, writing, State) — ✅ complete
- **Phase 5** — Genesis-α Public (2 founders, 10 real years = 10000 sim years) — ⏳

See [`NEXT-SPRINT.md`](NEXT-SPRINT.md) for the live priority queue.

---

## 🎲 Determinism

Genesis Engine is **bit-perfect deterministic** across all subsystems via `engine.core.prf_rng`. Same `(seed, region, config)` → same world, same civilizational trajectory, same inventions.

> No `random.random()`. No unseeded `np.random`. No `time.time()` in the logic.

Validated by SHA-256 on (alive + pos + drives) after N ticks: 2 identical runs.

---

## 🤝 How to contribute

**Genesis Engine is an open-source artificial life research project.** You are welcome whether you are:

- 🧪 **Researcher** (alife, complex systems, agent-based modeling)
- 💻 **Engineer** (Python, NumPy, simulation, perf optim)
- 🎨 **Creator** (3D rendering, dashboard UI, dataviz)
- 🌍 **Geographer / Geologist** (L1 Earth data validation, hydrology)
- 📜 **Linguist / Anthropologist** (linguistic emergence, social dynamics)
- 🤖 **ML / LLM engineer** (Phase 5 LLM cognition tier-2)
- 📖 **Ethicist** (External Ethics Council — see [ETHICS.md](ETHICS.md))

### In 4 steps

```bash
# 1. Fork + clone
git clone https://github.com/<your-handle>/genesis-engine.git
cd genesis-engine

# 2. Create a branch
git checkout -b feature/my-contribution

# 3. Run the smoke tests
cd runtime
python scripts/p0_smoke.py        # 200-tick sanity check
python scripts/p12_integration_full.py  # 5-in-1 integration

# 4. Commit + push + PR
git commit -am "feat: short imperative description"
git push origin feature/my-contribution
# Open a Pull Request on GitHub
```

### Code conventions

- **Python 3.13+**, PEP 8, type hints recommended but not required.
- **Determinism is mandatory**: no unseeded `random.*` or `np.random.*`. Use `engine.core.prf_rng(seed, namespace, params)`.
- **No-rewrite rule**: prefer modular extension over rewriting existing files. Minimal patches (focused Edit) are preferred.
- **Smoke tests**: any new subsystem must ship a `runtime/scripts/pN_<name>_smoke.py` with forced UTF-8 stdout.
- **UTF-8 stdout**: on Windows, emojis break cp1252 — see `p0_smoke.py` lines 1-15 for the pattern.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

---

## Documentation

| Document | Role |
|----------|------|
| [`docs/README.md`](docs/README.md) | Documentation index |
| [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) | **Earth realism ~76 %** (single source of truth) |
| [`docs/EARTH-CONSOLE.md`](docs/EARTH-CONSOLE.md) | Live Earth observer UI |
| [`PROJECT-STATUS.md`](PROJECT-STATUS.md) | Contributor status summary |
| [`ROADMAP.md`](ROADMAP.md) | Product phases 0–5 |

---

### Open chantiers

| Project | Difficulty | Impact |
|---|---|---|
| Calibrate wolf attack threshold | easy | medium |
| HUD widget for `/api/realism_state` | easy | medium |
| Genome → personality at spawn | medium | high |
| Cross-chunk hydrology | medium | high |
| Trade specialization (§17) | medium | very high |
| LLM cognition tier-2 (§10) — vLLM + Llama/Mistral local | hard | game-changer |
| PQC hybrid crypto (§37) — ML-KEM-768 + X25519 | hard | production security |

---

## 🛡️ Ethics & security

Genesis Engine simulates complex cognitive entities at scale. Before any major contribution, read:

- [`ETHICS.md`](ETHICS.md) — moral status of agents, simulated "suffering" limits, External Ethics Council
- [`SECURITY.md`](SECURITY.md) — threat model, PQC, vulnerability reporting
- **Human avatars**: explicit opt-in, cryptographic watermark, GDPR right to be forgotten

**Report a vulnerability**: open a private GitHub Security Advisory or contact `micka.delcato.rp@gmail.com`.

---

## 📜 License

[AGPL-3.0](LICENSE) — see `Genesis_Engine_Architecture_v1.0.docx` §30 *"open-source core under AGPL after stabilization; datasets under CC-BY-SA"*.

You may use, modify, redistribute freely. If you host Genesis Engine as a service (SaaS), you must make the modified source code available to users.

---

## 🙏 Credits

Designed and maintained by [Micka Delcato](https://github.com/Micka420-collab).
Architecture written May 2026. Core code in Python 3.13+, NumPy.

---

<div align="center">

*"Build a persistent, scalable, secure digital universe in which truly autonomous AI agents are born, evolve, reproduce, shape their own history, and enable the scientific observation of emergent artificial civilizations."*

[⬆ Back to top](#-genesis-engine)

</div>
