# SPRINT 2026-05-14 — Phase 4 writing (Wave 9b)

**Priorité attaquée**: Phase 4 — Émergence civilisationnelle — 2e des
3 livrables : **écriture** (transmission inter-générationnelle de
recettes, semences et lois).

**Statut**: ✅ livré
**Cible**: les agents inscrivent leur savoir sur des supports physiques
qui vieillissent (Wave 4), un lecteur de culture différente gagne la
knowledge inscrite, la durée de vie d'une inscription dépend du support.

---

## Roadmap Phase 4 — où on en est

| Sprint | État |
|---|---|
| Wave 9 — Agriculture | ✅ session 22 |
| **Wave 9b — Writing** | ✅ **session 23 (ce sprint)** |
| Wave 9c — Polity (État) | ⏳ |
| Wave 9d — Cognition wiring | ⏳ |

---

## `engine/writing.py` (~370 LOC)

### Types de contenu

```python
class InscriptionType(IntEnum):
    RECIPE = 0      # référence à un material_synthesis.SynthesizedMaterial
    SEED = 1        # nom d'un plant_catalog.PlantClade
    LAW = 2         # règle textuelle (futur polity)
    LEXICON = 3     # entrée phonémique (futur language)
```

### Structure

```python
@dataclass class Inscription:
    inscription_id: int
    instance_id: int             # → material_aging.MaterialInstance
    content_type: int
    content_key: str             # nom de matériel, clade, etc.
    author_culture: int
    created_tick: int
    times_read: int
    illegible: bool

@dataclass class WritingState:
    inscriptions: Dict[int → Inscription]
    culture_recipes / culture_seeds / culture_laws / culture_lexicon
    read_events: List[ReadEvent]  # audit log
```

### Couplage Wave 4 (material_aging)

Chaque inscription est **liée à un MaterialInstance**. Sa lisibilité
est recalculée à chaque lecture via `_check_legibility`:

```python
inst = aging._by_id[instance_id]
if inst.integrity < 0.10:
    inscription.illegible = True
```

L'inscription **survit exactement aussi longtemps que le support
physique**. La règle métier réelle :

| Support | ANNUAL_LOSS | Lifespan utile |
|---|---|---|
| `stone_granite` | 0.005 %/yr | ~immortel (4000+ ans) |
| `ceramic` cuite | 0.08 %/yr | ~6000 ans (cuneiforme Sumer ✓) |
| `wood` carving | 18 %/yr | ~5-10 ans (humide) |
| `leather` parchemin | 20 %/yr | ~5 ans |

### API publique

```python
install_writing(sim) -> WritingState                  # idempotent
inscribe(sim, state, instance_id, content_type, content_key, author_culture)
  -> (inscription_id, "")
read_inscription(sim, state, row, inscription_id)
  -> (success, outcome)   # outcomes: new_knowledge | already_known | illegible
```

### Propagation cross-module

Quand un agent lit une **SEED inscription**, l'API `discover_seed`
de `agriculture` est appelée → la culture du lecteur gagne la
seed dans `culture_seed_library`. **Round-trip écriture → lecture →
agriculture activée**.

Quand un agent lit une **RECIPE inscription**, le matériau est
ajouté à `material_synthesis.MaterialRegistry._culture_known`
pour la culture du lecteur.

---

## Validation `p31_writing_smoke` — **12/12 PASS**

```
[OK] step 1 — install_writing idempotent
[OK] step 2 — inscribe creates 3 inscriptions               ids=1,2,3
[OK] step 2 — author culture 1 already knows all 3
[OK] step 3 — culture 2 reader gains recipe                 outcome=new_knowledge
[OK] step 3 — re-read same inscription → already_known
[OK] step 4 — wood integrity after 10 yr wet ≈ 0            integrity=0.0000
[OK] step 4 — wood-inscribed law now illegible              ← support détruit
[OK] step 5 — granite integrity still > 0.99 after 10 yr    integrity=0.999900
[OK] step 5 — granite seed inscription still readable       ← support immortel
[OK] step 6 — seed propagates to agriculture lib            agri.culture_seed_library updated
[OK] step 7 — ADR-0005 lists writing OK
[OK] step 8 — persistence round-trip preserves state
```

---

## Boucle de rétroaction complète

```
agent invente bronze (Wave 1/2)
  ↓
MaterialRegistry register(material, culture_id)
  ↓
agent inscribes recipe on clay tablet (Wave 9b NEW)
  ↓
clay aging in material_aging — 0.08%/yr decay
  ↓
GENERATIONS PASS (10K-100K ticks)
  ↓
agent original meurt → recipe perdue sans écriture
  ↓
nouveau agent lit la tablette (Wave 9b NEW)
  ↓
recipe ajoutée à MaterialRegistry pour culture du lecteur
  ↓
peut refaire le bronze
```

C'est **exactement la transition néolithique → âge du bronze**
historique : la transmission orale du savoir-faire est limitée par
la longévité humaine ; l'écriture sur argile cuite (Mésopotamie 3500
BCE) permet l'accumulation sur 6000 ans.

---

## ADR-0005 → 13 modules requis taggés

| Module | Capability |
|---|---|
| earth_loader | paper-L1 |
| sim_lift | paper-L2 |
| realism | paper-L2 |
| physiology | paper-L2 |
| photosynthesis | paper-L2 |
| material_aging | paper-L1 |
| marine | paper-L2 |
| global_world | paper-L2 |
| plant_evolution | paper-L2 |
| meteorology | paper-L2 |
| animal_evolution | paper-L2 |
| agriculture | paper-L2 |
| **writing** (nouveau) | paper-L2 |

`p18_capabilities_lint` passe **13/13** OK.

---

## Non-régression

- `p22_material_aging_smoke` → 6/6 PASS (writing dépend de aging, OK)
- `p23_persistence_roundtrip` → 7/7 PASS
- `p30_agriculture_smoke` → 10/10 PASS

---

## Fichiers touchés

```
runtime/engine/writing.py                        (nouveau, ~370 LOC)
runtime/engine/dashboard.py                      (+10 LOC : endpoint)
runtime/engine/world_library.py                  (+1 LOC : _PERSISTENT_MODULES)
runtime/engine/world_model_capabilities.py       (+1 LOC : _REQUIRED_MODULES)
runtime/scripts/p31_writing_smoke.py             (nouveau, ~220 LOC, 12/12 PASS)
docs/sprints/2026-05-14_PHASE20-WRITING.md       (ce fichier)
NEXT-SPRINT.md                                   (Phase 4 writing archivé)
```

---

## Phase 4 — Reste à faire

### Wave 9c — Polity (État)
`engine/polity.py` — Émergence d'un proto-gouvernement quand :
- N agents partagent un territoire (chunks proches)
- N agents lisent les MÊMES LAW inscriptions
- Une fonction « autorité » émerge (chef = agent avec le plus d'enfants
  vivants ? Ou avec le plus d'inscriptions auteur ?)

Mécanismes : taxation (collecte 10% du `inv_food` produit), distribution
(redistribute aux agents en hunger > 0.8), application des lois (sanction
des relief près d'eau, gestion des champs, etc.).

### Wave 9d — Cognition wiring
Router `PLANT`, `HARVEST`, `READ`, `INSCRIBE` dans
`cognition.apply_decision`. Les agents décideront eux-mêmes en
fonction de leur état.
