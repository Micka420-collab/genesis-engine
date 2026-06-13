# Contribuer à Genesis Engine

Merci de t'intéresser à Genesis Engine ! Ce document explique **comment contribuer** au moteur, les **conventions** à respecter, et la **gouvernance** du projet.

> Genesis Engine est un laboratoire open-source d'artificial life dont l'objectif scientifique est de tester si la complexité civilisationnelle (langage, économie, religion, science, gouvernance) peut émerger spontanément à partir d'agents IA autonomes. Voir [README.md](README.md), [PROJECT-STATUS.md](PROJECT-STATUS.md) et [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx).

---

## Premier jour (First day)

Checklist pour être opérationnel en ~30 minutes :

```bash
git clone https://github.com/<ton-handle>/genesis-engine.git
cd genesis-engine
python -m venv .venv
# Windows: .venv\Scripts\activate  |  Linux/macOS: source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"

make doctor          # outils + imports
make smoke           # p0 baseline
make test-python     # pytest runtime/tests

# Rust world-engine (core, biome, worldgraph)
make rust-test

# Pont Python natif (optionnel)
make maturin-dev
PYTHONPATH=runtime python runtime/scripts/p73_rust_worldgraph_smoke.py

# Smokes réalisme (p72–p87, aligné validate-all)
make validate-all
# ou sous-ensemble rapide :
make smoke-realism
```

### Maturin / `genesis_world`

Depuis la racine du dépôt :

```bash
pip install maturin
cd native/world-engine
maturin develop -m crates/pybindings/Cargo.toml --release
```

Le module expose `PyWorld(seed=…).observe_chunk(cx, cy)` et `biome_at(x,y,z)`.
Le runtime utilise `engine.rust_bridge.create_py_world` (natif ou mock).

Lire ensuite : [`runtime/README.md`](runtime/README.md) (PYTHONPATH, smokes) et [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md) (où le projet en est scientifiquement).

---

## Où coder quoi

| Domaine | Stack | Chemin principal |
|---------|-------|------------------|
| Agents, cognition, civilisation | **Python** | `runtime/engine/` |
| Smokes & démos | **Python** | `runtime/scripts/` |
| Genesis monde, rendu, atmosphère | **Python** | `world_genesis.py`, `world_render.py`, `world_atmosphere.py` |
| Köppen, coupler, épidémie contact | **Python** | `koeppen_grid.py`, `multi_rate_coupler.py`, `epidemic_observer.py` |
| Chunks, WorldGraph, biome bas niveau | **Rust** | `native/world-engine/crates/` |
| Bindings Python ↔ Rust | **Rust + Python** | `crates/pybindings/`, `runtime/engine/rust_bridge.py` |
| Spec / ADR | **Markdown** | `adr/`, `architecture/`, `specs/` |
| Historique livraisons | **Doc** | `docs/sprints/` (index, pas déplacement massif) |

**Règle** : ne pas dupliquer la logique civilisation en Rust tant que le pont n'est pas explicitement requis par un ADR ou une issue.

---

## 🪜 Niveaux d'engagement

Tu peux contribuer **à toutes les échelles** :

| Niveau | Effort | Exemples |
|---|---|---|
| 🟢 **Tester** | 5 min | Lance les smoke tests, signale un bug |
| 🟢 **Docs** | 30 min | Corrige une typo, ajoute un exemple, traduis |
| 🟡 **Bug fix** | 1-3 h | Issue étiquetée `good first issue` |
| 🟡 **Calibration** | 2-6 h | Ajuste les paramètres Lotka-Volterra, fertility, etc. |
| 🟠 **Feature** | 1-3 j | Nouvelle action agent, nouveau sub-system L2/Reality |
| 🔴 **Architecture** | semaine+ | LLM cognition tier-2, PQC, multi-shard |

---

## 🚀 Premier setup

```bash
# 1. Fork le repo sur GitHub
# 2. Clone ton fork
git clone https://github.com/<ton-handle>/genesis-engine.git
cd genesis-engine

# 3. Crée un environnement isolé, puis installe le runtime Python
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# Optionnel : données Earth-anchored (Copernicus DEM + ESA WorldCover)
python -m pip install -e ".[earth,dev]"

# 4. Vérifie que tout marche
make doctor
make compile-python
make test-python

# Smoke plus long
make smoke
# attendu : "P0 SMOKE PASSED" en fin de sortie

# 5. Optionnel : run le multi-régions demo (~5 min)
python scripts/multi_region_demo.py
```

### Configurer ton remote upstream

