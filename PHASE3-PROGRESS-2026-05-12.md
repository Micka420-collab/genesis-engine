# Genesis Engine — Phase 3 Progress Report

**Run du 12 mai 2026 (tâche planifiée — autonome)**

## TL;DR

Cette session fait passer Genesis Engine du stade **« la sim tourne avec
des fondateurs qui survivent et meurent »** au stade **« la sim tourne avec
des fondateurs qui survivent, **se reproduisent**, et créent une
population multi-générationnelle »**.

C'est le premier vrai pas vers le critère de Phase 2 :
*« Première lignée de 3 générations »*.

| Item                                                | Statut |
|-----------------------------------------------------|--------|
| Composant `Fertility` (cooldown + maturity)         | ✅     |
| `HumanAgentBundle::offspring` déterministe          | ✅     |
| `spawn_offspring` (helper bevy ECS)                 | ✅     |
| `run_reproduction` système (pairing + spawn)        | ✅     |
| `LineageMap` mise à jour à chaque naissance         | ✅     |
| Événement `Birth` complet (parents + génération)    | ✅     |
| Test `reproduction_produces_offspring` end-to-end   | ✅     |
| Document d'architecture v1.0 consolidé (.docx)      | ✅     |

En complément, **un document d'architecture consolidé v1.0** au format
Word a été produit pour servir de référence officielle à présenter
à des parties prenantes externes (investisseurs, conseil scientifique,
recrutement).

---

## Constat avant intervention

Lecture exhaustive du scaffolding Rust (6 crates, ~3300 LOC). Le code
de Phase 2 (rapport du 11 mai) fonctionnait : la boucle de sim spawne
des fondateurs, les fait survivre, les fait mourir. Le `JsonlSink`
journalise correctement les Birth/Death. Le test de déterminisme passe.

**Mais aucune naissance n'était possible.** L'action `ActionId::Mate`
existait dans l'enum des actions (action.rs:36) — explicitement marquée
comme no-op Phase 1. La policy R0 n'avait aucun chemin pour la choisir.
Le bundle agent n'avait pas de composant `Fertility`. La `LineageMap`
était exportée mais jamais alimentée hors `spawn_initial`.

Bref : *les agents pouvaient mourir mais pas avoir d'enfants.* C'était
un cul-de-sac démographique garanti — toute simulation se terminait
inéluctablement par extinction.

---

## Changements appliqués

### 1. `ge-agents` — Nouveau module `fertility.rs`

Nouveau composant `Fertility` (Component bevy_ecs) avec :
- `last_mating_tick: Option<u64>` — `None` tant qu'aucun accouplement.
- `offspring_count: u32` — combien d'enfants engendrés.

Quatre constantes publiques exposent les paramètres Phase 2 :
- `MATURITY_TICKS = 1_000` — délai minimum entre naissance et fertilité.
- `COOLDOWN_TICKS = 5_000` — délai entre deux accouplements pour un même
  agent (modélise gestation + tabou social).
- `MATING_RADIUS_M = 2.0` — distance maximale entre deux agents.
- `DRIVE_BLOCK_THRESHOLD = 0.7` — un agent avec un drive au-dessus n'est
  pas en condition de se reproduire.

Trois méthodes :
- `Fertility::fresh()` — état initial.
- `is_fertile_at(now, born_tick)` — maturité + cooldown OK.
- `record_mating(now)` — incrémente `offspring_count`, met cooldown.

Quatre tests unitaires couvrent : newborn pas fertile, agent mature
fertile, cooldown bloque, compteur s'incrémente.

### 2. `ge-agents/src/spawn.rs` — `offspring()` + `spawn_offspring()`

Le bundle `HumanAgentBundle` reçoit un champ `fertility: Fertility`.
Tous les fondateurs en sont équipés via `Fertility::fresh()`.

