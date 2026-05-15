# Sprint 2026-05-15 — Wave 11 elite cognitive metrics

**Mode :** Autonome (déclenchement scheduled-task `continue-la-cration-de-genesis-enginer`).
**Cible :** Combo veille — métriques d'élite cognitive émergente (Hill α + Gini)
sur les cultures Genesis, inspiré du papier arXiv avril 2026 *"Do Agent
Societies Develop Intellectual Elites? The Hidden Power Laws of Collective
Cognition in LLM Multi-Agent Systems"*.

---

## Étape 0 — Veille (résumé)

| # | Découverte | Couche impactée | Statut |
|---|-----------|------------------|--------|
| 1 | MCP-SIM plan-act-reflect-revise framework | Agentic / Cognition | Backlog |
| 2 | Bevy 0.16 ECS Relationships + GPU-driven render | Substrate / World | Backlog (phase 6) |
| 3 | ML-KEM v0.2.0 Rust pur (FIPS 203 final) + Cryspen verified | Platform | Rejeté (pas de surface réseau prod) |
| 4 | Weaviate hybrid BM25 + dense + metadata | Observatory | Backlog |
| 5 | **arXiv 2026 — Intellectual elites & power laws in agent societies** | **Agentic + Observatory** | **RETENU** |

**CVE_ACTIVES :** aucune critique sur le stack courant.

## Étape 1 — Combo retenu

`Power-law cognitive elite metrics × Genesis cognition+culture`.

- **Gain :** métrique d'émergence sociale *mesurable* (Gini, top10/médiane,
  estimateur de Hill α) sans toucher l'engine. Première instrumentation
  *scientifique* H0-compatible : si les civilisations émergent vraiment
  sans script, leurs distributions cognitives devraient tendre vers des
  lois de puissance — testable observationnellement.
- **Coût :** ~1 h · complexité 2/5 · risque régression 1/5.
- **Intégration :** observateur pur-lecture, journal JSONL append-only.
- **ADR requis :** non (pas de décision architecturale, pas de mutation
  d'état sim, pas de changement de format de save).

## Étape 2 — Livré

### `runtime/engine/elite_metrics.py` (~160 LOC)

API publique :

```python
compute_elite_metrics(sim) -> Dict[culture_id, dict]
    # n_alive, mean, std, gini, top10_median_ratio, hill_alpha
log_elite_metrics(sim, journal_path, extra=None) -> Dict
detect_power_law(metrics, alpha_min=1.2, alpha_max=4.0) -> Dict[cid, bool]
```

Définitions :

- `skill_proxy(i) = 0.5 * intelligence[i] + 0.5 * conscientiousness[i]`
  (deux traits du Big-Five étendu déjà présents sur `AgentRegistry`).
- **Gini** : formule trapézoïdale standard sur valeurs triées, bornée
  `[0, 1]`.
- **top10_median_ratio** : moyenne du décile supérieur ÷ médiane. >1
  signale concentration.
- **Hill α** : estimateur de l'indice de queue Pareto sur la moitié
  supérieure (`α = 1 + n_tail / Σ log(x_i / médiane)`). NaN si <8
  observations.
- **detect_power_law** : heuristique — α ∈ [1.2, 4.0] et Gini > 0.05.

Pure-lecture, aucun PRNG, aucun appel à `prf_rng`, aucune mutation.

### `runtime/scripts/p37_elite_metrics_smoke.py` — 8/8 PASS

```
step 1 — empty sim returns {}                               OK
step 2 — bootstrap yields >=1 culture                       OK   cultures=[0,1]
step 3 — 250 ticks + 5 logs no crash                        OK   logged=5
step 4 — JSONL parsed, 5 entries, schema OK                 OK   n=5
step 5 — metric ranges sane                                 OK   violations=[]
step 6 — detect_power_law keys align                        OK   keys=[0,1]
step 7 — determinism + pure-read observer                   OK   c341d9b6...
step 8 — extinct culture pruned cleanly                     OK   cultures_after_kill=[0]
```

### Non-régression

`p23_persistence_roundtrip` : **PASS** (4 steps OK, hashes bit-identiques).

## Étape 3 — Observation initiale (16 founders, 2 cultures, 250 ticks Léman)

Tick 50 — `culture 0` : `Gini=0.28, α=3.98, top10/median=1.79` (queue plus
plate, légère inégalité).
Tick 50 — `culture 1` : `Gini=0.14, α=4.50, top10/median=1.78` (queue
fine, plus égalitaire).

Les α restent élevés (queues courtes) parce que la cognition Phase 4 est
*génétique-statique* — `intelligence` et `conscientiousness` sont
échantillonnées à la naissance puis figées. Pour observer une vraie
formation d'élite, il faudra :

1. **Plasticité d'apprentissage** (Wave 12 candidat) — boost cumulé sur
   `intelligence_effective` selon les inventions transmises/reçues.
2. **Sélection sexuelle assortative** sur intelligence (Wave 12 candidat) —
   matings préférentiels sur trait cognitif, augmente le Gini sur ~10
   générations.
3. **Runs longs ≥10k ticks avec naissances** pour laisser la dérive
   génétique agir.

## Étape 4 — Backlog en sortie

- **W11-FOLLOWUP-1** : brancher un appel `log_elite_metrics` toutes les
  500 ticks dans `experiments/run_all.py` pour produire un dataset
  long-run reproductible.
- **W11-FOLLOWUP-2** : exposer `compute_elite_metrics` via
  `genesis/api/server.py` (`GET /api/elite/{culture_id}`) — couche
  Observatory.
- **W12 candidat (haut)** : plasticité d'apprentissage sur
  `intelligence_effective` — observer si Gini grimpe.
- **W12 candidat (haut)** : sélection sexuelle assortative.

## Genesis Delta

| Métrique | Avant | Après |
|---|---|---|
| Modules engine | 47 | **48** |
| Smoke scripts | 35 | **36** |
| Métriques émergentes observables | 0 méta-pop | **1 (Gini/α/top10)** |
| Couches touchées | — | Agentic + Observatory |
| Surfaces PQC | — | inchangé (rejeté pour ce sprint) |
| Régressions | — | **0** |

## Méta

- Veille → combo → audit → code → smoke → doc : routine respectée.
- Innovation : première instrumentation H0-compatible d'émergence sociale.
- Aucune ligne de code écrite avant complétion de la veille.
