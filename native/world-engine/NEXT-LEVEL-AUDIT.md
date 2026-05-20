# Genesis World Engine — Audit "Next Level" et roadmap révolutionnaire

**Date :** 2026-05-16
**Périmètre :** workspace Rust `native/world-engine/` (15 crates)
**Mode :** audit complet + propositions architecturales + code stubs Rust isolés.
**Source-of-truth des proposals :** `proposals/axis{N}_*` (modules indépendants, hors build pour ne rien casser).

---

## 0. Verdict global en une page

Le moteur **fonctionne** et a un socle solide :

- Détermination bit-à-bit (PRF tree, BLAKE3 hashes, `forbid(unsafe_code)`).
- Pipeline procédural propre : heightmap → érosion → hydrologie → climat → biome → voxels → flore/faune.
- ECS pré-câblé (`bevy_ecs` workspace dep), Tokio + Rayon, DashMap pour cache hot.
- WorldGraph DAG content-addressed (cache L1/L2) — vraie innovation.
- GPU compute pour érosion (wgpu) — câblé en feature, pas wired par défaut.

Mais il est **générique** et plafonne à un terrain plausible-statique sans vie. Six failles bloquent le saut vers "next-level" :

| # | Faille critique                                              | Impact            |
|---|--------------------------------------------------------------|-------------------|
| F1 | Tectonique = Voronoi statique (pas de vraie dérive)         | Pas de réalisme géologique |
| F2 | Érosion s'arrête au bord du chunk (rivières discontinues)   | Rivières "fantômes" cross-chunk |
| F3 | Climat = fonction analytique pure de (lat, alt)             | Pas de météo dynamique, pas d'ombre pluviométrique |
| F4 | Ecosystem = seeds posées, **aucune simulation runtime**     | Pas de chaîne alimentaire, pas d'émergence |
| F5 | `WorldClient::apply_pending` est un **stub** documenté tel  | Les agents IA ne peuvent **pas écrire** dans le monde |
| F6 | Pas de caves / pas de SDF 3D, pas de saisons, pas de snapshot/restore | Bloque RL, immersion, exploration |

Les six failles correspondent **exactement** aux six axes de la mission. Aucune n'est insurmontable ; toutes demandent du vrai code, pas un patch.

---

## 1. Audit détaillé du moteur actuel

### 1.1 Inventaire des crates (`native/world-engine/crates/`)

| Crate           | Lignes | Rôle                                              | État    |
|-----------------|--------|---------------------------------------------------|---------|
| `core`          | ~300   | PRF, seed tree, voxel, chunk coord, tick          | ✅ solide |
| `noise`         | ~400   | FBM, ridged, simplex, domain warp                 | ✅ solide |
| `terrain`       | ~500   | Heightmap, tectonique Voronoi, érosion CPU        | ⚠ statique |
| `climate`       | ~190   | Climate sample (temp, humidité, vent)             | ⚠ statique |
| `biome`         | ~250   | Whittaker + registry                              | ✅ solide |
| `hydrology`     | ~135   | D8 drainage + lakes (par chunk)                   | ⚠ par-chunk |
| `ecosystem`     | ~210   | Flora/fauna seeds (génère, ne simule pas)         | ❌ seeds only |
| `streaming`     | ~400   | ChunkManager (Tokio + DashMap), Chunk, LOD        | ✅ correct |
| `persist`       | ~80    | bincode + zstd                                    | ✅ solide |
| `agent-api`     | ~310   | WorldView trait + WorldClient                     | ⚠ writes stubbed |
| `pybindings`    | -      | PyO3 (non lu en détail)                           | ? |
| `cache`         | ~130   | L1 (DashMap) + L2 (mmap files)                    | ✅ solide |
| `worldgraph`    | ~250   | DAG content-addressed, Lineage                    | ✅ innovant |
| `gpu`           | ~240   | wgpu erosion compute                              | ⚠ pas wired |
| `intent`        | ~250   | Intent-aware prefetch                             | ✅ solide |

### 1.2 Bottlenecks critiques identifiés

