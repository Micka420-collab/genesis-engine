# Sprint 2026-06-29 (run 9) — D12 wire #14 : la boucle agent CONSTRUIT un four à tirage (consomme C11)

> **Type :** `feat(agentic/cognition)` / câblage d'arc via le registre `_ARC_SEEKS`.
> **Acte :** [ADR-0009](../../adr/0009-agent-consumer-loop.md). **Suite de :** C4 GLEAN (run 8).
> **14ᵉ bouchée → 14/20.** **La 1ʳᵉ FABRICATION D'APPAREILLAGE de l'arc** (le pendant de C7 : C7
> *amorce* un feu, C11 *l'enferme* pour le rendre plus chaud).

## Décision — un wire propre, pas (encore) un ADR

Mon point d'inflexion (delta run8) classait le four et la métallurgie comme « cycle ADR ». La
lecture de C11 `kiln_draft` montre qu'il est en réalité une **affordance in-situ non-mutante** (comme
C7/C8/C9/C10) : il **compose** argile de paroi (C5) × feu (C7) et expose `kiln_peak_c` ground-truthé
— **sans surfacer de matière, sans `geo.mine_at`, sans structure persistante lourde**. Il est donc
**wireable proprement** comme un « build » (l'agent chemise son foyer d'argile). **Reste ADR :** C13
cuivre / C17 fer (qui, eux, franchissent **D10** via `geo.mine_at`).

## La tranche livrée — la première structure bâtie

Append d'une ligne au registre (`("kilnbuild", _seek_kilnbuild)` après `fuel`). Un agent qui **SAIT
faire du feu** (`has_made_fire`, C7) **ET porte de l'argile** (`inv_clay`, DIG/C5) à un site
constructible (`kiln_draft.best_kiln_site_near`) **RAISE_KILN** (`ActionKind.RAISE_KILN = 31`) :
il chemise le feu de parois d'argile → un four à tirage atteignant `kiln_peak_c` (≈1000–1100 °C) bien
au-delà du feu nu (~800 °C). **Auto-limité** : il construit le four **une fois** (`has_built_kiln`, la
découverte de l'appareillage), comme la 1ʳᵉ étincelle de C7. Consomme `inv_clay` (la chemise) ;
**aucun nouveau champ d'inventaire**.

### Le mensonge rendu visible #19 — l'inversion-de-l'inversion

Les parois en **argile commune** *fluent* à haute température (plafond modeste) ; la **kaolinite
réfractaire** — celle qui *sous-cuit comme un pot* dans un feu nu (mensonge #14 de C9) — fait les
**meilleures parois de four**. `best_kiln_site_near` préfère le four le plus chaud (réfractaire). Le
smoke le montre : parois réfractaires **1070 °C** > communes **1000 °C** > feu nu **800 °C**.

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (le wire n'ajoute aucun tell) | ✅ COMPOSE C5 × C7 ; `PY_TO_RUST` reste **15** |
| **D10** (mutation gelée) | ✅ four = appareillage non-mutant, **0 `geo.mine_at`** |
| **Dépendances honorées** | ✅ gate sur `has_made_fire` **et** `inv_clay` |
| **Auto-limité** | ✅ `has_built_kiln` → une seule construction (découverte), pas de reconstruction par tick |
| **Hot-loop / Zéro-régression** | ✅ gate sur C11 installé ; `bootstrap` ne l'installe pas → inerte par défaut |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, 0 RNG |

**Nouvel état :** `ActionKind.RAISE_KILN = 31` ; `EpisodicMemory.{known_kiln_site_locations,
has_built_kiln, last_kiln_peak_c}` ; `_ARC_SEEKS` → **13 entrées**. **Aucun champ `AgentRegistry`
nouveau** (consomme `inv_clay`).

## Vérif

- `runtime/tests/test_kiln_draft_loop.py` — **13 tests** (gate ; dépendance feu ; dépendance argile ;
  choix RAISE_KILN sur le site choisi par le wire ; consomme argile + record + mémoire ; inversion #19
  réfractaire>commun>feu-nu ; auto-limité has_built_kiln ; site stérile → argile conservée ; survie ;
  back-compat ; non-mutation ; déterminisme). *Note : `best_kiln_site_near` étant déterministe mais
  préférant un four à pic égal de plus haute confiance, les tests placent l'agent sur le propre choix
  du wire (les nombreux fours saturent au plafond des parois).*
- `runtime/tests/test_arc_seek_registry.py` — **6 tests** (registre à 13 entrées, `kilnbuild` après `fuel`).
- `runtime/scripts/p169_kiln_draft_loop_smoke.py` — **8/8** (live, seed `0xBEEF` ; inversion #19 ;
  `sim.step()` propre + wire vivant ; gate + déterminisme ; D8/D10).
- `pytest` (four + registre) **19/19** ; `ruff` clean. Portail smoke CI p168 → **p169**.
- **Non-régression vérifiée live :** p168 (GLEAN) **8/8** après l'insertion de `kilnbuild` au registre.

## Reste

6 capacités (C1, C12, C13, C16, C17, C19) + piliers **langage**/**bâtiments**. **Saut qualitatif à
portée :** le four étant bâti, la prochaine bouchée à forte valeur est de **coupler le four à C9/C10**
— faire que `FIRE_CLAY`/`CALCINE` détectent un four de l'agent (`has_built_kiln` / un four à proximité)
et utilisent `kiln_peak_c` au lieu de la température du feu nu → **vitrification** (C9 racheté) et
**mortier hard-burnt** (C10 racheté). Puis **C12 `forced_draught`** (tirage soufflé → température
cuivre) et la **métallurgie C13/C17** (cycle **ADR D10** : `geo.mine_at` dans la boucle agent).
