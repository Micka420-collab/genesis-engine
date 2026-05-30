# Wave 53 — LTI river-discharge routing observer

**Date** : 2026-05-30
**Couche** : Observateur L5 — routage hydrologique émergent (read-only)
**Smoke** : `runtime/scripts/p122_discharge_routing_smoke.py`
**Module** : `runtime/engine/discharge_observer.py`
**Tests** : `runtime/tests/test_discharge_observer.py`
**Status** : ✅ smoke 10/10 vert · pytest module 11/11 vert · suite cœur + voisins (~120 tests) verts

---

## 1. Motivation et règle d'émergence

La veille du jour ([`2026-05-30_VEILLE.md`](../veille/2026-05-30_VEILLE.md))
classe en **piste #1 actionnable** (gap Hydrologie 70 %) le *routage de
rivière différentiable sur GPU* (Hascoet et al. 2025) : un schéma de
routage **linéaire invariant dans le temps (LTI)** est mathématiquement
équivalent à une convolution **block-sparse**, d'où accélération GPU +
différentiabilité. Wave 49 (`watershed_observer`) avait déjà **quantifié**
le réseau (Strahler / Horton / drainage density) mais ne propageait aucun
**débit**.

Wave 53 livre la **version CPU déterministe** de cet opérateur LTI : on
propage un champ de **ruissellement** (dérivé du climat émergent
`precip_mm` / `temp_c`) le long du graphe D8 déjà émergent. La variante
GPU/conv différentiable reste explicitement en backlog (dépendance
torch/GPU à isoler hors cœur déterministe) — Wave 53 ne touche pas le hot
path.

**Règle d'émergence respectée** : aucune nouvelle ontologie. Le débit est
la réponse stationnaire d'un opérateur linéaire appliqué au ruissellement
que les champs climatiques encodent déjà. Aucun script ne fixe un débit,
ne nomme un fleuve, ne déclare un bassin. Module **read-only strict** : ne
touche jamais aux arrays du monde ni au tick.

---

## 2. Modèle — l'opérateur LTI exact

Avec `A` la matrice d'adjacence aval D8 (une seule arête sortante par
cellule, `255` = puits drainant hors domaine), le débit stationnaire `Q`
résout :

```
Q = r + Aᵀ Q     ⇔     Q = (I − Aᵀ)⁻¹ r
```

où `r` est le champ de ruissellement. Comme chaque cellule a **exactement
un** voisin aval, `(I − Aᵀ)⁻¹` s'évalue **exactement** par un seul balayage
topologique amont→aval (Kahn) — pas d'inverse de matrice, pas d'itération,
O(N). C'est la même infrastructure topologique déterministe que le Strahler
de Wave 49.

**Bilan de ruissellement** (monotone, non négatif, sans paramètre caché) :

```
ET   = min(P, k · max(T, 0))        ET actuelle limitée par température
q    = max(P − ET, 0)               ruissellement (mm/an)
r    = q · 1e-3 · A_cellule / s_an  débit volumétrique (m³/s)
```

`k = et_mm_per_degc` (défaut 45 mm/°C) ; `s_an` = secondes/an.

---

## 3. Invariants vérifiés (smoke + tests)

| Invariant | Garantie | Vérif |
|-----------|----------|-------|
| **Conservation de masse** | `Σ discharge[puits] == Σ runoff` | smoke 3/6, tests |
| **Monotonie aval** | `runoff ≥ 0 ⇒ Q[aval] ≥ Q[amont]` | test dédié |
| **Identité ruissellement unitaire** | `r ≡ 1 ⇒ Q == aire contributrice D8` | smoke 2, test |
| **Confluence** | `Q_aval == Σ tributaires + runoff local` | smoke 4, test |
| **Déterminisme** | signature sha256 stable cross-sim | smoke 8, test |
| **Read-only** | arrays monde + tick inchangés | smoke 7, test |
| **Install/uninstall** | idempotent, restaure `sim.step` | smoke 9/10, tests |

---

## 4. Run réel (sim p122_real, seed 0xCAFE_0122, res=64, threshold=8.0)

```
cell_km                : 62.500
total_runoff_m3s       : 127 239.5
total_outflow_m3s      : 127 239.5      (résidu masse = 0.00e+00)
mean_runoff_mm_yr      : 250.96
max_discharge_m3s      : 2 656.0  @ (13, 31)   (main stem émergent)
mean_river_discharge   : 426.4
bassins total/considérés : 818 / 155
top bassin #51   area=113 281 km²  Q_out=1993.6 m³/s  q=555 mm/yr
top bassin #209  area=113 281 km²  Q_out=1954.2 m³/s  q=544 mm/yr
top bassin #174  area= 27 344 km²  Q_out=1611.6 m³/s  q=1860 mm/yr (humide)
```

Débits spécifiques par bassin (≈ 500–1860 mm/an) cohérents avec des
bassins humides ; le bilan de masse ferme exactement.

---

## 5. Gaps honnêtes / suite

- **Routage stationnaire**, pas transitif : pas d'hydrogramme temporel
  (réservoir linéaire / Muskingum à célérité finie) — c'est le palier
  suivant pour passer de « débit moyen annuel » à « crue ».
- **Variante GPU/conv différentiable** (la vraie nouveauté Hascoet 2025)
  reste backlog : portage de l'opérateur LTI→conv block-sparse, parité
  déterministe CPU↔GPU à garantir avant tout branchement smoke.
- Le ruissellement est un bilan `P − ET` volontairement minimal (pas de
  neige/fonte, pas d'infiltration sol) — extensible sans casser l'API.

Impact réalisme : **Écologie / hydrologie 70 → 72 %** (routage de débit
émergent ajouté à la quantification réseau). Global ≈ **77 %** (inchangé
à l'arrondi).