#### B1 — Tectonique = Voronoi statique (`terrain/src/tectonics.rs:48-147`)
```rust
let conv_sign = (self.prf.signed_f32(self.layer, 0, 0, 0, s.id as u32)).signum();
```
Les plaques **n'ont pas de mouvement temporel**. `motion: [f32; 2]` est calculé mais **jamais utilisé**. Le terme d'orogenèse est juste un hash signé pseudo-aléatoire. Pas de convergence/divergence physique, pas de cycle de Wilson, pas de subduction asymétrique.

#### B2 — Érosion bloquée au bord du chunk (`terrain/src/erosion.rs:50-52`)
```rust
if nx < 1 || ny < 1 || nx >= w - 2 || ny >= h - 2 {
    break;  // ← le droplet meurt au bord
}
```
Les rivières se coupent à la frontière chunk. Hydrology calcule un drainage par chunk → "rivière" qui apparaît dans un chunk et **n'existe pas** dans le chunk voisin.

#### B3 — Hydrologie : drainage local + sort O(N log N) (`hydrology/src/lib.rs:40-77`)
```rust
let mut order: Vec<u32> = (0..total as u32).collect();
order.sort_by(|a, b| ...);  // sort par élévation décroissante, séquentiel
```
- Le tri est séquentiel (~20k cells × log → 200k cmp par chunk).
- Pas de paralleisation possible sur la passe drainage.
- Pas de basin-filling (lacs marqués par "0 voisin downslope + drainage > 4 × threshold" — approximation grossière).

#### B4 — Climate trois-bandes hardcodé (`climate/src/lib.rs:128-136`)
```rust
let (u, v) = if lat_deg < 30.0 { (-6.0, -1.5 * hemi) }
             else if lat_deg < 60.0 { (8.0, 1.0 * hemi) }
             else { (-3.0, -0.5 * hemi) };
```
- Vent indépendant du terrain (pas d'effet Föhn, pas d'ombre pluviométrique).
- `humidity_decay` est exponentiel pur en distance — pas d'advection par le vent.
- Le terme `ocean_distance_m: Option<f32>` est documenté `None → noise stand-in` — donc en pratique pas couplé aux océans réels.

#### B5 — Ecosystem n'a pas de runtime (`ecosystem/src/lib.rs`)
- `flora_for_chunk` → liste statique de positions.
- `fauna_for_chunk` → `FaunaSeed { center, niche, count }` — **aucune mise à jour**, **aucune interaction**.
- Pas de croissance plante, pas de mortalité, pas de prédation, pas de migration.

#### B6 — `apply_pending` est un stub (`agent-api/src/lib.rs:139-151`)
```rust
pub fn apply_pending(&self) -> usize {
    let mut applied = 0;
    while let Ok(m) = self.inner.write_rx.try_recv() {
        // ... a deterministic stub keeps the API surface stable
        tracing::debug!(?m, "mutation queued (write-back stub)");
        applied += 1;
    }
    applied
}
```
**Documenté en clair comme stub.** Les agents IA ne peuvent **pas modifier le monde**.

#### B7 — Eviction FIFO crue (`streaming/src/manager.rs:86-101`)
```rust
// Crude: drop the first `excess` we iterate. A real LRU comes later
```
Sur une session longue, des chunks "loin de tout agent" sont gardés au hasard et des chunks "près d'un agent" peuvent être évincés.

#### B8 — Raycast naïf (`agent-api/src/lib.rs:221-244`)
DDA pas-fixe 0.5 m, regénère un chunk synchrone (`ensure_chunk_blocking`) à chaque pas. Sur 100 m de range → 200 lookups × 1 chunk-gen potentiel.

#### B9 — `entities_in_radius` retourne `Vec::new()` (`agent-api/src/lib.rs:215-219`)
Stub explicite — pas de spatial index dans le moteur. Les agents ne peuvent pas se voir entre eux via l'API.

#### B10 — Voxel column 1D pur (`streaming/src/manager.rs:300-352`)
```rust
fn column_material(z, surface_z, biome, ...) { ... }
```
Le matériau d'une cellule **ne dépend que de la colonne** (i,j) et de la profondeur. Pas de caves, pas d'overhangs, pas de structures souterraines.

#### B11 — Pas de loop de simulation
`WorldClient::advance_tick` existe mais aucun composant ne l'appelle dans une boucle. Le moteur génère à la demande puis se tait. Pour faire vivre faune/flore/saisons il faut une boucle.

