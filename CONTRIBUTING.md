# Contribuer à Genesis Engine

Merci de t'intéresser à Genesis Engine ! Ce document explique **comment contribuer** au moteur, les **conventions** à respecter, et la **gouvernance** du projet.

> Genesis Engine est un laboratoire open-source d'artificial life dont l'objectif scientifique est de tester si la complexité civilisationnelle (langage, économie, religion, science, gouvernance) peut émerger spontanément à partir d'agents IA autonomes. Voir [README.md](README.md) et [`Genesis_Engine_Architecture_v1.0.docx`](Genesis_Engine_Architecture_v1.0.docx).

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

# 3. Installe les dépendances
pip install numpy rasterio pyproj

# 4. Vérifie que tout marche
cd runtime
python scripts/p0_smoke.py
# → attendu : "✅ P0 SMOKE PASSED" en fin de sortie

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

- **Python 3.13+**
- **PEP 8** (line length 100, pas 79)
- **Type hints recommandés** mais pas obligatoires
- **Imports** : stdlib → third-party (numpy/rasterio) → engine (`engine.xxx`)

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

### Tests d'intégration

`p12_integration_full.py` teste les 5 sub-systems ensemble. Si ton change touche un de ces sub-systems, **vérifie que p12 passe toujours** (4/5 ou 5/5).

---

## 🧪 Tests obligatoires avant PR

```bash
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
- **Roadmap** : trackée dans [`NEXT-SPRINT.md`](NEXT-SPRINT.md) et [`ROADMAP.md`](ROADMAP.md), maintenue par le mainteneur principal après discussion publique.
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
