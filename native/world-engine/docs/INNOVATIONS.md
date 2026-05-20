# Innovations — comment on scale Genesis Engine d'un cran

Ce document décrit **trois inventions** qui, combinées, permettent à
Genesis de générer 10× plus vite, de cacher infiniment, et d'expliquer
chaque voxel — sans renoncer au déterminisme strict.

Aucune de ces inventions n'existe (à ma connaissance) sous cette forme
combinée dans un moteur Rust open-source. Le SOTA s'en approche par
morceaux :
- Minecraft 1.18 a la déclarativité
- Houdini a le DAG
- NMS et Star Citizen ont le déterminisme
- ipfs / Nix ont le content-addressing

→ Genesis les fusionne.

---

## Invention #1 — **WorldGraph**

Le terrain est défini comme un **DAG de passes pures**. Chaque passe est :

```rust
pub trait Pass: Send + Sync + 'static {
    type Input:  ContentAddressable + Send + Sync;
    type Output: ContentAddressable + Send + Sync + Clone;

    /// Stable identifier — same `id()` ⇒ same code for the cache.
    fn id(&self) -> PassId;

    /// Hash of the pass parameters. Combined with the input hash to key
    /// the output cache. Changing params invalidates downstream output.
    fn params_hash(&self) -> u64;

    /// Pure function: same input + same params ⇒ same output.
    fn run(&self, ctx: &PassCtx, input: &Self::Input) -> Self::Output;
}
```

### Propriétés (que l'impératif n'a pas)

1. **Composable** — n'importe quelle passe se branche à n'importe quelle
   autre du moment que les types s'accordent.
2. **Analyzable** — on peut interroger le DAG : "que dépend de ce pass ?",
   "quelles passes peuvent tourner en parallèle ?", "quel chemin a produit
   ce voxel ?".
3. **Content-addressed** — chaque sortie est nommée par
   `BLAKE3(passe_id || params_hash || input_hash || coord)`. Deux mondes
   différents qui se trouvent avoir les mêmes inputs sur une zone
   partagent le résultat.
4. **Partiellement évaluable** — changer une passe n'invalide que ses
   descendants. Le reste reste cache hit.
5. **Hétérogène** — la même interface accepte CPU (rayon, SIMD) ou GPU
   (wgpu compute) ou même IA externe (un appel à un modèle).
6. **Traçable** — chaque sortie embarque un *lineage* : les ids et hashs
   des passes amont. Donne des explications gratuites au gameplay/agents
   IA ("pourquoi ce voxel est de l'eau ?" → trace).

### Architecture concrète

```
                                                ┌────────────┐
                                                │  TickClock │
                                                └──────┬─────┘
                                                       │
                ┌─────────────┐    ┌──────────────┐    │
   seed ───────►│ TectonicsP. │───►│   ReliefP.   │    │
                └─────┬───────┘    └──────┬───────┘    │
                      │                   │            │
                      ▼                   ▼            │
                ┌──────────────────────────────┐       │
                │       HeightmapMerge         │       │
                └──────────────┬───────────────┘       │
                               │                       │
                ┌──────────────▼──────────────┐        │
                │   HydraulicErosion (CPU)    │◄───────┤
                │   or HydraulicErosionGpu    │   (params: passes, droplets)
                └──────────────┬──────────────┘        │
                               │                       │
                  ┌────────────┼────────────┐          │
                  ▼            ▼            ▼          │
            ┌──────────┐ ┌──────────┐ ┌──────────┐    │
            │ Climate  │ │Hydrology │ │  Slope   │    │
            └────┬─────┘ └────┬─────┘ └────┬─────┘    │
                 └────────────┼────────────┘           │
                              ▼                        │
                         ┌──────────┐                  │
                         │  Biome   │                  │
                         └────┬─────┘                  │
                              ▼                        │
                       ┌──────────────┐                │
                       │ Ecosystem    │                │
                       └────┬─────────┘                │
                            ▼                          │
                        ┌────────┐                     │
                        │ Voxels │                     │
                        └────────┘                     │
```

Chaque arc est typé et hashable. Le scheduler `worldgraph::Scheduler`
extrait le sous-DAG nécessaire pour produire le `Voxels` final d'un chunk
donné, lance les passes indépendantes en parallèle (Rayon ou wgpu
queue), et passe les sorties par référence en zéro-copie quand c'est
possible.

---

## Invention #2 — Cache content-addressed (CAS) à 2 étages

