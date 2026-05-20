# Wave 31 — Cultural Diffusion via Trade Network

**Date :** 2026-05-18 (session 34o)
**Module livré :** `engine.cultural_diffusion`
**Smoke :** `scripts/p61_cultural_diffusion_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Wave 30 livre des volumes commerciaux entre settlements. Wave 31
exploite cette structure : la **culture diffuse le long des routes
commerciales**, pondérée par les volumes. Phénomène anthropologique
classique : le grec koinè s'est propagé le long des routes
méditerranéennes, le latin via les caravanes, les cuisines fusionnent
le long des caravansérails.

Aucune coordination centralisée. Chaque settlement reçoit une culture
initiale (vecteur 5-D aléatoire prf_rng-déterministe) qui évolue par
diffusion pondérée vers ses voisins commerciaux. Au bout de K
itérations, des **blocs culturels émergent**.

---

## Architecture mathématique

L'équation de diffusion correspond exactement à un **noyau de chaleur
sur graphe** (graph Laplacian heat kernel) :

```
P[i, j] = flow_ij / Σ_k flow_ik           # matrice stochastique par rangée
culture_i(t+1) = (1 − α) · culture_i(t)
               + α · Σ_j P[i, j] · culture_j(t)
               + ε · innovation_noise
```

Où :
- α = `diffusion_rate` (typique 0.10–0.30) — intensité de l'attraction
  vers les voisins par step.
- ε = `innovation_rate` (typique 0.005) — petite dérive aléatoire qui
  empêche la convergence totale et préserve la diversité.

Sans bruit d'innovation, le système converge vers la moyenne globale
en perdant toute distinction. Avec ε > 0 il se stabilise sur un
équilibre dynamique qui reflète la topologie commerciale.

### Initialisation

```
culture_i(0) = prf_rng(initial_seed, "culture_init", [rank_i]).random(D)
             ∈ [0, 1]^D
```

5-D par défaut. Stockable comme RGB (3 premières dims) + métadonnées
hors visualisation (2 dernières dims).

### Détection de blocs

Greedy union-find : deux settlements appartiennent au même bloc ssi
`||culture_i - culture_j|| < similarity_threshold`. Pas de k-means
arbitraire ; simple proximité euclidienne.

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique | OK |
| 2 | Init shape (N, D) float32, range [0, 1] | OK |
| 3 | Init déterministe (même seed → même cultures) | OK |
| 4 | Matrice de diffusion row-stochastique (rows = 1.0) | OK |
| 5 | Cultures clampées [0, 1] après K itérations | OK |
| 6 | **Heavy-trade pair (1,2) flow=100 → d_cult=0.026 vs light (0,6) flow=8.6 → d_cult=0.248 (9.5×)** | OK |
| 7 | Full run déterministe inter-runs | OK |
| 8 | Render paint dots avec culture-derived RGB | OK |
| 9 | `cultural_summary` plausible (1 bloc sur 8 settlements) | OK |

**Step 6 est le check clé** : il prouve quantitativement que les
voisins commerciaux fort-débit convergent culturellement plus que les
voisins faible-débit. Ratio 9.5× sur cette seed.

---

## Renders générés

`docs/renders/wave31_cultures_*.png` :

| Fichier | Scénario | Blocs | Convergence |
|---|---|---:|---:|
| `wave31_cultures_early.png` | diffusion=0.10, 20 iters | 1 | 0.440 |
| `wave31_cultures_late.png` | diffusion=0.20, 100 iters | 1 | 0.540 |

Sur les deux renders, **12 settlements visibles aux couleurs variées**
(jaune, vert, violet, magenta) sur fond de continent + routes grises.
Le late shot montre des couleurs un peu plus convergées vers la
moyenne — diffusion plus poussée.

Pour des blocs distincts visibles, il faut soit :
- diminuer la diffusion_rate (cultures plus persistantes)
- séparer le réseau en plusieurs composantes connexes (multi-region)
- augmenter innovation_rate (drift dominant)

---

## API publique

```python
from engine.cultural_diffusion import (
    # Configuration + history
    CulturalConfig,                 # 5 hyperparams
    CulturalHistory,                # initial, final, convergence_metric

    # Core
    initialize_cultures,            # settlements, cfg → (N, D) f32
    step_cultural_diffusion,        # cultures, P, cfg, step_seed → cultures
    run_cultural_diffusion,         # settlements, trade, cfg → CulturalHistory

    # Analysis
    detect_cultural_blocs,          # cultures → List[List[int]]
    culture_to_rgb,                 # vec → (R, G, B)

    # Visualisation
    render_cultural_map,            # world, network, settlements, history → PNG

    # Reporter
    cultural_summary,               # → dict with bloc info
)
```

### Usage type

```python
from engine.cultural_diffusion import (CulturalConfig,
                                          run_cultural_diffusion,
                                          render_cultural_map,
                                          cultural_summary)

cfg = CulturalConfig(
    n_dimensions=5,
    n_iterations=50,
    diffusion_rate=0.15,
    innovation_rate=0.005,
    initial_seed=0xCAFE_C0DE,
)
history = run_cultural_diffusion(settlements, trade, cfg)
render_cultural_map(world, network, settlements, history,
                      path="cultures.png", dot_radius_px=3)

print(cultural_summary(settlements, history,
                          similarity_threshold=0.25))
```

---

## Limitations connues

- **Convergence rapide vers un bloc** : si le réseau est très connecté
  et innovation_rate trop faible, tout converge vers la moyenne après
  50-100 iters. Pour des blocs persistants, isoler des sous-graphes
  (multi-region Wave 22) ou augmenter ε.
- **Dimensions abstraites** : un vecteur 5-D ne représente pas
  explicitement "langue / religion / technologie". Wave 32+ pourrait
  réifier chaque dimension avec un sens (e.g., D0=langue, D1=religion).
- **Pas de mort culturelle** : une culture peut diffuser à zéro, mais
  son vecteur n'est jamais "effacé". Pour des extinctions linguistiques
  réelles, ajouter un attribut `alive` per-dim.
- **Pas d'asymétrie de transmission** : la diffusion est symétrique
  (flux i→j = flux j→i). En réalité une culture dominante imprime
  davantage qu'elle n'absorbe (e.g. romanisation). Ajouter un facteur
  d'asymétrie basé sur le poids relatif des settlements.
- **Pas de temps long** : 100 iters = millénaires culturels. Pour
  modéliser des dynamiques millénaires (Néolithique → âge du fer),
  ajouter un calendrier sim-temps.

---

## Branchements futurs

| Module | Intégration |
|---|---|
| `polity` | Polities adjacentes culturellement → alliances ; éloignées → conflits. |
| **Wave 32** | Cultures réifiées par dimension (langue, religion, tech). |
| **Wave 33** | Conflict emergence quand cultures divergent + frontières routes. |
| `dashboard` | Time-lapse de la diffusion sur N iters. |
| Multi-region (Wave 22) | Diffusion intra-région forte, inter-région faible → blocs visibles. |
