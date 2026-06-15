# Cap. C7 — `fire_ignition` : amorçage émergent du feu (la voûte de l'arc C1→C6)

**Date** : 2026-06-15 · **Type** : capacité agent (7ᵉ, pas un observateur) ·
**Couche** : World/Substrate · **Smoke** : `p139` (7/7) ·
**Tests** : `tests/test_fire_ignition.py` (20)

> Veille du jour : [`docs/veille/2026-06-15_VEILLE_fire_ignition.md`](../veille/2026-06-15_VEILLE_fire_ignition.md)

---

## Pourquoi — la voûte qui ferme l'arc C1→C6

C1→C6 ont rendu *perceptibles* les **matières** de l'âge de pierre : le minerai (C1),
la pierre taillable (C2), l'eau potable (C3), le combustible (C4), l'argile (C5), le
calcaire (C6). Mais **presque toutes demandent ensuite un feu** pour devenir outil :

- **C1** cuivre vert → il faut le **fondre** (feu) ;
- **C4** combustible → il faut l'**allumer** (feu) ;
- **C5** argile → il faut la **cuire** en céramique (feu) ;
- **C6** calcaire → il faut le **calciner** en chaux (feu).

Sans amorçage *par l'agent*, ces capacités restaient des **matières inertes** :
l'agent voit le cuivre mais ne peut pas le fondre, voit l'argile mais ne peut pas la
cuire. **Le feu est la voûte qui rend l'arc C1→C6 actionnable.**

Or l'amorçage *anthropique* restait muet. `engine.wildfire` (Wave 14) modélise le feu
**spontané** (foudre → ignition → propagation Rothermel) et note lui-même, dans son
docstring, que l'agent doit *déduire* que « le silex frappé produit la même chose en
petit ». Mais **aucun signal de substrat** ne disait, *par site*, si un humain *peut*
allumer un feu ici, et *comment*. C7 comble ce trou. **Ce n'est pas un doublon de
`wildfire`** : celui-ci allume le monde (foudre + propagation), celui-ci expose
l'**affordance d'amorçage anthropique** (briquet à pyrite, archet à feu) —
complémentaires.

## Ce que fait la capacité

`engine.fire_ignition` rend l'**affordance d'amorçage** perceptible, sans rien
scripter. Un agent ne *sait* pas qu'on fait du feu : il **VOIT** une pierre
brun-rouille qui jette des étincelles quand on la frappe (pyrite), une pierre dure et
vitreuse pour la percuter (silex), de l'herbe sèche qui prend ; ou il **frotte**
longuement deux bois sur un amadou très sec. Le briquet, l'archet à feu, le foyer, la
cuisson — toute la chaîne — émergent.

### Combo veille 1+1>2 — deux voies physiques honnêtes et **distinctes**

La préhistoire réelle connaît deux familles de production du feu, toutes deux
modélisées depuis le **substrat seul** (veille confirmée) :

- **D1 — PERCUSSION (briquet à pierre / strike-a-light).** On frappe un nodule de
  **pyrite** (FeS₂ — sulfure de fer *pyrophorique* : l'éclat arraché s'oxyde
  instantanément à l'air en jetant une étincelle, énorme ratio surface/volume) avec
  une **pierre dure** (silex/quartz). C'est la **plus ancienne production de feu
  connue** (site néandertalien de Beeches Pit ~400 ka : sol brûlé + bifaces de silex
  *fire-cracked* + 2 fragments de pyrite ; méthode d'Ötzi ~3300 av. J.-C. : silex +
  pyrite + amadou de polypore). Conditions :
  - source d'étincelle = **pyrite** peu profonde (`ore_mix ≥ MIN_VISIBLE_FRACTION`,
    profondeur ≤ `MAX_IGNITER_DEPTH_M = 6 m`) — exactement le minéral du chapeau de
    fer (gossan) **déjà surfacé par C1** ;
  - **percuteur** = pierre dure (`knap_quality ≥ STRIKER_MIN_QUALITY = 0.40`) — la
    **pétrologie de C2 réutilisée *verbatim*** (`lo._candidates_in_layer`,
    `lo._has_carbonate_host`), amélioration silex/chert `CHERT_BONUS` incluse ;
  - **amadou** *assez* sec (`ambient_moisture ≤ PERCUSSION_DRY_MOISTURE = 0.58`).
- **D2 — FRICTION (archet/drille à feu).** Aucune pierre : échauffement par
  frottement d'un foret de bois jusqu'à la braise. Universelle (pas de pyrite
  requise) mais **plus exigeante en sécheresse** : un amadou humide tue la braise.
  Conditions : combustible fin (`fine_fuel ≥ FRICTION_FUEL_FLOOR = 0.45`) + amadou
  *très* sec (`ambient_moisture ≤ FRICTION_DRY_MOISTURE = 0.45`).

