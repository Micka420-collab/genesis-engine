# Phase 5g — Hybrid Stratified Worldgen
**Date :** 13 mai 2026
**Question :** peut-on combiner Earth-anchored + procédural physique + IA générative pour un résultat plus puissant que chacun isolément ?

**Réponse courte :** oui, et c'est genuinely original. Aucun projet en 2026 ne fait
les trois ensemble. L'idée est de stratifier le monde en 5 couches qui
travaillent à des résolutions et des cadences différentes, chacune
contraignant les suivantes.

---

## Architecture stratifiée

```
┌─────────────────────────────────────────────────────────────┐
│  L5 — World Models dans les agents (DreamerV3)              │
│       Imagination, planification, "et si"                    │
│       Cadence : par décision saillante                       │
├─────────────────────────────────────────────────────────────┤
│  L4 — Feedback boucle agents → monde                         │
│       Actions modifient L2 ; L2 modifie L3                   │
│       Cadence : par tick                                     │
├─────────────────────────────────────────────────────────────┤
│  L3 — AI Detail (NCA + latent diffusion)                     │
│       Texture cellule, végétation unique, micro-features     │
│       Résolution : < 1 m                                     │
│       Cadence : à la demande sur cellules visibles           │
├─────────────────────────────────────────────────────────────┤
│  L2 — Sim-Lift physique vivante                              │
│       Érosion live, succession végétale, météo, pollution    │
│       Résolution : 1 m – 100 m                               │
│       Cadence : par jour-sim                                 │
├─────────────────────────────────────────────────────────────┤
│  L1 — Earth-Seed immuable                                    │
│       Copernicus DEM + CHELSA + Resolve + HydroSHEDS         │
│       Résolution : 30 m – 1 km                               │
│       Cadence : chargé une fois, jamais modifié              │
└─────────────────────────────────────────────────────────────┘
```

**Direction des contraintes :** chaque couche contraint la suivante mais
n'est jamais contrainte en retour. Une rivière qui existe en L1 ne peut
jamais être supprimée par les agents ; ils peuvent en détourner un bras
local (L2) ou modifier sa texture immédiate (L3), pas faire disparaître
la Loire.

---

## Détail des cinq couches

### L1 — Earth-Seed (immuable)

- **Sources** : Copernicus DEM GLO-30 + CHELSA bio1/bio12 + Resolve
  Ecoregions 2017 + HydroSHEDS HydroRIVERS/HydroLAKES + ESA WorldCover
  10 m + SoilGrids.
- **Stockage** : streamé depuis AWS Open Data via `rasterio.windows.from_bounds`,
  jamais matérialisé entier en mémoire.
- **Rôle** : c'est la photo de la Terre. Elle ne bouge plus. Elle dit
  "ici, c'est le lac Léman, 372 m, biome tempéré, sol calcaire, rivière
  Rhône qui sort vers l'ouest". Toutes les autres couches sont
  contraintes par L1 — la cohérence planétaire vient de là.

### L2 — Sim-Lift (vivante, physique)

C'est l'ajout par rapport à Earth-anchored seul. Au lieu d'utiliser L1
comme un environnement figé, on **simule la physique par dessus** à une
échelle plus fine :

- **Érosion hydraulique live** — chaque pluie ERA5 ou CHELSA fait couler
  de l'eau le long du gradient L1. Sur quelques décennies-sim, des
  ravines apparaissent dans les pentes que l'érosion réelle n'a pas
  encore creusées au pas de temps du DEM. Implémentation : `richdem`
  pour flow accumulation + simulation goutte stochastique.
- **Succession végétale** — chaque chunk a un état de végétation qui
  évolue selon biome × temps-depuis-perturbation. Forêt coupée par les
  agents → friche → garrigue → bois jeune → forêt mature, avec des
  vraies constantes de temps (~80 ans pour reconstituer un peuplement
  forestier tempéré).
- **Météo locale ERA5** — au-dessus des climatologies CHELSA, on
  superpose des événements météo horaires : orages, pluies de mousson,
  vagues de chaleur. Provient de `cdsapi` quand on a internet,
  procédural sinon.
- **Géomorphologie ponctuelle** — éboulements, glissements de terrain,
  inondations locales déclenchées par météo + pente + saturation du sol.
- **Pollution L2** — le CO₂ atmosphérique de `ecology.py` vit ici, avec
  un mélange spatial (ce n'est pas un simple scalaire global mais une
  grille de concentration). Les fumées de foyers se dispersent selon le
  vent.

Cadence : update par "jour-sim" (≈ 86 400 ticks de drive_accel). Léger.

### L3 — AI Detail (génératif)

C'est la couche que tu n'auras nulle part ailleurs. Elle apporte les 99 %
de réalisme visuel.

