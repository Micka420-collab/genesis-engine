# Genesis Engine — Technology Stack (May 2026)

> Selection criteria: **most recent + most mature** at May 2026, **open-source preferred**, **modular substitution** without rewrite, **production-ready** at scale.

## Layer 1 — Frontend & Presentation (Web)

| Concern | Choice | Why | Alternative |
| --- | --- | --- | --- |
| Framework | **Next.js 16** | RSC, Server Actions, Partial Prerendering, mature App Router | Remix v3, SolidStart |
| UI library | **React 19** | Concurrent rendering, Actions, Server Components | Vue 3.5, Svelte 5 |
| Language | **TypeScript 5.7** | Type safety mandatory at this scale | — |
| Styling | **Tailwind 4** + **shadcn/ui** + **Radix** | Constraint-based, accessible, headless | Panda CSS |
| 3D engine | **Three.js r170** + **react-three-fiber** + **drei** | Mature, huge ecosystem, integrates with React | Babylon.js, PlayCanvas |
| GPU API | **WebGPU** (primary) / **WebGL2** (fallback) | Modern compute support, ~50% perf gain over WebGL2 | — |
| State | **Zustand** + **TanStack Query v6** + **Valtio** | Performant, ergonomic, predictable | Redux Toolkit, Jotai |
| XR | **WebXR** + **OpenXR bridge** | Standard, multi-vendor | — |
| Mobile observe | **React Native 0.78** + **Expo 53** | Code share with web, native perf | Flutter 4 |

## Layer 2 — Native Clients & Simulation Engine

| Concern | Choice | Why | Alternative |
| --- | --- | --- | --- |
| AAA client | **Unreal Engine 5.6** | Nanite, Lumen, World Partition, State Tree, Verse | Unity HDRP |
| ECS client/server | **Unity 6.1 LTS** + Entities 1.4 (DOTS) + Burst + Jobs | Mature ECS, Netcode for Entities, mass-agent perf | — |
| Pure-Rust ECS | **Bevy 0.16** | Fast, safe, headless servers | Specs, Hecs |
| Physics | **Jolt Physics** | Used in Horizon Forbidden West, blazing fast | PhysX 5 (Unity), Rapier |
| Backend physics | **Rapier 0.20** (Rust) | Pure-Rust, deterministic | Bullet |
| Audio | **Wwise** (UE) / **FMOD** (cross) / **Web Audio API** | Standard pipeline | OpenAL |
| Spatial audio | **Resonance Audio** | Open-source, HRTF | Steam Audio |

## Layer 3 — Backend & Services

| Concern | Choice | Why | Alternative |
| --- | --- | --- | --- |
| Hot-path lang | **Rust 1.84** | Memory safety + perf for the substrate | C++ 23 |
| Network lang | **Go 1.23** | Ergonomic for gRPC services, simple ops | — |
| ML/glue lang | **Python 3.13** | Free-threaded mode + native asyncio | — |
| Rust web framework | **Axum** | Type-safe, Tower middleware, async | Actix-Web |
| Python framework | **FastAPI** | Async, OpenAPI auto-gen | Litestar |
| Go framework | **Fiber** | Fast, Express-like | Echo |
| RPC | **gRPC + Protobuf** | Bi-streaming, schema-first | Cap'n Proto |
| Rust gRPC | **Tonic** | First-class Rust gRPC | — |
| Messaging (real-time) | **NATS JetStream** (cluster) | Low latency, lightweight, KV/stream/object | — |
| Messaging (durable) | **Apache Kafka 3.9** | Industry standard for event sourcing | Redpanda |
| Orchestration | **Kubernetes 1.32** | De facto standard | Nomad |
| Autoscaling | **KEDA** + **Karpenter** | Event-driven + cost-optimized nodes | Cluster Autoscaler |
| Service mesh | **Linkerd 2.16** | Lightweight, mTLS auto, Rust-based | Istio Ambient |

## Layer 4 — Data & Storage

| Concern | Choice | Why | Alternative |
| --- | --- | --- | --- |
| OLTP relational | **PostgreSQL 17** | Mature, extensible | MySQL 8.4 |
| OLTP distributed | **CockroachDB 24.3** | Multi-region strong consistency | YugabyteDB |
| Cache / fast KV | **Redis 7.4** Cluster | Battle-tested | Valkey 8 (fork) |
| Vector DB | **Qdrant 1.13** | Performant, Rust-native, BM42 hybrid | Weaviate, Milvus |
| OLAP | **ClickHouse 25.2** | Columnar, blazing fast aggregation | StarRocks, DuckDB |
| Object storage | **Cloudflare R2** | Zero egress, S3-compatible | Backblaze B2, MinIO |
| Time-series | **TimescaleDB** | Postgres extension | InfluxDB 3 |
| Graph | **Neo4j 6** | Mature, Cypher | Memgraph |
| Search | **Meilisearch 1.10** | Lightweight, typo-tolerant | Elasticsearch 9 |

## Layer 5 — AI & Models

