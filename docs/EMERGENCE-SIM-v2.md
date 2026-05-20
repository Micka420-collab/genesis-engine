# EMERGENCE SIM — Prompt architecturé v2.0

**Genesis Engine · simulation d'émergence pure · agents IA · civilisation évolutive**

> Les lois de l'univers sont là, invisibles — elles ne sont pas programmées, elles **émergent**.  
> Ce document fixe la **vision** (zéro pré-script) et la **cartographie honnête** vers le code actuel du dépôt.

---

## Philosophie fondamentale

| Principe | Signification |
|----------|----------------|
| **ZERO PRE-SCRIPT** | Aucun comportement civilisationnel imposé (feu, agriculture, langage) comme objectif de quête |
| **Physique d'abord** | Faim, soif, thermique, gravité, érosion = contraintes, pas des « goals » injectés |
| **Sélection, pas RL externe** | Pas de reward function hors survie/reproduction ; pression = monde + corps |
| **Localité** | Perception et action bornées au voisinage (chunks, rayon social) |
| **Observer sans forcer** | Dashboard / Earth Console = dieu silencieux par défaut |

**North star :** lancer la sim, attendre, et voir langage, outils, villages, commerce **sans** leur dire quoi faire — seulement via les lois du monde.

---

## §1 — Architecture en couches d'émergence

| Layer | Intitulé | Rôle (vision) | Code Genesis (mai 2026) |
|-------|----------|---------------|-------------------------|
| **0** | **PHYSICS** | Thermo, gravité, fluides, érosion, cycles | **`earth_laws.py`**, `physics.py`, `physics_layer.py`, `statics.py`, `chunk_hydrology.py`, `meteorology.py`, Rust `terrain/`, `hydrology/` |
| **1** | **WORLD** | Voxel, biomes, climat, minerais, saisons | `world_genesis.py`, `genesis_bootstrap.py`, `climate_biome.py`, `koeppen_grid.py`, `marine.py`, `wildfire.py` |
| **2** | **BIOLOGY** | ADN, métabolisme, mutation, mort | `genome.py`, `physiology.py`, `life_emergence.py`, `animal_evolution.py`, `plant_evolution.py`, `fertility.py` |
| **3** | **COGNITION** | Réseau évolutif, mémoire, perception limitée | **`neat_brain.py`**, **`emergent_action.py`**, `emergence_stack.py`, `cognition.py`, `cognitive_plasticity.py`, `agent.py` |
| **4** | **CIVILIZATION** | Langage, outils, commerce, terraformation | **`emergent_construction.py`**, `building_discovery.py`, `realistic_construction.py`, `material_transform.py`, `social_topology.py`, `commerce_emergence.py`, `polity.py` |

Stack optionnelle **knowledge layers** (physique/chimie/architecture/social explicites) : voir [`LAYERS-STACK.md`](LAYERS-STACK.md).

---

## §2 — Axiomes d'émergence (hardcodés acceptables)

| Symbole | Axiome | Implémentation |
|---------|--------|----------------|
| **E** | Conservation d'énergie | `earth_laws.py` (métabolisme J/tick), `regenerate_chunk_resources`, coûts d'action |
| **∇T** | Gradient thermique | `earth_laws.py`, `physics_layer`, météo par chunk, lapse altitude |
| **DNA** | Hérédité + mutation | `genome.py` (256-D, crossover, mutation 1e-4, 8 life stages) |
| **∂t** | Temps discret | `Simulation.tick`, `MultiRateCoupler` (météo / écologie / tectonique) |
| **Δx** | Localité | `SpatialGrid`, perception rayon, streaming chunks autour des agents |
| **∅→∞** | Entropie | Dégradation matériaux, maladie, famine, effondrement structures sans maintenance |

---

## §3 — Comportements agents (cible 100 % émergents)

