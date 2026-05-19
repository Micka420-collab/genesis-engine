# Genesis Engine — Runtime Python

Implémentation opérationnelle de la simulation : agents autonomes, monde, civilisation, rendu et observateurs. C’est le **cœur exécutable** du dépôt ; le moteur Rust (`../native/world-engine/`) s’y branche progressivement via `rust_bridge` et PyO3.

**Vue d’ensemble repo** : [`../README.md`](../README.md) · **Contribuer** : [`../CONTRIBUTING.md`](../CONTRIBUTING.md)

---

## Rôle

- Boucle de simulation déterministe (`engine/sim.py`, `cognition.py`, `agent.py`)
- **Biosphère émergente** : substrat → protocellules → microbes → faune → sapients
  (`appraise.py`, `protocell_evolution.py`, `life_emergence.py`) — voir
  [`../docs/BIOSPHERE-EMERGENCE.md`](../docs/BIOSPHERE-EMERGENCE.md)
- Génération de monde L1/L2 (Earth, géologie, hydrologie, climat, biomes)
- Émergence civilisationnelle (agriculture, métallurgie, polity, routes, commerce…) — **dans le tick**, pas via jobs externes
- Monde réaliste Waves 16–41 (`world_genesis`, hydrologie, Köppen, observateurs) branchés via `sim_emergence.py` + `sim.step()`
- Smokes de non-régression `scripts/p*.py`
- Dashboard HTTP et exports GIS

---

## Layout

```
runtime/
├── engine/           # Package principal (import: from engine.xxx)
│   ├── sim.py        # Tick loop
│   ├── agent.py      # Registre agents, ActionKind
│   ├── cognition.py  # Perception → appraise → décision
│   ├── appraise.py   # Viabilité monde / reproduction
│   ├── life_emergence.py      # Pipeline biosphère + civilisation
│   ├── protocell_evolution.py
│   ├── biosphere_stack.py
│   ├── world*.py     # Monde procédural / genesis / render / atmosphere
│   ├── *_observer.py # Épidémie, lignée, vision agent
│   └── dashboard.py  # Serveur HTTP god-view
├── scripts/          # Smokes p0–p79, démos (p4 live, multi_region_demo)
├── tests/            # pytest (config: ../pyproject.toml)
├── experiments/      # exp1–4 + stress (science reproductible)
├── journals/         # JSONL événements par smoke/expérience
├── artifacts/        # Résumés métriques JSON
├── configs/          # YAML partagés avec scaffolding
├── dashboard.html    # UI complémentaire (vision cones, etc.)
└── README_OPERATIONAL.md  # Notes ops détaillées (legacy)
```

---

## PYTHONPATH et installation

Le package est installé depuis la racine :

```bash
cd ..   # racine genesis-engine
python -m pip install -e ".[dev]"
```

Les imports utilisent `from engine.xxx` — **pas** `from runtime.engine`. En ligne de commande sans install :

```bash
# Depuis la racine
make smoke
# ou
PYTHONPATH=runtime python runtime/scripts/p0_smoke.py
```

Windows PowerShell : `$env:PYTHONPATH = "runtime"`

---

## Premier jour (runtime)

```bash
# 1. Environnement (à la racine du repo)
python -m venv .venv && .venv\Scripts\activate   # adapter selon OS
pip install -e ".[dev]"

# 2. Sanity
make doctor
make smoke

# 3. Tests unitaires
make test-python
# ou: PYTHONPATH=runtime python -m pytest runtime/tests -q

# 4. Smoke d’un sous-système récent
cd runtime
python scripts/p72_world_atmosphere_smoke.py
```

---

## Smoke tests

Convention : `scripts/pN_<nom>_smoke.py` — exit 0 = PASS, UTF-8 stdout forcé en tête de fichier (Windows).

| Plage | Domaine |
|-------|---------|
| p0, p12 | Baseline + intégration multi-subsystems |
| p44+ | World genesis, tectonique, climat, NCA, rendu |
| p70–p71 | Observateurs épidémie, lignée |
| **p72** | Atmosphère temporelle (jour/nuit/saisons) |
| **p73** | Observation agents + WorldGraph Rust (mock/natif) |
| **p74–p75** | Köppen harness + grille macro |
| **p76** | Multi-rate coupler |
| **p77** | Contact graph épidémie |
| **p78** | Rendu PBR-lite |
| **p79** | Vision cone + JSONL |
| **p80** | Köppen sur monde Genesis bootstrap + manifeste FAIR |
| **p81** | Hydrologie cross-chunk (Saint-Venant + LBM D2Q9) |
| **p82** | Pipeline civilisation (`civilization_pipeline.py`) + SSE observation |

Le **multi-rate coupler**, l’observateur épidémie, Köppen et l’état observable
live sont installés dans `Simulation.__init__` quand `emergence_subsystems=True`
(voir `engine/sim_emergence.py`). `run.py` et les expériences n’orchestrent plus
ces sous-systèmes à part.

```bash
cd runtime
python scripts/p0_smoke.py
python scripts/p12_integration_full.py
```

