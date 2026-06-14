# Cap. C5 — `clay_outcrop` : découverte émergente de l'argile

**Date** : 2026-06-14 · **Type** : capacité agent (5ᵉ, pas un observateur) ·
**Couche** : World/Substrate · **Smoke** : `p137` (7/7) ·
**Tests** : `tests/test_clay_outcrop.py` (20) + contrat cross-langage (+1)

> Veille du jour : [`docs/veille/2026-06-14_VEILLE_clay_outcrop.md`](../veille/2026-06-14_VEILLE_clay_outcrop.md)

---

## Pourquoi

C1 a livré le **minerai**, C2 la **pierre taillable**, C3 l'**eau potable**, C4 le
**combustible** (amorce énergétique). La docstring même de C4 désigne le maillon
suivant : « feu durable → **four en argile** + charbon → fusion → métallurgie ».
Or **l'argile elle-même restait muette** :

- la géologie portait le schiste argileux (`shale` = *clay_consolidated*) en
  surface partout, sans aucun signal exploitable ;
- la crate Rust `genesis-geology` réservait depuis Wave 43 un `Mineral::FineClay`
  (« Plastic clay suitable for pottery / brick », couleur `[180,140,110]`) —
  **orphelin** : le contrat cross-langage le notait explicitement *« Python uses
  rock_type/clay vocabulary, no catalogue mineral of this name »*.

L'argile est la **clé de voûte** stone-age : le **récipient** qui contient l'eau
potable (C3), le **four** qui contient le feu (C4), le **creuset** qui contient le
métal fondu, la **brique** qui bâtit. C'est le matériau qui *contient* tous les
autres — et donc le déverrouilleur émergent de la poterie, du stockage, de la
métallurgie.

## Ce que fait la capacité

`engine.clay_outcrop` rend l'**affleurement d'argile** perceptible, sans rien
scripter. Un agent ne *sait* pas qu'on en fait des pots : il **VOIT** une berge de
terre lisse beige-ocre, la **malaxe** (plastique ⇒ tient la forme), la sèche, la
**cuit** — la céramique émerge.

### Combo veille 1+1>2

- **D1 — hiérarchie de grade** (comme le rang houiller de C4) :
  - `shale` (source `lithology`, topsoil quasi-ubiquitaire) → **argile schisteuse**,
    grade *brique* (`pottery_grade = 0.45`) : se façonne, durcit, mais reste poreux.
    Explique que la poterie ait été inventée indépendamment d'innombrables fois.
  - `fine_clay` (source `ore`, kaolinite résiduelle, plus rare) → **argile
    plastique**, grade *céramique* (`pottery_grade = 0.85`) : cuite, elle vitrifie
    en poterie durable et étanche → seul grade `ceramic_grade` (creuset / four de
    fusion). C'est le `FineClay` du crate Rust, tell `(180,140,110)` **byte-exact**.
- **D2 — porte de plasticité (limites d'Atterberg 1911)** sur l'humidité ambiante :
  - `ambient < PLASTIC_LIMIT (0.18)` → `too_dry_to_shape` (friable ; mouiller & corroyer) ;
  - `PL ≤ ambient ≤ LIQUID_LIMIT (0.55)` → `workable_now` (plastique, tient la forme) ;
  - `ambient > LL` → `too_wet_slurry` (boue qui flue ; drainer & sécher).

  C'est le pendant **inversé** de la porte d'humidité de C4 : le combustible veut
  être **sec** pour brûler, l'argile veut être **humide** (juste ce qu'il faut)
  pour se façonner. L'humidité vient du **même** substrat que C4 (biome +
  `chunk.water`) → une seule vérité, deux lectures (SYSTÈME A hydrologie × SYSTÈME C
  géologie × SYSTÈME F feu de C4 qui transforme l'argile crue en céramique).

### « Le monde ne ment jamais »

Un indice n'est émis QUE si l'argile existe réellement dans la même colonne
`chunk_geology` que `mine_at` : `lithology` ⇒ couche peu profonde `rock_type ==
"shale"` ; `ore` ⇒ couche peu profonde avec `fine_clay` ≥ seuil de visibilité.
`workable_now` ⇒ humidité dans la fenêtre PL→LL. `ceramic_grade` ⇒ grade ≥ seuil.
Les trois états d'humidité sont mutuellement exclusifs et exhaustifs. Réciproque
volontairement faible (un lit sous 50 m de grès ne trahit rien en surface) →
émergence préservée (pas de carte des gîtes). `shape_preview` est un **oracle non
mutant** : `can_shape` vrai seulement si argile réelle + fenêtre plastique → le
mensonge (argile sèche *vue* mais infaçonnable) rendu visible.

## Émergence & moratoire

**Émergence absolue** : on rend l'argile et sa plasticité détectables, jamais
« fais un pot ». **Capacité, pas observateur** : aucun hook `sim.step`, coût tick
nul (cues paresseux mémoïsés) → conforme au moratoire observateurs (Wave-64+).
Déterminisme pur (`prf_rng` via `chunk_geology` + biome + `chunk.water`),
bit-identique même-seed.

## Garde-fou ADR-0007 (cross-langage)

C5 **ferme l'orphelin `FineClay`** :
1. ajout d'un vrai `fine_clay` (kaolinite `Al2Si2O5(OH)4`) au catalogue Python
   (appendu en fin de `MINERALS` → `MINERAL_INDEX` stable) ;
2. `PY_TO_RUST` enrichi `fine_clay → FineClay` (sorti de `RUST_ONLY`) ;
3. tell `(180,140,110)` verrouillé **byte-exact** ⇔ `Mineral::FineClay::surface_color()`
   — 3ᵉ référence couleur après malachite (cuivre) et charbon.

Risque de perturbation de `_select_ore_mix` par le nouveau minéral : **vérifié nul**
— affinité `fine_clay` exclut les déserts (n'entre pas en concurrence avec le monde
aride gossan/soufre de C1) ; C1/C2/C3 smokes verts, suite pytest verte.

## Validation

- `tests/test_clay_outcrop.py` : 20 tests (hiérarchie/seuils, tell byte-exact,
  dérivation pure, porte d'Atterberg dry/workable/slurry, monde ne ment jamais
  synthétique + réel seed `0xC1A7`, `shape_preview` non mutant, `best_clay_near`
  filtres, déterminisme, install idempotent).
- `tests/test_geology_cross_language_contract.py` : +1 (`test_fine_clay_tell_is_byte_exact`).
- `scripts/p137_clay_outcrop_smoke.py` : 7/7 sur monde Genesis réel (seed `0xC1A7` :
  144 chunks, 123 kaolin + 21 schiste, 123 céramique, 0 violation).
- Makefile `validate-all` + CI smoke list : `p137` ajouté.

## Gap honnête

- La diagenèse argile → schiste → ardoise (lithification) n'est pas simulée (les
  deux grades sont des matériaux distincts du catalogue, pas un continuum).
- La levigation / le tri granulométrique (préparation réelle de la pâte) n'est pas
  modélisé : le grade est intrinsèque au matériau.
- Ne ferme **aucun** item Rust Phase A/B (D5-wiring reste dû ; `cargo` absent →
  CI = vérité). C'est une capacité du **runtime Python live**.
