# Diagrammes d'architecture (Mermaid)

## C1 — Contexte système

```mermaid
flowchart LR
  user[Scientifique / Observateur]
  admin[Admin SRE]
  api_partner[Partenaire Analytics]

  subgraph GE[Genesis Engine]
    direction TB
    obs[Observer Web]
    api[API Gateway]
    sim[Simulation Plane]
    data[Data Plane]
    inf[Inference Plane]
  end

  user -->|HTTPS+PQC| obs
  obs -->|gRPC-Web| api
  admin -->|Just-In-Time| api
  api_partner -->|Homomorphic Analytics| api

  api --> sim
  api --> data
  sim <--> data
  sim <--> inf
```

## C2 — Conteneurs

```mermaid
flowchart TB
  subgraph Client
    A[Next.js Observer]
    B[Bevy Immersive]
  end

  subgraph Edge
    CF[Cloudflare CDN/WAF]
    EV[Envoy Gateway]
  end

  subgraph SimPlane[Simulation Plane]
    TC[Tick Coordinator]
    SN1[Sim Node 1]
    SN2[Sim Node 2]
    SNn[Sim Node N]
    AN[Annaliste]
  end

  subgraph DataPlane[Data Plane]
    CR[CockroachDB]
    TB[TigerBeetle]
    QD[Qdrant]
    NJ[Neo4j]
    M[MinIO]
    TS[TimescaleDB]
    DF[DragonflyDB]
  end

  subgraph InfPlane[Inference Plane]
    TR[Triton + vLLM]
    GPU[H200/B200 Pool]
  end

  subgraph Bus
    RP[Redpanda]
  end

  A --> CF --> EV
  B --> CF
  EV --> TC
  EV --> AN
  TC <--> SN1 <--> SN2 <--> SNn
  SN1 --> RP
  SN2 --> RP
  SNn --> RP
  RP --> AN
  SN1 --> TR --> GPU
  SN1 <--> CR
  SN1 <--> DF
  SN1 --> TB
  SN1 --> QD
  AN --> CR
  AN --> NJ
  AN --> TS
  CR --> M
```

## Cycle de tick

```mermaid
sequenceDiagram
  participant TC as Tick Coordinator
  participant SN as Sim Node
  participant TR as Triton
  participant DF as Dragonfly
  participant CR as CockroachDB
  participant RP as Redpanda

  TC->>SN: tick T start
  SN->>SN: world step (physics, climate)
  SN->>SN: ecosystem step
  SN->>SN: perception step (per agent)
  SN->>TR: cognition batch (256 agents)
  TR-->>SN: actions
  SN->>SN: action resolution
  SN->>DF: write hot state
  SN->>RP: emit deltas + events
  SN->>CR: persist warm state
  SN-->>TC: tick T done
  TC->>TC: barrier all shards
  TC-->>SN: tick T+1 start
```

## Pipeline avatar utilisateur

```mermaid
flowchart LR
  IN[Photos + vidéo + voix] --> TDX[Confidential Enclave TDX/SEV-SNP]
  TDX --> FACE[Face Mesh - FLAME 2025]
  TDX --> BODY[Body Mesh - SMPL-X]
  FACE --> RIG[Skeleton + Blendshapes]
  BODY --> RIG
  RIG --> TEX[Texture Synthesis SD3/Flux]
  TEX --> ANI[Animation Retargeting]
  TDX --> VOC[Voice Clone XTTS v2.5]
  ANI --> PKG[Avatar Package .glb]
  VOC --> PKG
  PKG -->|E2E encrypted| OUT[User HSM/Yubikey]
```

## Pile cognitive d'un agent

```mermaid
flowchart BT
  L1[L1 Drives] --> L2[L2 Perception]
  L2 --> L3[L3 Appraisal]
  L3 --> L4[L4 Memory]
  L4 --> L5[L5 Reasoning]
  L5 --> L6[L6 Intent]
  L6 --> L7[L7 Metacognition]
  L7 -.feedback.-> L5
  L4 -.update.-> L3
  L3 -.modulate.-> L4
```

## Arbre de civilisation émergente

```mermaid
flowchart TD
  S[Survie individuelle] --> R[Reproduction]
  R --> C[Coopération diadique]
  C --> B[Bandes / Familles]
  B --> T[Tribu]
  T --> PL[Proto-langage]
  PL --> O[Outils complexes]
  O --> AG[Agriculture]
  AG --> SE[Sédentarité]
  SE --> H[Hiérarchie]
  H --> RE[Religion / écriture]
  RE --> CI[Cités]
  CI --> SC[Science]
  SC --> ET[État]
  ET --> GT[Guerres totales]
  GT --> EX[Effondrement]
  EX --> RN[Renaissance]
  RN --> CI
```

## Plans de sécurité (couches)

```mermaid
flowchart TB
  subgraph S1[Couche transport]
    TLS[TLS 1.3 + Kyber768 hybrid]
  end
  subgraph S2[Couche identité]
    FIDO[Passkeys WebAuthn]
    SPIFFE[SPIFFE/SPIRE mTLS]
  end
  subgraph S3[Couche données]
    AES[AES-256-GCM]
    HE[Homomorphic CKKS/BGV]
    HSM[HSM FIPS 140-3 L3]
  end
  subgraph S4[Couche signatures]
    ED[Ed25519]
    ML[ML-DSA Dilithium]
    SLH[SLH-DSA SPHINCS+]
  end
  subgraph S5[Couche audit]
    LOG[Append-only logs]
    OBJ[S3 Object Lock]
  end
```
