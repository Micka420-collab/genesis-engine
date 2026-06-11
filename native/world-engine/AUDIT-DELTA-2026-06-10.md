# Genesis World Engine — Delta-Audit 2026-06-10

**Mode :** suivi automatique (scheduled task `analyse-le-projet-regarde-si-il-y-a-des-amelioration`). Successeur de [`AUDIT-DELTA-2026-05-27.md`](./AUDIT-DELTA-2026-05-27.md) (lui-même successeur de [`NEXT-LEVEL-AUDIT.md`](./NEXT-LEVEL-AUDIT.md) du 2026-05-16).
**Périmètre :** workspace Rust `native/world-engine/` — **23 crates** (était 22 au 2026-05-27, +1 = `genesis-geology`).
**Objet :** delta sur ~14 jours. Trois fronts à mesurer :
1. Suivi des risques **N1–N6** ouverts par la session précédente (corrigés / pas corrigés).
2. Avancement résiduel **Phase A / B / C**.
3. Nouveaux risques **D1–D5** introduits ou amplifiés par l'activité récente.

---

## 0. Verdict express

> En 14 jours : **0 item Phase A ou B mergé**. En face, **14 Waves d'observateurs** (49→63) ont été shippées dans le runtime Python, plus une nouvelle crate Rust (`genesis-geology`) qui sert l'émergence couleur des minéraux. Le projet ressemble de plus en plus à un **laboratoire scientifique d'observation** et de moins en moins à un **moteur de monde** — l'écart entre les deux roadmaps (réalisme observé vs. capacité du moteur) se creuse.

> **Recommandation principale** : freezer les nouveaux observateurs (Waves 64+) **jusqu'à** clôture de A3 (spatial index), A4 (raycast chunk-aware) et A5 (GPU wire), puis enclencher au moins **un** item Phase B (B6 boids ou B1 tectonique) sinon "Phase A" restera un projet zombi alors que les observateurs scientifiques mesurent un monde de plus en plus statique sous le capot.

### Score Phase A après 25 jours dev (depuis le 2026-05-16)

| Item | Cible            | 2026-05-27   | 2026-06-10   | Glissement |
|------|------------------|--------------|--------------|------------|
| A1   | apply_pending    | ✅ fait      | ✅ stable    | —          |
| A2   | LRU réelle       | ❌ crude FIFO | ⚠ pin-mutated patch (toujours O(N) scan, **pas** une vraie LRU) | partiel    |
| A3   | Spatial index    | ❌ stub      | ❌ stub identique | **stagnation** |
| A4   | Raycast accéléré | ❌ DDA naïf  | ❌ DDA naïf identique | **stagnation** |
| A5   | GPU erosion wire | ❌ pas wired | ❌ pas wired (genesis-gpu non importé par streaming) | **stagnation** |
| A6   | Snapshot/restore | ✅ bincode+zstd | ✅ + pin de chunks mutées (N6-fix) | renforcé |
| A7   | Fog-of-war       | ⚠ partiel    | ⚠ partiel (pas de `observe_area_filtered`) | stagnation |

**A1+A6 livrés (29 % de Phase A). 3 items stagnent depuis 25 jours.** L'effort dev n'a pas été allocé sur le backlog architectural ; il a basculé sur la couche émergence (cf. §3).

---

## 1. Suivi des risques N1–N6 ouverts par la session précédente

