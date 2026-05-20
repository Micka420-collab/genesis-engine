# Wave 25 — Offline NCA Weight Training

**Date :** 2026-05-18 (session 34i)
**Module livré :** `engine.nca_training`
**Smoke :** `scripts/p55_nca_training_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Waves 23 et 24 implémentent l'architecture Mordvintsev NCA mais avec
des **poids hand-tuned** à des priors physiques. Le claim "neural" est
architecturalement correct (state vector + 3×3 stencils + iterated K
times = NCA selon le paper *Growing Neural Cellular Automata* 2020)
mais les coefficients ne sont pas appris.

Wave 25 ferme la boucle : **les poids sont maintenant apprenables et
appris** par descente de gradient finite-differences en pure numpy.
Pas de PyTorch, pas d'autograd — simplement
`(loss(w + ε) − loss(w − ε)) / 2ε` par poids par étape.

C'est de la **vraie machine learning** appliquée au cellular automaton
de Genesis.

---

## Architecture du training

```
Training set : N FBM chunks (n=4 default) générés via prf_rng
       │
       ├─→ Teacher : refine_chunk_multichannel à K_teacher iters
       │            (24 par défaut) = "ground truth" mature landscape
       │
       └─→ Student : refine_chunk_multichannel à K_student iters
                    (6 par défaut), poids θ à optimiser

Loss :   L(θ) = mean_chunks( MSE( student(θ).height − teacher.height ) )

Optim :  finite-difference gradient descent
         g[w] = (L(θ + ε·e_w) − L(θ − ε·e_w)) / (2ε)
         θ[w] ← max(0, θ[w] − lr · g[w])
         repeat n_gradient_steps times

Output : NCATrainingResult (initial_config, learned_config, loss_history,
                              improvement_pct, learned_weights)
```

10 poids optimisés : `h_diffuse`, `h_erode_by_water`, `h_deposit_sediment`,
`s_pickup_efficiency`, `s_diffuse`, `s_settle_slope_cap`,
`w_rain_per_iter`, `w_evaporate`, `w_neighbour_share`, `w_initial`.

---

## Résultats mesurés (smoke step 2)

| Métrique | Valeur |
|---|---|
| n_chunks_used | 2 |
| reference_iters (teacher) | 12 |
| student_iters | 6 |
| n_gradient_steps | 4 |
| **Loss initiale (hand-tuned)** | 0.0121 |
| **Loss finale (learned)** | 0.0042 |
| **Amélioration** | **65.3 %** |
| Convergence | monotone : 0.0121 → 0.0087 → 0.0065 → 0.0051 → 0.0042 |

Poids appris (delta sur 4 GD steps) :

| Poids | Init | Learned | Δ |
|---|---|---|---|
| `h_erode_by_water` | 0.0200 | 0.0356 | **+0.0156** |
| `h_diffuse` | 0.0600 | 0.0638 | +0.0038 |
| `w_rain_per_iter` | 0.0600 | 0.0619 | +0.0019 |
| `w_initial` | 0.4000 | 0.4007 | +0.0007 |
| `h_deposit_sediment` | 0.0800 | 0.0799 | -0.0001 |
| `w_evaporate` | 0.0500 | 0.0491 | -0.0009 |

Insight : pour rattraper un teacher 12-iters avec 6 iters seulement,
le student a besoin d'**éroder presque deux fois plus agressivement**
(`h_erode_by_water` × 1.78). Les autres poids bougent peu. Cohérent
avec l'intuition : plus d'érosion par tick compense la moitié de
temps d'évolution.

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique (`train_nca_weights`, `LEARNED_NCA_CONFIG`, `refresh_*`) | OK |
| 2 | Déterminisme : deux runs même seed → `loss_history` identique | OK |
| 3 | Training set construit : `n_chunks_used > 0` | OK (2/2) |
| 4 | Initial loss > 0 (student différent du teacher) | OK (0.0121) |
| 5 | Final < initial (training fonctionne) | OK (0.0042 < 0.0121) |
| 6 | Improvement ≥ 5 % | OK (65.3 %) |
| 7 | Tous les poids appris ≥ 0 (clamp correct) | OK |
| 8 | Learned config produit output différent du default | OK (0.072 m diff) |
| 9 | `LEARNED_NCA_CONFIG` embedded utilisable directement | OK |

---

## API publique

```python
from engine.nca_training import (
    NCATrainingConfig,         # hyper-params : n_chunks, lr, steps...
    NCATrainingResult,         # output : initial_config, learned_config,
                                #         loss_history, improvement_pct, ...
    train_nca_weights,         # main : pure-function trainer
    refresh_learned_weights,   # convenience : train + dump to file
    LEARNED_NCA_CONFIG,        # pretrained config embedded in module
)
```

### Usage type — entraîner et appliquer

```python
from engine.nca_training import train_nca_weights, NCATrainingConfig
from engine.nca_multichannel import install_nca_multichannel

