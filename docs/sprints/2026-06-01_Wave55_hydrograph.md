# Wave 55 — Hydrogramme transitif (réservoir linéaire)

**Date :** 2026-06-01 · **Module :** `engine.hydrograph_observer` · **Smoke :** `p124`

## Motivation

La Wave 53 (`discharge_observer`) route le ruissellement émergent vers un débit
**stationnaire** `Q*` à chaque exutoire de bassin du graphe D8, mais laissait
explicitement en backlog l'**hydrogramme transitif** (« pas d'hydrogramme
transitif / réservoir linéaire », `NEXT-SPRINT.md`). Wave 55 comble ce trou
avec la construction canonique de l'hydrologie, **sans nouveau substrat
physique** et sans script de comportement.

## Modèle

Chaque exutoire émergent est traité comme un **réservoir linéaire unique**
(Maillet 1905 ; Nash 1957) :

```
dS/dt = I(t) − S/k ,   Q = S/k
```

Pour une entrée `I` constante par morceaux sur un pas `Δt`, la solution est
**exacte et fermée** (pas d'intégration numérique, inconditionnellement
stable, bit-déterministe) :

```
a       = exp(−Δt / k)
S_{n+1} = S_n · a + I_n · k · (1 − a)
Q_{n+1} = S_{n+1} / k
```

L'observateur excite ce réservoir par une **impulsion de pluie finie**
(`storm_days`) dont le régime d'équilibre est le `Q*` émergent du bassin lu de
la Wave 53. Résultat : un hydrogramme d'orage réaliste — montée pendant
l'orage, pic en fin d'orage, récession exponentielle de constante `k`.

## Invariants (prouvés par tests + smoke)

| Invariant | Vérification |
|-----------|--------------|
| Fermeture de masse du réservoir | `s0 + Σ I·Δt − out_cum == S` (résidu ≈ 1e-16) |
| Récession géométrique monotone | `Q[n] == Q0·aⁿ`, strictement décroissante |
| Réponse indicielle → `Q*` | entrée constante depuis vide ⇒ `Q → I` (lien Wave 53) |
| Demi-récession | `t½ ≈ k·ln 2` (interpolation sur le limbe) |
| Lecture seule | `flow_dir`, `precip_mm`, `sim.tick` inchangés |
| Déterminisme | signature sha256 stable cross-sim |

## Surface

`HydrographConfig` · `BasinHydrograph` · `HydrographSnapshot` ·
`HydrographHistory` · `HydrographState` ·
`linear_reservoir_response` · `storm_hydrograph` · `half_recession_days` ·
`observe_hydrograph` · `install_hydrograph_observer` /
`uninstall_hydrograph_observer` · `hydrograph_summary`.

Réutilise `engine.discharge_observer` (`observe_discharge`, `DischargeConfig`) —
aucune duplication du routage D8.

## Résultats

- `runtime/tests/test_hydrograph_observer.py` — **11/11** verts.
- `runtime/scripts/p124_hydrograph_smoke.py` — **10/10 PASS** (résidu masse
  max réel = 8.6e-16, pic max 1586 m³/s, `t½ ≈ 3.5 j` sur monde Genesis).
- `ruff` clean ; voisins hydrologie (`p122`, `p123`) verts.
- Câblé dans `make validate-all` + CI (après `p123`).

## Gaps honnêtes / pistes

- Réservoir **unique** ; la cascade de Nash `n > 1` (IUH multi-réservoirs,
  pic décalé `t_p = (n−1)·k`) reste backlog.
- `k` et `storm_days` sont des constantes de configuration, non dérivées d'une
  géomorphologie émergente. Piste : `k ∝ longueur de drain / pente` à partir
  des champs D8 déjà disponibles.
- Hydrogramme **groupé à l'exutoire** ; pas (encore) de couplage transitoire
  cellule-par-cellule sur le graphe (la variante GPU/conv différentiable de la
  Wave 53 reste hors cœur déterministe).
