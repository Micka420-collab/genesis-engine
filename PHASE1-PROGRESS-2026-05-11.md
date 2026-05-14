# Genesis Engine — Phase 1 Progress Report
**Run du 11 mai 2026 (tâche planifiée)**

## TL;DR

Cette session autonome a converti les 5 crates Rust marquées « à implémenter »
dans `INDEX.md` en **scaffolding compilable** suivant les contrats déjà fixés
(determinisme via PRF, ECS Bevy, gRPC `sim.proto`). On passe de **1 crate
fonctionnelle (`ge-core`) à 6 crates branchées**, avec une boucle de tick
embryonnaire exposée via HTTP.

Aucune dépendance externe ajoutée hors workspace existant — tout est aligné sur
les versions déclarées dans `scaffolding/Cargo.toml`.

---

## Ce qui a été ajouté

### ge-world (génération de monde déterministe)

| Module        | Contenu                                                                 |
|---------------|-------------------------------------------------------------------------|
| `noise.rs`    | Value noise + fBm, indexé par `prf_rng` — pas de RNG global             |
| `biome.rs`    | Classifieur Whittaker 12 biomes, NPP + habitabilité                     |
| `terrain.rs`  | Échantillonnage `(elev, temp, precip)` continu sur le monde            |
| `chunk.rs`    | Chunk 64×64 voxels, génération pure + BLAKE3 content root              |
| `resource.rs` | Distribution stone/wood/metal corrélée au biome                         |
| `climate.rs`  | Saisons sinusoïdales + cycle jour/nuit                                  |
| `streaming.rs`| Cache LRU-par-touch, area_around, GC périodique                         |

**Garanties** : `generate_chunk(seed, coord)` est pur. Deux nœuds différents
produisent un `content_root` identique pour les mêmes inputs. Tests unitaires
de déterminisme inclus.

### ge-agents (composants ECS)

| Module           | Composants                                                       |
|------------------|------------------------------------------------------------------|
| `identity.rs`    | `Identity`, `Deceased`, `DeathCause`                             |
| `body.rs`        | `Position`, `Velocity`, `Heading`, `Metabolism` (humain adulte)  |
| `drives.rs`      | `Drives` × 8 axes (faim/soif/sommeil/fatigue/thermal/...)       |
| `health.rs`      | `Health` (vitalité, blessures, charge pathogène)                |
| `inventory.rs`   | `Inventory` typé par `ItemKind`, capacité kg                    |
| `personality.rs` | Big Five + ambition/risk_tolerance/aggression, **PRF-sampled**  |
| `spawn.rs`       | `HumanAgentBundle::founder`, `spawn_founders`                   |
| `systems.rs`     | `tick_drives`, `apply_velocity`, `check_mortality`               |

