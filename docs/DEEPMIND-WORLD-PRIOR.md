# DeepMind-inspired world priors (CPU, ZERO PRE-SCRIPT)

Genesis Engine n’appelle **aucune API DeepMind**. On réutilise des **idées publiées** pour affiner le substrat physique avant que les agents émergent.

## Philosophie

| Principe | Application |
|----------|-------------|
| ZERO PRE-SCRIPT | Les priors modifient vent / relief / colonnes atmo — pas les buts des agents |
| Déterministe | Même seed → même monde (PRF + numpy) |
| Observable | `/api/world_prior`, `/api/circulation_state` (bloc `column_3d`) |

## Modules

### GraphCast-lite (`engine/deepmind_world_prior.py`)

Inspiré de **GraphCast** (Lam et al., 2023) : message-passing sur la grille macro Genesis (`wind_u`, `wind_v`, `temp_c`).

- 2 passes de moyenne voisinage + correction géostrophique légère + masque équatorial ITCZ
- Activé : `SimConfig.graphcast_lite_prior=True` ou `wire_emergence_v2(..., graphcast_lite=True)`
- Earth Console : `python scripts/run_earth_console.py --graphcast-lite`

### NCA terrain (déjà Wave 25)

**Growing Neural Cellular Automata** (Mordvintsev 2020) — poids appris offline (`LEARNED_NCA_CONFIG`). Option : `wire_emergence_v2(..., nca_learned=True)`.

### Circulation 3D colonne (`engine/circulation_3d_column.py`)

Trois niveaux (1 / 5 / 12 km) avec lapse hydrostatique et ω vertical Hadley/Ferrel — branché dans `tick_atmospheric_circulation`.

### Rendu WebGPU agents (`engine/earth_console_webgpu.js`)

Instancing GPU des agents en mode **◎ 2D lite** si le navigateur supporte WebGPU et ≥ 40 agents ; sinon repli Canvas 2D. Données : `/api/agents?packed=1` (24 B/agent).

## Ce qui n’est **pas** inclus (volontairement)

- Genie 3 / Veo (transformers vidéo fermés)
- Appels cloud DeepMind
- Script de civilisation ou quêtes

## Piste 80 %+ réalisme

1. GraphCast-lite + Genesis Hadley → synoptique cohérente  
2. Colonne 3D + sv1d hydrologie → eau + vertical  
3. WebGPU + pack binaire → 500+ agents observables  
4. Rust ECS gameplay (`god-engine`) — prochain pont

## Smoke

```bash
cd runtime && python scripts/p84_earth_console_lite_smoke.py
```

## Références

- GraphCast: https://deepmind.google/discover/blog/graphcast-ai-model-for-weather-forecasting/
- NCA: Mordvintsev et al., 2020 — *Growing Neural Cellular Automata*
- [`EMERGENCE-SIM-v2.md`](EMERGENCE-SIM-v2.md) · [`ROADMAP-REALISME-TERRE.md`](ROADMAP-REALISME-TERRE.md)
