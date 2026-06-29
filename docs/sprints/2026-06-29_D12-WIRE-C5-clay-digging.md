# Sprint 2026-06-29 (run 2) — D12 wire #8 : la boucle agent CREUSE l'argile (consomme C5)

> **Type :** `feat(agentic/cognition)` / câblage d'arc. **Acte :** [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Suite de :** wire #7 C8 TEMPER (même jour, run 1). **8ᵉ bouchée → 8/20.**
> **Précurseur NON-FEU** — rétablit l'alternance feu/non-feu après IGNITE (C7) + TEMPER (C8).

## Veille (obligatoire, avant code)

Règle d'or respectée. Recherche ciblée (foraging multi-agents à retour énergétique ;
stratégies préhistoriques de collecte de matières ; *Semantic Information in Resource Gathering
Agents*). **Apport : validation de la direction** (collecte de matières émergente = brique de
boucle agent), pas de pivot. Aucune brique externe intégrable (cargo-less). **CVE : aucune
critique.**

**COMBO_RETENU :** `utility-based action selection` × `C5 clay_outcrop` → 8ᵉ tranche. Précurseur
non-feu choisi pour (a) rétablir l'alternance D9, (b) amorcer la **chaîne céramique** : l'argile
est la matière que **C9 `ceramic_firing`** consommera une fois branché. Couche **Agentic**. Pas de
nouvel ADR.

## La tranche livrée

Dans `cognition.decide()`, après le cluster outils/feu/trempe et **avant** le symbolique
`_seek_ochre` : un agent rassasié et curieux qui **perçoit** (`clay_outcrop.best_clay_near`, C5)
une berge d'argile travaillable marche jusqu'à elle et la **CREUSE** (`ActionKind.DIG = 25`) →
`inv_clay` se remplit ∝ `pottery_grade` *réelle* × travaillabilité. La position entre en
`EpisodicMemory.known_clay_locations` ; `last_clay_class` retient **quelle** argile (SHALE_CLAY /
PLASTIC_CLAY) — appris **par l'acte**.

**Ordre dans `decide()` :** GATHER(frost) → KNAP → IGNITE → TEMPER → **DIG(argile)** → GRIND →
MARK → EXPLORE. **La matière utile avant l'art.** DIG travaille sur sa **propre** réserve
(`inv_clay`), donc ne concourt jamais avec les pools pierre/pigment.

### Nouveau champ d'inventaire `inv_clay` (précédent `inv_pigment`)

Contrairement aux wires #1–#7, C5 produit une matière sans réserve existante. `inv_clay` est ajouté
**exactement comme `inv_pigment` l'a été** : champ dataclass `AgentRegistry`, boucle d'init, **et
les deux listes de persistance** (`global_world`, `world_library`) — chargement défensif
(`if fld in loaded.files`), donc **les anciennes sauvegardes restent compatibles** (champ absent →
zéros). `inv_clay` figurait déjà dans `_INVENTORY_MASS_FIELDS` (matière brute = masse portée) →
compté dans la capacité, cohérent avec les gardes `cap_left` de DIG.

### Le mensonge rendu visible #13 (la berge d'argile ment au potier)

« Une belle berge d'argile fait toujours de la bonne argile » → **FAUX** : une **kaolinite
plastique** dans sa fenêtre de plasticité se creuse en argile céramique fine (rendement ∝
`pottery_grade`) ; un **schiste silteux** (SHALE_CLAY) lui ressemble mais travaille mal ; et une
berge **hors fenêtre plastique** (trop sèche à façonner / trop liquide en boue → `workable_now`
False) ne rend que la **fraction humide** (`DAMP_CLAY_FACTOR`) tant qu'elle n'est pas conditionnée.
`best_clay_near` route vers la meilleure berge ; creuser une mauvaise enseigne le mensonge **en
agissant**.

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (le wire n'ajoute aucun tell) | ✅ lit C5 ; `PY_TO_RUST` reste **15** |
| **D10** (mutation gelée à `geo.mine_at`) | ✅ DIG = collecte de surface, **0 mutation géologie** (pas de `mine_at(` dans la branche DIG) |
| **D9** (alternance feu/non-feu) | ✅ **NON-FEU** — rétablit l'alternance après IGNITE+TEMPER |
| **Hot-loop** | ✅ gate sur C5 déjà installé ; jamais d'`install_*` en tick |
| **Zéro-régression par construction** | ✅ `bootstrap` n'installe pas C5 → wire inerte partout sauf `install_clay_outcrop` |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, 0 RNG nouveau |
| **Back-compat persistance** | ✅ `inv_clay` ajouté défensivement aux deux listes → anciennes sauvegardes OK |

**Nouvel état :** `ActionKind.DIG = 25` ; `AgentRegistry.inv_clay` (nouveau champ) ;
`EpisodicMemory.{known_clay_locations, last_clay_class}`.

## Vérif

- `runtime/tests/test_clay_digging_loop.py` — **12 tests** (gate sans C5 ; choix DIG/WALK_TO ;
  remplissage + mémoire ; plastique > schiste ; mensonge #13 fenêtre plastique ; site stérile ;
  saturation ; survie>argile ; back-compat `sim=None` ; orthogonalité inv_clay≠pierre/outils/pigment ;
  non-mutation géologie ; déterminisme).
- `runtime/scripts/p163_clay_digging_loop_smoke.py` — **8/8** (boucle live, seed `0x42` ; plastique
  > schiste ; mensonge #13 sur seed `0xF00D` ; `sim.step()` propre ; gate + déterminisme ; D8/D10).
- `pytest` du nouveau test **vert** (12/12) ; `ruff` clean (fichiers neufs). Portail smoke CI
  p162 → **p163**.
- **Non-régression vérifiée live :** p162 (TEMPER) **9/9** après le réordonnancement de `decide()`
  et l'ajout d'`inv_clay`.

## Reste

12 capacités (C1, C4, C6, C9–C13, C15–C17, C19) + piliers **langage**/**bâtiments**. L'argile
posée, le candidat naturel suivant est soit **C6 `limestone_outcrop`** (l'autre matière du four —
calcaire → chaux) pour continuer d'alimenter en intrants, soit la **1ʳᵉ transformation à deux
ingrédients** **C9 `ceramic_firing`** (argile `inv_clay` + feu `has_made_fire` → poterie cuite),
qui *consommerait* enfin l'argile qu'on vient de rendre récoltable — bouclant argile→feu→pot.
