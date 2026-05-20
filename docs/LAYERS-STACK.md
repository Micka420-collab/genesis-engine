# Quatre couches de connaissance — Physics · Chemistry · Architecture · Social

Stack optionnelle branchée via `install_knowledge_layers(sim)` ou
`SimConfig.knowledge_layers=True`.

## 1. Physics (gravité réelle, statique, thermo)

| Module | Rôle |
|--------|------|
| `engine/physics.py` | CODATA, mécanique, thermodynamique (conduction, radiation, Gibbs, Arrhenius) |
| `engine/statics.py` | Stabilité voxel : support, compression, porte-à-faux, basculement |
| `engine/physics_layer.py` | Tick : charge pesanteur, thermo chunks (lapse + météo), `check_voxel_structure_stable` |
| `engine/statics_load.py` | Répartition des charges (style Gustave), score de stabilité [0,1] |

**Gravité :** `G_EARTH = 9.81 m/s²`, poids agent = `mass_kg` + inventaire.

**Thermo :** échantillonnage `thermal_conductivity_table` par chunk ; radiatif/conductif pour agents.

**Statique :** toute structure voxel passe `is_structurally_stable` avant commit architecture.

## 2. Chemistry (Materials Project + synthèse)

| Module | Rôle |
|--------|------|
| `engine/chemistry.py` | Tableau périodique, énergies de liaison, alliages |
| `engine/material_synthesis.py` | `synthesize()`, validité physique |
| `engine/materials_project.py` | Bundle JSON + `fetch_from_mp_api` (mp-api) → `STRENGTH_TABLE`, match composition |

**Pipeline :** composition → `check_physical_validity` → `synthesize` → `MaterialRegistry`.

**MP live :** optionnel via `mp-api` + `MP_API_KEY` (futur) ; le bundle offline suffit aux tests.

## 3. Architecture émergente (voxel + statique)

| Module | Rôle |
|--------|------|
| `engine/building_discovery.py` | Placement bloc par bloc, archétypes culturels |
| `engine/architecture_layer.py` | `agent_place_voxel` = statique puis `place_block` |

Pas de recettes HEARTH/HUT imposées : empreinte + toit + stabilité → nom culturel déterministe.

## 4. Social ouverte (topologies arbitraires)

| Module | Rôle |
|--------|------|
| `engine/social_topology.py` | Graphe typé + commerce gravitaire (XTENT) + alliances émergentes |
| `engine/knowledge_wiring.py` | `BUILD` → voxel, `SMELT` → pipeline bronze |
| `NamedTopology` | Sous-graphes nommés (clan, guilde, marché) sans template |

Au-delà de `group_id` dans `sim.py` : relations explicites multi-types, diffusion d'affinité le long des arêtes.

`engine/polity.py` reste la couche proto-État (lois, impôts) — complémentaire, pas remplacée.

## Installation

```python
from engine.sim import Simulation, SimConfig
from engine.knowledge_layers import install_knowledge_layers

sim = Simulation(SimConfig(founders=8, knowledge_layers=True))
install_knowledge_layers(sim)
for _ in range(200):
    sim.step()
print(sim.snapshot().get("knowledge_layers"))
```

CLI :

```bash
python run.py custom --knowledge-layers --founders 8 --ticks 300
```

## Tests

```bash
PYTHONPATH=runtime python -m pytest runtime/tests/test_knowledge_layers.py -q
```

## Réalisme (sources)

- **Statique** : règles Poutre/voûte + répartition multi-appuis (inspiré [Gustave](https://github.com/vsaulue/Gustave), [StableLego](https://arxiv.org/abs/2402.10711))
- **Chimie** : [Materials Project API](https://docs.materialsproject.org/) (`formation_energy_per_atom`, densité)
- **Social** : modèle gravitaire commerce (JASSS inter-settlement trade)

## Wiring Terre (P1)

| Module | Rôle |
|--------|------|
| `engine/trade_exchange.py` | Transferts food/stone/water/wood sur arêtes TRADE |
| `engine/run_report.py` | Enrichissement artifact post-run (journal, observe, stack) |
| `engine/commerce_emergence.py` | Settlements + `trade_flow` → boost liens TRADE + flux 1-hop |
| `engine/full_stack.py` | Post-`Simulation()` : genesis bootstrap, rust WorldGraph, MP API (si clé), 5cd |
| `engine/rust_worldgraph_tick.py` | `observe_chunk` sparse chaque N ticks via `sim_emergence` |
| `runtime/run.py` | Presets **`realism`** et **`terre`** appellent `wire_full_stack` |

**MP live :** `try_fetch_mp_bootstrap(sim)` si `MP_API_KEY` est défini (sinon bundle offline).

```bash
python run.py terre --ticks 500
python run.py realism --no-5cd
python run.py origins --ticks 8000   # émergence seule ; ajouter --realism pour layers+hydro
```

**Origins + realism :** preset **`terre`** ou `python run.py origins --realism`.

## Earth Console (observation live)

| Module | Rôle |
|--------|------|
| `scripts/run_earth_console.py` | Bootstrap Genesis + `wire_full_stack` + météo Wave 7 + serveur HTTP |
| `engine/earth_console.html` | UI : globe WebGL, iso, replay journal, SSE, panneau agent |
| `engine/dashboard.py` | API `/api/journal/*`, `/api/events/stream`, `/api/observable`, render bbox |
| `engine/annalist.py` | Journal JSONL + `_last_batch` pour tail événements |

```bash
make earth-console
# → http://127.0.0.1:8090/
```

Raccourcis : **G** globe · **I** iso · **P** replay · **Espace** pause · **S** pas.

Doc : [`EARTH-CONSOLE.md`](EARTH-CONSOLE.md).

## Ponts futurs

- `ge-substrate` (Rust) ↔ Python physics tick
- FEA léger pour structures > 500 blocs
