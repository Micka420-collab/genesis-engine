# Wave 45 — Mètre d'open-endedness intrinsèque (ontology-free)

**Date** : 2026-05-29
**Couche** : Observateur L5 · méta-mesure d'émergence (read-only)
**Smoke** : `runtime/scripts/p115_open_endedness_smoke.py`
**Module** : `runtime/engine/open_endedness.py`
**Tests** : `runtime/tests/test_open_endedness.py`
**Status** : ✅ smoke 10/10 vert · pytest 11/11 vert · suite runtime 187/187 vert

---

## 1. Objectif et règle d'émergence

Le papier scientifique (section « positionnement épistémologique : vie
artificielle faible vs forte ») pose la question : Genesis Engine est-il
**ouvert** (open-ended), c.-à-d. continue-t-il d'inventer du nouveau, ou
finit-il par tourner en rond dans un répertoire fixe ? On ne peut pas le
**revendiquer** sans le **mesurer**. Wave 45 est l'instrument de mesure —
le premier pas instrumental vers la **VA forte**.

Le piège classique : `engine.emergence_metrics` compte déjà des choses
(`technologies_discovered`, `communication_entropy`…) mais **contre un
vocabulaire codé en dur** (8 types d'événements, une liste de techs
figée). Cela mesure l'émergence *relativement aux catégories que l'on a
choisies d'avance*. Or un système réellement ouvert invente des catégories
qu'on n'avait **pas** anticipées : toute ontologie fixe finit par saturer
et devient aveugle à la nouveauté pendant que le système, lui, continue
d'innover.