- **NCA léger** entraîné offline (50–200k paramètres, tournable CPU) qui,
  conditionné par (biome, saison, humidité, sol, perturbation), génère
  une "texture cellule" : densité d'arbres, type d'herbes, patches de
  rochers, mousses. Cellule = 1 m² ; régénéré quand un agent passe à
  moins de 100 m d'une cellule jamais visitée.
- **Modèle de diffusion latent** plus lourd (1–2 B params, single-GPU
  optionnel) pour les "patches uniques" : sentier de transhumance,
  clairière, dolmen, mégalithe, lieu de culte agent-construit. Appelé
  seulement à des points particuliers (densité < 1 par km²).
- **Output sémantique structuré**, pas pixels. Le L3 émet une
  description structurée que la couche de rendu interprète : "ici
  3 chênes, 1 frêne, un buisson, 4 pierres" plutôt qu'une image. Comme
  ça la simulation reste manipulable par les agents (ils peuvent
  abattre un chêne précis) et reste déterministe pour le replay.
- **Déterminisme préservé** : chaque cellule a un seed PRF dérivé de
  `(world_seed, lat, lon, perturbation_history_hash)` qui pilote
  l'inférence — les sorties IA sont reproductibles bit-à-bit.

### L4 — Feedback agents → monde

Le pont qui rend le système vivant :

- Quand un agent coupe un arbre, la cellule L3 perd un arbre, son hash
  de perturbation change, sa texture sera regénérée la prochaine fois
  qu'elle est visible.
- Quand un groupe construit un village (Phase 5c), L2 enregistre les
  emprises au sol comme "perturbation permanente" qui empêche la
  succession végétale.
- Quand l'agriculture (Phase 5d) défriche, L2 passe la cellule en
  "champ cultivé" qui modifie le bilan CO₂ (champs absorbent moins que
  forêt), ce qui propage à `ecology.atm`.
- Quand un foyer brûle du bois, fumée + CO₂ → L2 grille du vent →
  concentration locale.

### L5 — World Models dans les agents

C'est ce qui transforme les agents de réflexes en planificateurs :

- **DreamerV3** entraîné sur la simulation (pas sur des pixels) pour
  donner aux agents un modèle prédictif latent. Un agent peut
  "imaginer" : "si je marche 30 minutes vers le sud, qu'est-ce qui se
  passe ?" ; "si je coupe tous les arbres autour, qu'est-ce que ça
  donne dans 10 ans ?". Single-GPU pour entraîner, CPU pour inférer
  une politique distillée.
- **Imagination partagée par groupe** — plutôt qu'un Dreamer par agent
  (trop cher), un Dreamer par culture/groupe, partagé. Les agents
  utilisent l'imagination du groupe quand ils ont une décision
  saillante (construction, migration, conflit).
- **Boucle réflexe + délibéré** : la policy R0 réflexive (Phase 4) gère
  95 % des ticks ; le World Model n'est consulté que sur événements
  saillants (drive critique, opportunité repérée, conflit). Coût
  amorti.

---

## Synergies — pourquoi c'est plus que la somme

**L1 contraint L3.** Le modèle de diffusion ne génère jamais d'arbre
dans le lac Léman parce que L1 dit "c'est de l'eau". Pas de patchs
absurdes — c'est ce qui distingue notre approche de "Stable Diffusion
sur des coordonnées GPS" qui produit des images jolies mais
incohérentes.

**L2 anime L1.** Le DEM Copernicus est une photo de 2024-25 ; nos
agents vont vivre des décennies-sim. L2 fait évoluer le terrain au
rythme géologique compressé (érosion, succession), donc le monde
ressemble à la Terre mais pas figé.

**L3 cache L1.** L'observateur ne voit jamais les pixels SRTM directs,
il voit toujours la texture L3 conditionnée. Donc même si L1 est à 30 m
de résolution, la sortie visible est à 1 m — gain de 900× sans avoir à
stocker un DEM à 1 m.

**L4 ferme la boucle.** C'est ce qui rend la civilisation "vraie" : ce
qu'ils font modifie le monde, le monde modifié contraint leur
prochaine décision. Sans L4 la simulation reste un theme park, avec L4
c'est un laboratoire scientifique.

**L5 transforme les agents.** Avec L5, deux agents avec exactement les
mêmes drives et personnalités peuvent diverger parce que leurs World
Models intériorisés ont vu des histoires différentes — première vraie
graine d'individualité cognitive. C'est aussi la couche qui leur permet
de "planifier le futur climatique" : un agent avec L5 peut imaginer
"si on continue à brûler, dans 200 ans on a +3 K et la forêt brûle" et
décider d'agir en conséquence.

---

## Originalité — où placer ça dans le paysage 2026

