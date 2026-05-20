# Wave 30 — Trade Flow Gravity Emergence

**Date :** 2026-05-18 (session 34n)
**Module livré :** `engine.trade_flow`
**Smoke :** `scripts/p60_trade_flow_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Wave 29 livre des routes inter-settlements. Mais toutes les routes ne
sont pas équivalentes : une route Manhattan-Bronx est très différente
d'un sentier perdu en Sibérie. Wave 30 quantifie le **flux commercial
émergent** sur chaque arête du MST en utilisant le **modèle
gravitationnel** classique de l'économie urbaine.

L'équation de Stewart (1948) / Wilson (1967) :

```
flow_ij = K · (weight_i · weight_j) / (distance_ij ^ β)
```

C'est la même équation que Newton pour la gravitation, transposée à
l'interaction spatiale. Elle reproduit empiriquement les flux
commerciaux observés entre villes : deux grandes villes éloignées
produisent autant d'échanges que deux petites villes proches.

Aucun script ne fixe "Paris vend 500 t à Lyon". Les volumes émergent
des poids et des distances calculés par les waves précédentes.

---

## Architecture

### Poids settlement (population proxy)

```
weight_i = max(settlement_score_i, floor)
         × (1 + bias_food × biome_NPP_at_site)
```

- `settlement_score_i` : composite Wave 28 (flatness + water + ...).
- `biome_NPP_at_site` : food potential du biome (Wave 16).
- `bias_food = 0.5` : un site avec NPP=1 (rainforest) a +50 % de poids.

### Distance

Distance = longueur réelle de la route MST en km (Wave 29 `RoadEdge.length_km`),
PAS l'Euclidienne. Une route qui contourne une montagne paie ses km.

### Flux

Pour chaque paire (i, j) connectée par une arête MST :

```
flow_ij = (weight_i × weight_j) / (length_km_ij ^ 1.6)
```

β = 1.6 par défaut (typique économie urbaine, Reilly 1931 → β = 2 ;
Stewart 1948 → β = 1).

Matrice (N, N) symétrique, normalisée tel que `max(flow) = 100.0`
(`max_flow_volume` config).

Les paires NON directement connectées dans le MST restent à zéro —
modèle one-step. Pour propagation multi-hop, lancer une chaîne de
Markov sur la matrice (Wave 31+).

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique | OK |
| 2 | Weights shape (N,) float32, tous > 0 | OK (min=0.086) |
| 3 | Rainforest 0.75 > Desert 0.51 (NPP bias correct) | OK |
| 4 | Flow matrix symétrique (max_diff=0.0) | OK |
| 5 | Top-flow edge = top w_i·w_j/d^β (gravité correcte) | OK |
| 6 | Seuls MST-pairs ont nonzero flow | OK (extraneous=0) |
| 7 | Déterminisme inter-runs | OK |
| 8 | Render paint roads en couleurs flow-magnitude (jaune→rouge) | OK |
| 9 | `trade_summary` plausible avec top routes | OK |

---

## Résultats visibles

`docs/renders/wave30_trade_flows.png` :

- 12 settlements (cercles roses dimensionnés par poids — la plus
  grande = dominant city)
- 11 arêtes MST colorées par volume :
  - **jaune pâle (255, 240, 100)** = faible flux
  - **ambre (255, 150, 60)** = flux moyen
  - **rouge profond (200, 40, 40)** = flux élevé
- Volume total : 386.43 (normalisé)
- Top route : **1 ↔ 7** à volume 100 (max)
- Dominant city : rank 1, weight 0.467

| Route | Volume |
|---|---:|
| 1 ↔ 7 | 100.0 |
| 0 ↔ 3 | 53.48 |
| 2 ↔ 7 | 41.91 |
| 1 ↔ 8 | 36.08 |
| 5 ↔ 9 | 31.25 |

La carte révèle visuellement les **hubs commerciaux** (ville 1, ville 7)
et les **routes secondaires** sans avoir scripté qui devait
échanger avec qui.

---

## API publique

```python
from engine.trade_flow import (
    # Config + data
    TradeConfig,                  # beta_distance, weight_floor, bias_food
    TradeNetwork,                 # weights + flows + edge_flow + summary

    # Pure functions
    compute_settlement_weights,   # settlements, world → (N,) float32
    compute_trade_flows,          # settlements, world, network → TradeNetwork

    # Visualisation
    render_trade_flows,           # → uint8 RGB + PNG

    # Reporter
    trade_summary,                # → dict with top routes
)
```

### Usage minimal

```python
from engine.world_genesis import generate_world, GenesisParams
from engine.settlement_emergence import find_settlement_candidates
from engine.road_network import build_road_network
from engine.trade_flow import compute_trade_flows, render_trade_flows

world = generate_world(GenesisParams(seed=0xCAFE, resolution=128))
cands = find_settlement_candidates(world, n_candidates=12)
network = build_road_network(world, cands)
trade = compute_trade_flows(cands, world, network)

render_trade_flows(world, network, cands, trade,
                     path="trade_flows.png")
```

### Tuning the gravity exponent

```python
from engine.trade_flow import TradeConfig

# Beta=2.0 (Newton-style) : distance penalizes more strongly → only
# nearby pairs trade significantly.
cfg = TradeConfig(beta_distance=2.0)

# Beta=1.0 (Stewart 1948) : less distance decay → far-away big cities
# still trade.
cfg = TradeConfig(beta_distance=1.0)
```

---

## Limitations connues

- **One-step gravity** : seules les paires directement connectées en
  MST ont du flow. Pour modéliser le transit (Paris → Munich via
  Strasbourg), faire une chaîne de Markov sur la matrice — Wave 31+.
- **Pas de spécialisation** : un poids unique encode "tout". Pas de
  notion de "ville textile" vs "ville céréalière". Pour ça, un vecteur
  de production par bien serait nécessaire.
- **Statique** : les flux sont calculés à `t=0`. Pas d'évolution
  temporelle (croissance, déclin, perturbation).
- **β fixe** : un seul exposant. En réalité β dépend du bien (lourd =
  haut β, info = faible β).

---

## Branchements futurs

| Module | Intégration |
|---|---|
| `polity` | Polities riches = celles aux hauts flux. |
| **Wave 31** | Markov multi-hop : flux indirects via les hubs. |
| **Wave 32** | Cultural diffusion via le réseau commercial. |
| `dashboard` | Animation de la croissance d'une route au fil des ticks. |
| Multi-region | Trade inter-régional via les border outlets (Wave 22). |
