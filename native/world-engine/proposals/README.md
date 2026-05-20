# proposals/ — code stubs pour la roadmap Next-Level

Ce dossier contient des **modules Rust isolés**, un par axe d'amélioration de
`NEXT-LEVEL-AUDIT.md`. Ils ne sont **pas** ajoutés au workspace Cargo : le
build actuel reste vert. Chaque fichier est conçu pour être copié-collé dans
la crate cible après revue.

## Plan d'intégration suggéré

| Fichier proposal                              | Crate cible           | Action                            |
|-----------------------------------------------|------------------------|-----------------------------------|
| `axis1_geology/dynamic_tectonics.rs`          | `crates/terrain/src/` | nouveau module `tectonics_dyn`    |
| `axis1_geology/sdf_caves.rs`                  | `crates/terrain/src/` | nouveau module `caves`            |
| `axis2_climate/advected_humidity.rs`          | `crates/climate/src/` | nouveau module `advection`        |
| `axis2_climate/seasons.rs`                    | `crates/climate/src/` | nouveau module `season`           |
| `axis3_ecosystem/boids.rs`                    | `crates/ecosystem/src/` | nouveau module `boids`         |
| `axis3_ecosystem/food_web.rs`                 | `crates/ecosystem/src/` | nouveau module `food_web`      |
| `axis4_performance/lru.rs`                    | `crates/streaming/src/` | nouveau module `lru_cache`     |
| `axis4_performance/spatial_index.rs`          | `crates/agent-api/src/` | nouveau module `spatial`       |
| `axis4_performance/gpu_pipeline.rs`           | `crates/gpu/src/`     | extension du module existant       |
| `axis5_agent_api/mutation_apply.rs`           | `crates/agent-api/src/` | remplace le stub `apply_pending` |
| `axis5_agent_api/snapshot.rs`                 | `crates/agent-api/src/` | nouveau module `snapshot`      |
| `axis5_agent_api/fog_of_war.rs`               | `crates/agent-api/src/` | nouveau module `fog`           |
| `axis6_devtools/hot_reload.rs`                | new crate `devtools`  | crate à créer                     |
| `axis6_devtools/debug_overlay.rs`             | new crate `devtools`  | crate à créer                     |

## Dépendances additionnelles à enregistrer dans `Cargo.toml`

Si on intègre :

- `spatial_index.rs` → `rstar = "0.12"`
- `hot_reload.rs` → `notify = "6.1"`, `serde_yaml = "0.9"`
- `debug_overlay.rs` → `image = "0.25"`, `axum = "0.7"`
- `dynamic_tectonics.rs` → utilise `spade = "2.10"` (optionnel ; le stub fait sans)

## Règles communes à tous les proposals

- `#![forbid(unsafe_code)]`
- Aucune `Instant::now()`, aucune source d'entropie hors `genesis_core::Prf`
- Test `*_deterministic_two_runs` quand le module produit un état
- Pas de panic dans le chemin nominal — `Result<_, ThisModuleError>`
- Documentation `//!` au module et `///` sur chaque item public
