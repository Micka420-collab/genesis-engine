# Infrastructure & Scaling

## Topologie cible (mode Continent)

```
                        ┌────────────────────────┐
                        │  Edge POPs (Cloudflare)│
                        │  Caching · Bot mgmt    │
                        └──────────┬─────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
       ┌────────────┐       ┌────────────┐       ┌────────────┐
       │  Region A  │       │  Region B  │       │  Region C  │
       │  (us-east) │       │  (eu-west) │       │ (ap-south) │
       │            │       │            │       │            │
       │  K8s + GPU │◄─────►│  K8s + GPU │◄─────►│  K8s + GPU │
       │  Cockroach │       │  Cockroach │       │  Cockroach │
       └────────────┘       └────────────┘       └────────────┘
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   ▼
                       ┌──────────────────────┐
                       │  Cold Storage (MinIO │
                       │  + S3 Glacier)        │
                       └──────────────────────┘
```

## Pools de ressources

| Pool | Taille (Continent) | Notes |
|---|---|---|
| sim-cpu | 200 nodes 64 vCPU | Sim nodes Rust |
| inference-gpu | 80 H200 | Cognition |
| data-cpu | 30 nodes 32 vCPU | DB workers |
| observer-cpu | 20 nodes | API + analytics |
| ingest | 10 nodes | Redpanda brokers |

## Auto-scaling

- **Karpenter** + **KEDA** :
  - sim-cpu scale sur backlog du tick coordinator
  - inference-gpu scale sur p95 latence Triton
  - observer-cpu scale sur QPS
- **Spot/preemptible** : OK pour observer/analytics, jamais pour sim plane (déterminisme)

## Réseau

- **VPC peering** ou **Cloud WAN** entre régions
- **Private subnets** uniquement pour la simulation
- **Public ingress** via Cloudflare → Envoy seulement
- **eBPF** (Cilium) pour les NetworkPolicies + observabilité réseau

## Stockage

| Tier | Tech | Capacité initiale |
|---|---|---|
| Hot RAM | DragonflyDB cluster | 2 TB |
| Warm SSD | CockroachDB local NVMe | 50 TB répartis |
| Object | MinIO sur HDD | 1 PB |
| Vector | Qdrant sur SSD | 20 TB |
| Cold | S3 Glacier Deep | illimité |

## CI/CD

- **GitHub Actions** : build, test, security scan (Trivy + Grype + CodeQL)
- **SBOM** émis en SPDX 3 + CycloneDX 1.6
- **Sigstore / Cosign** : signatures images + provenance SLSA Level 3+
- **Argo CD** : déploiement GitOps multi-cluster
- **Argo Rollouts** : canary + analysis (Prometheus queries comme gate)

## Disaster Recovery

| Scénario | RPO | RTO |
|---|---|---|
| Perte d'un node sim | 0 (tick replay) | < 30 s |
| Perte d'une AZ | 0 (multi-AZ Cockroach) | < 2 min |
| Perte d'une région | < 1 min | < 30 min |
| Perte totale data plane | 1 jour simulé (snapshot quotidien) | < 24 h |

## Tests de chaos

- **Chaos Mesh** : injection latence, perte paquets, kill node
- **Game days** trimestriels : on coupe une région entière, on mesure RTO
- **Determinism canary** : à chaque release, on rejoue une simulation de 10⁶ ticks et on compare le hash final → bit-identique requis

## FinOps

- Tagging strict : `sim_id`, `tier`, `tenant`, `env`
- **Kubecost** + **OpenCost** pour breakdown
- Alertes budget par tenant
- **GPU sharing** (MIG) en mode Lab pour amortir le coût

## Conformité & souveraineté

- ISO 27001 (cible)
- SOC 2 Type II (cible)
- GDPR / CCPA : aucune donnée personnelle dans la simulation par défaut. Les avatars utilisateurs (section 2 du brief) sont **opt-in** et stockés sous chiffrement E2E.
- **Souveraineté UE** : option de déploiement sur **OVHcloud / Scaleway / Outscale** + pile entièrement open-source.
