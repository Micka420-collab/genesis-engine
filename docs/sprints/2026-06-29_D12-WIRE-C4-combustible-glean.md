# Sprint 2026-06-29 (run 8) — D12 wire #13 : la boucle agent GLANE le combustible (consomme C4)

> **Type :** `feat(agentic/cognition)` / câblage d'arc via le registre `_ARC_SEEKS`.
> **Acte :** [ADR-0009](../../adr/0009-agent-consumer-loop.md). **Suite de :** C15 RAKE (run 7).
> **13ᵉ bouchée → 13/20.** Précurseur **NON-FEU** (le combustible qui *alimentera* les feux/fours).

## Veille + décision (report explicite de C16)

Règle d'or respectée. Le candidat « salaison » **C16 `food_curing`** a été examiné puis **reporté** :
c'est un **oracle** (`shelf_life_days`) dont la dose de sel vient de la **proximité** d'un marais
(`best_saltpan_near`), pas du sel *porté* ; et il n'y a **ni modèle de pourriture** (le `inv_food` ne
se dégrade pas) **ni champ `inv_cured`**. Le câbler fidèlement demande une décision de design
(réconcilier sel-porté ↔ sel-proximité + définir le bénéfice mécanique) → **cycle design**, pas un
append. À la place : **C4 `combustible_outcrop`** — un gather non-feu propre, miroir de QUARRY.

**COMBO_RETENU :** `C4` → 13ᵉ tranche, précurseur non-feu qui pose le **combustible** (tourbe /
schiste bitumineux / charbon) — le **charbon** est le seul de grade fusion, futur catalyseur de la
métallurgie C13.

## La tranche livrée

Append d'une ligne au registre (`("fuel", _seek_fuel)` après `saltpan`). Un agent rassasié et curieux
qui **perçoit** une exposition de combustible brûlable (`combustible_outcrop.best_fuel_near`,
require_burnable) marche jusqu'à elle et la **GLANE** (`ActionKind.GLEAN = 30`) → combustible
(`inv_fuel`) ∝ `calorific_grade` réelle. Mémoire : `known_fuel_locations`, `last_fuel_class`.

### Le mensonge rendu visible #18 — sombre ≠ combustible prêt

Charbon / schiste exposés **secs** se glanent en combustible riche et long (rendement ∝ pouvoir
calorifique) ; une **tourbière spongieuse** paraît tout aussi sombre mais est trop **humide** pour
brûler maintenant (`burnable_now=False` → seulement une fraction tant qu'elle n'est pas coupée &
séchée). `best_fuel_near(require_burnable)` route vers une source sèche ; glaner une tourbière humide
l'enseigne **en agissant**.

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (le wire n'ajoute aucun tell) | ✅ lit C4 ; `PY_TO_RUST` reste **15** |
| **D10** (mutation gelée) | ✅ GLEAN = collecte de surface, **0 `geo.mine_at`** |
| **D9** (alternance) | ✅ **NON-FEU** |
| **Zéro-régression** | ✅ `bootstrap` n'installe pas C4 → inerte par défaut |
| **inv_fuel ≠ inv_wood** | ✅ nouveau champ dédié (le combustible n'est pas le bois de construction) |
| **Back-compat persistance** | ✅ `inv_fuel` ajouté défensivement aux deux listes |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, 0 RNG |

**Nouvel état :** `ActionKind.GLEAN = 30` ; `AgentRegistry.inv_fuel` (nouveau champ) ;
`EpisodicMemory.{known_fuel_locations, last_fuel_class}` ; `_ARC_SEEKS` → **12 entrées**.

## Vérif

- `runtime/tests/test_combustible_glean_loop.py` — **11 tests** (gate ; choix GLEAN/WALK_TO ;
  remplissage + mémoire ; charbon > schiste ; site stérile ; saturation ; survie ; back-compat ;
  orthogonalité incl. `inv_wood` intact ; déterminisme).
- `runtime/tests/test_arc_seek_registry.py` — **6 tests** (registre à 12 entrées, `fuel` après `saltpan`).
- `runtime/scripts/p168_combustible_glean_loop_smoke.py` — **8/8** (live, seed `0xBEEF` ; charbon >
  schiste ; `sim.step()` propre ; gate + déterminisme ; D8/D10).
- `pytest` (combustible + registre) **17/17** ; `ruff` clean. Portail smoke CI p167 → **p168**.
- **Non-régression vérifiée live :** p166 (CALCINE) **8/8** après l'insertion de `fuel` au registre.

## Reste

7 capacités (C1, C11–C13, C16, C17, C19) + piliers **langage**/**bâtiments**. Le combustible posé,
les prochaines bouchées se répartissent en deux familles :

- **Gathers/transformations « append » restantes** : C16 `food_curing` (salaison — nécessite un
  petit modèle de conservation ou un champ `inv_cured` + décision design) ; C1 `surface_mineralization`
  (le tell minéral de base — perception, verbe « prospect »).
- **Gros morceaux « cycle ADR »** : le **four** C11/C12 (1ʳᵉ **structure bâtie** de l'arc, lèverait
  l'inversion réfractaire C9/C10 et débloquerait la fusion) ; **C13 cuivre** + **C17/C19 fer** (la
  métallurgie — franchissent **D10** via `geo.mine_at` ; à instruire par ADR « l'agent peut-il muter
  la géologie ? »).
