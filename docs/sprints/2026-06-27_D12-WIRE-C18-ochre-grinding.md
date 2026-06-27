# Sprint 2026-06-27 — D12 wire #4 : la boucle agent BROIE l'ocre (consomme C18)

> **Type :** `feat(agentic/cognition)` / câblage d'arc (pas une nouvelle capacité « Cap. CN »).
> **Exécute :** R-J15-2 (P1) de `SCHEDULED-TASK-2026-06-25-delta.md`. **Acte :** ADR-0009.
> **Suite de :** DRINK/C3 (`2d0ebd0`), KNAP/C2 (`7d4c748`), GATHER/C14 (`7da4cb4`) — les 3
> premières bouchées de D12. **4ᵉ bouchée → 4/20.**

## Veille (obligatoire, avant code)

5 axes. Découvertes retenues (cohérentes avec les 15 jours précédents) :
- **AIvilization v0** (arXiv 2602.10429, *unified agent architecture + adaptive profiles*),
  **Project Sid / PIANO** (économies/lois/religion émergentes ~1000 agents) et **TerraLingua**
  (open-endedness en écologies LLM) — confirment *frontalement* la voie ADR-0009 :
  **sélection d'action par utilité, spécialisation émergente sans direction explicite**.
  **Apport : validation de la direction, pas de pivot.**
- **JaxLife / Emergence World** — utility-based action selection **sans LLM** : compatible
  cargo-less + invariant sandboxing (ADR-0002). Le « cerveau LLM décisionnel » reste écarté.
- Bevy / WGPU / ML-KEM (Rust gelé ADR-0008, aucun endpoint réseau) → backlog / N/A.
- **CVE actives : aucune critique** (numpy / PCG64 clean ; pas de surface réseau créée).

**COMBO_RETENU :** `utility-based action selection (SID/AIvilization/JaxLife)` × `C18
ochre_grinding` → 4ᵉ tranche verticale de consommation d'arc, **première sur le pilier
SYMBOLIQUE**. **0 LLM, 0 dépendance nouvelle.** Couche **Agentic**. Pas de nouvel ADR
(ADR-0009 a déjà ratifié le patron ; ceci en est la 4ᵉ application).

## Le problème (D12 / R0)

L'arc de 20 capacités n'avait que **3/20** consommateurs agent (C3, C2, C14). R-J15-2
réclamait une 4ᵉ capacité branchée par le patron canonique — **non-feu** (alternance) et
de préférence une qui **amorce un pilier d'émergence immobile**. Le pilier **symbolique**
(dessin) n'avait jamais bougé depuis J0 ; C18 ``ochre_grinding`` (le pigment, substrat de
la marque) en est la première brique de substrat. La brancher, c'est la **première
consommation agent de l'axe symbolique**.

## La tranche livrée

Dans `cognition.decide()`, sous les drives de survie et **après** `_seek_toolstone` : un
agent **rassasié et curieux** qui **perçoit** (`ochre_grinding.best_ochre_site_near`, C18)
une terre rouille d'oxyde broyable marche jusqu'à elle et **broie** (`ActionKind.GRIND`)
une poignée → **pigment** (`inv_pigment`) ∝ `pigment_quality` *réelle* (chroma d'oxyde ×
richesse du chapeau). La position entre en `EpisodicMemory.known_ochre_locations`.

**Ordre dans `decide()` :** `_seek_frost_clast` (GATHER) → `_seek_toolstone` (KNAP) →
**`_seek_ochre` (GRIND)** → EXPLORE. **L'outil de survie d'abord, puis le symbole.** GRIND
travaille sur sa **propre** réserve (`inv_pigment`), donc il **ne concourt jamais** avec le
pool de pierre brute (gate distinct `PIGMENT_SATED_KG`).

### L'orthogonalité (GRIND ≠ KNAP ≠ GATHER)

