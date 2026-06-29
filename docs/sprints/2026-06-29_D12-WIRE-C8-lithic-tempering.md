# Sprint 2026-06-29 — D12 wire #7 : la boucle agent TREMPE la pierre au feu (consomme C8)

> **Type :** `feat(agentic/cognition)` / câblage d'arc (pas une nouvelle capacité « Cap. CN »).
> **Acte :** [ADR-0009](../../adr/0009-agent-consumer-loop.md). **Suite de :** DRINK/C3, KNAP/C2,
> GATHER/C14, GRIND/C18, MARK/C20, IGNITE/C7 — les six premières bouchées de D12.
> **7ᵉ bouchée → 7/20.** Premier consommateur **en aval du feu** (C7, la VOÛTE, câblée hier).

## Veille (obligatoire, avant code)

Règle d'or respectée. Recherche ciblée (ALIFE 2026 « la vie = processus émergent » ; *emergent
tool use from multi-agent autocurricula* ; Project Sid / JaxLife / AIvilization). **Apport :
validation de la direction, pas de pivot** — cohérent avec les 16 jours précédents. Aucune brique
externe intégrable dans l'environnement cargo-less (Rust gelé ADR-0008 ; 0 surface réseau →
PQC N/A). **CVE actives : aucune critique** (numpy / PCG64 clean).

**COMBO_RETENU :** `utility-based action selection (SID/JaxLife)` × `C8 lithic_tempering` → 7ᵉ
tranche verticale de consommation d'arc. **0 LLM, 0 dépendance nouvelle, 0 nouveau champ
d'inventaire.** Couche **Agentic**. Pas de nouvel ADR (ADR-0009 a déjà ratifié le patron ; 7ᵉ
application).

## Le problème (D12 / R0)

Hier, le feu (C7) est devenu **vécu** — mais comme une **fin** (se réchauffer), pas encore comme
un **moyen**. La VOÛTE était posée sans premier étage. C8 `lithic_tempering` est, dans l'arc, **la
toute première utilisation du feu SUR une matière** : la plus ancienne pyrotechnologie après le
feu lui-même (chauffer lentement un nodule de silice cryptocristalline — silex/chert — pour que
sa fracture conchoïdale devienne plus régulière, attesté à Pinnacle Point ~72 ka). La brancher,
c'est donner au feu son **premier consommateur en aval** et refermer une boucle entre les deux
capacités les plus établies de la boucle agent : **KNAP (C2)** produit une pierre, **IGNITE (C7)**
produit un feu, **TEMPER (C8)** marie les deux en un **meilleur tranchant**.

## La tranche livrée

Dans `cognition.decide()`, sous les drives de survie et **après** `_seek_firesite` : un agent
**rassasié, curieux et qui SAIT déjà faire du feu** (`mem.has_made_fire`) qui **perçoit**
(`lithic_tempering.best_temper_site_near`, C8) une silice réactive à la chaleur marche jusqu'à elle
et la **TREMPE** (`ActionKind.TEMPER = 24`) → un tranchant (`inv_tools`) ∝ `tempered_quality`
*réelle* (qualité de taille post-traitement, bornée à `TEMPER_CEILING` 0,95, ground-truthée par le
monde). La position entre en `EpisodicMemory.known_temper_locations` ; `has_tempered_stone` et
`last_temper_gain` enregistrent la compétence apprise **par l'acte**.

**Ordre dans `decide()` :** `_seek_frost_clast` (GATHER) → `_seek_toolstone` (KNAP) →
`_seek_firesite` (IGNITE) → **`_seek_tempersite` (TEMPER)** → `_seek_ochre` (GRIND) →
`_seek_canvas` (MARK) → EXPLORE. **La pierre, puis le feu, puis la trempe — les outils avant
l'art.** Le smoke `p162` (check 1b) montre l'arc **vécu de bout en bout** sur un seul site
chert+feu : `KNAP, KNAP, IGNITE, TEMPER, TEMPER…` — l'agent ramasse la pierre, allume le feu,
puis la trempe, sans aucun script.

### L'orthogonalité (TEMPER ≠ KNAP ≠ IGNITE)

