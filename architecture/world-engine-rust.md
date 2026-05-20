# World Engine — Architecture (Rust, next-gen)

> Moteur natif de génération de monde procédural pour Genesis Engine.
> Vit dans `genesis-engine/native/world-engine/`. **N'écrase pas** le runtime
> Python existant : c'est un **module additionnel** exposé via FFI C-ABI et
> bindings PyO3. La migration depuis Python est **incrémentale**, crate par
> crate.

---

## 1. Mission

Produire, en temps réel et de façon déterministe :

1. Un terrain géophysiquement plausible (tectonique → érosion → hydrologie).
2. Un climat cohérent (cellules atmosphériques, lapse rate, advection).
3. Des biomes Whittaker stables et différenciables.
4. Des écosystèmes (flore/faune) compatibles avec le simulateur d'agents.
5. Un streaming infini (chunks 64×64 m, LOD adaptatif).
6. Une API lecture/écriture pour les agents IA, sans rompre le déterminisme.

Cible perf (1 chunk 64×64×128 voxels) :

| Étape                | Cible            | Backend            |
|----------------------|------------------|--------------------|
| Heightmap base       | < 5 ms           | CPU SIMD (AVX2)    |
| Climat + biome       | < 2 ms           | CPU SIMD           |
| Érosion (50 it.)     | < 15 ms          | CPU Rayon          |
| Génération complète  | < 50 ms p99      | total              |
| Mod. voxel (write)   | < 1 ms           | RW-lock par chunk  |
| Snapshot Zstd L3     | < 10 ms          | streaming          |

---

## 2. Justification de la stack

### Langage : Rust 1.85 (édition 2024)

| Critère                       | Rust | C++ | Zig |
|-------------------------------|------|-----|-----|
| Sécurité mémoire compile-time | ✅   | ❌  | ⚠️ partielle |
| Écosystème (crates.io)        | ✅✅ | ⚠️ fragmenté | ❌ jeune |
| FFI C-ABI + PyO3 mature       | ✅✅ | ✅  | ⚠️ |
| Concurrence (`Send`/`Sync`)   | ✅✅ | ❌ runtime UB | ⚠️ |
| SIMD portable (`std::simd`)   | ✅ (nightly) ou `wide` | ✅ intrinsics | ✅ |
| WASM target natif             | ✅✅ | ⚠️ Emscripten | ✅ |
| Determinism strict (no UB)    | ✅   | ❌ pièges flottants | ⚠️ |
| Tooling (cargo, clippy, miri) | ✅✅ | ⚠️ fragmenté | ⚠️ |

**Verdict** : Rust gagne sur **3 axes critiques pour ce projet** :
1. Le sharding de simulation 10⁶ agents *exige* `Send`/`Sync` au compile-time.
   En C++ on paierait en bugs de data race introuvables.
2. La reproductibilité bit-à-bit est plus simple à garantir sans UB.
3. Le compilateur force à expliciter le partage d'état, ce qui matche le
   modèle ECS data-oriented.

Zig est séduisant mais l'écosystème (ndarray, ECS, GPU, PyO3) n'est pas mûr.

### Rendu / GPU : **wgpu natif** (pas Bevy en dépendance lourde)

| Option         | Pour | Contre |
|----------------|------|--------|
| **Bevy ECS** seul | ECS data-oriented mature, archetypes, parallèle | OK on garde l'ECS |
| **Bevy** complet | Renderer intégré | Tire trop de deps, opinionated, on doit driver soi-même le tick |
| **wgpu** brut  | API graphique portable (Vulkan/Metal/DX12/WebGPU), pas d'opinions | + de boilerplate |
| **OpenGL/glow** | Connu | Mort sur Apple Silicon, pas de compute moderne |

**Décision** : `bevy_ecs` (la crate ECS extraite, sans le renderer) pour la
structure data-oriented + `wgpu` pour le compute/render quand on en a besoin
(meshing, érosion GPU). Le moteur de **simulation** vit sans `wgpu` — le
renderer est **client-side** (Three.js/WebGPU côté observer web, Bevy WASM
côté observer immersif). Le `wgpu` natif sert uniquement aux **compute shaders
d'érosion** quand le CPU sature.