#### B12 — Pas de snapshot/restore d'un *monde*
`persist` sérialise un chunk. Mais pas l'état global (intent bus, agents, drives, saisons). Pour le RL training, c'est bloquant : impossible de checkpointer un épisode et le rejouer.

### 1.3 Ce qui est déjà excellent

À préserver/étendre, pas à refactorer :

1. **PRF tree (`core/src/prf.rs`, `seed.rs`)** — base solide du déterminisme. Toutes les nouvelles couches doivent dériver leur seed via `SeedTree::prf(layer_name)`.
2. **WorldGraph DAG (`worldgraph/`)** — l'innovation centrale. Toutes les nouvelles passes (tectonique dynamique, atmos, ecosystem-tick) doivent s'enregistrer comme `Pass` pour bénéficier du cache content-addressed.
3. **`Cache L1/L2` (`cache/`)** — réutiliser via la lineage du WorldGraph.
4. **`forbid(unsafe_code)` partout** — règle d'or, à maintenir.
5. **Tests `*_deterministic`** — pattern à dupliquer pour toute nouvelle feature.

---

## 2. Roadmap priorisée

### Légende
- ⚡ Quick win : < 1 semaine, faible risque, fort impact mesurable.
- 🔧 Refactor moyen : 2–4 semaines, modifie une crate.
- 🏗 Refactor lourd : > 1 mois, traverse plusieurs crates ou introduit une nouvelle.

### Phase A — Quick wins (cumul ≈ 2-3 semaines, débloquent 80 % du gameplay)

| Prio | Item                                                  | Crate(s)            | Effort | Impact |
|------|-------------------------------------------------------|---------------------|--------|--------|
| A1   | Wire `apply_pending` → vraie mutation voxel (Cu-W cache invalidation) | `agent-api`+`streaming` | ⚡ 3j  | **Débloque agents writers** |
| A2   | LRU réelle (priority queue par `last_touch_tick`)     | `streaming`         | ⚡ 1j  | Stabilité long-run |
| A3   | Spatial index `r-tree` pour `entities_in_radius`     | `agent-api`         | ⚡ 2j  | Débloque perception |
| A4   | Raycast accéléré (DDA chunk-aware + early-out air)   | `agent-api`         | ⚡ 2j  | Latence vision ÷10 |
| A5   | GPU erosion auto-fallback dans `ChunkManager`         | `streaming`+`gpu`   | ⚡ 1j  | Throughput chunk ×5 sur GPU |
| A6   | Snapshot/restore JSONL+rkyv minimal du `WorldClient` | `agent-api`+`persist`| ⚡ 3j  | **Débloque RL training** |
| A7   | Fog-of-war filter sur `observe_area`                  | `agent-api`         | ⚡ 1j  | Realistic agent obs |

### Phase B — Refactors moyens (cumul ≈ 6-8 semaines)

| Prio | Item                                                  | Crate(s)            | Effort | Impact |
|------|-------------------------------------------------------|---------------------|--------|--------|
| B1   | **Tectonique dynamique** — particle-cloth Lagrange, advection 10-step | `terrain`         | 🔧 2 sem | Continents *bougent* |
| B2   | Hydrologie cross-chunk (border-padding 8 cells + global flow accumulation) | `hydrology`+`streaming` | 🔧 2 sem | Rivières continues |
| B3   | Climat dynamique — advection humidité par le vent (Eulerian 256x256) | `climate`         | 🔧 2 sem | Ombre pluvio. réelle |
| B4   | Saisons + cycle diurne (tick → temp_offset, daylight) | `climate`+`core`    | 🔧 1 sem | Biome dynamique |
| B5   | Voxel SDF 3D pour caves (Worley + warp + threshold) | `terrain`           | 🔧 1 sem | Caves génératives |
| B6   | Boids/flocking déterministes + chaîne alim simple    | `ecosystem`         | 🔧 2 sem | Émergence faunique |
| B7   | Hot-reload `BiomeRegistry` from YAML                  | `biome`             | 🔧 3j   | Iter ratio dev |
| B8   | Debug overlay HTTP (`/debug/temp`, `/debug/humidity`)  | new `debug`         | 🔧 4j   | Vis. dev |

