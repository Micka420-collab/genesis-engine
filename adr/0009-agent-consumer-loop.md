# ADR 0009 — La boucle agent consomme l'arc : `perceive→decide→act→remember` comme frontière de la découverte vécue

- **Statut** : Accepted
- **Date** : 2026-06-24
- **Décideurs** : Lead Engineer (morning-routine auto, J+14 du delta-audit)
- **Suite de** : [ADR-0008](0008-python-rust-frontier.md) (runtime Python = couche active) ·
  exécute **R-J13-1 (P0)** de [`AUDIT-DELTA-2026-06-23.md`](../native/world-engine/AUDIT-DELTA-2026-06-23.md) ·
  prolonge la **1ʳᵉ bouchée** de D12 (DRINK / C3, commit `2d0ebd0`).

## Contexte

L'audit J+13 a nommé le **trou architectural dominant**, **D12 / R0** :

> Le projet a **deux moitiés qui ne se touchent pas** — un **arc de 20 capacités**
> émergentes C1→C20 (riche, testé, discipliné) qui **ne se compose que lui-même**
> et n'est **invoqué que par ses propres tests + smokes** ; et une boucle agent
> (`cognition.perceive→decide→apply_decision`) qui tourne mais **n'importe AUCUNE
> des 20 capacités**. Les 20 affordances sont **véridiques mais sans consommateur** :
> la découverte est *prouvée possible*, **jamais vécue**.

C'est la contradiction centrale d'un « civ-sim où les agents découvrent ». Le fix
DRINK / C3 (R-J13-4) a pris la 1ʳᵉ bouchée — mais en *corrigeant une action
existante* (boire devient honnête face à la salinité), pas en **donnant à la boucle
un comportement nouveau** piloté par la perception d'une capacité.

La question non tranchée : **comment un agent consomme-t-il l'arc sans violer
l'émergence absolue** (`feedback_no_scripting`, `feedback_stone_age_emergence`) ?
Un arbre technologique scripté (« si pierre alors tailler → débloque outil ») est
explicitement interdit. Il faut une frontière qui laisse le **monde** décider, pas
le code.

## Décision

### 1. La boucle de consommation canonique = `perceive → decide → act → remember`

Un agent consomme une capacité de l'arc **uniquement** via les quatre temps de
`cognition` (les trois appels exacts que `Simulation.step` fait déjà par agent,
plus l'écriture mémoire) :

1. **perceive** — la capacité expose un *signal de monde véridique interrogeable*
   (`discover_*_by_sight`, `best_*_near`, `prospect_*`, `*_cue_for_chunk`) ; jamais
   un fait poussé à l'agent.
2. **decide** — l'agent **choisit** par *utilité* (utility-based action selection,
   cf. Project SID / JaxLife) : la capacité s'insère dans `decide()` **strictement
   sous les drives de survie** et au-dessus de l'exploration aléatoire. Aucun
   ordre scripté ; un trait (curiosité…) module la propension.
3. **act** — `apply_decision` exécute un verbe (`ActionKind`) ; le **monde**
   détermine le résultat (qualité, rendement, échec) à partir du *cue véridique*.
4. **remember** — le résultat entre dans `EpisodicMemory` (`known_*_locations`,
   `remember_short`) ; l'agent **apprend la corrélation par l'action**, jamais par
   donnée pré-câblée.

### 2. Invariant « le monde ne ment jamais » étendu au COMPORTEMENT

Comme pour DRINK, la consommation doit être honnête *en acte*, pas seulement en
perception : une pierre d'aspect tranchant qui n'est pas taillable ne **rend** pas
d'outil ; un site sans indice ne **rend** rien et n'est **pas mémorisé**. Le
mensonge perceptible (un beau caillou stérile) n'est **levé que par l'action**.

### 3. Garde-fous repris des capacités (pas affaiblis par le câblage)

- **D8** — la consommation **lit** la capacité, n'ajoute **aucun tell** ; `PY_TO_RUST`
  inchangé (composition).
- **D10** — la frontière de mutation reste **gelée** au seul `geo.mine_at`. Un verbe
  de **ramassage de surface** (KNAP, gather…) **ne mute pas** la géologie.
- **D9** — le câblage n'est pas une capacité « Wave/Cap » et ne perturbe pas
  l'alternance feu/non-feu ; c'est un `fix(cognition)`, comme DRINK.
- **Hot-loop** — on ne **lit qu'une capacité déjà installée** (gate sur son cache) ;
  jamais d'`install_*` en cours de tick (corromprait la chaîne de wrappers
  `apply_decision`).
- **Déterminisme** — dérivation pure + cues mémoïsés ; aucun RNG nouveau.

### 4. 1ʳᵉ application : KNAP (consomme C2 `lithic_outcrop`)

Un agent rassasié et curieux qui **voit** un affleurement taillable y va et **taille**
un éclat (`ActionKind.KNAP`) au lieu d'errer ; `inv_stone` se remplit, `inv_tools`
gagne un **tranchant proportionnel à la `knap_quality` réelle** du cue (obsidienne →
rasoir ; bloc à meule → médiocre ; site stérile → rien). 1ᵉʳ remplisseur de
`inv_tools` de tout l'arc — le **premier outil réellement fabriqué** par un agent.

## Conséquences

**Positives.** D12 passe de *R0 ouvert* à *en cours de fermeture* (2ᵉ capacité
consommée après C3 ; 1ʳᵉ qui crée un **comportement agent nouveau**). Établit le
**patron réutilisable** pour brancher les 18 capacités restantes (C1, C4–C20) et,
à terme, les piliers langage / bâtiments — sans jamais scripter d'arbre tech.

**Négatives / dette.** (a) `decide()` est sur le **chemin chaud** : chaque capacité
branchée y ajoute une lecture ; on borne par gate (curiosité + survie satisfaite) et
mémoïsation, mais un futur **registre de capacités** + un budget de perception
seront nécessaires au-delà de quelques branchements (suivi backlog). (b) De
nombreuses capacités réassignent globalement `cognition.decide`/`apply_decision`
(wrappers sans teardown) : la boucle de consommation vit dans les **fonctions
originales** ; tests et smoke capturent les originaux pour rester déterministes
(dette `D8`-adjacente, à rationaliser via un dispatch de wrappers ordonné).

**Réversibilité.** Le câblage est additif et gated ; retirer l'appel `_seek_toolstone`
de `decide()` et la branche `KNAP` rend la boucle identique à l'avant-ADR (l'arc
redevient bibliothèque sans joueur). Décision donc **réversible**.

## Alternatives écartées

- **Arbre technologique scripté** (recettes « pierre→outil→… » débloquées) —
  viole l'émergence absolue (`feedback_no_scripting`). Rejeté frontalement.
- **Cerveau LLM décisionnel** — viole l'invariant de sandboxing (ADR-0002, pas
  d'agent LLM avec état décisionnel) et l'environnement *cargo-less* / externes
  gated. La sélection par utilité déterministe est suffisante au stone age.
- **Registre de capacités + ECS de consommation tout de suite** — sur-ingénierie
  pour 2 capacités branchées ; on l'introduira quand le nombre de branchements le
  justifiera (noté backlog). On préfère **une tranche verticale prouvée** à une
  abstraction prématurée.
