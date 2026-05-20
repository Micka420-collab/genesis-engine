# Wave 40 — Lineage / Reproductive Genetics Observer

**Date :** 2026-05-18 (session 34y)
**Module livré :** `engine.lineage_observer`
**Smoke :** `scripts/p71_lineage_observer_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré (dernière wave de la roadmap Black Mirror)

---

## Pourquoi

Dernière brique de la roadmap "Black Mirror civilisation virtuelle".
Les modules existants couvrent déjà tout :

- `engine.genome` (Sprint A4) : 256-D genome, 8 life stages, meiosis +
  mutation 1e-4
- `engine.agent.spawn_offspring` : héritage Big-Five midparent ±
  N(0, σ=0.05), lexicon idem, parents tracking, generation,
  offspring_count

Wave 40 ne fait que **observer cette mécanique existante** en
read-only et produit les analytics : arbres généalogiques,
distribution par génération, drift Big-Five, coefficient de
consanguinité Wright.

---

## Architecture

### Données déjà disponibles (Wave A4)

```
agents.parents[row]         = (pa, pb) ou (None, None) pour founders
agents.generation[row]      = max(gen[pa], gen[pb]) + 1
agents.offspring_count[row] = nombre d'enfants
agents.<trait>[row]         = midparent + N(0, 0.05) [11 traits Big-Five]
```

### Lecture read-only

```python
observe_lineage(sim) → LineageSnapshot {
    tick, n_alive, n_total_ever,
    n_founders, n_descendants, max_generation,
    generation_counts: Dict[gen → count],
    trait_mean_by_gen: Dict[gen → Dict[trait → mean]],
    trait_std_by_gen:  Dict[gen → Dict[trait → std]],
    top_reproducer_row, top_reproducer_offspring,
    founder_descendants_count: Dict[founder → N_descendants],
}
```

### Coefficient de consanguinité Wright F

Approximation hiérarchique :

```
F = 0.0     si parents partagent zéro ancêtre
F = 0.0625  si parents = cousins-germains
F = 0.25    si parents = frère/sœur (full siblings)
```

Algorithme : compare `build_ancestors(parent_a)` et
`build_ancestors(parent_b)`, détecte si les parents eux-mêmes
partagent un parent (siblings) ou plus loin (cousins).

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API + 11 traits Big-Five | OK |
| 2 | Fresh sim : 4 founders, 0 descendants, max_gen=0 | OK |
| 3 | `is_founder` distingue founders vs offspring | OK (child gen=1, founders gen=0) |
| 4 | Child parents recordés + generation incrémentée | OK |
| 5 | **Héritage intelligence : midparent 0.426, child 0.434, delta 0.008** | OK |
| 6 | `build_ancestors(child)` → {pa, pb} | OK |
| 7 | `build_descendants(parent)` → {child} | OK |
| 8 | **Inbreeding Wright F** : unrelated=0.000, full siblings child=**0.2500** | OK |
| 9 | Observer install déterminisme inter-sims | OK |

**Step 5 est la preuve génétique** : enfant intelligence = (0.282 + 0.570)/2 + ε = 0.434 (delta 0.008 << 3σ = 0.15). L'héritage Mendélien-like fonctionne.

**Step 8 est la preuve Wright F** : créer un couple frère/sœur
incestueux produit un enfant avec F = 0.25 exactement (valeur
théorique pour offspring of full siblings). Cohérent avec la
génétique des populations humaines.

---

## API publique

```python
from engine.lineage_observer import (
    # Configuration
    LineageConfig, LineageSnapshot, LineageHistory,
    LineageObserverState,
    TRAIT_NAMES, FOUNDER_PARENT_SENTINEL,

    # Read-only queries
    is_founder,                     # sim, row → bool
    build_ancestors,                # sim, row, *, max_depth → set[int]
    build_descendants,              # sim, row, *, max_depth → set[int]
    inbreeding_coefficient,         # sim, row → float (0, 0.0625, 0.25)

    # Snapshot
    observe_lineage,                # sim, cfg → LineageSnapshot

    # Sim integration
    install_lineage_observer,       # idempotent + wraps sim.step
    uninstall_lineage_observer,
    lineage_state_summary,          # diagnostic dict
)
```

### Usage type

```python
from engine.lineage_observer import (install_lineage_observer,
                                        LineageConfig,
                                        lineage_state_summary,
                                        inbreeding_coefficient)

install_lineage_observer(sim, LineageConfig(snapshot_every=100))

for _ in range(50_000):
    sim.step()           # cognition + spawn_offspring naturel

summary = lineage_state_summary(sim)
print(summary)
# {'n_alive': 247, 'n_founders': 12, 'n_descendants': 235,
#  'max_generation': 8, 'generation_counts': {0:12, 1:30, 2:78, ...},
#  'top_reproducer_row': 4, 'top_reproducer_offspring': 11,
#  'founder_descendants_count': {0:45, 1:38, 2:20, ...} }

# Detect incestuous offspring.
for row in range(sim.agents.n_active):
    F = inbreeding_coefficient(sim, row)
    if F > 0.1:
        print(f"agent {row} is inbred (F={F:.3f})")
```

---

## Limitations connues

- **Inbreeding F approximé** par tiers discrets (0, 0.0625, 0.25). Une
  formulation continue exigerait Wright's path counting algorithm.
- **Pas de tracking maternal/paternal** : on agrège les deux parents
  indistinctement. Pour mitochondrial / Y-chromosome lineages,
  instrumenter `spawn_offspring`.
- **Pas de sex** : tous les agents peuvent reproduire avec tous (sauf
  cognition prevention). Pour génétique sexuée, ajouter un attribut
  `sex` per-agent.
- **Pas d'arrêt fertilité** : un agent reste fertile tant qu'il est
  vivant. Pour menopause / age fertility curve, instrumenter
  `engine.cognition.decide` pour ActionKind.MATE.
- **Pas de drift cumulatif observable sans long run** : pour observer
  une dérive Big-Five sur 8+ générations, il faut une sim long-running
  (10K+ ticks).

---

## Branchements futurs

| Module | Intégration |
|---|---|
| `polity` | "Dynasties" = familles avec >N descendants en N générations. |
| `epidemic_observer` Wave 39 | Génétique × susceptibilité (HLA-like). |
| `cognition` | Mate choice par similarité Big-Five (sélection sexuelle). |
| Cultural diffusion (analytical Wave 31) | Compare cultural distance vs genetic distance. |
| Animation Wave 37 | Color agents par lignée founder origin (visualisation phylogénie). |
