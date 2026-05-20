# Wave 33 — Stone-Age Evolution Observer

**Date :** 2026-05-18 (session 34q)
**Module livré :** `engine.stone_age_evolution`
**Smoke :** `scripts/p63_stone_age_evolution_smoke.py` — **9/9 PASS**
**Status :** ✅ Livré

---

## Pourquoi (et mea culpa)

L'utilisateur m'a redrigé après que j'ai dérivé en livrant Waves 28-32
qui sont des **solveurs analytiques top-down** (Poisson-disk pour
settlements, Dijkstra MST pour roads, gravité pour trade, Laplacien
pour culture, Voronoi pour polities). Ces waves prédisent où seront
les phénomènes ; elles ne les observent pas émerger.

Rappel de la règle absolue du projet :

> "Tout doit émerger comme s'ils étaient à l'âge de pierre, les voir
> évoluer comme notre histoire mais avec leur libre arbitre. Rien qui
> est pré-programmé. Comme l'apparition de la vie sur Terre."

Wave 33 corrige : **observateur read-only** qui lance la simulation
existante (Simulation + bootstrap_genesis_sim + tous les modules
agent-driven déjà émergents : `cognition`, `invention`, `agriculture`,
`writing`, `polity`, `cognitive_plasticity`, …) et **capture
périodiquement ce qui émerge**, sans rien décider ni scripter.

---

## Architecture

```
1. sim = Simulation(SimConfig(founders=12, cultures=3, ...))
2. bootstrap_genesis_sim(sim)                  # Wave 16-19 substrate
3. install_polity, install_invention, etc.     # modules agent-driven
4. for tick in range(N):
       sim.step()                              # cognition décide TOUT
       if tick % snapshot_every == 0:
           snap = take_snapshot(sim)           # READ-ONLY
       accumulate_trail(snap.agents)           # READ-ONLY
5. return EvolutionHistory(snapshots, trail_density)
```

Le harness fait **3 lignes utiles** (init + step + observe). Tout le
reste de l'évolution est dans `engine.cognition`, `engine.invention`,
etc. — déjà existants depuis les Waves 1-15.

---

## Phénomènes émergents observés (read-only)

| Phénomène | Source observée | Décision émergente |
|---|---|---|
| **Settlements** | `observe_clusters(agents)` DBSCAN | Where agents stop wandering |
| **Trails / roads** | `accumulate_trail(positions)` | Where agents walk repeatedly |
| **Polities** | `engine.polity` Wave 9c state | Leader election by prestige × ambition |
| **Inventions** | `engine.invention.InventionRegistry` | try_invent par curiosity × matériau |
| **Buildings** | `engine.building_discovery` state | Voxel placements → archetypes |
| **Drawings** | `engine.art_discovery` state | Pigment × surface fingerprints |
| **Language** | `engine.communication` lexicons | Drift + heritage per culture |
| **Writing** | `engine.writing` inscriptions | Material-bound recipes/laws |
| **Agriculture** | `engine.agriculture` culture_seed_library | forage discoveries |
| **Metallurgy** | `engine.metallurgy` smelt events | ore + fuel + furnace |

**Aucune** de ces dynamiques n'est pilotée par Wave 33. Wave 33 LIT.

---

## Smoke test — 9 checks

| # | Vérification | Résultat |
|---|---|---|
| 1 | API publique (`observe_*`, `take_snapshot`, `run_*`) | OK |
| 2 | Stone-age starting state : 6 alive, 0 polities, 0 inventions | OK |
| 3 | Snapshots à intervalles corrects (4 sur 30 ticks / snap_every=10) | OK |
| 4 | Trail density populé (5×5, sum=186) | OK |
| 5 | Clusters observés naturellement (4/4 snapshots) | OK |
| 6 | Déterminisme inter-runs : SHA-256 snapshots identiques | OK |
| 7 | **Read-only : n_active, positions, alive bit-identiques après 5 snapshots** | OK |
| 8 | `evolution_summary` plausible | OK |
| 9 | Ticks monotones (0, 10, 20, 30) | OK |

**Le step 7 est le check le plus important** : prouve que l'observation
ne mutate JAMAIS sim. C'est le contrat read-only.

---

## Exemple de trajectoire émergente (12 founders, 3 cultures, 200 ticks)

```
tick   0:  12 alive, 2 clusters initial
tick  40:  12 alive, 3 clusters    (un cluster s'est scindé)
tick  80:  12 alive, 3 clusters stables
tick 120:  3 clusters stables, positions précises :
              cluster 0: 3 agents à (-76, 130) m, radius 1m (campement serré)
              cluster 1: 7 agents à (-40, -74) m, radius 109m (groupe large)
              cluster 2: 2 agents à (86, 116) m, radius 0m (dyade)
tick 160:  positions identiques (système stable)
tick 200:  positions identiques

trail_max_visits = 551 sur le cell le plus fréquenté
trail_cells_visited = 19 cellules touchées
```

**Personne n'a scripté ces positions.** Les agents les ont choisies via
`engine.cognition.decide()` en fonction de leurs needs (hunger, thirst,
shelter) et de leurs préférences (Big Five, plasticity).

