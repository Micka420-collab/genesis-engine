# Roadmap réalisme Terre — Genesis Engine

**Source de vérité** pour tous les pourcentages « réalisme Terre » du dépôt.  
**Dernière mise à jour :** 19 mai 2026 (post Earth Console : écoute, iso chantiers, monde autonome).

---

## Score global officiel : **~76 %**

| Ce que vous voyiez ailleurs | Signification correcte |
|-----------------------------|------------------------|
| **~68 %** ou **~74 %** | Anciennes estimations ou moyennes partielles — **à ne plus utiliser** |
| **~80 %** | **Objectif cible** utilisateur, ou score **climat / biomes** seul — **pas** le global |
| **~76 %** | **Moyenne des 7 dimensions** ci-dessous (référence unique) |

**Recalcul transparent :**  
(80 + 55 + 68 + 76 + 82 + 86 + 82) ÷ 7 = **75,6 %** → arrondi **~76 %**.

> L’objectif **80 % global** (simulation « publication-grade ») reste une **cible** : il faudrait NWP 3D, hydrologie bassin complet, géologie dynamique GPU, et WorldGraph Rust en hot path production.

---

## Grille de maturité (7 dimensions)

| Dimension | % | Justification | Gap vers 80 % |
|-----------|---|---------------|---------------|
| Climat / biomes | **80** | Circulation L1 + colonne 3D + GraphCast-lite prior + vent 2D | NWP 3D numérique, validation Beck 2018 |
| Géologie / relief | **55** | Tectonique live + stratigraphie légère | Érosion GPU dynamique, datation absolue |
| Écologie / hydrologie | **68** | Earth Console `sv1d` + overlay flux 2D ; cross-chunk près des agents | Biogeochimie, bassins versants complets |
| Sociétés / agents | **76** | NEAT + latent_action ; memetic + lexique ; construction émergente ; parole `/api/audio` | `ActionKind` encore enum ; pas de LLM tier-2 |
| Rendu visuel | **82** | Earth Console globe + iso 2.5D + humains + ombres soleil + 2D lite | Volumétrique GPU, photoréalisme |
| Observation IA | **86** | Earth Console SSE + replay JSONL + observer_feed + WebGPU agents | Fog-of-war mmap Rust, multi-tenant |
| Pont Python↔Rust | **82** | GENM macro-bridge + mutations write-back + snapshot zstd | WorldGraph hot path prod |

**Moyenne (global) :** **~76 %**

### Deux moteurs (ne pas confondre avec le global)

| Stack | % | Note |
|-------|---|------|
| **Continent Python** (Genesis, climat, civ, Earth Console) | **~76** | Aligné sur la moyenne globale ci-dessus |
| **Pont Rust** (GENM, agent-api, Köppen crates) | **82** | Dimension « Pont » — pas le score monde entier |
| **Chunk procgen Rust seul** (sans align Genesis) | **~45** | Intégration partielle — voir [`GOD-ENGINE-ARCHITECTURE.md`](GOD-ENGINE-ARCHITECTURE.md) |

---

## Livrables récents (mai 2026)

| Livrable | Statut | Fichiers |
|----------|--------|----------|
| Earth Console (globe, iso, sky, écoute) | ✅ | `earth_console.html`, `run_earth_console.py`, `docs/EARTH-CONSOLE.md` |
| Monde autonome (dynamo, plaques, construction émergente) | ✅ | `autonomous_world.py`, `emergent_construction.py` |
| Parole agents → SoundField | ✅ | `speech_audio_bridge.py`, `/api/audio`, `/api/languages` |
| GraphCast-lite + prior monde | ✅ | `deepmind_world_prior.py` |
| Köppen FAIR + MultiRateCoupler | ✅ | `koeppen_grid.py`, `multi_rate_coupler.py` |
| Pont Rust GENM + write-back | ✅ | `macro-bridge`, `macro_grid_export.py` |

---

## Prochain sprint (vers 80 % global)

1. **CI maturin** : wheel + smoke verts → monter WorldGraph en prod.
2. **Köppen** : validation 50 stations (Beck 2018).
3. **Hydrologie** : LBM 2D ou D8 accumulation cross-macro.
4. **Géologie** : érosion GPU + datation relative.
5. **Observation** : fog mmap Rust ; reste JSONL live ✅.

**Earth Console (live) :**

```bash
make earth-console
# http://127.0.0.1:8090/ — SSE: GET /api/events/stream
```

---

## Commandes de vérification

```bash
# Python (depuis runtime/)
python -m pytest tests/ -q          # 133 tests (mai 2026)
python scripts/p74_koeppen_harness_smoke.py
python scripts/p86_autonomous_world_smoke.py
python scripts/p87_observer_sky_smoke.py

# Rust (si cargo disponible)
cd native/world-engine
cargo test -p genesis-core -p genesis-biome -p genesis-worldgraph
```

---

## Exemple métriques Köppen (FAIR)

```python
from engine.world_genesis import GenesisParams, generate_world
from engine.koeppen_grid import fair_koeppen_manifest
world = generate_world(GenesisParams(seed=42, resolution=128))
print(fair_koeppen_manifest(world))
```

---

## Références

- Synthèse projet : [`PROJECT-STATUS.md`](../PROJECT-STATUS.md)
- Manifeste : [`EMERGENCE-SIM-v2.md`](EMERGENCE-SIM-v2.md)
- Console : [`EARTH-CONSOLE.md`](EARTH-CONSOLE.md)
- README multilingues (même score **~76 %**) : [`README.md`](../README.md), [`README.en.md`](../README.en.md), [`README.es.md`](../README.es.md), [`README.zh-CN.md`](../README.zh-CN.md), [`README.ar.md`](../README.ar.md)