Le **second seuil, plus strict** (0.45 < 0.58), est le cœur physique : une étincelle
chaude prend sur un amadou plus humide qu'une braise marginale de friction. Effet
**1+1>2** : géologie (pyrite + silex, SYSTÈME C) × hydrologie de surface
(`chunk.water`, SYSTÈME A) × biome combustible (SYSTÈME E). Une seule vérité de
substrat (biome + `chunk.water`), lue par **C4 (sec), C5 (plastique), C6 (sain),
C7 (amadou sec)**. La flammabilité gouvernée par l'humidité du combustible est
attestée (feux de prairie à FMC < 35 %) → la **prairie/savane sèche** est l'amadou
canonique ; le boréal/forêt humide ne s'allume pas.

### « Le monde ne ment jamais »

Un site n'est déclaré `can_ignite` QUE si les ingrédients existent réellement dans la
même colonne `chunk_geology` que `mine_at` : `can_percussion` ⇒ pyrite réelle peu
profonde **et** percuteur réel **et** amadou sec ; `can_friction` ⇒ combustible fin
**et** humidité ≤ seuil friction. Le site porte `spark_depth_m` : aller frapper là
**rend** vraiment cette pyrite. Réciproque volontairement faible (une pyrite sous
50 m de grès ne s'allume pas) → émergence préservée. `ignition_preview` est un
**oracle non mutant** qui nomme l'ingrédient manquant — le mensonge rendu visible :
une **prairie détrempée** *paraît* être de l'amadou (`tinder_available`) mais une
étincelle n'y prend pas (`tinder_state = DAMP`).

## Émergence & moratoire

**Émergence absolue** : on rend la pierre-à-étincelle, le percuteur et la sécheresse
de l'amadou détectables, jamais « frappe la pyrite sur le silex au-dessus de l'herbe
sèche pour faire du feu » — l'agent doit *apprendre* cette corrélation en agissant.
**Capacité, pas observateur** : aucun hook `sim.step`, coût tick nul (cues paresseux
mémoïsés) → conforme au moratoire observateurs (Wave-64+). Déterminisme pur
(`prf_rng` via `chunk_geology` + biome + `chunk.water`), bit-identique même-seed.

## Garde-fou D8 (cross-langage) — respecté par **COMPOSITION**, pas contourné

Contrairement à C2/C4/C5/C6, C7 **n'introduit AUCUN nouveau tell minéral** :

1. **pas de table `_PROFILE`** — donc le garde-fou D8 (`test_geology_cross_language_
   contract.py`, qui *glob* `engine/*_outcrop.py` portant un `_PROFILE`) ne le vise
   pas, et **n'a pas à le viser** : le fichier n'est pas un `*_outcrop.py` (c'est une
   *affordance composite*, pas un affleurement) ;
2. **aucune entrée `PY_TO_RUST` / `PY_CATALOGUE_ONLY` créée** : C7 *réutilise* des
   tells **déjà classés** — la **pyrite** (source d'étincelle = exactement le minéral
   du group `gossan` que C1 `surface_mineralization` surface) et le **percuteur**
   (silex/obsidienne/quartzite, pétrologie C2) ;
3. la décision est **consciente et asservie** par `test_introduces_no_new_tell` :
   il vérifie l'absence de `_PROFILE`, que chaque `_SPARK_MINERALS` est un minéral
   réel **et** un tell gossan de C1, et que le percuteur sort du `_PROFILE` de C2.

C7 **n'aggrave donc pas le treadmill** que l'audit J+4 craignait (pas de 7ᵉ minerai
muet parallèle) : il **débloque l'actionnabilité** des six capacités précédentes au
lieu d'empiler une matière de plus.

## Validation

- `tests/test_fire_ignition.py` : 20 tests (seuils ordonnés, **composition sans
  nouveau tell**, percussion pyrite+silex, pyrite sans percuteur → friction, pyrite
  profonde / fraction faible → pas de percussion, friction sans minéral, **porte des
  deux seuils** forêt tempérée étincelle-oui/friction-non, eau stagnante éteint un
  site, masquage océan/détrempé/désert/boréal, monde ne ment jamais synthétique +
  réel seed `0xBEEF`, `ignition_preview` non mutant + nomme l'ingrédient manquant,
  `best_firesite_near` préfère/filtre la percussion, déterminisme, install idempotent).
- `scripts/p139_fire_ignition_smoke.py` : 7/7 sur monde Genesis réel (seed `0xBEEF`,
  prairie : 144 chunks ignitables = 61 percussion + 144 friction, 0 violation).
- Makefile `validate-all` + CI smoke list : `p139` ajouté.
- Suite complète : **pytest 536/536** (+1 skip pré-existant).

## Gap honnête

- La **cinétique de combustion**, l'**entretien du foyer** et le passage
  amadou→brindilles→bois ne sont pas simulés : C7 est une **affordance binaire
  d'amorçage** (peut-on partir un feu, et comment), pas une flamme physique — la
  propagation reste à `wildfire` (Wave 14).
- Le `fine_fuel` (charge d'amadou) est une propriété **statique du biome**, pas une
  biomasse dynamique : un surpâturage ou une saison sèche n'abaissent pas encore le
  load localement.
- La **marcasite** (polymorphe FeS₂ plus efficace, absente du catalogue) est
  modélisée via `pyrite` (même formule) — distinction non faite.
- Ne ferme **aucun** item Rust Phase A/B (D5-wiring reste dû ; `cargo` absent →
  CI = vérité). C'est une capacité du **runtime Python live**.
