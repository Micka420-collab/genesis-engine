# Genesis Engine — Phase 5c + 5d (en cours)
**Date :** 13 mai 2026
**Statut :** fondations livrées, intégration au tick loop en attente.

Cette note documente ce qui est livré aujourd'hui et ce qui reste pour
exposer ces capacités à la simulation tournante.

---

## Ce qui est livré (7 modules, ~70 KB de code)

### Pilier physique — `engine/materials.py`
14 matériaux avec propriétés réelles : `WOOD`, `STONE`, `FLINT`, `CLAY`, `FIBER`, `LEATHER`, `BONE`, `COPPER`, `TIN`, `BRONZE`, `IRON`, `CERAMIC`, `CHARCOAL`, `GRAIN`. Chaque matériau porte densité (kg/m³), dureté Mohs, point de fusion en Kelvin, combustibilité, valeur calorifique MJ/kg, ouvrabilité et qualité-de-coupe. Sources : CRC Handbook, Tylecote *History of Metallurgy*. Inclut les seuils de fusion historiques (Cu @ 1358 K, Sn @ 505 K, Fe @ 1811 K) et un tableau `BIOME_YIELDS` qui dit ce qu'un agent peut récolter dans chaque biome.

### Pilier construction — `engine/construction.py`
10 recettes anchorées dans l'archéologie : `HEARTH`, `LEAN_TO`, `HUT`, `WELL`, `GRANARY`, `WORKSHOP`, `KILN`, `FURNACE`, `BLOOMERY`, `FARM_PLOT`. Chaque recette spécifie matériaux requis (en kg), heures de travail, nombre min de bâtisseurs, technologies prérequises, capacité d'occupants, rayon d'effet, soulagement thermique, facteur de décomposition des aliments, rendement en eau, bonus de cuisson, autorisation d'artisanat, température max atteinte. Les classes `Structure`, `ConstructionProject` et `ConstructionRegistry` gèrent les chantiers en cours et les bâtiments terminés. Une hutte coûte ~24 heures de travail × 2 bâtisseurs, ce qui correspond aux données ethnographiques.

### Pilier technologique — `engine/tech_tree.py`
14 technologies organisées en DAG cohérent avec l'histoire humaine : `FIRE` (paléolithique) → `STONE_TOOLS` → `SHELTER` → `COOKING` → `WEAVING` → `AGRICULTURE` (néolithique) → `POTTERY` → `CERAMICS` → `METALLURGY` (âge du bronze) → `BRONZE` → `IRON_SMELT` (âge du fer) + `WHEEL`, `WRITING`, `NAVIGATION`. Chaque tech a difficulté, ère historique et prérequis. La probabilité de découverte par tick = curiosité × intelligence × (1 - difficulté) × accélération × bonus-d'observation (5× si un voisin connaît déjà la tech). La transmission entre agents observateurs est probabiliste.

### Pilier écologique — `engine/ecology.py`
**Atmosphère réelle de Terre.** Démarrage : 280 ppm CO₂ (référence holocène pré-industrielle), 0 K d'anomalie thermique. Combustion : `combustion_co2_kg(material, kg)` utilise la fraction de carbone réelle (bois 50 %, charbon 85 %, ratio CO₂/C 44/12). Puits : forêts -0,0008 kg/s/km², océans -0,0005 kg/s/km². Sensibilité climatique 3 K par doublement de CO₂ (fourchette IPCC AR6). Quand la civilisation émet plus que les puits absorbent, l'anomalie monte, et `apply_climate_feedback()` réduit `food_capacity` proportionnellement et fait monter le niveau des mers. **Si la civilisation reste sub-industrielle, l'aiguille bouge à peine** — c'est le test que tu voulais : peuvent-ils éviter le réchauffement climatique ?

