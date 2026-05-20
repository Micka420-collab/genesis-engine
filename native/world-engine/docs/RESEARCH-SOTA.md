# Recherche — état de l'art en génération de monde (2026)

> Document de veille interne. Pour chaque approche : ce qui est utilisé en
> production, ce qui marche bien, ce qui ne marche pas, et ce qu'on peut en
> tirer pour Genesis Engine.

---

## 1. Pipelines artistiques DCC

### Houdini + SideFX Labs Terrain Tools
- Référence absolue cinéma + AAA games. Pipeline : `heightfield_*` nodes →
  érosion, biomes, scatter, export.
- **Forces** : pipeline réutilisable, érosion physiquement plausible (Houdini
  18+ avec heightfield erosion GPU OpenCL).
- **Limites** : non temps réel ; baking offline.
- **À retenir** : le *modèle nodal* (DAG de passes) est l'idiome universel.
  Toutes les boîtes pro convergent dessus.

### GAEA 2.x (QuadSpinner) et World Machine 4
- DCC dédiés à la heightmap. GPU compute pour l'érosion.
- **Forces** : qualité visuelle, vitesse (érosion 4 km² en < 1 s sur GPU).
- **Limites** : monolithique, pas pluggable hors de leur UI.
- **À retenir** : leurs algos d'érosion (multi-flow, sediment transport
  hiérarchique) sont publiés ; on peut les porter.

---

## 2. Open-world games en production

### No Man's Sky (Hello Games)
- Univers de 18 quintillions de planètes, générées à la volée à partir
  d'une graine 64 bits.
- Pipeline : **superformula** + bruit pour la silhouette, biomes par
  Whittaker simplifié, voxel sculpting offline.
- **À retenir** : déterminisme absolu = streaming sans BDD géographique.

### Star Citizen — Object Container Streaming
- Streaming hiérarchique : galaxie → système → planète → biome → tile → mesh.
- Chaque niveau est un *container* lazy ; chargement asynchrone, déchargement
  par distance + budget mémoire.
- **À retenir** : la hiérarchie de containers évite les "monde géant chargé
  en RAM". On a déjà cette idée (chunks), elle se généralise.

### Minecraft 1.18+ — "Density Functions"
- Refonte totale du terrain en **fonctions de densité déclaratives** (JSON).
- Chaque biome contient un AST d'opérations : `add`, `mul`, `noise`,
  `spline`, `clamp`, `cache_2d`, `cache_once`, etc.
- Compilateur Java qui fusionne les opérations pour ré-utiliser les
  sous-expressions.
- **À retenir** : **la déclaration > l'impératif**. Le terrain devient un
  programme analysable, qu'on peut introspecter, fusionner, paralléliser.
  C'est la piste la plus intéressante pour notre invention.

### Outerra
- Planète entière, géo précise, depuis l'orbite jusqu'au cm.
- Quadtree spherique adaptatif sur GPU.
- **À retenir** : *fractal-zoom-in déterministe* à n'importe quelle échelle
  est possible — il faut un schéma de coordonnées spherique propre.

### Roblox — infinite procedural terrains (2024)
- Auto-generation de terrains "playable" pour creators non-tech.
- Mélange `wave-function-collapse` (WFC) + heightfield.
- **À retenir** : WFC pour les tilings cohérents (ex. donjons, urbanisme),
  bruit pour les paysages.

---

## 3. Recherche académique récente (2024-2026)

### WaveFunctionCollapse (Gumin, 2016 → toujours actif)
- Adjacency-constraint based ; génère du contenu localement cohérent.
- **Forces** : excellent pour structures discrètes (tiles, rooms, voxel arts).
- **Limites** : scaling difficile, backtracking coûteux.
- **À retenir** : utile pour **biome transitions** discrètes et patterns
  urbains, pas pour le terrain continu.

### Differentiable rendering / Differentiable procgen
- Travaux Adobe / NVIDIA Research (2024-2025) : pipelines procéduraux dont
  les paramètres sont différentiables → on peut *inverser* la génération
  ("trouve la graine qui produit ce paysage").
- **À retenir** : exotique mais permet l'édition par les agents — "rends
  cette zone plus humide" devient un problème d'optimisation.

### Neural world models (Google Genie 2/3, DeepMind SIMA, V-JEPA-2)
- Modèles génératifs qui *prédisent* le pixel suivant conditionnel à une
  action. Worlds joués, pas générés à proprement parler.
- **Forces** : richesse visuelle, prompts en langue naturelle.
- **Limites** : non déterministe à la perfection, coûteux (GPU dense).
- **À retenir** : **pas pour le rendu canonique** du monde — mais
  excellent en *world model* pour la cognition d'agents (imagination de
  futurs courts). C'est le rôle qui leur revient dans Genesis (cf.
  `architecture/tech-stack-2026.md`).

### Gaussian Splatting (3DGS, 2023-2026)
- Représentation neuro-explicite ultra-rapide à rendre.
- **À retenir** : pour la *vue immersive* d'un sous-ensemble du monde, pas
  pour la simulation. Aucun impact sur la couche de génération.

### Sebastian Lague — hydraulic erosion (CPU/GPU pédagogique)
- Implémentation lisible, base de beaucoup d'engins indie modernes.
- **À retenir** : algo droplet-based, idéal pour port WGSL.

### "Procedural Generation in Game Design" (Short & Adams, 3e éd. 2024)
- Référence d'ingénierie. Insiste sur : *constraint propagation*,
  *content-addressed determinism*, *replayable seeds*.

---

## 4. Tendances 2026

| Tendance                            | Adoptée ici |
|-------------------------------------|-------------|
| Déclaratif > impératif              | ✅ → WorldGraph |
| Content-addressed caching           | ✅ → cache crate |
| Compute shader pour érosion         | ✅ → wgpu pass |
| Déterminisme bit-à-bit              | ✅ déjà fait via PRF |
| LOD adaptatif quadtree              | partiel (chunk-based) |
| Neural rendering / Gaussian splats  | ❌ — out of scope (rendu, pas génération) |
| World models neuro pour génération  | ❌ — utile pour la cognition d'agents seulement |
| WFC pour structures discrètes       | 🚧 — phase 2, optionnel |
| Differentiable procgen              | 🚧 — phase 3, recherche |

## 5. Synthèse

Trois piliers conceptuels émergent du SOTA :

1. **Déclaratif** : Minecraft 1.18 a démontré qu'on peut écrire le terrain
   comme un programme analysable, pas une cascade d'appels impératifs.
2. **Content-addressed** : NMS et Star Citizen exploitent le déterminisme
   pour ne JAMAIS stocker le terrain — il se régénère depuis la graine.
   Pousser l'idée à toutes les passes intermédiaires = mémoire infinie
   gratuite.
3. **DAG hétérogène** : Houdini prouve qu'un pipeline nodal mixant CPU et
   GPU est plus maintenable que des fonctions imperatives géantes.

→ Notre **invention** (cf. `INNOVATIONS.md`) unifie ces trois piliers dans
un seul module Rust : le **WorldGraph**.