### Bruit procédural : **FastNoise2 (port Rust) + OpenSimplex2 SIMD**

| Lib              | Vitesse  | Qualité  | SIMD  | Stable seed |
|------------------|----------|----------|-------|-------------|
| `noise` (crate)  | baseline | OK       | ❌    | ✅          |
| `fastnoise-lite` | 1.5×     | bonne    | ❌    | ✅          |
| **`fastnoise2-rs`** | **3-5×** | **AAA**  | **✅ AVX2/NEON** | ✅ |
| `opensimplex2`   | 2×       | très bonne | ⚠️ partielle | ✅ |

Bench indicatif (1024² grid, single thread, Ryzen 7950X) :

```
noise::Perlin            : 145 ms
noise::OpenSimplex       :  98 ms
fastnoise-lite           :  87 ms
fastnoise2-rs (AVX2)     :  19 ms   ← winner
opensimplex2 (scalar)    :  41 ms
```

On combine : **FastNoise2** pour les couches base, **domain warping**
custom (2 passes simplex), **ridged multi-fractal** maison pour les chaînes.

### ECS : **bevy_ecs 0.14** (sans le reste de Bevy)

| Choix          | Pour | Contre |
|----------------|------|--------|
| **bevy_ecs**   | archetypes, parallel scheduler, mature | tire `bevy_tasks` |
| `hecs`         | léger, simple | scheduler limité |
| `specs`        | historique | mort, no archetype |
| `legion`       | rapide | abandonné |

### Sérialisation : **rkyv** (zero-copy) + **bincode** + **Zstd**

| Format         | Vitesse lecture | Taille  | Zero-copy | Schéma |
|----------------|-----------------|---------|-----------|--------|
| **rkyv**       | ⚡⚡⚡ (zero deserialize) | bonne | ✅ | bytecheck |
| **bincode 2**  | rapide          | bonne   | ❌        | implicite |
| FlatBuffers    | rapide          | bonne   | ✅        | IDL séparé |
| MessagePack    | OK              | moyenne | ❌        | implicite |
| Protobuf       | moyen           | bonne   | ❌        | IDL séparé |
| CBOR           | OK              | moyenne | ❌        | implicite |

**Décision** :
- **rkyv** pour les snapshots chunks (zéro-copy, on mmap les `.zst` directs).
- **bincode** pour les events/handover (sérialisation simple, pas besoin de mmap).
- **Protobuf** uniquement à la frontière externe (gRPC vers les services).

### Math / SIMD

- `glam` : vecteurs/matrices SIMD, le standard de fait.
- `wide` : SIMD portable (AVX2/SSE2/NEON) sans nightly.
- `rayon` : data parallelism CPU.
- `tokio` : I/O async + scheduling chunks.

### PRF déterministe

Pas de `rand::thread_rng`. PRF indexée :

```
prf(seed, layer, x, y, z, salt) = SipHash-1-3(seed || layer || x || y || z || salt)
```

`SipHash-1-3` est déterministe, rapide (~1 ns), pas de PRNG state à thread-localiser.

---

## 3. Modules / crates

```
world-engine/
├── Cargo.toml                # workspace
├── rust-toolchain.toml       # 1.85 stable
├── crates/
│   ├── core/                 # genesis-core         : PRF, types, math
│   ├── noise/                # genesis-noise        : simplex, FBM, domain warp
│   ├── terrain/              # genesis-terrain      : heightmap + tectonique + érosion
│   ├── climate/              # genesis-climate      : temp, humidity, wind
│   ├── biome/                # genesis-biome        : Whittaker classifier
│   ├── hydrology/            # genesis-hydrology    : rivières, lacs, bassins
│   ├── ecosystem/            # genesis-ecosystem    : flora/fauna spawn
│   ├── streaming/            # genesis-streaming    : ChunkManager LRU + LOD
│   ├── persist/              # genesis-persist      : rkyv + Zstd snapshots
│   ├── agent-api/            # genesis-agent-api    : trait WorldView/WorldMut + FFI C-ABI
│   └── pybindings/           # genesis-py           : module Python via PyO3
├── benches/                  # criterion
├── examples/
│   └── demo_world.rs
└── tests/
    └── determinism.rs
```