| ID  | Risque                                                | État 2026-06-10 | Preuve                              |
|-----|-------------------------------------------------------|-----------------|--------------------------------------|
| N1  | Race `get_or_generate` (leader ne se met pas dans la file) | ✅ **CORRIGÉ** | `streaming/src/manager.rs:88-123` : nouveau `InflightGuard` + `Entry::Vacant.insert(Vec::new())` + RAII drop pour cleanup ; double-check cache après lock ; `loop` au lieu de `return rx.await.expect(...)` (panic-safe). |
| N2  | `dominant_biome` allocation HashMap + match fragile   | ✅ **CORRIGÉ** | `streaming/src/manager.rs:483-497` : remplacé par `[u32; Biome::COUNT]` + `Biome::from_index(best_idx)`. Tests `dominant_biome_picks_majority` ajoutés (≥3). |
| N3  | Hash non-NaN-safe sur `ContentAddressable<f32>`        | ✅ **CORRIGÉ** | `worldgraph/src/pass.rs:69-78` : `pub fn hash_f32(h, v)` et `hash_f64` canonicalisent `v.is_nan()` vers un quiet-NaN unique. `weather` migré (`hash_f32(h, c.precipitation_mm_h)`). |
| N4  | `macro-bridge` source d'entropie externe non testée   | ⚠ **PARTIEL**    | Variant `MutError::ChunkNotLoaded` existe (`agent-api/src/lib.rs:42-43`) ; **test E2E déterminisme avec/sans macro-grid pas localisé** ; hash de la grille macro non confirmé intégré au content-key. |
| N5  | `set_voxel` génère synchrone full pipeline             | ❌ **PAS CORRIGÉ** | `streaming/src/manager.rs:319-332` : `set_voxel` appelle toujours `get_or_generate_blocking(coord)` → pipeline complète (heightmap+érosion+climat+biome+voxel). Variant `MutError::ChunkNotLoaded` ajouté mais **non utilisé sur le hot-path**. 100 écritures lointaines par tick = encore 2-3 s. |
| N6  | Snapshot perd les chunks mutées évincées               | ✅ **CORRIGÉ** | `streaming/src/manager.rs:207-234` `maybe_evict` skip toute chunk avec `mutation_version > 0` (pinned). `restore_chunk_voxels` re-insère après `restore`. |

**Résultat : 4/6 corrigés, 1 partiel, 1 ouvert.** Bon ratio sur les bugs déterministes ; N5 reste un pied dans la latence agent.

---

## 2. Avancement Phase A + Phase B (delta)

### Phase A — reste 5 jours dev sur 7 jours initiaux estimés

| Prio | Item                            | État        | Commentaire delta                   |
|------|---------------------------------|-------------|--------------------------------------|
| A2   | Vraie LRU + tier pinned         | ⚠ partiel   | `maybe_evict` skip les mutées (pinning fonctionnel) mais reste un **scan O(N)** sur tout le cache à chaque insert. Pas de priority queue par `last_touch_tick`. Une vraie LRU reste à coder. |
| A3   | Spatial index (`rstar`)         | ❌ **stub identique** | `agent-api/src/lib.rs:306-309` : `entities_in_radius` retourne `Vec::new()` avec commentaire "the entity index lives in the agent runtime, not in the world engine". **Décision de contrat non actée** : soit on l'assume (le moteur n'a **pas** d'index spatial — alors documenter), soit on tient l'engagement (alors implémenter). En l'état, c'est un stub muet qui ment au caller. |
| A4   | Raycast chunk-aware             | ❌ **DDA naïf identique** | `agent-api/src/lib.rs:312-335` : toujours `step = 0.5_f32` constant, `t += step`, et appel `self.voxel(wc)` qui re-lock un chunk **à chaque pas**. Sur 100 m de range = 200 lookups × 1 RwLock.read par lookup. **Bloque la perception agent à toute échelle hors cellule unique.** |
| A5   | GPU erosion auto-fallback       | ❌ **pas wired** | `genesis-gpu` n'est pas listé dans `streaming/Cargo.toml`. Aucune branche `if gpu_available { HydraulicErosionGpu::run } else { cpu_erosion }`. Le throughput chunk reste plafonné CPU. |
| A7   | Fog-of-war filter               | ⚠ partiel   | `observe_area_filtered(p, radius_m)` reste absent. Le fichier proposal `proposals/axis5_agent_api/fog_of_war.rs` est **toujours là, jamais promu**. |

### Phase B — état 0 %

