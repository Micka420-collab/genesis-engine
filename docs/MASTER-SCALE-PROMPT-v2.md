# Genesis Engine — MASTER SCALE PROMPT v2.0

**Simulation d'émergence pure · civilisation IA · mai 2026**

> Copier ce bloc pour onboarder un agent IA ou un contributeur.  
> Manifeste détaillé : [`EMERGENCE-SIM-v2.md`](EMERGENCE-SIM-v2.md) · Grille % : [`ROADMAP-REALISME-TERRE.md`](ROADMAP-REALISME-TERRE.md)

---

## Identité du projet

| Clé | Valeur |
|-----|--------|
| **Nom** | Genesis Engine |
| **Racine** | `F:\DEvOps\projet alpha\genesis-engine` |
| **Runtime** | `runtime/` |
| **Console** | http://127.0.0.1:8090/ — `.\earth-console.ps1` |
| **Tests** | `cd runtime && python -m pytest tests/ -q` → **96 tests OK** |
| **Score global** | **~76 %** (objectif 80 %) |

---

## Philosophie — ZERO PRE-SCRIPT (immuable)

Rien n'est pré-scripté. Seules les **lois physiques de base** existent.  
Vie, intelligence, langage, outils, civilisation, terraformation doivent **émerger seuls** — comme les lois de l'univers sont là, invisibles, et ce sont les agents qui les découvrent.

| Statut | Règle |
|--------|--------|
| ✅ **Autorisé** | Lois physiques (E, ∇T, DNA, ∂t, Δx, entropie) |
| 🚫 **Interdit** | Comportements pré-définis, arbre tech forcé, dialogue hardcodé, objectif global injecté, actions « ramasser nourriture » scriptées |

---

## Architecture couches (L0 → L4)

### L0 PHYSICS — seule couche immuable

| | |
|--|--|
| **Fichiers** | `earth_laws.py`, `physics.py`, `physics_layer.py`, `statics.py`, `chunk_hydrology.py`, `meteorology.py` |
| **Axiomes** | E (énergie) · ∇T (thermo) · DNA · ∂t · Δx · entropie |
| **API** | `GET /api/earth_laws` → lapse, T, charge, entropie live |

### L1 WORLD

| | |
|--|--|
| **Fichiers** | `world_genesis.py`, `genesis_bootstrap.py`, `climate_biome.py`, `koeppen_grid.py`, `marine.py`, `wildfire.py`, `realism.py` |
| **Systèmes** | Hydrology (D8 intra-chunk ; cross-chunk stub/sv1d/lbm via `sim_emergence`), wildlife (Lotka-Volterra), trails, seasons (`SeasonalClock`), disease (SIR) |
| **API** | `GET /api/lite_field` → raster RGBA biomes (mode 2D lite) |

### L2 BIOLOGY

| | |
|--|--|
| **Fichiers** | `genome.py` (256-D, crossover, mutation 1e-4, 8 stages), `physiology.py`, `life_emergence.py`, `animal_evolution.py`, `plant_evolution.py`, `fertility.py` |
| **Drives** | hunger, thirst, thermal — **contraintes physiques**, pas des « goals » |

### L3 COGNITION — cœur du scaling agent

| | |
|--|--|
| **Fichiers** | `neat_brain.py` (NEAT-inspired, poids = gènes 64–127), `emergent_action.py` (`genome_decide`, pas heuristique), `emergence_stack.py` (`wire_emergence_v2`), `agent_batch.py` (scale hot path) |
| **Config** | `SimConfig.emergent_cognition = True` (activé Earth Console) |
| **Gap** | NEAT complet + espace d'actions continu (hors enum `ActionKind` fixe) |

### L4 CIVILIZATION

| | |
|--|--|
| **Fichiers** | `building_discovery.py`, `social_topology.py`, `commerce_emergence.py`, `polity.py`, `writing_state`, `agriculture_state`, `vocalization` |
| **État** | commerce ✅ · langage 🟡 · terraformation 🟡 |

---

## Modules récents (v2 — mai 2026)

