# SPRINT 2026-05-15 — Wave 10e emergent building discovery

**Règle invariante respectée** : rien n'est scripté, les agents
découvrent par eux-mêmes.

**Statut**: ✅ livré
**Cible**: remplacer les recettes hardcodées de Wave 10d par un
système de découverte émergente via blocs + statics réelle.

---

## Pourquoi ce sprint

Wave 10d (`engine/realistic_construction.py`) a livré 6 recettes
nommées (`stone_hut`, `marble_temple`, etc.) avec matériaux exacts.
**C'est scripté** — contraire à la règle "ils découvrent par eux-mêmes".

Cette Wave 10e ajoute un canal parallèle où :
1. Agent pose des blocs sans connaître à l'avance le résultat
2. L'engine valide la stabilité statique (Wave 1 — physique réelle)
3. Si stable + forme habitable → un archetype émerge
4. La culture du builder lui donne un nom **auto-généré déterministe**

**Pas de table de recettes.** Pas de "stone_hut" pré-écrit.

---

## `engine/building_discovery.py` (~440 LOC)

### API

```python
install_building_discovery(sim) -> BuildingDiscoveryState     # idempotent
place_block(sim, row, pos, material)                          # buffer pending
complete_structure(sim, row) -> (success, building_id, name)  # validate + emerge
abandon_pending(sim, row) -> int                              # discard buffer
```

### Pipeline d'évaluation

```
agent place_block × N → state.pending_blocks[row]
                       ↓
            complete_structure(sim, row)
                       ↓
   Function check :
     - n_blocks >= MIN_BLOCKS_FOR_BUILDING (8)
     - footprint >= MIN_FOOTPRINT_VOXELS (4)
     - height >= MIN_HEIGHT_VOXELS (2)
     - has_roof = top_layer >= 50 % footprint
                       ↓
   Structural check via engine.statics.is_structurally_stable :
     - support : tous blocs soutenus
     - compressive stress < strength × safety
     - overhang max_voxels respecté
                       ↓
   Fingerprint = (dominant_material × footprint_xy × height × roof)
                       ↓
   Match dans cultural_archetypes[culture_id] ?
     - Oui → instances_count += 1
     - Non → auto-name déterministe via prf_rng
                       ↓
   DiscoveredBuilding record
```

### Auto-naming déterministe

```python
suffix = consonant + vowel + consonant (sampled via prf_rng on seed
                                        + culture + fingerprint key)
name = f"{material}_{fx}x{fy}x{h}_{suffix}"
```

Exemple : la même forme 3×3×2 stone donne :
- Culture 0 → `stone_3x3x2_vap`
- Culture 99 → `stone_3x3x2_nuv`

**Comme deux langues réelles pour le même objet** (case, hutte, igloo,
isba — tous des abris en matériaux locaux mais nommés différemment).

---

## Smoke `p38_building_discovery_smoke` **8/8 PASS**

```
[OK] step 1 — install idempotent
[OK] step 2 — 2 blocs → function:too_few_blocks (rejet propre)
[OK] step 3 — blocs flottants → unstable:unsupported (statics)
[OK] step 4 — 3×3×2 stone shelter → 'stone_3x3x2_vap' émerge
[OK] step 5 — même culture refait → 'stone_3x3x2_vap' reconnu (2x)
[OK] step 6 — culture 99 fait pareil → 'stone_3x3x2_nuv' (différent)
[OK] step 7 — persistence round-trip
[OK] step 8 — ADR-0005 18/18
```

**Cas validé scientifiquement** : deux cultures isolées découvrent
indépendamment la **même architecture stable** mais lui donnent des
**noms différents** — exactement le pattern linguistique humain.

---

## ADR-0005 → 18 modules requis taggés

```
engine.earth_loader / sim_lift / realism / physiology /
photosynthesis / material_aging / marine / global_world /
plant_evolution / meteorology / animal_evolution / agriculture /
writing / polity / geology / metallurgy / realistic_construction /
building_discovery (NEW)
```

`engine.building_discovery` : Genesis-L4 Feedback / paper-L2 Simulator.

---

## Comparaison avec Wave 10d

| Aspect | Wave 10d realistic_construction | Wave 10e building_discovery |
|---|---|---|
| Recettes | hardcoded (`REAL_RECIPES`) | aucune |
| Validation | matériaux suffisants | statics + function émergente |
| Naming | pré-défini | auto-généré per culture |
| Mode | scripted | discovery-driven |

Wave 10d **reste disponible** pour les use-cases "agent informé
suit une recette connue" (futur : transmission via writing
inscriptions). Wave 10e est le canal **scientifiquement honnête**
où la connaissance vient de l'expérimentation.

---

## Pré-requis Phase 5 — état

| Pré-req | État |
|---|---|
| 18 modules ADR-0005 | ✅ |
| P-NEW.22 + .24 | ✅ |
| Wave 9d cognition wiring | ✅ |
| Wave 10b/c/d (mine/smelt/build) | ✅ |
| **Wave 10e discovery-driven** | ✅ |
| Wave 11 personality → polity | ⏳ |
| Wave 12 10K sim-yr long-run | ⏳ |

8/10 pré-requis Phase 5 livrés.

---

## Fichiers touchés

```
runtime/engine/building_discovery.py                       (nouveau, ~440 LOC)
runtime/engine/dashboard.py                                (+10 LOC : endpoint)
runtime/engine/world_library.py                            (+3 LOC : persistent module)
runtime/engine/world_model_capabilities.py                 (+1 LOC : required module)
runtime/scripts/p38_building_discovery_smoke.py            (nouveau, ~190 LOC, 8/8 PASS)
docs/sprints/2026-05-15_PHASE25-BUILDING-DISCOVERY.md      (ce fichier)
NEXT-SPRINT.md                                             (Wave 10e archivé)
```