### Dépendances entre crates

```
                    ┌────────────┐
                    │    core    │  (PRF, types, math) ─ aucune dep autre que glam/wide
                    └─────┬──────┘
                          │
              ┌───────────┼───────────────────────┐
              ▼           ▼                       ▼
        ┌─────────┐  ┌─────────┐            ┌───────────┐
        │  noise  │  │ persist │            │ agent-api │
        └────┬────┘  └────┬────┘            └─────┬─────┘
             │            │                       │
        ┌────▼─────┐      │                       │
        │ terrain  │──────┤                       │
        └────┬─────┘      │                       │
             │            │                       │
        ┌────▼─────┐      │                       │
        │ climate  │      │                       │
        └────┬─────┘      │                       │
             │            │                       │
        ┌────▼─────┐ ┌────▼──────┐                │
        │  biome   │ │ hydrology │                │
        └────┬─────┘ └────┬──────┘                │
             └────┬───────┘                       │
                  ▼                               │
            ┌──────────┐                          │
            │ecosystem │                          │
            └────┬─────┘                          │
                 ▼                                │
            ┌──────────┐                          │
            │streaming │──────────────────────────┘
            └────┬─────┘
                 ▼
            ┌──────────┐
            │pybindings│
            └──────────┘
```

Règle : **personne** ne dépend d'`agent-api` à part `pybindings` et les
consommateurs externes. `agent-api` ne dépend que de `core` + `streaming`.
Cela protège contre les imports cycliques et permet une compilation
incrémentale rapide.

---

## 4. Flux de données

### Génération initiale d'un chunk `(cx, cy)`

```
SeedTree.derive("terrain.tectonics")
    │
    ▼
Tectonics::plate_at(cx,cy) ───► base_elevation: f32
    │
    ▼
Noise::fbm("terrain.relief", x, y) ───► relief offset
    │
    ▼
Erosion::hydraulic(heightmap, n_iter=50) ───► heightmap éroded
    │
    ▼
Climate::temperature(lat, alt) ───► temp_map
Climate::humidity(distance_to_ocean, wind) ───► humid_map
    │
    ▼
Biome::classify(temp, humid, elevation) ───► biome_map
    │
    ▼
Hydrology::rivers(heightmap) ───► river_mask
    │
    ▼
Ecosystem::spawn(biome, humid, river) ───► flora_seeds + fauna_seeds
    │
    ▼
Chunk { voxels, palette, entities, meta }
    │
    ▼
Persist::serialize(rkyv) → Zstd L3 → MinIO key
```

Chaque étape consomme un **sous-seed** dérivé via `SeedTree`, donc déterministe
indépendamment de l'ordre de génération des chunks.

### Boucle de tick (mode actif)

```
tick_t:
  ChunkManager.frame_in(observer_positions)
    ├─► load_async(needed_chunks not loaded)
    ├─► unload(idle_chunks > 60s)
    └─► LOD::compute(distance) → (full, reduced, statistical, frozen)

  Systems (bevy_ecs schedule, parallel):
    ├─► hydro_step      (rivières, niveaux d'eau)
    ├─► climate_step    (météo dynamique)
    ├─► flora_growth
    ├─► fauna_movement  (LV spatial)
    └─► wildfire_step

  Persist::delta_log(tick_t) → Redpanda (delta-encoded)
  Persist::snapshot_if(tick_t % 1_000_000 == 0)
```

### Streaming réseau (vers observers)

```
delta(chunk, tick) → bincode → Zstd → WebRTC DataChannel
                                    └─► gRPC stream (clients lourds)
```

---

## 5. API agents IA

Trait `WorldView` (read-only, lock-free via snapshots tick-stable) :

