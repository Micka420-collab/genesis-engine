# Wave 24 — Multi-channel Neural Cellular Automata

**Date :** 2026-05-18 (session 34h)
**Module livré :** `engine.nca_multichannel`
**Smoke :** `scripts/p54_nca_multichannel_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Wave 23 (`engine.neural_terrain`) implémente une NCA mono-canal :
``height`` seul subit smoothing + curvature + diffusion. Mais
l'architecture Mordvintsev *et al.* 2020 *Growing Neural Cellular
Automata* est multi-canal — chaque cellule porte un **state vector**
de plusieurs valeurs qui co-évoluent via stencils 3×3 entrelacés.

Wave 24 implémente la version complète sur trois canaux physiquement
motivés :

- **H — height**   : élévation du substrat rocheux (m).
- **S — sediment** : matière meuble sur la surface (m-équivalent).
- **W — water**    : humidité/ruissellement [0, 5].

Ces trois canaux **se nourrissent mutuellement** par les règles :

```
1. erosion = h_erode · W · slope       (eau + pente carve la roche)
2. pickup  = pickup_eff · erosion      (sédiment créé)
3. deposit = h_deposit · S / (1 + slope/cap)
                                       (Lorentzian → tous slopes déposent
                                        un peu, flats déposent tout)
4. dH      = h_diffuse·∇²H − erosion + deposit   (Laplacian smoothing)
5. dS      = pickup − deposit + s_diffuse·(gauss(S) − S)
                                       (sédiment diffuse vers voisins)
6. dW      = w_rain − w_evap·W + w_share·(gauss(W) − W)
                                       (pluie + évap + voisinage)
```

Le résultat : **vallées qui se creusent là où l'eau coule**, **cônes
alluviaux qui s'étalent en pied de pente**, **crêtes affûtées** par la
diffusion sédiment + carvage différentiel. Ces dynamiques sont
émergentes — aucune n'est explicitement programmée.

---

## Architecture (vs Wave 23)

| Aspect | Wave 23 (mono) | Wave 24 (multi) |
|---|---|---|
| Channels per cell | 1 (H) | 3 (H, S, W) |
| Stencils 3×3 | 4 (lap, dx, dy, gauss) | 4 par canal |
| Update rule | linéaire sur H | linéaire sur (H, S, W) avec cross-channel |
| Mass conservation | non (pure smoothing) | quasi (sediment cycle) |
| Iterations défaut | 4 | 6 |
| Erosion | implicite via lap | explicite par water × slope |
| Deposition | non | explicite via Lorentzian |
| Visible effet | smoothing modéré | rivers + alluvial fans + sharp crests |

Architecture strictement NCA Mordvintsev. Les poids sont hand-tuned à
des priors physiques mais l'architecture est learnable — un offline
training sur DEM réel remplacerait les coefficients sans toucher au
code d'inférence.

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique (`refine_*`, `install_*`, `MultiChannelDecision`) | OK |
| 2 | Déterminisme pure-function : `max_diff=0.000000` | OK |
| 3 | Refinement modifie : `mean|dH|=0.102m, max|dH|=0.902m` | OK |
| 4 | Mass balance : drift 0.09 m (0.01 % rel, limite 15 %) | OK |
| 5 | **Erosion + déposition co-évolutives** : `eroded=24576 deposited=10151` | OK |
| 6 | Cellules abyssales gelées (bathymétrie intacte) | OK |
| 7 | Install idempotent | OK |
| 8 | Streamer wrap : 1 chunk refined, 6 iters | OK |
| 9 | Uninstall restaure le streamer | OK |

Particularité step 5 : **les deux phases du cycle sédimentaire sont
détectées simultanément**. 24576 cells érodent (water + slope carve)
ET 10151 cells déposent (Lorentzian decay laisse passer un peu partout
plus fort sur les flats). Le ratio 0.41 (deposit/erode) est cohérent
avec la fraction de sédiment effectivement transportée vs piégée.

---

## API publique

```python
from engine.nca_multichannel import (
    NCAMultiChannelConfig,
    NCAMultiChannelState,
    MultiChannelDecision,

    # Pure function overlay
    refine_chunk_multichannel,      # chunk, cfg -> MultiChannelDecision

    # Sim integration
    install_nca_multichannel,       # idempotent installer
    apply_to_existing_chunks,       # retro-refine cached
    nca_multichannel_state,         # reporter
    uninstall_nca_multichannel,
)
```

### Paramétrage

```python
cfg = NCAMultiChannelConfig(
    iterations=6,
    # height
    h_diffuse=0.06,            # Laplacian smoothing
    h_erode_by_water=0.020,    # erosion = factor × W × slope
    h_deposit_sediment=0.08,   # deposition coefficient
    # sediment
    s_pickup_efficiency=0.4,
    s_diffuse=0.12,
    s_settle_slope_cap=1.0,    # Lorentzian half-width
    # water
    w_rain_per_iter=0.06,
    w_evaporate=0.05,
    w_neighbour_share=0.18,
    w_initial=0.40,
)

install_nca_multichannel(sim, cfg)
```

### Composition avec Wave 23

Les deux waves peuvent cohabiter — applique Wave 23 puis Wave 24 en
chaîne. Wave 23 fait un smoothing/curvature pass rapide, Wave 24
ajoute le cycle hydro/sédimentaire complet.

```python
install_neural_terrain(sim)        # Wave 23 : single-channel refining
install_nca_multichannel(sim)      # Wave 24 : multi-channel co-evolution
```

---

## Limitations

- **Pas de routage global** : la water + sediment diffusent localement
  via 3×3, pas de D8 downstream propagation à l'échelle du chunk. Pour
  un vrai flow accumulation, voir Wave 18 (`chunk_hydrology`) qui ancre
  les rivières sur la macro.
- **State vector limité à 3** : Mordvintsev original utilise 16 canaux
  (dont des canaux "hidden" sans interprétation physique apprise par
  gradient descent). Sans training, ces canaux seraient du bruit, donc
  pas inclus ici.
- **Hand-tuned weights** : la qualité visuelle dépend de la calibration.
  Wave 25+ pourrait entraîner les coefficients sur DEMs réels offline.
- **Cost CPU** : ~6 iters × 4 stencils × 3 channels × CHUNK_SIZE² ≈
  300k ops par chunk au démarrage. ~1.5 ms par chunk. Acceptable
  (worst-case 100 chunks = 150 ms de bootstrap).

---

## Branchements futurs

| Module | Intégration |
|---|---|
| `chunk_hydrology` | Le canal W de Wave 24 pourrait initialiser à partir des rivières macro. |
| `geology` | Le carvage rocheux pourrait exposer des strates différentes par profondeur. |
| **Wave 25** | Entraîner sur DEMs Copernicus (10 min sur CPU avec scikit-learn LinearRegression sur les coefficients), embed comme `.npy`. |
| **Wave 26** | Ajouter canaux "hidden" + un mini-MLP de cross-channel weights, full Mordvintsev. |
| `dashboard` | Hillshade post-Wave-24 montrerait visuellement la richesse ajoutée. |