| ID | Item                                | État | Code source observé |
|----|-------------------------------------|------|---------------------|
| B1 | Tectonique dynamique (advection Lagrange) | ❌ | `terrain/src/tectonics.rs:1-78` : Voronoi statique à requête lazy, `motion: [f32; 2]` calculé mais **jamais utilisé** (cohérent avec audit 2026-05-16). |
| B2 | Hydrologie cross-chunk              | ❌ | `hydrology/src/lib.rs:34-78` : tri séquentiel par-chunk, voisins clampés à `[1, w-1] × [1, h-1]`. La rivière meurt au bord. |
| B3 | Climat dynamique (advection humidité) | ❌ | `weather` crate ajoutée mais c'est un anchor + FBM perturbation, **pas une advection**. Pas d'ombre pluviométrique. |
| B4 | Saisons + diurne                    | ❓ | non audité aujourd'hui — voir delta précédent ; suspect inchangé. |
| B5 | Voxel SDF 3D (caves)                | ❌ | `streaming/src/manager.rs:500-551` `column_material(z, surface_z, biome, …)` : signature 1D-colonne intacte. Pas d'`is_cave_at(wx,wy,wz)`. **L'action agent « creuser une cave » n'a aucune surface matérielle à creuser.** |
| B6 | Boids + chaîne alim                 | ❌ | `ecosystem/src/lib.rs:1-100` : `flora_for_chunk` retourne `SmallVec<FloraInstance>` statique, `fauna_for_chunk` (cf. tail) retourne `FaunaSeed` sans tick. Pas de update runtime. |
| B7 | Hot-reload `BiomeRegistry`          | ❌ | `notify` toujours pas en dep. |
| B8 | Debug overlay HTTP                  | ❌ | aucun endpoint `/debug/*`. |

### Phase C — non démarré (attendu).

### Proposals — toujours non promues

```
proposals/axis1_geology/dynamic_tectonics.rs        ← 25 jours dans la salle d'attente
proposals/axis1_geology/sdf_caves.rs                ← idem
proposals/axis2_climate/advected_humidity.rs        ← idem
proposals/axis2_climate/seasons.rs                  ← idem
proposals/axis3_ecosystem/boids.rs                  ← idem
proposals/axis3_ecosystem/food_web.rs               ← idem
proposals/axis4_performance/lru.rs                  ← idem (A2 partiellement résolu via patch direct)
proposals/axis4_performance/spatial_index.rs        ← idem (A3 stagne)
proposals/axis4_performance/gpu_pipeline.rs         ← idem (A5 stagne)
proposals/axis5_agent_api/fog_of_war.rs             ← idem (A7 stagne)
proposals/axis6_devtools/hot_reload.rs              ← idem (B7 stagne)
proposals/axis6_devtools/debug_overlay.rs           ← idem (B8 stagne)
```

**Question stratégique** : ces stubs ont coûté du temps à écrire (~1900 lignes). Soit ils sont obsolètes — alors les marquer `DEPRECATED.md` et les archiver — soit ils sont la roadmap — alors **les promouvoir un par un**. Les laisser pourrir entre les deux est un signal négatif.

---

## 3. Activité réelle sur la fenêtre 2026-05-27 → 2026-06-10

### 3.1 Commits engine (top-level)

`git log --oneline` sur `genesis-engine/` montre **14 commits Wave** sur la fenêtre, et **0** sur le backlog Phase A/B :

| Date       | Wave | Titre commit                                                          | Type             |
|------------|------|-----------------------------------------------------------------------|------------------|
| 2026-05-29 | 49   | watershed observer (Strahler + Horton + drainage density)             | observer (lecture) |
| 2026-05-29 | 50   | frost weathering (Walder & Hallet)                                    | observer (lecture) |
| 2026-05-30 | 53   | LTI river-discharge routing                                            | observer (lecture) |
| 2026-06-01 | 55   | transient linear-reservoir hydrograph                                 | observer (lecture) |
| 2026-06-02 | 57   | sediment Exner (lit mobile, transport sédimentaire)                   | observer (lecture) |
| 2026-06-03 | 58   | open-endedness / evolutionary activity (Bedau-Packard)                | observer (lecture) |
| 2026-06-06 | 60   | behavioral illumination / MAP-Elites + novelty search                 | observer (lecture) |
| 2026-06-10 | 61   | elastic lithospheric flexure (Vening-Meinesz)                         | observer (lecture) |
| 2026-06-10 | 62   | hypsometry / landscape-maturity (Strahler 1952)                       | observer (lecture) |
| 2026-06-10 | 63   | channel-concavity / chi-steepness (Flint + Perron-Royden)             | observer (lecture) |

