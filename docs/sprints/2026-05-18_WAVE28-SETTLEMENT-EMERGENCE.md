# Wave 28 — Settlement Emergence via Multi-Criteria Scoring

**Date :** 2026-05-18 (session 34l)
**Module livré :** `engine.settlement_emergence`
**Smoke :** `scripts/p58_settlement_emergence_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Le pipeline Waves 16-27 produit un monde ultra-réaliste mais ne dit
JAMAIS "où poser un village". Wave 28 répond — sans script.

L'algorithme combine **6 critères macro** (tous issus des Waves 16-22)
en un score de viabilité par cellule, puis sélectionne N sites par
**Poisson-disk sampling déterministe**. Aucune coordonnée n'est
hardcodée ; les sites émergent du paysage.

---

## Scoring multi-critères

Chaque cellule macro reçoit 6 sub-scores ∈ [0, 1] :

| Critère | Formule | Source Wave |
|---|---|---|
| **Flatness** | `1 − clip(|∇elev|/50, 0, 1)` | Wave 16 elev |
| **Water access** | distance-decayed proximity to `river_mask` | Wave 16/18 rivers |
| **Food potential** | biome NPP lookup (rainforest=1, desert=0.05) | Wave 16 biome |
| **Tectonic safety** | 1 if no CONVERGENT 4-neighbour, else 0.25 | Wave 17 boundaries |
| **Climate** | Gaussian around T=15°C × Gaussian around P=800mm | Wave 16 temp/precip |
| **Coast bonus** | Gaussian around dist_to_coast = 25 km, σ=40 km | Wave 16 dist_coast |

**Score combiné = moyenne géométrique pondérée** (poids configurables).
La moyenne géométrique = si UN composant est zéro, le score collapse à
zéro. Un village a besoin de TOUT, pas juste de quelques bonnes choses.

```
log_score = Σ_i (w_i / Σw) · log(max(component_i, ε))
score = exp(log_score) · (1 if land else 0)
```

---

## Poisson-disk sampling

Greedy avec spacing minimal en km :

```
1. score = score_field + tiny prf_rng jitter (tie-break déterministe)
2. available = score > floor
3. répéter N fois :
       cand = argmax(score on available)
       record(cand)
       mask all cells within min_spacing_km of cand as unavailable
```

Garantit : N sites max, spacing ≥ min_spacing_km × 0.9 (cell-rounding
slack), tous land.

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique | OK |
| 2 | 7 composants (6 sub-scores + score combiné), shape (R, R) float32 | OK |
| 3 | Ocean cells score ≈ 0 | OK (`max_ocean_score=0.000000`) |
| 4 | 8 candidats, min_dist 318.7 km ≥ 300 km cible | OK |
| 5 | Cellules convergent → safety 0.250 vs 0.939 ailleurs | OK |
| 6 | Water score : near-river > far-river (skipped si pas de rivière) | OK |
| 7 | Déterminisme : mêmes inputs → candidats identiques | OK |
| 8 | Render overlay paint dots sur les sites | OK |
| 9 | `candidates_summary` plausible | OK |

---

## Render généré

`docs/renders/wave28_settlements.png` — 15 sites roses overlay sur la
carte macro (128×128) avec seed 0xC0FFEE_42. Top sites :

| Rank | Position (km) | Biome | Score |
|---:|---|---|---:|
| 0 | (1546, 1328) | COLD_DESERT (oasis) | 0.380 |
| 1 | (2671, 1171) | BOREAL_FOREST | 0.367 |
| 2 | (2640, 578) | TUNDRA | 0.340 |
| 3 | (1265, 1890) | HOT_DESERT | 0.296 |
| 4 | (2953, 2640) | COLD_DESERT | 0.290 |
| 5 | (2515, 1984) | TROPICAL_DRY_FOREST | 0.186 |
| ... | ... | ... | ... |

Note : le top biome est COLD_DESERT pour cette seed parce que les
plaines désertiques cochent flat + safe + (coast à la lisière). Les
forêts arrivent juste après. Très réaliste : la civilisation humaine
historique a longtemps préféré les zones semi-arides aux jungles
denses (transport, agriculture).

---

## API publique

```python
from engine.settlement_emergence import (
    # Pure function scoring
    score_settlement_viability,    # world, cfg → dict[component → (R,R) f32]

    # Site picking
    find_settlement_candidates,    # world → List[SettlementCandidate]

    # Visualisation
    render_settlements_overlay,    # world, candidates → uint8 RGB + PNG

    # Summary
    candidates_summary,            # candidates → dict

    # Data classes
    SettlementConfig,              # weights + sigmas + thresholds
    SettlementCandidate,           # rank, ix/iy, x/y_km, score, components, biome

    # Reference
    BIOME_FOOD_POTENTIAL,          # 12-biome NPP lookup
)
```

### Usage minimal

```python
from engine.world_genesis import generate_world, GenesisParams
from engine.settlement_emergence import (find_settlement_candidates,
                                           render_settlements_overlay)

world = generate_world(GenesisParams(seed=0xCAFE, resolution=128))
candidates = find_settlement_candidates(
    world, n_candidates=20, min_spacing_km=250.0)

render_settlements_overlay(world, candidates,
                             path="settlements.png")

for c in candidates[:5]:
    print(f"  rank {c.rank}: ({c.macro_x_km:6.1f}, "
          f"{c.macro_y_km:6.1f}) km  score={c.score:.3f}")
```

### Custom weighting

```python
from engine.settlement_emergence import SettlementConfig

# Favor coastal sites (Phoenician-style)
cfg = SettlementConfig(
    weight_coast=2.0,
    weight_flatness=0.5,
    coast_optimal_km=10.0,    # closer to coast
)
candidates = find_settlement_candidates(world, cfg=cfg, n_candidates=12)
```

---

## Limitations connues

- **Macro-scale only** : Wave 28 opère sur la grille macro (~30 km/cell
  par défaut). Pour placer un village au km près, il faudrait redescendre
  sur chunk-scale. Le candidat retourne la cellule macro ; un user peut
  zoomer ensuite avec ses propres heuristiques chunk-level.
- **Pas de simulation temporelle** : les sites sont calculés à `t=0`.
  Une vraie émergence (croissance/déclin) nécessiterait coupler avec
  agriculture + cognition + polity.
- **Poisson-disk greedy** : peut louper l'optimum global pour
  ``n_candidates`` grand. Pour N > 100, considérer Bridson sampling.
- **Score zéro-collapsé** : la moyenne géométrique punit les cellules
  excellentes dans 5/6 critères mais nulles dans le 6e. C'est voulu
  (un village a besoin de tout) mais peut être trop strict pour
  certaines civilisations historiques (déserts pour Bedouins, mers
  pour Polynésiens). Ajuster les poids ou utiliser une moyenne
  harmonique pour assouplir.

---

## Branchements futurs

| Module | Intégration |
|---|---|
| `agriculture` | Initialiser `culture_seed_library` aux candidats. |
| `polity` | Fonder polities à partir des top candidates. |
| `world_genesis_global` | Coordonner peuplement inter-régions (sister cities). |
| **Wave 29** | Simulation croissance + déclin via cognition + agriculture. |
| **Wave 30** | Réseau de routes entre settlements via shortest-path sur cost field (1 / score). |