À 200 ticks (~3 sim-min avec accel 1500), pas encore d'inventions ni
de polities. C'est cohérent : ils n'ont pas eu le temps. À 10 000+
ticks, on observerait l'émergence du Néolithique : agriculture par
forage discoveries, inscriptions sur clay tablets, leaders élus...

---

## API publique

```python
from engine.stone_age_evolution import (
    # Configuration + types
    StoneAgeConfig,
    AgentSnapshot,
    ClusterObservation,
    EvolutionSnapshot,
    EvolutionHistory,

    # Observation read-only (ne modifient JAMAIS sim)
    observe_agents,                    # snapshot positions + meta
    observe_clusters,                  # DBSCAN-like proto-settlements
    observe_polities,                  # engine.polity Wave 9c state
    observe_inventions,                # engine.invention registry
    observe_buildings,                 # engine.building_discovery
    observe_languages,                 # lexicon drift signatures
    observe_inscriptions,              # engine.writing
    observe_artifacts,                 # engine.art_discovery
    take_snapshot,                     # tout dans un EvolutionSnapshot

    # Trail accumulation (read-only sur agents)
    accumulate_trail,

    # Runner principal
    run_stone_age_evolution,           # sim, cfg → EvolutionHistory

    # Reporter
    evolution_summary,
)
```

### Usage type — observation d'une longue évolution

```python
from engine.sim import Simulation, SimConfig
from engine.genesis_bootstrap import bootstrap_genesis_sim
from engine.stone_age_evolution import (StoneAgeConfig,
                                            run_stone_age_evolution,
                                            evolution_summary)

# 1. Sim avec founders stone-age
sim = Simulation(SimConfig(
    name="long_run", seed=0xCAFE,
    founders=20, max_agents=200,
    bounds_km=(2.0, 2.0), spawn_radius_m=200.0,
    drive_accel=1500.0, cultures=4,
))

# 2. Substrate géographique + provinces minéralisées + climat + ...
bootstrap_genesis_sim(sim)

# 3. (Optionnel) installer les autres modules émergents :
# install_polity(sim), install_invention(sim), install_writing(sim), ...

# 4. Run K ticks et observe
cfg = StoneAgeConfig(n_ticks=10000, snapshot_every=500)
history = run_stone_age_evolution(sim, cfg)

# 5. Analyse
print(evolution_summary(history))
# → first_invention_tick, first_polity_tick, first_inscription_tick, ...
```

---

## Statut des Waves 28-32 (analytical baselines, pas ground truth)

Les Waves 28-32 livrées avant Wave 33 sont à considérer comme
**baselines analytiques de référence** :

| Wave | Module | Statut |
|---|---|---|
| 28 | `settlement_emergence` | Score multi-critères → prédit OÙ une civilisation idéale s'installerait. Utile pour comparer aux clusters observés. |
| 29 | `road_network` | MST Dijkstra → trajet OPTIMAL entre villes. Utile pour comparer aux trails émergents. |
| 30 | `trade_flow` | Gravité → flux PRÉDITS par modèle. Utile pour comparer aux inventaires qui circulent réellement. |
| 31 | `cultural_diffusion` | Laplacien → diffusion ANALYTIQUE. Utile pour comparer au lexicon drift de `engine.communication`. |
| 32 | `polity_emergence` | Voronoi sur cultures → carte POLITIQUE PRÉDITE. Utile pour comparer aux polities émergentes de `engine.polity` Wave 9c. |

Ces modules sont conservés car leurs sorties servent de **point de
comparaison scientifique** ("la civilisation émergente s'est-elle
développée près de l'optimum analytique ou ailleurs ?"). Ils ne sont
PAS la simulation canonique.

**Wave 33 est la simulation canonique** depuis aujourd'hui.

---

## Limitations connues

- **Run-time** : 200 ticks tournent en ~5-10s. Pour voir vraiment
  bronze age + écriture, il faut ~10K-100K ticks (5 min — 1h CPU).
- **DBSCAN-like clustering** : O(N²) pairwise distances. À N>500
  agents, passer à un grid-based index.
- **Trail density flat** : on n'a pas (encore) de visualisation 2D des
  trails. Wave 34+ pourrait ajouter un overlay PNG des paths les plus
  fréquentés.
- **Pas de death tracking** : `n_alive_track` montre la trajectoire
  population, mais pas qui est mort quand. Pour la démographie fine,
  lire `sim.annalist` events.
- **Modules optionnels** : si `install_polity` etc. n'a pas été
  appelé, les `observe_polities` etc. retournent `{"installed": False}`.
  L'observer ne casse pas — il rapporte simplement l'absence.

---

## Branchements futurs

| Module | Intégration |
|---|---|
| **Wave 34** | Animation timelapse : rendu des snapshots PNG → GIF montrant la civilisation grandir. |
| **Wave 35** | Comparaison observe vs analytical : overlay des settlements émergents (Wave 33) sur les sites prédits (Wave 28). |
| `dashboard` | Live tracking pendant la sim. |
| Long-run validation | Run 10K + snapshot tous les 100 ticks → premier polity, première inscription, … |
