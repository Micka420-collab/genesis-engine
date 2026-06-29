# Sprint 2026-06-29 (run 6) — D12 wire #11 : la boucle agent CUIT la chaux (consomme C10)

> **Type :** `feat(agentic/cognition)` / câblage d'arc via le registre `_ARC_SEEKS`.
> **Acte :** [ADR-0009](../../adr/0009-agent-consumer-loop.md). **Suite de :** C6 QUARRY (run 5).
> **11ᵉ bouchée → 11/20.** **2ᵉ transformation à deux ingrédients** — miroir exact de C9 FIRE_CLAY :
> argile→pot :: calcaire→chaux.

## Veille (obligatoire, avant code)

Règle d'or respectée. La chaux = *« Burning Lime, the oldest chemical industry on Earth »*,
néolithique (enduits de Göbekli Tepe ~9500 av. J.-C.), antérieure à la métallurgie. C10 est le
**pendant exact de C9** : C9 cuit l'argile (contient), C10 brûle le calcaire (lie). **Apport :
validation**, pas de pivot. Aucune brique externe (cargo-less). **CVE : aucune.**

**COMBO_RETENU :** `utility-based action selection` × `C10 lime_burning` → 11ᵉ tranche, la 2ᵉ
transformation à deux intrants, qui *consomme* le calcaire que C6 QUARRY (run 5) rend récoltable —
boucle calcaire→feu→chaux. Couche **Agentic**. Pas de nouvel ADR.

## La tranche livrée — la 2ᵉ chaîne se referme

Append d'une ligne au registre (`("limekiln", _seek_limekiln)` après `limestone`). Un agent qui
**SAIT faire le feu** (`has_made_fire`, C7) **ET porte du calcaire** (`inv_limestone ≥ cost`, C6)
et **perçoit** un site de cuisson (`lime_burning.best_burning_site_near`, require_well_burnt) marche
jusqu'à lui et le **CALCINE** (`ActionKind.CALCINE = 28`) → chaux vive caustique (`inv_lime`) ∝
`lime_yield` *réelle*. `apply_decision` **consomme** `inv_limestone` et **émet** `inv_lime` — le 2ᵉ
flux matière inter-capacités piloté par l'agent (après argile→céramique). Mémoire :
`known_limekiln_locations`, `has_burnt_lime`, `last_lime_yield`.

**Ordre dans `decide()` :** … → limestone (QUARRY) → **limekiln (CALCINE)** → ochre → … (la chaîne
carbonate calcaire→chaux, miroir de la chaîne argile clay→kiln).

### Le mensonge rendu visible #16 — l'inversion réfractaire (la même que C9)

Un **feu ouvert** ne cuit jamais *dur* : il ne produit qu'une **chaux aérienne** (douce, pour le
lait de chaux) — **jamais** la chaux de mortier hard-burnt (`mortar_ready` **toujours False** ; il
faudra un four à chaux, bouchée future). Et une pierre **sous-cuite** (feu trop froid / carbonate
impur) consomme le calcaire pour **rien** — un cœur cru qui se re-carbonate. `best_burning_site_near
(require_well_burnt)` route vers la cuisson utilisable ; cuire un site sous-cuit l'enseigne **en
agissant**. Exactement l'inversion réfractaire de C9 (terre cuite oui, vitrifié non).

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **D8** (le wire n'ajoute aucun tell) | ✅ COMPOSE C6 × C7 ; `PY_TO_RUST` reste **15** |
| **D10** (mutation gelée) | ✅ CALCINE = transformation, **0 `geo.mine_at`** |
| **Dépendances honorées** | ✅ gate sur `has_made_fire` **et** `inv_limestone` — sans feu OU sans calcaire, pas de chaux |
| **Hot-loop / Zéro-régression** | ✅ gate sur C10 installé ; `bootstrap` n'installe pas C10 → inerte par défaut |
| **Back-compat persistance** | ✅ `inv_lime` ajouté défensivement aux deux listes |
| **Déterminisme** | ✅ dérivation pure + cues mémoïsés, 0 RNG |

**Nouvel état :** `ActionKind.CALCINE = 28` ; `AgentRegistry.inv_lime` (nouveau champ) ;
`EpisodicMemory.{known_limekiln_locations, has_burnt_lime, last_lime_yield}` ; `_ARC_SEEKS` → **10 entrées**.

## Vérif

- `runtime/tests/test_lime_burning_loop.py` — **13 tests** (gate ; dépendance feu ; dépendance
  calcaire ; choix CALCINE/WALK_TO ; consomme calcaire + produit chaux + mémoire ; inversion #16
  sous-cuit + mortar_ready False ; site stérile → calcaire conservé ; survie ; saturation ;
  back-compat ; orthogonalité ; déterminisme).
- `runtime/tests/test_arc_seek_registry.py` — **6 tests** (registre à 10 entrées, `limekiln` après `limestone`).
- `runtime/scripts/p166_lime_burning_loop_smoke.py` — **8/8** (live, seed `0xBEEF` ; deux dépendances ;
  inversion #16 ; `sim.step()` propre ; gate + déterminisme ; D8/D10).
- `pytest` (chaux + registre) **19/19** ; `ruff` clean. Portail smoke CI p165 → **p166**.
- **Non-régression vérifiée live :** p165 (QUARRY, entrée précédant `limekiln`) **8/8**.

## Reste

9 capacités (C1, C4, C11–C13, C15–C17, C19) + piliers **langage**/**bâtiments**. Les deux chaînes
pyrotechnologiques de base sont vécues (argile→pot, calcaire→chaux). Suite naturelle : **C13
`copper_smelting`** (la métallurgie : minerai + combustible + feu → métal `inv_metal`) — qui
introduirait l'usage du **combustible C4** (encore non branché) ; ou **C4 `combustible_outcrop`**
(récolte de combustible, précurseur non-feu) d'abord. Le **four** (C11/C12) lèverait l'inversion
réfractaire des deux chaînes (vitrification + mortier hard-burnt). Append trivial au registre dans
tous les cas.
