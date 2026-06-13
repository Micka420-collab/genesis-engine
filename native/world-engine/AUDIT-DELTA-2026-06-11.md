# Genesis World Engine — Delta-Audit 2026-06-11 (J+1)

**Mode :** suivi automatique (scheduled task `analyse-le-projet-regarde-si-il-y-a-des-amelioration`).
**Successeur direct de** [`AUDIT-DELTA-2026-06-10.md`](./AUDIT-DELTA-2026-06-10.md).
**Périmètre :** ce qui s'est passé en **24 h** sur la zone moteur Rust `native/world-engine/` (23 crates) + interface live Python↔Rust.
**Contrainte env :** `cargo` absent. Toute affirmation Rust est validée par **inspection lecture seule** ; CI = source de vérité.

---

## 0. Verdict express

> En 24 h : **3 commits structurants** (`7ac4280`, `064875f`, `1779687`) — **rupture nette** avec le treadmill d'observateurs. Le pont Python↔Rust, **inactif depuis Wave 42**, est réactivé live (`backend="terrain"`). La garde D1 (observer-budget + moratoire Wave 64+) est en place dans `CONTRIBUTING.md`. La 1ʳᵉ **capacité** (vs. observateur) en 25 jours, `surface_mineralization`, ferme la boucle "voir le minerai → creuser → trouver" côté Python.
>
> **Mais** côté backlog moteur : **0 item Phase A/B mergé**. A3, A4, A5 stagnent depuis 26 jours. **Nouveau bug confirmé** : `genesis-geology` (Wave 43) est **orphelin** — aucune crate ne l'importe (D5 du delta précédent passe de "risque" à "réalisé").
>
> **Recommandation principale** : maintenir le moratoire Wave 64+ (déjà en place) et flécher les 5 prochains jours dev sur **A3 (spatial index)** + **wiring `genesis-geology` dans le pipeline `worldgraph`** (D5-fix). Ce sont les 2 items qui *débloquent simultanément* la perception multi-agent **et** la cohérence du score réalisme (qui sinon mesure une crate géologie non câblée).

### Score Phase A après 26 jours dev

| Item | 2026-06-10 | 2026-06-11 | Delta J+1 |
|------|------------|------------|-----------|
| A1 apply_pending | ✅ | ✅ | — |
| A2 vraie LRU    | ⚠ partial (FIFO + skip pinned)  | ⚠ identique | — |
| A3 spatial index | ❌ stub `Vec::new()` | ❌ **stub identique** | **stagnation J+26** |
| A4 raycast chunk-aware | ❌ DDA step=0.5 | ❌ **identique** | **stagnation J+26** |
| A5 GPU erosion wired | ❌ | ❌ (`genesis-gpu` absent de `streaming/Cargo.toml`) | **stagnation J+26** |
| A6 snapshot/restore | ✅ + pin mutées | ✅ identique | — |
| A7 fog-of-war   | ⚠ partiel | ⚠ identique | — |

**A1 + A6 livrés (29 %) — inchangé sur 24 h, conforme à l'absence de Wave de moteur.**

---

## 1. Ce qui a changé en 24 h

### 1.1 Commits (ordre chronologique)

| Commit  | Titre                                                                              | Couche |
|---------|------------------------------------------------------------------------------------|--------|
| `7ac4280` | reactivate native Rust backend + D1 observer-budget guardrail                    | Pont + garde + Rust fix |
| `064875f` | observe_chunk_compat adapts both wheel arities (fixes CI maturin-pybindings)     | Pont CI |
| `1779687` | surface mineralization cues — emergent visual mineral discovery (Cap. C1)         | Python (capacité) |

Aucun de ces commits ne touche `agent-api/src/lib.rs::entities_in_radius` (A3), `::raycast` (A4), `streaming/Cargo.toml` (A5 wire) — vérifié par lecture (cf. §2).

### 1.2 Trois ruptures positives

**R1 — Treadmill d'observateurs interrompu (D1 fermé).**
- `runtime/engine/observer_budget.py` introduit : `installed_observers`, `observer_wrap_depth`, `measure_observer_overhead`, `assert_observer_budget` (budget tick < 10 %).
- `runtime/tests/test_observer_budget.py` prouve l'idempotence cross-observer (pas de double-wrap, stack LIFO).
- `CONTRIBUTING.md` formalise la règle : « pas de Wave 64+ tant que Phase A < 5/7 et 0 Phase B mergée ». Le moratoire est donc **automatisé** par doc + test. Risque de récidive = bas.