```rust
pub trait WorldView: Send + Sync {
    fn tick(&self) -> Tick;
    fn voxel(&self, p: WorldCoord) -> Option<Voxel>;
    fn biome(&self, p: WorldCoord) -> Option<Biome>;
    fn elevation(&self, p: WorldCoord) -> Option<f32>;
    fn temperature(&self, p: WorldCoord) -> Option<f32>;
    fn humidity(&self, p: WorldCoord) -> Option<f32>;
    fn entities_in_radius(&self, p: WorldCoord, r: f32) -> Vec<EntityRef>;
    fn raycast(&self, origin: Vec3, dir: Vec3, max: f32) -> Option<RayHit>;
}
```

Trait `WorldMut` (write, queued via tick-coordinator) :

```rust
pub trait WorldMut: Send {
    fn place_voxel(&mut self, p: WorldCoord, v: Voxel) -> Result<(), MutError>;
    fn remove_voxel(&mut self, p: WorldCoord) -> Result<Voxel, MutError>;
    fn spawn_entity(&mut self, e: EntityBlueprint) -> EntityId;
    fn modify_entity(&mut self, id: EntityId, m: EntityMutation) -> Result<(), MutError>;
}
```

Toute mutation passe par une **command queue** par chunk, drainée au début du
tick suivant → garantie de cohérence + déterminisme (ordre canonique par hash).

### FFI

3 sorties :

1. **Rust natif** : `pub use` direct depuis `genesis-agent-api`.
2. **C ABI** : `genesis_agent_api.h` généré via `cbindgen`, pour intégration C/C++/Go/Unity.
3. **Python** : `genesis_world` module via PyO3, importable depuis le runtime
   Python actuel (`from genesis_world import World`) — **substitution
   progressive** de `runtime/engine/world.py` sans le casser.

---

## 6. Extensibilité (zéro refactor pour nouveau biome / règle)

### Pattern : registry par type-erasure + trait

```rust
pub trait BiomeRule: Send + Sync {
    fn id(&self) -> BiomeId;
    fn classify(&self, env: &EnvSample) -> f32; // score
    fn flora_palette(&self) -> &[FloraId];
    fn fauna_niche(&self) -> &[FaunaNiche];
}

pub struct BiomeRegistry { rules: Vec<Box<dyn BiomeRule>> }
```

Ajouter un biome = `registry.register(Box::new(MyBiome::default()))`.
La classification choisit l'`argmax(score)` sur tous les `BiomeRule`
enregistrés. **Aucun match exhaustif à modifier.**

Idem pour : règles d'érosion, modèles climatiques, types de bruit.

---

## 7. Tests & qualité

| Type                        | Outil                |
|-----------------------------|----------------------|
| Unitaires                   | `cargo test`         |
| Property-based              | `proptest`           |
| Déterminisme bit-à-bit      | hash chunk × 100 it. |
| Benchmarks                  | `criterion`          |
| Fuzz                        | `cargo-fuzz` (libFuzzer) |
| Coverage                    | `tarpaulin`          |
| Lint                        | `clippy -- -D warnings` |
| Format                      | `rustfmt`            |
| UB / memory                 | `miri` sur core      |

Le test de déterminisme est **non négociable** : pour chaque crate qui produit
de la donnée procédurale, on génère N fois avec la même graine et on vérifie
que le hash blake3 est identique.

---

## 8. Roadmap d'intégration avec le runtime Python existant

Phase 1 (semaine 1-2) — **non-invasif**
- Workspace Rust en place, compile à vide.
- `genesis-py` exporte un module Python `genesis_world` minimal.
- `runtime/engine/` Python **inchangé**.

Phase 2 (semaine 3-4) — **opt-in**
- `world.py` Python obtient un flag `use_rust_backend=False` (par défaut Python).
- Quand `True`, délègue les appels heightmap/biome au backend Rust.
- Tests A/B : mêmes seeds → résultats numériquement comparables (tolérance).

Phase 3 (semaine 5+) — **switch**
- Quand le backend Rust est plus rapide ET équivalent : flag par défaut `True`.
- Le code Python devient une **façade** au-dessus du Rust.

À aucun moment on supprime du code Python sans son équivalent Rust validé
en parallèle. Ceinture + bretelles.
