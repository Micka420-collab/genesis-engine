# Sprint 2026-06-29 (run 3) — D12 wire #9 : la boucle agent CUIT l'argile en poterie (consomme C9)

> **Type :** `feat(agentic/cognition)` / câblage d'arc. **Acte :** [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Suite de :** wire #7 C8 TEMPER, wire #8 C5 DIG (même jour). **9ᵉ bouchée → 9/20.**
> **JALON :** 1ʳᵉ capacité dont les intrants sont **les produits de deux autres wires** (argile DIG + feu IGNITE).

## Veille (obligatoire, avant code)

Règle d'or respectée. Recherche ciblée (cuisson céramique émergente ; chaînes de craft à deux
ingrédients ; Vintage Story / TerraFirmaCraft : argile→séchage→cuisson au four). **Apport :
validation de la direction** (transformation à deux intrants = saut qualitatif de la boucle agent),
pas de pivot. Aucune brique externe (cargo-less). **CVE : aucune.**

**COMBO_RETENU :** `utility-based action selection` × `C9 ceramic_firing` → 9ᵉ tranche, **la
transformation néolithique fondatrice**. Choisie parce qu'elle *consomme* enfin une matière qu'un
autre wire rend récoltable (DIG/C5 → `inv_clay`) à l'aide d'une compétence apprise (IGNITE/C7 →
`has_made_fire`) : l'arc se referme sur lui-même. Couche **Agentic**. Pas de nouvel ADR.

## La tranche livrée — l'arc se referme sur lui-même

Dans `cognition.decide()`, après `_seek_clay` : un agent qui **SAIT faire le feu**
(`mem.has_made_fire`) **ET porte de l'argile** (`inv_clay ≥ FIRE_CLAY_COST_KG`) et **perçoit** un
site de cuisson (`ceramic_firing.best_firing_site_near`, require_sound) marche jusqu'à lui et la
**CUIT** (`ActionKind.FIRE_CLAY = 26`) → la terre molle devient **céramique irréversible**
(`inv_ceramic`) ∝ `ware_quality` *réelle*. C'est la **1ʳᵉ bouchée dont les deux intrants viennent
de deux wires antérieurs** — jusqu'ici chaque wire était autonome ; ici la chaîne **argile→feu→pot**
vit dans la boucle.

**Le jalon en acte :** `apply_decision` **consomme** `inv_clay` (le vase façonné part au feu) et
**émet** `inv_ceramic` — le premier flux matière inter-capacités piloté par l'agent.

**Ordre dans `decide()` :** … → IGNITE → TEMPER → DIG(argile) → **FIRE_CLAY(poterie)** → GRIND →
MARK → EXPLORE.

### Le mensonge rendu visible #14 — l'inversion réfractaire

« La plus belle argile fait le meilleur pot » → **FAUX** sur un feu ouvert : un feu nu n'atteint
jamais la température d'un four, donc le **schiste** humble (terre cuite) cuit **sound** (vase
utilisable) tandis que la **kaolinite** plastique fine reste **sous-cuite** — crayeuse, se redélite —
et l'argile est **dépensée pour rien**. `best_firing_site_near(require_sound)` route vers le sound ;
cuire un site sous-cuit enseigne le mensonge **en agissant** (argile perdue, 0 pot). Un feu ouvert
ne **vitrifie** jamais (`watertight` toujours False) — il faudra un vrai four (bouchée future).

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (le wire n'ajoute aucun tell) | ✅ COMPOSE C5 × C7 ; `PY_TO_RUST` reste **15** |
| **D10** (mutation gelée à `geo.mine_at`) | ✅ FIRE_CLAY = transformation, **0 mutation géologie** (pas de `mine_at(` dans la branche) |
| **D9** (alternance) | ✅ `feat(cognition)`, câblage |
| **Dépendances honorées, pas scriptées** | ✅ gate sur `has_made_fire` **et** `inv_clay` — un agent sans feu OU sans argile ne cuit pas (le monde, pas un arbre tech) |
| **Hot-loop / Zéro-régression** | ✅ gate sur C9 installé ; `bootstrap` n'installe pas C9 → wire inerte par défaut |
| **Back-compat persistance** | ✅ `inv_ceramic` ajouté défensivement aux deux listes (comme `inv_clay`/`inv_pigment`) |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, 0 RNG |

**Nouvel état :** `ActionKind.FIRE_CLAY = 26` ; `AgentRegistry.inv_ceramic` (nouveau champ) ;
`EpisodicMemory.{known_kiln_locations, has_fired_pottery, last_ware_quality}`.

## Vérif

- `runtime/tests/test_ceramic_firing_loop.py` — **13 tests** (gate ; dépendance feu ; dépendance
  argile = le jalon ; choix FIRE_CLAY/WALK_TO ; consomme argile + produit poterie + mémoire ;
  inversion réfractaire #14 ; site stérile → argile conservée ; survie>cuisson ; saturation poterie ;
  back-compat `sim=None` ; orthogonalité inv_clay↓/inv_ceramic↑ ; non-mutation ; déterminisme).
- `runtime/scripts/p164_ceramic_firing_loop_smoke.py` — **8/8** (boucle live, seed `0xBEEF` ; les deux
  dépendances ; inversion réfractaire ; `sim.step()` propre ; gate + déterminisme ; D8/D10).
- `pytest` du nouveau test **13/13** ; `ruff` clean (fichiers neufs). Portail smoke CI p163 → **p164**.
- **Non-régression vérifiée live :** p163 (DIG) **8/8** après le réordonnancement de `decide()` et
  l'ajout d'`inv_ceramic`.

## Reste

11 capacités (C1, C4, C6, C10–C13, C15–C17, C19) + piliers **langage**/**bâtiments**. L'arc a franchi
un seuil : il y a désormais une **chaîne** vécue (DIG→IGNITE→FIRE_CLAY), pas seulement des actes
isolés. Candidats suivants : **C10 `lime_burning`** (calcaire C6 + feu → chaux ; même patron à deux
intrants, exige d'abord de brancher C6 limestone-gathering), **C13 `copper_smelting`** (minerai +
combustible + feu → métal), ou **C6 `limestone_outcrop`** (récolte non-feu, alterne et garnit
l'intrant de C10). Penser au **registre de capacités + budget de perception** : `decide()` porte
maintenant **9** lectures gated (dette ADR-0009 §Conséquences proche du seuil).
