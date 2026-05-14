# Genesis Engine — Wave 1 Knowledge Base

> Living reference for the four foundation modules shipped in FUTURE-VISION
> **Wave 1 — Pillar 1 (Bases du monde réel)**.

---

## Pourquoi cette vague

Comme l'explique [`FUTURE-VISION.md`](FUTURE-VISION.md) (Pilier 1, *Bases du
monde réel*), le moteur a longtemps encodé la gravité, la chimie et la
résistance des matériaux **de manière implicite** — gravity baked-in,
materials reduced to 14 hard-coded strings, no statics. Cela suffit pour
faire vivre une civilisation, mais pas pour répondre à la vraie question
Genesis : *"avec les mêmes lois physiques, qu'auraient pu inventer d'autres
civilisations ?"*.

Wave 1 répare ce gap. Les **constantes, lois et propriétés matérielles
réelles** deviennent des objets de premier ordre — nommés, importables,
testables. Les agents IA (Builder, Inventor, Scientist) peuvent maintenant
**interroger la physique** au lieu de la deviner, et les inventions sont
soumises à des contraintes thermodynamiques explicites.

> *"Avec les mêmes briques de Lego que nous, qu'auraient-elles pu construire
> d'autre ?"* — la question reste la même, mais on a enfin les briques.

---

## 4 modules livrés

| Module                          | Responsabilité                                                              | API publique principale                                                                                          | Smoke script                          |
|---------------------------------|-----------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|---------------------------------------|
| `engine.physics` (B1)           | Constantes CODATA, mécanique, friction, thermodynamique, Arrhenius          | `G_EARTH`, `R_GAS`, `gibbs_free_energy`, `is_thermodynamically_favorable`, `arrhenius_rate`, `MU_STATIC`         | `scripts/p13_physics_smoke.py`        |
| `engine.chemistry` (B2)         | Table périodique (50 éléments), énergies de liaison, helpers d'alliages     | `PERIODIC_TABLE`, `Element`, `BOND_ENERGY`, `bond_energy`, `density_alloy`, `melting_point_estimate`, `molar_mass` | (intégré via P17)                     |
| `engine.material_synthesis` (B3)| Pipeline `combine(elements, conditions)` + `check_physical_validity()`      | `SynthesisConditions`, `SynthesizedMaterial`, `synthesize(...)`, `check_physical_validity(...)`                  | (intégré via P17)                     |
| `engine.statics` (B4)           | Stabilité structurelle (poids, supports, moment fléchissant, flambement)    | `Block`, `Structure`, `STRENGTH_TABLE`, `Structure.is_structurally_stable()`                                     | (intégré via P17)                     |

Le test d'intégration end-to-end qui consomme les quatre ensemble est
[`runtime/scripts/p17_wave1_integration.py`](runtime/scripts/p17_wave1_integration.py).

---

## Comment utiliser ensemble — *Bronze Age scenario*

Un script complet et copy-pasteable. Il enchaîne les quatre couches pour
inventer du bronze et bâtir un mur :

```python
from engine import physics, chemistry, material_synthesis, statics
from engine.material_synthesis import SynthesisConditions
from engine.statics import Block, Structure

# --- Step 1 — Thermodynamique : réaction spontanée à 1200 K ? ---------------
dG = physics.gibbs_free_energy(dH_J=-50_000.0, T_K=1200.0, dS_J_per_K=10.0)
assert physics.is_thermodynamically_favorable(dG), "reaction non spontanee"

# --- Step 2 — Chimie : caracteriser l'alliage Cu/Sn -------------------------
cu = chemistry.PERIODIC_TABLE["Cu"]
sn = chemistry.PERIODIC_TABLE["Sn"]
rho = chemistry.density_alloy({"Cu": 0.7, "Sn": 0.3})  # g/cm^3
print(f"Cu (Z={cu.atomic_number}) + Sn (Z={sn.atomic_number}) -> rho = {rho:.2f} g/cm^3")

# --- Step 3 — Synthèse : produire un materiau valide ------------------------
conditions = SynthesisConditions(temperature_K=1200.0, atmosphere="reducing")
bronze = material_synthesis.synthesize(
    composition={"Cu": 0.7, "Sn": 0.3},
    conditions=conditions,
    tools_available=("forge",),
)
assert bronze.valid, "synthese invalide — verifier dG, Ea, stoechiometrie"

# --- Step 4 — Statique : ériger un mur de bronze 5x2 ------------------------
wall = Structure(name="bronze_wall_5x2")
for row in range(2):
    for col in range(5):
        wall.add_block(Block(material="bronze", position=(float(col), float(row))))

assert wall.is_structurally_stable(), "le mur s'effondre — revoir l'empilement"
print("Bronze invented + wall standing -> Bronze Age unlocked.")
```

À tout moment, un agent peut interroger les constantes en cours
d'inventaire (`physics.MU_STATIC["stone_stone"]`, `chemistry.bond_energy("Cu", "Sn")`)
ou injecter une nouvelle composition non-historique pour voir si la nature
l'autorise.

---

## Limites actuelles

Wave 1 livre **les bases** mais reste volontairement frugale. À noter avant
de bâtir dessus :

- **Phase diagrams binaires uniquement** dans `chemistry` — les eutectiques
  ternaires et au-delà ne sont pas modélisés (Vague 2).
- **Pas de mécanique quantique** : `H_PLANCK` est exposé en constante, mais
  aucune équation de Schrödinger, aucune structure de bande.
- **Cinétique simplifiée** : `arrhenius_rate` utilise une forme Arrhenius
  classique. Pas de mécanisme multi-étape, pas d'effet catalytique, pas
  d'inhibition.
- **Statique élémentaire** : `statics.Structure` raisonne en blocs rigides
  empilés (support area, moment basique). Pas d'analyse aux éléments finis,
  pas de fissuration progressive.
- **Synthèse limitée aux conditions "macro"** : `SynthesisConditions`
  capture température / atmosphère / outils, mais pas la pression locale
  ni la durée d'exposition (relaxation cinétique).
- **Pas de cycle azote ni biochimie** — biologie est Pilier 1.4, hors-Wave-1.
- **Pas d'auto-download datasets** (PubChem / Materials Project) — toutes les
  valeurs sont hardcodées depuis références publiques. La Vague 1.5 pourra
  ajouter un loader optionnel.

Ces limites sont **volontaires** : on préfère une base correcte et lisible à
une simulation complète et fragile.

---

## Prochaine vague

**Vague 2 — Synthesis avancée + invention émergente** (cf.
[`FUTURE-VISION.md`](FUTURE-VISION.md) §"Vague 2") :

- Alliages **ternaires** et **dopage** (Cu/Sn/Pb, Fe/C/Si...).
- **Materials emergent registry** par culture — chaque civilisation maintient
  son propre dictionnaire de matériaux découverts.
- **Transmission de recettes** stœchiométriques (analogue à
  `invention_transmitted` mais avec composition complète).
- Pipeline de **validation enrichi** : énergie d'activation atteignable avec
  les outils disponibles, cinétique réelle, sous-produits.
- Connexion optionnelle au **Materials Project** (REST API) pour
  cross-check des matériaux émergents face à la littérature.

Ensuite Vague 3 reprendra `engine.statics` pour le brancher dans le pipeline
de construction émergente (voxel-par-voxel + effondrement physique).

---

*Document maintenu manuellement. Pour ré-générer la table modules → smoke
scripts après un sprint Wave 1.x, regarder `INDEX.md` au root.*
