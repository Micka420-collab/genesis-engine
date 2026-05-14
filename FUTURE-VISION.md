# Genesis Engine — Future Vision

> **L'objectif ultime** : donner aux agents IA toutes les bases du monde réel — physique, chimie, matériaux, biologie, géographie — puis les laisser explorer **d'autres styles de construction, d'autres styles de société**, pour voir **ce que l'humanité aurait pu faire**. Les IA peuvent inventer de nouveaux matériaux, mais **tout en respectant les lois de la nature**.

---

## 🌌 Pourquoi cette vision

L'histoire humaine est **un seul tirage** parmi un espace immense de possibles civilisationnels. Nous avons :
- Domestiqué le blé et pas le seigle sauvage de façon dominante.
- Inventé l'arc avant l'arbalète parce que la chimie du bois courbé l'a permis tôt.
- Construit en pierre cubique parce que l'équilibre statique le facilite.
- Adopté la propriété individuelle plus que collective dans la plupart des cultures du Néolithique tardif.

**Mais rien de tout cela n'est nécessaire.** Avec les mêmes lois physiques, les mêmes contraintes chimiques, les mêmes ressources géographiques, **d'autres chemins étaient ouverts**. Genesis Engine veut explorer ces chemins parallèles via des civilisations IA autonomes qui re-découvrent le monde sans connaître la nôtre.

> *"Avec les mêmes briques de Lego que nous, qu'auraient-elles pu construire d'autre ?"*

---

## 🧪 Hypothèse scientifique élargie

| H0 (actuelle) | H1 (vision future) |
|---|---|
| La complexité civilisationnelle peut émerger à partir d'agents IA autonomes avec règles minimales. | **Plusieurs trajectoires civilisationnelles distinctes émergent à partir des mêmes lois physiques et de la même base géographique, démontrant la contingence historique.** |

H1 est falsifiable : si **toutes** les runs convergent vers la même structure macro (même tech tree, même hiérarchie sociale), alors l'histoire humaine est **déterministe par les lois physiques**. Si **les runs divergent radicalement**, l'histoire humaine est **contingente** (un produit de hasards historiques accumulés).

---

## 🏗️ Les 4 piliers de la vision

### 1. **Bases du monde réel** — alimentation du moteur

Le moteur doit ingérer **les lois fondamentales** de notre monde :

| Domaine | État actuel | Vision |
|---|---|---|
| Physique mécanique | implicite (gravité, friction non modélisés) | g=9.81, μ static/kinetic, stress-strain |
| Thermodynamique | partielle (atmosphère CO2) | conduction/convection/radiation, capacité calorifique |
| Chimie | 14 matériaux fixes (`materials.py`) | 118 éléments, énergies de liaison, phase diagrams |
| Biologie | génome 256-gènes + 8 stades de vie | métabolisme cellulaire, photosynthèse, prédation trophique |
| Géographie | Copernicus DEM + ESA WorldCover ✅ | + climat CHELSA + hydro HydroSHEDS + géologie SoilGrids |
| Cycle solaire | day/night basique | spectre solaire, photopériodes, vit-D, panneaux PV |

**Approche** : ne pas dupliquer la science. Ingérer des **datasets ouverts** standardisés (PubChem pour la chimie, Materials Project pour les matériaux connus, CHELSA pour le climat) et exposer leurs constantes au moteur comme **environnement de contraintes**.

### 2. **Invention émergente de matériaux** — respectant les lois de la nature

Aujourd'hui : `engine/invention.py` combine 2 matériaux via une fonction → artefact si fonction satisfaite.

Demain : **matériaux entièrement nouveaux** émergent quand des agents combinent des éléments dans des conditions physico-chimiques valides.

```
agent.combine(
    [cuivre: 0.7 mol, étain: 0.3 mol],
    conditions={température: 950°C, atmosphere: réducteur, contenant: charbon}
) 
→ check_physical_validity()
    ├─ énergie d'activation ≥ disponible ?       ✓ (charbon fournit 1100°C)
    ├─ produits stables thermodynamiquement ?    ✓ (Δ G_mix < 0)
    ├─ stœchiométrie respectée ?                  ✓
    └─ conservation masse/énergie ?               ✓
→ nouveau matériau : "alliage_Cu70Sn30"
   - hardness: dérivée empirique de la composition
   - melting_point: interpolé Cu-Sn phase diagram
   - workability: calculée
```

**Si les conditions ne sont pas réunies** (ex. tenter de combiner Cu+Sn à 200°C) → l'invention **échoue** physiquement. Pas de magie.

