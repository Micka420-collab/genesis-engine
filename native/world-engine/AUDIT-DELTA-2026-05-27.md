# Genesis World Engine — Delta-Audit 2026-05-27

**Mode :** suivi automatique (scheduled task). Successeur de [`NEXT-LEVEL-AUDIT.md`](./NEXT-LEVEL-AUDIT.md) (2026-05-16).
**Périmètre :** workspace Rust `native/world-engine/` (22 crates au lieu de 15 il y a 11 jours).
**Objet :** ce qui a progressé, ce qui est bloqué, **nouveaux risques techniques** non couverts par l'audit précédent.

---

## 0. Verdict express

Phase A est **à 30 %** terminée. Les axes 1, 2, 3 sont **toujours** sur le rail générique (rien de la roadmap B mergé). En revanche, 7 nouvelles crates (`laws`, `weather`, `physics`, `macro-bridge`, `mesh`, `scenario`, `studio`) ont été ajoutées — direction **« sandbox scientifique FAIR »** qui n'était pas dans le mandat initial et qui crée de la dette implicite. Trois **nouveaux bugs latents** sont introduits par le code mergé depuis le 16 mai.

> **Recommandation prioritaire** : terminer Phase A (LRU, spatial index, GPU wire, raycast accéléré) avant tout ajout de nouveau crate, sinon le scope explose.

---

## 1. Avancement par rapport à la roadmap A/B/C

### Phase A — Quick wins (cible : 2-3 sem, état : 30 % au jour 11)

| Prio | Item                                                     | État 2026-05-16 | État 2026-05-27 | Preuve / commentaire |
|------|----------------------------------------------------------|-----------------|-----------------|----------------------|
| A1   | `apply_pending` → vraie mutation voxel                   | stub            | ✅ **fait**     | `agent-api/src/lib.rs:151-177`, tests `set_voxel_writeback_in_chunk_buffer` |
| A2   | LRU réelle (priority queue par `last_touch_tick`)        | crude FIFO      | ❌ **pas fait** | `streaming/src/manager.rs:128` — commentaire `Crude: drop the first excess we iterate` toujours en place |
| A3   | Spatial index `rstar` pour `entities_in_radius`          | stub `Vec::new` | ❌ **pas fait** | `agent-api/src/lib.rs:301-305` — encore `Vec::new()` avec commentaire « entity index lives in the agent runtime » |
| A4   | Raycast DDA chunk-aware + early-out air                  | naïf pas-fixe 0.5 m | ❌ **pas fait** | `agent-api/src/lib.rs:307-330` — même boucle pas-fixe, commentaire `a per-chunk acceleration structure is a future task` |
| A5   | GPU erosion auto-fallback dans `ChunkManager`            | feature-gated   | ❌ **pas fait** | `streaming/src/manager.rs` ne mentionne pas `HydraulicErosionGpu` ; `genesis-gpu` jamais importé par `streaming/Cargo.toml` |
| A6   | Snapshot/restore JSONL+rkyv minimal                      | absent          | ✅ **fait** (bincode+zstd au lieu de rkyv) | `agent-api/src/snapshot.rs` + tests `snapshot_roundtrip_preserves_voxel` |
| A7   | Fog-of-war filter                                        | absent          | ⚠ **partiel**   | `observe_area` retourne 1 chunk entier ; pas de filtre rayon agent |

### Phase B — Refactors moyens (cible : 6-8 sem, état : 0 % au jour 11)