| Module | Rôle |
|--------|------|
| `earth_laws.py` | Axiomes L0 + `/api/lite_field` (overlay flux) |
| `neat_brain.py` | Politique MLP poids-génome (gènes 64–127) |
| `latent_action.py` | Softmax PRF + offsets explore continus |
| `memetic_engine.py` | Imitation lexique sur SPEAK |
| `hydrology_state.py` | `GET /api/hydrology_state` |
| `emergent_action.py` | Remplace `decide()` heuristique |
| `emergence_stack.py` | `wire_emergence_v2` + sv1d + memetic |
| `agent_batch.py` | Snapshot lite hot path |
| `koeppen_grid.py` | Köppen FAIR multi-stations |
| `realism.py` | Reality Engine (5 subsystems opt-in) |

---

## Interface observateur

| Fonction | Accès |
|----------|--------|
| **Mode 2D lite** | Touche **L** ou bouton **◎** → terrain biomes + agents glow |
| **Zoom** | **1** Macro · **2** Région · **3** Village · **4** Agent |
| **Overlays 2D** | Biomes / Temp / Eau (chips gauche) |
| **HUD L0** | lapse · T · charge · entropie (bas-gauche) |
| **Inspector** | Clic agent → ADN + `genome_brain` top logits + drives |
| **Temporel** | Pause · ×0.5 · ×1 · ×2 · ×5 · Replay (**P**) |
| **SSE** | `GET /api/events/stream` |
| **Émergence** | `GET /api/emergence_metrics` → `genetic_complexity_mean`, `communication_entropy`, `technologies_discovered`, `wealth_gini`, `terraformed_ratio`, `structures_diversity` |

---

## Commandes de base

```powershell
cd "F:\DEvOps\projet alpha\genesis-engine"
.\earth-console.ps1
```

```bash
cd runtime && python -m pytest tests/ -q    # 93 tests
cd runtime && python run.py realism          # preset Terre
make earth-console                           # alt Makefile
```

---

## État actuel honnête (74 % global)

| % | Dimension | Notes |
|---|-----------|-------|
| ✅ 82% | Rendu visuel | Earth Console globe + iso + 2D lite |
| ✅ 86% | Observation IA | SSE, replay JSONL, observable |
| ✅ 82% | Pont Python↔Rust | GENM bridge + mutations write-back |
| 🟡 80% | Climat / biomes | GraphCast-lite + colonne 3D + circulation L1 ; NWP 3D manquante |
| 🟡 74% | Sociétés / agents | NEAT proto ; `ActionKind` encore enum |
| 🟡 65% | Écologie / hydrologie | D8 intra-chunk ; cross-chunk stub/sv1d/lbm partiel |
| 🔲 55% | Géologie / relief | Érosion GPU manquante |

---

## Contraintes de code

1. Ne jamais ajouter de « goals » narratifs dans le tick path.
2. Vérifier [`runtime/AUDIT.md`](../runtime/AUDIT.md) avant tout ajout comportemental.
3. Chaque nouveau comportement → observable dans `emergence_metrics`.
4. Déterminisme bit-perfect : `prf_rng` partout, SHA-256 A==B.
5. **93 tests pytest** doivent rester verts après toute modification.
6. API REST existante : ne pas casser les endpoints `/api/*`.

---

## Référence fichiers clés

| Fichier | Rôle |
|---------|------|
| `runtime/engine/sim.py` | Simulation principale |
| `runtime/engine/earth_laws.py` | Axiomes L0 |
| `runtime/engine/neat_brain.py` | Cognition génomique |
| `runtime/engine/emergence_metrics.py` | KPIs ZERO PRE-SCRIPT |
| `runtime/engine/agent_batch.py` | Scale hot path |
| `runtime/engine/realism.py` | Reality Engine (5 subsystems) |
| `runtime/scripts/run_earth_console.py` | Entrypoint console |
| `runtime/engine/earth_console.html` | UI observateur |
| `docs/EMERGENCE-SIM-v2.md` | Manifeste v2 |
| `docs/GOD-ENGINE-ARCHITECTURE.md` | Rust Terre unique |
| `docs/ROADMAP-REALISME-TERRE.md` | Grille maturité |

---

## Prompt condensé (une ligne)

```text
Genesis Engine · ZERO PRE-SCRIPT · L0 earth_laws → L4 civilization · observer http://127.0.0.1:8090/ · wire_emergence_v2 · 93 tests · 74% realism
```