- **KNAP / C2** = *casser* un affleurement → pierre brute + tranchant ∝ `knap_quality` brute.
- **IGNITE / C7** = *amorcer* un feu → **chaleur** (drive thermique baisse) + compétence `has_made_fire`.
- **TEMPER / C8** = *chauffer* une silice dans ce feu → tranchant **supérieur** ∝ `tempered_quality`
  (le **premium pyrotechnologique** : `tempered_quality ≥ base`). 10ᵉ verbe primitif. **Réutilise
  `inv_tools`** (aucun nouveau champ d'inventaire → aucune migration de persistance).

### Le mensonge rendu visible #12 (l'obsidienne ment au tailleur qui découvre le feu)

« La meilleure pierre à tailler doit être la meilleure à passer au feu » → **FAUX** :
l'obsidienne (verre volcanique, `base_quality` 1,0) **semble** la candidate idéale au foyer — mais
la chauffer ne gagne **rien** (déjà parfaite, et risque de la fendre). `best_temper_site_near` ne
route **jamais** vers un site non-trempable (gain 0 → pas de cue) ; broyer… pardon, **tremper** une
obsidienne barrée directement (`prospect_tempering` → None) n'enseigne le mensonge qu'**en
agissant** (pas de tranchant gagné). Chert (Δ≈0,20) répond fort, quartzite (Δ≈0,12) modestement,
obsidienne 0 — tous **émergent** de la pétrologie réelle (« le monde ne ment jamais », étendu au
comportement).

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (pas de nouveau tell) | ✅ COMPOSE C2 × C7 ; `PY_TO_RUST` reste **15** ; `lithic_tempering` n'a pas de `_PROFILE` |
| **D10** (mutation gelée à `geo.mine_at`) | ✅ TEMPER = chauffe d'un nodule, **0 mutation géologie** (vérifié : pas de `mine_at(` dans la branche TEMPER) |
| **D9** (alternance feu/non-feu) | ✅ `feat(cognition)`, câblage (pas une capacité Wave/Cap) — exempt de l'alternance |
| **Dépendance au feu honorée, pas scriptée** | ✅ gate sur `has_made_fire` : un agent qui n'a jamais fait de feu **ne trempe pas** (le monde, pas un arbre tech, l'en empêche) |
| **Hot-loop** | ✅ gate sur C8 déjà installé ; **jamais** d'`install_*` en tick |
| **Zéro-régression par construction** | ✅ `bootstrap_genesis_sim` n'installe **pas** C8 → wire **inerte** partout sauf `install_lithic_tempering` explicite |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, **0 RNG nouveau** |
| **Émergence absolue** | ✅ aucun arbre tech ; le monde décide le gain (et le mensonge obsidienne) |

**Nouvel état :** `ActionKind.TEMPER = 24` ; `EpisodicMemory.{known_temper_locations,
has_tempered_stone, last_temper_gain}`. **Aucun nouveau champ `AgentRegistry`** (réutilise
`inv_tools`) → **aucune migration de persistance**, risque minimal.

## Vérif

- `runtime/tests/test_lithic_tempering_loop.py` — **14 tests** (gate sans C8 ; dépendance feu
  sans/avec `has_made_fire` ; choix TEMPER/WALK_TO ; rendement = `tempered_quality` ; premium
  trempe ≥ taille à froid ; site stérile inerte ; routage jamais vers non-trempable ; saturation
  outils ; survie>trempe ; back-compat `sim=None` ; orthogonalité tools≠pierre/pigment ; non-mutation
  géologie ; déterminisme).
- `runtime/scripts/p162_lithic_tempering_loop_smoke.py` — **9/9** (boucle live
  perceive→decide→act→remember sur monde réel à chert+feu, seed `0xBEEF` ; **arc vécu
  KNAP→IGNITE→TEMPER** ; chert>quartzite ; mensonge #12 ; dépendance feu ; `sim.step()` propre ;
  gate + déterminisme ; D8/D10).
- `pytest` (set de l'arc) **vert** (+14 tests) ; `ruff` clean (fichiers neufs : `+test_lithic_tempering_loop.py`,
  glob smoke `p162`). Portail smoke CI étendu p161 → **p162** (`Makefile` + `ci.yml`).
- **Non-régression :** wire inerte hors `install_lithic_tempering` (bootstrap ne l'installe pas) →
  les smokes des six wires précédents (p153/p155/p158/p160/p161) restent intacts par construction.

> **Note d'implémentation :** comme pour les wires précédents, de nombreuses capacités réassignent
> globalement `cognition.decide`/`apply_decision` (wrappers sans teardown). Le wire vit dans les
> fonctions **originales** ; tests + smoke capturent les originaux à l'import pour rester
> déterministes (dette notée ADR-0009 §Conséquences → futur dispatch ordonné).

## Reste

13 capacités (C1, C4–C6, C9–C13, C15–C17, C19) + piliers **langage**/**bâtiments** à brancher,
même patron, une tranche verticale à la fois. **Le feu a désormais son premier étage** (la trempe) ;
les prochains consommateurs naturels du feu sont la **cuisson de l'argile** (C9 `ceramic_firing`,
qui exige aussi C5 `clay_outcrop`), la **calcination de la chaux** (C10 `lime_burning`, qui exige
C6 `limestone_outcrop`), et la **fonte du cuivre** (C13 `copper_smelting`). Candidat le plus
naturel pour la 8ᵉ bouchée : brancher d'abord un **précurseur non-feu** (C4 `combustible_outcrop`,
ramasser du combustible — rétablit l'alternance et nourrit le feu) **ou** C5/C6 (les matières que
le feu transformera), avant les transformations à deux ingrédients.
