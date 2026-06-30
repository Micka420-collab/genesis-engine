# Sprint 2026-06-30 — D12 wire #17 : la boucle agent LIT la couleur du sol (consomme C1)

> **Type :** `feat(agentic/cognition)` / câblage d'arc via le registre `_ARC_SEEKS`.
> **Acte :** [ADR-0009](../../adr/0009-agent-consumer-loop.md). **Suite de :** C12 FORCE_DRAUGHT (wire #16).
> **17ᵉ bouchée → 17/20.** **Le 1ᵉʳ ACTE PUREMENT COGNITIF/VISUEL de la boucle** (la première fois que
> l'agent agit *sans rien transformer du monde* — il apprend par association couleur↔ce qui se trouve
> dessous). **Le pont vers la métallurgie** : pose la fondation cognitive du futur D10 (C13 cuivre /
> C17 fer / C18 ochre déjà câblé, etc.) **sans franchir D10**.

## Veille du jour (étape 0, 5 axes) → 0 combo externe intégrable

Veille libre (axes IA/agents · Rust/ECS · crypto/CVE · infra/data · arXiv). Découvertes notées,
**toutes gated** pour l'ère *cargo-less* / *no-LLM-brain* / *no-endpoint-nouveau* :

- **DÉCOUVERTE_1** — *Fill–Spill–Merge* (flow routing en hiérarchie de dépressions, Barnes/Callaghan)
  encore en **COMBO_BACKLOG** (risque de régression sur `river_discharge.py` > la valeur d'une session
  non surveillée). Repoussé à un sprint à deux mains.
- **DÉCOUVERTE_2** — *Emergence World* (arxiv 2606.08367) **gated** (déjà couvert par Wave 58/60).
- **DÉCOUVERTE_3** — *EvoSkills* (auto-évolution de skills LLM) **REJETÉ** : viole
  [emergence-only](../../adr/0002-no-frontier-llm-as-agent-brain.md) (arbre tech scripté).
- **CVE_ACTIVES** — *CVE-2026-3298* (asyncio `ProactorEventLoop` OOB write, Windows) + supply-chain
  *litellm* (PyPI). **Aucune surface Genesis impactée**. Aucune action.
- **PAPER_DU_JOUR** — Fill–Spill–Merge (voir DÉCOUVERTE_1).

**Combo retenu = interne** : C1 `surface_mineralization` (substrat depuis J+1, déjà composé par C12
forced_draught) × la chaîne cognitive de la boucle agent. Pas d'ADR (affordance in-situ purement
non-mutante).

## Décision — un wire propre, pas un ADR

C1 `surface_mineralization` est **lecture pure d'un signal physique véridique** : le module ne mute
rien et n'introduit ni nouvelle action mutante (`geo.mine_at`) ni nouveau tell cross-langage
(`PY_TO_RUST` reste 15). Wireable proprement comme un « prospect » (l'agent voit une couleur,
l'enregistre, apprend qu'elle *signifie* quelque chose). **Reste ADR :** C13 cuivre / C17 fer (qui
franchissent **D10** via `geo.mine_at`).

## La tranche livrée — le 1ᵉʳ acte cognitif

Append d'une ligne au registre (`("prospect", _seek_prospect)` **après `canvas`** — l'arc se termine
sur l'acte le plus *gratuit* : la cognition pure). Un agent **survie-satisfait, curieux**, qui voit
une **tache colorée** dans son rayon de perception (`PROSPECT_PERCEPT_M = 96 m`) **dont il n'a pas
encore lu le groupe** (`mem.prospected_ore_groups`), **PROSPECTE** (`ActionKind.PROSPECT = 34`) : il
enregistre `(group, x, y)` dans `mem.known_ore_sites`, marque le groupe comme découvert, et **apprend
par association** ce que cette couleur *signifie* sous terre. **Auto-limité par groupe** : chaque
couleur (copper / gossan / sulfur / salt / gold_placer) est sa propre découverte ; l'agent ne
re-prospecte pas un groupe déjà rencontré. Avec 5 groupes la limite naturelle est de 5 prospections
par vie (les **5 mensonges du sol** à apprendre).

**Aucun nouveau champ `AgentRegistry`. Aucune nouvelle entrée inventaire** : l'acte est *purement
cognitif* — pas de pigment ramassé, pas de pierre cassée, pas de combustible brûlé, pas de géologie
mutée. **C'est la première fois qu'un wire ne mute strictement rien du monde sauf la cognition de
l'agent qui agit.** Quatre champs nouveaux sur `EpisodicMemory` :
``known_ore_sites: List[Tuple[str, float, float]]``,
``prospected_ore_groups: List[str]``,
``has_prospected_ore: bool``,
``last_prospect_group: Optional[str]``.