- **KNAP / C2** = *casser* un affleurement (`collect_depth_m > 0`, percussion) → pierre + tranchant.
- **GATHER / C14** = *ramasser* un gélifract de surface (`collect_depth_m == 0`) → pierre + tranchant.
- **GRIND / C18** = *broyer* une terre de surface (`collect_depth_m == 0`) → **pigment**.
  9ᵉ verbe primitif, **inventaire orthogonal** (le symbole, pas l'outil).

### Le mensonge rendu visible #9 (le chapeau de fer ment AUSSI au peintre)

« Une terre rouille spectaculaire fait toujours de la peinture » → **FAUX** : un gossan
**oxyde** (hématite → ocre rouge, magnétite → noir) broie en pigment lightfast ; le **même**
chapeau rouille sur **pyrite** (sulfure) / **galène-sphalérite** (plomb-zinc) broie en
**rien d'utilisable** (rouille ≠ rouge). `best_ochre_site_near` ne route que vers des sites
`usable` ; broyer un gossan barré directement (`GRIND` sur pyrite) n'enseigne le mensonge
qu'**en agissant** (`usable == False` → pigment 0). (« le monde ne ment jamais », étendu au
comportement, pendant orthogonal de l'inversion à 5 voies de C17.)

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (pas de nouveau tell) | ✅ lit C18 (qui compose C1) ; `PY_TO_RUST` reste **15** ; pas de `_PROFILE` |
| **D10** (mutation gelée à `geo.mine_at`) | ✅ GRIND = broyage de surface, **0 mutation géologie** (vérifié : pas de `mine_at(` dans la branche GRIND) |
| **D9** (alternance feu/non-feu) | ✅ `feat(cognition)`, **non-feu** (D9 reste à 0 ; 4ᵉ wire d'affilée non-feu, mais ce sont des câblages, pas des capacités) |
| **Hot-loop** | ✅ gate sur C18 déjà installé ; **jamais** d'`install_*` en tick |
| **Zéro-régression par construction** | ✅ `bootstrap_genesis_sim` n'installe **pas** C18 → wire **inerte** partout sauf `install_ochre_grinding` explicite (tous les autres smokes intacts) |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, **0 RNG nouveau** |
| **Émergence absolue** | ✅ aucun arbre tech ; le monde décide le rendement (et le mensonge) |

**Nouveau champ d'état :** `AgentRegistry.inv_pigment` (réserve symbolique, plafond
`INV_PIGMENT_MAX`), `EpisodicMemory.known_ochre_locations`, `ActionKind.GRIND = 21`. Le
champ est ajouté aux listes de migration/persistance (`global_world`, `world_library`) en
miroir de `inv_tools` — chargement défensif (`if fld in loaded.files`), donc les anciennes
sauvegardes restent compatibles. **Exclu** de `_INVENTORY_MASS_FIELDS` (comme `inv_tools` :
un bien produit, poudre fine, pas une charge brute) → logique de capacité **inchangée**,
zéro régression.

## Vérif

- `runtime/tests/test_ochre_grinding_loop.py` — **11 tests** (gate sans C18, choix
  GRIND/WALK_TO/EXPLORE, rendement oxyde>sulfure-rouille, site sans gossan inerte,
  survie>broyage, back-compat `sim=None`, **inventaire orthogonal** pigment≠pierre/outil,
  borne `inv_pigment`).
- `runtime/scripts/p158_ochre_grinding_loop_smoke.py` — **8/8** (boucle live
  perceive→decide→act→remember sur monde réel à gossans émergents, seed `0x42` ; oxyde
  peint / sulfure ne peint pas ; `sim.step()` propre ; gate + déterminisme ; D8/D10).
- `pytest` complet **vert** (0 failed, 1 skipped ; +11 tests `test_ochre_grinding_loop.py`) ;
  `ruff` clean (set de l'arc :
  +`test_ochre_grinding_loop.py`, glob smoke `p15[0-8]`) ; portail smoke CI étendu p157 →
  **p158** (`Makefile` + `ci.yml`).
- **Non-régression vérifiée live :** p153 (KNAP) **8/8**, p155 (GATHER) **8/8**, p150
  (C18 capability) **8/8**, p146 (cryoclasty) **8/8**, p86 (autonomous world) **PASS**.

> **Note d'implémentation :** comme pour KNAP / GATHER, de nombreuses capacités
> réassignent globalement `cognition.decide`/`apply_decision` (wrappers sans teardown). Le
> wire vit dans les fonctions **originales** ; tests + smoke capturent les originaux à
> l'import pour rester déterministes (dette notée ADR-0009 §Conséquences → futur dispatch
> ordonné).

## Reste

16 capacités (C1, C4–C13, C15–C17, C19–C20) + piliers **langage**/**bâtiments** à
brancher, même patron, une tranche verticale à la fois. **Le pilier symbolique est amorcé
côté substrat (pigment) ET côté consommation agent (GRIND) ; le GESTE (tracer une marque
sur le `rock_canvas` C20) reste à brancher** — prochain candidat naturel : un verbe
`MARK`/`PAINT` qui consomme `inv_pigment` sur une paroi calcaire C20 durable, fermant la
boucle pigment→support→dessin (toujours émergent : *de quoi* et *où*, jamais *quoi*
dessiner).
