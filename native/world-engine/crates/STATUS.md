# `native/world-engine/crates/` — STATUS (état des 23 crates)

**Créé :** 2026-06-16 (J+6) — ferme **R1** du `BLIND-SPOTS-AUDIT-2026-06-13`
(« audit des 8 crates non lues », dette de transparence J+30).
**Méthode :** inspection **source uniquement** — `cargo`/`rustc` sont **absents**
de l'environnement (cf. [ADR-0008](../../../adr/0008-python-rust-frontier.md), D7).
Aucune affirmation ci-dessous n'est garantie par une compilation : la **CI est la
seule source de vérité** pour le statut de build réel.

> **Cadre ADR-0008.** L'arbre `native/world-engine/` entier est le **substrat
> worldgen gelé (Wave 42)** + oracle de contrat. La couche de simulation/perception
> *active* du projet est le runtime **Python** (`runtime/engine/`). Ici « active »
> signifie donc **« intégrée au graphe de dépendances du worldgen Rust »**, pas
> « en développement actif ». Aucune de ces crates n'a reçu de commit depuis
> Wave 42 (D7, 31 j).

---

## Tableau (30 s/crate)

Colonne **Dépendée par** = crates **du workspace** qui l'importent (reverse-deps).
Une crate que personne n'importe et qui n'est pas un binaire top-level = **orpheline**.

| Crate | ~LOC | Rôle (1 ligne) | Dépendée par (workspace) | Statut |
|-------|------|----------------|--------------------------|--------|
| `core` | 778 | Primitives déterministes (seed, tick, voxel, coord, math) | **toutes** (fondation) | active |
| `physics` | 328 | Unités SI fortes + constantes physiques réelles | laws, scenario, studio | active |
| `noise` | 382 | Bruits cohérents (simplex, FBM, ridged, domain-warp) | climate, ecosystem, terrain, weather, streaming | active |
| `laws` | 359 | Lois physiques (Stefan-Boltzmann, Saint-Venant, Darcy, Lotka-Volterra) | scenario, studio | active |
| `terrain` | 616 | Heightmap + tectonique + érosion (hydraulique, Kelvin-Helmholtz) | gpu, hydrology, macro-bridge, streaming | **active (backend live du pont Python `backend="terrain"`)** |
| `climate` | 184 | Température / humidité / vent (carte statique déterministe) | agent-api, biome, streaming, weather, scenario | active |
| `biome` | 688 | Classifieur Whittaker + registre de biomes extensible | agent-api, ecosystem, macro-bridge, pybindings, scenario, streaming | active |
| `hydrology` | 134 | Rivières/lacs/bassins (flux D8 + aire cumulée) | streaming | active |
| `ecosystem` | 202 | Règles de spawn flore/faune (Poisson-disk × densité biome) | streaming | active |
| `weather` | 240 | Météo évolutive (précip., fronts, tempêtes) comme passe WorldGraph | scenario | active |
| `worldgraph` | 1078 | DAG content-addressed des passes de worldgen | scenario, weather | active |
| `cache` | 582 | Cache content-addressed L1+L2 (mémoire + disque, clé BLAKE3) | worldgraph | active |
| `persist` | 77 | Sérialisation de chunks (bincode + zstd) | streaming | active |
| `streaming` | 883 | Chunk manager — load/unload async + LOD + génération multi-couches | agent-api, pybindings, scenario, studio | active |
| `mesh` | 565 | Voxel → triangles (Naive Surface Nets + simplification) | pybindings | active |
| `intent` | 251 | Prefetcher de chunks dirigé par l'intention (trajectoire agent) | pybindings | active |
| `macro-bridge` | 389 | Pont grille macro continentale (GenesisWorld Python ↔ chunks Rust) | pybindings, streaming | active |
| `agent-api` | 640 | Façade lecture/écriture pour agents IA (snapshots tick-safe + files de mutation) | pybindings, scenario | active |
| `pybindings` | 369 | Module Python `genesis_world` (pont PyO3) | — (export PyO3, R-J4-2) | active (entrypoint) |
| `studio` | 251 | Genesis Studio — lanceur d'expériences scientifiques (CLI, scénarios YAML) | — (binaire top-level) | active (entrypoint) |
| `scenario` | 730 | Scénarios scientifiques déclaratifs (YAML) + manifeste FAIR + runner | studio | active ⚠ *(voir note)* |
| `gpu` | 281 | Passes compute GPU (wgpu/WGSL, accélération optionnelle feature-gated) | — (optionnel) | **dormant** |
| `geology` | 1095 | Distribution minérale déterministe + tells RGB de surface (Wave 43) | **— (aucune)** | **orpheline** |

**Total : 23 crates** · 20 « active » (intégrées) · 2 entrypoints (pybindings,
studio) · 1 **dormant** (gpu) · 1 **orpheline** (geology).

---

## Notes par statut

### Orpheline — `geology` (1095 LOC) — *décision déjà prise*
Importée par **aucune** crate. C'est l'orphelin **D5** : tranché par
[ADR-0007](../../../adr/0007-d5-geology-orphan-resolution.md) comme **oracle de
contrat lecture-seule**. `runtime/tests/test_geology_cross_language_contract.py`
le parse comme texte pour figer l'enum `Mineral` (16 variantes) et les couleurs
« tell » byte-exact (malachite/charbon/kaolin/calcaire) que les capacités
Python C1, C4, C5, C6 surfacent. Son **câblage** dans `Chunk::generate()`
(ADR-0007 étape 2, « D5-wiring ») reste **différé session cargo**
([ADR-0008 §5](../../../adr/0008-python-rust-frontier.md)).

### Dormant — `gpu` (281 LOC)
Accélération GPU **feature-gated** (`gpu` off par défaut). Des fallbacks CPU
existent (l'érosion vit dans `terrain`). Saine à l'inspection, mais non utilisée
dans le build par défaut. Réactivation = item Phase A « A5 GPU erosion
auto-fallback » (différé cargo).

### ⚠ À vérifier en session cargo — `scenario`
L'**audit complet du 2026-06-09** notait *« genesis-scenario ne compile pas »*.
La présente inspection (skim source, sans `cargo`) **ne trouve pas** de cause
évidente : le code paraît complet (runner + manifeste FAIR). **Statut de build
non vérifiable ici** (cargo absent) → marqué `active ⚠`. **À trancher** dès
qu'une toolchain Rust est disponible : soit l'erreur a été corrigée depuis le
09-06, soit elle subsiste sous une forme non visible au skim. Ne pas affirmer
« scenario compile » sans CI verte.

### Entrypoints sans reverse-dep (normal)
`pybindings` (cdylib PyO3 exporté vers Python — le binding `mineral_tells`
compilé de R-J4-2 vivra ici) et `studio` (binaire CLI) n'ont légitimement aucun
dépendant interne.

---

## Limites de cet inventaire (honnêteté)
- **Pas de build.** « active » = *intégrée au graphe d'imports*, pas *compile +
  passe ses tests*. Seule la CI le prouve.
- **LOC approximatives** (somme `src/`, arrondie).
- Aucun `todo!()` / `unimplemented!()` flagrant repéré, mais une absence de stub
  visible n'est pas une preuve de correction fonctionnelle.
- Réévaluer ce fichier à chaque réactivation Rust (conditions ADR-0008 §5).
