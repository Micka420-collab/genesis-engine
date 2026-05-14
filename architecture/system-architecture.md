# Architecture système

## Diagramme à blocs (haut niveau)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT TIER                                 │
│  Observer Web (Next.js + Three.js/WebGPU)   Immersive Client (Bevy) │
└────────────────────────────┬────────────────────────────────────────┘
                             │ WebRTC / gRPC-Web / REST
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       EDGE / API GATEWAY (Envoy)                     │
│         mTLS · WAF · OAuth2/OIDC + Passkeys · Rate-limit             │
└────────────┬────────────────────────────────────┬───────────────────┘
             │                                    │
             ▼                                    ▼
   ┌──────────────────┐                ┌────────────────────┐
   │ Observer API     │                │  Control Plane     │
   │ (Rust/axum)      │                │  Sim mgmt, auth     │
   └────────┬─────────┘                └─────────┬──────────┘
            │                                    │
            │           ┌────────────────────────┴───────────┐
            │           │                                    │
            ▼           ▼                                    ▼
  ┌──────────────────────────────────────┐       ┌──────────────────┐
  │       SIMULATION PLANE                │       │  DATA PLANE      │
  │                                       │       │                  │
  │  ┌──────────────┐  ┌──────────────┐  │       │ CockroachDB      │
  │  │ Tick Coord   │  │ World Engine │  │       │ TigerBeetle (€)  │
  │  │ (HLC clock)  │  │ (Rust shards)│  │       │ Redis/Dragonfly  │
  │  └──────┬───────┘  └──────┬───────┘  │       │ Qdrant (vectors) │
  │         │                 │          │       │ Neo4j (graph)    │
  │         ▼                 ▼          │       │ MinIO (snapshots)│
  │  ┌──────────────────────────────┐    │       │ TimescaleDB      │
  │  │   Sim Nodes (1 per chunk)    │    │       └──────────────────┘
  │  │   Rust + Bevy ECS            │    │
  │  └────────┬──────────────┬─────┘    │       ┌──────────────────┐
  │           │              │          │       │  EVENT BUS       │
  │           ▼              ▼          │◄──────┤  Redpanda/Kafka  │
  │  ┌────────────┐  ┌──────────────┐   │       │                  │
  │  │ Cognition  │  │ Annaliste    │   │       └──────────────────┘
  │  │ (Triton/   │  │ (event       │   │
  │  │  vLLM)     │  │ detector)    │   │       ┌──────────────────┐
  │  └────────────┘  └──────────────┘   │       │  WORKFLOW        │
  │                                       │       │  Temporal.io     │
  └───────────────────────────────────────┘       └──────────────────┘
```

## Plans logiques

### Control Plane
Gestion : utilisateurs, simulations, snapshots, paramètres, billing.
Tech : Rust (axum), CockroachDB.

### Simulation Plane
Boucle de tick distribuée. Hot path. Pas d'humain dans la boucle.
Tech : Rust, Bevy ECS, Redpanda.

### Data Plane
Toute la persistance + analytics. Réplication multi-région.
Tech : CockroachDB (état), TigerBeetle (économie), Qdrant (mémoires), MinIO (snapshots/chunks).

### Inference Plane
Pool GPU pour cognition agents.
Tech : Triton + vLLM + TensorRT-LLM, autoscaling Karpenter.

### Observability Plane
OTLP collector → Tempo/Mimir/Loki. Toujours hors path.

## Principes d'architecture

### 1. Déterminisme strict
- RNG indexé : `rng_for(tick, agent_id, action_id) = PRF(seed, tick, agent_id, action_id)`
- Pas de wall-clock dans la logique
- Ordre d'exécution canonique (par hash)

### 2. Sharding par chunk spatial
- 1 chunk = 64×64 m²
- 1 sim node ≈ 256–1024 chunks selon densité
- Rebalancing dynamique (Karpenter + custom controller)

### 3. Handover inter-shards
Quand un agent traverse une frontière de chunk :
1. Le node source freeze l'agent (atomic)
2. Sérialisation rkyv
3. Publication sur Redpanda (`agent.handover.v1`)
4. Node cible désérialise et résume
5. ACK two-phase

### 4. Tick coordination
- **HLC (Hybrid Logical Clocks)** par node
- Barrier all-shards à chaque tick
- Backpressure : si un shard prend du retard, le coordinator ralentit le tick global
- Pas de tick partial : c'est tout ou rien (consistency over availability sur la sim)

### 5. Immutable history
- Chaque tick produit un **delta** ajouté à un log append-only sur Redpanda + S3
- Snapshots périodiques (paramétrable, par défaut tous les 10⁶ ticks)
- Le replay est garanti bit-à-bit avec snapshot + log

## Communication inter-services

| Lien | Protocole | Pourquoi |
|---|---|---|
| Sim node ↔ Sim node | **gRPC streaming + rkyv** | latence + zero-copy |
| Sim node ↔ Inference | **NVIDIA Triton client gRPC** | dynamic batching |
| Sim plane ↔ Data plane | **gRPC (proto)** | contrats stricts |
| API ↔ Client | **gRPC-Web + WebRTC + REST fallback** | flexibilité |
| Event bus | **Redpanda (Kafka protocol)** | streaming durable |

## Sécurité Zero Trust

- mTLS partout (SPIFFE/SPIRE pour les identités de service)
- Pas de service exposé sans mTLS, même intra-cluster
- Politiques **OPA / Cedar** (autorisation déclarative)
- Tokens d'accès **signés Ed25519 + Dilithium** (PQC, voir doc sécurité)

## Multi-tenancy

- Une **simulation** = un tenant logique
- Isolation namespace Kubernetes + NetworkPolicies
- Quotas CPU/GPU/Stockage par tenant
- Encryption-at-rest par clé tenant (KMS, rotation 90 j)

## Failover & disponibilité

- Sim plane : si un sim node tombe, ses chunks sont rejoués depuis le dernier snapshot + tail du log → reprise en < 10 s
- Data plane : multi-AZ par défaut, multi-région optionnel
- Control plane : actif-actif sur 3 régions

> **Note** : la simulation accepte un **freeze** plutôt qu'une corruption. Si le système ne peut pas garantir la cohérence, il fige et alerte.

## Coût (ordres de grandeur 2026)

| Mode | Coût/jour | Coût/mois |
|---|---|---|
| Petri (dev) | ~$0 (laptop) | ~$0 |
| Lab (10 k agents) | ~$200 | ~$6 k |
| Continent (1 M agents) | ~$15 k | ~$450 k |
| Planet (100 M agents) | ~$1 M | ~$30 M |

Le coût dominant est le GPU pour la cognition (~70 %).
