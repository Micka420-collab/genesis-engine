# Phase 15 — Inter-region coherence (P3)

**Date** : 2026-05-14
**Sprint type** : Architecture — premier pas de "monde virtuel global"
**Scope** : `runtime/engine/global_world.py` + endpoint + smoke test
**Statut** : Livré, 16/16 PASS sur `p26_inter_region_smoke`, aucune
régression p20/p21/p23.

---

## Pourquoi

Avant ce sprint, chaque `WorldBuilder.build()` produisait une
`Simulation` dans une bulle :

- Atmosphère locale (`engine.ecology.Atmosphere`) par sim → un hearth
  Léman émet du CO2 que Sahara ne voit jamais.
- Horloge locale (`sim.tick`) par sim → pas de "même année" partagée.
- Aucun pont entre `AgentRegistry`s → un agent Léman ne peut pas
  rejoindre la sim Jura.

`multi_region_demo.py` lance déjà 4 régions (Lausanne / Sahara /
Amazon / Reykjavík) en parallèle, mais ce sont 4 univers
indépendants. Pour viser un vrai monde virtuel multi-régional, on a
besoin d'un état global partagé.

---

## Architecture

### `runtime/engine/global_world.py` (~ 570 LOC)

Quatre concepts, tous **side-attached** : aucun changement de
signature sur `Simulation`, `WorldBuilder` ou `AgentRegistry`.

#### `GlobalAtmosphere`

API drop-in compatible avec `engine.ecology.Atmosphere` : mêmes
attributs (`co2_kg`, `co2_ppm`, `temp_anomaly_k`, `cum_emissions_kg`,
etc.), mêmes méthodes (`begin_tick`, `emit`, `absorb`, `tick`,
`update_concentration`). `attach_to_global(sim, world)` remplace
`sim.atmosphere` par l'instance globale → `tick_atmosphere` continue
de marcher mais maintenant deux sims émettent dans le même box.

Une debounce `_mark_tick(global_tick)` évite que `begin_tick` reset
N fois par tick (une par sim attachée) : seule la première sim à
passer dans le tick global remet les compteurs à zéro.

`bounds_km2` est la **somme** des sims attachées — la concentration
locale d'1 ppm correspond donc à `bounds_km2_total × 1000 kg` de CO2.

#### `GlobalClock`

`tick`, `year`, `day_of_year`, `hour_of_day`. `advance_to(sim_tick)`
prend toujours le **max** → monotonie garantie même si les sims
ticken en cascade non synchronisée. `drive_accel` partagé (lecture
sur la dernière sim qui a tické).

#### `MigrationCoordinator`

Garde une `_RegisteredSim` (anchor lat/lon + bounds_km + nom) par
sim attachée. `find_target(lat, lon)` renvoie la sim dont
l'enveloppe géographique couvre (lat, lon).

`request_migration(from_sim, agent_row, target_lat, target_lon)` :

1. Vérifie source enregistrée + agent_row vivant + target couvert.
2. Sérialise l'agent → `MigrationBlob` : drives, traits, génome,
   lexicon, inventaire, physio, memory, culture_id.
3. Alloue une row vide dans `dst_sim.agents` (incrémente
   `n_active`), restaure le blob.
