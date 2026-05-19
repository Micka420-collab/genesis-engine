# Quatre couches de connaissance — Physics · Chemistry · Architecture · Social

Stack optionnelle branchée via `install_knowledge_layers(sim)` ou
`SimConfig.knowledge_layers=True`.

## 1. Physics (gravité réelle, statique, thermo)

| Module | Rôle |
|--------|------|
| `engine/physics.py` | CODATA, mécanique, thermodynamique (conduction, radiation, Gibbs, Arrhenius) |
| `engine/statics.py` | Stabilité voxel : support, compression, porte-à-faux, basculement |
| `engine/physics_layer.py` | Tick : charge pesanteur agents, conductivité chunks, `check_voxel_structure_stable` |

**Gravité :** `G_EARTH = 9.81 m/s²`, poids agent = `mass_kg` + inventaire.

**Thermo :** échantillonnage `thermal_conductivity_table` par chunk ; radiatif/conductif pour agents.

**Statique :** toute structure voxel passe `is_structurally_stable` avant commit architecture.

## 2. Chemistry (Materials Project + synthèse)

| Module | Rôle |
|--------|------|
| `engine/chemistry.py` | Tableau périodique, énergies de liaison, alliages |
| `engine/material_synthesis.py` | `synthesize()`, validité physique |
| `engine/materials_project.py` | Ingestion JSON (`runtime/data/materials_project_bundle.json`) → `STRENGTH_TABLE` |

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
| `engine/social_topology.py` | Graphe d'arêtes typées (`KIN`, `ALLIANCE`, `TRADE`, `FEUD`, …) |
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

## Ponts futurs

- `ge-substrate` (Rust) ↔ Python physics tick
- MP REST ingestion batch
- Cognition `BUILD` → `agent_place_voxel` automatique