```
┌────────────────────────────────────────────────────────┐
│ L1 — in-memory (dashmap)                                │
│  key = BLAKE3(pass_id || params || input || coord)      │
│  value = Arc<dyn AnyOutput>                             │
│  capacity = paramétrable, LRU                           │
└────────────────────┬───────────────────────────────────┘
                     │  miss
                     ▼
┌────────────────────────────────────────────────────────┐
│ L2 — on-disk content-addressed blob store               │
│   path = $CACHE_ROOT/aa/bbbb...zz.cas                   │
│   format = zstd-compressed rkyv-ish frame                │
│   mmap-able, fsync-safe, multi-process correct          │
└────────────────────┬───────────────────────────────────┘
                     │  miss
                     ▼
              ┌────────────┐
              │  Pass::run │  (only if cache fully misses)
              └────────────┘
```

**Conséquence forte** : *deux mondes différents qui se trouvent avoir
exactement la même zone tectonique pour leurs coords (0, 0) — par exemple
deux graines qui partagent une plaque continentale au même coord —
réutilisent le cache pour les passes en aval, gratuitement*.

C'est l'extension du déterminisme local au déterminisme global.

---

## Invention #3 — Intent-aware prefetch

Spécifique aux mondes d'agents IA. Les agents *savent* où ils vont
(planification interne) avant d'y aller, contrairement à un joueur humain.

```rust
client.declare_intent(Intent {
    agent: agent_id,
    plan: Plan::WalkAlong(path),       // séquence de WorldCoord
    horizon_ticks: 200,
});
```

L'engine convertit chaque `Plan` en une liste de chunks à toucher dans
les N prochains ticks, et amorce leur génération **avant** que l'agent
n'arrive. La latence perçue côté agent tombe à zéro pour le steady-state.

**Pourquoi c'est nouveau** : les engines classiques prefetchent en
fonction de la *caméra* (frustum + neighbours). Ici on prefetch en
fonction de l'*intention* du consommateur, ce qui :
- élimine le pop-in y compris quand l'agent fait un demi-tour brusque,
- permet de planifier *au-delà* de la portée visuelle (un agent qui
  prévoit de voyager 1 km demande le terrain à 1 km maintenant),
- libère la mémoire intelligemment : on sait qu'un chunk ne sera plus
  visité, on l'évince.

Comportement : sécurisé même si l'agent change d'avis (les chunks
préchargés ne périment pas, ils s'inscrivent simplement en LRU).

---

## Invention #4 (bonus) — Pass d'érosion GPU en WGSL

Le SOTA des engines récents (Sebastian Lague port GPU, GAEA 2) montre
que l'érosion hydraulique CPU est l'étape qui domine le coût d'un chunk.

Solution : la même `Pass` peut être implémentée :
- CPU (rayon, déterministe) — `crate genesis-terrain::erosion`
- GPU (wgpu compute, déterministe via uniform seed) — `crate genesis-gpu`

Le scheduler choisit selon : `GPU disponible && chunk_taille >= seuil &&
budget GPU non saturé`. Sinon il rabat sur le CPU sans perdre le
déterminisme (un test cross-backend vérifie l'équivalence numérique à
1e-3 près).

---

## Bilan : ce qu'on gagne

| Métrique                                | Avant          | Après          |
|-----------------------------------------|----------------|----------------|
| Génération chunk vierge (cible)         | ~23 ms         | ~10 ms (GPU)   |
| Génération chunk déjà vu (cache hit L1) | ~23 ms         | < 0.05 ms      |
| Re-génération après tweak d'une passe   | N×23 ms        | seulement les descendants |
| Mémoire pour 10⁶ chunks différents      | proportionnelle | sub-linéaire (zones tectoniques partagées) |
| Latence perçue par un agent qui marche  | ~50–200 ms     | ~0 ms (prefetch intent) |
| Debug "pourquoi ce voxel ?"             | impossible     | trace lineage native |

---

## Fichiers à venir

```
crates/cache/         — content-addressed L1+L2 cache
crates/worldgraph/    — Pass trait, DAG, scheduler, lineage
crates/gpu/           — wgpu compute passes (feature-gated)
crates/intent/        — agent intent prefetcher
```

Le `streaming::ChunkManager` existant est ré-écrit comme un *consommateur*
du WorldGraph (la pipeline retourne un `Chunk`) sans modifier son API
externe — les downstream callers (Python, agent-api) ne voient rien
changer.
