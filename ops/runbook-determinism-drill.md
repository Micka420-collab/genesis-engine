# Runbook — Determinism drill (mensuel)

## Objectif

Garantir que le moteur Genesis Engine produit des résultats **bit-à-bit identiques** entre deux exécutions à partir des mêmes (seed, config, build).

## Procédure

```
1. Choisir le scénario de référence : "ref-tiny-v1" (10 agents, 10⁴ ticks)
2. Récupérer le snapshot zéro signé : minio://genesis-bench/ref-tiny-v1/snapshot-0.zst
3. Récupérer le manifest binaire signé attendu (commit hash + SBOM)
4. Lancer la simulation sur env clean :
     ge-sim run --config ref-tiny-v1.yaml \
                --snapshot snapshot-0.zst \
                --until-tick 10000 \
                --emit-final-root tick_root_run.bin
5. Comparer tick_root_run.bin vs tick_root_expected.bin :
     blake3sum --check expected.b3
6. Si match : OK → publier le rapport vert
7. Si mismatch : déclencher S2 — Drift de hash (runbook-incidents.md)
```

## Critères

- 100 % match : test passe
- Toute différence : test échoue (zéro tolérance)

## Cadence

- Mensuel (1er lundi du mois)
- Avant chaque release majeure
- Avant publication scientifique

## Déclencheurs ad hoc

- Mise à jour d'une dépendance crypto, math, ou ECS
- Migration toolchain Rust majeure
- Changement de version GPU driver / CUDA
- Changement modèle d'inférence

## Interprétation

Un drift indique **toujours** un bug, jamais un comportement attendu. Causes typiques :
- Ordre d'itération sur `HashMap` (utiliser `BTreeMap`)
- Wall-clock non déterministe (utiliser `Tick`)
- Floating-point instable (FMA, `fma()` vs `a*b+c`)
- Threading sans ordre canonique (sortir tri sur `agent_id`)
- RNG non indexé via PRF