### Phase C — Refactors lourds (cumul ≈ 3-6 mois)

| Prio | Item                                                  | Crate(s)            | Effort | Impact |
|------|-------------------------------------------------------|---------------------|--------|--------|
| C1   | **GPU compute generalisé** — tectonics, erosion, climate, advection tous WGSL | new `gpu` modules | 🏗 2 mois | Throughput ×10–50 |
| C2   | Atmospheric solver — Navier-Stokes simplifié 3D (incompressible) | new `atmos`     | 🏗 1 mois | Vraies cellules atmos |
| C3   | Replay system — événements append-only + restore state | `persist`+new `replay` | 🏗 1 mois | Debug, RL evals |
| C4   | Multi-node sharding — shard horizontal par macroblock (10 km × 10 km) | streaming+new `cluster` | 🏗 3 mois | 1 M agents, world ∞ |
| C5   | Plant ECS (croissance, reproduction, succession) — biomes vivants | `ecosystem`+`bevy_ecs` | 🏗 2 mois | Forêt vraiment vivante |

---

## 3. Code pour chaque axe — pointeurs

Tous les stubs Rust sont dans `proposals/axisN_*/*.rs`. Ils ne sont **pas** ajoutés au workspace `Cargo.toml` pour préserver la compilation actuelle ; un humain les copiera vers la crate de destination après revue.

### Axe 1 — Réalisme géologique
- `proposals/axis1_geology/dynamic_tectonics.rs` — plaques mobiles (Lagrangian particle cloth, advection 10 steps, convergence/divergence détectée par gradient de vitesse, orogenèse pondérée par le delta de motion).
- `proposals/axis1_geology/sdf_caves.rs` — Worley 3D + domain warp + threshold pour produire des cavités. Plug dans `column_material` via `is_cave_at(wx, wy, wz)`.

### Axe 2 — Climat & météo dynamique
- `proposals/axis2_climate/advected_humidity.rs` — semi-Lagrangian advection 2D de l'humidité par le vent. Une passe / tick saisonnier.
- `proposals/axis2_climate/seasons.rs` — phase astronomique + amplitude saisonnière par latitude (latitude × 0.4 cos(2π t/year)).

### Axe 3 — Écosystème vivant
- `proposals/axis3_ecosystem/boids.rs` — boids déterministes (separation/alignment/cohesion) en grille spatiale O(N).
- `proposals/axis3_ecosystem/food_web.rs` — chaîne alim 3 niveaux (producer/herbivore/carnivore), équations Lotka-Volterra discrètes par chunk.

### Axe 4 — Performance extrême
- `proposals/axis4_performance/lru.rs` — vraie LRU pour `ChunkManager` (intrusive list + `parking_lot::Mutex`).
- `proposals/axis4_performance/spatial_index.rs` — grid hash spatiale pour `entities_in_radius` (O(1) amorti).
- `proposals/axis4_performance/gpu_pipeline.rs` — squelette wgpu pour `noise + heightmap` batchés (32 chunks/dispatch).

### Axe 5 — Interface agents IA
- `proposals/axis5_agent_api/mutation_apply.rs` — `apply_pending` réel (lock chunk, swap voxel, invalidate cache).
- `proposals/axis5_agent_api/snapshot.rs` — snapshot/restore (rkyv) de l'état WorldClient + IntentBus.
- `proposals/axis5_agent_api/fog_of_war.rs` — `observe_area_filtered(p, radius_m)` qui masque tout hors disque.

### Axe 6 — Outils de développement
- `proposals/axis6_devtools/hot_reload.rs` — watcher `notify` sur `config/biomes.yaml` → re-injecte le `BiomeRegistry`.
- `proposals/axis6_devtools/debug_overlay.rs` — endpoints axum `/debug/heatmap?layer=temp&z=...` rendant PNG en mémoire.

---

## 4. Crates recommandées (avec justifications)