| Projet | L1 | L2 | L3 | L4 | L5 |
|---|---|---|---|---|---|
| Generative Agents (Smallville) | ❌ | ❌ | ❌ | ✓ | partiel |
| Project Sid (PIANO) | ❌ | partiel | ❌ | ✓ | ✓ |
| NVIDIA Earth-2 | ✓ | ✓ | partiel | ❌ | ❌ |
| GeoLife+ (Patterns of Life) | ✓ | ❌ | ❌ | partiel | ❌ |
| OASIS (CAMEL-AI) | ❌ | ❌ | ❌ | ✓ | partiel |
| Genie 3 (DeepMind) | ❌ | ❌ | ✓ | partiel | ❌ |
| **Genesis Engine Phase 5g** | **✓** | **✓** | **✓** | **✓** | **✓** |

Genesis Engine serait donc le premier système connu à empiler les cinq
couches. Le créneau identifié dans le dossier de recherche
("aucun projet 2024–26 ne combine agents culture-bearing + terrain géo
réel + couplage climat") devient occupable.

---

## Coût et chemin d'exécution

L'architecture complète n'est PAS livrable en un seul sprint, mais elle
se décompose en étapes incrémentales qui livrent de la valeur à chaque
palier :

| Palier | Couches actives | Effort estimé | Valeur livrée |
|---|---|---|---|
| **P1** | L1 seule | ~1,5 sem | Le monde est la vraie Terre, statique |
| **P2** | L1 + L2 | +2 sem | Le monde évolue physiquement |
| **P3** | L1 + L2 + L4 | +1 sem | Les agents modifient le monde réel |
| **P4** | L1 + L2 + L3 + L4 | +3 sem | Détails IA visuels, 99 % de réalisme |
| **P5** | L1 + L2 + L3 + L4 + L5 | +4 sem | Agents avec imagination DreamerV3 |

Soit ~11,5 semaines pour l'architecture complète. P1 + P2 + P4 (sans
L5) en ~6,5 semaines donne déjà un résultat extraordinaire — agents
réflexes mais monde indiscernable de la Terre. P5 est ce qui pousse les
agents à la "qualité humaine" cognitive.

---

## Détails techniques notables

### Déterminisme bout-en-bout
Toute la stack reste reproductible bit-à-bit grâce à un PRF unique
`(world_seed, layer_id, coord, perturbation_hash)`. Même un run avec
L3-IA donne le même monde sur deux machines différentes, à condition
de fixer le seed des modèles génératifs (graines `numpy` et `torch`).

### Cache stratifié sur disque
- L1 : COG streaming, jamais en cache local complet.
- L2 : par chunk, sérialisé en npz quand un chunk sort du LRU.
- L3 : par cellule, hashé par perturbation_history. Cache hit ratio
  attendu > 95 % une fois le monde exploré.
- L5 : checkpoints DreamerV3 sur disque, chargés à la demande par
  culture.

### Backward compatibility
La structure `Chunk` actuelle devient une vue sur L2. Les Phases 1–4
qui consomment `chunk.height`, `chunk.biome`, `chunk.water`,
`chunk.food_kcal` continuent à fonctionner sans modification : ces
champs sont exposés comme propriétés calculées à partir de
(L1 + L2 + L4).

### Sécurité scientifique
Quand on lance un run en `--science-mode`, L3-IA est désactivée
(reproductibilité absolue) et L5 est gelée à un checkpoint fixe. Les
runs de production avec L3 et L5 sont signalés dans le journal comme
"non-replicable-from-seed-only-needs-model-weights".

---

## Recommandation pratique

**Ne PAS essayer de faire les 5 couches en parallèle.** L'ordre que je
recommande :

1. **L1 seule (Phase 5a)** : on charge la vraie Terre. Tu te promènes
   au Léman. Concret, livrable, motivant.
2. **L4 minimum (boucle feedback)** : connecter ce qu'on a déjà
   (construction, pollution, agriculture) au monde L1 statique.
3. **L2 simple (érosion + succession végétale)** : passer le monde de
   statique à vivant. C'est là que tu sens vraiment la différence.
4. **L3 NCA** : la couche texture détaillée, single-CPU pour
   commencer. Avant de t'engager dans un modèle de diffusion lourd.
5. **L5 DreamerV3** : la couche cognition imaginative. C'est ce qui
   transforme tes agents en "êtres planifiant" — la qualité humaine que
   tu m'as demandée. Mais c'est le plus cher en R&D, c'est pour la fin.

Dis-moi si on attaque **L1 (Earth-anchored réelle)** tout de suite, ou
si tu veux d'abord stabiliser et intégrer ce qui est déjà conçu
(Phase 5c construction + 5d invention/écologie + 5e god avatar + 5g
audio/livres) avant de partir sur le worldgen.
