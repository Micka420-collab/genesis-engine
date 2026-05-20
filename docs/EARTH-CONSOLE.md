# Earth Console — UI Terre virtuelle

Console unifiée pour **contrôler** la simulation et **voir** le monde Terre (macro Genesis + vue locale agents).

## Lancer

```powershell
cd "f:\DEvOps\projet alpha\genesis-engine\runtime"
python scripts/run_earth_console.py
```

Ouvre **http://127.0.0.1:8090/** dans le navigateur.

## Fonctionnalités

| Zone | Rôle |
|------|------|
| **Vue locale** | Terrain top-down (`/api/render`), pan/zoom, agents en overlay |
| **Globe WebGL** | Sphère Three.js texturée par `/api/macro` — rotation + clic téléport |
| **Vue isométrique** | 2.5D Age-of-Empires (`/api/render?mode=iso`) |
| **Carte macro** | Mini-carte continent — clic pour ancrer la caméra |
| **Timeline** | Sparkline population (footer) |
| **Couches** | Relief, température, précip, NDVI, marin, nuages |
| **Transport** | Pause, pas, vitesses 0.5×–5× |
| **Panneau** | KPIs, liste agents, événements récents |

## API ajoutées

- `GET /api/macro` — PNG carte continentale (Genesis bootstrap)
- `GET /api/macro_meta` — métadonnées (seed, `map_size_km`, `origin_km`)
- `/` → `earth_console.html` (god view legacy : `/god_view_v2.html`)

## Prérequis

- Python 3.11+ avec `numpy`
- Navigateur moderne (Chrome, Firefox, Edge)
- Optionnel : wheel Rust `genesis_world` (`maturin develop` dans `native/world-engine/crates/pybindings`)

## Raccourcis

| Touche | Action |
|--------|--------|
| Espace | Pause / lecture |
| S | Un pas |
| G | Globe WebGL / local |
| I | Isométrique / local |
| R | Recentrer sur les agents |
| Drag | Pan (local) ou rotation (globe) |
| Molette | Zoom (local) |
| Clic globe | Téléportation |

## Voir aussi

- [`GOD-ENGINE-ARCHITECTURE.md`](GOD-ENGINE-ARCHITECTURE.md)
- [`runtime/README.md`](../runtime/README.md)