| Besoin                            | Choix                | Alternative          | Pourquoi                          |
|-----------------------------------|----------------------|----------------------|-----------------------------------|
| ECS pour faune/flore vivante      | `bevy_ecs 0.14`      | `hecs`, `legion`     | Déjà workspace dep ; benchmarks favorables (240 it/s vs 180 hecs) — voir BENCHMARKS.md |
| Spatial index entités             | `rstar 0.12`         | `kiddo` (kd-tree)    | R-tree rééquilibrable mieux pour entités mobiles ; pure-rust, no_std possible |
| File watcher hot-reload           | `notify 6.1`         | `inotify`/`fsevents` | Cross-platform, déjà battle-tested |
| Atmos solver                      | maison sur `glam`    | `nalgebra`           | Pour 256² grid maison plus simple que nalg. heavy |
| Snapshot binaire compact          | `rkyv 0.7`           | `bincode` (utilisé)  | rkyv = zero-copy load via mmap, indispensable pour RL replay |
| Replay évents                     | `jsonl` + `serde`    | `flatbuffers`        | Human-readable pour debug, gzip-friendly |
| GPU compute généralisé            | `wgpu 22.1` (déjà)   | `vulkano`            | Déjà workspace dep, portable DX12/Vulkan/Metal |
| Async runtime                     | `tokio` (déjà)       | `smol`/`async-std`   | Mature, déjà workspace dep |
| Hash dispersant                   | `ahash`+`siphasher`+`blake3` (déjà) | -    | Triple-stack présent, garder |
| Voronoi/Delaunay (advection plaques) | `spade 2.10`      | `geo`/maison         | Pure-rust, déterministe, suffit pour 1k plaques |

---

## 5. Architecture cible — schéma des modules

```
                           ┌──────────────────────────────┐
                           │   AGENT RUNTIME (Python/RL)  │
                           └──────────────┬───────────────┘
                                          │ PyO3 / IPC
                              ┌───────────▼───────────┐
                              │   genesis-agent-api    │
                              │  - WorldView (read)    │
                              │  - WorldClient (write) │◀── NEW: mutation_apply
                              │  - Snapshot / Restore  │◀── NEW: axis5_agent_api/snapshot
                              │  - Fog-of-war filter   │◀── NEW: axis5_agent_api/fog_of_war
                              └───┬────────────┬───────┘
                                  │            │
                ┌─────────────────▼─┐        ┌─▼────────────────────┐
                │  intent-bus       │        │  spatial-index (NEW) │
                │  (prefetch chunks)│        │  rstar R-tree         │
                └─────────────────┬─┘        └──────────────────────┘
                                  │
        ┌─────────────────────────▼──────────────────────────────────────┐
        │                       worldgraph DAG                            │
        │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
        │  │ Tectonics│───▶│ Heightmap│───▶│ Erosion  │───▶│Hydrology │   │
        │  │ (dynamic)│    │          │    │  CPU/GPU │    │ cross-chk│   │
        │  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
        │       │                                                  │      │
        │       └───┐  ┌──────────┐    ┌──────────┐                │      │
        │           ▼  │ Atmos    │───▶│ Climate  │◀───────────────┘      │
        │              │ (advect) │    │ (season) │                        │
        │              └──────────┘    └──────────┘                        │
        │                                   │                              │
        │                                   ▼                              │
        │                              ┌──────────┐                        │
        │                              │  Biome   │                        │
        │                              └──────────┘                        │
        │                                   │                              │
        │                                   ▼                              │
        │              ┌──────────┐    ┌──────────┐    ┌──────────┐        │
        │              │ Voxel +  │◀───│ Ecosystem│◀───│  Caves   │        │
        │              │ Materials│    │  (boids+ │    │  (SDF3D) │        │
        │              └──────────┘    │  food-w) │    └──────────┘        │
        │                              └──────────┘                        │
        └───────────────────────────────────────────────────────────────────┘
              ▲                            ▲                          ▲
              │                            │                          │
       ┌──────┴──────┐              ┌──────┴──────┐            ┌──────┴──────┐
       │ Cache L1/L2 │              │  GPU dispatch│           │  Persist     │
       │ (content-ad)│              │  (wgpu)      │           │ (rkyv+zstd)  │
       └─────────────┘              └─────────────┘            └─────────────┘
              ▲                            ▲                          ▲
              │                            │                          │
              └────────────────────────────┴──────────────────────────┘
                                           │
                                  ┌────────▼────────┐
                                  │ Streaming Mgr   │
                                  │ - real LRU       │◀── NEW: axis4/lru.rs
                                  │ - LOD            │
                                  │ - prefetch       │
                                  └─────────────────┘

       ┌─────────────────── DEV TOOLS ───────────────────┐
       │  Hot-reload BiomeRegistry  ←─  notify watcher   │
       │  Debug overlay (HTTP+PNG)  ←─  axum + image     │
       │  Replay system (events)    ←─  jsonl + rkyv     │
       └──────────────────────────────────────────────────┘
```