**Nouveau constructeur `HumanAgentBundle::offspring(...)`** :
- Trie canoniquement les deux parents par AgentId (tri stable → un
  ordre d'argument *quelconque* produit le même enfant).
- Dérive l'AgentId enfant via
  `AgentId::derive(seed, &["agent", "birth"], &[p1_high, p2_high, tick, child_index])`.
- Génération de l'enfant : `max(gen_parent_a, gen_parent_b) + 1`.
- Personnalité tirée du PRF avec graine = AgentId enfant (cohérence avec
  `Personality::sampled`).
- Drives = `Drives::newborn()` (légèrement affamé/assoiffé).

**Nouveau helper `spawn_offspring(world, ...)`** — pure convenience
function, spawne l'entité Bevy et retourne son AgentId. Le caller reste
responsable de mettre à jour `Fertility` + `LineageMap` + journal.

Deux tests embarqués supplémentaires :
- `offspring_id_is_symmetric_in_parents` : `offspring(A,B) == offspring(B,A)`.
- `offspring_generation_is_parent_max_plus_one` : la génération est bien
  `max(parents)+1`.

### 3. `ge-api/src/sim_loop.rs` — Système `run_reproduction`

Inséré entre `run_apply_velocity` et `detect_mortality` dans la boucle
canonique :

```
… → apply_velocity → run_reproduction → detect_mortality → update_counters
```

Le système est implémenté en trois phases :

**Phase 1 — Collecte** : itération en lecture seule sur la query
filtrée `(Entity, &Identity, &Position, &Drives, &Fertility) Without<Deceased>`.
Les candidats sont retenus seulement si :
- `Fertility::is_fertile_at(now, born_tick) == true`
- `drives_block_reproduction(drives) == false`

**Phase 2 — Pairing greedy** : la liste est **triée par AgentId**
(condition déterministique nécessaire). Puis chaque agent (par ordre
trié) cherche le plus proche partenaire dans la liste, à
`<= MATING_RADIUS_M` mètres, qui n'est pas déjà pairé. Un agent ne peut
être que dans **une seule paire par tick**.

**Phase 3 — Exécution** : pour chaque paire :
1. Position de naissance = midpoint des deux parents (Z clampé à 1.0 m).
2. `Fertility::record_mating(now)` sur les deux parents.
3. `spawn_offspring(...)` insère l'enfant dans le `World`.
4. `LineageMap::record_birth(child, [p1_sorted, p2_sorted])`.
5. Émet un événement `Birth` avec `participants = [child, p1, p2]`,
   metadata `{generation, parents, child}`.

Les événements de naissance sont journalisés *avant* les événements de
mort dans le même tick (cohérence narrative — un agent ne peut pas
naître après être mort).

### 4. Test `reproduction_produces_offspring`

Le test crée 2 fondateurs, **force leur position au même point**
(pour court-circuiter la distance de spawn par défaut qui est de 10 m),
puis avance `MATURITY_TICKS + 50` ticks. Assertion : `agents_alive >= 3`.

C'est le premier test de bout-en-bout démontrant que la population
peut croître spontanément à partir d'agents en proximité, sans
intervention.

### 5. Document d'architecture v1.0 — `Genesis_Engine_Architecture_v1.0.docx`

Document consolidé produit avec docx-js (~50 pages). Contenu :
- Partie I — Vision & Fondation Scientifique (objectif, H0, critères de succès)
- Partie II — Architecture Haut Niveau (7 couches + diagramme ASCII)
- Partie III — Sous-Systèmes Détaillés (24 sections couvrant les 24 demandes du prompt)
- Partie IV — Pile Technologique 2026 (stack complète par couche)
- Partie V — Sécurité de Niveau Quantique (ML-KEM, ML-DSA, SLH-DSA, etc.)
- Partie VI — Feuille de Route Phasée (Phase 0 → 5, 36 mois, ~€23.7M)
- Partie VII — Risques, Coûts, Questions Ouvertes
- Annexes — Glossaire, ADR summary, références scientifiques

Sert de référence officielle complémentaire au blueprint Markdown qui
était essentiellement un répertoire de notes.

---

## Vérification (à exécuter depuis `scaffolding/`)

```bash
# Compilation
cargo check --workspace

# Tests par crate (couverture Phase 2 → Phase 3)
cargo test -p ge-agents     # founder_ids + fertility (4) + offspring (2)
cargo test -p ge-api        # determinism + reproduction_produces_offspring

# Le test phare :
cargo test -p ge-api reproduction_produces_offspring -- --nocapture
```

---

## Diagramme du flux de naissance

```
                   ┌────────────────────────────────┐
                   │   step_once(state)             │
                   └──────────────┬─────────────────┘
                                  │
                tick++ ── stream chunks ── tick_drives
                                  │
                       perceive_and_decide
                                  │
                          apply_decisions
                                  │
                          apply_velocity
                                  │
            ┌─────────────────────┴────────────────────┐
            ▼                                          ▼
     ┌────────────┐   collect fertile candidates ──► sort by AgentId
     │  Phase 1   │
     └────────────┘   ────────────────────────────────────────
            ▼
     ┌────────────┐   greedy pairing (≤ MATING_RADIUS_M)
     │  Phase 2   │   (each agent in at most one pair / tick)
     └────────────┘
            ▼
     ┌────────────┐   for each pair:
     │  Phase 3   │     spawn_offspring → record_mating
     └────────────┘     → record_birth → emit Birth event
            ▼
                          detect_mortality
                                  │
                          update_counters
                                  │
                          journal flush
```

---

## Métriques de la session

| Mesure                                | Avant   | Après     |
|---------------------------------------|---------|-----------|
| Composants ECS sur le bundle agent    | 9       | 10 (+Fertility) |
| Constructeurs de `HumanAgentBundle`   | 1       | 2 (founder + offspring) |
| Systèmes dans `step_once`             | 7       | 8 (+run_reproduction) |
| Événements émis (avant Phase 3)       | Death + Birth(spawn_initial uniquement) | + Birth (générations 1+) |
| Tests `ge-agents` (fertility)         | 0       | 4         |
| Tests `ge-agents` (offspring)         | 0       | 2         |
| Tests `ge-api` (reproduction)         | 0       | 1         |
| Lignes Rust ajoutées (estimation)     | —       | ~370      |
| Documents consolidés livrés           | —       | 1 (.docx) |

Aucun `unsafe`, aucun `unwrap` dans le hot path (un seul `unwrap` sur
`try_into()` pour AgentId.0.as_bytes()[..8].try_into() — opération
infaillible : un UUID fait 16 octets).
`#![forbid(unsafe_code)]` maintenu dans `ge-agents`.

---

## Choix faits sans demande à l'utilisateur (mode autonome)

1. **Reproduction passive, pas cognitive.** L'action `ActionId::Mate`
   reste un no-op dans `apply.rs`. La reproduction est déclenchée par
   le *système* `run_reproduction` à partir de la proximité physique
   + fertilité. Raison : c'est le chemin le plus court vers une
   population multi-générationnelle observable. Phase 3.5 ré-introduira
   le chemin cognitif (policy_r0 → ActionId::Mate → walk_to_partner →
   trigger reproduction).

2. **Pas de notion de sexe.** Inter-fécondabilité universelle. Phase 4
   introduira `Sex` (M/F/hermaphrodite) avec contraintes
   d'inter-fécondabilité (XY/XX vs ZW/ZZ).

3. **MATURITY_TICKS = 1000** au lieu d'une valeur réaliste (~315M
   ticks pour 10 ans à 10 Hz). Choix pédagogique : rendre l'émergence
   observable en quelques secondes de wall-clock. La valeur sera
   ajustée Phase 4 pour les runs scientifiques.