Quatre autres waves (54, 56, 59) mentionnées dans le log sont du **même registre** : observateurs purs read-only. **Aucun** commit ne touche `streaming/manager.rs::set_voxel`, `agent-api/lib.rs::raycast` ou `entities_in_radius`, `hydrology/lib.rs` (modèle), `ecosystem/lib.rs` (tick), `terrain/tectonics.rs` (motion).

### 3.2 Nouvelle crate

`genesis-geology` (`crates/geology/{lib.rs, chemical.rs, mineral.rs, rock.rs, visual.rs}`) — sert l'**émergence visuelle** des minéraux (cohérent avec la règle d'or "no scripting" de la mémoire `feedback_no_scripting`). C'est un ajout **légitime** au pipeline procédural ; pas une dette implicite comme `scenario`/`studio` listés au delta précédent. Reste pédagogique : ne participe pas encore au worldgraph DAG en tant que `Pass` (à vérifier en hash-into).

### 3.3 Lecture stratégique

Le projet a pris une **double trajectoire qui diverge** :

1. **Couche Python (`runtime/engine/*_observer.py`)** : 14 observateurs scientifiques en 14 jours. Bench de tests : **389/389 verts**. Score "réalisme Terre" pondéré : **~79,0 %** (objectif 80 %). C'est **excellent** pour la dimension scientifique / falsifiabilité ([`FALSIFIABILITY.md`](./FALSIFIABILITY.md)).

2. **Couche moteur Rust (`native/world-engine/crates/*`)** : 0 nouvelle capacité côté actions agents, écosystème ou tectonique. Le moteur **reste générique** comme noté dans l'audit du 16 mai — il a juste reçu un patch sécurité (N1, N2, N3, N6).

**Cassure de cohérence** : le score réalisme à 79 % est mesuré **par observation passive du monde Python**, qui contient un macro-bridge vers Rust mais dont le tick effectif passe **côté Python** (`Simulation.step()`). Quand un agent décide de creuser, l'action n'a pas où atterrir côté Rust (B5 absent, N5 ouvert). Quand un agent veut percevoir un congénère, `entities_in_radius` retourne vide (A3 ouvert). On mesure de plus en plus précisément un système qui n'est pas instrumenté pour les interventions qu'on lui prête.

> **Métaphore** : on construit le **sismographe** avant la **maison**. C'est défendable si la maison existait déjà ; ici elle est habitable mais sans portes.

---

## 4. Nouveaux risques détectés (D-series, delta 2026-06-10)

### D1 — Treadmill d'observateurs : scope drift formel

**Symptôme** : 14 nouveaux modules `runtime/engine/*_observer.py` en 14 jours, tous read-only, tous additifs au tick. **Coût caché** :
- 14 calls supplémentaires par `Simulation.step()` quand tout est enregistré.
- 14 hooks dans `make validate-all` (p119 → p132).
- Cohérence des invariants : chaque observer prétend être "additif, pur, read-only strict" — mais une fois en chaîne, **un bug dans un observer peut hooker un autre** via état global mutable (`sim.step` wrapping). À vérifier : le wrap multiple est-il idempotent ? (Memoirs de Wave 60 mentionnent "install/uninstall idempotents (wrap unique de sim.step)" — confirmer la garantie cross-observer.)

**Fix proposé** : 
- (i) un registre central d'observateurs avec ordre déterministe et garantie "au plus un wrap" cross-observer ; 
- (ii) un budget tick global instrumenté (cible : observers cumulés < 10 % du tick) ; 
- (iii) moratoire Wave 64+ jusqu'à clôture d'au moins un item Phase A ou B.

### D2 — `maybe_evict` reste O(N) scan, dégénère quand mutations dominent

**Localisation** : `streaming/src/manager.rs:207-234`.

```rust
for kv in self.cache.iter() {                       // O(N) scan
    if to_drop.len() >= excess { break; }
    let chunk = kv.value().read();                  // O(1) lock par chunk
    if chunk.meta.mutation_version == 0 { to_drop.push(*kv.key()); }
}
```

