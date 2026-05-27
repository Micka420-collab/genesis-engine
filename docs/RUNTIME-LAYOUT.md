# Genesis Engine — Canonical Source-Tree Layout

**Statut :** décision gravée 2026-05-27. Successeur de [`PROJECT-VIABILITY.md`](./PROJECT-VIABILITY.md) §"Authoritative Entry Points" (qui pointait encore vers `scaffolding/crates` comme Rust de référence — désormais obsolète).

Ce document est la **source unique de vérité** sur "où vit le code". Il a priorité sur tout autre doc qui dirait le contraire — mettre les autres à jour, pas faire l'inverse.

---

## TL;DR — matrice de décision

| Chemin                                     | Statut             | Rôle actuel                                          | Action suivante                       |
|--------------------------------------------|--------------------|------------------------------------------------------|---------------------------------------|
| `runtime/engine/`                          | ✅ **CANONICAL**   | Package Python officiel — toutes les vagues 1-72+    | (rien — c'est l'authoritative)        |
| `runtime/tests/`                           | ✅ **CANONICAL**   | Tests pytest officiels                                | (rien)                                 |
| `runtime/scripts/p*_smoke.py`              | ✅ **CANONICAL**   | Smokes par vague (p0–p111)                            | (rien)                                 |
| `runtime/run.py`                           | ✅ **CANONICAL**   | Launcher unifié (`make terre`, `make civilization`)   | (rien)                                 |
| `native/world-engine/`                     | ✅ **CANONICAL**   | Workspace Rust actif — build de la wheel `genesis_world` | Continuer Phase A roadmap            |
| `runtime/genesis/`                         | 🪦 **MORT**        | Bloqué `raise ImportError` à l'import (cf. `__init__.py:7`) | **Supprimer** — zéro importeur Python   |
| `runtime-phase5/`                          | 🪦 **MORT**        | Fork archéologique self-contained, exclu de pytest    | **Supprimer** — zéro importeur externe  |
| `scaffolding/crates/`                      | ⚠️  **FORK ACTIF** | Workspace Rust historique — produit aussi `genesis_world` !  | **Résoudre conflit** (cf. §3 ci-dessous) |

---

## 1. Pourquoi ce document existe

Le 16 mai 2026, [`PROJECT-VIABILITY.md`](./PROJECT-VIABILITY.md) déclarait :

> - Python operational runtime: `runtime/engine`
> - Rust long-term core: `scaffolding/crates`
> - Deprecated prototype: `runtime/genesis`

Entre le 16 et le 27 mai (~11 jours), un **deuxième** workspace Rust est apparu sous `native/world-engine/`, et le `Makefile` + `.github/workflows/ci.yml` ont été redirigés pour builder la wheel Python depuis `native/world-engine/crates/pybindings` **au lieu de** `scaffolding/crates/ge-py`. PROJECT-VIABILITY.md n'a pas été mis à jour. Résultat : trois sources de vérité contradictoires (le doc, la CI, et le `Makefile`), et deux crates qui produisent le **même module Python `genesis_world`**.

Ce document est la résolution.

---

## 2. Le problème "deux wheels, un module"

### 2.1 Le diagnostic

Deux crates PyO3 distincts déclarent `#[pyclass(name="PyWorld", module="genesis_world")]` et exposent leur lib comme `name = "genesis_world"` + `crate-type = ["cdylib"]` :

| Crate                                          | Lignes  | Construit par                                                              | API surface                                                            |
|------------------------------------------------|---------|----------------------------------------------------------------------------|------------------------------------------------------------------------|
| `scaffolding/crates/ge-py`                     | 1762    | `cd scaffolding && maturin develop --release`                              | `PyWorld`, `sample_terrain_chunk`, `py_scan_chunk`, `py_scan_resources`, `py_batch_near_agents`, `py_batch_scan_resources`, `py_tick_drives`, `py_regen_chunk` |
| `native/world-engine/crates/pybindings`        | 369     | `make maturin-dev` → `cd native/world-engine && maturin develop -m crates/pybindings/Cargo.toml --release` | `PyWorld` (set_voxel, apply_pending, save_snapshot, restore_snapshot, observe_chunk) |

Les deux installent **le même** module `genesis_world` dans le `site-packages` du venv. Celui qui passe en dernier gagne et écrase l'autre.

### 2.2 Les smokes en dépendent — différemment

Les smokes Python importent depuis `genesis_world` des symboles qui n'existent que dans **l'une** des deux crates :

| Smoke                                | Symbole importé                       | Présent dans                       |
|--------------------------------------|---------------------------------------|------------------------------------|
| `p73_rust_worldgraph_smoke.py`       | `genesis_world.PyWorld` (set_voxel, apply_pending) | `native/world-engine/pybindings`  |
| `p89_rust_benchmark_smoke.py`        | `sample_terrain_chunk`                | `scaffolding/ge-py`                |
| `p94_rust_full_chunk_smoke.py`       | `observe_chunk`                       | les deux                           |
| `p104_rust_regen_smoke.py`           | `py_regen_chunk`                      | `scaffolding/ge-py`                |
| `p108_batch_near_smoke.py`           | `py_batch_near_agents`                | `scaffolding/ge-py`                |
| `p109_rust_drives_smoke.py`          | `py_tick_drives`                      | `scaffolding/ge-py`                |
| `p110_batch_scan_smoke.py` / p111    | `py_batch_scan_resources`             | `scaffolding/ge-py`                |