4. Marque la source `alive=False` + `death_cause=NONE` (pour
   distinguer d'une mort réelle).
5. Loggue dans `migrations` / `failed` selon succès.

Le blob réutilise le pattern de `engine.world_library` : array
fields whitelistés (`_MIGRATABLE_SCALAR_FIELDS`,
`_MIGRATABLE_PHYSIO_FIELDS`), genome + lexicon copiés tels quels,
memory + relations recréées en `EpisodicMemory()` /
`SocialRelations()` fresh pour éviter les références cross-sim.

#### `GlobalWorld`

Container : `atmosphere` + `clock` + `sims: List[_RegisteredSim]` +
`migrations`. Expose `state()` pour `/api/global_world_state`.

#### `attach_to_global(sim, world, ...)`

1. Wrap `sim.step` → après chaque step, `world.clock.advance_to(...)`.
2. Replace `sim.atmosphere` par `world.atmosphere` (idempotent : si
   déjà attaché, no-op).
3. `_n_attached` compte les sims pour debounce de `begin_tick`.
4. Register dans `MigrationCoordinator` avec anchor + bounds.

### Endpoint

`GET /api/global_world_state` dans `dashboard.py` (handler ligne 396)
retourne `gw.state()` pour la sim attachée (lecture sur
`sim._global_world`). Si la sim n'est pas attachée à un GW → payload
vide structuré (clés présentes, valeurs nulles).

### ADR-0005

`engine.global_world` ajouté à `_REQUIRED_MODULES` dans
`world_model_capabilities.py`. Tags :

- `PIPELINE_LAYER = "Genesis-L4 Feedback"` — l'atmosphère et la
  migration sont des feedbacks macroscopiques émergeant des sims
  régionales.
- `WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"` — multi-step
  rollouts qui respectent la conservation de masse CO2 + monotonie
  temporelle.

Le linter `p18_capabilities_lint` passe 7/7 required modules
taggués.

---

## Smoke test : `p26_inter_region_smoke.py`

Recipe :
- Region A : Léman (46.510 / 6.633), 1.5 km, 10 founders.
- Region B : Jura (47.0 / 7.5), 1.5 km, 10 founders.
- Wave 1-4 installés (5cd + lift + physio + photo + aging).

Test :
1. Attache les deux à un `GlobalWorld`.
2. 100 ticks.
3. Migre row vivant de A vers (47.0, 7.5).
4. 50 ticks supplémentaires.

Vérifications (16) :

- ✅ 2 sims enregistrées
- ✅ même instance d'atmosphère pour A, B, gw
- ✅ co2_ppm identique entre A et B
- ✅ clock.tick ≥ 100
- ✅ row vivant trouvé dans Léman
- ✅ migration succeeded
- ✅ source row alive=False post-migration
- ✅ destination row alive
- ✅ hunger conservé (1e-5)
- ✅ curiosity conservée (1e-5)
- ✅ genome conservé (bit-identique)
- ✅ physiologie (hygiene, bladder, melanin, body_fat) conservée
- ✅ migré reste vivant ou meurt avec cause
- ✅ migration loggée dans coordinator (count=1)
- ✅ payload `/api/global_world_state` shape correcte
- ✅ déterminisme cross-process (sub-process pour éviter les
  patches process-global de physiology)

**Hash global** identique cross-process : `f0d99ab614388cc076bbf366`.

---

## Limites assumées

1. **Migration = transfert one-shot**, pas un mouvement continu.
   L'agent disparaît et réapparaît au tick suivant. Pas de "en
   transit", pas de visibilité simultanée. Pour un vrai *passage de
   frontière temps-réel* il faudrait des chunks frontaliers
   partagés — sprint futur.
2. **GlobalAtmosphere est instantanément mélangée**. La vraie
   atmosphère terrestre met ~1 an à se mélanger
   inter-hémisphériquement. Pour Genesis (échelle Léman-Jura =
   80 km), cette approximation est acceptable.
3. **GlobalClock prend le max**. Si une sim tique 10× plus vite
   qu'une autre, l'horloge globale suit la plus rapide. C'est OK en
   single-thread séquentiel (usage actuel), mais en multi-thread
   il faudra une primitive de synchronisation explicite.
4. **Migration unidirectionnelle** sur cet appel : pas de retour
   "merge agent dont l'enveloppe couvre (lat, lon) le plus
   proche". Le coordinator choisit la PREMIÈRE sim qui couvre la
   target dans son `sims` order — déterministe mais potentiellement
   contre-intuitif si les enveloppes se chevauchent.
5. **Parents (rows)** ne sont PAS transférés — c'étaient des indices
   dans la registry source qui n'ont pas de sens dans la
   destination. Le lignage est conservé via `generation` et
   `born_tick`, mais le parent direct devient `(None, None)` dans
   la sim cible.

---

## Pitfalls évités

- **`ecology.tick_atmosphere`** : on garde 100 % d'API compatibility
  via `GlobalAtmosphere.begin_tick / emit / absorb / tick /
  update_concentration` → aucun changement dans
  `sim_5cd_integration.py`.
- **Double-reset des compteurs per-tick** : sans debounce, deux sims
  attachées appelleraient `begin_tick` deux fois par tick global et
  perdraient les émissions de la première. Resolved via
  `_mark_tick(global_tick)`.
- **Horloge non monotone** : `advance_to(max)` au lieu de
  `set(sim_tick)`.

---

## Files

| Path | LOC | Note |
|---|---|---|
| `runtime/engine/global_world.py` | ~570 | nouveau module |
| `runtime/engine/world_model_capabilities.py` | +1 | `_REQUIRED_MODULES` += `engine.global_world` |
| `runtime/engine/dashboard.py` | +12 | endpoint + import |
| `adr/0005-world-model-taxonomy.md` | +1 ligne | row dans la table de mapping |
| `runtime/scripts/p26_inter_region_smoke.py` | ~280 | nouveau smoke |

---

## Prochaine étape (R&D)

- **Boundary chunks** : chunks frontaliers partagés entre 2 sims pour
  un vrai passage temps-réel.
- **Diffusion atmosphérique** : modèle de mixing latitude-dépendant
  (vs. instant-mix actuel).
- **Migration bidirectionnelle implicite** : agent qui arrive en bord
  de bounds → declenche `request_migration` automatique.
- **`world_library` integration** : save/load d'un `GlobalWorld`
  entier (avec ses N sims + leurs save_world locaux + le manifest
  inter-region).