**Règle d'émergence respectée** : le mètre ne nomme, ne privilégie, ne
scripte **aucune** catégorie. Son vocabulaire — le « motif » — est généré
**par le substrat lui-même** (quantification grossière de l'état physique
et physiologique d'un agent). Les motifs sont **découverts**, jamais
déclarés. C'est un approfondissement de la discipline ZERO_PRE_SCRIPT, pas
une entorse : on mesure l'émergence sans lui imposer notre grille.

---

## 2. Modèle — trois mesures ontology-free

### Le motif (vocabulaire auto-généré)

Pour chaque agent **vivant**, on encode un identifiant 64 bits :

```
motif = blake2b( 8 bins de pulsions ‖ bin de vitesse ‖ bin de voisinage )
```

- **8 pulsions** (`hunger, thirst, sleep, fatigue, thermal, pain, stress,
  loneliness`) — quantités du substrat (`engine.agent`), chacune ∈ [0,1]
  binnée sur `drive_levels` niveaux.
- **vitesse** `‖vel‖` binnée sur `[0, max_ref_speed_ms)`.
- **voisinage** : nombre d'agents dans `neighbor_radius_m`, saturé à
  `neighbor_levels-1`.

> ⚠️ **`hashlib.blake2b`, jamais `hash()` Python** : `hash()` est randomisé
> par processus (`PYTHONHASHSEED`) → non déterministe entre runs. blake2b
> donne un id stable, reproductible à l'octet près.

### (1) Nouveauté cumulée N(t)

Nombre de motifs **distincts jamais observés**. Un plateau de N(t) = espace
comportemental épuisé ; une N(t) qui monte régulièrement = signature
d'open-endedness.

### (2) Complexité par compression

Longueur `zlib` (niveau 6) d'une fenêtre glissante canonicalisée de la
distribution de motifs de la population. Approxime l'incompressibilité
(≈ complexité de Kolmogorov) du flux comportemental : un système qui
produit de la structure résistant à la compression produit de
l'**information**, pas du bruit.

> Note honnête : sur une fenêtre minuscule (un seul motif), l'overhead de
> framing zlib fait que `compression_ratio > 1`. Ce n'est pas un bug, c'est
> de la théorie de l'information. Le ratio ∈ (0,1] ne devient informatif
> qu'une fois la fenêtre remplie (cf. test `test_compression_full_window`).

### (3) Activité évolutionnaire de Bedau–Packard

- **A(t)** = activité cumulée (somme des usages des motifs *persistants*).
- **D(t)** = diversité = nb de motifs dont l'usage accumulé franchit
  `persistence_threshold` (distingue la persistance *adaptative* de la
  dérive neutre).
- **new_activity** = activité gagnée par les motifs nouvellement persistants
  dans la fenêtre.

> Variante seuil-de-persistance. Le modèle complet à *neutral shadow*
> (comparaison à un modèle nul) est noté comme travail futur.

---

## 3. API publique

```python
from engine.open_endedness import (
    OpenEndednessConfig, install_open_endedness,
    observe_open_endedness, open_endedness_summary,
    uninstall_open_endedness,
)

install_open_endedness(sim, OpenEndednessConfig(snapshot_every=256))
for _ in range(N):
    sim.step()                       # le step wrappé capture les snapshots
print(open_endedness_summary(sim))   # N(t), A(t), D(t), ratio, signature…
```

Patron d'observateur read-only identique à Wave 39 (épidémie) / Wave 40
(lignée) : `Config / Snapshot / History / State`, `install_X` idempotent
qui wrappe `sim.step`, `observe_X` pur lecture, `X_summary`, `uninstall_X`
qui restaure le `step` original.

---

## 4. Tests d'invariants

| Test                                   | Garantit                                              |
|----------------------------------------|-------------------------------------------------------|
| `test_quantize_unit_edges`             | Quantification clampe, jamais d'overflow de bin       |
| `test_observe_returns_snapshot`        | Snapshot sain (pop, ≥1 motif, sha256 64-hex)          |
| `test_observe_is_read_only`            | **Zéro mutation** du sim (arrays + tick gelés)        |
| `test_signature_stable_on_identical_state` | Même état ⇒ même signature                        |
| `test_cross_run_determinism`           | Même seed ⇒ même signature (blake2b, pas `hash()`)    |
| `test_novelty_monotonic_non_decreasing`| N(t) jamais décroissante                              |
| `test_compression_full_window`         | Ratio ∈ (0,1] une fois la fenêtre pleine              |
| `test_bedau_packard_persistence`       | A(t) ≥ 0 et ≥1 motif persistant après usage répété    |
| `test_full_run_determinism`            | Flux de snapshots identique sur deux runs même seed   |
| `test_install_idempotent_and_uninstall_restores_step` | Double install = un seul wrap ; uninstall restaure |

Smoke `p115` : 10 checks miroir + dump diagnostic.

---

## 5. Conformité STONE-AGE

- **Read-only strict** : `observe_*` ne touche jamais aux arrays de
  simulation ni au `tick` (testé). Le seul état écrit est le bookkeeping de
  l'observateur sous `sim._open_endedness_state`.
- **Aucune ontologie scriptée** : pas de « outil », « mot », « bâtiment ».
  Le motif est une quantification physique brute. On ne récompense ni ne
  guide aucun comportement — on **observe** seulement.
- **Aucun solveur analytique** : pas de modèle top-down de l'évolution ;
  juste de la comptabilité déterministe (ensembles, compteurs, zlib).
- **Déterminisme** : aucun RNG. blake2b + zlib + sha256, reproductible à
  l'octet près sur la même seed.

---

## 6. WORLD_VEILLE_COMBO

Combo interne — comblement de gap **méta-émergence** : le papier réclamait
une mesure d'open-endedness intrinsèque (indépendante de l'observateur)
absente jusqu'ici. Inspirations académiques intégrées conceptuellement :
nouveauté cumulée (lignée open-ended search), complexité-par-compression
(proxy Kolmogorov), statistiques d'activité évolutionnaire de
**Bedau–Packard**.

> **WORLD_VEILLE_COMBO** : aucun combo externe (comblement gap — mètre
> open-endedness vers VA forte)

---

## 7. Métriques Wave 45

```
PHYSICAL_SYSTEMS:
  eau:         ✓
  erosion:     ✓
  geologie:    ✓ (Wave 43 visuel + Wave 44 olfactif)
  atmosphere:  ✓
  biologie:    ⚙ WIP
  decouverte:  ✓
  world_model: ⚙ Wave 45 — méta-mesure open-endedness

EMERGENCE_OBSERVED (mètre ontology-free):
  mesures:                3 (nouveauté N(t), compression, Bedau–Packard)
  vocabulaire:            auto-généré (motif blake2b, jamais déclaré)
  determinisme:           signature sha256, reproductible à l'octet
  exemple run 4-fondateurs: N(t)=[1,2,3,4,5,5,6,6,6,6,6,6] (découverte→plateau)
  tests_added:            11 pytest + 10 smoke checks
  non_regression:         187/187 suite runtime verte

INVARIANTS: ✓ tous déclarés (read-only, déterministe, ontology-free)

NEXT (vers VA forte):
  Wave 46 candidate: décodeur génotype→phénotype héritable (clôture
  sémantique au sens de Pattee — le génome 256-d doit se décoder
  *de l'intérieur*, pas via une table externe).
```
