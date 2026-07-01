# Sprint 2026-07-01 — D12 wire #20 : la boucle agent CINGLE la loupe (consomme C19) — ARC FERMÉ 20/20

> **Type :** `feat(agentic/cognition)` / câblage d'arc via le registre `_ARC_SEEKS`.
> **Acte :** clôture de [ADR-0009](../../adr/0009-agent-consumer-loop.md) (l'arc C1→C20 est enfin
> **entièrement consommé** par la boucle agent). **NON-mutant** : cette 3ᵉ métallurgie ne franchit **PAS**
> D10 — [ADR-0010](../../adr/0010-agent-driven-mutation.md) reste **gelé à 2 franchissements** (SMELT C13,
> BLOOM C17). **Suite de :** C17 BLOOM (wire #19, la loupe spongieuse) et C13 SMELT (wire #18, le bouton).
> **20ᵉ bouchée → 20/20.** **L'ARC C1→C20 SE FERME.** Après le cuivre coulé (C13) et le fer réduit à
> l'état solide (C17), un agent **martèle** ici la loupe à chaud dans **la même fournaise à tirage forcé**
> (C12) qui l'a produite — la scorie de fayalite gicle, l'éponge se soude en **fer forgé**. Le monde décide
> si le billon **soude** ou **fissure**.

## Veille du jour → étape sautée dans cette session (autonome, pas d'accès web) — à faire manuellement

Le combo retenu est **strictement interne** (C17 déjà installé + C12 déjà chaud + `bloom_forging` module
livré au sprint J+13 run #2) : aucun signal externe n'est nécessaire pour clôturer l'arc. À rejouer
manuellement si le rituel du sprint l'exige.

| | |
|---|---|
| **COMBO_RETENU** | C19 `bloom_forging` × la boucle cognitive (BLOOM/C17 loupe → FORGE consolidation) |
| **Gain** | +1 comportement agent (le 20ᵉ) ; `inv_metal` **transformé** en fer forgé consolidé (pas rempli) ; **D12 tombe : 20/20** |
| **Coût** | ~2 h · complexité 2 · risque régression 1 (module C19 stable, D10 non touché ; p173/p175/p151 verts) |
| **Couche** | Agentic (cognition) × Substrate (C19) — **pure transformation, D10 gelé** |
| **Intégration** | `_seek_forge` + branche `FORGE` d'`apply_decision` lisant `bloom_forging.prospect_forge` |
| **ADR** | aucun neuf — ADR-0009 se **clôt** (arc consommé) ; ADR-0010 reste borné à 2 franchissements |

## La tranche livrée — la dernière bouchée, sans D10

Append d'une **ligne** au registre (`("forge", _seek_forge)` **juste après `"bloom"`** — la chaîne
métallurgique se lit désormais **SMELT (cuivre) → BLOOM (fer) → FORGE (fer forgé)**). **`ActionKind.FORGE`
= 36** est un verbe neuf : le cinglage à chaud n'est **ni** la fonte du cuivre (SMELT) **ni** la réduction
solide du minerai (BLOOM) — c'est la **consolidation** d'un produit **déjà tenu en poche**. Un agent qui :

1. a **DÉJÀ GAGNÉ UNE LOUPE** (`mem.has_bloomed_iron` True, C17/BLOOM — la sortie de la réduction solide),
2. n'a **pas déjà découvert la forge** (`mem.has_forged_iron` False — seuil unique, comme BLOOM lui-même),
3. **PORTE** assez de fer-loupe (`inv_metal ≥ FORGE_ORE_COST_KG = 1.0` kg — le même `inv_metal` que
   SMELT/BLOOM remplissent),

et qui **voit** un site de forge assez chaud (`bloom_forging.best_forge_site_near`, rayon
`FORGE_PERCEPT_M = 96 m` — la **même** fournaise à tirage forcé C12 qui a soufflé la loupe) y va et
**FORGE**. Le **monde** décide (`prospect_forge`) : la loupe d'**oxyde** (hématite/magnétite) se **soude**
sous le marteau (le billon est SAIN, dense, `is_wrought = True`) ; la loupe **red-short** (pyrite — le FeS
aux joints de grain fond sous la chaleur de forge) **fissure** en *hot-shortness* (`cracked = True`,
soundness plafonnée bas, rendement effondré). Auto-limité sur `has_forged_iron`, **posé seulement quand
le billon est SAIN** — un échec honnête ne verrouille **jamais** l'agent, il pourra retenter sur une loupe
d'oxyde.

### La transformation, PAS l'extraction — pourquoi D10 reste gelé

C'est la **différence structurelle** avec SMELT et BLOOM. Ceux-là appellent `geo.mine_at` : le minerai
disparaît **de la colonne** (mutation D10, ADR-0010 §a). FORGE, elle, `prospect_forge` **ne touche jamais
la géologie** — pas de `geo.mine_at`, pas de `chunk_geology` invalidée. Elle **transforme un produit déjà
en inventaire** : le fer-loupe (`inv_metal`, gagné à BLOOM) est **dépensé** (`spent = min(1 kg, inv_metal)`)
et remplacé par du fer forgé au ratio `cue.consolidation_ratio` (`wrought_iron_per_kg_ore /
bloom_iron_per_kg_ore`) — la **fraction de masse** qui survit au cinglage (la scorie de fayalite et les
battitures FeO partent, le reste se consolide). C'est la **1ʳᵉ capacité agent qui est un pur raffinage
d'un produit déjà en poche** (comme la trempe C8 ou la cuisson C9, mais appliqué à un métal), et donc la
**1ʳᵉ métallurgie sans mutation** — **D10 reste exactement où SMELT/BLOOM l'ont laissé**, gelé à 2
franchissements. L'expansion de la frontière métallurgique s'arrête ici par design.

### Le MENSONGE PHYSIQUE #10 — la même leçon relue au marteau (le sequel du #8)

L'arc C1→C20 a livré une famille de mensonges — le tell est **honnête** (la couleur/l'odeur/la texture
sont ce qu'elles semblent), **le RENDEMENT ment**. #8 (au bas-fourneau, BLOOM/C17) : le **même** chapeau
rouille couvre l'oxyde (fer sain) ET la pyrite (griller d'abord → red-short). #10 (à la forge) : la
**même** loupe qui sort du même bas-fourneau **soude saine** si elle vient d'un oxyde, **fissure**
sous le marteau si elle vient d'une pyrite. Le forgeron qui hammer un billon red-short comme s'il était
d'oxyde récolte un shattered billon — soundness plafonnée `RED_SHORT_SOUNDNESS_CEIL`, wrought-iron yield
effondré. La leçon que le fondeur a apprise à 1300 °C est **relue, plus tard et plus cher**, à 1200 °C sur
l'enclume. C'est C17 et C19 qui, ensemble, gravent l'archéométrie complète du fer : deux étapes, deux
occasions de rater sur le même **mensonge de surface**.