| Item                            | État | Détail |
|---------------------------------|------|--------|
| B1 Tectonique dynamique         | ❌    | `terrain/src/tectonics.rs` toujours Voronoi statique, `motion: [f32; 2]` calculé jamais utilisé |
| B2 Hydrologie cross-chunk       | ❌    | `hydrology/src/lib.rs` toujours par-chunk, pas de border-padding |
| B3 Climat dynamique (advection) | ⚠    | Couvert *différemment* par `weather` crate (anchor snapshots + FBM perturbations) — mais **pas d'advection** ; voir §3 |
| B4 Saisons + cycle diurne       | ❓    | `weather` parle de « time-coherent field » — pas vu de saison réelle, à vérifier |
| B5 Voxel SDF 3D pour caves      | ❌    | `streaming/src/manager.rs:288-311` toujours `column_material(z, surface_z, ...)` — colonne 1D |
| B6 Boids / chaîne alim          | ❌    | `ecosystem/src/lib.rs` toujours seeds-only, aucune mise à jour runtime |
| B7 Hot-reload BiomeRegistry     | ❌    | Pas de watcher `notify` ajouté |
| B8 Debug overlay HTTP           | ❌    | Pas d'endpoint `/debug/*` |

### Phase C — Refactors lourds : non démarré (attendu).

---

## 2. Nouvelles crates apparues depuis le 16 mai

| Crate              | Lignes | Rôle déclaré                              | Évaluation rapide |
|--------------------|--------|-------------------------------------------|-------------------|
| `weather`          | 240    | Time-coherent weather (anchor + FBM)      | Bonne idée, mais **n'est pas la météo dynamique** (pas d'advection humidité) |
| `physics`          | ~50    | Units SI + constants                     | Solide, pure helpers, ✅ |
| `laws`             | 5 modules | Atmosphere/ecology/gravity/hydrology/thermo equations canoniques | Pédagogique, à ressouder vers `climate`/`hydrology` (sinon duplication) |
| `macro-bridge`     | 227    | Alignement heightmap avec macro-grid Python | **Risque déterminisme** (cf §3.4) |
| `mesh`             | 20+    | Mesh simplification (nets, simplify)      | Utile pour rendu, hors path agent |
| `scenario`         | 22 + manifest/runner/schema | Runner YAML d'expériences FAIR (DOI, license, exports NetCDF) | **Hors mandat** initial (« moteur de monde + agents IA ») |
| `studio`           | binaire `studio/src/main.rs` | CLI scientifique | Idem `scenario` |

**Lecture stratégique :** le projet a pivoté vers un produit dual — moteur de monde + sandbox scientifique reproductible. C'est **légitime** (réutilisation de la propriété de déterminisme), mais ça consomme du temps qui n'est pas appliqué à Phase A/B. Décision à arbitrer par le mainteneur.

---

## 3. Nouveaux risques techniques détectés (delta-audit)

### N1 — Race potentielle dans `ChunkManager::get_or_generate` (`streaming/src/manager.rs:152-179`)

```rust
let should_generate = {
    let mut entry = self.inflight.entry(coord).or_default();
    if entry.is_empty() {
        true                       // ← leader
    } else {
        let (tx, rx) = oneshot::channel();
        entry.push(tx);
        drop(entry);
        return rx.await.expect(...);
    }
};
```

