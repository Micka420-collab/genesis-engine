# Sprint 2026-06-29 (run 5) — D12 wire #10 : la boucle agent EXTRAIT le calcaire (consomme C6)

> **Type :** `feat(agentic/cognition)` / câblage d'arc — **1ʳᵉ bouchée ajoutée via le registre**
> `_ARC_SEEKS` (le refactor run 4). **Acte :** [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Suite de :** wires #7–#9 (C8, C5, C9) + refactor registre. **10ᵉ bouchée → 10/20.**
> **Précurseur NON-FEU** — la pierre liante, matière du futur C10 `lime_burning`.

## Veille (obligatoire, avant code)

Règle d'or respectée. La chaux est **le plus ancien liant connu** (néolithique, enduits de Göbekli
Tepe ~9500 av. J.-C., antérieur à la métallurgie). Le calcaire est le pendant bâtisseur de l'argile :
la matière qui *colle et bâtit*. **Apport : validation** (la pierre liante est une brique d'arc
légitime), pas de pivot. Aucune brique externe (cargo-less). **CVE : aucune.**

**COMBO_RETENU :** `utility-based action selection` × `C6 limestone_outcrop` → 10ᵉ tranche,
**précurseur non-feu** (alterne après la chaîne céramique) qui garnit l'intrant de la prochaine
transformation à deux ingrédients (C10 chaux). Couche **Agentic**. Pas de nouvel ADR.

## La tranche livrée — la première via le registre

Le refactor run 4 tient sa promesse : câbler C6 = **un append d'une ligne** au registre
`_ARC_SEEKS` (`("limestone", _seek_limestone)`, placé après la chaîne céramique), **sans toucher au
corps de `decide()`**. Un agent rassasié et curieux qui **perçoit** une berge carbonatée mortar-grade
(`limestone_outcrop.best_limestone_near`, require_mortar) marche jusqu'à elle et l'**EXTRAIT**
(`ActionKind.QUARRY = 27`) → `inv_limestone` se remplit ∝ `lime_grade` *réelle*. Mémoire :
`known_limestone_locations` + `last_lime_class`.

### Le mensonge rendu visible #15 (la falaise blanche ment au chaufournier)

« Une belle falaise blanche fait toujours de la bonne chaux » → **FAUX** : un carbonate **pur et
sain** s'extrait en stock liant riche (rendement ∝ `lime_grade`) ; une berge **karstique /
gélifractée** ou **dolomitique** paraît tout aussi blanche mais rend une pierre de moindre grade —
mensonge pleinement révélé *plus tard*, à la cuisson. `best_limestone_near(require_mortar)` route vers
le carbonate le plus pur en vue ; extraire une mauvaise berge l'enseigne **en agissant**.

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (le wire n'ajoute aucun tell) | ✅ lit C6 ; `PY_TO_RUST` reste **15** (le `limestone_pure` de C6 est catalogue-only) |
| **D10** (mutation gelée) | ✅ QUARRY = extraction de surface, **0 `geo.mine_at`** |
| **D9** (alternance) | ✅ **NON-FEU** — alterne après la chaîne céramique |
| **Zéro-régression par construction** | ✅ `bootstrap` n'installe pas C6 → wire inerte par défaut |
| **Back-compat persistance** | ✅ `inv_limestone` ajouté défensivement aux deux listes |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, 0 RNG |

**Nouvel état :** `ActionKind.QUARRY = 27` ; `AgentRegistry.inv_limestone` (nouveau champ) ;
`EpisodicMemory.{known_limestone_locations, last_lime_class}` ; `_ARC_SEEKS` passe à **9 entrées**.

## Vérif

- `runtime/tests/test_limestone_quarry_loop.py` — **11 tests** (gate ; choix QUARRY/WALK_TO ;
  remplissage + mémoire ; pur > commun ; site stérile ; saturation ; survie>carrière ; back-compat
  `sim=None` ; orthogonalité inv_limestone seul ; non-mutation ; déterminisme).
- `runtime/tests/test_arc_seek_registry.py` — **6 tests** mis à jour (registre à 9 entrées, ordre
  canonique avec `limestone` après `kiln`).
- `runtime/scripts/p165_limestone_quarry_loop_smoke.py` — **8/8** (boucle live, seed `0xBEEF` ;
  pur > commun ; `sim.step()` propre ; gate + déterminisme ; D8/D10).
- `pytest` (calcaire + registre) **17/17** ; `ruff` clean. Portail smoke CI p164 → **p165**.
- **Non-régression vérifiée live :** p164 (FIRE_CLAY, entrée précédant `limestone` dans le registre)
  **8/8**.

## Reste

10 capacités (C1, C4, C10–C13, C15–C17, C19) + piliers **langage**/**bâtiments**. L'intrant de la
chaux est posé : le candidat suivant naturel est **C10 `lime_burning`** (calcaire `inv_limestone` +
feu `has_made_fire` → chaux vive), la **2ᵉ transformation à deux ingrédients** (après C9), qui
*consommerait* le calcaire qu'on vient de rendre récoltable — bouclant calcaire→feu→chaux, comme C9
a bouclé argile→feu→pot. Puis **C13 `copper_smelting`** (minerai + combustible + feu → métal).
