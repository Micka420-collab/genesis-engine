# Wave 37 — Animation Timelapse Export

**Date :** 2026-05-18 (session 34v)
**Module livré :** `engine.animation_timelapse`
**Smoke :** `scripts/p68_animation_timelapse_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Wave 36 livre les snapshots isométriques statiques. Wave 37 ajoute la
**capture multi-frame** + export GIF/PNG → tu peux maintenant
**voir une civilisation évoluer en accéléré** comme un timelapse
documentaire. Pas de scripting de scénario : la sim tourne
normalement (cognition + tous modules émergents), Wave 37 ne fait
que photographier périodiquement.

---

## Architecture

```
capture_timelapse(sim, cfg) :
    if not sim._bootstrapped: sim.bootstrap()
    frame_0 = render(sim) + read-only snapshot  ← état pré-évolution
    for tick in range(n_ticks):
        sim.step()                              ← cognition full
        if (tick+1) % capture_every == 0:
            rgb   = render(sim)
            snap  = read_only_counts(sim)       ← alive, polities, machines, ...
            frame = TimelapseFrame(tick, rgb, snap, sha256)
    return TimelapseHistory(frames, config, ...)

# Renderer pluggable :
#   - défaut iso : Wave 36 render_sim_isometric
#   - défaut top : Wave 27 world_render
#   - custom_renderer : callable(sim) → ndarray
```

Snapshot per-frame (read-only) :
- `n_alive` — agents vivants
- `n_clusters` — DBSCAN-like clusters (settlements émergents)
- `n_polities` — engine.polity Wave 9c
- `n_inventions` — engine.invention
- `n_buildings` — engine.building_discovery
- `n_machines` — engine.machine_emergence Wave 35
- `n_inscriptions` — engine.writing
- `blood_min_l` — engine.anatomy Wave 34
- `signature_hex` — SHA-256 du RGB pour audit déterminisme

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique (`capture_timelapse`, `frames_to_gif`, …) | OK |
| 2 | `capture_timelapse` retourne `1 + n_ticks // capture_every` frames | OK (4/4) |
| 3 | Chaque frame est (H, W, 3) uint8 valide | OK |
| 4 | Ticks monotones + variation signature inter-frames | OK |
| 5 | Métadonnées frame populées (`n_alive`, `signature_hex`, blood_min) | OK |
| 6 | **Déterminisme** : 2 captures même seed → mêmes signatures | OK |
| 7 | `frames_to_gif` écrit GIF lisible par PIL (n_frames ≥ unique-1) | OK |
| 8 | `frames_to_pngs` écrit N PNG sequentiels | OK |
| 9 | `history_to_manifest` produit JSON valide round-trip | OK |

---

## Demo généré (`docs/renders/wave37_timelapse_iso.gif`)

Configuration :
- 12 founders, 3 cultures, R=0.5 km bounds
- 80 ticks total, capture_every=8 → **11 frames**
- Renderer iso (Wave 36) avec `tile_w=16, tile_h=8, z_compress=0.3`
- Anatomy installé pour wounded markers

Trajectoire émergente observée (`clusters_track`) :

```
tick   0:  1 cluster   (founders spawn ensemble)
tick   8:  1 cluster   (encore groupés)
tick  16:  2 clusters  ← scission émergente
tick  24:  3 clusters
tick  32:  4 clusters  ← stabilisation à 4 settlements
tick  40:  4 clusters
tick  48:  4 clusters
tick  56:  4 clusters
tick  64:  4 clusters
tick  72:  4 clusters
tick  80:  4 clusters  (stable)
```

**Aucun script ne dit "place 4 settlements ici"**. Les 4 groupes
émergent des décisions cognition individuelles. C'est le premier
"film documentaire" du moteur Genesis.

Tailles fichiers :
- GIF iso 11 frames : 11.3 MB
- PNG sequence : ~1 MB/frame

---

## API publique

```python
from engine.animation_timelapse import (
    TimelapseConfig,                # n_ticks, capture_every, use_isometric, etc.
    TimelapseFrame,                 # tick, rgb, n_alive, n_machines, …, signature
    TimelapseHistory,

    capture_timelapse,              # sim, cfg → TimelapseHistory
    frames_to_gif,                  # history, path, duration_ms → bool
    frames_to_pngs,                 # history, output_dir → n_written
    history_to_manifest,            # history, path → dict
    timelapse_summary,              # → tracks dict
)
```

### Usage type

```python
from engine.sim import Simulation, SimConfig
from engine.genesis_bootstrap import bootstrap_genesis_sim
from engine.anatomy import install_anatomy
from engine.animation_timelapse import (TimelapseConfig,
                                          capture_timelapse,
                                          frames_to_gif)

sim = Simulation(SimConfig(
    name="evolution_demo", seed=0xCAFE,
    founders=20, max_agents=200,
    bounds_km=(1.5, 1.5), spawn_radius_m=200.0,
    drive_accel=1500.0, cultures=4,
))
bootstrap_genesis_sim(sim)
install_anatomy(sim)
# + install_polity, install_invention, install_writing, ... selon les
# modules émergents qu'on veut observer

cfg = TimelapseConfig(
    n_ticks=2000,           # ~ 1 sim-heure
    capture_every=50,       # 40 frames
    use_isometric=True,     # vue Age of Empires
    gif_duration_ms_per_frame=200,
)

history = capture_timelapse(sim, cfg)
frames_to_gif(history, "evolution.gif")
```

### Custom renderer (par exemple top-down + overlay légende)

```python
def my_render(sim):
    # Renderer custom : utilise Wave 27 + ajoute des annotations.
    ...
    return rgb_arr

cfg = TimelapseConfig(n_ticks=500, capture_every=25,
                        custom_renderer=my_render)
```

---

## Limitations connues

- **Taille GIF iso** : à pleine résolution (R=128 macro), 1 frame iso =
  ~8000 × 4000 px = 100 MB raw. GIF compressé reste lourd (~1 MB/frame).
  Pour des timelapses très longs, descendre `tile_w/tile_h` ou utiliser
  un custom_renderer plus compact.
- **Pas de MP4** : seulement GIF + PNG sequence. Pour MP4, post-process
  avec ffmpeg (out of scope ici, mais facile à wrapper).
- **Capture après chaque step** : `capture_every=1` capture chaque tick
  (très lourd). Default 10 donne un bon compromis.
- **Read-only** : Wave 37 NE MUTATE PAS sim. Si tu veux quantifier
  l'impact d'un événement, run avant/après séparément.
- **Pas de sound** : c'est un sim, pas un film. Pas de bande son.
- **Renderer iso au défaut** : nécessite Wave 36 installé. Sinon
  fallback top-down Wave 27. Sinon fond noir 256×256.

---

## Branchements futurs

| Module | Intégration |
|---|---|
| **Wave 38** | Combat dynamics → animer les batailles inter-polities. |
| Long-run | Lance 100K ticks → GIF de 1000+ frames montrant bronze age. |
| `dashboard` | Animation live pendant la sim (streaming). |
| MP4 export | Wrapper ffmpeg pour HD long-form vidéo. |
| Multi-camera | Plusieurs renderers parallèles : top-down + iso + chunk close-up. |
