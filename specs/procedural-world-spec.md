# Spec — Monde procédural

## Paramètres globaux d'une simulation

```yaml
world:
  seed: u128
  size: infinite | bounded(W, H)
  gravity: 9.81
  day_length_seconds_real: 86400 / time_scale
  year_length_days: 360
  axial_tilt_deg: 23.5
  rotation_period_h: 24

physics:
  voxel_size_m: 0.5
  chunk_size_voxels: [64, 64, 128]
  fluid_model: cellular_advection
  fire_model: cellular_humidity_wind

biology:
  metabolic_rate: 1.0
  reproduction_cooldown_days: 30
  child_dependency_years: 10
  max_lifespan_years: 80   # baseline, modulé par génome

cognition:
  policy_model: "policy-tx-200m"
  world_model: "dreamer-v3-base"
  memory_capacity_episodic: 20000
  memory_consolidation: nightly

evolution:
  mutation_rate: 0.001
  crossover: gene_wise
  selection: fitness_proportional + sexual_selection

events:
  earthquake_per_century: 3
  volcano_per_century: 1
  pandemic_per_century: 0.5
```

## Génération du terrain — détail algorithmique

### 1. Tectonique
- 10 plaques tectoniques initialisées par Voronoï sur sphère
- Vecteurs de mouvement aléatoires
- Itérations : convergence/divergence/transformation
- Output : carte « élévation tectonique base » + lignes de subduction (volcans)

### 2. Erosion
- **Hydraulique** (rivières) : algorithme stream-power
- **Thermique** (montagnes) : adoucissement angles
- 100 itérations sur la heightmap base

### 3. Climat — modèle simplifié
- Cellules de Hadley/Ferrel/Polaire approximées
- Advection humidité depuis océans (Lambert-Beer modifié)
- Effet d'altitude (lapse rate adiabatique)
- Effet de continentalité (variance journalière)

### 4. Biomes (Whittaker)
- Axes : T° moyenne annuelle, précipitation annuelle
- 16 biomes mappés
- Transitions douces (gradient noisy)

### 5. Hydrologie
- Steepest descent depuis chaque pixel élevé → rivières
- Bassins de drainage → lacs
- Aquifères implicites

### 6. Géologie
- Couches strates simulées
- Minerais : Poisson cluster process
- Grottes : 3D Perlin worms (algorithme Minecraft-like, version moderne)

### 7. Flore
- Densité par biome (Poisson disk)
- Espèces spécifiques par biome
- Cycle de vie individuel par plante (état persistant)

### 8. Faune
- Spawn par niche (herbivore plaine, prédateur forêt, …)
- Densité initiale équilibrée pour l'écosystème
- Population dynamique selon Lotka-Volterra spatialement explicite

## Reproductibilité

- **Toute** valeur aléatoire utilise un PRF indexé : `prf(world_seed, "category", x, y, z, ...)`
- **Aucun** appel à `rand()` non indexé n'est autorisé (lint custom Rust)
- Régénération bit-à-bit garantie

## Performance cible

| Opération | Cible (1 chunk) |
|---|---|
| Génération initiale | < 50 ms CPU |
| Modification voxel | < 1 ms |
| Streaming chargement | < 100 ms |
| Compression état | < 10 ms (Zstd L3) |

## Format de stockage chunk

```
chunk.zst
  header (16 B):
    version u8
    palette_size u8
    flags u16
    voxel_count u32
    timestamp_tick u64
  palette: PaletteEntry[palette_size]
  voxels: rle_encoded(palette_indices)
  entities: rkyv-serialized list
```