**Les lois respectées** :
- Conservation masse-énergie
- Premier et second principes thermodynamiques
- Énergies de liaison réalistes (référence PubChem)
- Stabilité thermodynamique du produit (Δ G < 0)
- Cinétique : énergie d'activation atteignable avec les outils dispo

**Résultat possible** : civilisations qui découvrent des alliages que nous n'avons jamais explorés (ex. composites bois-céramique à liaison hydrogène que nous avons négligés). Ou qui re-découvrent les nôtres dans un ordre différent (le bronze peut venir après le fer si l'étain est rare géographiquement).

### 3. **Architecture émergente** — pas de plans pré-écrits

Aujourd'hui : `construction.py` a des `RECIPES` fixes (HEARTH, HUT, MANOR...).

Demain : **structures émergent de l'assemblage par les agents** soumis à :
- **Statique** : poids supportable par les fondations, moment fléchissant, flambement
- **Géométrie** : angles d'empilement, surfaces d'appui
- **Matériaux** : résistance à la compression / traction / cisaillement
- **Fonction** : abri = isolation thermique + barrière vent + accès humain

```
agent.start_construction(intent="shelter_for_4")
→ agent dépose pierres, le moteur calcule la stabilité
→ si stable + fonction satisfaite → structure "valide"
→ agent peut transmettre le plan (mèmes architecturaux)
→ autre culture reproduit + adapte → patrimoine architectural distinct
```

**Hypothèse** : si on lance 20 civilisations indépendantes avec **même climat tempéré** + **mêmes matériaux disponibles** :
- Une culture peut converger sur la **maison à colombages** (notre histoire).
- Une autre sur la **yourte** (notre histoire alternative).
- Une troisième sur quelque chose que **personne n'a jamais bâti** mais qui est physiquement valide — voûte en encorbellement avec bois ligaturé + torchis sans chaux.

### 4. **Structures sociales contre-factuelles**

Aujourd'hui : `engine/values.py` + `groups` émergent par affinité, groupes basés sur la proximité.

