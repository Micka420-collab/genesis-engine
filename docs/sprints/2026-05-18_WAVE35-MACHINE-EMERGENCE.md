# Wave 35 — `machine_emergence` : découverte émergente de machines composites

**Date** : 2026-05-18
**Module** : `engine.machine_emergence` (~340 LOC)
**Smoke** : `runtime/scripts/p65_machine_emergence_smoke.py` — **9/9 PASS**
**Wave précédente** : 34 (anatomy, livrée séparément)
**Wave suivante** : 36 (wiring `cognition.decide` ↔ `try_assemble_machine`)

---

## Pourquoi — vision Black Mirror

Le projet Genesis Engine repose sur une règle invariante :
**rien n'est scripté, tout émerge**. Les agents préhistoriques ne se
voient pas remettre une table de recettes "wheel = 2 wood + 1 axle". Ils
découvrent les machines comme l'humanité les a réellement découvertes :
par tâtonnement, en combinant les outils déjà inventés et les matériaux
qu'ils ont sous la main.

Deux cultures séparées par une montagne qui placent les mêmes pierres et
les mêmes morceaux de bois pour la même fonction tombent
nécessairement sur la **même machine** — mais lui donnent des **noms
différents**. C'est exactement le motif Lascaux/Altamira déjà appliqué à
la découverte de bâtiments (Wave 10e). Wave 35 le porte au niveau des
outils composites.

---

## Architecture — fingerprinting déterministe

### Composants

Un `MachineComponent` est soit :

* `kind == 'material'` : une masse de matériau brut (ex. `wood`, `stone`),
* `kind == 'artifact'` : un artefact existant dans `InventionRegistry`.

Aucun champ ne décrit "à quoi ça sert" — l'agent peut empiler n'importe
quoi.

### Fingerprint

Le tuple-signature est strictement déterministe :

```
fingerprint = (
    n_components,         # nombre de pièces
    dominant_material,    # str — matériau de masse maximale (tie-break α)
    mass_bucket,          # 0..5 sur MASS_BUCKETS_KG = (0.5, 5, 20, 100, 500)
    sorted(function_kinds),  # union des FunctionKind portées par les artefacts
)
```

Deux assemblages dont les quatre champs sont identiques sont *la même
machine*. Toute différence (un composant en plus, une fonction
supplémentaire, un palier de masse franchi) produit un fingerprint
distinct et donc une **machine distincte**.

### Auto-naming CVCV

Le nom est tiré par `prf_rng(seed, ["machine_emergence", "name",
repr(fp)], [culture_id])`. La culture entre dans l'entropie : deux
cultures qui partagent le fingerprint reçoivent des noms différents.
Pattern syllabique CVCV (consonne-voyelle-consonne-voyelle, 4 lettres),
sur les consonnes `kmnprstvgdlbz` et les voyelles `aeiou`.

### Static stability — proxy

Footprint approché : `sqrt(n_components) * 0.5 m`, donc surface
`max(0.25, ...)` m². Loading : `total_mass_kg / footprint_m²` comparé à
`STATIC_STRESS_CEILING_KG_PER_M2 = 1000.0`. Sous le seuil →
`is_static_stable=True`. Le flag ne bloque pas l'enregistrement (une
machine bancale a quand même un nom) ; il sera consommé par la
cognition à partir de Wave 36 pour décider si la machine est utilisable.

---

## API publique

```python
@dataclass MachineComponent       # kind, id_or_name, mass_kg
@dataclass Machine                 # machine_id, fingerprint, components,
                                   # function_kinds, dominant_material,
                                   # total_mass_kg, culture_id, inventor_row,
                                   # tick_created, is_static_stable
@dataclass MachineRegistry         # machines, machines_by_culture,
                                   # fingerprint_to_id, inventor_credit,
                                   # n_total_attempted, n_total_invented
@dataclass MachineEmergenceState   # registry

install_machine_emergence(sim) -> MachineEmergenceState        # idempotent
uninstall_machine_emergence(sim) -> bool

try_assemble_machine(sim, row, components,
                     intended_function_kinds=None)
    -> (success, reason, machine_or_None)
    # reason ∈ {'invented', 'recognized', 'too_few_components:n<2'}

compute_machine_fingerprint(components, function_kinds,
                             invention=None) -> Tuple
auto_name_machine(world_seed, culture_id, fingerprint) -> str
machine_emergence_state(sim) -> Dict[str, object]
```