```bash
git remote add upstream https://github.com/Micka420-collab/genesis-engine.git
git fetch upstream
```

Pour rester à jour :

```bash
git checkout main
git pull upstream main
```

---

## 🌳 Workflow de contribution

### 1. Trouve / crée une issue

- Va sur [Issues](https://github.com/Micka420-collab/genesis-engine/issues)
- Cherche `good first issue` ou `help wanted` si tu commences
- Sinon, ouvre une nouvelle issue **avant** de coder, pour valider l'approche

### 2. Crée ta branche

```bash
git checkout -b <type>/<short-description>
```

Conventions de naming :
- `feature/...` — nouvelle fonctionnalité
- `fix/...` — bug fix
- `perf/...` — optimisation
- `docs/...` — documentation
- `refactor/...` — réorganisation sans changement de comportement
- `test/...` — ajout/amélioration de tests

### 3. Code

Suis les **conventions** ci-dessous. Lance les smoke tests régulièrement.

### 4. Commit

Conventions de message :

```
<type>(<scope>): <short imperative description>

[longer body if needed]
```

- `feat(realism): add wildlife migration tick`
- `fix(cognition): handle empty near_agents in decide()`
- `perf(scan_chunk): bbox prefilter cuts 56% of calls`
- `docs(readme): add multi-region demo gif`

### 5. Push + Pull Request

```bash
git push origin feature/ma-contribution
```

Sur GitHub, ouvre une **Pull Request** vers `main`. Le template te demandera :

- ✅ Description du changement
- ✅ Issue liée (si applicable)
- ✅ Smoke tests qui passent
- ✅ Pas de régression sur `p0_smoke.py` / `p12_integration_full.py`
- ✅ Déterminisme préservé (voir ci-dessous)

---

## 📐 Conventions de code

### Python

- **Python 3.12+** (3.13 recommandé ; CI 3.12)
- **PEP 8** (line length 100, pas 79)
- **Type hints recommandés** mais pas obligatoires
- **Imports en tête de fichier uniquement** — pas d'imports inline au milieu d'une fonction (lisibilité, lint, revue)
- **Ordre des imports** : stdlib → third-party (numpy/rasterio) → `engine.*`

### Déterminisme **obligatoire**

C'est **la règle d'or** de Genesis Engine. Toute la simulation doit être bit-perfect reproductible.

❌ **Interdit** :

```python
import random
x = random.random()                  # ← non-déterministe

np.random.random()                   # ← global state
np.random.default_rng().random()     # ← non-seedé

import time
seed = int(time.time())              # ← wall-clock
```

✅ **Correct** :

```python
from engine.core import prf_rng

rng = prf_rng(sim.cfg.seed, ["my_subsystem", "purpose"], [agent_row, sim.tick])
x = rng.random()
```

Le namespace (2e arg) et les params (3e arg) doivent identifier de manière unique le contexte d'appel pour qu'un même call sur 2 runs identiques donne la même valeur.

### No-rewrite rule

Préfère **l'extension modulaire** à la réécriture des fichiers existants :

❌ Réécrire `cognition.py` pour ajouter HUNT
✅ Ajouter HUNT via Edit minimal + helper externe

❌ Remplacer `apply_decision`
✅ Monkey-patcher via `sim_5cd_integration.install(sim)`

Les patches minimaux (Edit ciblé) sont **systématiquement préférés** aux Write/rewrite. Voir comment `sim_5cd_integration.py` patche `_is_fertile`, `_seed_initial_project`, `apply_decision` sans toucher `sim.py` ni `cognition.py`.

### Smoke tests

**Tout nouveau sub-system doit livrer un smoke test** dans `runtime/scripts/pN_<name>_smoke.py` :

```python
import io, os, sys
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

# ... ton test ...

if __name__ == "__main__":
    raise SystemExit(main())
```

Le script doit :
- **Forcer UTF-8 stdout** (Windows cp1252 casse sinon)
- **Exit 0** sur succès, **≠0** sur échec
- **Imprimer** un résumé clair en fin
- **Écrire** un journal dans `runtime/journals/pN_<name>.jsonl`

### Moratoire observateurs (anti-treadmill)

Les phénomènes scientifiques read-only (`engine/*_observer.py` qui wrappent
`sim.step`) sont précieux mais bon marché à empiler. Le delta-audit du
2026-06-10 (`native/world-engine/AUDIT-DELTA-2026-06-10.md` §D1) a constaté
**14 vagues d'observateurs en 14 jours pour 0 item Phase A/B mergé**. Règle :

- **Pas de nouvelle vague d'observateur (Wave 64+)** tant que le tableau
  **Phase A** (`AUDIT-DELTA-*.md`) n'a pas **≥ 5/7 items à ✅** *et* qu'au
  moins **un item Phase B** n'est pas mergé.
- Tout nouvel observateur doit garder le coût cumulé de la chaîne **< 10 % du
  tick** — mesure avec `engine.observer_budget.measure_observer_overhead(...)`
  + `assert_observer_budget(...)`. L'idempotence install/uninstall est gardée
  par `tests/test_observer_budget.py`.

### Moratoire capacités géologie (anti-divergence Python↔Rust)

Le delta-audit 2026-06-12 (§D6) a constaté **3 capacités consécutives**
(C1 `surface_mineralization`, C2 `lithic_outcrop`, C3 `water_potability`) qui
dérivent toutes la géologie côté **Python** pendant que la crate Rust
`crates/geology` reste dormante — *double source de vérité, protocole non
documenté*. La **décision D5** ([ADR-0007](adr/0007-d5-geology-orphan-resolution.md))
a levé le blocage Cap. C4 **par garde-fou**, pas par renoncement :

- Toute **nouvelle capacité** qui surface un minéral « tell » à un agent
  **doit** ajouter ce minéral à `PY_TO_RUST` dans
  `tests/test_geology_cross_language_contract.py` (ou le justifier dans
  `RUST_ONLY`). Ce test fige l'enum `Mineral` Rust et le tell cuivre/malachite
  byte-exact ; il **casse le build** à la moindre divergence.
- Le **câblage moteur Rust** de `genesis-geology` (Cargo dep + `sample_at` +
  pybindings) reste un item **Phase A** (« D5-wiring »), à faire en session CI
  avec `cargo` — il n'est **plus** un bloqueur de C4.

### Tests d'intégration

`p12_integration_full.py` teste les 5 sub-systems ensemble. Si ton change touche un de ces sub-systems, **vérifie que p12 passe toujours** (4/5 ou 5/5).

### Runs longs : utiliser `experimental_run`

Tout run de simulation **> 1000 ticks** destiné à valider une hypothèse, produire une métrique citable, ou alimenter une comparaison cross-seed doit passer par
[`engine.experiment_manifest.experimental_run`](runtime/engine/experiment_manifest.py).
Il capture la provenance (git commit, hash du `pyproject.toml`, version Python,
plateforme), l'horodatage début/fin, le `world.summary()` final, et un
**fingerprint sha256** de l'état final — ce qui permet de comparer deux runs
bit-pour-bit dans un ledger de falsifiabilité.

```python
from engine.experiment_manifest import experimental_run
from engine.world_builder import WorldBuilder

with experimental_run("lausanne-baseline") as ctx:
    world = WorldBuilder("demo").anchor(46.51, 6.63).founders(20).build()
    world.run(2000)
    ctx.attach(world)
    ctx.note("baseline — aucune perturbation, seed défaut")

# → runtime/experiments/lausanne-baseline_<ISO_UTC>/
#     ├── manifest.json   (provenance + summary + fingerprint)
#     └── summary.json    (world.summary() brut)
```

Un crash dans le bloc `with` écrit quand même le manifest, avec une note
recensant l'exception — utile pour diagnostiquer les runs interrompus.

#### Pré-enregistrement (runs visant à valider une hypothèse)

Si le run vise à **tester une hypothèse** (et pas juste à mesurer une perf
ou à itérer sur un bug), copier
[`runtime/experiments/PREREGISTRATION_TEMPLATE.md`](runtime/experiments/PREREGISTRATION_TEMPLATE.md)
vers `runtime/experiments/<run_name>/preregistration.md`, le remplir **avant**
le `world.run()`, et le committer. Sans pré-enregistrement, le résultat est
une observation — pas une prédiction validée.

Une fois le run terminé et l'analyse faite, si la prédiction tenait, ajoute
une ligne dans [`FALSIFIABILITY.md`](FALSIFIABILITY.md) avec le
`state_fingerprint` du `manifest.json`.

---

## 🧪 Tests obligatoires avant PR

```bash
# Depuis la racine (recommandé)
make smoke
make test-python

# Ou depuis runtime/
cd runtime

# 1. Smoke baseline (sanity check)
python scripts/p0_smoke.py
# Doit terminer par "✅ P0 SMOKE PASSED"

# 2. Intégration (si ton change touche realism, lift, timewarp, genome, HUD)
python scripts/p12_integration_full.py
# Doit terminer par ">=3/5 subsystems passed integration"

# 3. Multi-régions (si ton change touche L1 / earth_loader / streamer)
python scripts/multi_region_demo.py
# Doit générer 4 dossiers exports/multi_region_*/ sans erreur
```

Si tu ajoutes un nouveau sub-system, ajoute aussi son smoke test au workflow CI.

---

## 🗺️ Architecture conformity

Toute contribution doit respecter [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx). Les sections les plus pertinentes :

- **§4-6** — Architecture haut-niveau (7 couches)
- **§8** — Worldgen procédural / earth-anchored
- **§10-13** — Agents IA + biologie + génétique + évolution
- **§14-22** — Faune, économie, construction, société, langage, politique
- **§23-25** — Mode 'God', multi-POV, time-warp
- **§26-27** — Persistance, événements globaux
- **§37-43** — Sécurité PQC (pour la couche plateforme)

**Si ta contribution écarte le doc**, ouvre une issue de discussion avant : l'architecture peut évoluer mais doit le faire de manière consciente.

---

## 🛡️ Sécurité

- **Vulnérabilités** : ouvre une [GitHub Security Advisory](https://github.com/Micka420-collab/genesis-engine/security/advisories) ou contacte `micka.delcato.rp@gmail.com` (PGP key dans [SECURITY.md](SECURITY.md)).
- **PQC** : toute contribution touchant la crypto doit utiliser ML-KEM / ML-DSA / SLH-DSA (NIST FIPS 203/204/205) en mode **hybride** avec X25519/Ed25519.
- **Avatars humains** : opt-in explicite, watermark cryptographique sur tout output dérivé.

---

## 📖 Éthique

Voir [`ETHICS.md`](ETHICS.md). En particulier :

- Pas d'optimisation pour générer de la "souffrance" agentique au-delà des limites homéostatiques nécessaires à la sélection.
- Toute fonctionnalité qui pourrait permettre à un opérateur de manipuler malicieusement la simulation doit être discutée publiquement.
- Le **Conseil Éthique externe** (3 philosophes + 3 chercheurs ML + 1 juriste) a un droit de veto sur les changements à fort impact — voir [ETHICS.md](ETHICS.md) section "Conseil Éthique".

---

## 🏛️ Gouvernance

- **Maintainer principal** : [Micka Delcato](https://github.com/Micka420-collab)
- **Décisions architecturales** : via ADRs (Architecture Decision Records) dans `architecture/` — ouvre une PR avec l'ADR proposé.
- **Roadmap** : [`PROJECT-STATUS.md`](PROJECT-STATUS.md) (synthèse), [`NEXT-SPRINT.md`](NEXT-SPRINT.md) (détail), [`ROADMAP.md`](ROADMAP.md), [`docs/ROADMAP-REALISME-TERRE.md`](docs/ROADMAP-REALISME-TERRE.md).
- **Releases** : suit le [Semantic Versioning](https://semver.org/). La version actuelle est en alpha pré-publique.

---

## 💬 Communication

- **Bug / feature** : [GitHub Issues](https://github.com/Micka420-collab/genesis-engine/issues)
- **Question générale** : [GitHub Discussions](https://github.com/Micka420-collab/genesis-engine/discussions)
- **Code review** : commentaires dans la PR

Sois respectueux·se. Lis le [Code of Conduct](CODE_OF_CONDUCT.md) (Contributor Covenant 2.1).

---

## 🎓 Pour aller plus loin

- 📄 [README.md](README.md) — vue d'ensemble
- 📜 [Genesis_Engine_Architecture_v1.0.docx](Genesis_Engine_Architecture_v1.0.docx) — spec contractuelle (53 sections)
- 🗺️ [ROADMAP.md](ROADMAP.md) — phases 0-5
- 📅 [NEXT-SPRINT.md](NEXT-SPRINT.md) — file de priorités vivante
- 🧬 [REALITY-ENGINE.md](REALITY-ENGINE.md) — détail du Reality Engine
- 🌍 [WORLD-CREATION-SOFTWARE.md](WORLD-CREATION-SOFTWARE.md) — API WorldBuilder/Export/Library
- ⚖️ [ETHICS.md](ETHICS.md) — considérations éthiques
- 🛡️ [SECURITY.md](SECURITY.md) — modèle de menace + PQC

---

**Merci de contribuer.** Chaque PR, chaque issue, chaque test rend Genesis Engine un peu plus réaliste, un peu plus reproductible, un peu plus utile à la communauté alife.
