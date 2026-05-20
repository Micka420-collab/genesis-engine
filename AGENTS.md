# Genesis Engine — guide agents

**Lire en premier :** [`docs/MASTER-SCALE-PROMPT-v2.md`](docs/MASTER-SCALE-PROMPT-v2.md) (identité, couches L0–L4, commandes, contraintes).

| Besoin | Document |
|--------|----------|
| Manifeste ZERO PRE-SCRIPT | [`docs/EMERGENCE-SIM-v2.md`](docs/EMERGENCE-SIM-v2.md) |
| État livré + tests | [`PROJECT-STATUS.md`](PROJECT-STATUS.md) |
| Earth Console | [`docs/EARTH-CONSOLE.md`](docs/EARTH-CONSOLE.md) |
| Grille réalisme **~76 %** (objectif 80 %) | [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) |
| Audit tick path | [`runtime/AUDIT.md`](runtime/AUDIT.md) |

## Commandes (Windows)

```powershell
cd "F:\DEvOps\projet alpha\genesis-engine"
.\earth-console.ps1
cd runtime; python -m pytest tests/ -q
```

## Règles immuables

- Pas de comportement civilisationnel scripté sur le tick path.
- Lois L0 via `earth_laws.py` / `physics_layer.py` uniquement.
- Cognition Earth Console : `wire_emergence_v2` + `neat_brain.genome_decide`.
- Tout changement : **145** tests pytest verts + KPIs `emergence_metrics` si comportement nouveau.
- Hydrologie Earth Console : `hydrology_mode=sv1d` · overlay 2D **Flux eau**.