**Calibration biologique Phase 1** :
- Soif critique en **3 jours** simulés sans boire
- Faim critique en **14 jours** sans manger
- 1 tick = 1 seconde simulée (cadence Standard ×10 sur l'horloge réelle)

### ge-cognition (policy R0)

| Module        | Contenu                                                              |
|---------------|----------------------------------------------------------------------|
| `action.rs`   | `ActionId` (8 actions), `ActionArgs`, `Decision`                     |
| `perception.rs` | `Observation`, `PerceivedTarget`, `TargetKind`                     |
| `intent.rs`   | `Intent` (composant ECS) — persistance multi-tick                    |
| `policy_r0.rs`| Décision utilitariste : critique > dominant > idle                   |

**Tests inclus** : drive critique avec/sans cible, agent calme idle.

### ge-ann (Annaliste)

| Module         | Contenu                                                             |
|----------------|---------------------------------------------------------------------|
| `event.rs`     | `Event` + 9 `EventKind` alignés sur `sim.proto`                     |
| `detectors.rs` | Trait `Detector`, `VitalDetector` (births/deaths)                  |
| `lineage.rs`   | Graphe parent↔enfant + comptage transitif des descendants          |
| `journal.rs`   | Trait `Sink` + `JsonlSink` append-only                              |

### ge-api (binaire HTTP)

| Module        | Contenu                                                              |
|---------------|----------------------------------------------------------------------|
| `main.rs`     | CLI clap + Tokio + Axum + spawn sim_loop                             |
| `routes.rs`   | `/healthz`, `/readyz`, `/api/v1/sim/state`, `/api/v1/sim/step`       |
| `state.rs`    | `AppState`, `SimSnapshot`, parseur YAML minimal embarqué            |
| `sim_loop.rs` | Boucle tick à 10 Hz (100 ms cible), GC chunks tous les 1000 ticks    |

---

## Vérification

```bash
# Depuis scaffolding/
cargo check --workspace          # types & dépendances
cargo test  -p ge-core           # déterminisme PRF
cargo test  -p ge-world          # chunk hash stable
cargo test  -p ge-cognition      # policy R0
cargo run   -p ge-api -- --bind 127.0.0.1:8080
curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8080/api/v1/sim/state
```

---

## Conformité aux ADR existants

| ADR  | Décision                                  | Statut                                |
|------|-------------------------------------------|---------------------------------------|
| 0001 | Cœur Rust (pas Unity/Unreal)              | ✅ tout est Rust 2024                 |
| 0002 | Pas de LLM frontier comme cerveau         | ✅ policy R0 = règle pure, déterministe |
| 0003 | PQC-first (dilithium/ed25519)             | ⏳ Phase 0 — pas encore branché ici  |
| 0004 | CockroachDB > Postgres                    | ⏳ pas encore intégré (Phase 1.5)    |

---

## Choix faits sans demande à l'utilisateur (mode autonome)

1. **Parseur YAML minimal embarqué** dans `ge-api/state.rs` plutôt que d'ajouter
   `serde_yaml` au workspace. Ça nous donne `simulation.seed` sans toucher au
   `Cargo.toml`. À remplacer par `serde_yaml` en Phase 1.5.
2. **`uuid::Uuid::new_v4()`** pour les fondateurs : non-déterministe, **à
   remplacer** par UUIDv5 dérivé du seed dès Phase 1.5. Marqué TODO implicite
   dans `spawn.rs`.
3. **Climat sinusoïdal pur** (pas d'équations primitives). Suffisant pour faire
   varier `temp_c` dans la perception agent.
4. **Pas de gRPC server** dans `ge-api` ce tour-ci — seulement HTTP REST. Le
   `.proto` est déjà en place, on branche `tonic` en Phase 1.5 quand on
   ajoutera `prost-build` au build.

---

## Reste à faire pour fermer Phase 1 (selon `roadmap/mvp-roadmap.md`)

- [ ] Brancher Bevy ECS World dans `sim_loop` (actuellement la boucle ne crée
  pas d'agents — elle ne fait que stream les chunks)
- [ ] Système `apply_action` qui consomme les `Decision` de R0 et mute les
  components
- [ ] Système `perceive` qui peuple `Observation` depuis le streamer + voisins
- [ ] Brancher `JsonlSink` au tick delta pour enregistrer les events
- [ ] OpenTelemetry tracing (le span se contente d'info!())
- [ ] **Determinism check** : 2 runs identiques → même hash final (le
  `runbook-determinism-drill.md` existe déjà)
- [ ] Observer 3D (Next.js) — pas dans ce repo, dépendance front

**Critère de succès Phase 1** rappelé :
> 10 agents survivent 24 h simulées sans intervention humaine,
> 0 crash sur 100 simulations consécutives,
> Determinism check vert (replay bit-à-bit).

---

## Fichiers ajoutés (récapitulatif)

```
scaffolding/crates/ge-world/Cargo.toml
scaffolding/crates/ge-world/src/{lib,noise,biome,terrain,chunk,resource,climate,streaming}.rs

scaffolding/crates/ge-agents/Cargo.toml
scaffolding/crates/ge-agents/src/{lib,identity,body,drives,health,inventory,personality,spawn,systems}.rs

scaffolding/crates/ge-cognition/Cargo.toml
scaffolding/crates/ge-cognition/src/{lib,action,perception,intent,policy_r0}.rs

scaffolding/crates/ge-ann/Cargo.toml
scaffolding/crates/ge-ann/src/{lib,event,detectors,lineage,journal}.rs

scaffolding/crates/ge-api/Cargo.toml
scaffolding/crates/ge-api/src/{main,routes,state,sim_loop}.rs

PHASE1-PROGRESS-2026-05-11.md   (ce fichier)
```

**~1 800 lignes de Rust ajoutées**, 6 modules par crate en moyenne,
3 fichiers de tests embarqués, 0 unsafe.
