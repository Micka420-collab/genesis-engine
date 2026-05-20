# Wave 32 — Polity Emergence + Voronoi Territory

**Date :** 2026-05-18 (session 34p)
**Module livré :** `engine.polity_emergence`
**Smoke :** `scripts/p62_polity_emergence_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Wave 31 livre des vecteurs culturels par settlement. Wave 32 les
**agrège en nations** : les settlements culturellement similaires
forment des polities ; chaque polity revendique le territoire macro le
plus proche de ses membres.

Le résultat : une **carte politique Risk/Civ-style émergente**,
entièrement dérivée du pipeline géologie → culture sans aucune
coordination centralisée.

---

## Architecture

```
1. Cluster settlements (cultural_diffusion.detect_cultural_blocs)
       greedy union-find : ‖culture_i − culture_j‖₂ < threshold

2. Per cluster, construct Polity :
       capital      = member with highest trade weight
       avg_culture  = mean of member cultures
       color_rgb    = culture_to_rgb(avg_culture)
       population   = Σ member weights

3. Voronoi territory assignment :
       For each macro land cell, find nearest settlement (Euclidean
       distance × weighted by population^voronoi_weight_exp).
       Cell receives that settlement's polity_id.
       Ocean cells → -1.

4. Border detection :
       Cell is a border iff any 4-neighbour has a different polity_id
       (both non-ocean).
```

### Multiplicatively-weighted Voronoi

Avec ``voronoi_weight_exp = 1.0`` (défaut), le Voronoi est ordinaire :
chaque cellule rejoint le settlement géographiquement le plus proche.

Avec ``voronoi_weight_exp > 1.0``, les settlements à fort poids
"volent" plus de territoire. Modèle de villes-hégémons (Rome, Pékin
impérial).

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique | OK |
| 2 | ≥ 1 polity émerge | OK (9 polities sur 10 settlements) |
| 3 | Partition stricte : chaque settlement dans 1 et 1 seule polity | OK |
| 4 | Chaque capital ∈ member_ranks de sa polity | OK |
| 5 | Voronoi couvre **toutes** les land cells (0 unassigned) | OK |
| 6 | Distances intra-polity culturelles < threshold (max_intra=0.248) | OK |
| 7 | Déterminisme inter-runs | OK |
| 8 | Render PNG avec ≥ 12 couleurs distinctes (= biomes + tints) | OK (105 RGB distinctes) |
| 9 | `polity_summary` plausible | OK |

---

## Render généré

`docs/renders/wave32_polities.png` :

Configuration de génération :
- World R=128, seed 0xC0FFEE_42
- 14 settlements, threshold culturel 0.20 (strict → diversité préservée)
- Cultural diffusion light (5 iters, α=0.03)

**14 polities émergent**, chacune singleton dans cette config (cultures
trop diverses pour fusionner). Top par territoire :

| Polity | Territory | Color | Capital |
|---:|---:|---|---:|
| 4 | 1998 cells | (75, 62, 77) gris-violet | rank 4 |
| 3 | 1613 cells | (32, 40, 193) bleu | rank 3 |
| 1 | 933 cells | (91, 108, 175) ciel | rank 1 |
| 0 | 555 cells | (141, 123, 121) beige | rank 0 |
| 11 | 451 cells | (26, 101, 105) sarcelle | rank 11 |

Sur le PNG :
- Territoires teintés avec ``territory_alpha=0.55``
- Frontières noires (`border_rgb=(30, 30, 30)`)
- Capitales en blanc (radius 2 px)
- Routes Wave 29 en gris (`road_rgb=(180, 180, 180)`)
- Océan en bleu (depuis Wave 27 hillshade)

Le résultat ressemble visuellement à une carte politique Risk ou
Civilization VI — territoires contigus, capitals identifiables,
frontières claires, routes visibles.

---

## API publique

```python
from engine.polity_emergence import (
    # Configuration + types
    PolityConfig,                # 5 hyperparams
    Polity,                      # id, capital_rank, members, territory_mask, ...
    PolityMap,                   # polities + polity_id_grid + totals

    # Core
    assign_polities,             # world, settlements, cultures, trade → PolityMap

    # Visualisation
    render_polities,             # → uint8 RGB + PNG

    # Reporter
    polity_summary,              # → dict
)
```

### Usage type minimal

```python
from engine.polity_emergence import (PolityConfig, assign_polities,
                                        render_polities, polity_summary)

cfg = PolityConfig(similarity_threshold=0.25, voronoi_weight_exp=1.0)
pmap = assign_polities(world, settlements, cultures, trade, cfg)
render_polities(world, pmap, settlements, network,
                  path="polities.png", territory_alpha=0.55)

print(polity_summary(pmap))
```

### Tuning the geopolitical scale

```python
# Loose threshold → big multi-city empires (Roman / Han)
cfg_empire = PolityConfig(
    similarity_threshold=0.5,
    voronoi_weight_exp=1.4,  # capitals dominate
)

# Strict threshold → fragmented tribes / city-states
cfg_tribes = PolityConfig(
    similarity_threshold=0.15,
    voronoi_weight_exp=1.0,
)
```

---

## Limitations connues

- **Statique** : les polities sont calculées à un instant t. Pas
  d'évolution historique (conquêtes, sécessions, alliances). Pour le
  temps long, voir Wave 33+ (conflict + diplomacy).
- **Voronoi non topographique** : la distance est Euclidienne, pas
  Dijkstra-routes. Une montagne au milieu d'une polity n'est pas un
  obstacle. Wave 33 pourrait passer à Dijkstra-cost-field.
- **Pas d'enclave / exclave** : chaque polity est une seule composante
  Voronoi. En réalité, l'Alaska est USA mais physiquement séparé.
  Plusieurs Voronoi cells géographiquement disjointes peuvent porter
  la même polity_id, mais sans frontière visible spéciale.
- **Pas de capital migration** : la capital est figée au settlement le
  plus riche au moment de la création. En réalité, Pékin ↔ Nankin
  shifts historiques. Pour ça il faudrait lier au Wave temps long.

---

## Branchements futurs

| Module | Intégration |
|---|---|
| **Wave 33** | Conflict emergence : polities adjacentes culturellement éloignées → tension. |
| **Wave 34** | Time evolution : naissance / fusion / scission au fil des ticks. |
| `engine.polity` | Genesis Engine a déjà un module `polity.py` (Wave 9c) — fusionner pour brancher les decisions agents sur la polity_id émergente. |
| `dashboard` | Tooltip polity-info au survol. |
| Multi-region (Wave 22) | Polities cross-régionales via les border outlets. |
