# 04 — World Engine

## Génération procédurale

Le monde est **infini, déterministe et reproductible** à partir d'une seed `u128`.

### Pipeline de génération

```
seed
  │
  ▼
[1] Tectonique simulée (10 plaques, 100 itérations)
  │
  ▼
[2] Heightmap (Perlin/Simplex multi-octaves + erosion hydraulique)
  │
  ▼
[3] Climat (Hadley cells + advection humidité)
  │
  ▼
[4] Biomes (Whittaker — température/précipitation)
  │
  ▼
[5] Hydrologie (rivières par steepest descent + lacs)
  │
  ▼
[6] Géologie (couches, minerais, grottes via 3D Perlin worms)
  │
  ▼
[7] Flore (Poisson disk sampling pondéré par biome)
  │
  ▼
[8] Faune initiale (spawn par niche écologique)
```

### Biomes supportés

Tropical humide · Tropical sec · Savane · Désert chaud · Désert froid · Méditerranéen · Tempéré humide · Tempéré sec · Steppe · Taïga · Toundra · Polaire · Aquatique côtier · Aquatique profond · Volcanique · Caverneux

### Climat & météo

- **Modèle simplifié** mais cohérent : cellules de Hadley/Ferrel, advection humidité, masse d'air.
- **Cycles** : jour/nuit (24 h), saisons (4 × 90 j), années, cycles longs (El Niño-like sur 7 ans simulés).
- **Phénomènes émergents** : tempêtes, sécheresses, vagues de froid, moussons.
- **Pas de scripts** : chaque événement extrême est la conséquence d'un état atmosphérique cohérent.

## Représentation du monde

### Choix : voxel hybride + heightmap + entités

- **Heightmap** pour le sol (résolution 1 m, compressé en run-length sur disque)
- **Voxels 3D** uniquement dans les zones modifiables (constructions, grottes, terre creusée) — résolution 0.5 m
- **Entités** pour faune/flore/agents/objets (ECS — Entity Component System)

Cela permet à la fois rendu efficace et **modification émergente** (creuser, bâtir, abattre).

## Streaming intelligent

### Niveaux de détail (LOD)

| LOD | Distance | Représentation | Coût |
|---|---|---|---|
| LOD0 | 0–32 m | full voxel + animations | élevé |
| LOD1 | 32–128 m | mesh simplifié, animations rares | moyen |
| LOD2 | 128–1024 m | impostors (billboards) | faible |
| LOD3 | 1–10 km | tile statique imagée | très faible |
| LOD4 | >10 km | macroblock (couleur dominante) | nulle |

### Stratégie chunk

- **Chunk** = 64×64×128 voxels
- Génération **lazy** : un chunk est créé au moment de la première observation
- **Hashage déterministe** : `hash(seed, chunk_x, chunk_y, chunk_z)` → garantit régénération identique
- **Persistance différée** : un chunk regénérable n'est sauvegardé que s'il a été modifié (gain stockage massif)

## Physique

- **Solide rigide** : Jolt Physics (open-source, performant, déterministe)
- **Fluides simplifiés** : eau cellulaire (cell-by-cell flow, pas Navier-Stokes complet)
- **Feu** : modèle cellulaire avec propagation par humidité/vent
- **Démolition** : voxel destructible avec stabilité structurelle (chaque voxel pèse, supporté ou non)

## Cycles écologiques

### Plantes

- Croissance dépendant de `(soleil, eau, nutriments_sol)`
- Reproduction par dispersion de graines (Poisson process)
- Mortalité par âge, sécheresse, surpâturage, feu

### Faune

- **Modèle proie/prédateur** émergent (Lotka-Volterra spatialement explicite)
- Chaînes trophiques à 4 niveaux : producteurs → herbivores → carnivores petits → carnivores apex
- **Pression de chasse** humaine modélisée comme régulateur

### Ressources minérales

- Distribution **non-uniforme** (gisements concentrés en clusters)
- Épuisables : un gisement extrait ne se régénère pas → tension économique réaliste

## Événements globaux (rares mais réels)

| Événement | Probabilité par siècle simulé | Effets |
|---|---|---|
| Séisme majeur | ~3 | destruction structures, mort, tsunami si côtier |
| Éruption volcanique | ~1 | hiver volcanique global (-2°C, -30% rendements) |
| Pandémie | ~0.5 | propagation par contact, mortalité variable |
| Famine | conséquence climat | mortalité, migrations |
| Impact météoritique | ~0.01 | catastrophique |
| Aurore boréale extrême | ~5 | perturbation comportementale (mythologisée par les agents !) |

Les pandémies sont modélisées par un SEIR spatial sur le graphe de contact des agents.