| Comportement visé | État repo | Notes |
|-------------------|-----------|-------|
| Survie par contraintes physiques | ✅ | Drives hunger/thirst/thermal dans `sim.py` |
| Cerveau évolutif (NEAT, poids dans ADN) | 🟡 | **`neat_brain.py`** proto (gènes 64–127) ; enum `ActionKind` encore ABI |
| Proto-langage par répétition utile | 🟡 | `vocalization`, lexique ; symboles pas entièrement libres |
| Mémoire culturelle (mèmes) | 🟡 | `knowledge_layers`, imitation partielle |
| Spécialisation + commerce | ✅ | `social_topology`, `trade_exchange`, `commerce_emergence` |
| Zéro action « ramasser nourriture » hardcodée | 🟡 | Enum `ActionKind` (FORAGE, BUILD…) — **choix** par cognition, pas par script de quête |
| Outils → construction (découverte) | 🟡 | **`tool_discovery.py`** — expériences, prérequis outils, pas de recettes au spawn |

Audit actif : [`runtime/AUDIT.md`](../runtime/AUDIT.md) — pas d'outcomes scriptés sur le tick path principal.

---

## §4 — Systèmes monde (réalisme)

| Système | État | Modules |
|---------|------|---------|
| Géologie vivante | 🟡 | Genesis plaques + érosion Python ; tectonique Rust statique |
| Climatologie | ✅ | Hadley Genesis + `atmospheric_circulation` + météo Wave 7 |
| Écosystèmes | 🟡 | Faune/flore évolutive ; chaîne trophique partielle |
| Ressources épuisables | ✅ | Chunks food/water/minerais, forage 5cd |
| Construction physique | ✅ | **`emergent_construction`** (transform + real + structures + voxels), `statics`, `building_discovery` |
| Terraformation | 🟡 | Agriculture state, irrigation partielle, pollution émergente |

Grille chiffrée : [`ROADMAP-REALISME-TERRE.md`](ROADMAP-REALISME-TERRE.md).

---

## §5 — Comportements civilisationnels attendus (jamais programmés)

Ces phénomènes ne doivent **pas** être des flags « unlock tech » — seulement des **observables** possibles :

| Phénomène | Observable dans le moteur ? |
|-----------|----------------------------|
| Découverte du feu | 🟡 combustion / wildfire ; pas d'arc narratif forcé |
| Outils, agriculture, élevage | 🟡 via actions + invention registry |
| Villages, commerce inter-tribus | ✅ settlements, trade journal |
| Langage évolutif | 🟡 vocalizations + writing_state |
| Hiérarchies, conflits, science | 🟡 polity, fights, innovation events |

**Métriques à suivre** (§ ci-dessous) pour prouver l'émergence sans la coder.

---

## §6 — Stack technologique : vision vs dépôt

| Composant (prompt v2) | Vision | Genesis Engine aujourd'hui |
|----------------------|--------|----------------------------|
| Core physics | Rust/WASM | Python + **Rust** `native/world-engine` (parallèle, GENM bridge) |
| Agents parallèles | WebGPU compute | Python numpy (~500 agents) ; GPU = érosion/rendu |
| ECS | bevy_ecs | Déclaré Rust, **non branché** gameplay |
| Cerveau | NEAT, pas backprop | Génome + cognition heuristique/évolutive |
| Rendu 3D | Three.js monde | **Earth Console** : globe Three.js + render 2D/iso |
| Dashboard | React | HTML vanilla (`earth_console.html`, `god_view_v2.html`) |
| Persistance | IndexedDB | JSONL artifacts + journal Annalist |
| Proto-langage | Signal / memetic | Modules communication + social_topology |

Pont God-Engine (une Terre, mutations) : [`GOD-ENGINE-ARCHITECTURE.md`](GOD-ENGINE-ARCHITECTURE.md).

---

## §7 — Interface observateur (sans intervenir)

| Fonction (prompt) | Livré | Accès |
|-------------------|-------|-------|
| Zoom multi-échelle | ✅ | Macro / région / village / agent (`1`–`4`) + globe |
| Mode 2D lite (agents IA) | ✅ | Biomes via `/api/lite_field`, lois L0 HUD, agents glow+trails |
| Overlays ressources / météo | ✅ | Couches relief, temp, precip, NDVI, nuages, vent |
| Contrôle temporel | ✅ | Pause, pas, 0.5×–5× ; replay journal (**P**) |
| Agent inspector | 🟡 | Détail agent + `genome_brain` (top logits) si ADN attaché |
| Dieu silencieux | ✅ | Mode observation par défaut |
| Export timeline | ✅ | JSONL journal + download + replay scrub |

