# ADR 0010 — Franchir D10 : la première MUTATION du monde par un agent (la fonte du cuivre)

- **Statut** : Accepted
- **Date** : 2026-07-01
- **Décideurs** : Lead Engineer (morning-routine auto, J+21 du delta-audit)
- **Suite de** : [ADR-0009](0009-agent-consumer-loop.md) (la boucle agent consomme l'arc — qui
  **gelait** explicitement D10) · exécute la 2ᵉ étape annoncée par le wire #17 PROSPECT (commit
  `5c46f37` : « posera la fondation cognitive du futur D10… sans le franchir aujourd'hui »).

## Contexte

[ADR-0009](0009-agent-consumer-loop.md) a établi le patron « `perceive→decide→act→remember` », et
a posé un garde-fou explicite (§3, **D10**) :

> **D10** — la frontière de mutation reste **gelée** au seul `geo.mine_at`. Un verbe de **ramassage
> de surface** (KNAP, gather…) **ne mute pas** la géologie.

Ce gel a tenu à travers **17 wires** (C1–C12, C14–C16, C18, C20) : chacun ne consommait que
l'inventaire porté par l'agent, jamais la colonne géologique — chaque test l'asseyait par
`g_before == g_after`. Le gel était une décision de **séquençage**, pas une loi permanente : il
laissait mûrir le patron avant d'ouvrir l'acte le plus lourd.

Or **les trois capacités restantes de l'arc sont toutes métallurgiques et toutes mutantes** :
C13 `copper_smelting` (`smelt_at`), C17 `iron_bloomery` (`bloom_at`), C19 `bloom_forging`. Il
**n'existe plus aucune capacité non-mutante à brancher** : continuer l'arc **exige** de franchir
D10. Le wire #17 PROSPECT (le 1ᵉʳ acte purement cognitif) l'a préparé à dessein — l'agent
**connaît** désormais les taches vertes (`"copper" in prospected_ore_groups`) **avant** que la
métallurgie n'en mute le contenu. C'est le moment prévu.

La question tranchée ici : **comment un agent peut-il MUTER le monde sans violer l'émergence
absolue** (`feedback_no_scripting`, `feedback_stone_age_emergence`) ? Un arbre technologique
scripté (« si minerai vert + four chaud → produire métal ») reste interdit ; la mutation doit
rester **gouvernée par le monde**, pas par le code.

## Décision

### 1. D10 est **franchi**, mais uniquement par le SSOT mutant audité de la capacité

Un agent ne mute le monde **que** via l'unique point d'entrée mutant déjà asservi par test de la
capacité (`copper_smelting.smelt_at` → `geo.mine_at`, la SSOT d'extraction). Le wire **n'invente
aucune mutation** : il déclenche celle que C13 modélise et teste déjà (`test_copper_smelting` :
« la fonte effective »). La géologie change (`extracted_kg ↑`) — c'est **l'acte**, distinct de
l'oracle non-mutant (`smelt_cue_for_chunk`).

### 2. La mutation reste **émergente** — le monde décide, jamais une recette

L'agent ne « sait » pas fondre. Il a (a) découvert le four à tirage forcé (`has_forced_draught`,
C12 — seul régime ≥1085 °C), (b) **appris** que le vert signifie cuivre (PROSPECT/C1), (c) du
charbon en main (C4) — et en jetant la pierre verte dans sa braise rugissante, il **découvre** le
perlé de métal. Le **monde** décide du rendement (`copper_smelt_yield`, SSOT thermo+minéralogie) :
le cuivre natif coule en bouton, **la même** chalcopyrite (sulfure réfractaire) n'est que consommée
en scorie tant qu'elle n'est pas grillée (le **mensonge #4 vécu**). Aucune étape n'est débloquée par
recette ; la chaîne opératoire (creuset, tuyère, fluxage) reste émergente.

### 3. La chaîne de préconditions est **vécue**, jamais scriptée

`PROSPECT (vert==cuivre) → RAISE_KILN (C11) → FORCE_DRAUGHT (C12) → SMELT (C13)`. Chaque maillon
est une découverte antérieure réelle portée en mémoire ; aucun n'est un flag « débloqué ». Retirer
n'importe quel maillon rend le wire inerte (gates testés).

### 4. Honnêteté de la mutation : le bouton, pas le minerai brut

`geo.mine_at` porte un **pont Wave-1 legacy** (`_credit_agent_inventory`) qui crédite la masse de
minerai **brute** (minerai + gangue) à `inv_metal`/`inv_stone`. C'est faux pour une fonte : le
minerai est **réduit**, pas empoché tel quel. Le wire **corrige** ce crédit — seul le **bouton de
cuivre récupéré** (`recovered_cu_kg`) entre en `inv_metal`, la gangue part en scorie. « Le monde ne
ment jamais » vaut donc aussi *en acte* : l'inventaire reflète la physique, pas le bridge.

### 5. Garde-fous NON affaiblis par le franchissement

- **D8** — le wire **lit** C13 (qui compose C12 + C1), n'ajoute **aucun tell** ; `PY_TO_RUST`
  reste **15** (composition).
- **D9** — SMELT est **feu** (le four) → l'alternance passe **0→1** après le PROSPECT non-feu.
- **Hot-loop** — on ne **lit qu'un C13 déjà installé** (gate sur `_copper_smelt_cue_cache`) ;
  jamais d'`install_*` en cours de tick. Auto-limité (`inv_metal ≥ SMELT_METAL_SATED_KG`).
- **Déterminisme** — l'oracle est pur/mémoïsé ; `smelt_at` mute **déterministiquement** (même
  seed + même colonne ⇒ bouton bit-identique — asservi par p173 check 7 et le wire test).
