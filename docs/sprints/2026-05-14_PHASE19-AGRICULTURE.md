# SPRINT 2026-05-14 — Phase 4 agriculture

**Priorité attaquée**: Phase 4 — Émergence Civilisationnelle —
**agriculture** (premier livrable des trois : agriculture + écriture + État).

**Statut**: ✅ livré
**Cible**: agents peuvent semer + récolter, plant_evolution devient
ressource civilisationnelle active, déterminisme préservé.

---

## Roadmap §44-49 — où on en est

| Phase | État |
|---|---|
| Phase 0 — Foundations | ✅ |
| Phase 1 — MVP Vie | ✅ |
| Phase 2 — MVP Société | ✅ |
| **Phase 3 — MVP Civilisation** | 🟡 partiel (construction ✓, troc ✓, métiers ?, conflits ✓) |
| **Phase 4 — Émergence Civilisationnelle** | 🟡 **agriculture ✓**, écriture ⏳, État ⏳ |
| Phase 5 — Genesis-α Public | ⏳ |

---

## `engine/agriculture.py` (~330 LOC)

### État

```python
@dataclass class CultivatedField:
    clade: str
    owner_culture: int
    sown_tick: int
    last_harvest_tick: int
    harvest_count: int
    total_kcal_harvested: float

@dataclass class AgricultureState:
    fields_per_chunk: Dict[coord → List[CultivatedField]]
    culture_seed_library: Dict[culture_id → Set[clade_name]]
    plant_events / harvest_events / total_kcal_harvested / discoveries
```

### API

| Fonction | Effet |
|---|---|
| `discover_seed(state, culture, clade)` | Ajoute clade à la library d'une culture. True si nouveau. |
| `plant_seed(sim, state, row, clade)` | Inject 40 kg du clade dans `plant_evolution.ChunkVegetation`. Gated par `culture_seed_library`. |
| `harvest(sim, state, row)` | Choisit le clade édible le plus rentable du chunk, tire 50% biomasse, crédit `inv_food` (cap 10 kg). Découvre automatiquement le clade pour la culture (forage-time discovery). |
| `maybe_record_forage_discovery(sim, state, row)` | Hook FORAGE : ajoute tous les clades édibles présents au seed library. |
| `tick_agriculture(sim, state)` | Per-tick : boost ×1.5 sur fields cultivés (pression de sélection artificielle). |

### Constantes calibrées

```python
SEED_BIOMASS_KG = 40.0                # injection par PLANT
HARVEST_FRACTION = 0.5                # 50% durable
HARVEST_INVENTORY_CAP_KG = 10.0       # par agent par récolte
CULTIVATED_GROWTH_BONUS = 1.5         # selection pressure
```

---

## `ActionKind` étendu

```python
class ActionKind(IntEnum):
    ...
    HUNT = 14
    # Phase 4 — Émergence civilisationnelle.
    PLANT = 15       # sow a known seed clade
    HARVEST = 16     # gather standing biomass
```

L'wiring dans `cognition.apply_decision` reste à faire (sera Wave 9b).
Pour l'instant les fonctions `plant_seed` / `harvest` sont callable
manuellement (test + futur scripting agent).

---

## Smoke `p30_agriculture_smoke` 10/10 PASS

```
[OK] step 1 — install_agriculture idempotent
[OK] step 2 — discover_seed adds new, idempotent on known
[OK] step 2 — agent's culture library has poaceae_c3 + legumes
[OK] step 3 — plant_seed succeeds + injects biomass     50.0 → 90.0
[OK] step 3 — plant_events counter incremented
[OK] step 4 — harvest succeeds, draws biomass, fills inv_food
              kcal=148501  inv 0.00→10.00  biomass 740→695
[OK] step 5 — forage discovery adds clades              n_new=10
[OK] step 6 — tick_agriculture grows cultivated biomass 45.000 → 45.016
[OK] step 7 — ADR-0005 lists agriculture OK
[OK] step 8 — persistence round-trip preserves stats
```

---

## Boucle de rétroaction complète

```
plant_evolution.ChunkVegetation
        ↓
photosynthesis pathway override
        ↓
chunk.food_kcal
        ↓
agent.inv_food  ←─── HARVEST (Phase 4 NEW)
        ↓
PLANT inject  ────→ ChunkVegetation += SEED_BIOMASS_KG
        ↓
tick_agriculture boost ×1.5
        ↓
plant_evolution growth accelerated
        ↓
(cycle)
```

Les agents peuvent maintenant **modifier activement l'écosystème
végétal** au lieu de juste le brouter passivement. La culture qui
domestique le riz (`poaceae_c3` au Néolithique) voit son seed library
grandir, ses champs se multiplier, son `total_kcal_harvested`
exploser. C'est le mécanisme central de la révolution néolithique.

---

## ADR-0005 → 12 modules requis taggés

| Module | Pipeline | Capability |
|---|---|---|
| earth_loader | L1 | paper-L1 |
| sim_lift | L2 | paper-L2 |
| realism | L4 | paper-L2 |
| physiology | L4 | paper-L2 |
| photosynthesis | L4 | paper-L2 |
| material_aging | L4 | paper-L1 |
| marine | L4 | paper-L2 |
| global_world | L4 | paper-L2 |
| plant_evolution | L4 | paper-L2 |
| meteorology | L4 | paper-L2 |
| animal_evolution | L4 | paper-L2 |
| **agriculture** (nouveau) | L4 | paper-L2 |

`p18_capabilities_lint` passe **12/12** OK.

---

## Non-régression

- `p20_physiology_smoke` → 7/7 PASS (cholera fix toujours actif)
- `p29_animal_evolution_smoke` → 9/9 PASS (pyramide écologique intacte)
- `p23_persistence_roundtrip` → 7/7 PASS
- `p18_capabilities_lint` → 12/12 OK

---

## Fichiers touchés

```
runtime/engine/agent.py                          (+3 LOC : ActionKind PLANT/HARVEST)
runtime/engine/agriculture.py                    (nouveau, ~330 LOC)
runtime/engine/dashboard.py                      (+12 LOC : endpoint + import)
runtime/engine/world_library.py                  (+1 LOC : _PERSISTENT_MODULES)
runtime/engine/world_model_capabilities.py       (+1 LOC : _REQUIRED_MODULES)
runtime/scripts/p30_agriculture_smoke.py         (nouveau, ~215 LOC, 10/10 PASS)
docs/sprints/2026-05-14_PHASE19-AGRICULTURE.md   (ce fichier)
NEXT-SPRINT.md                                   (Phase 4 agriculture archivé)
```

---

## Suite Phase 4

### Écriture (Wave 9b)
`engine/writing.py` — supports persistants (tablettes, papyrus,
ouvrages). Permettre la **transmission inter-générationnelle de
recettes** (Wave 1 MaterialRegistry) et **lois** (Phase 4 polity).
Production matérielle gated par `material_synthesis` (argile pour
tablettes, papyrus de cuc).

### État / Polity (Wave 9c)
`engine/polity.py` — quand >N agents partagent un territoire +
règles communes, émergence d'un proto-gouvernement avec taxation
+ distribution + autorité. Boucle de rétroaction avec
`material_aging` (impôts → entretien des matériaux).

### Cognition wiring (Wave 9d)
Router `PLANT` et `HARVEST` dans `cognition.decide` : agent voit un
champ cultivé en perception, hunger > seuil → décide HARVEST. Ou
inventory bas + chunks fertiles + dans seed library → décide PLANT.