### Pilier invention libre — `engine/invention.py`
**Pas seulement des recettes pré-écrites.** Le système définit 10 catégories fonctionnelles (`CUT`, `STRIKE`, `PIERCE`, `CONTAIN`, `INSULATE`, `IGNITE`, `BIND`, `GRIND`, `PROJECT`, `SHELTER`) avec leurs exigences physiques sur les matériaux. Un agent qui détient des matériaux peut tenter `try_invent()` ; si la combinaison satisfait la physique (un silex peut couper, du bois peut allumer, de la fibre peut lier, l'argile ne peut pas couper) et n'a pas déjà été inventée par quelqu'un d'autre, il crée un nouvel `Artifact` qui rejoint le registre culturel partagé. Probabilité = curiosité × intelligence × (1 - fatigue × 0,7) × accélération. Transmission par observation via `transmit()`. Les artefacts inventés sont nommés automatiquement (par exemple `flint_cut`, `clay_contain`, `wood_fiber_bind`).

### Pilier libre arbitre — `engine/values.py`
7 dimensions de valeurs morales : `SURVIVAL`, `FAMILY`, `CURIOSITY`, `COMMUNITY`, `LEGACY`, `FREEDOM`, `DOMINANCE`. Le vecteur est normalisé (somme = 1) et biaise les décisions au-delà du réflexe utilitaire via `value_bias_for_action()`. Le mécanisme `free_will_override()` permet à un agent — quand un drive n'est pas critique — d'ignorer son utilité court terme pour agir selon sa valeur dominante. La probabilité d'override = (1 - drive_strength) × valeur_dominante × 0,10 ; on ne triche pas sur la survie quand elle est critique. `evolve_value()` modifie les valeurs au cours de la vie selon les expériences : perdre un proche augmente `family` et `legacy`, être attaqué augmente `survival` et `dominance`, inventer augmente `curiosity` et `legacy`, etc.

### Pilier extension agent — `engine/agent_5cd_fields.py`
Module non-invasif qui étend l'`AgentRegistry` existant sans réécrire `agent.py` (risque de troncature sur le mount). Ajoute : `known_techs (N, 14) bool`, `current_project_id (N,) int`, `labor_invested (N,) float`, inventaire par matériau (12 nouveaux), `emotions (N, 6)`, `values (N, 7)`, `chronic_fatigue (N,)`, `injury_parts (N, 6)`, `skills (N, 8)`, et flags d'éveil cognitif. Les fondateurs naissent avec `FIRE` connu (condition initiale de la Terre), 60 % avec `STONE_TOOLS`, 20 % avec `SHELTER` — état du paléolithique tardif. La fonction `inherit_5cd_fields()` est appelée à chaque naissance pour transmettre techs/valeurs/skills aux enfants avec mutation.

---

## Test d'auto-import (vérifié à 5/13 08:02 UTC)

```
14 matériaux chargés
10 recettes (de hearth=6 kg/2 h à bloomery=130 kg/80 h)
14 techs du paléolithique au fer
combustion 10 kg bois → 18.3 kg CO2
atmosphère : 280 → 561 ppm pour 280 t locales, +3.01 K anomalie
flint satisfait CUT : True ; clay satisfait CUT : False
fiber satisfait BIND : True ; wood satisfait IGNITE : True
free-will override actif (survival-dominant override déclenché)
```

Tous les modules s'importent sans warning ni erreur.

---

## Ce qu'il reste à intégrer (tâches 20, 21, 22, 26)

Les modules sont écrits ; ils ne sont pas encore branchés au tick loop. Pour passer de « code livré » à « agents qui construisent vraiment » il faut :

### Tâche 20 — `cognition.py`
Ajouter trois branches dans `decide()` :
- `HARVEST_MATERIAL` quand idle et la cellule courante a un yield de matériaux selon le biome
- `BUILD` quand thermal/sleep est haut et qu'on est éligible à démarrer un projet abri/hutte
- `CRAFT` en présence d'un workshop avec les matériaux requis
Et dans `apply_decision()`, brancher ces actions sur le registry de construction.

### Tâche 21 — `sim.py`
Dans le tick loop :
1. `atm.begin_tick()` au début
2. Comptage des cellules forêt/océan pour les puits → `atm.tick()`
3. Chaque `HEARTH`/`FURNACE`/`BLOOMERY` allumé émet CO₂ ce tick selon le bois/charbon consommé
4. Boucle sur `construction.projects` : pour chaque builder présent à proximité, ajouter labor_hours × skill[build]
5. Chaque chunk reçoit `apply_climate_feedback()` une fois par jour-sim
6. Appel `invention.try_invent()` pour chaque agent (probabiliste, peu coûteux)
7. Appel `transmit()` entre voisins
8. À chaque tick, `free_will_override()` peut basculer la décision avant `apply_decision()`

### Tâche 22 — annalist + smoke test + rapport
Ajouter événements `BUILD_STARTED`, `BUILD_COMPLETED`, `INNOVATION` (déjà dans EventKind), `INVENTION` (nouveau), `CO2_THRESHOLD_CROSSED`. Smoke test : 30 agents × 200 ticks dans biome forêt tempérée — au moins 1 abri et 1 foyer construits, ≥ 1 invention, CO₂ < 290 ppm (test : la civilisation reste sub-industrielle).

### Tâche 26 — drives étendus
Fatigue chronique cumulative (tick + 0,00005 × labor_invested), maladies par contact (déjà en partie via `pathogen_load`), émotions mises à jour selon les événements (joie sur birth/share, peur sur fight, tristesse sur death de relation, etc.).

---

## Cadence estimée

L'intégration au tick loop (tâches 20–22, 26) représente ~2-3 sessions de travail dédiées, parce que chaque modification dans `sim.py`/`cognition.py` doit être faite avec précaution sur le mount (risque de troncature qu'on a vu en Phase 4). Je le ferai en plusieurs passes avec smoke tests à chaque étape.

---

## Récapitulatif pour le projet

Avec Phase 5c + 5d livrés, le Genesis Engine aura :

- des **matériaux réels** avec physique réelle
- des **bâtiments réels** qui se construisent avec du temps et des matériaux
- un **arbre technologique réel** qui se découvre et se transmet
- **l'invention libre** : un agent peut combiner matériaux pour découvrir un nouvel artefact que le concepteur n'a pas pré-écrit, à condition que la physique le permette
- **l'atmosphère réelle de Terre** au démarrage (280 ppm CO₂) avec rétroaction climatique réelle si la civilisation pollue trop
- le **libre arbitre via valeurs morales** : deux agents identiques peuvent agir différemment selon ce qu'ils valorisent
- la **fatigue, les blessures localisées et les émotions** (extension prête à brancher)

C'est exactement le test scientifique que tu voulais : peut-on observer une civilisation artificielle émerger, inventer, construire, transmettre — sans provoquer le réchauffement climatique que nous, vrais humains, avons provoqué ?