- **Réutilisation d'`ActionKind`** — le wire **ne crée pas** de verbe : il rend **honnête** le
  `SMELT = 18` legacy (comme C3 l'a fait pour DRINK), branché dans la boucle de base `cognition`.

### 6. Portée : la mutation agent est ouverte au **sous-arc métallurgique**

Cet ADR autorise la mutation pilotée-agent pour la métallurgie (C13 aujourd'hui ; C17 `bloom_at`,
C19 suivront le **même patron** : SSOT mutant audité + préconditions vécues + monde qui décide).
Il **ne** généralise **pas** la mutation à tout verbe : hors métallurgie, D10 reste gelé (un
ramassage de surface ne mute toujours pas).

## Conséquences

**Positives.** L'arc atteint le **seuil chalcolithique VÉCU** : un agent produit le **premier
métal** de l'histoire de la simulation — D12 franchit sa dernière frontière conceptuelle. Établit
le patron réutilisable pour C17/C19. Sert directement H0 (une civilisation qui **transforme** son
substrat, pas seulement le ramasse).

**Négatives / dette.** (a) L'état du monde est désormais **muté par les agents** : le déterminisme
*sous mutation* devient un invariant à surveiller (couvert ici par le test wire + p173, à re-vérifier
à chaque wire mutant futur). (b) Le pont Wave-1 de `geo.mine_at` (`_credit_agent_inventory`) est une
**verrue legacy** que le wire doit corriger ligne à ligne ; à rationaliser (mine_at ne devrait pas
supposer une destination d'inventaire) — **backlog cleanup**. (c) `decide()`/`apply_decision`
grandissent d'un cran (borné par le registre `_ARC_SEEKS` + budget d'ADR-0009).

**Réversibilité.** Additif et gated : retirer l'entrée `("smelt", _seek_smelt)` du registre et la
branche `SMELT` d'`apply_decision` **regèle** D10 à l'identique de l'avant-ADR (l'arc métallurgique
redevient bibliothèque sans acteur). Décision donc **réversible**.

## Alternatives écartées

- **Garder D10 gelé indéfiniment** — l'arc ne pourrait **jamais** atteindre la métallurgie ; on
  abandonnerait la progression au cœur de H0. La découverte resterait *prouvée possible, jamais
  vécue* pour tout le tiers métallurgique. Rejeté.
- **Recette de fonte scriptée** (« vert + 1085 °C → cuivre ») — viole l'émergence absolue
  (`feedback_no_scripting`). Rejeté frontalement ; le monde décide via `copper_smelt_yield`.
- **Cerveau LLM décisionnel pour la fonte** — viole le sandboxing (ADR-0002) et l'environnement
  *cargo-less*. La sélection par utilité déterministe + préconditions vécues suffit.
- **Nouveau `ActionKind` dédié** — inutile : `SMELT = 18` existe déjà (legacy) ; le rendre honnête
  est plus propre et cohérent avec C3/DRINK.