**Conclusion :** la suite complète `make validate-all` ne peut **pas** passer avec une seule wheel installée. Le seul moyen actuel d'avoir tous les smokes verts est de switcher entre les deux wheels — invisible dans la CI parce que la CI ne builde que `pybindings` et ne lance que `p73` côté Rust.

Cette ambiguïté a été masquée par le `try_import_genesis_world()` de [`runtime/engine/rust_bridge.py`](../runtime/engine/rust_bridge.py) qui retombe gracieusement sur un mock Python si l'import échoue — donc les smokes ne crashent pas, ils passent en mode dégradé sans qu'on le voie.

### 2.3 Trois options pour résoudre

| Option                           | Effort       | Avantage                                                | Inconvénient                          |
|----------------------------------|--------------|---------------------------------------------------------|---------------------------------------|
| **A. ge-py absorbe pybindings**  | 2-3 sem      | Garde toutes les API smoke (1762 lignes mûres)          | Réintroduit le legacy ge-* ; perd la roadmap clean de `native/world-engine` |
| **B. pybindings absorbe ge-py**  | 4-6 sem      | Architecture moderne (worldgraph DAG, content-addressed cache, snapshot rkyv) | Réécrire ~1400 lignes de fonctions Rust ; smokes p89-p111 **rouges** pendant la migration |
| **C. Renommer ge-py → `genesis_world_legacy`** | 0.5 j | Coexistence propre dans le même venv ; smokes choisissent leur module ; **non-bloquant** | Dette technique nommée explicitement (acceptable si on s'engage à terminer B après) |

**Recommandation :** **C immédiatement, puis B sur 3 mois.** C débloque la CI honest-to-god (toutes les smokes vertes ensemble), B livre la fusion propre. A est piégeux : on revient en arrière sur la roadmap "next-level" du moteur.

---

## 3. Plan de nettoyage immédiat (≤ 1 journée dev)

### Étape 1 — Supprimer `runtime/genesis/` (morte)

Le `__init__.py` lève `ImportError` immédiatement et 0 module Python l'importe (vérifié via `grep -r "^from genesis\." runtime/`). Le commentaire "host filesystem does not currently allow file deletion" est obsolète : sous Windows, la suppression normale du dossier marche. Si elle bloque, c'est parce qu'un Python `__pycache__` lock-tient un fichier — fermer tous les processus Python puis :

```powershell
Remove-Item -Recurse -Force "runtime/genesis"
```

Test post-suppression : `make test-python` + `make smoke-realism` doivent passer (ils ne dépendent pas de `genesis.*`).

### Étape 2 — Supprimer `runtime-phase5/` (morte)

Self-contained, 0 importeur externe (vérifié via `grep -rE "phase5\.|runtime-phase5" runtime/`). Retirer aussi les références dans `Makefile:39` (`compile-python` compile encore phase5) :

```diff
 compile-python:
-	$(PYTHON) -m compileall -q runtime/engine runtime/scripts runtime/tests runtime-phase5/engine runtime-phase5/tests
+	$(PYTHON) -m compileall -q runtime/engine runtime/scripts runtime/tests
```

Et retirer la mention archaïque dans `pyproject.toml:42-46` (le commentaire qui dit "runtime-phase5/tests was here").

Test post-suppression : `make compile-python && make test-python`.

### Étape 3 — Renommer la wheel scaffolding pour éliminer le conflit

Dans `scaffolding/crates/ge-py/Cargo.toml` :

```diff
 [lib]
-name = "genesis_world"
+name = "genesis_world_legacy"
 crate-type = ["cdylib"]
```

Dans `scaffolding/pyproject.toml` :

```diff
 [project]
-name            = "genesis_world"
+name            = "genesis_world_legacy"
```

Dans `scaffolding/crates/ge-py/src/lib.rs`, mettre à jour les attributs `#[pyclass(name = "PyWorld", module = "genesis_world_legacy")]` et le `m.add_class::<PyWorld>()?` reste dans le PyModule décoré `#[pymodule] fn genesis_world_legacy(...)`.

Dans `runtime/engine/rust_bridge.py:89-95`, `try_import_genesis_world()` tente d'importer `genesis_world` d'abord, puis fallback `genesis_world_legacy` — les smokes qui veulent la legacy peuvent l'importer explicitement.

Pour les smokes p89-p111, deux options :
1. Modifier `from genesis_world import py_batch_scan_resources` → `from genesis_world_legacy import py_batch_scan_resources`
2. Garder l'import unifié via un nouveau `runtime/engine/_native.py` qui ré-exporte tout

Choisir (2) — minimal break des smokes.

### Étape 4 — Mettre à jour PROJECT-VIABILITY.md

Remplacer le bloc "Authoritative Entry Points" pour pointer vers `native/world-engine/` comme Rust canonique. Lien vers ce document.

### Étape 5 — Issue tracker

Ouvrir une issue GitHub "Migration B : absorber ge-py dans native/world-engine/pybindings" avec checklist (15 fonctions, par groupe : terrain, scan, batch, regen, drives, snapshot). Label `epic`, target Q3 2026.

---

## 4. État final attendu après l'étape 5

```
genesis-engine/
├── runtime/
│   ├── engine/            ✅ CANONICAL package Python
│   ├── tests/             ✅ CANONICAL pytest suite
│   ├── scripts/           ✅ CANONICAL smokes p0–p111
│   ├── run.py             ✅ CANONICAL launcher
│   ├── artifacts/         ⏪ runtime outputs (.gitignore'd)
│   └── journals/          ⏪ runtime outputs (.gitignore'd)
│
├── native/
│   └── world-engine/      ✅ CANONICAL workspace Rust
│       ├── crates/
│       │   ├── core, biome, terrain, climate, …
│       │   └── pybindings/     ← produit la wheel `genesis_world`
│       └── …
│
├── scaffolding/           ⚠️  LEGACY (wheel renommée → genesis_world_legacy)
│   └── crates/ge-py/      ← à absorber dans pybindings sous 3 mois
│
└── docs/
    ├── RUNTIME-LAYOUT.md       ← ce document, source de vérité
    ├── PROJECT-VIABILITY.md    ← contrat d'installabilité (pointe ici)
    └── STACK.md                ← stack tech externe (Next.js, Postgres…)
```

**Suppressions effectives par rapport au snapshot 2026-05-27 :**
- `runtime/genesis/` (21 fichiers Python, tous .pyc-only, 0 importeur)
- `runtime-phase5/` (13 fichiers Python + tests, 0 importeur externe)
- Références dans `Makefile`, `pyproject.toml`, `PROJECT-VIABILITY.md`

**Renommages :**
- `scaffolding/crates/ge-py` wheel : `genesis_world` → `genesis_world_legacy`

---

## 5. Vérifications de non-régression

À lancer après chaque étape :

```bash
# Étapes 1-2 (suppression code mort) :
make compile-python
make test-python
make smoke-realism

# Étape 3 (renommage wheel) :
make maturin-dev                    # build pybindings (new)
cd scaffolding && maturin develop --release   # build ge-py (legacy)
make validate-all                   # tous les smokes p72-p87
PYTHONPATH=runtime python runtime/scripts/p111_rayon_scan_smoke.py  # smoke ge-py-spécifique
PYTHONPATH=runtime python runtime/scripts/p73_rust_worldgraph_smoke.py  # smoke pybindings-spécifique
```

Tous doivent passer 9/9.

---

## 6. Décisions reportées (hors scope de cette journée)

- **Migration B** : absorption de ge-py dans pybindings. Plan détaillé à écrire dans une issue séparée. Target Q3 2026.
- **Bench croisé** : comparer ge-py.sample_terrain_chunk vs pybindings.observe_chunk sur identiques `(seed, coord)` pour confirmer bit-identical avant migration. Si divergence détectée, comprendre AVANT de migrer.
- **CI étendue** : ajouter un job qui builde ge-py legacy ET pybindings, puis lance `validate-all` avec les deux wheels installées simultanément.

---

## 7. Annexe — preuve d'instruction

Faits cités dans ce document, prouvés en arbre :

| Affirmation                                                  | Preuve                                                                       |
|--------------------------------------------------------------|------------------------------------------------------------------------------|
| `runtime/genesis/` lève ImportError                           | `runtime/genesis/__init__.py:7`                                              |
| 0 importeur Python pour `runtime/genesis/`                    | `grep -r "^from genesis\.\|^import genesis$" runtime/` → 0 résultat          |
| `runtime-phase5/` self-contained                              | `grep -rE "phase5\.|runtime-phase5" runtime/` → 0 résultat                   |
| pytest exclut runtime-phase5                                  | `pyproject.toml:46` `testpaths = ["runtime/tests"]`                          |
| Deux wheels du même nom                                       | `scaffolding/crates/ge-py/Cargo.toml:11` et `native/world-engine/crates/pybindings/Cargo.toml:11` — tous deux `name = "genesis_world"` |
| Maturin pointe pybindings                                     | `Makefile:121`                                                               |
| CI canonique builde pybindings                                | `.github/workflows/ci.yml:113`                                               |
| API divergente                                                | Voir tableau §2.2                                                            |

---

**Document écrit dans le cadre du delta-audit 2026-05-27 (cf. [`native/world-engine/AUDIT-DELTA-2026-05-27.md`](../native/world-engine/AUDIT-DELTA-2026-05-27.md)).**
