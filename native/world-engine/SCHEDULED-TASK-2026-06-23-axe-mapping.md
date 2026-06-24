# Tâche planifiée 2026-06-23 — Mapping prompt « next level » ↔ réalité moteur

> **Type :** rapport (pas de modif code, user absent, prompt scheduled-task).
> **Contexte :** la tâche planifiée « analyse le projet, regarde si il y a des
> améliorations » porte un prompt d'audit générique (Rust actif, heightmap +
> FastNoise2 + biomes basiques, 6 axes, livrable « Code Rust »). Cette description
> **ne correspond plus** à l'état du moteur — qui a été tranché par
> [`ADR-0008`](../../adr/0008-python-rust-frontier.md) et a livré 20 capacités
> émergentes côté Python depuis J+0. Ce rapport produit le seul livrable utile :
> un mapping audit-générique → audit-réel + verdict sur les recommandations
> encore actionnables.
>
> **Méthode :** lecture seule. Sources : [`NEXT-LEVEL-AUDIT.md`](NEXT-LEVEL-AUDIT.md)
> (515 LOC, J0=2026-05-16, annoté J+9), [`AUDIT-DELTA-2026-06-23.md`](AUDIT-DELTA-2026-06-23.md)
> (206 LOC, J+13, audit multi-agent re-vérifié dépôt), `MEMORY.md` (35 entrées
> capacités C1→C20 + DRINK fix R-J13-4).

---

## 0. TL;DR

1. **La tâche planifiée tire un prompt obsolète.** Le moteur ciblé par le prompt
   (« heightmap statique + biomes basiques + faune scriptée ») n'existe plus
   tel quel : depuis ADR-0008, le runtime de simulation est **Python actif**,
   le workspace Rust est **gelé Wave 42** (oracle de contrat lecture-seule).
   La livraison demandée — « Code Rust pour chaque axe amélioré » — est
   **incompatible** avec l'environnement (cargo/rustc absents, [`reference_env_no_cargo.md`]).
2. **Les 6 axes du prompt ≡ les 6 sections du `NEXT-LEVEL-AUDIT.md`** déjà rédigé
   en J0 (15 mai 2026), avec 14 stubs Rust dans `proposals/axis{N}_*` — donc
   **aucun nouveau trou architectural** n'est identifié par la re-lecture du
   prompt. Tous les bottlenecks B1–B12 et les phases A/B/C restent valides
   (et restent en stase explicite par ADR-0008).
3. **Le vrai « next level » 2026-06-23** est **différent** de celui imaginé en
   J0. Il a été identifié par l'audit J+13 d'hier (2 P0 nouveaux) :
   - **D12 / R0 (nouveau)** : l'arc C1→C20 n'a aucun consommateur agent — 20
     capacités testées mais jamais invoquées dans une boucle de simulation.
     1ʳᵉ bouchée prise hier soir (DRINK potability fix R-J13-4, commit `2d0ebd0`).
   - **D11 / R0** : substrat figé sur le chemin agent/chunk (météo macro→0.0,
     rivières peintes, cross-chunk stubs) — mutation tectonique existe mais dans
     une boucle disjointe.
4. **Recommandation : routine d'audit à gater.** R-J12-1 (P0, 2026-06-22) signalait
   déjà la cadence ~30k tokens × N runs à vide de cette routine planifiée.
   Aujourd'hui la routine tombe **après activité réelle** (C20 + DRINK fix
   2026-06-23), donc le run n'est pas à vide — mais il **duplique** un audit
   complet livré la veille. → Voir §4 reco R-ST-1.

---

## 1. Mapping prompt 6-axes → état réel (vérifié)