Pas de wrap de `sim.step` : la découverte est *event-driven*, déclenchée
par la cognition (Wave 36+). L'installateur attache seulement
`sim._machine_state`.

---

## Smoke `p65_machine_emergence_smoke.py` — 9/9 PASS

| # | Check | Résultat |
|---|-------|----------|
| 1 | API publique exposée + module charge sans warning | OK |
| 2 | `install_machine_emergence` idempotent | OK |
| 3 | 1 composant → fail (`too_few_components:1<2`) | OK |
| 4 | 2 cultures, mêmes composants → même fp, noms différents (`malo` / `kura`) | OK |
| 5 | Reproduction du même fp dans la même culture → `recognized`, pas de nouvelle invention | OK |
| 6 | 5 specs distinctes → 5 machines, 5 noms uniques | OK |
| 7 | Composants `Artifact` (CUT + STRIKE) → `function_kinds = {0, 1}` | OK |
| 8 | Assemblage lourd/compact → `is_static_stable=False` ; léger → `True` | OK |
| 9 | Deux sims même seed → même séquence de noms inventés | OK |

Reproduction :

```bash
cd runtime
python scripts/p65_machine_emergence_smoke.py
# RESULT: PASS — Wave 35 machine_emergence smoke complete (9/9).
```

Non-régression vérifiée : `p38_building_discovery_smoke.py` reste
**8/8 PASS** ; `p43_social_resonance_smoke.py` reste **9/9 PASS**.

---

## Limites notables

1. **Statics simplifiée** : le test masse/footprint est un proxy, pas
   une analyse compressive_stress comme `engine.statics`. Wave 36+
   branchera un voxel-layout machine sur la pipeline `Structure /
   is_structurally_stable` pour des assemblages assez gros pour le
   justifier.
2. **Pas de persistance JSON** : `MachineRegistry` n'est pas encore
   sérialisé par `world_library.save_world`. Wave 36 ajoutera
   `save_machine_registry` / `load_machine_registry` sur le même
   patron que `material_synthesis`.
3. **Pas de wiring cognition** : les agents ne *décident* pas encore
   d'assembler ; `try_assemble_machine` doit être appelé manuellement
   (ou par un test/scénario). Le wiring `ActionKind.BUILD_MACHINE` est
   prévu Wave 36.
4. **Pas de transmission inter-cultures** : à la différence des
   matériaux et des bâtiments, les machines ne se transmettent pas
   encore d'une culture à l'autre. Wave 37 ajoutera
   `transmit_machine(reg, from_c, to_c, machine_id, rng)`.
5. **Pas d'effectiveness** : `Machine` ne porte pas encore d'indicateur
   de qualité fonctionnelle (comme `Artifact.effectiveness`). Sera
   dérivé de la moyenne pondérée des `Artifact.effectiveness` des
   composants en Wave 36.

---

## Branchements futurs (Wave 36+)

* **Wave 36** : `cognition.decide` peut sélectionner
  `ActionKind.BUILD_MACHINE` quand l'agent possède ≥ 2 artefacts ou
  matériaux compatibles avec une `FunctionKind` qu'il cherche à exercer
  (chasse → CUT + PROJECT ⇒ tentative d'arc composite).
* **Wave 37** : transmission inter-cultures via voisinage / commerce
  (`polity.trade`) avec probabilité de transmission selon la complexité
  (`n_components`).
* **Wave 38** : `world_render_isometric` affiche les machines comme un
  cluster de glyphes (un par composant), avec une étiquette portant le
  nom CVCV.
* **Wave 40** : effets gameplay — une machine `function_kinds == {CUT,
  STRIKE}` accélère le défrichage et la construction quand un agent la
  porte ; une machine `{GRIND}` (futur watermill) débloque la
  transformation grain → farine.

---

## Fichiers livrés

* `runtime/engine/machine_emergence.py` — module Wave 35 (~340 LOC).
* `runtime/scripts/p65_machine_emergence_smoke.py` — smoke 9/9 (~250 LOC).
* `docs/sprints/2026-05-18_WAVE35-MACHINE-EMERGENCE.md` — ce document.

Aucun module pré-existant n'a été modifié (anti-conflit respecté).
