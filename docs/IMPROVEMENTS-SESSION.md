# Déprécié

Contenu fusionné dans :

- [`EMERGENCE-SIM-v2.md`](EMERGENCE-SIM-v2.md)
- [`ROADMAP-REALISME-TERRE.md`](ROADMAP-REALISME-TERRE.md)

Voir [`OBSOLETE.md`](OBSOLETE.md).

## Pont Rust — mock actif

`genesis_world` non importable ; smokes utilisent `engine.rust_bridge.MockPyWorld`. Compiler pour le natif :

```bash
cd native/world-engine
maturin develop -m crates/pybindings/Cargo.toml
```


## Pont Rust — OK

`genesis_world` importable, observe_chunk OK.

