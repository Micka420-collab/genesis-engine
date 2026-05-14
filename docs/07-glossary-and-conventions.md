# Glossaire & Conventions

## Glossaire

| Terme | Définition |
|---|---|
| **Tick** | Unité atomique de temps simulé. Tout effet causal est aligné sur des frontières de tick. |
| **Chunk** | Sous-volume spatial du monde (64×64×128 voxels). Unité de sharding et de streaming. |
| **Shard** | Un sim node responsable d'un ensemble de chunks. |
| **Drive** | Besoin biologique ou homéostatique d'un agent (faim, soif, fatigue, …). |
| **Appraisal** | Évaluation cognitive d'un événement (modèle OCC/Plutchik). |
| **R0–R4** | Niveaux de raisonnement : reflex, planner, world-model, theory-of-mind, symbolique. |
| **Annaliste** | Sous-système qui détecte les événements remarquables et reconstruit la chronique. |
| **Lignée** | Arbre généalogique d'agents reliés par reproduction. |
| **Émergence** | Apparition d'un phénomène collectif non explicitement codé. |
| **PQC** | Post-Quantum Cryptography — algorithmes résistant aux ordinateurs quantiques. |
| **PRF** | Pseudo-Random Function — clé du déterminisme indexé. |
| **Handover** | Migration d'agent ou d'objet entre deux shards. |
| **HLC** | Hybrid Logical Clock — horloge distribuée. |
| **LOD** | Level Of Detail — granularité de rendu/simulation selon distance. |
| **Mode GOD** | Mode observateur omniscient passif. |
| **Petri / Lab / Continent / Planet** | Tiers de déploiement par taille. |
| **Saut symbolique** | Transition d'un signal causal vers un signe référentiel (apparition du langage). |

## Conventions de code

- **Rust** : edition 2024, `clippy::pedantic`, `unsafe` interdit hors modules cryptographiques explicitement listés
- **TypeScript** : strict, no-any, `biome` strict
- **Python** : `ruff`, `mypy --strict`, pydantic v2 partout pour validation
- **Pas de wall-clock** dans la sim. Timer = `tick`. Random = `prf(seed, …)`.

## Conventions de versioning

- **SemVer** sur tous les paquets
- Schema events / state : versionné explicitement, migrations non-rétroactives interdites en prod
- API : `/v1`, `/v2` distincts ; deprecation 12 mois minimum

## Conventions d'observabilité

- Trace par tick, par agent, par chunk
- Attribut OTel obligatoire : `sim.id`, `sim.tick`, `agent.id`, `chunk.id`, `tenant.id`
- Sampling : 100 % en dev, 10 % en prod hors événement annaliste (toujours 100 %)

## Conventions de sécurité

- Pas de PII dans logs ni traces
- Tous secrets : Vault dynamic ou cloud-native workload identity
- Toute exfiltration externe : DLP scan obligatoire

## Conventions documentation

- ADR = Architecture Decision Record, format MADR 4.0
- Tout choix de techno listé dans `tech-stack-2026.md` doit avoir un ADR correspondant
- Chaque ADR : status (proposed/accepted/superseded), context, decision, consequences

## Conventions scientifiques (pour les publications)

- Toute publication scientifique fournit :
  - le **seed**
  - le **manifest binaire signé** (hash SBOM)
  - la **config complète** (yaml)
  - le **snapshot zéro**
  - une **commande de replay** reproductible
- Pas de cherry-picking : si une simu de l'expérience est exclue, motif documenté
