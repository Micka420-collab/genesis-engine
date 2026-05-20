# Genesis World Engine (Rust)

Moteur natif de génération et simulation de monde pour Genesis Engine : bruit, terrain, climat, biomes Köppen, hydrologie, streaming LOD, WorldGraph DAG, et bindings Python.

> **Important** : ce crate **ne remplace pas** le runtime Python (`../../runtime/engine/`). Intégration incrémentale via `rust_bridge` / PyO3 ; la civilisation et les agents restent en Python pour l’instant.

**Statut global** : [`../../PROJECT-STATUS.md`](../../PROJECT-STATUS.md) · **Réalisme Terre global** : **~76 %** · **Pont Rust (dimension)** : **82 %** · chunk seul non aligné : ~45 % ([`../../docs/ROADMAP-REALISME-TERRE.md`](../../docs/ROADMAP-REALISME-TERRE.md))

---

## Statut des crates (mai 2026)

| Crate | Rôle | Maturité |
|-------|------|----------|
| `genesis-core` | PRF, ticks, coupler multi-rate | ✅ tests |
| `genesis-noise` | Simplex, FBM, warp | ✅ + bench |
| `genesis-terrain` | Heightmap, tectonique, érosion CPU | ✅ |
| `genesis-biome` | Whittaker + **Köppen** | ✅ harness |
| `genesis-climate` / `hydrology` / `weather` | Champs macro | 🟡 |
| `genesis-streaming` | ChunkManager, LOD | ✅ exemples |
| `genesis-worldgraph` | Pipeline DAG, scheduler, lineage | 🟡 prod path |
| `genesis-gpu` | Érosion WGSL (feature `gpu`) | 🟡 |
| `genesis-macro-bridge` | GENM + align_heightmap (P0 Terre unique) | ✅ |
| `genesis-pybindings` | `PyWorld` GENM + mutations + snapshot | 🟡 maturin |
| `genesis-studio` | CLI scénarios YAML | ✅ |

---

## Toolchain

```bash
# Installer Rust 1.85+ (rust-toolchain.toml dans ce dossier)
rustup show

cd native/world-engine   # depuis la racine du repo
cargo build
cargo test
cargo build --release
```

Windows : [rustup.rs](https://rustup.rs) → `rustup-init.exe`.

---

## Layout

```
crates/
├── core/          PRF, TickDomain, MultiRateCoupler
├── noise/         Génération procédurale SIMD
├── terrain/       Relief, tectonique, érosion
├── biome/         Whittaker + koeppen.rs (+ tests harness)
├── climate/       Température, humidité, vent
├── hydrology/     Rivières, bassins
├── ecosystem/     Flore / faune spawn
├── streaming/     Chunks + LOD + exemples demo
├── worldgraph/    Pass, Pipeline, Scheduler, Branch
├── gpu/           Compute érosion (feature gpu)
├── intent/        Prefetch intent-aware agents
├── mesh/          Surface Nets, simplification
├── physics/       Unités SI, constantes CODATA
├── laws/          Lois physiques (thermo, hydro, écologie)
├── scenario/      Manifest YAML FAIR
├── persist/       Snapshots bincode + zstd
├── agent-api/     Lecture/écriture pour agents IA
├── pybindings/    PyO3 → pip install maturin
└── studio/        Binaire genesis-studio
```

Propositions expérimentales : [`proposals/README.md`](proposals/README.md).  
Architecture cible « God-Engine » : [`../../docs/GOD-ENGINE-ARCHITECTURE.md`](../../docs/GOD-ENGINE-ARCHITECTURE.md).

---

## Exemples

```bash
cargo run --release -p genesis-streaming --example demo_world
cargo run --release -p genesis-streaming --example worldgraph_demo
cargo run --release -p genesis-streaming --example intent_prefetch_demo

cargo run --release -p genesis-studio -- info
cargo run --release -p genesis-studio -- run ./scenarios/coastal_storm.yaml -o ./runs
```

Scénarios : [`scenarios/`](scenarios/).

---

## Tests & benchmarks

```bash
cargo test
cargo test -p genesis-biome -p genesis-worldgraph -p genesis-core
cargo bench -p genesis-noise
cargo bench -p genesis-streaming
```

Pont Python (smoke côté runtime) :

```bash
cd ../../runtime
python scripts/p73_rust_worldgraph_smoke.py
python scripts/p74_koeppen_harness_smoke.py
```

---

## Bindings Python

```bash
cd crates/pybindings
pip install maturin
maturin develop --release
```

```python
import genesis_world as gw
from engine.macro_grid_export import export_macro_grid_bytes

w = gw.PyWorld(seed=42, macro_grid_bytes=export_macro_grid_bytes(world))
obs = w.observe_chunk(0, 0)
w.set_voxel(1, 1, 2, 2)  # Stone
w.apply_pending()
snap = w.save_snapshot()
mesh = w.extract_mesh(0, 0, 1)  # L2 cache keyed on mutation_version
w.restore_snapshot(snap)
```

Depuis la racine du repo (PowerShell) :

```powershell
cd native/world-engine/crates/pybindings
pip install maturin
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
maturin develop --release
cd ../../../../runtime
$env:PYTHONPATH = "."
pytest tests/test_native_genesis_world.py -q
```

---

## Recherche interne

1. [`docs/RESEARCH-SOTA.md`](docs/RESEARCH-SOTA.md) — état de l’art 2026  
2. [`docs/INNOVATIONS.md`](docs/INNOVATIONS.md) — WorldGraph, cache BLAKE3, GPU, intent prefetch  
3. [`docs/RESEARCH-SCIENTIFIC.md`](docs/RESEARCH-SCIENTIFIC.md) — Genesis Studio, lois physiques  

---

## Où coder quoi (Rust)

| Objectif | Emplacement |
|----------|-------------|
| Nouveau pass monde | `crates/worldgraph/src/pass.rs`, pipeline |
| Classif. biome / Köppen | `crates/biome/` |
| Perf chunks / LOD | `crates/streaming/` |
| Érosion GPU | `crates/gpu/` |
| Exposer à Python | `crates/pybindings/` |
| Scénario reproductible | `scenarios/*.yaml` + `crates/scenario/` |

Civilisation, cognition, rendu civilisationnel → **runtime Python**.

---

## Voir aussi

- [`../../architecture/world-engine-rust.md`](../../architecture/world-engine-rust.md)
- [`../../specs/procedural-world-spec.md`](../../specs/procedural-world-spec.md)
- [`BENCHMARKS.md`](BENCHMARKS.md)
- [`NEXT-LEVEL-AUDIT.md`](NEXT-LEVEL-AUDIT.md)

> **Note CI racine** : `make rust-check` cible encore `scaffolding/` (historique). Pour ce workspace : `cd native/world-engine && cargo check --workspace`.
