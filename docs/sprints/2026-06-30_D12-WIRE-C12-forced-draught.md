# Sprint 2026-06-30 — D12 wire #16 : la boucle agent FORCE le tirage de son four (consomme C12)

> **Type :** `feat(agentic/cognition)` / câblage d'arc via le registre `_ARC_SEEKS`.
> **Acte :** [ADR-0009](../../adr/0009-agent-consumer-loop.md). **Suite de :** C11 RAISE_KILN (wire #14)
> et C16 CURE (wire #15).
> **16ᵉ bouchée → 16/20.** **Le 2ᵉ APPAREILLAGE de l'arc** (le pendant exact de C11 : C11 *enferme*
> le feu dans des parois d'argile, C12 *souffle dessus* pour le pousser dans le régime haute température).

## Veille du jour (étape 0, 5 axes) → 0 combo externe intégrable

Veille libre (axes IA/agents · Rust/ECS · crypto/CVE · infra/data · arXiv). Découvertes notées,
**toutes gated** pour l'ère *cargo-less* / *no-LLM-brain* / *no-endpoint-nouveau* :

- **DÉCOUVERTE_1** — *Fill–Spill–Merge* (flow routing en hiérarchie de dépressions, Barnes/Callaghan) ·
  couche **World** (hydrologie, Wave 64 `river_discharge`) · gain estimé : lacs endoréiques émergents +
  routage des cuvettes. **→ COMBO_BACKLOG** (touche du code testé existant : `river_discharge.py` +
  `test_river_discharge_coupling.py` — risque de régression > la valeur d'une seule session non
  surveillée ; porté à [`ROADMAP.md`](../../ROADMAP.md)). Reste **émergence pure** (physique, pas un
  arbre tech).
- **DÉCOUVERTE_2** — *Emergence World* (arxiv 2606.08367, éval autonomie multi-agent long-horizon 15 j) ·
  couche **Observatory** · gain : protocole d'éval d'émergence. **Gated** (déjà couvert par Wave 58/60
  open-endedness ; pas d'intégration neuve aujourd'hui).
- **DÉCOUVERTE_3** — vague *EvoSkills / AutoSkill / MUSE-Autoskill* (auto-évolution de skills LLM) ·
  couche **Agentic** · **REJETÉ** : viole [emergence-only](../../adr/0002-no-frontier-llm-as-agent-brain.md)
  (skills = scripted tech tree piloté par LLM ; Genesis interdit l'arbre tech scripté).
- **CVE_ACTIVES** — *CVE-2026-3298* (asyncio `ProactorEventLoop` OOB write, Windows) + supply-chain
  *litellm* (PyPI). **Aucune surface Genesis impactée** : l'arc n'utilise ni asyncio sockets ni
  litellm (déterministe, numpy seul). Aucune action.
- **PAPER_DU_JOUR** — Fill–Spill–Merge (voir DÉCOUVERTE_1), seul candidat directement applicable →
  backlog World.

**Combo retenu = interne** : C11 `forced_draught` (déjà en substrat depuis J+8) × la chaîne
d'appareillage de la boucle agent. Pas d'ADR (affordance in-situ non-mutante).

## Décision — un wire propre (comme C11), pas un ADR

C12 `forced_draught` est une **affordance in-situ non-mutante** : il **compose** le four de C11
(`kiln_cue_for_chunk`) × le cuivre de C1, et expose `forced_peak_c` ground-truthé — **sans surfacer de
matière, sans `geo.mine_at`**. Wireable proprement comme un « force » (l'agent souffle un soufflet sur
son four au charbon). **Reste ADR :** C13 cuivre / C17 fer (qui franchissent **D10** via `geo.mine_at`).

## La tranche livrée — le 2ᵉ appareillage, le soufflet

Append d'une ligne au registre (`("forcedraught", _seek_forcedraught)` **après `kilnbuild`** — la chaîne
d'appareillage *raise → force*). Un agent qui a **DÉJÀ BÂTI UN FOUR** (`has_built_kiln`, RAISE_KILN/C11)
**ET porte du combustible** (`inv_fuel ≥ FORCE_FUEL_COST_KG`, la charge de charbon, GLEAN/C4) à un site
forçable (`forced_draught.best_forced_site_near`) **FORCE_DRAUGHT** (`ActionKind.FORCE_DRAUGHT = 33`) :
il souffle de l'air dans le charbon → le four dépasse le pic à tirage naturel (`forced_peak_c`, ≈1100–
1400 °C). **Auto-limité** : il force le tirage **une fois** (`has_forced_draught`, la découverte de
l'appareillage), comme la 1ʳᵉ étincelle de C7 / le 1ᵉʳ four de C11. Consomme `inv_fuel` (le charbon) ;
**aucun nouveau champ d'inventaire**. **Compose deux produits de wires antérieurs** : le *savoir-four*
de RAISE_KILN (C11) × le *combustible* de GLEAN (C4).

**Le payoff** : le régime haute température que le soufflet ouvre **VITRIFIE enfin** le corps kaolin
réfractaire (`vitrifies_watertight` True — l'étape que C9 ET C11 différaient) et **atteint le seuil de
fonte du cuivre** (`reaches_copper_smelting_temp`). L'arc « rachat du kaolin » se ferme dans la boucle
agent.

### Le mensonge rendu visible #20 — le mur que le soufflet ne bat pas

On peut souffler aussi fort qu'on veut : une paroi en **argile commune** *flue* (`FORCED_COMMON_WALL_CAP_C`
**1100 °C**, juste au-delà du cuivre) — elle **ne vitrifie jamais** et **n'atteint jamais** le régime du
fer. Seule la paroi en **kaolinite réfractaire** (`FORCED_REFRACTORY_WALL_CAP_C` **1400 °C**) **perce**.
`best_forced_site_near` préfère le plus chaud. Le smoke le montre sur le monde réel seed `0xBEEF` :
four réfractaire **forced 1295 °C → vitrifie** ; four commun **forced 1100 °C → ne vitrifie pas**. « Le
soufflet ne bat pas le mur » — appris en forçant. C'est le pendant exact du mensonge #19 de C11, poussé
d'un cran : la même kaolinite qui *sous-cuit comme un pot* (mensonge #14 de C9) est la **seule** clé de
la haute pyrotechnologie.

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (le wire n'ajoute aucun tell) | ✅ COMPOSE C11 × C4 ; `PY_TO_RUST` reste **15** |
| **D10** (mutation gelée) | ✅ tirage forcé = appareillage non-mutant, **0 `geo.mine_at`** |
| **D9** (alternance feu/non-feu) | ✅ **0 → 1** : feu (la fournaise) après le non-feu C16 CURE |
| **Dépendances honorées** | ✅ gate sur `has_built_kiln` (C11) **et** `inv_fuel` (C4) |
| **Auto-limité** | ✅ `has_forced_draught` → un seul forçage (découverte), pas par tick |
| **Hot-loop / Zéro-régression** | ✅ gate sur C12 installé ; `bootstrap` ne l'installe pas → inerte par défaut |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, 0 RNG |

**Nouvel état :** `ActionKind.FORCE_DRAUGHT = 33` ; `EpisodicMemory.{known_forced_locations,
has_forced_draught, last_forced_peak_c}` ; `_ARC_SEEKS` → **15 entrées** (`forcedraught` après
`kilnbuild`). **Aucun champ `AgentRegistry` nouveau** (consomme `inv_fuel`).

## Vérif

- `runtime/tests/test_forced_draught_wire.py` — **13 tests** (gate C12 ; dépendance four bâti ;
  dépendance combustible ; choix FORCE_DRAUGHT sur le site choisi par le wire ; WALK_TO hors-site ;
  consomme combustible + record + mémoire ; inversion #20 réfractaire>commun + vitrification ;
  auto-limité `has_forced_draught` ; site stérile → combustible conservé ; survie > forcer ;
  back-compat `sim=None` ; non-mutation géologie ; déterminisme).
- `runtime/tests/test_arc_seek_registry.py` — **6 tests** (registre à 15 entrées, `forcedraught`
  après `kilnbuild`).
- `runtime/scripts/p171_forced_draught_loop_smoke.py` — **8/8** (live, seed `0xBEEF`, 144 sites
  forçables dont 17 réfractaires ; inversion #20 ; `sim.step()` propre + wire vivant ; gate +
  déterminisme ; D8/D10).
- `pytest` suite complète **verte** (forced-draught wire + registre + non-régression de tout l'arc) ;
  `ruff` clean. Portail smoke CI/Makefile p170 → **p171** ; glob lint étendu à `p17[0-9]`.
- **Non-régression vérifiée live :** p169 (RAISE_KILN), p170 (CURE), p161 (IGNITE), p164 (FIRE_CLAY)
  **8/8** chacun après l'insertion de `forcedraught` au registre.

## Reste

4 capacités non encore consommées par l'agent : **C1** (gossan / minéralisation de surface), **C13**
(`copper_smelting`), **C17** (`iron_bloomery`), **C19** (`bloom_forging`) + piliers **langage** /
**bâtiments**. **Saut qualitatif à portée :** le tirage forcé étant acquis, la prochaine bouchée à forte
valeur est la **1ʳᵉ métallurgie agent — C13 `copper_smelting`** : faire que la boucle consomme le minerai
de cuivre (le vert C1) sous le four forcé `has_forced_draught` → bouton de cuivre. C'est le **cycle ADR
D10** (`geo.mine_at` dans la boucle agent — la 1ʳᵉ mutation pilotée par l'agent), donc **ADR avant code**.
Le COMBO_BACKLOG **Fill–Spill–Merge** (lacs endoréiques) attend en couche World.
