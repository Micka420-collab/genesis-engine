# Capacité Substrate C2 — Affleurements de pierre taillable (découverte d'outil émergente)

**Date :** 2026-06-12 · **Module :** `engine.lithic_outcrop` · **Smoke :** `p134` (7/7) · **Tests :** `tests/test_lithic_outcrop.py` (15) · **pytest global : 426/426**

> **Ce n'est PAS une Wave d'observateur.** C'est une **capacité** : un signal de
> monde interrogeable que les agents consomment pour **agir** (aller débiter la
> bonne pierre). Elle ne wrappe pas `sim.step` et n'ajoute **aucun coût au tick**
> (indices dérivés paresseusement par chunk, mémorisés). Elle respecte donc le
> **moratoire observateurs** (`CONTRIBUTING.md` §"Moratoire observateurs") qui
> ne vise que les `*_observer.py` read-only.

## Motivation — pendant de Cap. C1, technologie plus fondamentale encore

Hier, **Cap. C1** (`surface_mineralization`) a livré la découverte **visuelle du
minerai métallique** (gossan, malachite…) : l'enseigne de l'**âge du bronze**.
Mais la technologie **plus fondamentale** — la **pierre taillée** de l'âge de
pierre — restait muette. `engine.geology` portait pourtant déjà :

* la **lithologie** par couche (`StrataLayer.rock_type`) ;
* les **silicates taillables** dans l'`ore_mix` (`obsidian`, `quartz`).