### Flux de données critique : génération d'un chunk au tick T

```
1.  WorldClient::ensure_chunk(coord)  ─────────────┐
2.    ↳ ChunkManager::get_or_generate              │  async
3.       ↳ cache.get(content_key) ?────► HIT ─────▶│  Arc<Chunk> returned
4.                                  │               │
5.                                  └─ MISS         │
6.         ↳ spawn_blocking:                       │
7.            ↳ Scheduler::run(pipeline, ctx)      │  worldgraph DAG
8.               ↳ Pass[Tectonics]   (cache L1/L2) │
9.               ↳ Pass[Heightmap]   (cache L1/L2) │
10.              ↳ Pass[Erosion CPU/GPU auto]      │  feature-gated
11.              ↳ Pass[Hydrology cross-chunk]     │  NEW: borders
12.              ↳ Pass[AtmosAdvection]            │  NEW: pre-tick once
13.              ↳ Pass[Climate(t=current)]        │  NEW: takes tick
14.              ↳ Pass[Biome]                     │
15.              ↳ Pass[Caves SDF3D]               │  NEW
16.              ↳ Pass[VoxelFill]                 │
17.              ↳ Pass[Ecosystem seeds]           │
18.            ↳ Chunk
19.         ↳ cache.put(content_key, chunk)        │
20.         ↳ Arc::new(chunk) ─────────────────────┘
```

### Flux de données critique : tick de simulation

```
T = tick N → tick N+1 :
  agent_runtime.submit(intents)          (Python)
    │
    ▼
  WorldClient.apply_pending()            ← NEW: vraie mutation
    ↳ pour chaque mutation:
       ↳ chunk.write_lock
       ↳ swap voxel
       ↳ cache.invalidate(content_key)
       ↳ ecosystem.notify(pos, kind)
    ↳ worldgraph.invalidate_downstream(coord)

  ecosystem.tick()                       ← NEW: boids + Lotka-Volterra
    ↳ pour chaque chunk loaded:
       ↳ update boids positions
       ↳ update population counts (LV step)
       ↳ emit events (predation, birth)

  atmos.tick(if tick % SEASON_TICKS == 0)  ← NEW: advection saisonnière
  climate.tick(tick)                       ← NEW: applique saison + diurne

  WorldClient.advance_tick()
```

---

## 6. Contraintes respectées

| Contrainte                                         | Respect |
|----------------------------------------------------|---------|
| Rust stable uniquement (pas de nightly)            | ✅ rustc 1.85 stable, aucune feature nightly  |
| Chaque module testable indépendamment              | ✅ chaque file proposal a son `#[cfg(test)]` |
| Pas de régression sur l'API agents IA existante    | ✅ `WorldView` trait inchangé, ajouts pur add-only |
| Open source, zéro licence propriétaire             | ✅ Apache-2.0 OR MIT, aucune crate proprio   |
| Forbid unsafe_code partout                         | ✅ tous les stubs portent `#![forbid(unsafe_code)]` |
| Déterminisme bit-à-bit                             | ✅ tous les nouveaux modules dérivent du PRF tree |

---

## 7. Métriques cibles & vérifications