**Problème delta** :
1. **Quand le cache se remplit de chunks mutées**, le scan termine sans rien évincer et `cache.len() > cap` durablement. Le commentaire dit "soft cap" — mais aucune métrique ne surveille la dérive.
2. **Aucun ordre LRU** : le premier chunk non-muté rencontré est viré, même s'il vient d'être touché. Sur un parcours agent oscillant entre 2 zones, c'est typiquement le chunk encore actif qu'on évince.
3. **Aucun test** sur le scénario : 1000 chunks insérés, 500 mutés, capacity=200 → comportement attendu non spécifié.

**Fix** : transformer `maybe_evict` en vraie LRU (priority queue par `last_touch_tick`) **avec** double tier (mutated/clean). Promotion partielle de `proposals/axis4_performance/lru.rs` (~150 lignes). Test ciblé : `lru_evicts_clean_before_mutated` + `cache_drift_alert_when_all_pinned`.

### D3 — Coupling implicite agent-runtime ↔ moteur via `entities_in_radius` muet

**Localisation** : `agent-api/src/lib.rs:306-309`.

```rust
fn entities_in_radius(&self, _p: WorldCoord, _r: f32) -> Vec<EntityRef> {
    // Stub — the entity index lives in the agent runtime, not in the
    // world engine. The Python layer will populate this.
    Vec::new()
}
```