| Axe prompt (générique) | NEXT-LEVEL-AUDIT.md (J0) | État 2026-06-23 (J+13) | Verdict |
|---|---|---|---|
| **Axe 1 — Réalisme géologique** (tectonique plaques, érosion thermique+hydraulique runtime, SDF caves) | F1 + B1/B2/B3 ; stubs `proposals/axis1_geology/dynamic_tectonics.rs`, `sdf_caves.rs` | Côté Python : `plate_tectonics_live.py` mute `elevation_m` (boucle `autonomous_world` disjointe) ; observateurs Waves 50/62/63 (cryoclastie/hypsométrie/concavité) lisent sans muter. Côté Rust : gelé Wave 42, Voronoi statique inchangé | **Stase ADR-0008** — branche Rust intacte ; côté Python on a des observateurs mais le pont chemin-agent est cassé (D11/R0) |
| **Axe 2 — Climat & météo dynamique** (atmosphère, précip relief, saisons) | F3 + B4 ; stubs `proposals/axis2_climate/advected_humidity.rs`, `seasons.rs` | Climat chunk → branche `macro` retourne 0.0 + TODO (vérifié J+13). Pluies = analytique pure de (lat, alt). Saisons : absentes | **Inchangé depuis J0** — P1 du backlog J+13 (#7) |
| **Axe 3 — Écosystème vivant** (faune émergente, végétation, chaîne alim) | F4 + B5 + B11 ; stubs `proposals/axis3_ecosystem/boids.rs`, `food_web.rs` | Côté Python : `ecosystem.py` toujours seeds-only. Arc C1→C20 introduit des AFFORDANCES (eau potable C3, combustible C4, sel C15, salaison C16, fer forgé C19) mais aucun bouclage prédateur/proie. C16 = 1ʳᵉ chaîne « ressource→conservation » | **Bouchée prise mais embryonnaire** — D12/R0 |
| **Axe 4 — Performance extrême** (streaming async, GPU compute, 60fps×10k entités) | B7 (LRU FIFO crue), F2 ; stubs `proposals/axis4_performance/lru.rs`, `spatial_index.rs`, `gpu_pipeline.rs` | Rust gelé, performance non profilée depuis ADR-0008. Côté Python : `pytest 803 passed` en ~30s — non bloquant. Pas de boucle 60fps active | **Stase ADR-0008** — non-prioritaire tant que D12 ouvert |
| **Axe 5 — Interface agents IA** (déterminisme, snapshot/restore, fog-of-war, mutations) | F5 + B6 + B8 + B9 + B12 ; stubs `proposals/axis5_agent_api/mutation_apply.rs`, `snapshot.rs`, `fog_of_war.rs` | Côté Python : déterminisme **excellent** (prf_rng seul, BLAKE2b, 0 thread_rng). Mutation côté Python : `geo.mine_at` (C13/C17) + `plate_tectonics_live.py`. Snapshot/restore : absent. Fog-of-war : `chunk_view` mais pas filtré natif. **API agent existe (`best_*_near`, `discover_*_by_sight`) mais aucun agent ne l'appelle** (D12/R0) | **PRIORITÉ #1 actuelle** — backlog P0 #1 J+13 |
| **Axe 6 — Outils de dev** (hot-reload biomes, debug overlay, replay) | B8 + B12 ; stubs `proposals/axis6_devtools/hot_reload.rs`, `debug_overlay.rs` | Côté Python : ~150 smokes p1→p152 sont les outils de dev en pratique (visualisation déterministe + signatures SHA-256). Pas de hot-reload, pas de replay. **CI trouée : portail smoke s'arrête à p139 (vérifié `Makefile:137`)** — 13 smokes p140→p152 non gardés | **Inchangé sur replay/hot-reload** — mais gap CI P0 J+13 #2/#3 |

---

## 2. Inadéquation du livrable demandé

> « 3. **Code Rust pour chaque axe amélioré** (modules indépendants) »

Le prompt scheduled-task suppose qu'on puisse écrire et tester du Rust dans cet
environnement. **C'est faux et documenté** :

- [`reference_env_no_cargo.md`] — env = Python 3.14 SEUL, cargo/rustc absents.
- [`ADR-0008`] — Python actif, Rust gelé Wave 42 (réactivation conditionnelle ;
  pas un état transitoire).
- [`NEXT-LEVEL-AUDIT.md` §0 annoté J+9] — la stase est *explicite* dans le doc
  même que le scheduled-task voudrait étendre.
- Le livrable « code Rust » a **déjà été produit** en J0 sous forme de 14 stubs
  dans `proposals/axis{N}_*` — hors `Cargo.toml` pour préserver la compilation
  actuelle, en attente d'une « session cargo » humaine (backlog P3 #21 J+13).

→ **Le rapport présent EST le livrable.** Aucun nouveau stub ne sera écrit.

---

## 3. Bottlenecks « next level » réels au 2026-06-23 (vs ceux du prompt)

Les bottlenecks B1–B12 du prompt sont historiquement vrais mais aujourd'hui
**dominés** par deux trous architecturaux découverts post-J0 :

### B13 / D12 — Arc capacités sans consommateur agent (R0, P0)
Vérifié J+13 : aucun module hors arc+tests+smokes n'importe une capacité C1→C20.
20 affordances émergentes (eau, sel, fer, ocre, support pariétal…) **prouvées
possibles mais jamais vécues**. Le DRINK potability fix (R-J13-4, commit
`2d0ebd0` du 2026-06-23) est la **1ʳᵉ bouchée** dans ce trou (boucle agent
respecte C3) — il en reste 19.

### B14 / D11 — Substrat figé sur le chemin agent/chunk (R0, P1)
Vérifié J+13 : la mutation tectonique côté Python existe
(`plate_tectonics_live.py:130`, `novel_operators.py:159`) mais dans une boucle
`autonomous_world` **disjointe** du chemin agent/chunk. La météo chunk-side
retourne `0.0 + TODO`. Les rivières runtime sont une bande géométrique. Les
fonctions `cross_chunk_*` sont des stubs auto-déclarés.

### Trou CI (P0, cheap)
Portail smoke s'arrête à p139 (vérifié `Makefile:137` + `.github/workflows/ci.yml`)
→ 13 smokes C9–C20 (p140→p152) dans aucun job CI. `ruff` configuré mais jamais
invoqué. `Cargo.lock` untracked et non ignoré.

---

## 4. Recommandations — R-ST-x (scheduled-task)

### R-ST-1 (P0) — Gater cette routine sur activité ou la réécrire
La tâche planifiée tire un prompt obsolète (état J0) et duplique l'audit J+13
livré la veille. Deux options :
1. **Désactiver** (R-J12-1 déjà recommandait ça pour la routine d'audit-delta).
2. **Réécrire le prompt** pour qu'il pointe sur l'état réel : « relire
   `NEXT-LEVEL-AUDIT.md` + dernier `AUDIT-DELTA-*.md`, produire un mapping
   delta-J → état dépôt, identifier ce qui a bougé depuis la veille ». Le
   présent rapport est un exemple de ce que ça donnerait.

### R-ST-2 (P0) — Aucune nouvelle action sur les 6 axes du prompt
Tous les points du prompt sont déjà soit traités (déterminisme, agent API
read-side), soit en stase ADR-0008 (Rust GPU/atmos), soit dans le backlog J+13
priorisé (D12/D11/CI). Aucune urgence à dupliquer.

### R-ST-3 (P1) — Lecture proactive
Le prochain humain en session devrait lire **d'abord** `AUDIT-DELTA-2026-06-23.md`
(yesterday), pas `NEXT-LEVEL-AUDIT.md` (J0). Les 21 items du backlog J+13 ont été
re-priorisés et **corrigés post-critique adverse**.

---

## 5. Verdict final

| Question scheduled-task | Réponse |
|---|---|
| Y a-t-il des améliorations ? | Oui, **21 items priorisés** dans `AUDIT-DELTA-2026-06-23.md` §3 |
| L'audit demandé existe-t-il ? | Oui, **complet en J0** (`NEXT-LEVEL-AUDIT.md`, 515 LOC + 14 stubs) **et** à jour J+13 |
| Faut-il écrire du Rust ? | **Non** — ADR-0008, env cargo-less, livrable existe déjà sous forme de stubs |
| Le moteur est-il bloqué sur les 6 axes du prompt ? | **Sur 4 axes oui** (1/2/4/6 = stase ADR-0008 cohérente) ; sur axe 3 + axe 5 = nouveaux R0 (D12/D11) identifiés J+13 |
| Cadence de la routine ? | À gater (R-J12-1 + R-ST-1) — sinon ~30k tokens/run à dupliquer du travail livré |

---

**Commit prévu :** aucun (rapport pur, pas de modif sur l'arc). Update `MEMORY.md`
avec une ligne courte pour traçabilité.
