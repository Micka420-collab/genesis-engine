# Runbook — Incidents Genesis Engine

## Sévérités

| Sev | Définition | Exemples | SLA réponse |
|---|---|---|---|
| SEV-1 | Sim plane down ou intégrité compromise | tick coord crash, drift hash, snapshot corrompu | 15 min |
| SEV-2 | Dégradation majeure | latence cognition >5x baseline, perte node sim sans recovery auto | 30 min |
| SEV-3 | Dégradation localisée | un tenant dégradé, dashboard down | 2 h |
| SEV-4 | Cosmétique | UI glitch, doc obsolète | 1 jour ouvré |

## Escalade

```
On-call SRE  ─►  Tech Lead  ─►  Architecte  ─►  Direction projet
   (15 min)      (30 min)        (1 h)            (2 h)
```

## Scénarios

### S1 — Tick coordinator crashé

**Symptômes** : tick stream interrompu, sim nodes en backpressure.

**Investigation** :
1. `kubectl logs -l app=tick-coordinator --tail=200`
2. Vérifier état HLC : `coredb=> SELECT * FROM tick_state ORDER BY tick DESC LIMIT 5;`
3. Vérifier Redpanda : `rpk topic consume tick.commands -n 5`

**Mitigation** :
1. Si crash unique : laisser Argo Rollouts restart auto
2. Si crash boucle : `kubectl scale deploy/tick-coordinator --replicas=0` → rollback à la version N-1 → scale up
3. Si state corrompu : restore depuis dernier snapshot + replay du log Redpanda

### S2 — Drift de hash entre nodes

**Symptômes** : determinism canary rouge, hash final ≠ baseline.

**Action immédiate** :
1. **Stop world** sur la simulation impactée (état FROZEN, pas STOP)
2. Bisect : compare delta-roots tick par tick entre nodes
3. Identifier le tick d'introduction du drift
4. Investigation : code review du module touché

**Cause typique** : appel à `rand::thread_rng()`, accès filesystem non déterministe, dépendance d'ordre HashMap (utiliser BTreeMap).

**Récupération** : restore snapshot précédent du drift + correctif + replay.

### S3 — Latence cognition > 5x baseline

**Symptômes** : Triton p99 > 100 ms, sim nodes en attente.

**Investigation** :
1. Triton metrics : batch fill, queue depth
2. GPU util : `nvidia-smi`
3. Karpenter scaling status

**Mitigation** :
1. Forcer un scale-up GPU pool
2. Réduire batch window si trop d'attente
3. Activer le mode statistique pour les zones non observées

### S4 — Snapshot corrompu

**Symptômes** : checksum mismatch au restore, BLAKE3 root invalide.

**Action** :
1. Marquer le snapshot comme corrompu en DB
2. Récupérer le snapshot précédent
3. Replay log Redpanda jusqu'au tick cible
4. Ouvrir investigation root cause (CRC stockage, bit-flip, intentional ?)
5. Si suspicion intentional → process security incident (`runbook-security-incident.md`)

### S5 — Sim node plante en boucle

**Action** :
1. Drain du node via API : `POST /v1/sim-nodes/{id}/drain`
2. Les chunks sont rebalancés
3. Investigation logs + core dump
4. Si pattern : capacity planning sous-dimensionné → scale out

### S6 — Pic de coût cloud

**Investigation** :
- Kubecost dashboard
- Spend par tag `sim_id`, `tenant`, `tier`
- Vérifier que le mode auto-scale ne diverge pas

**Action** :
1. Notifier le tenant si dépassement
2. Activer la limite par tenant si non set
3. Investigation : runaway agent ? simulation Lab-tier exécutée Continent ?

### S7 — Compromission soupçonnée

→ Voir `runbook-security-incident.md` (ce document est partiel).

Action immédiate : **isoler** le namespace impacté (`kubectl cordon` + NetworkPolicy `deny-all`), **ne pas redémarrer**, **préserver les artefacts** pour forensics.

## Communication

- Page status publique : `status.genesis-engine.example`
- Incident channel Slack : `#incidents-active`
- Postmortem obligatoire pour SEV-1/SEV-2 sous 5 jours ouvrés (blameless)

## Drills

- **Game day** trimestriel : simuler une coupure de région
- **DR drill** annuel : restore from cold backup
- **Determinism drill** mensuel : rejeu d'une simulation reference, comparaison hash

## Outillage on-call

- Grafana dashboards :
  - `Genesis / Sim Plane Health`
  - `Genesis / Cognition Latency`
  - `Genesis / Cost`
  - `Genesis / Determinism`
- Alertes PagerDuty : routées par sévérité
- Runbooks par alerte : lien direct dans la notif PagerDuty
