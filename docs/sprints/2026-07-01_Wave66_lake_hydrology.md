# Wave 66 — Observateur de dépressions endoréiques & lacs (Priority-Flood)

**Date** : 2026-07-01
**Couche** : Substrat / hydrologie — observateur read-only (System A du prompt World-Realism v2.0)
**Module** : `runtime/engine/lake_hydrology.py`
**Tests** : `runtime/tests/test_lake_hydrology.py`
**Smoke** : `runtime/scripts/p174_lake_hydrology_smoke.py`
**Veille** : [`2026-07-01_VEILLE_lake_hydrology.md`](../veille/2026-07-01_VEILLE_lake_hydrology.md)
**Status** : ✅ smoke 8/8 · pytest module 17/17 · ruff clean · module **additif** (0 fichier testé modifié)

---

## 1. Motivation et règle d'émergence

Le substrat **route** déjà l'eau vers l'aval le long du réseau D8
(`discharge_observer` Wave 53, `river_discharge` Wave 64) et `world_genesis`
**marque** déjà les puits intérieurs (`flow_dir == 255` là où `best_drop ≤ 0`
au-dessus du niveau de la mer — des fonds de bassin sans voisin plus bas). Mais
**personne ne transformait ces puits en lacs** : le routeur de débit traite un
puits intérieur comme de l'eau qui *quitte le domaine*, alors qu'elle **s'y
accumule** physiquement. Wave 66 est le read manquant.

La veille du jour promeut la `DÉCOUVERTE_1` notée le 2026-06-30
(**Fill–Spill–Merge**, backlog P5) en livrant d'abord sa **fondation
topographique** — **Priority-Flood** (Barnes, Lehman & Mulla 2014,
arXiv [1511.04463](https://arxiv.org/abs/1511.04463)), l'algorithme **optimal**
de remplissage de dépressions : inonde le DEM **depuis les bords** via une file
de priorité. La surface remplie `filled ≥ elev` ; `filled − elev` est
exactement l'eau qu'un bassin fermé retiendrait s'il se remplissait jusqu'à son
**seuil** (point de débordement) — la *depression-storage capacity*, un produit
DEM standard.

**Règle d'émergence respectée** : aucune ontologie nouvelle. On ne *déclare*
jamais un lac — on lit l'élévation que le monde a déjà érodée et on rapporte où
l'eau se tiendrait. Aucun script ne place un lac, ne fixe un niveau, ne nomme un
bassin. **Read-only strict** : ne touche jamais aux arrays du monde ni au tick ;
aucun RNG (numpy + `heapq`) ; pas de nouvelle frontière `PY_TO_RUST` (physique du
substrat, pas une capacité d'agent).

## 2. Ce qui est mesuré (tout émergent)

1. **Surface remplie** (`filled`) et **champ de profondeur** `filled − elev`.
2. **Lacs** — composantes 8-connexes de `depth > eps` (terres seulement). Par
   lac : aire, élévation de surface (= seuil), élévation du fond, profondeur
   max/moyenne, **volume** impoundé (m³), centroïde, cellule la plus profonde.
3. **Classification endoréique** — un lac est *terminal* s'il contient un puits
   D8 intérieur (le routage propre du monde y meurt). C'est le **cross-check**
   entre deux dérivations indépendantes (seuils Priority-Flood vs pits
   `flow_dir`) et l'amorce de l'histoire du sel (un lac sans exutoire concentre
   la salinité — cf. `salt_evaporation` C15, **non câblé** ici).

## 3. Invariants (prouvés par tests + smoke)

- `filled ≥ elev` partout ; `filled == elev` sur **tout drain libre** (bord du
  domaine **et** cellules océaniques, semées comme toujours-drainantes → un
  bassin ouvert sur la mer n'est **pas** endigué).
- **La surface d'un lac est PLANE** : une composante connexe partage un seul
  niveau de seuil (l'eau trouve son niveau) — `std(filled[lac]) < 1e-9`.
- **Dépressions imbriquées → fusion** : une cuvette contenant un sous-puits plus
  profond devient **UN** lac au seuil externe (méta-dépression), pas deux plans
  d'eau empilés.
- **Cratère synthétique** : volume analytique exact (9 cellules × 10 m ×
  (1 km)² = 9·10⁷ m³).
- **Monde réel** (seed `0xC0FFEE_1234`, res 64) : **16 lacs émergents**, tous
  endoréiques (16 lacs ↔ 49 pits D8 : accord parfait des deux dérivations),
  `filled`/`flow_dir` inchangés (read-only), signature sha256 déterministe,
  ~13 ms.

## 4. Périmètre / honnêteté

- Priority-Flood donne l'**extension maximale** (remplissage jusqu'au seuil) —
  les volumes rapportés sont la *capacité de stockage* topographique, **pas**
  l'eau que le climat délivre réellement. La version **volume-fini**
  (**Fill–Spill–Merge**, Barnes/Callaghan/Wickert *ESurf* 2021) qui distribue
  l'apport routé de Wave 64 dans la hiérarchie de dépressions — et fait émerger
  les lacs *partiellement* remplis, donc l'endoréisme dynamique — est le
  **prochain jalon (Wave 67)**. Priority-Flood fournit les *contenants* ; FSM
  les *remplira*.
- Sur un DEM brut (non-routé), tous les bassins fermés sont terminaux → d'où
  `n_endorheic == n_lakes`. Sous Wave 67 (FSM), des lacs de *transit* (traversés
  par une rivière) apparaîtront et le flag deviendra discriminant.
- **Additif** : le module ne touche **aucun** fichier testé (`river_discharge` /
  `discharge_observer` restent intacts — garde-fou P5 respecté). Risque de
  régression 1/5.

## 5. Fichiers

| Fichier | Rôle |
|---|---|
| `runtime/engine/lake_hydrology.py` | Module Wave 66 (Priority-Flood + observateur) |
| `runtime/tests/test_lake_hydrology.py` | 17 tests d'invariants |
| `runtime/scripts/p174_lake_hydrology_smoke.py` | Smoke 8/8 |
| `docs/veille/2026-07-01_VEILLE_lake_hydrology.md` | Veille + décision COMBO |
| `Makefile` | `lake_hydrology.py` + test ajoutés à `make lint` |
| `ROADMAP.md` | P5 : FSM re-scopé Wave 67 (fondation Priority-Flood livrée) |

## 6. Suite

**Wave 67 — Fill–Spill–Merge** : coupler l'apport routé (`discharge_observer`
`route_runoff`) à la hiérarchie de dépressions de Wave 66 pour remplir les lacs
*à hauteur de leur apport réel* → lacs endoréiques dynamiques, playas sèches,
et concentration de salinité (pont émergent vers `salt_evaporation` C15).
