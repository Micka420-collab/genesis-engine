# Sprint 2026-06-25 — D11 (moitié hydro) : la rivière des chunks RÉPOND au débit vivant

> **Type :** `feat(substrate/hydrology)` / couplage physique (pas une nouvelle « Cap. CN »).
> **Exécute :** le « **Reste** » de [`2026-06-24_D11-orographic-climate-coupling.md`](2026-06-24_D11-orographic-climate-coupling.md)
> (la **moitié hydro** de **D11 / R0**) + R-J15-3 de
> [`SCHEDULED-TASK-2026-06-25-delta.md`](../../native/world-engine/SCHEDULED-TASK-2026-06-25-delta.md).
> **Veille :** combo `LTI river routing (Hascoet 2026)` × `bilan runoff Budyko` × `discharge_observer` existant.

## Veille (obligatoire, avant code) — résumé

Scheduled-task v2.0, axe **Eau & Hydrologie** (Système A : « que l'eau coule vraiment »).
Découvertes retenues :

- **Hascoet et al. 2026, *Differentiable River Routing* (JGR-ML)** — le routage **LTI**
  (linéaire, invariant dans le temps) `Q = (I − Aᵀ)⁻¹ r` reformulé en convolution
  bloc-creuse pour GPU/autodiff. **C'est exactement le papier que `discharge_observer`
  cite déjà** : le solveur CPU exact (balayage topologique de Kahn, O(N), déterministe)
  **est** la variante cargo-less correcte ; la version conv/GPU différentiable reste
  **backlog** (Rust/GPU gelés, ADR-0008). → **Pas de pivot.**
- **Budyko / Fu (Collignan 2025, *WRR* — attribution du débit des rivières d'Europe ;
  multiples études bassins 2025)** — le débit piloté par le climat = `f(P, PET/température)`.
  Le bilan SSOT déjà présent `runoff = max(P − ET, 0)`, `ET = min(P, k·max(T, 0))`
  (`discharge_observer.runoff_field_m3s`) **est** la forme parcimonieuse, monotone et
  déterministe de Budyko. L'enrichissement Fu (paramètre calibré) reste **backlog**.
- World models / Bevy / WGPU / ML-KEM : gated (Rust gelé, 0 surface réseau) → backlog.
- **CVE actives : aucune critique** (numpy / PCG64 clean).

**COMBO_RETENU :** `discharge_observer` (routage LTI mass-conservatif) × `chunk_hydrology`
(rivières peintes) → **couplage de débit vivant** qui câble le débit macro sur le chemin
chunk. Couche **Substrate**. **Pas d'ADR** (additif/opt-out, calque le précédent
orographique, cohérent ADR-0008).

## Le problème (D11 / R0 — moitié hydro)

Deux pièces existaient mais ne se rencontraient **jamais** :

- `chunk_hydrology` peint une bande de rivière au débit **codé en dur** `RIVER_WATER_LITRES
  = 800` L : la rivière peinte est **aveugle** à la quantité d'eau que son bassin porte
  réellement, et **ne change jamais** une fois peinte (« rivières peintes »).
- `discharge_observer` (Wave 53) calcule le **vrai** champ de débit `Q` — routage LTI
  mass-conservatif d'un bilan runoff climatique sur le réseau D8 — mais c'est un pur
  **observateur** : rien sur le chemin chunk ne le consomme (« observer treadmill »).

Le pendant exact du couplage orographique de température, côté eau, manquait.

## La tranche livrée

`engine.river_discharge` est le câble manquant — le **pendant hydrologique** du couplage
orographique de `climate_biome`. Là où celui-ci relit `elevation_m` vivant et le convertit
en anomalie de **température** par chunk, celui-ci relit le **même** `elevation_m` vivant et
le convertit en réponse de **débit de rivière** par chunk, via le canal **température/ET** :

```
temp_eff = temp_baseline − LAPSE_K_PER_M · (max(elev_vivant, 0) − max(elev_baseline, 0))
runoff   = max(P_baseline − min(P, k·max(temp_eff, 0)), 0)          # SSOT runoff_field_m3s
Q_vivant = route_runoff(flow_dir, runoff)                            # SSOT route_runoff (LTI, Kahn)
ratio    = clip(Q_vivant[cellule] / Q0[cellule], min_ratio, max_ratio)
chunk.water[cellules_rivière] = baseline_peinte × ratio
```

