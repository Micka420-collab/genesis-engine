# Veille technologique — 2026-07-01 (World Realism System v2.0, étape 0)

> Veille-first. Recherche **avant** toute ligne de code. Genesis est *cargo-less*
> (Python 3.14 / numpy seul, ADR-0008), *no-LLM-brain* (ADR-0002), déterministe.
> Un combo n'est « intégrable aujourd'hui » que s'il respecte ces trois contraintes
> **et** l'émergence pure (0 phénomène scripté — [feedback emergence-only]).
>
> Axe du jour : **Substrate / hydrologie** (System A du prompt v2.0 — « Nappe
> phréatique variable », « lacs », « oasis », endorheic basins). On promeut la
> `DÉCOUVERTE_1` déjà notée le 2026-06-30 (Fill–Spill–Merge), en livrant d'abord
> sa **fondation topographique** (Priority-Flood) comme Wave World dédiée et
> **purement additive** — le garde-fou exact demandé au backlog P5 (ne pas toucher
> `engine.river_discharge` testé).

## Les 6 axes (prompt v2.0)

### Recherche 1 — Hydraulique & érosion  ✅ **cœur du jour**
- **Priority-Flood** (Barnes, Lehman & Mulla 2014, *Computers & Geosciences* ;
  arXiv [1511.04463](https://arxiv.org/abs/1511.04463) ; réf. C++
  [r-barnes/Barnes2013-Depressions](https://github.com/r-barnes/Barnes2013-Depressions)).
  Algorithme **optimal** de remplissage de dépressions + étiquetage de bassins :
  inonde le DEM **depuis les bords** via une file de priorité ; garantit que chaque
  cellule draine. O(n) entier / O(n log n) flottant, ~20 lignes de pseudo-code.
  La surface remplie `filled ≥ elev` ; `filled − elev` = **profondeur de lac** si
  la dépression se remplit jusqu'à son point de débordement (« depression storage
  capacity » — un produit DEM standard). **Applicable directement**, numpy + `heapq`,
  déterministe (tie-break par compteur d'insertion). → **COMBO_TODAY**.
- **Fill–Spill–Merge** (Barnes, Callaghan & Wickert 2020/2021, *Earth Surface
  Dynamics* 9, 105 ; [ESurf](https://esurf.copernicus.org/articles/9/105/2021/) ;
  NSF [par.10263903](https://par.nsf.gov/servlets/purl/10263903)). Extension
  **volume-fini** : distribue un ruissellement *donné* dans une **hiérarchie de
  dépressions** (forêt d'arbres binaires ; fill → spill over sills → merge en
  méta-dépressions), 86–2645× plus rapide que FlowFill. Produit des lacs
  **partiellement** remplis → endoréiques quand l'apport < capacité de débordement.
  **Backlog Wave 67** : nécessite l'apport routé de Wave 64 (`discharge_observer`).
  Priority-Flood d'abord fournit les *contenants* ; FSM les *remplira* ensuite.

### Recherche 2 — World models & cohérence neuronale
- Cosmos / Genie 3 / diffusion géo-cohérente : **aucune nouveauté applicable
  cargo-less aujourd'hui**. Restent gated (Niveau 2 du prompt, backlog).

### Recherche 3 — Géologie procédurale & minéraux
- **Aucune nouveauté** vs l'arc C1→C20 déjà livré. RichDEM (r-barnes) confirmé
  comme bibliothèque de référence DEM (mêmes auteurs que Priority-Flood) mais
  non-intégrée (dépendance externe évitée — numpy-seul).

### Recherche 4 — Thermodynamique / atmosphère / météo
- GraphCast / GenCast / FourCastNet : gated (poids neuronaux + non-déterminisme).
  L'orographie vivante (Waves 65/64/climate_biome) reste la voie cargo-less.

### Recherche 5 — Biologie & écosystème
- Rien de nouveau applicable aujourd'hui (Rothermel/wildfire déjà présent).

### Recherche 6 — Bevy / WGPU / crates Rust
- Gated (P1 scaffolding Rust — `cargo` absent, ADR-0008). Backlog P5 inchangé.

### CVE / stack
- Numpy-seul, sans sockets/asyncio, sans dépendance LLM/réseau dans l'arc.
  **CVE_ACTIVES : aucune critique pour l'arc Substrate aujourd'hui.**

## Validation « rien de plus récent ne supplante le plan »
Balayage 2025-2026 (Gualilán endorheic basin, Mu Us Sandy Land, Tibetan-Plateau
lake-volume, MERIT-Plus endorheic delineation) : la littérature récente **valide
l'importance** (les bassins endoréiques ≈ **20 % des terres** ; la *depression
storage* améliore la prédiction du débit) mais **ne supplante pas** Priority-Flood
comme algorithme. Plan **actuel et sain**.

## SYNTHÈSE VEILLE (format obligatoire)

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-07-01"
  duree_recherche: "~25 min"

  decouvertes:
    - id: D1
      techno: "Priority-Flood (Barnes/Lehman/Mulla 2014) — depression fill optimal"
      source: "https://arxiv.org/abs/1511.04463"
      telecharge: false   # algorithme réimplémenté numpy+heapq (pas de dépendance)
      applicable_a: "Substrate/hydrologie — System A (lacs, dépressions, endoréisme)"
      gain_estime: "réalisme: lacs & bassins endoréiques ÉMERGENTS depuis la seule topo"
      action: "COMBO_TODAY"

    - id: D2
      techno: "Fill–Spill–Merge (Barnes/Callaghan/Wickert 2021) — volume-fini"
      source: "https://esurf.copernicus.org/articles/9/105/2021/"
      telecharge: false
      applicable_a: "couplage Wave 64 discharge → remplissage partiel des dépressions"
      gain_estime: "lacs vivants (apport réel), endoréisme dynamique, sel concentré"
      action: "BACKLOG_ROADMAP"   # Wave 67 — nécessite l'apport routé (couple code testé)
      raison_si_rejet: "n/a (différé, pas rejeté)"

  cve_stack:
    - "aucune CVE critique pour l'arc Substrate (numpy-seul, no-socket, no-LLM)"

  paper_du_jour:
    titre: "Priority-Flood: An Optimal Depression-Filling and Watershed-Labeling Algorithm"
    url: "https://arxiv.org/abs/1511.04463"
    technique: "flood inward-from-edges via priority queue → filled surface; depth = filled - elev"
    effort: "~3 h · complexité 2/5 (pur, additif, déterministe)"

  world_model_updates:
    cosmos: "aucune"
    genie3: "aucune"
    autre: "RichDEM confirmé lib de réf DEM — non intégrée (numpy-seul)"

  combo_retenu:
    techno: "Priority-Flood depression/lake observer"
    cible: "nouveau module engine.lake_hydrology (Wave 66) — read-only sur world.elevation_m"
    gain: "n_lakes, aire/volume impoundé, lacs endoréiques (pits D8 intérieurs) — émergents"
    adr_requis: false   # observateur additif pur, non-mutant, pas de nouvelle frontière PY_TO_RUST
```

## Décision COMBO (étape 1)

| Question | Réponse |
|---|---|
| REMPLACE ou ÉTEND ? | **ÉTEND** — nouveau module additif ; ne touche **pas** `river_discharge`/`discharge_observer` (garde-fou P5 respecté). |
| Combinaison multiplicatrice ? | Oui : les **pits D8 intérieurs** que `world_genesis` marque déjà (`flow_dir==255`, `best_drop≤0`) mais que **personne ne mesure** deviennent des **lacs terminaux**. Le `discharge_observer` route l'eau vers ces puits comme si elle « quittait le domaine » ; Wave 66 révèle qu'elle **s'y accumule** (fondation de FSM/Wave 67). |
| Gain physique mesurable ? | Réalisme +2 (lacs & endoréisme) ; +1 type de forme émergente (lac endoréique / playa) ; invariant « surface d'un lac est **plane** » testable ; 0 violation causale (read-only). |
| Coût honnête ? | ~3 h · complexité 2/5 · risque régression **1/5** (module additif, aucun code testé modifié) · ADR **non requis**. |

**COMBO_RETENU** : Priority-Flood → `engine.lake_hydrology` (Wave 66), observateur
read-only, déterministe, émergent, cargo-less. Livré ce jour avec tests + smoke
`p174` + doc sprint FR.