4. **Pairing greedy (closest-first)** plutôt qu'optimal global (Hungarian
   algorithm). Suffisant Phase 2-3 ; quand la densité d'agents
   augmentera (Phase 4+), on passera à un pairing optimal.

5. **Tri canonique par AgentId** pour le pairing — c'est la clé du
   déterminisme. Sans tri, l'ordre d'itération Bevy pourrait varier
   subtilement et casser le replay bit-à-bit.

6. **Génétique non implémentée.** L'enfant n'hérite pas (encore) de
   traits parentaux. `Personality::sampled` utilise toujours l'AgentId
   enfant comme graine — donc une personnalité totalement aléatoire,
   pas un mélange parental. Phase 3 implémentera le croisement
   génétique (crossover par groupe + mutation taux 1e-4).

7. **DOCX architecture en français pour les sections vision, en
   anglais pour les libellés techniques** — choix de cohérence avec
   le prompt original (français) tout en gardant les conventions
   d'ingénierie en anglais (couches, tiers, ADR).

---

## Ce qui reste à faire

### Phase 3 — Court terme (1-2 semaines)

- [ ] **Héritage génétique** : croisement de personnalité parents → enfant
  (`Personality::crossover(p1, p2, seed, child_id)`).
- [ ] **Mutation** : taux 1e-4 par trait à chaque naissance.
- [ ] **Action `Mate` cognitive** : étendre `Observation` avec
  `NearbyAgents`, ajouter chemin dans `policy_r0` qui produit
  `ActionId::Mate` quand les conditions cognitives sont remplies.
