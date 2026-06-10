# Veille technologique — Genesis Engine (Wave 63)

**Date :** 2026-06-10 (2ᵉ cycle de la journée — run automatisé Substrate)
**Auteur :** Routine Substrate (veille-first, cycle Genesis)
**Cadre :** ÉTAPE 0 du cycle « veille → combo → décision → code → push ». Aucune
ligne de code n'a été écrite avant la fin de cette veille (règle d'or).
**Contraintes respectées :** factuel et sourcé, pas de hype. La veille a informé
le choix de code du jour (**Wave 63 — concavité de chenal / χ-steepness**).

> Le 1ᵉʳ cycle du jour a livré la **Wave 62 — hypsométrie** (axe aire–altitude,
> identité de Pike-Wilson). Voir [`2026-06-10_VEILLE.md`](2026-06-10_VEILLE.md).
> Ce 2ᵉ cycle attaque la pièce complémentaire : la **loi pente–aire** du réseau
> de chenaux, le 2ᵉ descripteur fluvial canonique encore non observé.

---

## Contexte projet (rappel)

État lu dans `PROJECT-STATUS.md` après Wave 62. Score réalisme Terre global
**~78,9 %**, cible **80 %**. Gap géologie/relief : **descripteurs de la forme du
réseau fluvial** (la Wave 49 quantifie la topologie — ordres de Strahler, Horton,
densité de drainage ; la Wave 62 quantifie l'aire–altitude — hypsométrie ; il
manque la **relation pente–aire**, signature de l'incision par stream-power).

---

## Recherches (6 axes du cahier des charges Substrate)

### Axe 1 — Simulation hydraulique & érosion

- **Loi de Flint / relation pente–aire** : `S = k_s · A^(−θ)` où `θ = m/n` est
  l'**indice de concavité** et `k_s` l'**indice de raideur** (steepness). À
  l'état stationnaire détachement-limité sous soulèvement uniforme, le modèle
  stream-power `E = K·A^m·S^n` prédit une fourchette **étroite et théoriquement
  fondée : 0,4 < θ < 0,6** (la plupart des chenaux gradés). C'est l'invariant
  falsifiable recherché. Sources : Wobus et al. 2006, Kirby & Whipple 2012,
  ESurf « How concave are river channels? » (2018).
- **Méthode χ (chi) intégrale — Perron & Royden 2013** : transforme la longueur
  de chenal en variable `χ = ∫_{xb}^{x} (A0/A(x'))^θ dx'` normalisée par l'aire
  drainée. À l'état stationnaire, `z` est **linéaire en χ**, de pente = la
  raideur normalisée **ksn**. Avantage décisif sur la régression pente–aire
  brute (très bruitée car dérivée locale) : χ travaille sur l'**élévation**
  directement, donc bruit fortement réduit (Mudd et al. 2014, JGR-ES, cadre
  statistique ; outils LSDTopoTools / ChiProfiler / TopoToolbox).

### Axe 2 — World models & cohérence physique neuronale

- **NVIDIA Cosmos 3** (rapport technique 2026-06-01) : world model *omnimodal*
  pour Physical AI (20 T tokens). **Genie 3** (DeepMind) : mondes 3D interactifs
  temps réel 24 fps. Tous deux **génératifs pixel/vidéo**, orientés données
  d'entraînement robotique — **pas** des solveurs causaux déterministes.
  → **REJETÉ** pour le tick (cf. décisions de veille des 06-06 et 06-10) ;
  reste au backlog « initialisation macro cohérente », jamais sur le cœur
  déterministe.

### Axe 3 — Géologie procédurale & minéraux

- Confirme que **`flow_acc` (aire drainée, en mailles) est déjà émergent** dans
  `world_genesis` (`_flow_accumulation_topological`), aux côtés de `flow_dir`
  (D8), `river_mask`, `elevation_m`. Aucun nouveau substrat requis : la loi
  pente–aire se **mesure** sur ces champs, elle ne s'**impose** pas.

### Axe 4 — Thermodynamique / atmosphère / météo

- GraphCast/GenCast/NeuralGCM : météo neuronale globale. Hors-scope du combo du
  jour (géologie). Backlog inchangé.

### Axe 5 — Biologie / végétation / écosystème

- Sans nouveauté applicable au combo géologie du jour. Backlog inchangé.

### Axe 6 — Bevy / WGPU / crates Rust + CVE stack

- **CVE stack** : aucune CVE critique applicable. Recherche `numpy CVE 2026 /
  Python 3.14` : pas d'avis 2026 nouveau ; le seul CVE NumPy historique
  pertinent (CVE-2019-6446, désérialisation `.npy`) **ne s'applique pas**
  (Genesis ne charge aucun `.npy` non fiable). Stack propre.
- `numpy` / `np.trapezoid` / `np.searchsorted` suffisent — aucune nouvelle
  dépendance requise pour la Wave 63 (régression OLS en forme close).

---

## SYNTHÈSE VEILLE (format routine)

```
DÉCOUVERTE_1: Loi de Flint pente–aire (S = k_s·A^-θ, θ=m/n ∈ 0,4–0,6 état stationnaire) · Géologie/relief · descripteur fluvial canonique manquant + invariant falsifiable étroit
DÉCOUVERTE_2: Méthode χ intégrale (Perron & Royden 2013 ; Mudd 2014) · Géologie/relief · ksn à faible bruit (z vs χ linéaire à l'équilibre) — complément moderne de D1, même grandeur (m/n)
DÉCOUVERTE_3: NVIDIA Cosmos 3 / Genie 3 (world models physiques 2026) · World · génératifs pixel → REJETÉ pour le tick déterministe, backlog init macro
CVE_ACTIVES: aucune critique applicable (pas d'avis numpy/Python 3.14 2026 ; CVE-2019-6446 hors-scope, aucun .npy non fiable chargé)
PAPER_DU_JOUR: Perron & Royden 2013 « An integral approach to bedrock river profile analysis » — applicable J0 (transformée χ déterministe, read-only)
```

---

## COMBO-GENESIS (ÉTAPE 1)

```
COMBO_RETENU: Loi de Flint (D1) × Méthode χ (D2) sur le réseau D8 émergent (flow_dir + flow_acc + elevation_m)
  Gain:        descripteur pente–aire manquant + ksn χ faible bruit — géologie 73 → 74, global ~79,0 %
  Coût:        ~2 h · complexité 2/5 · risque régression 1/5 (pur read-only, 0 RNG)
  Couche:      World (géologie/relief)
  Intégration: nouvel observateur engine.concavity_observer — régression log-log pente–aire (θ, k_s, R²)
               + transformée χ par balayage topologique amont (χ=0 au niveau de base, z~χ linéaire),
               invariant pivot = récupération exacte de la loi de puissance + linéarité χ–z
  ADR requis:  NON (continue la série d'observateurs Waves 49/57/59/61/62, aucune décision d'archi nouvelle)
```

```
COMBO_BACKLOG:
  - Cross-check « θ qui linéarise au mieux χ–z == m/n pente–aire » (recherche sur θ) → extension Wave 64+
  - Variante par bassin versant (watershed_id) pour ksn par bassin → backlog
  - Érosion GPU transitoire (WGSL) → backlog géologie de longue date
COMBO_REJETÉ:
  - Cosmos 3 / Genie 3 → génératifs pixel, pas causaux déterministes (incompatibles cœur tick)
```

---

## Décision

Les DÉCOUVERTE_1 (loi de Flint) et DÉCOUVERTE_2 (méthode χ) sont **deux mesures
de la même grandeur émergente** (le rapport m/n d'incision) et se **renforcent**
(la χ corrige le bruit de la régression pente–aire brute). Fusion en une tâche
enrichie → **Wave 63 — concavité de chenal / χ-steepness** (cf.
[`docs/sprints/2026-06-10_Wave63_concavity.md`](../sprints/2026-06-10_Wave63_concavity.md)).
Read-only, déterministe, 0 RNG, conforme STONE-AGE (on lit le terrain émergent,
on ne script aucune loi).
