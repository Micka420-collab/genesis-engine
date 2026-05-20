# Earth Console — UI Terre virtuelle

Console unifiée pour **contrôler** la simulation et **voir** le monde Terre (macro Genesis + vue locale agents).

## Lancer

**Windows (sans `make`) :**

```powershell
cd "f:\DEvOps\projet alpha\genesis-engine"
.\earth-console.ps1
```

**Linux / macOS :**

```bash
make earth-console
```

**Équivalent manuel :**

```powershell
cd "f:\DEvOps\projet alpha\genesis-engine"
$env:PYTHONPATH = "runtime"
python runtime\scripts\run_earth_console.py
```

Ouvre **http://127.0.0.1:8090/** dans le navigateur.

## Fonctionnalités

| Zone | Rôle |
|------|------|
| **Vue locale** | Terrain top-down (`/api/render`), pan/zoom, agents en overlay |
| **Globe WebGL** | Sphère Three.js texturée par `/api/macro` — rotation + clic téléport |
| **Vue isométrique** | 2.5D avec chantiers qui grandissent (`/api/render?mode=iso`, tuiles 12×6) |
| **Soleil / ombres** | `GET /api/sun_state` → `earth_console_sun_shadow.js` |
| **Zoom agent** | Sons procéduraux (`earth_console_ambient_audio.js`) + interpolation (`earth_console_agent_anim.js`) |
| **Écoute / langage** | `GET /api/audio` + `GET /api/languages` · bulles + synthèse vocale (`earth_console_speech.js`, touche **E**) |

Raccourcis : **I** iso · **V** vue ciel · **L** 2D · **1–4** zoom · **E** écoute · clic carte = activer le son.
| **2D lite (◎)** | Terrain biomes (`/api/lite_field`), lois L0 HUD, agents glow + flèches de mouvement |
| **Vue du ciel (🛰)** | Humains (posture, peau, outil), chantiers, terraformation (`/api/observer_feed`, **V**) |
| **Terre réaliste** | Palette atlas unifiée, hillshade, hypsométrie (`earth_visual_tokens.py`) |
| **Agents humains** | Posture/démarche/outil via API lite (`agent_presence.py`) |
| **Échelles 1–4** | Macro / région / village / agent (header + clavier) |
| **Cerveau ADN** | `wire_emergence_v2` — policy `neat_brain.py` (gènes 64–127) |
| **Carte macro** | Mini-carte continent — clic pour ancrer la caméra |
| **Timeline** | Sparkline population (footer) — clic pour scrubber l’historique |
| **Replay** | Barre ⏪ : lecture du journal JSONL + événements live (**P** raccourci) |
| **Atmosphère** | Pilules 🌡 ☁ 💨 (météo Wave 7) + voile nuageux sur le globe |
| **SSE** | Bouton « SSE live » → `GET /api/events/stream` (même port que la console) |
| **Agent** | Panneau détail (inventaire, drives) via `/api/agent` |
| **Couches** | Relief, température, précip, NDVI, marin, nuages |
| **Transport** | Pause, pas, vitesses 0.5×–5× |
| **Panneau** | KPIs, liste agents, événements, artifacts post-run |
| **Artifacts** | Import snapshot `.json` ou journal `.jsonl` local |

## API ajoutées

- `GET /api/macro` — PNG carte continentale (Genesis bootstrap)
- `GET /api/macro_meta` — métadonnées (seed, `map_size_km`, `origin_km`)
- `GET /api/journal/events?n=` — fusion journal disque + tail live (replay)
- `GET /api/metrics/history` — séries temporelles Annalist (population, etc.)
- `GET /api/session` — seed, chemin journal, tick courant
- `GET /api/observable` — snapshot agents compact (émergence)
- `GET /api/agents?lite=1` — positions minimales (mode 2D lite)
- `GET /api/lite_field` — raster RGBA léger (biomes / temp / eau)
- `GET /api/earth_laws` — axiomes L0 + métriques live (lapse, entropie, charge)
- `GET /api/emergence_metrics` — KPIs ZERO PRE-SCRIPT
- `GET /api/events/stream` — SSE tick / métriques / météo
- `GET /api/journal/download` — téléchargement du JSONL journal
- `/` → `earth_console.html` (god view legacy : `/god_view_v2.html`)

## Journal par défaut

`run_earth_console.py` écrit les événements dans `artifacts/earth_console.jsonl` (créé automatiquement). Override : `--journal chemin/custom.jsonl`.

## Prérequis

- Python 3.11+ avec `numpy`
- Navigateur moderne (Chrome, Firefox, Edge)
- **Météo Wave 7** : activée automatiquement par `run_earth_console.py` (`install_meteorology`)
- Optionnel — wheel Rust `genesis_world` (chunks alignés GENM, mutations natives) :

```bash
# Rust toolchain requis (rustup)
cd native/world-engine/crates/pybindings
maturin develop --release
# puis relancer make earth-console
```

Sans wheel, la sim tourne en mode Python pur (mock macro + rendu bbox).

## Raccourcis

| Touche | Action |
|--------|--------|
| Espace | Pause / lecture |
| S | Un pas |
| G | Globe WebGL / local |
| I | Isométrique / local |
| L | 2D lite / local |
| 1–4 | Zoom macro → agent |
| P | Replay journal on/off |
| R | Recentrer sur les agents |
| Drag | Pan (local) ou rotation (globe) |
| Molette | Zoom (local) |
| Clic globe | Téléportation |

## Voir aussi

- [`GOD-ENGINE-ARCHITECTURE.md`](GOD-ENGINE-ARCHITECTURE.md)
- [`runtime/README.md`](../runtime/README.md)