…mais **aucun signal de surface** ne disait à un agent *où trouver une pierre qui
fait des lames tranchantes*. Le tailleur paléolithique réel **lit l'affleurement**
(éclat vitreux d'obsidienne, galet siliceux de silex, dalle de basalte). C'est
exactement ce que Cap. C2 rend perceptible — sans rien scripter.

**Règle d'émergence absolue respectée** : l'agent ne *sait* pas qu'une pierre est
bonne. Il VOIT une matière/un éclat, se souvient, revient, débite. On n'a jamais
scripté « ceci est de l'obsidienne » ; on a rendu **l'affleurement détectable**.

## Modèle pétrologique (véridique, non scripté)

La qualité d'une pierre tient à son **mode de fracture** :

| Classe (`KnapClass`) | Matières (geology) | Outils | Qualité base |
|----------------------|--------------------|--------|--------------|
| `CONCHOIDAL` (verre / cryptocristallin) | `obsidian`, `quartz`(→silex) | lames-rasoir, pointes | obsidian **1.00**, quartz **0.42** |
| `TABULAR` (schistosité) | `slate`, `shale` | grattoirs, lames plates | slate 0.40 |
| `GROUND` (percuter / polir) | `basalt`, `gneiss`, `granite`, `sandstone` | haches polies, meules, percuteurs | basalt 0.45 … sandstone 0.35 |
| `SOFT` (tendre) | `marble`, `limestone` | gravure (pas d'arête durable) | < seuil |

**Silex / chert** : la silice cryptocristalline **nuclée en rognons dans les
carbonates** (craie, calcaire). On modélise ce fait : `quartz` est **bonifié**
(`CHERT_BONUS = +0.30` → 0.72, `CONCHOIDAL`) quand un **hôte carbonaté**
(`limestone`/`marble`/`dolomite`/`calcite`) co-occurre dans la colonne.

**Seuil de signal** (`MIN_KNAP_QUALITY = 0.40`) : la pierre tendre et le grès de
régolithe sont *partout* — nul besoin de les « découvrir », ils n'émettent aucun
indice. Le signal porte donc sur la ressource **archéologiquement signifiante**
(obsidienne, silex), celle qui, dans la préhistoire réelle, structure des réseaux
d'échange (Melos, Lipari…).

## Affleurement vs enfouissement (géographie réelle des gîtes)

Le socle igné (granite/basalte) n'**affleure** (`depth_top ≤ MAX_OUTCROP_DEPTH =
6 m`) que là où la couverture est mince : en **altitude**, `engine.geology`
n'empile pas les 195 m de sédiment des basses terres ⇒ `bedrock_top ≈ 5 m`, il
affleure. En **plaine**, il est enfoui à ~200 m : pas d'indice lithologique, seuls
les silicates taillables des couches superficielles (`ore_mix`) trahissent une
source. C'est la géographie réelle de la matière première lithique.

## Invariant « le monde ne ment jamais »

Un indice n'est émis QUE si la matière existe réellement dans la même colonne
`chunk_geology` que celle que `mine_at` exploite :

* source `"lithology"` ⇒ une couche peu profonde a `rock_type == material` ;
* source `"ore"` ⇒ une couche peu profonde a `material` dans son `ore_mix` ≥ seuil.

L'indice porte `collect_depth_m` : débiter là **rend** la pierre. La réciproque
est volontairement *faible* (absence d'indice ⇏ absence de pierre) — le socle
enfoui ne s'affleure pas. Honnête physiquement ; préserve l'émergence (on ne donne
pas la carte des gîtes).

## API capacité

* `install_lithic_outcrop(sim)` — idempotent, cache paresseux, **coût tick nul**.
* `lithic_cue_for_chunk(sim, coord)` — indice mémorisé (ou `None`).
* `prospect_toolstone(sim, x, y)` — ce qu'un agent en `(x,y)` perçoit.
* `discover_toolstone_by_sight(sim, rows, radius)` — indices perçus par agent, triés.
* `best_toolstone_near(sim, row, radius)` — **le meilleur affleurement** (support
  de décision stone-age : marcher vers la pierre la plus tranchante visible).
* `lithic_cue_summary(sim)` — stats dashboard (`by_class`, `by_material`, `cue_rate`).

## Falsifiabilité

La hiérarchie `obsidian > silex > quartzite > basalte > granite` est une
**prédiction observable** : des agents cherchant une arête tranchante doivent
**converger** sur l'obsidienne/le silex (sources de lames), pas sur un bloc à
meule. Un classement plat/aléatoire de `best_toolstone_near` serait une
**réfutation** du modèle de perception (cf. `FALSIFIABILITY.md`).

## Preuves (smoke p134, seed `0xFACE`)

```
region: 100 land chunks | cue_rate=0.96 | best_knap_quality=1.0
classes:   {'CONCHOIDAL': 96}
materials: {'obsidian': 96}   ← province riche en obsidienne (cf. Melos/Lipari réels)
1 — Genesis world emits emergent outcrop cues        96/100 chunks   OK
2 — le monde ne ment jamais (cue ⇒ stone below)      violations=0    OK
3 — voir verre → débiter → obsidienne (mine_at)      {'obsidian':1.0} OK
4 — déterminisme même-seed (indices identiques)      mismatches=0    OK
5 — masquage physique (océan/glace/canopée vs désert)                OK
6 — hiérarchie de taille (obsidienne gagne ; tendre muet)            OK
7 — installation idempotente, coût tick nul                          OK
```

Hiérarchie + sélectivité prouvées sur colonnes contrôlées (check 6, tests
`test_quality_ranking_*`, `test_sharpest_stone_wins_selection`) ;
émergence + invariant sur monde réel (checks 1-2, `test_world_never_lies_*`).

## Gaps honnêtes

* **Provenance de l'obsidienne non verrouillée** : la couche `engine.geology`
  distribue l'obsidienne dans l'`ore_mix` selon l'affinité biome (désert chaud,
  toundra, forêt tropicale sèche) **sans exiger un hôte volcanique** dans la
  colonne. Conséquence : sur le seed `0xFACE` (forêt tropicale sèche, province
  obsidienne) le `cue_rate` est dominé par l'obsidienne (96 %). La capacité
  **reflète fidèlement** le monde (l'invariant tient : débiter rend de
  l'obsidienne) — mais un raffinement pétrologique consisterait à **conditionner
  l'obsidienne à une provenance volcanique** (basalte dans la colonne). À traiter
  **côté `engine.geology`** (source de la distribution), pas dans cette lecture.
* **Pas de nouvelle `ActionKind`** : comme C1, la capacité fournit la perception +
  le support de décision ; le débitage réutilise les flux existants
  (`engine.invention`, collecte/`mine_at`). Pas de wiring `cognition.decide` ici.
* **Visibilité par biome** (pas par pente) : les affleurements de versant raide
  ne sont pas modélisés indépendamment du biome.
* **Aucun item Rust Phase A/B fermé** (`cargo` absent de l'env, CI = vérité) —
  capacité du **runtime Python live**, distincte du backlog moteur Rust.

## Veille du jour

[`docs/veille/2026-06-12_VEILLE_lithic_outcrop.md`](../veille/2026-06-12_VEILLE_lithic_outcrop.md)
— synthèse 5 axes, COMBO retenu = `mineral_catalog (obsidian/quartz)` ×
`engine.geology (rock_type + ore_mix)`.