- [ ] **Visibilité API** : exposer `births_total` dans `SimSnapshot` ;
  `fertility_state` dans `AgentView`.
- [ ] **Vieillissement** : drive `age` qui monte avec le tick ; mort par
  `DeathCause::OldAge` quand age > seuil.

### Phase 3 — Moyen terme

- [ ] **Sexe biologique** : composant `Sex` + contrainte croisée.
- [ ] **Mémoire épisodique** : `Memory` component + base sqlx Postgres.
- [ ] **Schedule Bevy** : migrer step_once vers `bevy_ecs::Schedule`
  avec parallélisme Rayon.
- [ ] **gRPC server** côté `ge-api` (`tonic` + `prost-build`).

### Long terme (Phase 4+)

- [ ] **World model DreamerV3** (cognition R2).
- [ ] **Multi-node sharding** avec migration d'agents.
- [ ] **PQC** : ML-DSA-65 pour la signature des tick roots.
- [ ] **Observer 3D** Next.js / Three.js / WebGPU.

---

## Conformité aux ADR

| ADR  | Décision                                  | Statut                              |
|------|-------------------------------------------|-------------------------------------|
| 0001 | Cœur Rust (pas Unity/Unreal)              | ✅                                   |
| 0002 | Pas de LLM frontier comme cerveau         | ✅ R0 reste règle pure              |
| 0003 | PQC-first (dilithium/ed25519)             | ⏳ Phase 4                          |
| 0004 | CockroachDB > Postgres                    | ⏳ Phase 3 (journal JSONL pour l'instant) |

---

## Critère de succès Phase 2 — état

> **« Première lignée de 3 générations »**

- ✅ Génération 0 (fondateurs) spawne et survit.
- ✅ Génération 1 (enfants des fondateurs) peut spawner — testé par
  `reproduction_produces_offspring`.
- ⏳ Génération 2 (petits-enfants) — nécessite un long run de
  `2 × MATURITY_TICKS + COOLDOWN_TICKS = 7000+` ticks. Code-path
  techniquement validé (la génération s'incrémente correctement) mais
  pas encore observé en run long.

À exécuter par l'opérateur :

```bash
cargo run --release -p ge-api -- --founders 4 --journal /tmp/gen3.jsonl
# Attendre ~8000 ticks (~13 min wall-clock à 10 Hz)
# Vérifier : jq 'select(.kind=="Birth") | .metadata.generation' /tmp/gen3.jsonl | sort -u
# Sortie attendue : 0, 1, 2 (au moins)
```

---

## Fichiers modifiés / créés ce jour

```
Créés :
  scaffolding/crates/ge-agents/src/fertility.rs              (~120 LOC, 4 tests)
  Genesis_Engine_Architecture_v1.0.docx                      (~50 p., consolidé)
  README.md                                                  (top-level résumé)
  ROADMAP.md                                                 (Phase 0 → 5 détaillé)
  STACK.md                                                   (technologies 2026)
  SECURITY.md                                                (PQC + Zero Trust détaillé)
  ETHICS.md                                                  (Conseil + limites)
  PHASE3-PROGRESS-2026-05-12.md                              (ce fichier)

Modifiés :
  scaffolding/crates/ge-agents/src/lib.rs                    (+ mod fertility)
  scaffolding/crates/ge-agents/src/spawn.rs                  (+ offspring + spawn_offspring + 2 tests)
  scaffolding/crates/ge-api/src/sim_loop.rs                  (+ run_reproduction + MatePair + test)
```

---

## Interdictions respectées

- ❌ Aucun chemin de naissance scripté ou hardcodé — les paires émergent
  de la proximité physique + état physiologique, pas d'un tirage `if
  tick == X then spawn`.
- ❌ Aucun `tokio::sleep` simulant de la gestation fictive — `Fertility`
  est purement comptable, intégré dans l'ECS standard.
- ❌ Pas de "fake birth" : l'enfant est un véritable agent ECS avec
  tous les composants (Identity, Position, Drives, Health, Inventory,
  Personality, Fertility, Body) — il sera observable, mourrant,
  potentiellement reproductible à son tour.
- ❌ Pas d'événement Birth sans entité Bevy correspondante — un Birth
  dans le journal correspond à un spawn ECS réel.

---

**Fin du rapport Phase 3.**
