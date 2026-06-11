# Capacité Substrate C1 — Indices de surface minéralisée (découverte visuelle émergente)

**Date :** 2026-06-11 · **Module :** `engine.surface_mineralization` · **Smoke :** `p133` · **Tests :** `tests/test_surface_mineralization.py` (15)

> **Ce n'est PAS une Wave d'observateur.** C'est une **capacité** : un signal de
> monde interrogeable que les agents consomment pour **agir** (creuser au bon
> endroit). Elle ne wrappe pas `sim.step` et n'ajoute **aucun coût au tick**
> (indices dérivés paresseusement par chunk, mémorisés). Elle respecte donc le
> **moratoire observateurs** (`CONTRIBUTING.md` §"Moratoire observateurs",
> `AUDIT-DELTA-2026-06-10 §D1`) qui ne vise que les `*_observer.py` read-only.

## Motivation

La veille du jour ([`docs/veille/2026-06-11_VEILLE_surface_mineralization.md`](../veille/2026-06-11_VEILLE_surface_mineralization.md))
part d'un constat de l'audit : la couche d'**observation** progresse (réalisme
mesuré 79 %) mais les **capacités d'action** des agents stagnent depuis 25 jours
(« observer treadmill »). Le backlog moteur est en Rust, non compilable dans cet
environnement (cf. [`reference_env_no_cargo`]). On vise donc une capacité **côté
runtime Python vérifiable**.

**Le trou comblé :** `engine.geology` sème des minerais en profondeur (chaque
`StrataLayer` porte un `ore_mix`) et `mine_at` les extrait — mais **aucun signal
de surface** ne permettait à un agent de *découvrir par la vue* un gisement
enfoui. L'action `MINE` partait d'une profondeur par défaut (3 m), à l'aveugle.
Le monde portait la ressource mais restait **muet**.

`surface_mineralization` ajoute le **chapeau de fer / la tache d'altération** que
les prospecteurs lisent depuis l'âge du bronze. Conforme à la **règle d'émergence
absolue** : l'agent ne *sait* pas qu'un minerai existe — il **VOIT** une couleur,
se souvient, revient, creuse. On n'a jamais scripté « c'est du cuivre » ; on a
rendu le **vert détectable**.

## Modèle géochimique (véridique, non scripté)

L'expression de surface d'un corps minéralisé peu profond = son **produit
d'altération** (oxydation supergène, zone vadose). Table d'expression :

| Groupe | Minéraux (ore_mix) | Produit d'altération | RGB perçu | Prof. max d'expression |
|--------|--------------------|----------------------|-----------|------------------------|
| `copper` | `native_copper`, `chalcopyrite` | malachite/azurite | **(80,140,70)** vert | 40 m |
| `gossan` | `pyrite`, `hematite`, `magnetite`, `galena`, `sphalerite` | chapeau de fer (limonite/hématite/jarosite) | **(150,75,40)** brun-rouille | 50 m |
| `sulfur` | `native_sulfur` | croûte fumerollienne | **(220,200,60)** jaune | 20 m |
| `salt` | `halite` | efflorescence | **(235,235,240)** blanc | 12 m |
| `gold_placer` | `native_gold` | paillettes alluviales | **(212,175,55)** doré | 8 m |

Couleurs alignées sur le crate Rust `genesis-geology` (`Mineral::Malachite::surface_color() = [80,140,70]`)
afin que les indices Python (sim live) et Rust (world-engine) concordent.

**Règles physiques :**
- Un minerai n'exprime que si le **haut** de sa couche est ≤ profondeur max ET sa
  fraction massique ≥ `MIN_VISIBLE_FRACTION` (0,3 %) — sinon trop faible pour
  teinter la surface.
- **Couche la plus haute domine** : le chapeau de fer de surface masque ce qu'il
  y a dessous (réalité de terrain).
- **Priorité diagnostique** : un signal rare et parlant (cuivre vert, soufre,
  sel, placer) l'emporte sur le chapeau de fer commun quand ils coexistent.
- **Masquage par biome** : océan (sous l'eau), glace, canopée dense (forêt
  tropicale) masquent l'indice ; déserts/savanes l'exposent au mieux (visibilité
  par biome, seuil `VISIBILITY_FLOOR = 0,30`).

## Invariant pivot — « le monde ne ment jamais »

