# Veille technologique — 2026-06-15 · WORLD REALISM SYSTEM v2.0 — amorçage du feu

**Mode :** Substrate-engineer · veille-first · run automatique (tâche planifiée, user absent).
**Sortie :** informe la **Cap. C7 `fire_ignition`** — l'affordance d'amorçage du feu
par l'agent (briquet à pyrite / archet à feu). Veille du second deliverable du jour
(la veille du matin `2026-06-15_VEILLE.md` portait ADR-0008 + garde-fou D8).

> Ordre respecté : **VEILLE → COMBO → CODE → PUSH**. La veille a *confirmé* la
> physique (pyrite pyrophorique, méthode d'Ötzi, seuils d'humidité) et n'a trouvé
> aucune technique 2026 qui rende l'affordance d'amorçage obsolète.

---

## Pourquoi le feu, aujourd'hui

C1→C6 ont rendu *perceptibles* les **matières** de l'âge de pierre (minerai, pierre
taillable, eau, combustible, argile, calcaire). Mais **presque toutes demandent un
feu pour devenir outil** : fondre le cuivre (C1), brûler le combustible (C4), cuire
l'argile en céramique (C5), calciner le calcaire en chaux (C6). Sans amorçage *par
l'agent*, ces capacités restaient des matières inertes. `engine.wildfire` (Wave 14)
modélise le feu **spontané** (foudre + propagation Rothermel) et note lui-même que
l'agent doit *déduire* que « le silex frappé produit la même chose en petit » — mais
**aucun signal de substrat** ne disait, par site, si un humain *peut* allumer un feu
ici, et comment. **Le feu est la voûte qui ferme l'arc C1→C6.**

---

## Recherches (axes World Realism System)

### Axe 5/6 — Découverte agent & physique de l'amorçage (cœur du jour)
- **Pyrite + silex = la plus ancienne production de feu connue.** Site néandertalien
  de Beeches Pit / Suffolk (~400 ka) : sol brûlé + bifaces de silex fire-cracked +
  **deux fragments de pyrite de fer** frappés au silex. Dizaines de bifaces (France,
  dès ~50 ka) portent des traces d'usure de percussion sur pyrite.
