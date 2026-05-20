# Wave 39 — Epidemic Observer (SIR + R0 émergent)

**Date :** 2026-05-18 (session 34x)
**Module livré :** `engine.epidemic_observer`
**Smoke :** `scripts/p70_epidemic_observer_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi

Le moteur `engine.physiology` (Wave 3) simule déjà 3 pathogènes avec
R0 + transmission vectors :
- **cholera** waterborne via DRINK sur water contaminée
- **flu** airborne via near-agent dans envelope thermique
- **wound_infection** via injuries × dirtiness × Wave 34 anatomy

Mais aucune **observation populationnelle** des épidémies. Wave 39
ajoute la couche analytique read-only :

- Courbes SIR (Susceptible / Infectious / Recovered)
- Estimation R0 empirique depuis la croissance d'infections
- Snapshots par cadence configurable
- Multi-pathogène simultané

C'est l'outil scientifique pour observer des pandémies émergentes — pas
les scripter.

---

## Architecture

### Classification SIR par seuils

```
Susceptible : load < I_th  AND  immune < R_th
Infectious  : load ≥ I_th
Recovered   : load < I_th  AND  immune ≥ R_th

Default thresholds: I_th = 0.10, R_th = 0.20
```

Pour chaque pathogène, on lit les arrays exposés par physiology :
- ``sim._physio_fields.<pathogen>_load``
- ``sim._physio_fields.immune_<pathogen>``

### Estimation R0 émergent

```python
estimate_r0_for_pathogen(history, pathogen, window=3):
    recent = history.snapshots[-window:]
    new_total = Σ s.per_pathogen[pathogen].new_infections_this_window
    mean_inf  = mean(s.per_pathogen[pathogen].n_infectious)
    R0_est    = new_total / max(mean_inf, 1.0)
```

Approximation simple. Pour des chaînes de transmission tracées
individuellement, il faudrait instrumenter le moment exact où chaque
agent attrape la maladie — out of scope ici.

### Snapshot wrapper (idempotent, comme Wave 33)

```
install_epidemic_observer(sim, cfg):
    sim._epidemic_state = EpidemicObserverState(cfg, history=...)
    sim.step = wrap(sim.step):
        run inner step
        if tick % snapshot_every == 0:
            snap = take_epidemic_snapshot(sim, cfg, prev_inf)
            history.snapshots.append(snap)
            r0_per_pathogen = estimate_r0(history, p, window)
```

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API + 3 default pathogens (cholera, flu, wound) | OK |
| 2 | Sans physiology → tous infectious=0 | OK |
| 3 | Physiology + 0 infection → tous susceptibles (S=8/8) | OK |
| 4 | Injection manuelle cholera_load=0.5 sur 2 agents → infectious=2 | OK |
| 5 | **S + I + R = n_alive** (conservation populationnelle) | OK (6+2+0=8) |
| 6 | 3 pathogènes simultanés indépendants | OK |
| 7 | **R0 cholera = 0.750** (non-négatif fini, déclin sur cette seed) | OK |
| 8 | Déterminisme inter-sims (5 snapshots bit-identiques) | OK |
| 9 | Cadence wrapper respectée (4 snapshots / 19 ticks @ every=5) | OK |

**Step 5 est la preuve de cohérence SIR** : la conservation
populationnelle est respectée. Step 7 produit un R0 réaliste —
0.750 < 1.0 signifie épidémie en déclin (sur cette seed), exactement
ce qu'on observe en épidémiologie réelle quand l'immunité grippe le
pathogène.

---

## API publique

```python
from engine.epidemic_observer import (
    # Configuration
    DEFAULT_PATHOGENS,            # ("cholera", "flu", "wound")
    EpidemicConfig,               # snapshot_every, thresholds, window

    # Data
    PathogenSnapshot,             # S/I/R + mean_load + R0_estimate per pathogen
    EpidemicSnapshot,             # all pathogens at one tick
    EpidemicHistory,              # full trajectory
    EpidemicObserverState,

    # Read-only observation
    observe_pathogen,             # sim, pathogen → PathogenSnapshot
    take_epidemic_snapshot,       # sim → EpidemicSnapshot (all)
    estimate_r0_for_pathogen,     # history, pathogen, window → R0 float

    # Sim integration
    install_epidemic_observer,    # sim, cfg → state (idempotent)
    uninstall_epidemic_observer,
    epidemic_state_summary,       # diagnostic dict
)
```

### Usage type

```python
from engine.physiology import install_physiology
from engine.epidemic_observer import (install_epidemic_observer,
                                         EpidemicConfig,
                                         epidemic_state_summary)

install_physiology(sim)          # pathogens active
install_epidemic_observer(
    sim, EpidemicConfig(snapshot_every=10, r0_window_snapshots=5))

# Manual seed of an outbreak (cholera in agent 0).
sim._physio_fields.cholera_load[0] = 0.8

for _ in range(5000):
    sim.step()                   # cognition + physiology + observer

print(epidemic_state_summary(sim))
# → per_pathogen.cholera: {n_susceptible, n_infectious, n_recovered,
#                           mean_load, max_load, mean_immune, r0_estimate}
```

---

## Limitations connues

- **R0 est une approximation populationnelle**. Pour R0 individuel
  (chaîne de transmission tracée), il faudrait instrumenter
  l'événement exact où agent A → B. Hors scope ici.
- **Pas de spread sur road network** (Wave 29). Physiology utilise une
  transmission spatiale (near-agent + water cell). Pour modéliser une
  pandémie qui voyage le long des routes commerciales Wave 30, ajouter
  un term de transmission boost si deux agents partagent une edge.
- **Pas de mutations pathogène**. Chaque pathogène est une espèce
  unique. Pour variants (cf. COVID variants), ajouter un attribut
  ``strain_id`` par instance load.
- **Pas de vaccination**. Immune ne peut être que naturellement acquis
  via survie. Pour vaccination, Wave 39b pourrait ajouter une
  ``ActionKind.VACCINATE`` qui boost immune sans passer par
  l'infection.
- **3 pathogènes fixes**. Pour ajouter smallpox, plague, etc., il
  faut étendre `engine.physiology.PATHOGEN_NAMES` + ses tables (cf.
  son sprint Wave 3 / cholera).

---

## Branchements futurs

| Module | Intégration |
|---|---|
| **Wave 40** | Genetics → certains génomes plus susceptibles à certaines pathogènes (HLA-mimicking). |
| Combat (Wave 38) | Wounds non soignés → wound_infection automatique (déjà partiellement câblé via physiology). |
| Polities (Wave 9c) | Polities en guerre = transmission directe entre soldats. |
| Animation timelapse Wave 37 | Overlay infectious agents en rouge dans les GIFs. |
| `engine.cognition` | Agent malade (load > 0.3) → comportement FLEE prioritaire + cherche shelter. |
