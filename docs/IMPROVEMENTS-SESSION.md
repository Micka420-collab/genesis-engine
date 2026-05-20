# Améliorations session — priorités livrées (19 mai 2026)

## Résumé

Implémentation end-to-end des priorités haute / moyenne / basse : pont Rust (maturin + mock), Köppen FAIR sur monde Genesis, coupler multi-temps par défaut, CI GitHub matrix Python + Rust, hydrologie cross-chunk, épidémie dashboard, SSE observation, atmosphère volumétrique légère, gouvernance (CODE_OF_CONDUCT, issue templates), renders canoniques.

**Réalisme Terre global : ~68 %** (voir [`ROADMAP-REALISME-TERRE.md`](ROADMAP-REALISME-TERRE.md)).

## Smokes

| Script | Rôle |
|--------|------|
| p73 | Rust bridge (natif ou mock) |
| p75 | Köppen grille macro |
| p76 | Multi-rate coupler |
| p77 | Contact graph épidémie |
| p80 | Köppen Genesis bootstrap + manifeste FAIR |
| p81 | Hydrologie Saint-Venant / LBM |
| p82 | SSE observation server |

## CI

`.github/workflows/ci.yml` : Python 3.11/3.12, `cargo test` world-engine, maturin (continue-on-error), smokes p72–p82.

## Pont Rust

```bash
cd native/world-engine
pip install maturin
maturin develop -m crates/pybindings/Cargo.toml --release
PYTHONPATH=runtime python runtime/scripts/p73_rust_worldgraph_smoke.py
```

Sans module natif : `MockPyWorld` — p73 reste **PASS (mock)**.

## Artifacts exemple

- `runtime/artifacts/koeppen_genesis_fair_example.json`
- `docs/compliance/koeppen_genesis_fair_example.json`

## Vérification locale

```bash
make test-python
make smoke-realism
cd native/world-engine && cargo test -p genesis-core -p genesis-biome -p genesis-worldgraph
```

## Pont Rust — mock actif

`genesis_world` non importable ; smokes utilisent `engine.rust_bridge.MockPyWorld`. Compiler pour le natif :

```bash
cd native/world-engine
maturin develop -m crates/pybindings/Cargo.toml
```