- **Ötzi (3350–3105 av. J.-C.)** transportait **silex + pyrite + amadou de polypore**
  — exactement le modèle PERCUSSION codé (source d'étincelle + percuteur + amadou).
- **Mécanisme (confirmé)** : le silex dur **cisaille** la pyrite en particules
  microscopiques de FeS₂ ; *pyrophoriques*, elles s'oxydent instantanément à l'air
  (énorme ratio surface/volume) en libérant une chaleur trop rapide pour se
  dissiper → gerbe d'étincelles chaudes. ⇒ pyrite = **source d'étincelle**, silex =
  **percuteur** (jamais l'inverse : silex-sur-silex n'étincelle quasi pas).
- **Marcasite** (polymorphe orthorhombique de FeS₂) est *encore plus* efficace que
  la pyrite (plus friable). Non présente au catalogue → modélisée via `pyrite`
  (même FeS₂), noté dans le code.
- **Friction (archet/drille)** : seconde famille universelle, *sans minéral*, mais
  **plus exigeante en sécheresse** (un amadou humide tue la braise) — d'où le second
  seuil, plus strict.

### Axe E — Combustible, humidité & seuil d'inflammabilité
- **Humidité du combustible = facteur de flammabilité dominant** (la flammabilité
  chute quand FMC monte). Feux de **prairie méditerranéenne** surtout à **FMC < 35 %**
  ; LFMC < 79 % pour grands feux. ⇒ valide (a) le gating par humidité, (b) la
  **prairie/savane sèche comme amadou canonique**, (c) deux seuils étagés.

### Axe 1/2 — World models & simulation feu
- L'état de l'art « feu » (FSim, Random-Forest ignition probability 2025, ABM
  fire/ember/tree, Rothermel) porte sur la **propagation** et le **risque** de
  *wildfire* — **pas** sur l'**affordance d'amorçage anthropique**. Aucune technique
  ne supplante un signal de substrat « peut-on faire du feu ici, et comment ». La
  capacité comble un trou réel sans réinventer la propagation (déjà Wave 14).

### Axe 3 — Géologie / minéraux
- Aucune nouvelle donnée requise : la pyrite est **déjà** semée par `engine.geology`
  (`_select_ore_mix`, rareté 0.20, biomes tempéré/prairie/savane/boréal, peu
  profonde) et **déjà surfacée** par C1 `surface_mineralization` (group `gossan`).
  Le silex est **déjà** modélisé par C2 `lithic_outcrop` (quartz + `CHERT_BONUS` en
  hôte carbonaté). ⇒ **rien à télécharger, rien à ajouter au catalogue.**

### Axe 4 / CVE
- Hors-scope (cargo-less, Python pur ; cf. `reference_env_no_cargo`). Aucune CVE
  pile applicative pertinente ce jour.

---

## WORLD_VEILLE_REPORT

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-06-15"
  duree_recherche: "~25 min (3 axes web ciblés + relecture substrat interne)"

  decouvertes:
    - id: D1
      techno: "Pyrite/marcasite (FeS2) pyrophorique — percussion strike-a-light"
      source: "en.wikipedia.org/wiki/Fire_making ; rockngem.com fire-makers ; Beeches Pit ~400ka"
      telecharge: false
      applicable_a: "Cap. C7 fire_ignition — voie PERCUSSION (source étincelle=pyrite, percuteur=silex)"
      gain_estime: "+1 phénomène naturel (amorçage anthropique) ; débloque la chaîne C1/C4/C5/C6 (fonte/cuisson/calcination)"
      action: COMBO_TODAY
    - id: D2
      techno: "Seuil d'humidité d'inflammabilité (FMC<35% prairie) — deux familles d'amorçage"
      source: "ncbi PMC6171885 ; nwcg probability-of-ignition"
      telecharge: false
      applicable_a: "gating tinder : PERCUSSION_DRY=0.58 (étincelle chaude) vs FRICTION_DRY=0.45 (braise marginale)"
      gain_estime: "distribution physiquement étagée (prairie/savane allumables ; boréal/forêt humide non)"
      action: COMBO_TODAY
    - id: D3
      techno: "Modèles feu 2025 (FSim, RF ignition, ABM fire/ember/tree, Rothermel)"
      source: "research.fs.usda.gov FSim ; sciencedirect S1574954125003346"
      telecharge: false
      applicable_a: "wildfire propagation (déjà couvert Wave 14) — PAS l'affordance d'amorçage"
      gain_estime: "aucun delta : confirme que l'affordance anthropique est un trou non couvert ailleurs"
      action: REJETÉ
      raison_si_rejet: "porte sur la propagation/risque, pas sur 'peut-on faire du feu ici' ; Wave 14 suffit pour la propagation"

  cve_stack:
    - "aucune CVE critique aujourd'hui (env Python pur, cargo-less)"

  paper_du_jour:
    titre: "Neandertal fire-making technology inferred from microwear analysis (Sorensen et al., Sci. Rep. 2018)"
    url: "https://www.nature.com/articles/s41598-018-28342-9"
    technique: "trace d'usure pyrite-sur-silex ⇒ la percussion est la plus ancienne production de feu — ancre C7 dans l'âge de pierre"
    effort: "0 h (confirmation, pas d'intégration de code tiers)"

  world_model_updates:
    cosmos: "aucune nouveauté applicable au hot-path Genesis ce jour"
    genie3: "aucune"
    autre: "aucun world model n'adresse l'amorçage anthropique — affordance de substrat, lookup 1-étape"

  combo_retenu:
    techno: "D1 (pyrite percussion) × D2 (seuils FMC) — composés sur C1(pyrite gossan) + C2(silex)"
    cible: "engine.fire_ignition (Cap. C7) — nouvelle capacité de substrat"
    gain: "+1 phénomène ; débloque l'actionnabilité de C1/C4/C5/C6 ; 0 coût tick ; 0 nouveau tell (garde-fou D8 respecté par composition)"
    adr_requis: false   # réutilise ADR-0005 (paper-L1 Predictor) + ADR-0007/0008 (frontière) inchangés
```

---

## Décision

**COMBO retenu → CODÉ ce jour.** `engine.fire_ignition` (Cap. C7) expose l'affordance
d'amorçage par **deux voies physiques honnêtes** :

1. **PERCUSSION** — pyrite (FeS₂ pyrophorique, déjà gossan C1) frappée par un
   **percuteur dur** (silex/quartz, pétrologie C2 réutilisée *verbatim*) sur un
   **amadou assez sec** (humidité ≤ 0.58).
2. **FRICTION** — sans minéral, mais **amadou très sec** (≤ 0.45) + combustible fin.

Effet **1+1>2** : géologie (pyrite + silex, SYSTÈME C) × hydrologie de surface
(`chunk.water`, SYSTÈME A) × biome combustible (SYSTÈME E). **N'introduit aucun
nouveau tell minéral** (pas de `_PROFILE`, pas d'entrée `PY_TO_RUST`) : il *compose*
des tells déjà classés cross-langage — décision consciente, asservie par
`test_fire_ignition.test_introduces_no_new_tell`. Distinct de `wildfire` (feu
spontané + propagation) — **complémentaire**, pas doublon.

**Livré :** `engine/fire_ignition.py` · `scripts/p139_fire_ignition_smoke.py` (7/7)
· `tests/test_fire_ignition.py` (20/20). Déterministe, coût tick nul.

## Sources
- https://en.wikipedia.org/wiki/Fire_making
- https://www.rockngem.com/examining-pyrite-iron-and-flint-the-fire-makers/
- https://en.wikipedia.org/wiki/Fire_striker
- https://www.nature.com/articles/s41598-018-28342-9 (Neandertal fire-making, microwear)
- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6171885/ (fuel-moisture ignition thresholds)
- https://www.nwcg.gov/publications/pms437/fuel-moisture/probability-of-ignition
- https://research.fs.usda.gov/firelab/articles/fsim-and-expanding-uses-fire-risk-simulation
