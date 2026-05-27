# Wave 42 — Intégration Rust-Python (Phase 1 + 2)

**Date :** 2026-05-27  
**Smoke :** p88 — 9/9 ✓

---

## Objectif

Implémenter les **Phases 1 et 2** du roadmap d'intégration Rust-Python (section 8 de l'architecture) :

- **Phase 1 (non-invasif)** — workspace Rust avec crate `ge-py` (PyO3), `pyproject.toml` maturin, Python inchangé.
- **Phase 2 (opt-in)** — flag `use_rust_backend=False` dans `world.py`; quand `True`, délègue heightmap/biome au backend Rust.

---

## Livraisons

### Nouveau : `scaffolding/crates/ge-py/`

| Fichier | Rôle |
|---|---|
| `Cargo.toml` | Crate `cdylib` avec deps `ge-core`, `ge-world`, `pyo3 0.22` |
| `src/lib.rs` | Module `genesis_world` PyO3 — expose `PyWorld` |

**Interface `PyWorld` (compatible `MockPyWorld`):**

| Méthode | Signature Python | Description |
|---|---|---|
| `__init__` | `(seed=42, **kwargs)` | kwargs ignorés (compat Phase 1) |
| `observe_chunk` | `(cx, cy, cz) -> dict` | terrain + biome via ge-world Rust |
| `biome_at` | `(x, y, z=0.0) -> int` | biome Whittaker (ordinal Python 0-11) |
| `sample_terrain_chunk` | `(cx, cy) -> dict` | `{elev, temp, precip}` listes float32 — utilisé par Phase 2 |
| `cached_chunk_count` | `() -> int` | 0 Phase 1 (LRU Rust Phase 3) |

**Mapping biome Rust → Python** (`biome_to_py`) : `Ocean=0, Ice=1, ..., TropicalRainforest=11` — synchronisé avec `engine.world.Biome`.

### Mise à jour workspace Rust

- `scaffolding/Cargo.toml` : `ge-py` ajouté aux membres; `pyo3 = "0.22"` dans `workspace.dependencies`.

### Nouveau : `scaffolding/pyproject.toml`

Config maturin pour builder/installer le wheel :

```bash
# Depuis scaffolding/
pip install maturin
maturin develop --release   # Phase 1 : install wheel natif
maturin build   --release   # produit .whl dans target/wheels/
```

### Mise à jour : `runtime/engine/world.py`

**`generate_chunk`** — nouveau kwarg `rust_world=None` :
- Si fourni et `genesis is None` → appelle `rust_world.sample_terrain_chunk(cx, cy)`, convertit en numpy
- Exception → fallback Python silencieux
- Resources toujours calculées côté Python (prf_rng, déterministe)

**`ChunkStreamer.__init__`** — nouveau paramètre `use_rust_backend=False` :
- Si `True` : instancie `create_py_world(seed, synthetic_only=True)` via `engine.rust_bridge`
- Native absent → `_rust_world=None`, Python pur (pas d'erreur)
- `_rust_world_for_gen()` : retourne le handle seulement quand `genesis is None` (le backend Rust n'ancre pas encore la macro-tectonique)

---

## Déterminisme

Les valeurs Rust et Python **divergeront numériquement** — les PRF sont différents (Rust : BLAKE3+ChaCha20, Python : BLAKE2b+SplitMix64). C'est attendu et documenté : le roadmap Phase 2 exige **"résultats comparables (tolérance)"**, pas bit-for-bit. Le test A/B est prévu dans le smoke Phase 3.

---

## Smoke p88 — 9 checks

| # | Check | Résultat |
|---|---|---|
| 1 | Cargo.toml workspace contient ge-py | ✓ |
| 2 | ge-py/Cargo.toml présent avec pyo3 | ✓ |
| 3 | ge-py/src/lib.rs contient pyclass + pymodule | ✓ |
| 4 | scaffolding/pyproject.toml maturin avec manifest ge-py | ✓ |
| 5 | world.py contient use_rust_backend + rust_world | ✓ |
| 6 | ChunkStreamer(use_rust_backend=False) instanciable | ✓ |
| 7 | bridge_status() native=False (wheel absent OK) | ✓ |
| 8 | generate_chunk(python) produit chunk valide | ✓ |
| 9 | ChunkStreamer.get() ≡ generate_chunk direct | ✓ |

---

## Phase 3 (semaines 5+) — ce qui reste

1. **A/B benchmark** : comparer temps `generate_chunk` Python vs Rust sur N chunks.
2. **Validation tolérance** : `abs(rust_elev - py_elev).max() < threshold_m`.
3. Quand Rust > Python ET comparable → `use_rust_backend=True` par défaut.
4. **LRU cache Rust** (`cached_chunk_count > 0`) dans `ge-py`.
5. Ancrage macro `genesis_anchor` dans `PyWorld` (passer `macro_grid_bytes`).
6. Façade Python : `sample_terrain`, `fbm_2d` deviennent des thin wrappers.
