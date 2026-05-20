# Laboratoire d'évolution d'algorithmes

Boucle **générer → tester → sélectionner → améliorer → recommencer** pour découvrir des opérateurs monde **inédits** dans Genesis Engine.

## Opérateurs nouveaux (`novel_operators.py`)

| ID | Idée | Effet sur le monde |
|----|------|-------------------|
| `mycorrhizal_mesh` | Réseau fongique | Diffusion nutriment sol → boost précip forêts |
| `aurora_ionosphere` | Couplage polaire | Vent → chauffage surface \|lat\| > seuil |
| `orographic_resonance` | Onde orographique | Précip modulée par relief (sin phase) |
| `plate_stress_cascade` | Failles tectoniques | Stress aux frontières de plaques → relief |

Aucun de ces quatre opérateurs n'existait ailleurs dans le repo avant ce labo.

## Fitness (multi-critères)

Après application sur une copie Genesis :

- Cohérence du vent (alignement voisins)
- Entropie des biomes (diversité)
- Score orographique (corr relief ↔ précip)
- Balance énergétique (T et pluie continentales plausibles)
- Pénalité / bonus selon amplitude de changement

## Boucle évolutive (`algorithm_evolution.py`)

1. **Générer** — population de `OperatorGenome` (opérateur + paramètres bornés)
2. **Tester** — `evaluate_genome` sur grille Genesis
3. **Sélectionner** — élitisme + tournois k=3
4. **Améliorer** — croisement + mutation PRF déterministe
5. **Recommencer** — `improve_until_plateau` si gain < seuil

## CLI

```bash
cd runtime
python scripts/run_algorithm_evolution.py --generations 12 --population 24 --plateau
python scripts/p85_algorithm_evolution_smoke.py
```

## API (Earth Console / dashboard)

- `GET /api/algorithm_lab` — état du labo
- `GET /api/algorithm_lab/discover?generations=8&population=16&plateau=1` — lance une évolution
- `GET /api/algorithm_lab/install` — installe le meilleur sur le monde Genesis live

## Activer sur une sim

```python
wire_emergence_v2(sim, algorithm_lab=True)
# ou
SimConfig(..., algorithm_lab=True)
```

## Philosophie

ZERO PRE-SCRIPT : les opérateurs ne commandent pas les agents ; ils **mutent le substrat** (vent, T, précip, relief). La sélection favorise des mondes **cohérents et divers**, pas une civilisation scriptée.