## Nouveaux champs

**`AgentRegistry` :** aucun (réutilise `inv_metal` — le même que SMELT/BLOOM remplissent). **`EpisodicMemory` :**
un champ neuf — `has_forged_iron: bool` (drapeau de découverte, seuil unique comme `has_bloomed_iron` /
`has_forced_draught`, positionné **uniquement quand le billon est SAIN**). **`ActionKind` :** un neuf,
`FORGE = 36` (le cinglage ≠ ni la fonte SMELT ni la réduction BLOOM).

## Garde-fous tenus

- **D8 (cross-langage)** — compose C19 `bloom_forging` (lui-même C17 × C12 × C1) ; **0 nouveau tell** ;
  `PY_TO_RUST` reste **15**. Asservi (wire test + p176 check 8).
- **D9 (alternance feu/non-feu)** — la queue métallurgique reste structurellement liée au feu (SMELT,
  BLOOM et FORGE lisent la **même** fournaise C12). **Aucune nouvelle alternance** : la chaleur de forge
  est déjà la chaleur de bloom (`fd.IRON_BLOOMERY_TEMP_C`). Noté, pas masqué.
- **D10 (mutation)** — **pas de nouveau franchissement** : `prospect_forge` **ne mine rien**
  (`geo.mine_at` jamais appelé). D10 reste exactement où SMELT/BLOOM l'ont laissé, **gelé à 2
  franchissements** (le sous-arc métallurgique reste borné par design). Asservi (wire test + p176 check 2).
