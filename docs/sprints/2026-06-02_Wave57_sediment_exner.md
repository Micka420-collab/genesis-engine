# Wave 57 — Lit mobile / transport sédimentaire (Exner)

**Date :** 2026-06-02 · **Module :** `engine.sediment_observer` · **Smoke :** `p126`

## Motivation

La veille du jour ([`docs/veille/2026-06-02_VEILLE.md`](../veille/2026-06-02_VEILLE.md),
DÉCOUVERTE_1 — morphodynamique Shallow Water–Exner) pointe le **palier
explicitement nommé par la roadmap** : l'érosion dynamique / transport
sédimentaire, prochain saut de la géologie (68) et de l'hydrologie (72). La
Wave 53 (`discharge_observer`) calcule déjà le débit stationnaire `Q` par
routage LTI exact sur le graphe D8, mais le **lit reste fixe**. Wave 57 ferme
la boucle **eau → sédiment → relief** avec un opérateur **Exner** CPU
déterministe, **sans nouveau substrat physique** et sans script de
comportement — il réutilise le débit émergent et ne fait que *rapporter* la
vitesse à laquelle la physique fermée ferait évoluer le lit.

## Modèle (Exner transport-limité)

Le lit évolue par conservation de la masse de sédiment — l'**équation
d'Exner** :

```
(1 − λ) ∂z_b/∂t = − ∇·q_s
```

Sur le graphe D8 (une arête sortante par maille), la divergence se réduit à
`q_out − q_in`, donc le taux de variation discret est :

```
(1 − λ) · aire_maille · ∂z/∂t = q_in − q_out   (>0 aggradation, <0 incision)
```

Chaque maille porte une **capacité de transport** par loi de puissance de
ruissellement (stream power) sur le débit *déjà émergent* `Q` (Wave 53) et la
pente aval locale `S` issue du champ d'élévation émergent :

```
q_cap = k_transport · Q^m · S^n          (famille Engelund-Hansen / Bagnold)
```

Le flux est routé une fois, en ordre topologique exact (Kahn), et à chaque
maille :

- si `q_in ≥ q_cap` → le surplus **dépose** : `q_out = q_cap` ;
- si `q_in < q_cap` → le déficit **érode** le lit (transport-limité, ou
  plafonné par une limite de détachement optionnelle) : `q_out = q_in + e`.

## Invariants (prouvés par tests + smoke)

| Invariant | Vérification |
|-----------|--------------|
| **Fermeture de masse exacte** | `Σ érosion == Σ dépôt + export(puits)` (résidu = 0.00e+00 sur monde réel) |
| Identité tête de bassin | capacité constante ⇒ seule la tête érode (`E = q_cap`), le reste passe à capacité |
| Capacité décroissante | dépôt du surplus à chaque maille (`5,4,3,2,1 ⇒ dépôts 1,1,1,1`) |
| Confluence | `q_out` aval = capacité ; fermeture conservée |
| Limite de détachement | `erosion_limit` plafonne l'érosion par maille (`q_out` croît de 1 par maille) |
| Pente aval ≥ 0 | drop/run borné à 0 ; `q_cap ∝ Q^m·S^n` |
| Signe du lit | érosion ⇒ `∂z/∂t < 0`, dépôt ⇒ `∂z/∂t > 0` |
| Lecture seule | `flow_dir`, `elevation_m`, `sim.tick` inchangés |
| Déterminisme | signature sha256 stable cross-sim |

## Surface

`SedimentConfig` · `BasinSediment` · `SedimentSnapshot` ·
`SedimentHistory` · `SedimentState` ·
`downstream_slope` · `transport_capacity` · `route_sediment` ·
`bed_change_rate` · `observe_sediment` · `install_sediment_observer` /
`uninstall_sediment_observer` · `sediment_summary`.

Réutilise `engine.discharge_observer` (`route_runoff`, `runoff_field_m3s`,
`_resolve_world`, `_field`, `_SECONDS_PER_YEAR`, constantes D8) — **aucune
duplication** du routage D8.

## Résultats

- `runtime/tests/test_sediment_observer.py` — **13/13** verts.
- `runtime/scripts/p126_sediment_exner_smoke.py` — **10/10 PASS** (résidu de
  masse réel = 0.00e+00, incision max 10.6 mm/yr, aggradation max 11.2 mm/yr,
  85/612 bassins considérés sur monde Genesis 64²).
- `ruff` clean ; voisins hydrologie/géologie (`p122`–`p125`) verts.
- Câblé dans `make validate-all` + CI (après `p125`).

## Impact réalisme

Première brique de **lit mobile** : ferme la boucle eau→sédiment→relief en
s'appuyant sur le débit LTI (Wave 53) et la quantification réseau (Wave 49).
Géologie/relief **68 → 70 %** ; Écologie/hydrologie **72 → 73 %** ; global
≈ **78,4 %** (recalcul moyenne 7 dimensions : (80+70+73+76+82+86+82)/7).

## Gaps honnêtes / pistes

- **Transport-limité** par défaut (réserve de lit illimitée) ; la transition
  alluvial→socle rocheux est offerte via `detachment_limited` mais reste un
  plafond simple `k_erode·Q^m·S^n`, pas un modèle de socle (SPACE/SPIM).
- Régime **stationnaire** : le lit n'est pas rétro-injecté dans `elevation_m`
  (observateur read-only) ; le couplage transitoire morpho ↔ relief
  (mise à jour du DEM, re-calcul D8) reste backlog.
- `k_transport`, `m_exp`, `n_exp`, `porosity` sont des constantes de config,
  non dérivées d'une granulométrie émergente.
- Variante **GPU shallow-water + Exner** (sedExnerFoam / `bevy_gpu_compute`,
  veille 06-01/06-02) non portée — la physique CPU reste la source de vérité ;
  le GPU serait un accélérateur validé contre elle (parité déterministe à
  garantir avant smoke).
