# Sprint 2026-06-27 — D11 (moitié precip) : la pluie des chunks RÉPOND au relief vivant

> **Type :** `feat(substrate/climate)` / couplage physique (pas une nouvelle « Cap. CN »).
> **Exécute :** le `precip_mm` du **backlog #7** de [`AUDIT-DELTA-2026-06-23`](../../native/world-engine/AUDIT-DELTA-2026-06-23.md)
> (« recoupler l'atmosphère → temp_c/**precip_mm** ») — la **moitié précipitation** de **D11 / R0**,
> le backlog explicite nommé dans [`river_discharge.py`](../../runtime/engine/river_discharge.py) (« the
> windward/leeward orographic *precip* enhancement remains backlog »).
> **Veille :** [`2026-06-27_WORLD-VEILLE-REPORT.md`](2026-06-27_WORLD-VEILLE-REPORT.md).

## Veille (obligatoire, avant code) — résumé

Scheduled-task v2.0, axe **Thermodynamique, Atmosphère & Météo** (et Système A, biome dry/wet).

- **Smith & Barstad 2004 — Linear Theory of Orographic Precipitation** (J. Atmos. Sci. 61) :
  le modèle de référence (FFT, fonction de transfert) qui **généralise** la famille
  *upslope + advection* (Smith 2003). Le modèle worldgen Genesis
  (`world_genesis._orographic_precipitation`) **EST** déjà cette famille itérative :
  air humide forcé à monter au vent → condensation/pluie ; advection de l'humidité sous le
  vent → assèchement descendant (Foehn) → **rain shadow**. → **Pas de pivot** : la variante
  FFT *remplacerait* le modèle worldgen (plus lourde, casse la réutilisation SSOT et la
  garantie « monde statique bit-identique ») → **backlog** « session cargo/GPU ».
- Lapse rate environnemental **6.5 °C/1000 m** + lift au vent / Foehn sous le vent : physique
  **confirmée** (`LAPSE_K_PER_M = 0.0065` déjà en place).
- World models / Bevy / WGPU : gated (Rust gelé, ADR-0008) → backlog.
- **CVE actives : aucune critique** (numpy / PCG64 clean, 0 nouvelle dépendance).

**COMBO_RETENU :** `world_genesis._orographic_precipitation` (modèle upslope+advection, SSOT —
le code exact qui a cuit `world.precip_mm` à la génération) × `climate_biome` (proxy de
précipitation par chunk). Couche **Substrate**. **Pas d'ADR** (additif/opt-out, calque exact
des deux précédents D11, cohérent ADR-0008).

## Le problème (D11 / R0 — moitié precip)

Le couplage orographique de **température** (2026-06-24, p154) relit `elevation_m` vivant et
le convertit en anomalie de température par chunk. Son pendant **précipitation** manquait :
chaque chunk gardait la pluie de sa naissance (`chunk_precip_proxy`, figé au snapshot
d'install). Une chaîne de montagnes qui se soulève ne projetait **aucune ombre pluviométrique**
sur les biomes qu'un chunk voit — alors que ce proxy pilote la **branche dry/wet** de l'échelle
de réchauffement (désert vs forêt), et qu'en aval `river_discharge` gèle encore la précip.

## La tranche livrée

`climate_biome` recompose le champ orographique macro pour le relief **vivant** (réutilisation
*verbatim* du modèle worldgen — SSOT) et nourrit chaque chunk avec la pluie **effective** :

```
P_eff(chunk) = P_baseline(chunk) + ( field(elev_vivant) − field(elev_baseline) )(chunk)   ⩾ 0
field = world_genesis._orographic_precipitation(params, elev, belt_latitudinal, wind_u, wind_v, sea)
```

- **Au vent** (montée le long du vent) → le flanc essore plus de pluie (gain).
- **Sous le vent** → **rain shadow** (l'air descendant s'assèche).
- Le terme est **identiquement 0** sur un monde statique (même relief → champ bit-identique
  → `world.precip_mm` reproduit à l'octet près), **réversible** (toujours re-dérivé de la
  baseline gelée, jamais cumulatif) et **pur** (0 RNG, 0 écriture macro).

`P_eff` remplace la précip figée dans la branche `_shift_biomes_array(..., warming, precip)` :
un relief qui monte refroidit (lapse, déjà câblé) **et** verdit son flanc au vent / désertifie
son flanc sous le vent. L'agent le **vit** ; le monde ne ment jamais.

## Garde-fous (invariants)

- **No-op strict** sur élévation statique (0 régression, back-compat exact — `np.array_equal`).
- **Read-only macro** : `world.precip_mm` jamais écrit (D10 gelé).
- **`PY_TO_RUST` inchangé = 15** (D8 — substrat physique, pas une capacité agent ; aucun tell).
- **0 nouveau RNG**, **0 nouvelle constante réglable** (gain/decay lus depuis `GenesisParams`).
- **Déterministe** : même seed + même relief → `current_precip_proxy` + biomes identiques.
- **Live & gratuit** : terme dans `install_climate_biome` (défaut on), déjà installé par
  `genesis_bootstrap` → actif sur le chemin `terre` sans changement de bootstrap (calque
  exact du couplage de température). Opt-out : `orographic_precip_coupling=False`.

## Vérification

- **pytest 876 passed** (867 → 876, +9 : `test_climate_biome_orographic_precip.py`).
- **ruff clean** sur les fichiers touchés.
- **p159** orographic precip smoke **9/9** ; non-régression p154 8/8, p156 9/9.
- **Portail smoke CI** p158 → **p159** (`Makefile` + `ci.yml`).

## Reste (backlog cohérent)

- **river_discharge** consomme encore `base_precip_mm` figé : le brancher sur le champ de
  précip vivant (`_orographic_precip_field`) ferait répondre aussi les rivières à la pluie
  orographique (pas seulement au canal température/ET). Prochain pendant naturel.
- Variante **FFT Smith-Barstad** (fonction de transfert) : backlog « session cargo/GPU ».
- Advection d'humidité **cross-chunk** (B-series) : backlog.