L'indice est dérivé de **la même colonne `chunk_geology`** que celle que `mine_at`
exploite. Donc, par construction : **tout indice émis ⇒ il existe réellement, à
`dig_depth_m`, une couche dont l'`ore_mix` contient le minéral correspondant à la
couleur.** Creuser là **rend** ce minéral. La réciproque est volontairement
*faible* (absence d'indice ⇏ absence de minerai) : beaucoup de gisements ne
trahissent aucune couleur — l'agent doit alors explorer/creuser à l'aveugle
(préserve l'émergence : on ne donne pas la carte).

## Invariants (prouvés par 15 tests + smoke p133)

| Invariant | Vérification |
|-----------|--------------|
| **Le monde ne ment jamais** | tout `cue ⇒ chunk_geology.find_layer_at(dig_depth)` contient `cue.mineral` (synthétique + monde Genesis réel) |
| **Boucle de découverte** | `prospect` (voir vert) → `mine_at(dig_depth)` → `native_copper` extrait > 0 |
| Profondeur d'expression | corps dont le haut > prof. max ⇒ aucun indice |
| Seuil de visibilité | fraction < `MIN_VISIBLE_FRACTION` ⇒ aucun indice |
| Masquage physique | océan / glace / canopée ⇒ aucun indice ; désert ⇒ indice |
| Priorité diagnostique | cuivre vert l'emporte sur pyrite (chapeau de fer) co-localisée |
| Couche la plus haute | gossan de surface domine un cuivre juste dessous |
| Couleurs physiques | cuivre vert dominant ; gossan rouge>vert>bleu ; sel quasi-blanc |
| **Déterminisme** | même seed ⇒ indices bit-identiques (cue dérivé pur de la géologie `prf_rng`) |
| Coût tick nul | `install` idempotent, aucun hook `sim.step` (cache paresseux par chunk) |

## Surface (API capacité)

`SurfaceCue` · `ExpressionRule` · `install_surface_mineralization` ·
`surface_cue_for_chunk` · `surface_cue_rgb_grid` (color_hint pour Earth Console) ·
`prospect(sim, x, y)` (ce qu'un agent perçoit) · `discover_by_sight(sim, rows, r)`
(perception batch → cibles de fouille triées par distance) · `surface_cue_summary`.

Réutilise `engine.geology` (`chunk_geology`, `StrataLayer`, `install_geology`,
`mine_at`) et `engine.mineral_catalog` — **aucune duplication** de la source de
vérité minérale. Enregistré dans le contrat ADR-0005
(`engine.world_model_capabilities._REQUIRED_MODULES`, lint strict vert).

## Résultats

- `runtime/tests/test_surface_mineralization.py` — **15/15** verts (~2 s).
- `runtime/scripts/p133_surface_mineralization_smoke.py` — **7/7 PASS**. Monde
  Genesis réel (seed `0xFACE`, res 128, forêt tropicale sèche) : **100 chunks
  terre, 100 % d'indices émergents** (gossan hématite 53 + soufre 47),
  **0 violation** d'invariant. Boucle démontrée : *voir vert → creuser 0,50 m →
  cuivre extrait*. `journals/p133_surface_mineralization.jsonl` écrit.
- `ruff check` clean sur les 3 fichiers + `world_model_capabilities.py`.
- `pytest runtime/tests` : **vert** (baseline + 15) ; ADR-0005 lint strict vert.
- Câblé dans `make validate-all` + CI (après `p132`).

## Impact réalisme

Première **capacité** (vs. observateur) de la série depuis 25 jours : le monde
cesse d'être muet sur ses ressources. Ferme la chaîne SYSTÈME C (`color_hint`) →
SYSTÈME F (découverte visuelle) du prompt Substrate, côté runtime vérifiable, et
amène en sim live ce que le crate Rust `genesis-geology` (Wave 43) ne faisait
qu'inspecter statiquement (`p113` = grep de source). Écologie/hydrologie inchangée ;
**Géologie/relief 74 → 75 %** (nouvelle capacité de découverte minérale réelle,
pas seulement une mesure) ; global ≈ **79,1 %**.

## Gaps honnêtes / pistes

- **Granularité chunk** : la colonne géologique est *par chunk* (32 m) dans le
  modèle Python — l'indice est donc par chunk, pas par cellule. Une expression
  *sub-chunk* (filons affleurants ponctuels) demanderait une géologie par cellule
  (backlog ; côté Rust `genesis-geology` a déjà `sample_surface` par voxel).
- **Cognition de corrélation couleur→action** : `discover_by_sight` expose les
  indices ; *brancher* la décision `MINE` des agents NEAT sur ce percept (pour
  que la découverte émerge dans une vraie run multi-générations) est l'extension
  naturelle suivante — c'est la prochaine capacité, pas un observateur.
- **Mémoire culturelle** : transmettre « vert = creuser » entre agents (comme
  `building_discovery` nomme les archétypes) refermerait la boucle culturelle.
- **Couleurs secondaires** : cinabre (rouge, mercure), bauxite (rouge latéritique)
  pourraient enrichir la palette ; gardés hors scope pour une table haute-confiance.