- **D12 (consommation de l'arc)** — **FERMÉ** : 20/20. Registre à 19 entrées + C3 hors registre via DRINK.
- **Déterminisme** — oracle pur/mémoïsé ; même seed + même site ⇒ même `consolidation_ratio` +
  soundness + `is_wrought` (0 RNG). Asservi (wire test + p176 check 7).
- **Zéro-régression par construction** — `genesis_bootstrap` **n'installe pas** `bloom_forging` (comme
  pour les autres wires) ; le wire est **inerte** partout sauf `install_bloom_forging` explicite (gate sur
  `_forge_cue_cache`).
- **Hot-loop / ADR-0002** — lit un C19 **déjà installé** ; jamais d'`install_*` en tick ; try/except →
  None ; aucun cerveau LLM. Auto-limité sur `has_forged_iron` (posé uniquement en cas de succès).

## Couverture

- `runtime/engine/agent.py` — `ActionKind.FORGE = 36` + 1 champ `EpisodicMemory` (`has_forged_iron`).
- `runtime/engine/cognition.py` — `_seek_forge` + branche `FORGE` d'`apply_decision` + constantes
  `FORGE_PERCEPT_M`/`FORGE_ORE_COST_KG` + entrée `_ARC_SEEKS` (19ᵉ).
- `runtime/tests/test_bloom_forging_wire.py` — **13 tests** (gates C19/C17/inv_metal, décision, WALK_TO,
  branche FORGE sur oxyde/sain, sur pyrite/red-short, non-verrouillage sur cracked, non-mutation D10,
  place registre après `bloom`, back-compat sim=None, déterminisme même-seed).
- `runtime/tests/test_arc_seek_registry.py` — registre à **19 entrées** (`forge` inséré après `bloom`).
- `runtime/scripts/p176_bloom_forging_wire_smoke.py` — **8/8** sur seed `0x1901`.
- `Makefile` — lint-gate étendu à `test_bloom_forging_wire` ; `validate-all` étendu à `p176`.
- `.github/workflows/ci.yml` — smoke `p176` ajouté à la liste (miroir du Makefile).

## Vérification (locale)

- `PYTHONPATH=runtime python -m pytest runtime/tests/test_bloom_forging_wire.py -q` → **13 passed**.
- `PYTHONPATH=runtime python -m pytest runtime/tests/test_arc_seek_registry.py -q` → **passed**
  (registre re-synchronisé à 19 entrées).
- `python -m ruff check` sur l'ensemble arc (**exactement** la liste du Makefile) → **All checks passed!**.
- `PYTHONPATH=runtime python runtime/scripts/p176_bloom_forging_wire_smoke.py` → **PASS 8/8**
  (FORGE live sur oxyde ; billon SAIN 0,8574 kg ; red-short pyrite fissure ; déterministe ; D10 non muté).
- `PYTHONPATH=runtime python -m pytest runtime/tests` → **suite complète verte** (0 régression).
- Non-régression live : `p175_iron_bloom_loop_smoke.py` → **8/8** (BLOOM boucle intacte).

## Recommandations / Reste

**L'arc C1→C20 est FERMÉ** : toutes les 20 capacités matérielles sont consommées par la boucle agent
(19 via `_ARC_SEEKS`, C3 via DRINK). Le sous-arc métallurgique se clôt naturellement (SMELT → BLOOM →
FORGE), les 3 mensonges physiques métallurgiques (#4 cuivre natif vs sulfure, #8 fer vs pyrite,
#10 forge vs red-short) sont **tous vécus**. **La prochaine frontière** est hors de l'arc matériel :

1. **Le pilier LANGAGE** (immobile depuis J+0, axe 4 des 5 piliers d'émergence). Les agents ont désormais
   un vocabulaire d'objets riche (feu, forge, pot, chaux, ocre, sel, cure, loupe, fer forgé…) mais aucune
   forme de **transmission cognitive** entre agents. C'est le blocage sociétal réel.
2. **Le pilier BÂTIMENTS** (immobile depuis J+0, axe 5). Les kilns/forges C11/C12 sont des points
   ponctuels — pas de structure abritée, pas de séparation feu/dortoir, pas d'accumulation architecturale.
3. **Dette légère** : le fer forgé peut être forgé une seule fois (`has_forged_iron` verrouille) — à
   redébloquer si l'axe outils (armes, socs) émerge, en cassant proprement le verrou sur un signal fort
   (par ex. **usure** d'un outil déjà en poche).

Reco du lendemain : **choisir entre LANGAGE et BÂTIMENTS pour ouvrir le premier axe non-matériel**.