- **Uplift** (relief monte) → refroidit → **moins d'ET** → **plus de runoff** → la rivière
  **gonfle** (effet « château d'eau » des montagnes froides ; ×1,41 mesuré à +1 km).
- **Érosion / subsidence** → réchauffe → **plus d'ET** → **moins de runoff** → la rivière
  **rétrécit** (×0,43 à −1,5 km), et **se tarit** quand l'ET atteint le plafond de
  précipitation (oued émergent : ×0 mesuré à −4 km).

Seul le **canal température/ET** de la réponse orographique est modélisé : la précipitation
reste à sa baseline d'install (le renforcement orographique *du précip* windward/leeward
reste backlog), et le **réseau D8 est figé** (l'uplift ne re-route pas le bassin, il
re-pondère le runoff que chaque cellule contribue). Les deux simplifications **calquent**
le couplage orographique de température (qui lit — ne re-dérive jamais — le graphe macro).

Le pilote vivant **unique** est `elevation_m` — muté par `plate_tectonics_live` /
`novel_operators` dans la boucle `autonomous_world`, **jamais** dans un `sim.step` nu. Donc
sur toute simulation qui ne déforme pas le terrain (tous les smokes), c'est un **no-op
strict** : il sort avant de toucher un seul chunk, n'écrit rien, laisse le comportement
bit-identique. `genesis_bootstrap` l'installe via `ALL_MODULES` (optionnel, gardé sur
l'hydrologie ; **hors `_DEFAULT_MODULES`** comme `climate_biome`) → réutilisable sur le chemin
runtime, zéro régression sur les nombreux appelants à défauts.

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **Émergence absolue** | ✅ physique calculée (lapse × Budyko-runoff × routage LTI), aucun script ; l'agent vit l'effet via le niveau d'eau de la rivière |
| **« le monde ne ment jamais »** | ✅ le débit macro qui pilote l'échelle est **exactement mass-conservatif** (`Σ Q[puits] == Σ runoff`, résidu 1e-16 testé) — pas une profondeur peinte ad hoc |
| **D8 (pas de nouveau tell)** | ✅ substrat, pas une capacité agent ; `PY_TO_RUST` **inchangé** (15) |
| **D10 (mutation gelée à `geo.mine_at`)** | ✅ aucune mutation macro : on **lit** `elevation_m`, on n'écrit aucun array macro ; on n'écrit que `chunk.water` (le proxy aval) |
| **Réversibilité** | ✅ échelle depuis une baseline gelée → retour exact à la rivière peinte si l'élévation revient (jamais composé) |
| **Déterminisme** | ✅ dérivation pure + balayage de Kahn déterministe, **0 RNG nouveau** |
| **Back-compat** | ✅ no-op strict sur monde statique ; `p47`/`p49`/`p52`/`p122`/`p154`/`p155`/`p82` intacts |
| **ADR-0008 (cargo-less)** | ✅ 100 % Python, aucune dépendance (réutilise les SSOT existants) |

## Vérif

- `runtime/tests/test_river_discharge_coupling.py` — **10 tests** (statique=no-op strict,
  uplift gonfle, érosion rétrécit, fort réchauffement tarit, réversibilité bit-exacte,
  read-only macro temp/precip/flow_dir, débit pilote mass-conservatif, déterminisme,
  opt-out, reporter+uninstall, **wiring bootstrap** install-ssi-sélectionné).
- `runtime/scripts/p156_river_discharge_smoke.py` — **9/9** sur monde Genesis **tropical**
  réel (bassins ET-actifs) : uplift ×1,41, érosion ×0,43, tarissement ×0 (oued),
  réversibilité exacte, read-only, mass-conservation (résidu 1e-16), déterminisme.
- `pytest` complet **vert** ; `ruff` clean (module + test ajoutés au portail lint) ;
  portail smoke CI étendu **p155 → p156** (`Makefile` + `ci.yml`).

## Reste

- **Canal précipitation** de la réponse orographique (renforcement windward / ombre
  pluviométrique leeward du `precip_mm` par chunk) — backlog (le canal température/ET est
  livré ici).
- **Re-routage** du réseau D8 sous déformation vivante (l'uplift change le réseau en réalité ;
  ici figé) — backlog, complément naturel d'un observateur d'érosion qui abaisse `elevation_m`.
- **Transport latéral inter-chunks** (`cross_chunk_*`) : les stubs restent des fonctions
  orphelines (un, `cross_chunk_lbm_d2q9_step`, a même un `hash(str)` non-déterministe
  inter-processus à nettoyer si un jour câblé). Ce sprint a choisi le couplage de **débit**
  (le « combien d'eau ») plutôt que le **transport** latéral (le « où va l'eau ») : le débit
  est le signal physique dominant et ferme l'observer-treadmill de `discharge_observer`.
- **Promotion en défaut / chemin `terre`** : `climate_biome` ET `river_discharge` restent
  tous deux optionnels (hors `_DEFAULT_MODULES`). Les promouvoir ensemble dans le set par
  défaut du runtime serait la prochaine bouchée « vivant par défaut » de D11.
