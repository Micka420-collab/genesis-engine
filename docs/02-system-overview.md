# 02 — Vue d'ensemble du système

## Les sept sous-systèmes

```
┌─────────────────────────────────────────────────────────────┐
│                    GENESIS ENGINE                            │
└─────────────────────────────────────────────────────────────┘

  1. WORLD ENGINE        — terrain, biomes, climat, physique
  2. ECOSYSTEM ENGINE    — flore, faune, ressources, cycles
  3. AGENT RUNTIME       — perception, cognition, mémoire, action
  4. EVOLUTION ENGINE    — génétique, mutation, sélection
  5. EMERGENCE LAYER     — économie, politique, culture, religion
  6. OBSERVER PLATFORM   — replay, analytics, mode GOD
  7. PLATFORM SERVICES   — auth, storage, scheduling, telemetry
```

## Boucle de simulation (tick principal)

```
┌──────────────┐
│  TICK = T    │ (temps simulé, indépendant du wall clock)
└──────┬───────┘
       │
       ▼
[1] WORLD STEP        — physique, climat, érosion, croissance plantes
       │
       ▼
[2] ECOSYSTEM STEP    — animaux, ressources, météo, chaînes alimentaires
       │
       ▼
[3] PERCEPTION STEP   — chaque agent observe son champ local (FOV + audition)
       │
       ▼
[4] COGNITION STEP    — décision (en parallèle, batch GPU)
       │
       ▼
[5] ACTION STEP       — résolution des actions, conflits, déterministe
       │
       ▼
[6] CONSEQUENCE STEP  — santé, mémoire, émotions, génétique
       │
       ▼
[7] EMERGENCE STEP    — agrégation : économie, structures sociales détectées
       │
       ▼
[8] PERSIST STEP      — write-ahead log, snapshot incrémental
       │
       ▼
   TICK = T+1
```

## Échelles de temps

| Échelle | Tick rate | Usage |
|---|---|---|
| **Real-time (×1)** | 60 Hz logique, 30 Hz rendu | Mode immersif first-person |
| **Standard (×10)** | 600 Hz | Observation directe |
| **Fast (×100)** | 6 kHz | Génération sociale |
| **Eon (×1000)** | 60 kHz | Évolution civilisationnelle |
| **Geological (×10000)** | snapshots/heure | Pour observer extinction/renaissance |

Les tick rates supérieurs à ×100 désactivent automatiquement le rendu 3D et n'exécutent que la cognition + agrégats statistiques.

## Modèle de données — quatre niveaux

```
┌───────────────────────────────────────────────────┐
│  NIVEAU 4 — STATE PERSISTANT (PostgreSQL + S3)    │ ← snapshots, lignées
├───────────────────────────────────────────────────┤
│  NIVEAU 3 — STATE WARM (Redis + Vector DB)        │ ← mémoires, embeddings
├───────────────────────────────────────────────────┤
│  NIVEAU 2 — STATE HOT (RAM partagée GPU)          │ ← agents actifs du tick
├───────────────────────────────────────────────────┤
│  NIVEAU 1 — DELTAS (event stream Redpanda/Kafka)  │ ← log d'événements
└───────────────────────────────────────────────────┘
```

## Sharding — la clé du scale

Le monde est divisé en **chunks spatiaux** (ex. 256×256 m). Chaque chunk est attribué à un **simulation node**.

- Un agent qui traverse une frontière déclenche un **handover** (migration d'état entre nodes).
- Les chunks **non observés** par un humain et **sans agents** sont **gelés** (sleep state).
- Les chunks **inactifs depuis N ticks** sont **archivés** sur S3 et regénérables à la demande.

Cela permet une **carte théoriquement infinie** avec un coût marginal proportionnel au nombre d'agents actifs, **pas à la surface**.

## Composants critiques (au sens « si ça tombe, tout tombe »)

1. **Tick Coordinator** — horloge logique distribuée (basé sur HLC — Hybrid Logical Clocks)
2. **State Store** — DB OLTP avec MVCC fort + write-ahead log (CockroachDB ou TigerBeetle pour transactions économiques)
3. **Event Bus** — Redpanda (Kafka-compatible, lower latency)
4. **GPU Inference Pool** — Triton Inference Server + dynamic batching pour la cognition

## Modes d'exécution

| Mode | Description | Coût |
|---|---|---|
| **Petri** | 1 nœud, 100 agents max, dev local | gratuit |
| **Lab** | 10 nœuds, 10 k agents | ~$200/jour |
| **Continent** | 100 nœuds, 1 M agents | ~$15 k/jour |
| **Planet** | 1000 nœuds, 100 M agents | sur devis |

Le mode **Petri** est livrable dès la Phase 1.