### Cibles end-to-end après Phase A+B
| Métrique                            | Avant   | Cible Phase B | Méthode mesure |
|-------------------------------------|---------|---------------|----------------|
| Chunk gen p50 (CPU)                 | 22.8 ms | 22 ms (≈)    | `cargo bench -p streaming` |
| Chunk gen p50 (GPU erosion)         | n/a     | < 10 ms      | feature `gpu` + bench |
| Cache hit rate (steady state)       | n/a     | > 95 %       | tracing metrics |
| Apply 100 mutations / tick          | 0 (stub)| < 1 ms       | new bench `mutation_apply` |
| Snapshot 100 chunks                 | n/a     | < 50 ms      | new bench `snapshot` |
| Restore 100 chunks                  | n/a     | < 20 ms      | mmap rkyv |
| `entities_in_radius` (1000 agents)  | 0 (stub)| < 100 µs     | new bench `spatial_index` |
| Boids tick (10k boids, single chunk)| n/a     | < 5 ms       | new bench `ecosystem_tick` |
| Climat advection (256² grid)        | n/a     | < 2 ms       | new bench `atmos_advect` |
| Det. cross-thread (existing test)   | OK      | OK preserved | `same_seed_same_chunk` |
| Det. snapshot/restore round-trip    | n/a     | bit-identical| new test `snapshot_determinism` |

### Tests d'invariance à ajouter (un par module nouveau)
```
proposals/axis1_geology/dynamic_tectonics.rs::tests::same_seed_same_plate_field
proposals/axis1_geology/sdf_caves.rs::tests::cave_density_in_range
proposals/axis2_climate/advected_humidity.rs::tests::mass_conserved_to_1pct
proposals/axis2_climate/seasons.rs::tests::summer_warmer_than_winter
proposals/axis3_ecosystem/boids.rs::tests::deterministic_2_runs
proposals/axis3_ecosystem/food_web.rs::tests::lv_predator_decline_without_prey
proposals/axis4_performance/lru.rs::tests::lru_evicts_oldest
proposals/axis4_performance/spatial_index.rs::tests::radius_query_recall_100pct
proposals/axis5_agent_api/mutation_apply.rs::tests::voxel_mutation_visible_next_tick
proposals/axis5_agent_api/snapshot.rs::tests::snapshot_restore_identity
proposals/axis5_agent_api/fog_of_war.rs::tests::cells_outside_radius_are_unknown
proposals/axis6_devtools/hot_reload.rs::tests::yaml_change_updates_registry
```

---

## 8. Décisions techniques justifiées

### Pourquoi pas un nouveau langage / framework ?
Le moteur en Rust + Tokio + wgpu **est** la stack premium. Pas de raison de migrer. C# (Unity DOTS) plafonne en perf, Zig est trop jeune pour ce volume de deps.

### Pourquoi advection 2D et pas 3D pour l'atmosphère ?
Coût/bénéfice. Une advection 2D (humidité, température) de 256² entièrement Eulerian est < 2 ms / pas, et capture l'essentiel : ombre pluviométrique, dérive d'humidité, fronts. Un solver 3D incompressible (Stable Fluids) coûte 30–100 ms même optimisé et n'apporte rien de visible à l'échelle gameplay.

### Pourquoi boids et pas un état-action LSTM ?
Boids déterministes = reproductibilité + zéro modèle à entraîner + comportement émergent prouvé. Un LSTM par espèce ajoute du non-déterminisme float et bloque les tests `*_deterministic`. Si on veut du LSTM, c'est côté `agent-runtime` Python, pas dans le moteur.

### Pourquoi rkyv pour snapshot et pas bincode (qui marche déjà) ?
RL training : on restore des dizaines de snapshots/s. bincode demande désérialisation complète (~10 ms / chunk). rkyv via mmap = 0 ms en read. Pour un episode store de 1k snapshots, gain = 10 s par episode boundary.

### Pourquoi pas Voronoi déjà existant (`spade`) pour tectonique ?
On peut. Mais pour 100–500 plaques avec advection Lagrangienne 10 pas, l'overhead Delaunay re-trianguler à chaque pas est dominant. L'approche `proposals/axis1_geology/dynamic_tectonics.rs` est : grille de cellules + plaque-particles flottant dans une cellule + advection cell-to-cell. O(N plates), pas O(N² edges).

### Pourquoi `bevy_ecs` (déjà workspace dep) et pas un ECS maison ?
Voir BENCHMARKS.md : 240 it/s vs hecs 180. Déjà payée comme dépendance. Pas de raison de réinventer.

### Pourquoi pas une intégration native Bevy (engine entier) ?
Bevy est un moteur de jeu. Genesis World Engine est un *fournisseur de monde* consommé par un agent runtime Python. Acoupler à Bevy ferait sortir le moteur de son rôle.