Demain : **structures sociales arbitraires** émergent selon :
- Ressource rare locale (sel, métal, eau douce)
- Risque environnemental (zone sismique → coopération forcée)
- Génétique de la cohorte (variance d'agressivité → équilibres distincts)
- Aléas historiques accumulés (premier conflit → mémoire intergénérationnelle)

**Exemples de chemins parallèles à observer** :
- Société **sans propriété individuelle** (tout est partagé via réciprocité)
- Société **matrilinéaire** (héritage par les femmes, polyandrie)
- Société **acéphale stable** (anarchie organisée sans chef, longue durée)
- Société **multi-spécifique** (humanoïdes + autre espèce intelligente émergente)
- Société **post-domestication** où les chevaux/chiens deviennent agents semi-autonomes

Les **valeurs** des agents (déjà 7-dim dans `agent_5cd_fields.py`) ne sont pas universelles : elles dérivent par drift culturel. Une culture peut faire émerger une 8e valeur que nous n'avons pas (ex. "transmission_to_unborn", soin des générations futures), et bâtir son économie dessus.

---

## 🗺️ Roadmap d'implémentation (4 grandes vagues)

### Vague 1 — Knowledge base ingestion (3-6 mois)

- **`engine/physics.py`** — constantes physiques de base (g, ε₀, μ₀, R, k_B...), équations de mouvement, friction, thermodynamique
- **`engine/chemistry.py`** — periodic table (118 éléments), énergies de liaison, phase diagrams binaires/ternaires (référence Materials Project / PubChem)
- **`engine/materials_extended.py`** — étendre les 14 matériaux actuels à 200+ via dataset standardisé
- **`engine/biology.py`** — métabolisme cellulaire simplifié, photosynthèse-O2-CO2, cycle azote
- **`engine/climate_chelsa.py`** — auto-download CHELSA bio1-19 + ERA5 events

### Vague 2 — Material invention avec contraintes (6-9 mois)

- **`engine/material_synthesis.py`** — `combine(elements, conditions)` → check_physical_validity()
- **Validation pipeline** : Δ G, énergie d'activation, conservation, cinétique
- **Materials emergent registry** — chaque culture maintient son propre dictionnaire de matériaux découverts
- **Transmission de recettes** — analogue à `invention_transmitted` mais avec stochéométrie complète

### Vague 3 — Architecture émergente avec statique (6-9 mois)

- **`engine/statics.py`** — moteur de stabilité (poids, supports, moment fléchissant, flambement)
- **`engine/voxel_construction.py`** — passer du `RECIPES` fixe à l'assemblage voxel-par-voxel
- **`engine/architectural_memes.py`** — patterns architecturaux transmis comme mèmes culturels
- **Validation simulation** : si la structure tombe sous gravité → effondrement, deaths possibles

### Vague 4 — Structures sociales arbitraires (9-12 mois)

- **`engine/social_topology.py`** — graphes relationnels sans templates (clan/tribu/cité ne sont pas hardcodés)
- **Émergence de valeurs nouvelles** — agents peuvent inventer des dimensions de valeur au-delà des 7 actuelles
- **Multi-runs comparison** — `runs/run_001/`, `runs/run_002/`... avec analyse statistique des chemins divergents
- **Counterfactual dashboard** — visualiser les divergences entre runs (tech trees, valeurs dominantes, architecture)

---

## 🔬 Critères de succès de la vision

| Métrique | Cible |
|---|---|
| Diversité matériaux inventés entre 10 runs | ≥ 50 matériaux distincts émergents non identiques |
| Diversité architecturale entre 10 runs | ≥ 5 typologies structurelles distinctes |
| Divergence des valeurs culturelles | distance cosine ≥ 0.6 entre runs après 50 générations |
| Tech tree alternatif | ≥ 1 run découvre une tech absent de notre histoire humaine |
| Respect des lois | 100% des matériaux émergents passent les tests Δ G + conservation |
| Reproductibilité | même seed → même trajectoire, bit-perfect |

---

## 🌐 Implications scientifiques

Si Genesis Engine produit, sur 1000 runs indépendants, **des civilisations radicalement différentes** :
- L'histoire humaine est **contingente** — un seul tirage parmi des milliards de possibles.
- Les "lois de l'histoire" (cycles de Spengler, prédictions marxistes, etc.) sont **statistiquement molles** plutôt que strictes.
- Nous pouvons utiliser le moteur comme **laboratoire** pour tester des contre-factuelles précises : "et si le bronze n'avait jamais été découvert ?" "et si la propriété individuelle n'avait jamais émergé ?"

Si au contraire **les runs convergent** :
- Les lois physiques + les besoins biologiques **suffisent** à expliquer l'histoire humaine.
- Les biais cognitifs IA-spécifiques (héritage des LLM, choix d'architecture) doivent être interrogés.
- C'est une réfutation forte de l'hypothèse de contingence radicale.

Les deux résultats sont **scientifiquement précieux**.

---

## 🧭 Pour les contributeurs

Cette vision est ambitieuse mais s'aligne avec l'architecture stratifiée déjà en place. Les couches L1 (Earth-Seed) et L2 (Sim-Lift) sont **les bases du monde réel**. Le Reality Engine ajoute la **vie biologique**. Il reste à construire :

1. La **couche Physics** (gravité réelle, statique, thermo)
2. La **couche Chemistry** (Materials Project ingestion, synthesis pipeline)
3. La **couche Architecture émergente** (voxel + statique)
4. La **couche Sociale ouverte** (topologies arbitraires)

**Si tu veux contribuer sur cette vision long-terme**, regarde [NEXT-SPRINT.md](NEXT-SPRINT.md) pour les chantiers prioritaires, et discute ton approche en ouvrant une [GitHub Discussion](https://github.com/Micka420-collab/genesis-engine/discussions) **avant** de coder. Ces couches engagent des choix d'architecture lourds qui méritent débat public.

---

## 📚 Travaux scientifiques inspirants

- **Counterfactual history** : Niall Ferguson, *Virtual History* (1997) — pensée contrefactuelle rigoureuse
- **Path dependence** : Paul David, *Clio and the Economics of QWERTY* (1985)
- **Cultural evolution** : Boyd & Richerson, *The Origin and Evolution of Cultures* (2005)
- **Materials Project** : Jain et al., *Commentary: The Materials Project* (2013), dataset DFT 150k+ matériaux
- **PubChem** : Kim et al. (2023), 110M+ molécules avec propriétés
- **Synthetic societies** : Joshua Epstein, *Generative Social Science* (2006)
- **Statistical laws of history** : Peter Turchin, *Cliodynamics* — application des modèles dynamiques à l'histoire

---

<div align="center">

*"Si l'on rejouait l'histoire de la Terre 1000 fois avec les mêmes lois physiques et la même planète,  
combien des civilisations ressembleraient à la nôtre ?"*

— **Question Genesis Engine est conçu pour répondre.**

[⬅ Retour au README](README.md)

</div>
