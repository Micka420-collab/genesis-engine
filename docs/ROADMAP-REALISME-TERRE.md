# Roadmap réalisme Terre — Genesis Engine

Estimation honnête du niveau de réalisme **au 19 mai 2026** après la session « objectif 80 % ».

## Grille de maturité (cible utilisateur ~80 %)

| Dimension | % session | Justification | Gap vers 80 % |
|-----------|-----------|---------------|---------------|
| Climat / biomes | **76 %** | Köppen FAIR (checksums), bootstrap Genesis p80, harness 6 stations | Circulation 3D, Beck 2018 |
| Géologie / relief | **55 %** | Tectonique + stratigraphie légère | Érosion GPU dynamique, datation absolue |
| Écologie / hydrologie | **65 %** | Stub par défaut ; **`hydrology_mode`** (`stub` / `sv1d` / `lbm`) dans le tick + preset **`run.py realism`** | Biogeochimie, bassins versants complets |
| Sociétés / agents | **74 %** | R0 réseau ; TRADE avec transfert inventaire (`trade_exchange`) |
| Rendu visuel | **82 %** | Earth Console globe + iso live + couches météo | Volumétrique GPU, humains photoréalistes |
| Observation IA | **86 %** | Earth Console SSE intégré, replay JSONL, observable live | Fog-of-war mmap Rust, multi-tenant |
| Pont Python↔Rust | **82 %** | GENM macro-bridge + mutations write-back + snapshot zstd | WorldGraph hot path prod |

**Global pondéré : ~74 %** (moyenne simple des 7 dimensions, mai 2026 post Earth Console).

> L’objectif **80 % absolu** (simulation « publication-grade » type Terre) n’est pas atteint en une session : il exigerait modèles 3D atmosphère, hydrologie physique complète, et pont Rust en production. La session a **maximisé les gains mesurables** sur chaque axe ; le chemin vers 80 % global est documenté ci-dessous.

---

## Livrables session (19 mai 2026)

| Livrable | Statut | Fichiers |
|----------|--------|----------|
| Köppen grille macro + métriques FAIR | ✅ | `runtime/engine/koeppen_grid.py`, `p75_*` |
| MultiRateCoupler Python → sim | ✅ | `runtime/engine/multi_rate_coupler.py`, `p76_*` |
| Contact graph épidémie | ✅ | `runtime/engine/epidemic_observer.py`, `p77_*` |
| Rendu PBR-lite | ✅ | `runtime/engine/world_render.py`, `p78_*` |
| Vision cone + JSONL | ✅ | `runtime/engine/agent_observation.py`, `p79_*` |
| Pont Rust mock | ✅ | `runtime/engine/rust_bridge.py`, `p73_*` mis à jour |
| Cross-chunk hydrology stub | ✅ | `chunk_hydrology.cross_chunk_flow_stub` |
| Stratigraphie légère | ✅ | `tectonic_geology.stratigraphy_layer_index` |
| Fog altitude amélioré | ✅ | `world_atmosphere.atmospheric_fog_factor` |
| Dashboard vision | ✅ | `runtime/dashboard.html` |
| **Earth Console** (globe, replay, SSE, météo) | ✅ | `earth_console.html`, `run_earth_console.py`, `docs/EARTH-CONSOLE.md` |
| Journal replay + API `/api/journal/events` | ✅ | `dashboard.py`, `annalist.py` |
| Pont Rust GENM + align_heightmap (P0) | ✅ | `macro-bridge`, `macro_grid_export.py` |
| Mutations agent write-back + snapshot (P5) | ✅ | `agent-api/snapshot.rs`, pybindings |

---

## P0 — Fondations (sessions précédentes ✅)

| Livrable | Fichiers |
|----------|----------|
| Harness Köppen–Geiger Rust + Python | `crates/biome/src/koeppen.rs`, `p74_*` |
| MultiRateCoupler + TickDomain Rust | `crates/core/`, `crates/worldgraph/` |
| Snapshots agents | `agent_observation.py` |
| Atmosphère ACES / Rayleigh | `world_atmosphere.py` |

---

## Prochain sprint (vers 80 % global)

1. **CI maturin (bloquant)** : garder **`maturin-pybindings` vert** (wheel + smoke) → base pour monter le pont Rust ~70 %+.
2. **Köppen** : export NetCDF diagnostics ; valider 50 stations (Beck 2018).
3. **WorldGraph** : 1 pass Rust depuis `genesis_bootstrap` (tectonics/ecology).
4. **Hydrologie** : LBM 2D minimal ou D8 accumulation cross-macro.
5. **Observation** : ~~JSONL live~~ ✅ Earth Console + `earth_console_observable.jsonl` ; reste fog mmap Rust.

**Earth Console (recommandé pour le live) :**

```bash
make earth-console
# http://127.0.0.1:8090/ — SSE: GET /api/events/stream
```

---

## P4 livré (journal + observation live)

- Événements sociaux (`trade_transfer`, `trade_link_formed`) → journal Annalist (`kind: trade`).
- `tick_social_topology` appelé depuis `Simulation.step` (plus de wrapper tardif).
- `run.py realism/terre` : `artifacts/<exp>_observe.jsonl` par défaut.
- `observation_server.py --jsonl` : SSE sur la dernière ligne JSONL.
- Commerce : flux macro **2-hop** (3 settlements intermédiaires).
- `make terre` : run court preset Terre.

---

## Commandes de vérification

```bash
# Rust (si cargo disponible)
cd native/world-engine
cargo test -p genesis-core -p genesis-biome -p genesis-worldgraph

# Python (depuis runtime/)
python scripts/p74_koeppen_harness_smoke.py
python scripts/p75_koeppen_grid_smoke.py
python scripts/p76_multi_rate_coupler_smoke.py
python scripts/p77_epidemic_contact_smoke.py
python scripts/p78_pbr_render_smoke.py
python scripts/p79_vision_observation_smoke.py
python scripts/p72_world_atmosphere_smoke.py
python scripts/p73_agent_observation_smoke.py
python scripts/p73_rust_worldgraph_smoke.py

# Pytest
cd runtime && python -m pytest tests/ -q
```

---

## Exemple métriques Köppen (FAIR)

```python
from engine.world_genesis import GenesisParams, generate_world
from engine.koeppen_grid import fair_koeppen_manifest
world = generate_world(GenesisParams(seed=42, resolution=128))
print(fair_koeppen_manifest(world))
```