### Expérience « origins » (100 % émergent)

Aucun fondateur injecté : la vie monte la chaîne biologique avant les humains.

```bash
cd runtime
python run.py origins
# équivalent :
python run.py custom --emergent-origins --ticks 8000 --bounds-km 2.0 --drive-accel 12000
```

Options : `--full-biosphere`, `--emergent-origins`. Métriques : `life_emergence` dans le snapshot JSON.

### Pipeline civilisation (émergence)

Depuis la racine du dépôt :

```bash
make civilization
# ou
PYTHONPATH=runtime python runtime/scripts/civilization_pipeline.py \
  --seed 0xC1A71CE0 --ticks 200 --founders 12
```

Produit sous `runtime/artifacts/` :

| Fichier | Contenu |
|---------|---------|
| `civilization_run_manifest.json` | Seed, ticks, modules Genesis, chemins artifacts |
| `observable.json` | Snapshot agents + méta `genesis_bootstrap` |
| `koeppen_fair.json` | Köppen + checksums SHA-256 du **monde simulé** |
| `epidemic_contact.json` | SIR + R0 réseau vs SIR populationnel |

Observation live : `make observe` (ouvre `dashboard.html` + SSE sur le port 8765).

Inventaire partiel : [`../TESTS_INVENTORY.md`](../TESTS_INVENTORY.md).

---

## Dashboard

```python
from engine.sim import Simulation, SimConfig
from engine.dashboard import start_server

sim = Simulation(SimConfig(founders=50, max_agents=300))
start_server(sim, port=8080)
# Boucle: sim.step()
```

Ouvrir `http://localhost:8080/` — biomes, cultures, heatmaps, inspecteur agent.  
Fichier statique complémentaire : [`dashboard.html`](dashboard.html) — panneau
**Epidemic** si `summary.json` contient `epidemic`, bouton **Connect SSE** pour
rafraîchissement auto.

Serveur SSE léger (artifacts ou `observable.json`) :

```bash
PYTHONPATH=runtime python scripts/observation_server.py \
  --artifacts artifacts/exp4_catastrophe.json --port 8765
```

Démo live Léman : `python scripts/p4_leman_live.py --port 8765`

---

## Expériences scientifiques

```bash
cd experiments
python exp1_scarcity.py
python exp4_catastrophe.py
python stress_100.py
```

Journaux : `journals/<nom>.jsonl` — schéma événements `birth`, `death`, `founding`,
`conflict`, `mating`, `innovation` (protocellules / microbes), etc.

---

## Déterminisme

Tout aléatoire passe par `engine.core.prf_rng(seed, namespace, params)`.  
Ne jamais utiliser `random` ou `numpy.random` non seedé dans la logique de sim.

---

## Où coder quoi (runtime)

| Tu veux… | Fichiers typiques |
|----------|-------------------|
| Comportement agent | `cognition.py`, `agent.py`, `sim.py` |
| Biosphère émergente | `life_emergence.py`, `appraise.py`, `protocell_evolution.py`, `biosphere_stack.py` |
| Monde / terrain | `world.py`, `world_genesis.py`, `tectonic_geology.py`, `chunk_hydrology.py` |
| Climat / biomes | `macro_climate.py`, `climate_biome.py`, `koeppen_grid.py` |
| Civilisation | `agriculture.py`, `metallurgy.py`, `polity.py`, modules trade/roads |
| Rendu | `world_render.py`, `world_atmosphere.py`, `isometric_render.py` |
| Observateurs IA | `*_observer.py`, `agent_observation.py` |
| Pont Rust | `rust_bridge.py` + `genesis_world` (maturin) + `p73` |
| Observation SSE | `scripts/observation_server.py` + `p82` |

### Pont Rust (`genesis_world`)

```bash
pip install maturin
cd native/world-engine
maturin develop -m crates/pybindings/Cargo.toml --release
PYTHONPATH=runtime python runtime/scripts/p73_rust_worldgraph_smoke.py
```

Sans wheel natif : `rust_bridge.MockPyWorld` (déterministe) sert de **repli CI**
pour p73 — ce n’est pas la source de vérité du runtime Python ; la sim vit dans
`engine/sim.py` + `sim.step()`.
| Nouveau subsystem | module dans `engine/` + `scripts/pN_*_smoke.py` |

Pour le **moteur monde bas niveau** (chunks, WorldGraph, GPU) → [`../native/world-engine/README.md`](../native/world-engine/README.md).

---

## Performance (ordre de grandeur)

| Expérience | Agents (pic) | TPS ~ |
|------------|-------------|-------|
| exp1 | 49 | 25 |
| stress_100 | 255 | 4 |

Optimisations futures : index spatial, Rust hot path, parallélisme ECS.

---

## Voir aussi

- [`README_OPERATIONAL.md`](README_OPERATIONAL.md) — détail ops historique
- [`../docs/ROADMAP-REALISME-TERRE.md`](../docs/ROADMAP-REALISME-TERRE.md) — métriques réalisme
- [`../PROJECT-STATUS.md`](../PROJECT-STATUS.md) — statut global
