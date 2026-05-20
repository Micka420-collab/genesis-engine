# Wave 23 — Neural Cellular Automata Terrain Refinement

**Date :** 2026-05-18 (session 34g)
**Module livré :** `engine.neural_terrain`
**Smoke :** `scripts/p53_neural_terrain_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi : audit des modèles IA de génération de monde (mai 2026)

L'utilisateur a demandé "regarde sur internet les modèles d'IA qui
génèrent des mondes, vois si tu peux implémenter la technologie".
Survey :

| Modèle | Année | Implémentable Genesis ? |
|---|---|---|
| **Genie 3** (DeepMind, autoregressive transformer 11B-param, 720p/24fps real-time) | 2025-08 (paper), 2026-01 (public) | ❌ closed source + GPU farm |
| **TerraFusion** (Latent Diffusion Model joint heightmap+texture) | 2026-05 (arxiv 2505.04050) | ⚠️ requiert PyTorch + GPU + training |
| **Terrain Diffusion** (xandergos, intégré Minecraft) | SIGGRAPH '26 | ⚠️ PyTorch + pretrained weights |
| **InfiniteDiffusion** (open-world terrain) | SIGGRAPH '26 | ⚠️ GPU |
| **Wave Function Collapse** (Gumin) | 2016+ | ✅ pure Python |
| **Neural Cellular Automata** (Mordvintsev 2020, Lenia 2018) | 2020+ | ✅ pure numpy |

**Choix retenu : NCA** parce qu'elle est :

- une vraie technologie de research (Mordvintsev et al. 2020 *Growing
  Neural Cellular Automata*) ;
- déterministe et CPU-friendly (pas de GPU ni de training data
  requis) ;
- alignée sur la philosophie Genesis "rien n'est scripté, tout
  émerge" ;
- composable avec les Waves 16-22 existantes.

---

## Architecture

NCA-inspired refinement post-pass sur `chunk.height` :

```
input  : chunk.height (CHUNK_SIZE x CHUNK_SIZE float32)
output : refined chunk.height + reclassified biome (sea-level crossings)

per iteration (K = 4 default) :
    L  = laplacian(H)              # curvature, 3x3 stencil
    gx = central_diff_x(H)         # gradient x, 3x3
    gy = central_diff_y(H)         # gradient y, 3x3
    S  = sqrt(gx^2 + gy^2)         # slope magnitude
    G  = gaussian_blur(H)          # sediment field, 3x3

    dH = + lambda_curv  * L                       # curvature-driven smoothing
         - lambda_carve * S * sign(H - G)         # slope-proportional carving
         + lambda_diff  * (G - H)                 # sediment redistribution

    H_new = clip(H + dH, H - max_delta, H + max_delta)
    H     = where(initially_abyssal, H_init, H_new)   # freeze abyss
```

Ces trois dynamiques en compétition (smoothing convexités + carving
slopes raides + diffusion sédiments) imitent les processus d'érosion
réels à l'échelle du chunk (32 m).

### Pourquoi "Neural" ?

L'architecture est strictement celle d'un NCA :

- **state vector per cell** : implicite (juste `height` pour l'instant).
- **3×3 stencils** : laplacien + gradients + gaussien.
- **update rule** : combinaison linéaire des features extraites.
- **iterated K times** : 4 itérations par défaut.

Les "poids" sont **hand-tuned** à partir de priors physiques plutôt
que learned par gradient descent. C'est la même architecture — on
pourrait remplacer les coefficients par des poids appris sans
toucher au code d'inférence. Cela garde le module CPU-only, déterministe
sans embedded weights file.

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique (`NeuralTerrainConfig`, `refine_*`, `install_*`, ...) | OK |
| 2 | Déterminisme pure-function : deux appels identiques → `max_diff=0.000000` | OK |
| 3 | Refinement modifie le chunk : `mean|dH|=0.118m max|dH|=1.336m` | OK |
| 4 | Drift mean elev borné : `drift=0.07m (0.01%)` | OK |
| 5 | Cellules abyssales gelées par la NCA | OK |
| 6 | Install idempotent | OK |
| 7 | Streamer wrap déclenche `refine_chunk_elevation` sur cache miss | OK (4 iters/chunk) |
| 8 | `apply_to_existing_chunks` retro-refine tous les chunks cachés (106/106) | OK |
| 9 | `uninstall_neural_terrain` restaure streamer.get + supprime hooks | OK |

---

## API publique

```python
from engine.neural_terrain import (
    NeuralTerrainConfig,            # tuning hyperparams
    NeuralTerrainState,
    refine_chunk_elevation,         # pure function : chunk, cfg -> n_iters
    install_neural_terrain,         # idempotent installer
    apply_to_existing_chunks,       # rescue cached chunks
    neural_terrain_state,           # reporter dict
    uninstall_neural_terrain,
)
```

### Paramétrage

```python
cfg = NeuralTerrainConfig(
    iterations=4,
    lambda_curvature=0.12,   # smoothing strength (concavities accrete)
    lambda_carve=0.015,      # slope-driven erosion
    lambda_diffuse=0.10,     # gaussian sediment redistribution
    sea_level_m=0.0,
    max_delta_m=25.0,        # hard cap per iter to prevent runaway
    reclassify_biomes=True,  # flip OCEAN if cells get submerged by NCA
)

install_neural_terrain(sim, cfg)
```

### Usage type intégré au pipeline complet (Waves 16-23)

```python
from engine.genesis_bootstrap import bootstrap_genesis_sim
from engine.neural_terrain import install_neural_terrain, NeuralTerrainConfig

state = bootstrap_genesis_sim(sim, seed=0xCAFE)         # Wave 16-22
install_neural_terrain(sim, NeuralTerrainConfig(iterations=6))  # Wave 23
```

---

## Limitations connues

- **Hand-tuned weights, no learning** : la qualité des détails dépend
  des coefficients choisis. Une future Wave pourrait entraîner les
  poids sur des DEMs réels (offline) et les embedder comme `.npy`.
- **Single-channel state** : pour l'instant on n'opère que sur
  `chunk.height`. Le vrai NCA Mordvintsev a un state vector ~16D par
  cellule. À étendre si besoin.
- **No biome co-evolution** : Wave 23 reclassifie les biomes OCEAN/non
  uniquement aux passages de niveau de mer. Une vraie NCA biome-aware
  re-classifierait les biomes en fonction de la nouvelle élévation +
  flow accumulation chunk-level.
- **CPU cost** : ~4 iters × 4 stencils × CHUNK_SIZE² = ~65k ops par
  chunk par tick de génération. Acceptable car la NCA tourne *une fois*
  à la génération, pas par tick simulation. Pour 1000 chunks : ~0.5 s
  total au démarrage.

---

## Branchements futurs

| Module | Intégration |
|---|---|
| `geology.py` | Faire émerger des veines orientées par le gradient post-NCA. |
| `chunk_hydrology.py` | Recouper les rivières post-NCA pour qu'elles suivent les vallées affûtées. |
| `dashboard.py` | Visualisation hillshade pour rendre visible le gain de détail. |
| **Wave 24** | Entraîner les poids NCA sur DEMs réels (Copernicus, SRTM) et embedder le checkpoint. Vraie IA learned. |
| **Wave 25** | NCA multi-channel : ajouter `slope`, `flow`, `biome_logits` au state vector — plus proche de l'architecture Mordvintsev originale. |