### Le mensonge rendu visible #21 — la couleur ment sur la quantité

Une tache **VERTE éclatante** (malachite/azurite) *signifie une seule chose* — le cuivre
(`MINERAL_RULE[copper]`). Une tache **ROUILLÉE banale** (chapeau de fer / gossan) *signifie cinq
choses* — pyrite, hematite, magnetite, galena, sphalerite (cinq minéraux distincts sous la même
couleur d'altération oxydante). La richesse visuelle ne dit pas la richesse souterraine :
*l'enseigne lumineuse* ne dit qu'un mot, *la marque sale* en dit cinq. L'agent l'apprend en lisant 5
couleurs distinctes — sa cognition se construit en arbre par sites, pas par répétition. C'est le
pendant *inversé* du mensonge #11 (la falaise pâle qui ne tient pas la marque de C20) : ici, c'est la
sobre rouille qui *cache la richesse*.

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (le wire n'ajoute aucun tell cross-langage) | ✅ COMPOSE C1 seul ; `PY_TO_RUST` reste **15** |
| **D10** (mutation gelée) | ✅ acte purement cognitif, **0 `geo.mine_at`**, **0 inventaire consommé** |
| **D9** (alternance feu/non-feu) | ✅ **1 → 0** : non-feu (la cognition) après le feu (la fournaise C12) |
| **Dépendances honorées** | ✅ gate sur cue cache C1 ; cap auto sur `prospected_ore_groups` |
| **Auto-limité** | ✅ `has_prospected_ore` + per-group ; max 5 prospections (`PROSPECT_MAX_GROUPS`) |
| **Hot-loop / Zéro-régression** | ✅ gate sur C1 installé ; `bootstrap` ne l'installe pas → inerte par défaut |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, 0 RNG |

**Nouvel état :** `ActionKind.PROSPECT = 34` ; `EpisodicMemory.{known_ore_sites, prospected_ore_groups,
has_prospected_ore, last_prospect_group}` ; `_ARC_SEEKS` → **16 entrées** (`prospect` après
`canvas`). **Aucun champ `AgentRegistry` nouveau** (cognition pure, pas d'inventaire).

## Vérif

- `runtime/tests/test_prospect_ore_wire.py` — **13 tests** (gate C1 ; auto-limite à 5 groupes ;
  décision PROSPECT sur le stain choisi ; WALK_TO hors-site ; record group + site + flag + event ;
  idempotent même-groupe ; multi-groupes ; survie > prospect ; pas de stain → rien appris ;
  non-mutation totale ; back-compat `sim=None` ; déterminisme ; registre + budget).
- `runtime/tests/test_arc_seek_registry.py` — **6 tests** (registre à 16 entrées, `prospect` après
  `canvas`).
- `runtime/scripts/p172_prospect_ore_loop_smoke.py` — **8/8** (live, seed `0xC1` thématique, 143
  chunks cued / 3 groupes salt+gossan+sulfur ; mensonge #21 ; `sim.step()` propre + wire vivant ;
  gate + déterminisme ; D8/D10).
- `pytest` suite complète **verte** (prospect wire + registre + non-régression de tout l'arc) ;
  `ruff` clean sur la lint-gate. Portail smoke CI/Makefile p171 → **p172** ; lint étendu à
  `test_prospect_ore_wire.py`.
- **Non-régression vérifiée live :** p161 (IGNITE), p169 (RAISE_KILN), p170 (CURE), p171
  (FORCE_DRAUGHT) **chacun PASS** après l'insertion de `prospect` au registre. Un test ochre obsolète
  (`test_pigment_sated_agent_stops_seeking`) ajusté pour accepter PROSPECT comme fall-through légitime
  (le contrat sous test reste « pas de GRIND quand pigment-sated »).

## Reste

3 capacités non encore consommées par l'agent : **C13** (`copper_smelting`), **C17**
(`iron_bloomery`), **C19** (`bloom_forging`) + piliers **langage** / **bâtiments**. **Saut qualitatif
à portée :** PROSPECT a posé la fondation cognitive — la prochaine bouchée à forte valeur reste la
**1ʳᵉ métallurgie agent — C13 `copper_smelting`** (ADR D10 avant code, comme noté hier) : faire que la
boucle consomme un site `known_ore_sites['copper']` sous un four `has_forced_draught` → bouton de
cuivre. La cognition d'aujourd'hui est exactement le pré-requis qu'attendait C13.

**Reco du lendemain :** soit **C13 via ADR D10** (haute valeur, exige un humain pour l'ADR), soit
**Fill–Spill–Merge** sur `river_discharge` (couche World, lacs endoréiques, plus sûr en autonome).
Préférer **C13 + ADR** si une session humaine est planifiée.
