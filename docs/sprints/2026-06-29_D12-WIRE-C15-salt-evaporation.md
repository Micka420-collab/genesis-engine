# Sprint 2026-06-29 (run 7) — D12 wire #12 : la boucle agent RÂTELLE le sel solaire (consomme C15)

> **Type :** `feat(agentic/cognition)` / câblage d'arc via le registre `_ARC_SEEKS`.
> **Acte :** [ADR-0009](../../adr/0009-agent-consumer-loop.md). **Suite de :** C10 CALCINE (run 6).
> **12ᵉ bouchée → 12/20.** Précurseur **NON-FEU / non-thermal** (le soleil fait le travail).

## Veille + décision (report explicite de C13)

Règle d'or respectée. Le candidat « excitant » était **C13 `copper_smelting`** (la métallurgie),
mais sa lecture révèle **deux blocages** qui en font une décision d'architecture, pas un wire de
routine : (1) il **dépend de C12 `forced_draught`** (un four soufflé atteignant 1085 °C — non
câblé, et une *structure* à bâtir ; un feu ouvert ne fond pas le cuivre) ; (2) il **mute la
géologie** via `geo.mine_at` (`smelt_at` extrait le minerai) — il **franchit la frontière D10
gelée**. Brancher C13 dans la boucle agent = la 1ʳᵉ action agent qui mute le sol → mérite un ADR,
pas un append. **Reporté** (après le four C11/C12 + décision D10).

À la place, **C15 `salt_evaporation`** : le 8ᵉ opérateur orthogonal (séchage solaire), réponse à
`R-J9-1`. Non-feu (rétablit l'alternance après deux transformations-feu), propre, non-mutant, et il
pose le **sel** — l'intrant de la future C16 `food_curing` (conservation). **COMBO_RETENU.**

## La tranche livrée

Append d'une ligne au registre (`("saltpan", _seek_saltpan)` après `limekiln`). Un agent rassasié et
curieux qui **perçoit** une croûte de sel récoltable (`salt_evaporation.best_saltpan_near`) marche
jusqu'au bassin et le **RÂTELLE** (`ActionKind.RAKE = 29`) → sel (`inv_salt`) ∝ rendement réel
(`salt_yield`, ×`SALT_ABUNDANT_MULT` sur un salar copieux). Le soleil a déposé le sel : **aucun feu,
aucune percussion, aucune fonte**. Mémoire : `known_saltpan_locations`, `last_salt_zone`.

### Le mensonge rendu visible #17 — l'or blanc exige le soleil

Une saumure en climat **aride** (déficit évaporatif) forme une vraie croûte récoltable ; la **même**
saumure en climat **humide** paraît tout aussi mouillée mais ne cristallise **jamais** (le soleil ne
gagne pas contre la pluie — `harvestable=False`). `best_saltpan_near` ne route que vers un bassin
réellement croûté ; le mensonge est prouvé sur l'oracle pur (`_saltpan_from_inputs` aride vs humide).

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (le wire n'ajoute aucun tell) | ✅ compose C3 (salinité) × climat ; `PY_TO_RUST` reste **15** |
| **D10** (mutation gelée) | ✅ RAKE = récolte de surface solaire, **0 `geo.mine_at`** |
| **D9** (alternance) | ✅ **NON-FEU / non-thermal** — rétablit l'alternance après C9/C10 |
| **Zéro-régression** | ✅ `bootstrap` n'installe pas C15 → inerte par défaut |
| **Back-compat persistance** | ✅ `inv_salt` ajouté défensivement aux deux listes |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, 0 RNG |

**Nouvel état :** `ActionKind.RAKE = 29` ; `AgentRegistry.inv_salt` (nouveau champ) ;
`EpisodicMemory.{known_saltpan_locations, last_salt_zone}` ; `_ARC_SEEKS` → **11 entrées**.

## Vérif

- `runtime/tests/test_salt_evaporation_loop.py` — **12 tests** (gate ; choix RAKE/WALK_TO ;
  remplissage + mémoire ; rendement abondant ; mensonge #17 aride vs humide ; site stérile ;
  saturation ; survie ; back-compat ; orthogonalité ; déterminisme). Montage **ancré sur la côte
  aride salée** (seed `0x5A17`, comme le test de capacité C15).
- `runtime/tests/test_arc_seek_registry.py` — **6 tests** (registre à 11 entrées, `saltpan` après `limekiln`).
- `runtime/scripts/p167_salt_evaporation_loop_smoke.py` — **8/8** (live, côte aride ; mensonge #17 ;
  `sim.step()` propre + wire vivant ; gate + déterminisme ; D8/D10).
- `pytest` (sel + registre) **18/18** ; `ruff` clean. Portail smoke CI p166 → **p167**.
- **Non-régression vérifiée live :** p166 (CALCINE) **8/8** après l'insertion de `saltpan` au registre.

## Reste

8 capacités (C1, C4, C11–C13, C16, C17, C19) + piliers **langage**/**bâtiments**. Suite naturelle :
**C16 `food_curing`** (viande/poisson + **sel** `inv_salt` → conservation ; une transformation
non-feu à deux intrants, qui *consomme* le sel qu'on vient de poser — boucle sel→salaison) ; ou
**C4 `combustible_outcrop`** (combustible, autre précurseur non-feu). **C13 cuivre** et le **four
C11/C12** restent les gros morceaux à instruire (dépendances + D10 pour C13 ; structure bâtie pour
le four) — candidats pour un cycle « décision/ADR » plutôt qu'un append.
