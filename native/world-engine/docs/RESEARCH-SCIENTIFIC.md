# Recherche — simulateurs scientifiques de référence

> Cible : produire un **monde virtuel régi par les mêmes lois physiques que
> le nôtre**, exploitable pour des expériences scientifiques reproductibles.
> Ce document survole les moteurs "vrais" (pas jeux vidéo) que la communauté
> scientifique utilise déjà, et en tire les briques techniques à intégrer.

---

## 1. Modélisation climatique

### CESM (Community Earth System Model — NCAR)
- Référence mondiale du climat, Fortran 90 + OpenMP/MPI.
- Couple : atmosphère (CAM), océan (POP/MOM6), banquise (CICE), terre (CLM),
  hydrologie (MOSART), chimie atmosphérique (CAM-chem).
- **À retenir** : architecture **plusieurs noyaux couplés** par un *flux
  coupler* — chaque sous-modèle a son pas de temps et échange des champs
  flux à intervalles fixes. C'est l'idiome scientifique.

### ICON (DWD/MPI-M)
- Modèle non-hydrostatique sur grille triangulaire icosaédrique.
- **À retenir** : grille **icosaédrique** > lat/lon : pas de singularité aux pôles.

### ROMS / NEMO / MOM6
- Océans 3D, surfaces libres, advection-diffusion explicite.
- **À retenir** : les **conditions limites ouvertes** sont l'enfer ; tout
  domaine borné DOIT documenter ce qui entre/sort.

### NetCDF + CF Conventions
- Format de fait pour les données scientifiques multidim.
- **À retenir** : on exporte en **NetCDF-4** + suit les **CF conventions**
  (noms standard pour température, vent, etc.) → directement importable
  dans Paraview, xarray, ncview.

## 2. Mécanique des fluides

### OpenFOAM
- Suite C++ open-source, Navier-Stokes incompressible/compressible,
  k-ε turbulence, multi-phase.
- **À retenir** : décomposition de domaine + solveurs PISO/SIMPLE.

### SU2
- CFD Stanford, AMR (Adaptive Mesh Refinement) sérieux.
- **À retenir** : **AMR** raffine la grille là où ça change vite (chocs,
  surfaces libres). Indispensable pour scale 1 km → 1 cm.

### LBM (Lattice Boltzmann)
- Alternative à NS, parallélisable trivialement sur GPU.
- **À retenir** : pour rivières / fumée temps réel, LBM bat NS implicite.

## 3. Tectonique & géologie

### ASPECT (Advanced Solver for Problems in Earth's ConvecTion)
- Convection mantellique 3D, Stokes + transport thermique. C++ + deal.II.
- **À retenir** : **rhéologie viscoélastique-plastique** (Maxwell, Burgers,
  Drucker-Prager). C'est ça qui fait des plaques qui se cassent vraiment.

### Underworld 2
- Python + StGermain, lithosphère longue échelle.
- **À retenir** : couplage **mécanique + thermique** avec marker chain.

### PlaNet / Lithgis
- Simulation tectonique simplifiée pour génération de mondes.

## 4. Hydrologie

### MIKE SHE / SWAT / ParFlow
- Modèles hydrologiques distribués, équations de Saint-Venant 1D pour
  rivières, Darcy 3D pour nappes.
- **À retenir** : **Saint-Venant** est le standard pour rivières peu
  profondes; **Darcy** pour souterrain.

## 5. Écosystèmes

### NetLogo / SLiM / Ecosim
- Modèles individus-centrés (IBM/ABM), reproduction, prédation, sélection.
- **À retenir** : équations de **Lotka-Volterra spatialement explicites**;
  pour la génétique de populations, **modèles Wright-Fisher** ou
  **coalescent**.

### Madingley Model
- Modèle global de biomasse fonctionnelle (Microsoft Research, 2014).
- **À retenir** : **catégories fonctionnelles** plutôt que espèces
  individuelles à grande échelle.

## 6. Chimie & matériaux

### LAMMPS / GROMACS
- Dynamique moléculaire — pas pertinent à notre échelle pour l'instant.

### CALPHAD / Thermo-Calc
- Bases de données thermodynamiques pour alliages — utile pour
  métallurgie réaliste (étendre `engine/metallurgy.py` du runtime
  Python existant).

## 7. Cosmologie / astronomie

### GADGET-4 / Arepo / Ramses
- N-corps + hydrodynamique pour formation galactique.
- **À retenir** : si on veut un système solaire / une orbite réaliste,
  les intégrateurs **symplectiques** (Wisdom-Holman, leapfrog) sont
  obligatoires pour la stabilité long-terme.

## 8. Time-stepping multi-échelle

### IMEX (Implicit-Explicit) / Strang splitting
- Les sciences couplent souvent **rapide** (sound waves) et **lent**
  (convection). On résout l'un implicitement, l'autre explicitement.
- **À retenir** : un seul `dt` global n'est jamais bon. Genesis doit
  avoir un **scheduler multi-rate**.

### Sub-cycling
- Météo : `dt=300s`. Biologie : `dt=1 jour`. Tectonique : `dt=1000 ans`.
- Le coupler échange aux *plus grands communs multiples*.

## 9. Validation et reproductibilité

### Cf-checker, ESMValTool
- Outils de validation automatique des outputs climatiques contre
  observations.
- **À retenir** : **dual-output** : produire les mêmes diagnostics que
  les modèles réels (Köppen-Geiger, NDVI, runoff, etc.) pour pouvoir
  les comparer.

### FAIR Principles (Findable, Accessible, Interoperable, Reusable)
- Standard pour les données scientifiques.
- **À retenir** : chaque scénario doit produire un **manifeste FAIR** :
  métadonnées + DOI possible + licence + checksum.

---

## Synthèse → ce qu'on intègre dans Genesis Studio

| Brique scientifique          | Adoption Genesis                          |
|-------------------------------|-------------------------------------------|
| Multi-noyaux couplés (CESM)   | ✅ scenarios YAML → composition de passes |
| Unités SI fortes              | ✅ `crate genesis-physics`                |
| Constantes physiques réelles  | ✅ `crate genesis-physics::constants`     |
| AMR / multi-scale time        | ✅ scheduler multi-rate (phase 2)         |
| NetCDF + CF                   | ✅ exports `genesis-scenario::export::nc` |
| Saint-Venant rivières         | ✅ `crate genesis-laws::river`            |
| Lapse rate, Stefan-Boltzmann  | ✅ `crate genesis-laws::atmosphere`       |
| Darcy souterrain              | ✅ `crate genesis-laws::aquifer`          |
| Lotka-Volterra spatial        | ✅ `crate genesis-laws::ecology`          |
| FAIR manifest                 | ✅ chaque run produit `manifest.json`     |
| Validation Köppen-Geiger      | 🚧 phase 2                                |
| Symplectic integrator         | 🚧 phase 3 (si on simule des orbites)     |
| Vraie chimie LAMMPS-grade     | ❌ hors scope                             |

→ Le binaire **`genesis-studio`** est notre **launcher scientifique** :
analogue d'Epic Games Launcher, mais pour les expériences scientifiques.