# Entraîne offline (~30s pour 8 chunks / 30 steps)
result = train_nca_weights(NCATrainingConfig(
    n_chunks=8, reference_iters=30, n_gradient_steps=30,
), verbose=True)

print(f"Improvement: {result.improvement_pct:.1f}%")

# Applique les poids appris à une sim
install_nca_multichannel(sim, result.learned_config)
```

### Usage type — utiliser les poids pré-entraînés embedded

```python
from engine.nca_training import LEARNED_NCA_CONFIG
from engine.nca_multichannel import install_nca_multichannel

# Zero training — utilise les poids embedded.
install_nca_multichannel(sim, LEARNED_NCA_CONFIG)
```

### Usage type — régénérer les poids embedded

```python
from engine.nca_training import refresh_learned_weights

# Run training + dump à un fichier pour copier-coller dans le module.
refresh_learned_weights(
    out_path="learned_nca_weights.py",
    n_chunks=12, reference_iters=40, n_gradient_steps=50,
)
```

---

## Limitations connues

- **Finite-difference GD coûteux** : 2 evals par poids par étape × 10
  poids = 20 evals par étape. À n_chunks=8 et student_iters=6, chaque
  eval = 8 × 6 × ~300k ops = 14M ops. 20 evals/step × 30 steps = 600
  evals = 8.4G ops. Tourne en ~30-60s. Pour gros runs, batch via
  multiprocessing.
- **Pas de momentum / Adam** : juste vanilla SGD avec lr constant.
  Suffit pour les 10 poids du NCA mais convergence lente sur problèmes
  difficiles.
- **Pas de validation set** : risque d'overfit aux chunks training.
  À ajouter pour Wave 26.
- **Le teacher est une variante de l'étudiant**, pas un vrai DEM réel.
  Pour entraîner sur Earth réelle, il faudrait downloader Copernicus
  DEM + un VAE pour réduire la dimension. Hors scope Wave 25.

---

## Comparaison avec les autres approches AI world-gen

| Approche | Genesis Wave | Training data | Compute | Determinist |
|---|---|---|---|---|
| Genie 3 (DeepMind) | ❌ | huge video corpus | GPU farm | non |
| Terrain Diffusion (SIGGRAPH '26) | ❌ | curated DEM | GPU + PyTorch | non |
| WFC | optionnel | exemple tile | CPU | oui |
| NCA hand-tuned | Wave 23-24 | aucune | CPU pure numpy | oui |
| **NCA learned (FD-GD)** | **Wave 25** | self-supervised teacher | CPU pure numpy | oui |

Wave 25 reste la seule à combiner training + pure numpy + déterminisme.

---

## Branchements futurs

| Module | Intégration |
|---|---|
| **Wave 26** | Adam / momentum + validation set |
| **Wave 27** | Vrai DEM Copernicus + autoencoder reduction |
| **Wave 28** | Multi-task : learn weights per biome / per province |
| `genesis_bootstrap.py` | Ajouter `use_learned_nca_weights: bool = True` |
| `dashboard.py` | Visualiser loss history pour debug |
