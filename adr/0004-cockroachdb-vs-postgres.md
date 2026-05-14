# ADR 0004 — CockroachDB pour l'OLTP + TigerBeetle pour les transactions économiques

- **Statut** : Accepté
- **Date** : 2026-05-10

## Contexte

Une simulation Continent peut produire ~500 k events/tick et ~1 M transactions économiques par seconde. PostgreSQL classique ne tient pas le scale + multi-région + déterminisme requis sur les économies émergentes.

## Décision

- **CockroachDB** comme OLTP principal (état persistant, événements, métadonnées) — multi-région, MVCC fort, compatible PostgreSQL côté driver.
- **TigerBeetle** pour **toutes** les transactions économiques d'agents — double-entry natif, 1 M tx/s, déterministe.
- **TimescaleDB** pour les séries temporelles d'analytics (telemetry, métriques agrégées).
- **Neo4j / Memgraph** pour les requêtes de graphe (lignées, alliances, influence).

Postgres reste utilisable en dev local (Petri), mais CockroachDB est obligatoire dès Lab.

## Conséquences

### Positives
- Multi-région natif, failover transparent
- Garanties ACID strictes en distribué
- Audit trail économique infalsifiable (TigerBeetle)
- Pas de double-counting possible sur les inventaires

### Négatives
- Coût (CockroachDB licence pour features avancées)
- Complexité opérationnelle (4 stores au lieu d'1)
- TigerBeetle encore jeune (mais éprouvé production)

## Validation

Benchmark Phase 3 : 100 k échanges/s sur TigerBeetle pendant 1 h, latence p99 < 5 ms.