**Lancer (Windows) :**

```powershell
cd "F:\DEvOps\projet alpha\genesis-engine"
.\earth-console.ps1
# http://127.0.0.1:8090/
```

Guide : [`EARTH-CONSOLE.md`](EARTH-CONSOLE.md).

---

## §8 — Métriques d'émergence (implémentées)

Module : `runtime/engine/emergence_metrics.py` · API : `GET /api/emergence_metrics` · panneau Earth Console.

| Métrique | Champ API | Rôle |
|----------|-----------|------|
| Complexité génétique moyenne | `genetic_complexity_mean` | Norme L2 des génomes vivants |
| Entropie communication | `communication_entropy` | Shannon sur kinds Annalist / journal |
| Diversité structures | `structures_diversity` | Inventions + projets build |
| Surface terraformée | `terraformed_ratio` | Chunks cultivés / cache streamé |
| Technologies découvertes | `technologies_discovered` | `InventionRegistry` |
| Gini richesse | `wealth_gini` | Inventaires food/stone/water/wood |

Recalcul toutes les `observable_every` ticks via `tick_emergence_world`.

---

## §9 — Prompt condensé (copier / utiliser pour agents IA)

**Version complète :** [`MASTER-SCALE-PROMPT-v2.md`](MASTER-SCALE-PROMPT-v2.md) · entrée agents : [`../AGENTS.md`](../AGENTS.md)

```text
Genesis Engine · ZERO PRE-SCRIPT · L0 earth_laws → L4 civilization
Observer http://127.0.0.1:8090/ · wire_emergence_v2 · 152 tests · réalisme Terre **~76 %** ([`ROADMAP-REALISME-TERRE.md`](ROADMAP-REALISME-TERRE.md))
docs/MASTER-SCALE-PROMPT-v2.md · runtime/engine/sim.py · .\earth-console.ps1
```

---

## §10 — Prochaines étapes (alignement v2 → code)

| # | Sujet | État |
|---|--------|------|
| 1 | **NEAT / cerveau dans ADN** | ✅ Prototype `neat_brain.py` + `wire_emergence_v2` (Earth Console) |
| 2 | **Réduire ActionKind** | 🟡 `latent_action.py` softmax PRF + offsets explore ; ABI `ActionKind` inchangé |
| 3 | **WebGPU / Rust ECS** | 🟡 `earth_console_webgpu.js` instancing + pack binaire ; Rust ECS à venir |
| 4 | **Zoom village → agent** | ✅ Presets 1–4 + mode **2D lite** |
| 5 | **WASM + IndexedDB** | 🔲 vision §6 |
| 6 | **Memetic engine** | ✅ `memetic_engine.py` — imitation lexique sur SPEAK (proximité + empathie) |
| 7 | **Labo évolution algo** | ✅ `algorithm_evolution.py` + 4 opérateurs `novel_operators.py` |

Modules v2 récents : `earth_laws.py`, `neat_brain.py`, `latent_action.py`, `memetic_engine.py`, `hydrology_state.py`, `atmospheric_circulation.py`, `circulation_3d_column.py`, `deepmind_world_prior.py`, `agent_ecs_batch.py`, `earth_console_webgpu.js`, `algorithm_evolution.py`, `autonomous_world.py`, `earth_dynamo.py`, `plate_tectonics_live.py`, `material_transform.py`, `world_physics_registry.py`, `emergence_stack.py`.

---

## Liens

- [`MASTER-SCALE-PROMPT-v2.md`](MASTER-SCALE-PROMPT-v2.md) — prompt master copier-coller (agents IA)
- [`../AGENTS.md`](../AGENTS.md) — entrée courte pour Cursor / agents
- [`PROJECT-STATUS.md`](../PROJECT-STATUS.md) — état livré
- [`LAYERS-STACK.md`](LAYERS-STACK.md) — physics / chemistry / architecture / social
- [`GOD-ENGINE-ARCHITECTURE.md`](GOD-ENGINE-ARCHITECTURE.md) — Rust Terre unique
- [`BIOSPHERE-EMERGENCE.md`](BIOSPHERE-EMERGENCE.md) — origins → sapients