**R2 — Pont Python↔Rust réactivé (live).**
- Bug racine : `rust_bridge.py` n'acceptait que le contrat `is_canonical_pyworld` (snapshot/set_voxel). Le wheel réel `ge-py` (surface *terrain*: `sample_terrain_chunk`, `observe_chunk`) tombait silencieusement vers `MockPyWorld` → **backend natif inactif depuis Wave 42**.
- Fix : `is_terrain_pyworld` + `is_native_pyworld(contrat_terrain OR contrat_snapshot)` + champ `backend` dans `bridge_status()`.
- Vérifié live : `bridge_status() = {native: True, backend: "terrain"}`.
- C'est le délivrable n°1 de la session. Sans ce fix, le score "Pont Python↔Rust = 82 %" (`PROJECT-STATUS.md`) était un score de **surface API**, pas d'usage runtime. À partir de `7ac4280`, c'est mesurable.

**R3 — Première capacité (vs. observateur) en 25 jours.**
- `runtime/engine/surface_mineralization.py` (382 lignes) + 15 tests + smoke `p133` (7/7).
- Boucle agent fermée : `chunk_geology` (Rust seed minerai en profondeur) → `surface_mineralization` (Python, indice visuel de surface, *dérivé* de la même colonne) → action `MINE` qui touche le bon minerai.
- Invariant prouvé : « le monde ne ment jamais » sur seed `0xFACE`, 100 chunks, 0 violation.
- **Important** : c'est une capacité **Python live**, **pas** une fermeture d'item Rust Phase A/B. Le commit le déclare honnêtement : *"closes NO Rust Phase A/B item"*. (Cohérent avec D4 du delta précédent : score réalisme et capacité moteur restent décorrélés.)

### 1.3 Diffs Rust moteur (validés inspection)

- `streaming/src/manager.rs::set_voxel` + `restore_chunk_voxels` re-asserent l'appartenance cache **après** que l'écriture a pin la chunk (`mutation_version > 0`). Évite l'orphelinage par `maybe_evict()` côté race.
  - Vérifié `manager.rs:319-342` : `self.cache.insert(coord, shared); self.maybe_evict();` après `set_voxel_world`.
  - Note : N5 (set_voxel synchrone full pipeline) reste **ouvert**. Le `MutError::ChunkNotLoaded` variant existe (`agent-api/src/lib.rs:42`) mais n'est toujours pas utilisé sur le hot-path.
- `scenario/Cargo.toml` ajoute dep `genesis-worldgraph` (le crate compile à nouveau).
- `intent/mesh/scenario` : imports inutilisés retirés (-D warnings).

---

## 2. Ce qui n'a **pas** bougé (et reste critique)

Vérifications par lecture (cf. tableau Phase A §0).

### 2.1 A3 — entities_in_radius (`agent-api/src/lib.rs:306-310`)

```rust
fn entities_in_radius(&self, _p: WorldCoord, _r: f32) -> Vec<EntityRef> {
    // Stub — the entity index lives in the agent runtime, not in the
    // world engine. The Python layer will populate this.
    Vec::new()
}
```

26 jours. Le commentaire promet un *transfert de responsabilité* au Python qui n'est nulle part formalisé en trait `EntityIndex`. Le bug est **dormant** (D3) : tout futur appelant Rust qui lit cette API "voit le monde vide" et le silence est compile-OK.

### 2.2 A4 — raycast naïf (`agent-api/src/lib.rs:312-335`)

```rust
let step = 0.5_f32;
let mut t = 0.0_f32;
while t < max_distance {
    let p = origin + d * t;
    let wc = WorldCoord::new(p.x.floor() as i32, p.y.floor() as i32, p.z.floor() as i32);
    if let Some(v) = self.voxel(wc) {
        if !v.is_air() { return Some(RayHit { ... }); }
    }
    t += step;
}
```

Toujours O(distance / 0.5) = 200 lookups par 100 m, chaque lookup re-lock un `RwLock` chunk. Bloque la perception agent à toute échelle hors cellule unique.

