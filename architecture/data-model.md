# Modèle de données

## Entités principales

### Simulation
```
simulation_id: uuid
seed: u128
created_at: ts
status: enum(running, paused, frozen, archived)
config: jsonb        // paramètres physiques, biologiques, génétiques
current_tick: u64
tier: enum(petri, lab, continent, planet)
owner_org_id: uuid
```

### World Chunk
```
sim_id: uuid
chunk_x: i32
chunk_y: i32
chunk_z: i32
seed: u128            // hérité, déterministe
last_modified_tick: u64
state_blob_uri: text  // S3/MinIO
state_hash: bytes     // BLAKE3
modified: bool        // si false → regenerable from seed
```

### Agent (état canonique)
```
agent_id: uuid
sim_id: uuid
spawn_tick: u64
death_tick: u64?
position: vec3
genome: bytes (compact)
phenotype: jsonb       // dérivé du génome
drives: float[8]
mood: float[8]         // Plutchik
energy: float
health: float
inventory: jsonb
parents: uuid[2]?
group_id: uuid?
culture_id: uuid?
policy_lora_id: uuid?
```

### Memory (épisodique)
```
agent_id: uuid
memory_id: uuid
tick: u64
embedding: vector(384)
event_type: text
valence: float
agency: enum(self, other, world)
participants: uuid[]
location: vec3
text_summary: text     // optionnel
```

### Group / Tribe
```
group_id: uuid
sim_id: uuid
name_emerged: text?    // détecté par Annaliste
members: uuid[]
leader_id: uuid?
formed_tick: u64
dissolved_tick: u64?
center: vec3
identity_signals: jsonb // signaux culturels distinctifs
```

### Culture
```
culture_id: uuid
sim_id: uuid
parent_culture_id: uuid?  // dérive
vocab: jsonb              // signal → référent
rituals: jsonb
techs_known: text[]
mythologies: jsonb
```

### Event (chronique / Annaliste)
```
event_id: uuid
sim_id: uuid
tick: u64
type: enum(birth, death, innovation, conflict, founding, ...)
participants: uuid[]
location: vec3?
metadata: jsonb
causal_parents: event_id[]   // lien causal
significance_score: float    // pour cinematic
```

### Snapshot
```
snapshot_id: uuid
sim_id: uuid
tick: u64
created_at: ts
size_bytes: i64
storage_uri: text
checksum: bytes
parent_snapshot_id: uuid?
```

### Lineage (graphe de parenté)

Stocké dans Neo4j :
```
(:Agent {agent_id})-[:CHILD_OF]->(:Agent)
(:Agent)-[:MATED_WITH {tick}]->(:Agent)
(:Agent)-[:KILLED {tick, weapon}]->(:Agent)
(:Agent)-[:TRADED_WITH {tick, items}]->(:Agent)
```

## Volumes attendus

| Mode | Agents | Events/tick | Mémoires totales | Stockage/an simulé |
|---|---|---|---|---|
| Petri | 100 | ~50 | ~1 M | ~10 GB |
| Lab | 10 k | ~5 k | ~100 M | ~1 TB |
| Continent | 1 M | ~500 k | ~10 B | ~100 TB |
| Planet | 100 M | ~50 M | ~1 T | ~10 PB |

## Règles de rétention

| Donnée | Rétention par défaut |
|---|---|
| State agents (vivants) | toujours |
| State agents (morts) | 100 ans simulés puis compressé en agrégat |
| Mémoires individuelles | du vivant + 1 an post-mortem |
| Events | 10 000 ans simulés |
| Chunks regénérables non modifiés | jamais persistés (regénérés à la demande) |
| Snapshots | les 10 derniers + 1 par siècle simulé |

## Tiers de stockage

```
hot   (Redis/Dragonfly)        — agents actifs du tick courant
warm  (CockroachDB + Qdrant)    — vivants + 1000 ticks récents
cold  (TimescaleDB + MinIO)     — agrégats long terme
glacier (S3 Glacier / DeepArchive) — snapshots historiques
```

## Schéma de transactions économiques (TigerBeetle)

TigerBeetle est utilisé pour **tout échange** ressources/objets entre agents :
- Account = `(agent_id, asset_id)`
- Transfer = `(debit_account, credit_account, amount, code, flags)`

Avantages :
- 1 M tx/s
- Double-entry strict (impossible de créer du stock ex nihilo)
- Audit trail natif

## Indexation

- BLAKE3 pour tous les hashes (rapide, parallèle)
- `tick` est l'index principal partout
- `geo` index : H3 (Uber) pour requêtes spatiales rapides
- Embeddings : HNSW dans Qdrant

## Encryption-at-rest

- Toutes les DB chiffrées avec **AES-256-GCM** + clé tenant rotée tous les 90 j
- Snapshot blobs **chiffrés-côté-client** avant envoi (E2E pour le client : confidentialité même vis-à-vis du fournisseur cloud)
- Voir doc sécurité pour la couche post-quantique