| Concern | Choice | Why | Alternative |
| --- | --- | --- | --- |
| LLM heavy | **Claude 4.6 Opus / Sonnet** (Anthropic API) | Best reasoning, large context | GPT-5, Gemini 3 Ultra |
| LLM agent fast | **Llama 4 8B / Mistral Small 3 / Qwen 3 7B** | Auto-hostable, sub-100ms latency on H200 | Phi-4 |
| LLM inference | **vLLM 0.7** or **TGI 3.0** | Best throughput, prefix caching | TensorRT-LLM |
| Fine-tuning | **Unsloth + Axolotl** | Efficient LoRA/QLoRA | — |
| World models | **NVIDIA Cosmos-Predict-1** + **World Labs Marble** + **DeepMind Genie 3** | Environmental coherence | V-JEPA-2 |
| RL multi-agent | **PettingZoo + Tianshou** | PPO/IPPO/MAPPO recipes | RLlib |
| Embeddings | **voyage-3-large** or **BGE-M3** | Multilingual, 1024-d | E5-Mistral |
| ASR (speech-to-text) | **Whisper Large v3** | Multilingual, robust | NVIDIA Parakeet |
| TTS | **XTTS v2** / **ElevenLabs** | Voice cloning, multilingual | OpenAI TTS |
| Lipsync | **NVIDIA Audio2Face 3D** | Real-time, blendshape output | MetaHuman Animator |
| Vision | **DINOv3** + **SAM 3** | Best self-supervised + segmentation | Florence-2 |
| Avatar reconstruction | **InstantMesh** + **Hunyuan3D-2** + **Mixamo / RigNet** | Fast, multi-style | TripoSR |

## Layer 6 — Observability

| Concern | Choice | Why | Alternative |
| --- | --- | --- | --- |
| Tracing | **OpenTelemetry** + **Tempo** | Open standard | Jaeger |
| Metrics | **Prometheus** + **Mimir** | Horizontally scalable | VictoriaMetrics |
| Logs | **Loki** + **Vector** | Cheap, label-based | OpenSearch |
| Dashboards | **Grafana 11** | Standard | — |
| APM (optional) | **Sentry** / **Datadog** | Error tracking, RUM | — |

## Layer 7 — Security & Identity

| Concern | Choice | Why | Alternative |
| --- | --- | --- | --- |
| Identity | **OIDC + WebAuthn / Passkeys** | Passwordless, FIDO2 L2 | SAML |
| Secrets | **HashiCorp Vault** | KMS-backed, audit trail | AWS/GCP KMS |
| KEM (PQC) | **ML-KEM-768** + **X25519** (hybrid) | NIST FIPS 203 standard | — |
| Signature (PQC) | **ML-DSA-65** | NIST FIPS 204 | — |
| Long-term sig | **SLH-DSA-SHA2-128s** | NIST FIPS 205, hash-based fallback | — |
| TLS | **OpenSSL 3.4** + **liboqs** | PQC hybrid support | BoringSSL-PQC |
| VPN | **WireGuard** + **Rosenpass** (PQC) | Modern, fast | OpenVPN |
| SAST | **Semgrep** + **CodeQL** | Multi-language, custom rules | — |
| DAST | **OWASP ZAP** | Open-source | Burp |
| SCA | **Trivy** + **Snyk** | Container + dep scanning | Grype |
| SBOM | **Syft** + **cosign** signatures | SLSA L3 compliant | — |
| Sandboxing | **gVisor** / **Firecracker** | LLM agent isolation | Kata |
| Policy engine | **OPA** or **Cedar** | Declarative, auditable | — |
| WAF / DDoS | **Cloudflare Pro+** | Mature edge protection | AWS Shield |

## Layer 8 — Development & Operations

| Concern | Choice | Why | Alternative |
| --- | --- | --- | --- |
| Monorepo | **Turborepo** + **pnpm** | Fast, sane defaults | Nx, Bazel |
| CI | **GitHub Actions** | Matrix builds, easy | GitLab CI |
| CD | **ArgoCD** | GitOps standard | Flux |
| IaC | **Terraform** (Pulumi for niche) | Industry standard | OpenTofu |
| Container builds | **BuildKit** + **buildx** | Multi-arch, cached | — |
| Container registry | **GitHub Container Registry** | Integrated with CI | Harbor |
| Chaos engineering | **Chaos Mesh** | K8s-native | Litmus |
| Load testing | **k6** | Scriptable, fast | Locust |
| Property testing | **PropTest** (Rust) / **Hypothesis** (Py) | Catch determinism bugs | — |

---

## Hardware target (production)

- **GPU:** NVIDIA H200 (Phase 1-4) → B200 / B300 (Phase 5+)
- **CPU:** AMD EPYC Turin (Zen 5) — 192 cores / socket
- **RAM:** 1-2 TB DDR5 per node
- **Network:** 400 GbE backbone, 100 GbE per node, RDMA over RoCE v2
- **Storage:** NVMe Gen5 local + S3-compatible (R2/B2) for cold

---

## Stack changes log

| Date | Layer | Change | Reason |
| --- | --- | --- | --- |
| 2026-05-12 | All | Initial selection | Project start |