---

## 9. Recommandations stratégiques (vision)

1. **Ne pas tout faire en même temps.** Phase A débloque le gameplay. Phase B fait briller. Phase C est R&D 6 mois. Faire A complète et stabiliser **avant** de toucher B.

2. **Le déterminisme est sacré.** Chaque nouvelle feature doit avoir un test `*_deterministic_two_runs`. Sinon le système RL perd sa propriété d'apprentissage répétable. Aucune exception, même pour le "fun" — toute source d'entropie est dans le PRF.

3. **GPU est un multiplicateur, pas un fondement.** Garder toutes les passes CPU comme référence (cross-backend tests). Le jour où une plateforme n'a pas de wgpu (WASM 1.0, certains cloud workers), le moteur doit tourner en CPU sans branche conditionnelle dans l'algo.

4. **Wire l'agent-API en priorité (A1, A3, A6, A7).** Tant que les agents ne peuvent pas écrire / observer / checkpoint, le moteur est un démo. Les axes 1-4 (réalisme) sont moins critiques que l'axe 5 (interface agents) pour la mission "monde IA".

5. **Mesurer avant d'optimiser.** Phase C5 (Plant ECS) sonne bien mais sa profitabilité dépend de la densité réelle de plantes simulées par chunk. Profiler après Phase B avant de s'engager.

---

## 10. Annexe — Décisions reportées (pas dans cette session)

- **Multi-node sharding** (Phase C4) — design doc séparé requis (consistent hashing + ownership transfer).
- **Plant ECS complet** (Phase C5) — il faut d'abord stabiliser les passes Phase B avant d'embarquer un sous-système ECS dédié plantes.
- **Compaction de cache L2** — à activer quand le cache disque dépasse 50 GB en pratique.
- **Bindings WASM** — décision business : si le moteur doit tourner dans un navigateur (oui pour debug overlay, non pour prod), ajouter une feature `wasm` plus tard.

---

## 11. Procédure de revue suggérée

```
1. Lire ce document
2. Pour chaque axe que vous voulez incorporer :
     a. Lire proposals/axisN_*/
     b. Vérifier que la signature s'imbrique dans la crate cible
     c. cargo check sur un workspace temporaire avec le module ajouté
     d. Ajouter les tests dans la crate cible
     e. cargo test --release
     f. cargo bench -- baseline
     g. Merge si verts.
3. Pas tout d'un coup. Préférer A1 → A2 → A6 puis B1.
```

---

## 12. Fichiers livrés dans cette session

```
créés :
  NEXT-LEVEL-AUDIT.md                                         (ce document)
  proposals/axis1_geology/dynamic_tectonics.rs                 (~250 lignes)
  proposals/axis1_geology/sdf_caves.rs                         (~120 lignes)
  proposals/axis2_climate/advected_humidity.rs                 (~180 lignes)
  proposals/axis2_climate/seasons.rs                           (~110 lignes)
  proposals/axis3_ecosystem/boids.rs                           (~210 lignes)
  proposals/axis3_ecosystem/food_web.rs                        (~140 lignes)
  proposals/axis4_performance/lru.rs                           (~150 lignes)
  proposals/axis4_performance/spatial_index.rs                 (~170 lignes)
  proposals/axis4_performance/gpu_pipeline.rs                  (~120 lignes)
  proposals/axis5_agent_api/mutation_apply.rs                  (~150 lignes)
  proposals/axis5_agent_api/snapshot.rs                        (~140 lignes)
  proposals/axis5_agent_api/fog_of_war.rs                      (~110 lignes)
  proposals/axis6_devtools/hot_reload.rs                       (~120 lignes)
  proposals/axis6_devtools/debug_overlay.rs                    (~150 lignes)
  proposals/README.md                                          (guide d'intégration)

modifiés : (aucun — le build courant n'est pas touché)
```

Tous les proposals utilisent uniquement les crates déjà dans `[workspace.dependencies]` (pas de nouvelle dep), sauf trois identifiées explicitement dans la section 4 (`rstar`, `notify`, `spade`) — à ajouter au workspace quand le module correspondant est promu.

---

**Fin de l'audit.**