**Problème delta** : ce stub a 25 jours. Le commentaire affirme un **transfert de responsabilité** vers le runtime Python, mais :
- aucun **trait** ne déclare ce contrat (pas de `pub trait EntityIndex` côté Python qu'un module spatial implémente).
- aucun **test E2E** ne vérifie qu'un agent Python qui voit un autre agent Python passe par cette API.
- la fonction est **encore présente** dans la trait `WorldView` et retourne `Vec::new()`. Tout code Rust qui l'appelle reçoit silence.

**Risque réalisé** : un futur observateur ou un code agent qui aurait été écrit en supposant que cette API marche reçoit zéro entité et **considère le monde vide**. Bug de catégorie "promise rompue" qui ne pète pas en compile time.

**Fix** : soit
- (a) supprimer la méthode de `WorldView` et la remplacer par une type marker `MoteurNeFournitPasIndexSpatial` que le Python doit fournir (rupture explicite, propre) ;
- (b) implémenter rstar (proposal `axis4_performance/spatial_index.rs` à promouvoir, 2 jours dev).

L'option (b) reste **recommandée** parce qu'une vraie présence multi-agent (Wave 60 illumination, Wave 58 evolutionary activity) **exige** une perception entre agents pour mesurer les vraies dynamiques sociales. Le runtime Python actuel peut "voir" un agent par scan O(N) mais ne le scale pas.

### D4 — Décorrélation entre score "réalisme Terre" et capacités effectives du moteur

**Source** : `PROJECT-STATUS.md` annonce 79,0 % de réalisme Terre pondéré, dimension "Pont Python ↔ Rust" à 82 %.

**Problème delta** : la métrique "Pont Python ↔ Rust" reste à 82 % alors que :
- `entities_in_radius` rend vide (D3).
- `set_voxel` synchrone et lent (N5).
- `raycast` naïf O(distance) (A4 ouvert).
- GPU pas wired (A5 ouvert).

Le pont **fonctionne pour les chunks et le snapshot** mais **pas pour la boucle action-perception-mutation** en charge. Le 82 % est probablement mesuré sur la couverture API (surface), pas sur la latence ni le throughput sous charge.

**Fix** : ajouter au `ROADMAP-REALISME-TERRE.md` un **sous-score perception/action** distinct du sous-score chunks, et tracker A3+A4+A5 dedans. Sans quoi le score global devient un mensonge par omission.

### D5 — Absence d'audit de la chaîne de Pass `worldgraph` après ajout de la crate `geology`

**Contexte** : 23 crates contre 22 il y a 14 jours. Le `worldgraph` DAG est l'innovation centrale ; chaque nouvelle Pass doit être hashable et déterministe. La crate `geology` ne fait pas (encore ?) partie du DAG — à vérifier.

**Risques** :
- Si `geology` est appelée **hors DAG**, le content-hash d'un chunk **ne reflète plus** son contenu géologique. Cache miss permanent ou cache hit incorrect selon le sens.
- Si `geology` est appelée **dans DAG mais sans `ContentAddressable`**, deux runs du même seed peuvent produire deux hashes différents → cache cassé.

**Fix proposé** : un test `crate_geology_pass_is_content_addressable` qui force la hashabilité et un audit explicite (5 minutes) de qui appelle qui dans le `Scheduler::run` actuel. Sinon le déterminisme bit-à-bit du moteur — fondement du RL training — est silencieusement fragilisé.

---

## 5. Roadmap mise à jour (recommandation 2026-06-10)

### Priorité 0 — Stabilisation moteur (5–6 jours dev, **avant toute Wave 64+**)

| Item | Effort | Source proposal       | Bloque                  |
|------|--------|------------------------|--------------------------|
| A3   | 2 j    | `axis4/spatial_index`  | Perception multi-agent, métriques sociales émergentes (Wave 58/60 ont besoin) |
| A4   | 2 j    | (à coder)              | Latence vision agent ÷10 |
| A5   | 1 j    | `axis4/gpu_pipeline`   | Throughput chunk ×5      |
| D2-fix | 1 j  | `axis4/lru` (partielle)| Stabilité long-run + intégrité snapshot |
| D5-test | 0.5 j | (nouveau test)       | Déterminisme worldgraph + geology |

### Priorité 1 — Une faille B au choix (5–10 jours dev)

Le projet a besoin d'**un signal fort** que Phase B existe. Pas tout, **un seul** :

- **B6 (Boids + Lotka-Volterra)** — débloque la dimension écologie/hydrologie de 73 → 78 sans demander d'audit cross-crate massif. Lié à `proposals/axis3_ecosystem/{boids,food_web}.rs`. Mesurable via tests *_deterministic, surface d'audit limitée à 1 crate (`ecosystem`). **Recommandé**.

OU

- **B5 (SDF caves)** — débloque enfin l'action agent "creuser" et donne du volume au monde. Lié à `proposals/axis1_geology/sdf_caves.rs`. Impact rendu + gameplay direct. Petit risque sur la perf (SDF 3D évalué à la voxel — à benchmarker).

**Pas les deux.** Choisir et clore.

### Priorité 2 — Décision proposals (1 jour)

Quel que soit le choix B1/B6 : faire le **tri des proposals** en une session.

- Promouvoir : la proposal du B choisi.
- Archiver : tout ce qui ne sera pas attaqué d'ici la fin du Q3 → `proposals/ARCHIVED-2026-06.md` + suppression des fichiers.

Laisser 12 fichiers stubs de 25 jours pourrir est un signal projet négatif.

### Phase C — toujours non démarré (correct).

---

## 6. Métriques à instrumenter

À ajouter au harness de bench :

| Bench / metric                                        | Cible        | Crate           |
|-------------------------------------------------------|--------------|------------------|
| `observer_chain_time_per_step` (Python)               | < 10 % tick  | runtime          |
| `cache_drift_when_mutation_dominated`                 | borné        | streaming        |
| `entities_in_radius_with_1000_entities`               | < 100 µs     | agent-api        |
| `raycast_p50_at_50m`                                  | < 1 ms       | agent-api        |
| `set_voxel_when_chunk_not_loaded_returns_error`       | strict       | agent-api        |
| `worldgraph_hash_includes_geology_layer`              | bit-stable   | worldgraph + geology |

---

## 7. Recommandations stratégiques

1. **Geler les Waves observateurs 64+** jusqu'à clôture A3, A4, A5 et un B au choix. La règle est dure : c'est la seule manière d'éviter qu'un treadmill se réinstalle pour les 14 prochains jours.

2. **Formaliser dans `CONTRIBUTING.md`** : "Pas de nouvelle Wave d'observateur tant que le tableau Phase A n'a pas au moins 5/7 items à ✅". C'est ce qui aurait évité l'écart d'aujourd'hui.

3. **Découpler le score réalisme du score capacité moteur** dans `ROADMAP-REALISME-TERRE.md`. Le premier mesure ce qu'on observe ; le second mesure ce que les agents peuvent faire. Aujourd'hui ils sont confondus à 79 % global. Sortir un sous-score "Capacités moteur" (~50 % réel : A3, A4, A5, B1, B2, B5, B6 = 0/7) sera salutaire.

4. **Audit déterminisme géologique** (D5) avant la prochaine Wave géologie. Si `geology` est appelée hors DAG, **n'importe quel** observateur de la couche (cryoclastie, isostasie, flexure, hypsométrie, χ) hérite du bug.

5. **Décider du sort des 12 proposals.** Soit on les promeut, soit on les archive. La zone grise actuelle envoie le mauvais signal aux contributeurs.

---

## 8. Procédure suggérée pour les 6 prochains jours dev

```
J+1 : A3 (spatial_index rstar) + test D3 (entité présente → trouvée)         [débloque perception]
J+2 : A4 (raycast chunk-aware DDA) + bench                                    [vision agent ÷10]
J+3 : A5 (genesis-gpu wired dans streaming/Cargo.toml + fallback)             [throughput ×5]
J+4 : D2-fix (vraie LRU 2 tiers) + tests cache_drift                          [stabilité long-run]
J+5 : D5-test (worldgraph hash inclut geology) + audit Pass DAG                [déterminisme]
J+6 : B6 démarrage (boids déterministes, 1 chunk) — première moitié           [écosystème vivant]
```

Wave 64 (observer) reste autorisée à partir de J+7, **si** A3/A4/A5/D2 sont mergés.

---

## 9. Annexe — Inventaire 23 crates

```
agent-api      biome        cache        climate      core
ecosystem      geology★     gpu          hydrology    intent
laws           macro-bridge mesh         noise        persist
physics        pybindings   scenario     streaming    studio
terrain        weather      worldgraph
```

★ = ajouté depuis le delta 2026-05-27 (Wave 43 du runtime Python ; sert les indices visuels minéraux pour émergence agent).

Aucune crate retirée. Aucune fusion. Trois crates "hors mandat moteur de monde" toujours présentes (`scenario`, `studio`, `laws`) — le delta 2026-05-27 recommandait de les geler, recommandation **toujours d'actualité**.

---

## 10. Annexe — Fichiers évolués depuis le 2026-05-27 (zone moteur)

```
nouveaux :
  crates/geology/src/{lib,chemical,mineral,rock,visual}.rs       Wave 43

modifiés majeurs :
  crates/streaming/src/manager.rs        N1 InflightGuard + N2 dominant_biome array + N6 pin mutated
  crates/worldgraph/src/pass.rs          N3 hash_f32/hash_f64 canonicaux + helpers SerdeWrapper
  crates/agent-api/src/lib.rs            MutError::ChunkNotLoaded variant ajouté (non utilisé)
  crates/agent-api/src/snapshot.rs       restore_chunk_voxels + pinning (N6-fix coté API)
  crates/weather/src/lib.rs              migration vers hash_f32 (N3-fix)

inchangés (mais ciblés par l'audit) :
  crates/terrain/src/tectonics.rs        Voronoi statique, motion non utilisé (B1)
  crates/hydrology/src/lib.rs            sort sequential par-chunk (B2)
  crates/ecosystem/src/lib.rs            seeds only, pas de tick (B6)
  crates/streaming/src/manager.rs::column_material  1D-column (B5)
  crates/agent-api/src/lib.rs::entities_in_radius   stub Vec::new() (A3)
  crates/agent-api/src/lib.rs::raycast              DDA naïf step=0.5 (A4)
  crates/streaming/Cargo.toml             genesis-gpu absent des deps (A5)
```

---

**Fin du delta-audit 2026-06-10.**
Document généré automatiquement par tâche planifiée `analyse-le-projet-regarde-si-il-y-a-des-amelioration`.
Successeur attendu : prochaine exécution (~2 semaines), à compléter avec le score Phase A et le sort des 12 proposals.