Le leader **ne se met pas dans la file**. Si un 2ᵉ thread arrive après que le 1ᵉʳ ait relâché le guard de `DashMap::entry()` mais avant `cache.insert`, il voit `entry.is_empty() == true` (le leader n'a rien poussé) et devient un **deuxième leader**. Conséquences :
- double `spawn_blocking(generate(coord))`, donc deux érosions complètes pour le même chunk (CPU gâché).
- la 1ʳᵉ `cache.insert` rentre ; la 2ᵉ écrase silencieusement. Le `Arc<RwLock<Chunk>>` retourné aux deux callers diverge potentiellement.
- l'`inflight.remove` retourne `None` pour le perdant — pas de panique, mais pas de notification non plus aux waiters arrivés tardivement.

**Fix proposé :** stocker un sentinel `inflight.insert(coord, Vec::new())` côté leader, ou utiliser `dashmap::Entry::or_insert_with` retournant un état explicite (`Leader` vs `Joiner`). 1 jour de travail. Test : `same_coord_no_duplicate_generation_under_1000_threads`.

### N2 — `dominant_biome` alloue un `HashMap` par chunk (`streaming/src/manager.rs:342-368`)

```rust
fn dominant_biome(biomes: &[Biome]) -> Biome {
    use std::collections::HashMap;
    let mut counts: HashMap<u8, u32> = HashMap::new();
    for b in biomes { *counts.entry(*b as u8).or_insert(0) += 1; }
    ...
    match best {
        Some(0) => Biome::Ocean,
        Some(1) => Biome::CoastalSea,
        ...
    }
}
```

Trois problèmes :
1. **Allocation HashMap par chunk** : appelé une fois par chunk généré ; sous charge agent (100 chunks/s), 100 allocs+drops HashMap dont l'overhead dépasse le calcul lui-même. Remplacer par `[u32; 16]`.
2. **Match numérique fragile** : si on ajoute `Biome::Mangrove` sans renuméroter, le match retourne `Grassland` (catch-all `_`). Bug silencieux garanti à la première extension.
3. **Pas de test** : aucune assertion `dominant_biome(all_ocean) == Ocean`. Régression possible non détectée.

**Fix :** un tableau `[u32; Biome::COUNT]` + une méthode `Biome::from_index(i: u8) -> Option<Biome>` côté `biome` crate. 30 min de travail.

### N3 — Hash content-addressable du `WeatherField` non NaN-safe (`weather/src/lib.rs:43-54`)

```rust
impl ContentAddressable for WeatherField {
    fn hash_into(&self, h: &mut blake3::Hasher) {
        h.update(&self.tick.to_le_bytes());
        for c in &self.cells {
            h.update(&c.precipitation_mm_h.to_le_bytes());
            ...
        }
    }
}
```

`f32::to_le_bytes` sur un `NaN` produit une représentation parmi **2²³ possibles** (bit-pattern de payload non spécifié). Si une passe en amont (FBM, advection future) génère un `NaN` (overflow, division), deux exécutions identiques sur architectures différentes peuvent produire **deux hashes différents** → cache miss permanent, déterminisme cassé.

**Fix :** soit canonicaliser (`f.to_bits() & if f.is_nan() { 0xFFC0_0000 } else { !0 }`), soit `debug_assert!(f.is_finite())` à l'entrée du hash. À faire pour **tous** les `ContentAddressable` qui hashent du float — auditer les autres : `terrain`, `climate`, `hydrology`.

### N4 — `macro-bridge` introduit une source d'entropie externe non testée pour déterminisme

`macro-bridge/src/align.rs` mélange la heightmap Rust avec une grille macro produite côté Python. Le pipeline `streaming::generate` appelle `align_heightmap` après `generate_heightmap`. Si la grille macro :
- n'est pas chargée bit-à-bit identique (ordre de lignes, float precision Python f64 → Rust f32) ;
- ou si l'option `macro_grid: None` vs `Some(...)` change entre runs ;

→ deux runs avec la même seed produisent des chunks différents. La règle d'or « même seed = même monde » est rompue.

**Mitigation :** un test E2E `same_seed_with_and_without_macro_grid_produces_documented_difference` + un hash de la grille macro intégré au content-key des chunks impactés.

### N5 — `set_voxel` génère synchroneusement la chunk si non chargée (`streaming/src/manager.rs:194-202`)

```rust
pub fn set_voxel(&self, pos: WorldCoord, value: Voxel) -> bool {
    if !(0..CHUNK_SIZE_Z).contains(&pos.z) { return false; }
    let coord = pos.chunk();
    let shared = self.get_or_generate_blocking(coord);   // ← FULL pipeline
    shared.write().set_voxel_world(pos, value)
}
```

Un agent qui écrit dans une chunk non chargée déclenche **toute la pipeline** (heightmap, érosion 4 passes × 200 droplets, climat, biome, voxel fill, flora, fauna) — typique 20-30 ms. Sur 100 écritures « lointaines » par tick, c'est 2-3 s de latence d'agent. Cela compose mal avec un usage RL en exploration.

**Fix proposé :**
- Mode strict : `MutError::ChunkNotLoaded(coord)` pour forcer le runtime à préfetcher (cf. `intent` crate).
- Mode lazy : queue de mutations différées appliquées au prochain `get_or_generate` de la chunk concernée — pratique pour le streaming, mais demande de persister la file dans le snapshot.

### N6 — `WorldClient::snapshot_bytes` capture **chunks cachés** uniquement

`capture_snapshot` itère `manager.for_each_cached(...)`. Si l'eviction LRU (déjà crude — cf A2) a viré une chunk mutée mais que le voxel mutation est en cache disque (`persist`) ou nulle part → la mutation peut être **silencieusement perdue** au snapshot.

Trois actions nécessaires :
1. Garantir qu'une chunk avec `mutation_version > 0` est **pinnée** dans le cache (jamais évincée).
2. Documenter explicitement la sémantique de snapshot (« cached + mutated only »).
3. Ajouter un test : créer 2000 mutations sur 1000 chunks avec `cache_capacity: 100`, snapshot, restore, vérifier que les 2000 mutations sont là.

---

## 4. Roadmap mise à jour (deux semaines après l'audit initial)

### Reste de Phase A (priorité **absolue**, ~5 jours dev)

| Prio | Item                                | Effort | Bénéfice          |
|------|-------------------------------------|--------|--------------------|
| A2   | LRU réelle + pin des chunks mutées (lie N6) | 1.5 j | Stabilité long-run + intégrité snapshot |
| A3   | Spatial index `rstar`               | 2 j    | Débloque perception agents (toujours stub) |
| A4   | Raycast chunk-aware                 | 2 j    | Latence vision ÷ 10 |
| A5   | GPU erosion wired                   | 1 j    | Throughput chunk × 5 (cible BENCHMARKS.md) |

### Nouvelles items dérivés du delta-audit (à insérer **avant** Phase B)

| ID   | Item                                                       | Effort | Lié à |
|------|------------------------------------------------------------|--------|-------|
| N1-fix | Sentinel `inflight` pour éviter duplicate generation     | 1 j    | N1    |
| N2-fix | `[u32; 16]` array + `Biome::from_index` + test            | 0.5 j  | N2    |
| N3-fix | Canonicalisation NaN dans tous les `ContentAddressable` (audit float-hash global) | 1.5 j  | N3    |
| N4-test | Test déterminisme avec/sans macro-grid + hash en content-key | 1 j  | N4    |
| N5-fix | `MutError::ChunkNotLoaded` ou queue différée               | 1 j    | N5    |
| N6-fix | Pin des chunks mutées + test snapshot 2000 mutations       | 1 j    | N6 + A2 |

### Phase B inchangée — mais ne pas y toucher tant que A+N pas fini

---

## 5. Métriques (cibles inchangées + nouvelles)

À ajouter au harness de bench :

| Bench                                          | Cible      | Crate          |
|------------------------------------------------|------------|----------------|
| `chunk_gen_no_duplicate_under_concurrent_load` | 0 doublon  | `streaming`    |
| `dominant_biome_alloc_count`                   | 0          | `streaming`    |
| `weather_hash_stable_under_repeated_nan_injection` | bit-identical | `weather`  |
| `snapshot_restore_with_evicted_mutated_chunks` | 100 % recall | `agent-api`  |

---

## 6. Recommandations stratégiques (mise à jour)

1. **Geler les nouvelles crates** (`scenario`, `studio`) jusqu'à fin Phase A. Le moteur a une dette « interfaces agents IA » non comblée — c'est ce qui bloque la mission, pas un runner d'expériences FAIR.

2. **Auditer toutes les implémentations `ContentAddressable`** pour la canonicalité NaN (point N3). C'est le **seul** moyen de préserver la promesse « même seed = même monde » au fur et à mesure qu'on ajoute des passes (atmos, ecosystem-tick, …).

3. **Mettre en CI une property-test** `prop_compose! { fn arb_seed() } => same_world(s, s) is bit-identical` qui boucle sur plusieurs seeds, sur deux runs de la même binaire avec environnements différents (Linux + Windows si possible). Un seul faux-positif tue le crédit du moteur sur RL.

4. **Ne pas ajouter de nouveau crate avant la fin de Phase A + corrections N1-N6**. Hard limit, à formaliser dans `CONTRIBUTING.md`.

5. **`weather` crate : décision à prendre.** Si elle reste « anchor + FBM perturbations », c'est utile mais ce n'est pas la météo dynamique B3 promise. Soit on accepte ce niveau (et on remplace B3 par « advection humidité future »), soit on ajoute la passe advection sur l'output de `weather` pour rester dans la cible. Recommandation : accepter `weather` v0 actuel, ajouter une feature `advected_humidity` en module dédié dans `weather`, derrière feature flag.

---

## 7. Procédure suggérée pour les 5 prochains jours dev

```
J+1 :  N1 (inflight sentinel) + tests           [bug critique]
J+2 :  N2 (dominant_biome array) + N3 (NaN canonical) [perf + déterminisme]
J+3 :  A2 (LRU + pin mutated) + N6 (test 2k mut)      [stabilité]
J+4 :  A3 (spatial index rstar)                       [débloque perception]
J+5 :  A4 (raycast chunk-aware) + A5 (GPU wire)       [latence vision + throughput]
J+6 :  N4 (macro-grid determinism test) + N5 (MutError::ChunkNotLoaded)
```

Phase B peut ensuite démarrer (B1 tectonique dynamique, B2 hydro cross-chunk, B6 boids) dans l'ordre déjà documenté.

---

## 8. Annexe — Fichiers évolués depuis le 16 mai

```
nouveaux fichiers (sélection) :
  crates/agent-api/src/snapshot.rs              (~140 l)  ← A6
  crates/biome/src/koeppen.rs                              (Köppen-Geiger classifier)
  crates/cache/src/{l1,l2}.rs                              (split L1/L2)
  crates/core/src/{coupler,tick_domain}.rs                 (tick orchestration)
  crates/laws/src/{atmosphere,ecology,gravity,hydrology,thermo}.rs (laws physiques SI)
  crates/macro-bridge/src/{align,binary,lib}.rs            (Python↔Rust grid)
  crates/mesh/src/{lib,nets,simplify}.rs                   (mesh simplification)
  crates/physics/src/{constants,units}.rs                  (SI constants)
  crates/scenario/src/{lib,manifest,runner,schema}.rs      (YAML scenarios)
  crates/studio/src/main.rs                                (CLI binaire)
  crates/weather/src/lib.rs                                (anchor weather)
  crates/worldgraph/src/{branch,ctx,pass,pipeline,scheduler}.rs (DAG plus mature)

modifiés majeurs :
  crates/agent-api/src/lib.rs       (apply_pending wired, snapshot intégré)
  crates/streaming/src/manager.rs   (macro-bridge align, encore crude evict)
  crates/streaming/src/chunk.rs     (set_voxel_world ajouté)
  crates/pybindings/src/lib.rs      (probable exposition snapshot — non vérifié en détail)
```

Aucun de ces fichiers ne touche aux six bottlenecks Phase B documentés dans `NEXT-LEVEL-AUDIT.md`. La progression réelle est concentrée sur l'**outillage** (FAIR, snapshot, laws SI) plutôt que sur le **réalisme** (tectonique, hydrologie, écosystème).

---

**Fin du delta-audit 2026-05-27.**
Document généré automatiquement par tâche planifiée `analyse-le-projet-regarde-si-il-y-a-des-amelioration`.
