# Biosphère 100 % émergente

Pipeline biologique intégré au tick `Simulation.step()` — **aucun fondateur scripté**
en mode `origins`. Les humains (agents sapients) n’apparaissent qu’après la chaîne
prébiotique → protocellules → microbes → flore → faune → primates.

## Chaîne évolutive

```
Monde viable (appraise par cellule)
    → substrat prébiotique (accumulation locale)
    → protocellules (division + mutation de complexité)
    → cyanobactéries (graduation vers plant_evolution)
    → montée O₂ + clades végétaux (mode ancient)
    → espèces animales (phylogénie + O₂, mode ancient)
    → population primates (monkeys)
    → agents sapients (max 2, espacés)
    → reproduction + stades de civilisation (événements observés)
```

## Modules

| Fichier | Rôle |
|---------|------|
| `runtime/engine/appraise.py` | Viabilité monde + readiness reproduction |
| `runtime/engine/protocell_evolution.py` | Autocatalyse / fission des protocellules |
| `runtime/engine/biosphere_stack.py` | Installe photo + plantes + faune en mode `ancient` |
| `runtime/engine/life_emergence.py` | Orchestration, stades biosphère & civilisation |
| `runtime/engine/animal_evolution.py` | Émergence d’espèces par parent_clade + O₂ |

## Configuration (`SimConfig`)

| Champ | Défaut | Description |
|-------|--------|-------------|
| `life_emergence` | `True` | Appraisal + fertilité émergente |
| `full_biosphere` | `False` | Stack photo/flore/faune (auto si `emergent_origins`) |
| `emergent_origins` | `False` | `founders=0`, pas de cluster scripté |
| `max_emergent_founders` | `2` | Plafond sapients émergents |
| `substrate_threshold` | `0.85` | Seuil substrat (mode legacy direct désactivé) |

## Lancement

```bash
cd runtime
python run.py origins
# ou
python run.py custom --emergent-origins --ticks 8000 --bounds-km 2.0 --drive-accel 12000
```

Snapshot : clé `life_emergence` dans `sim.snapshot()` — `biosphere_stage`,
`total_protocells`, `oxygen_pct`, `monkeys_global`, `emergent_sapients`.

## Journalisation

- Fondateurs / sapients émergents → événement `founding` (`cum_foundings`), **pas** `birth`
- Divisions protocellulaires / microbes → `innovation`

## Tests

```bash
PYTHONPATH=runtime python -m pytest runtime/tests/test_life_emergence.py -q
```

## Références scientifiques (inspiration)

- Abiogenèse par compartiments autocatalytiques (auto-réplication locale)
- Mode `ancient` plantes : cyanobactéries puis clades selon O₂
- Mode `ancient` faune : arthropodes puis espèces selon phylogénie et O₂
