# Stack technique — état de l'art 2026

> Cette stack est sélectionnée selon trois critères : **performance**, **maturité production**, **trajectoire long-terme**.
> On évite le « shiny new thing » sans communauté ni gouvernance.

## Frontend / Observer Platform

| Couche | Choix | Justification |
|---|---|---|
| Framework UI | **Next.js 15+ (App Router, RSC)** | SSR/RSC, edge-ready |
| Langage | **TypeScript 5.5+** strict | sécurité de type |
| Rendu 3D web | **Three.js r170+ + WebGPU** (fallback WebGL2) | WebGPU généralisé en 2026 |
| Alternatif lourd | **Bevy WebAssembly** (Rust) | pour l'observer haute densité |
| Charts | **Visx + D3 v8** | analytics dashboards |
| State | **Zustand + TanStack Query** | léger, prévisible |
| Realtime | **WebRTC + Protobuf** (delta-state) | low-latency streaming |
| Auth | **WebAuthn / Passkeys** + OIDC | sans mot de passe |

## Moteur de simulation (cœur)

| Couche | Choix | Justification |
|---|---|---|
| Langage cœur | **Rust 1.85+** (édition 2024) | mémoire safe, perf native, écosystème mature |
| ECS | **Bevy ECS** (utilisé hors Bevy lui-même) | data-oriented, rapide |
| Physique | **Jolt Physics** (via wrapper Rust) | déterministe, scalable |
| Math | **glam, nalgebra, ndarray** | SIMD, GPU-friendly |
| Concurrence | **Tokio + Rayon** | I/O async + parallèle CPU |
| Sérialisation | **rkyv (zero-copy)** + Apache Arrow + Protobuf | snapshot + interop |
| Scripting modules | **Lua via mlua** ou **WASM (wasmtime)** | extensibilité utilisateurs |

### Pourquoi pas Unity / Unreal pour le cœur

Unity/Unreal sont excellents pour le **rendu** mais leurs runtimes ne sont pas conçus pour des simulations distribuées 10⁶ agents avec déterminisme strict. On les garde **uniquement pour le rendu high-fidelity** côté client immersif optionnel (pas dans la boucle de simulation).

## IA / cognition

| Couche | Choix 2026 | Justification |
|---|---|---|
| Inference serving | **NVIDIA Triton 25+** + **vLLM** + **TensorRT-LLM** | dynamic batching, MIG |
| Encodeur perception | **DINOv3-Small** ou **SigLIP-2** | self-supervised vision compact |
| World model | **DreamerV3** + composante **Genie 3** (style world-model interactif) | rollouts imaginés |
| Politique | **Transformer 50–200M params** custom (PPO/IMPALA) | rapide, batchable |
| Theory of Mind | **Bayesian Inverse Planning** (Pyro / NumPyro) | léger, interprétable |
| LLM méta-langage (post-émergence) | **Mistral / Llama small (1–3B)** local fine-tuné | apparaît tard dans la simu |
| Vector DB | **Qdrant** (per-agent collections) ou **pgvector 0.7+** | mémoire épisodique |
| RL framework | **CleanRL + RL4LMs** | reproductibilité |
| Orchestration multi-agent | **maison (Rust)** | agents LLM-orchestrators (LangGraph, AutoGen) ne scalent pas à 10⁶ |

### Note sur les « world models » 2025–2026

Les modèles génératifs interactifs type **Genie 2/3, V-JEPA-2, DeepMind SIMA** sont utilisés **comme sous-modules du modèle du monde** des agents (pour imaginer des futurs courts). Ils ne sont **pas** la couche de rendu graphique du monde Genesis (le monde réel est voxel + heightmap, pas neural).

## Backend services

| Service | Choix | Justification |
|---|---|---|
| API Gateway | **Envoy + gRPC** + REST/GraphQL bridges | perf + polyglotte |
| Microservices | **Rust (axum, tonic)** + Python (FastAPI) pour ML | Rust pour la donnée chaude, Python pour ML |
| Message bus | **Redpanda** (Kafka-compatible) | latence < 10 ms, pas de Zookeeper |
| Workflow | **Temporal.io** | sagas, retries, signals |
| Search | **MeiliSearch** ou **Elastic 9** | recherche dans les chroniques |

## Bases de données

| Usage | Choix | Justification |
|---|---|---|
| OLTP état persistant | **CockroachDB** | distribué, multi-region, fort sur transactions |
| Transactions économiques massives | **TigerBeetle** | 1M tx/s, double-entry natif |
| Cache + state warm | **Redis 7+ Cluster** ou **DragonflyDB** | hot data |
| Vector | **Qdrant** | per-agent, scalable |
| Time-series (telemetry) | **TimescaleDB** ou **InfluxDB 3.0** | analytics |
| Graph (relations sociales) | **Neo4j** ou **Memgraph** | requêtes de parenté/influence |
| Object store | **MinIO** (S3-compatible) | snapshots, chunks froids |
| Data lake analytics | **Apache Iceberg + Trino** | analytics historiques |

## Infrastructure

| Couche | Choix | Justification |
|---|---|---|
| Orchestration | **Kubernetes 1.32+** | standard de fait |
| GPU scheduling | **NVIDIA GPU Operator** + **Karpenter** | autoscaling |
| GPU réelles | **NVIDIA H200 / B200 / GB200** | inference dense |
| Service mesh | **Istio Ambient** (sidecar-less) | mTLS partout, faible overhead |
| IaC | **Terraform + Crossplane** | déclaratif, multi-cloud |
| CI/CD | **GitHub Actions + Argo CD** | GitOps |
| Secrets | **HashiCorp Vault** + **External Secrets Operator** | rotation auto |
| Multi-cloud | **AWS + GCP + bare metal (CoreWeave)** | résilience, GPU-arbitrage |

## Observabilité

| Couche | Choix |
|---|---|
| Traces | **OpenTelemetry → Tempo (Grafana)** |
| Métriques | **Prometheus + Mimir** |
| Logs | **Loki** + **Vector** ingest |
| Profiling continu | **Pyroscope / Parca** |
| eBPF | **Cilium + Pixie** | network + perf insights |
| SIEM | **Wazuh** ou **CrowdStrike Falcon** |

## DevX

| Domaine | Choix |
|---|---|
| Mono-repo | **Bazel 7** ou **Nx** | builds incrémentaux Rust+TS+Python |
| Lint / format | **ruff (Py)**, **biome (TS)**, **clippy (Rust)** |
| Tests | **cargo test, pytest, vitest, playwright** |
| Pre-commit | **lefthook** |
| Doc | **mkdocs-material + mermaid** |
| Spec REST | **OpenAPI 3.1** |
| Spec gRPC | **buf.build** |
| Schemas | **JSON Schema 2020-12 + Zod (TS) + pydantic v2 (Py)** |

## Hard requirements

- **Pas de framework propriétaire enfermant.**
- **Pas de SaaS sur le chemin critique de la simulation.** (Les SaaS restent acceptables pour CI, monitoring, analytics tiers.)
- **Tout déployable on-premise** pour les usages scientifiques sensibles.
- **Reproductibilité** : tout binaire de simulation doit avoir un hash SBOM (Software Bill of Materials, format SPDX 3 ou CycloneDX).