### 2.3 A5 — GPU erosion non wired (`streaming/Cargo.toml`)

```
[dependencies]
genesis-core, genesis-noise, genesis-terrain, genesis-climate,
genesis-biome, genesis-hydrology, genesis-ecosystem, genesis-persist,
genesis-macro-bridge
```

`genesis-gpu` **absent**. Le code wgpu existe (`crates/gpu/src/erosion.{rs,wgsl}`) mais n'est appelé par personne. Throughput chunk plafonné CPU.

### 2.4 D2 — `maybe_evict` reste O(N) scan (`streaming/src/manager.rs:207-234`)

```rust
for kv in self.cache.iter() {                       // O(N) scan
    if to_drop.len() >= excess { break; }
    let chunk = kv.value().read();
    if chunk.meta.mutation_version == 0 { to_drop.push(*kv.key()); }
}
```

Pinning fonctionnel (skip mutated). Mais **toujours pas** de priority queue par `last_touch_tick`. Scénario pathologique : cache 1000 chunks, 500 mutées, capacity 200 → `to_drop` plafonne à 500 - le scanner mange tous les non-mutés au hasard (pas LRU), inclus ceux *récemment touchés*. Aucun test ciblé.

### 2.5 B1–B8 — 0 % (inchangé)

Voir §2 du delta 2026-06-10. Tous les pointeurs sont stables. Les 12 stubs `proposals/axis*/` ne bougent pas (26 jours en file d'attente).

---

## 3. Nouveau bug confirmé : `genesis-geology` orphelin (D5 réalisé)

### 3.1 Constat

Recherche exhaustive sur le workspace :

```
grep -l "genesis-geology" crates/*/Cargo.toml
→ crates/geology/Cargo.toml      (auto-référence uniquement)

grep "geology\|Geology" crates/*/src/*.rs
→ crates/core/src/tick_domain.rs  (string "/// Geology / tectonics" — docstring)
→ crates/geology/src/*.rs         (auto-référence)
```

**Conclusion** : **aucune** crate du workspace ne dépend de `genesis-geology`. La crate ajoutée Wave 43 (commit `18c15a9`, indices visuels minéraux RGB déterministes) **n'est appelée par personne**.

### 3.2 Conséquences

1. **Du point de vue moteur Rust** : c'est du *dead code* compilé mais jamais exécuté. La crate ne participe pas au pipeline `streaming::generate()`, ni à un `Pass` du `worldgraph` DAG.
2. **Du point de vue score réalisme** : `PROJECT-STATUS.md` annonce géologie 75 % en partie pour des contributions de la crate (Wave 43 visual cues). En réalité, la dimension "géologie" évalue ce que le runtime **Python** observe — et la couche couleur Rust ne lui parvient jamais via le moteur.
3. **Du point de vue capacité shipped today (`1779687`)** : `runtime/engine/surface_mineralization.py` ré-implémente côté Python ce que `crates/geology/src/visual.rs` faisait côté Rust. **Code parallèle non-bridgé** — la source de vérité du minerai (`chunk_geology` Python) et la source de vérité de la couleur (`genesis-geology` Rust) sont **dans des univers séparés**. Aujourd'hui ça marche parce que le Python a tout réimplémenté. Demain si quelqu'un modifie la palette Rust, le Python ne le verra pas.

### 3.3 Fix proposé

Deux scénarios, choisir un :

- **(a) Promouvoir** : ajouter `genesis-geology` à `crates/streaming/Cargo.toml` et appeler `geology::sample_at(wx, wy, wz)` dans `Chunk::generate()`, l'hashé dans le content-key du `worldgraph` Pass. Coût estimé : 1.5 j dev (audit `Pass` content-addressable + test `geology_pass_is_deterministic`).
- **(b) Archiver** : créer `crates/geology/DEPRECATED.md` (« couvert par le runtime Python `surface_mineralization` ») et **retirer la crate du workspace**. Coût : 30 min. Risque : perte de la palette RGB Rust si jamais on re-bridge plus tard.

**Recommandation : (a)**. Le `surface_mineralization.py` shipped aujourd'hui prouve que la demande existe ; le re-implémenter en Python sans relier au Rust crée une dette qui sera difficile à payer une fois que d'autres observateurs hériteront du même pattern (cf. règle d'or *single-source-of-truth* du pont).

---

## 4. Roadmap mise à jour (recommandation 2026-06-11)

### Priorité 0 — Avant Wave 64 (= maintenir le moratoire ; déjà en place)

| Item   | Effort | Source                          | Bloque                                |
|--------|--------|----------------------------------|---------------------------------------|
| **A3** | 2 j    | `proposals/axis4_performance/spatial_index.rs` | Perception multi-agent → métriques sociales (Wave 58/60) |
| **D5-fix** | 1.5 j | (nouveau) wiring `genesis-geology` dans `streaming::generate()` + test `geology_pass_deterministic` | Cohérence source-of-truth, score réalisme honnête |
| **A4** | 2 j    | (à coder)                          | Latence vision agent ÷10              |
| **A5** | 1 j    | `proposals/axis4_performance/gpu_pipeline.rs` | Throughput chunk ×5                   |

**A3 + D5-fix avant A4/A5** : A3 débloque immédiatement la dimension sociale émergente (Wave 58/60 *prétendent* mesurer l'illumination comportementale en multi-agent — sans index, c'est O(N²) ou rien) ; D5-fix referme une incohérence qui se *creuse* à chaque commit (`surface_mineralization.py` shipped aujourd'hui en est l'instance la plus récente).

### Priorité 1 — Un item Phase B (5–10 j, post-Priorité 0)

Recommandation inchangée vs. 2026-06-10 : **B6 (boids + Lotka-Volterra)**, source `proposals/axis3_ecosystem/{boids,food_web}.rs`. Surface d'audit limitée à 1 crate, débloque la dimension écologie 73 → 78.

### Priorité 2 — Tri des proposals (1 j)

26 jours en file d'attente. Décision : promouvoir A3 + B6 sources ; archiver les autres dans `proposals/ARCHIVED-2026-06.md` si non attaqués d'ici Q3-end.

---

## 5. Risques **D-series** : delta 2026-06-11

| ID  | Risque (du delta précédent)                                  | État 2026-06-11 |
|-----|--------------------------------------------------------------|------------------|
| D1  | Treadmill observateurs (scope drift formel)                   | ✅ **CLÔTURÉ** par `observer_budget.py` + `CONTRIBUTING.md` moratoire |
| D2  | `maybe_evict` O(N) scan, dégénère sous mutations dominantes   | ❌ identique     |
| D3  | Coupling implicite agent-runtime ↔ moteur via `entities_in_radius` muet | ❌ identique  |
| D4  | Décorrélation score réalisme ↔ capacités moteur               | ⚠ **partiellement aggravé** — la capacité `surface_mineralization` ajoute 1 pt géologie côté Python sans toucher la crate Rust |
| D5  | Audit chaîne `worldgraph` Pass après ajout `genesis-geology` | ❌ **RÉALISÉ** — crate orphelin confirmé (§3) |

**Nouveau risque D6 : double-source-of-truth pour la minéralisation**.
- `runtime/engine/surface_mineralization.py` (Python, vivant, shipped `1779687`).
- `crates/geology/src/visual.rs` (Rust, dormant, jamais appelé).
- Les deux sont supposés produire le même rendu RGB pour le même minerai. Sans test cross-langage, ils peuvent diverger silencieusement à n'importe quel commit. **Fix** : un test invariant Python `test_geology_palette_matches_rust()` qui charge la palette Rust via PyO3 et la compare. Bloque tant que `genesis-geology` n'est pas exposé via `pybindings`. Coût : ½ j si l'exposition est faite ; sinon, inclus dans D5-fix (a).

---

## 6. Procédure suggérée pour J+1 → J+7

```
J+1 (2026-06-12) : A3 (spatial_index rstar) + tests D3 [perception]
J+2              : A3 fin + bench `entities_in_radius_with_1000_entities` < 100 µs
J+3              : D5-fix (wire genesis-geology → streaming) + Pass `Geology` content-addressable
J+4              : D5-fix tests cross-langage palette (D6) + audit Pass DAG
J+5              : A4 (raycast chunk-aware DDA) + bench `raycast_p50_at_50m` < 1 ms
J+6              : A5 (genesis-gpu wired dans streaming + fallback) + bench throughput
J+7              : Bilan A3/A4/A5/D5 — si ≥ 3/4 ✅, Wave 64 (1 observateur) ré-autorisée
```

**Note env** : aucune compilation Rust possible localement (`cargo` absent). Le déroulé ci-dessus suppose un push par feature suivi d'un cycle CI complet (matrix maturin + extended-workspace). Toute affirmation "✅" est conditionnée à `cargo test --release --workspace` vert sur CI.

---

## 7. Métriques à ajouter au harness de bench

Inchangé vs. 2026-06-10 §6, plus :

| Bench / metric                                  | Cible          | Crate           |
|-------------------------------------------------|----------------|------------------|
| `geology_pass_is_content_addressable`            | bit-stable     | worldgraph + geology |
| `geology_palette_matches_python_runtime`         | strict eq RGB  | pybindings + Python tests |
| `surface_mineralization_cue_round_trip_rust_python` | strict eq sur seed `0xFACE` | E2E |

---

## 8. Recommandations stratégiques

1. **Le D1 est fermé, ne pas le rouvrir.** Le `observer_budget` + moratoire `CONTRIBUTING.md` est la première vraie barrière dressée contre le treadmill. Le maintenir.

2. **La capacité Python d'aujourd'hui (`1779687`) n'est pas un substitut au backlog Rust.** Le commit message le dit lui-même (« closes NO Rust Phase A/B item ») et c'est une bonne pratique d'honnêteté à institutionnaliser. Toute future capacité Python doit déclarer explicitement *quels items Rust elle ne ferme pas*.

3. **Le bridge live (`backend="terrain"`) est une victoire — et un piège.** Le score "Pont Python↔Rust = 82 %" devient maintenant mesurable. Il devrait **baisser** au prochain reporting honnête (perception A3 = 0, mutation latency N5 = catastrophique sous charge). Préparer ce dégonflement.

4. **`genesis-geology` orphelin = D5 réalisé.** À traiter cette semaine (D5-fix option a) ou archiver formellement (option b). La zone grise est le seul vrai signal négatif du jour.

5. **Tri des proposals** : décision attendue depuis le delta du 2026-06-10. Le report J+7 (post-A3/A4/A5/D5) est acceptable mais doit être tenu.

---

## 9. Annexe — Inventaire 23 crates (inchangé vs. 2026-06-10)

```
agent-api      biome        cache        climate      core
ecosystem      geology★     gpu          hydrology    intent
laws           macro-bridge mesh         noise        persist
physics        pybindings   scenario     streaming    studio
terrain        weather      worldgraph
```

★ = **orphelin confirmé** (aucune dépendance entrante hors auto-référence). Voir §3.

---

## 10. Annexe — Diffs Rust moteur depuis 2026-06-10

```
modifiés :
  crates/streaming/src/manager.rs    set_voxel/restore re-assertent cache après pin
  crates/scenario/Cargo.toml         + dep genesis-worldgraph
  crates/terrain/Cargo.toml          + dev-dep blake3
  crates/intent/src/*                imports inutilisés retirés (-D warnings)
  crates/mesh/src/*                  imports inutilisés retirés
  crates/scenario/src/*              imports inutilisés retirés
  crates/scenario/examples/demo_world.rs  .read() sur lock partagé

inchangés (mais ciblés par l'audit) :
  crates/terrain/src/tectonics.rs                Voronoi statique, motion non utilisé (B1)
  crates/hydrology/src/lib.rs                    sort sequential par-chunk (B2)
  crates/ecosystem/src/lib.rs                    seeds only, pas de tick (B6)
  crates/streaming/src/manager.rs::column_material  1D-column (B5)
  crates/agent-api/src/lib.rs::entities_in_radius   stub Vec::new() (A3)  ← J+26
  crates/agent-api/src/lib.rs::raycast              DDA naïf step=0.5 (A4)  ← J+26
  crates/streaming/Cargo.toml                     genesis-gpu absent (A5)  ← J+26
  crates/streaming/src/manager.rs::maybe_evict     scan O(N) (D2)
  (workspace)                                     genesis-geology orphelin (D5)
```

---

**Fin du delta-audit J+1.**
Document généré automatiquement par tâche planifiée `analyse-le-projet-regarde-si-il-y-a-des-amelioration`.
Successeur attendu : prochaine exécution, à compléter avec l'état A3, D5-fix et le sort des 12 proposals.
