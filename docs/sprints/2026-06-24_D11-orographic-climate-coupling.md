# Sprint 2026-06-24 — D11 bite : la météo des chunks RÉPOND au relief vivant

> **Type :** `feat(substrate/climate)` / couplage physique (pas une nouvelle « Cap. CN »).
> **Exécute :** R-J13-5/6 (P1) + item #6/#7 de `AUDIT-DELTA-2026-06-23.md` (front
> immobile « substrat figé sur le chemin agent », **D11 / R0**).
> **Veille :** `docs/veille/2026-06-24_VEILLE_orographic_climate.md` (combo lapse rate
> × élévation vivante).

## Veille (obligatoire, avant code) — résumé

6 axes. Découvertes retenues :
- **Lapse rate environnemental** (Wikipedia ; basins observés 0.45–0.8 °C/100 m, Nature
  Sci. Reports 2022) — l'opérateur élévation→température. SSOT déjà présent :
  `earth_laws.LAPSE_K_PER_M = 0.0065`, **la même valeur que `world_genesis` cuit dans la
  température macro de base** → couplage auto-cohérent. **Apport direct.**
- **Couplage tectonique↔érosion↔climat↔végétation** (WRF-Landlab, HESS 2021, *Oasis* 2025
  érosion temps-réel + végétation dynamique) — valide la direction : uplift refroidit →
  migration biome ; érosion réchauffe.
- **Climat dépendant de l'altitude** (Nature Rev. Earth & Env. 2025) — justifie un terme
  **par chunk** (spatialement variable), pas l'anomalie globale scalaire existante.
- World models (Cosmos/Genie/GraphCast) : gated GPU/Rust (ADR-0008) → backlog.
- **CVE actives : aucune critique** (numpy/PCG64 clean).

**COMBO_RETENU :** `lapse rate (SSOT)` × `elevation_m déjà muté vivant` → anomalie de
température **par chunk**, additive, lecture-seule. **0 cargo, 0 RNG, 0 dépendance.**
Couche **Substrate**. Pas d'ADR (additif/opt-out, cohérent ADR-0008).

## Le problème (D11 / R0)

L'audit J+13 : le substrat est **figé sur le chemin agent/chunk**. Le macro `elevation_m`
**est** muté en vivant — par `plate_tectonics_live.py:130` et `novel_operators.py:159` —
mais **dans la boucle `autonomous_world`, disjointe** du chemin que l'agent lit. Et la
source d'anomalie `macro` de `climate_biome` était un **placeholder littéral `return 0.0`**
(« Hook to be replaced when a dynamic-macro Wave ships »). Résultat : tectonique et érosion
n'atteignaient **jamais** les biomes qu'un chunk voit. Le monde bougeait — pas pour l'agent.

## La tranche livrée

`engine.climate_biome` ajoute, **à chaque install**, un terme **orographique par chunk** qui
**relit** (jamais n'écrit) le champ macro `elevation_m` vivant au centre du chunk et convertit
sa dérive depuis la baseline (capturée à l'install) en anomalie de température au lapse rate :

```
oro_dT = -LAPSE_K_PER_M * (max(elev_courant, 0) - max(elev_baseline, 0))
```

- **Uplift** (relief monte) → `oro_dT < 0` → refroidit → l'échelle de migration **COOLING**
  (forêt tempérée → boréale → toundra → glace).
- **Érosion / subsidence** (relief baisse) → `oro_dT > 0` → réchauffe → échelle **WARMING**.
- Le `max(·, 0)` calque exactement le `-6.5·max(elev,0)/1000` de la température macro de base
  dans `world_genesis` → **auto-cohérent**, et une excursion sous le niveau de la mer ne porte
  aucune anomalie de lapse parasite.

Le terme s'**ajoute** à la source globale existante (`linear_warming`), il est piloté par
`orographic_coupling=True` (opt-out), et il est **identiquement 0 tant que l'élévation ne
bouge pas** → les mondes statiques gardent leur comportement exact. La source `macro` n'est
plus un placeholder mort : son anomalie globale reste 0 (pas de tendance synthétique), mais le
signal réel et spatialement variable lui vient désormais du terme orographique.

`genesis_bootstrap` installe `climate_biome` avec les défauts → **le couplage est vivant sur
le chemin runtime par défaut**, pas une capacité « disponible mais sans consommateur ».

## Garde-fous tenus

| Garde-fou | Statut |
|---|---|
| **Émergence absolue** | ✅ physique calculée (lapse rate), aucun script ; l'agent vit l'effet via la migration de biome |
| **« le monde ne ment jamais »** | ✅ lecture-seule du macro ; contrat read-only préservé (test dédié) |
| **D8** (pas de nouveau tell) | ✅ substrat, pas une capacité agent ; `PY_TO_RUST` **inchangé** |
| **D10** (mutation gelée à `geo.mine_at`) | ✅ aucune mutation : on **lit** `elevation_m`, on n'écrit aucun array macro |
| **Déterminisme** | ✅ dérivation pure (bilinéaire + lapse), **0 RNG nouveau** |
| **Back-compat** | ✅ terme = 0 sur monde statique ; tous les tests/smokes existants intacts |
| **ADR-0008 (cargo-less)** | ✅ 100 % Python, aucune dépendance |

## Vérif

- `runtime/tests/test_climate_biome_orographic.py` — **14 tests** (statique=0, signe+magnitude
  exacts du lapse, clamp sous mer, échelles cooling/warming, source `macro` vivante, composition
  avec `linear_warming`, opt-out, read-only, déterminisme, reporter).
- `runtime/scripts/p154_orographic_climate_smoke.py` — **8/8** sur monde Genesis réel, à travers
  le `sim.step()` patché : uplift `-6.500 C`, érosion `+6.500 C` (exacts), migration cooling,
  déterminisme (335 872 cellules identiques), read-only.
- `pytest` complet **vert** ; `ruff` clean (module ajouté au portail lint + 4 E702 / 1 F401
  pré-existants nettoyés au passage) ; portail smoke CI étendu **p153 → p154** (`Makefile` +
  `ci.yml`).

## Reste

La **moitié hydro** de D11 reste (rivières peintes, `cross_chunk_*` stubs, météo `temp_c`/
`precip_mm` côté chunk encore une horloge). La boucle `autonomous_world` mute le relief mais
n'est toujours pas la même horloge que le tick agent : ce sprint rend le pont **prêt et vivant
par défaut** côté climat — un scénario qui fait tourner uplift/érosion ET le `climate_biome`
verra désormais ses biomes migrer. Prochaine tranche substrat possible : recoupler
`temp_c`/`precip_mm` chunk au macro (item #7), ou un observateur d'érosion qui abaisse
`elevation_m` vu par les chunks sur le chemin agent (item #6, complément naturel de ce couplage).
