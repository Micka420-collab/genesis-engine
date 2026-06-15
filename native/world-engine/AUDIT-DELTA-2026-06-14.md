# Genesis World Engine — Delta-Audit 2026-06-14 (J+4)

**Mode :** scheduled task `analyse-le-projet-regarde-si-il-y-a-des-amelioration` (run automatique, user absent).
**Successeur direct de** [`AUDIT-DELTA-2026-06-13.md`](./AUDIT-DELTA-2026-06-13.md) (matin) et complément à [`BLIND-SPOTS-AUDIT-2026-06-13.md`](./BLIND-SPOTS-AUDIT-2026-06-13.md) (soir).
**Périmètre :** delta 24 h sur `native/world-engine/` (23 crates) + interface Python ↔ Rust.
**Contrainte env :** `cargo` absent. Affirmations Rust = lecture seule ; CI = vérité.

---

## 0. Verdict express

> **24 h = 2 capacités Python (C5 `clay_outcrop`, C6 `limestone_outcrop`), 0 commit Rust.**
> Le garde-fou D5/D6 **fonctionne** : C5 a fermé l'orphelin Rust `FineClay`, C6 a fermé `LimestonePure` (cf. `PY_TO_RUST` passé de 11 → 15 entrées). Le test `test_geology_cross_language_contract.py` a été enrichi sur les **deux** commits — pas de divergence ré-introduite.
>
> **Mais le pattern structurel D7 tient bon** : depuis 29 jours, **toute la livraison passe par Python**. Items Phase A `A3` (spatial index), `A4` (raycast), `A5` (GPU erosion wiring) : **stagnation J+29**. La crate `genesis-geology` reste dead-code Rust (référencée par 0 autre `Cargo.toml`), conservée par ADR-0007 comme **oracle de contrat lecture-seule**.
>
> **Question stratégique non encore tranchée** (BLIND-SPOTS R3) : la frontière Python/Rust. À ce rythme (1 capacité/jour côté Python, 0 côté Rust), `runtime/engine/` devient *de facto* la couche de simulation principale. ADR-0008 toujours à ouvrir.

---

## 1. Ce qui a changé en 24 h

### 1.1 Commits

| Commit  | Date              | Couche  | Titre                                                    |
|---------|-------------------|---------|----------------------------------------------------------|
| `966e850` | 2026-06-14 04:37  | Python  | Cap. C5 — clay outcrop (poterie/céramique, ferme `FineClay`) |
| `82805c2` | 2026-06-14 05:31  | Python  | Cap. C6 — limestone outcrop (pierre/chaux/mortier, ferme `LimestonePure`) |

Vérifications immuables (lecture-seule) :
- `git log --since="2026-06-13" -- native/world-engine/ -- ':!*AUDIT*' ':!*BLIND*'` → **vide** (hors ce document et l'audit J+3).
- `grep -c "Mineral::" crates/geology/src/mineral.rs` = **72** (16 variantes × 4-5 méthodes ≈ inchangé depuis Wave 43).
- `PY_TO_RUST` (test) : 11 → 15 entrées (+4 : `coal`, `peat`, `oil_shale`, `fine_clay`, `limestone_pure` ; mappings nouveaux dans la session J+3→J+4).
- `pytest --collect-only` : **513 tests** collectés (488 → 513, soit +25 pour C5 et +25 pour C6 — alignement avec memory `project_2026-06-14_clay_outcrop` et `project_2026-06-14_limestone_outcrop`).

### 1.2 Propriétés tenues (rappel J+3 → J+4)

| Garde-fou                       | État J+4   | Vérification immuable |
|--------------------------------- |-----------|------------------------|
| D1 observer-budget < 10 %        | ✅ tenu    | `runtime/engine/observer_budget.py` invariant — 0 nouveau wrapper |
| D5/D6 cross-language contract    | ✅ tenu    | `PY_TO_RUST` enrichi 2× sans casser le test |
| D7 cargo-less env                | ⚠ structurel | 2 commits Python en 24 h ; 0 commit Rust |
| Émergence (pas de scripting)     | ✅ tenu    | Cap. C5 et C6 dérivent toutes deux d'un canal géologique (porosité × humidité, pureté × altération) |
| Déterminisme bit-à-bit           | ✅ tenu    | tells RGB byte-exact dans le test |
| Smoke quotidien `pNNN_*_smoke.py` | ✅ tenu    | `p137_clay_outcrop_smoke.py`, `p138_limestone_outcrop_smoke.py` créés |

---

## 2. Scoreboard Phase A / B — delta J+4

### Phase A (extrait NEXT-LEVEL-AUDIT §2)

| Item                          | 2026-06-13 | 2026-06-14 | Delta |
|-------------------------------|-----------|-----------|-------|
| A1 apply_pending (vrai write) | ✅         | ✅         | — |
| A2 vraie LRU (priority queue) | ⚠ partial  | ⚠ partial  | stagnation J+29 |
| A3 spatial index (rstar)      | ❌ stub `Vec::new()` | ❌ identique | **stagnation J+29** |
| A4 raycast accéléré           | ❌ DDA naïf step=0.5 | ❌ identique | **stagnation J+29** |
| A5 GPU erosion auto-fallback  | ❌         | ❌         | **stagnation J+29** |
| A6 snapshot/restore           | ✅         | ✅         | — |
| A7 fog-of-war filter          | ⚠ partial  | ⚠ partial  | — |
| **D5-wiring** (issu ADR-0007) | ⏳ ouvert  | ⏳ ouvert  | reste déféré CI |

Score : **2 ✅ / 3 ⚠ / 3 ❌ + 1 ⏳** — inchangé sur 24 h. Rythme Phase A : **0 item mergé en 29 jours**.

### Phase B (extrait NEXT-LEVEL-AUDIT §2)

| Item B1 → B8 | 2026-06-13 | 2026-06-14 |
|--------------|-----------|-----------|
| Tous (tectonique dyn, hydro cross-chunk, advection humidité, saisons, SDF caves, boids, hot-reload biomes, debug overlay) | ❌ 0/8 | ❌ 0/8 |

---

## 3. Risques D-series — delta J+4

| ID | Risque                                          | État J+3 (matin) | État J+4         | Commentaire J+4 |
|----|-------------------------------------------------|------------------|------------------|-----------------|
| D1 | Treadmill observateurs                          | ✅ tenu          | ✅ tenu          | 0 observateur ajouté en 24 h, 2 capacités à la place — c'est l'objectif |
| D2 | `maybe_evict` O(N)                              | ❌                | ❌                | stagnation J+29 |
| D3 | Stub `entities_in_radius`                       | ❌                | ❌                | stagnation J+29 ; bloque toujours la perception multi-agent |
| D4 | Décorrélation score réalisme ↔ moteur Rust      | ⚠ stabilisé     | ⚠ **aggravé**    | géologie Python 77 → 78 sur 24 h ; aucun reflet côté Rust (cf. §4) |
| D5 | `genesis-geology` orphelin                      | ✅ décidé ADR-0007 | ✅ décidé        | crate reste oracle, câblage reporté |
| D6 | Double-source Python/Rust géologie              | ✅ fermé (divergence)  | ✅ fermé        | C5 + C6 ont **enrichi** `PY_TO_RUST` sans diverger — garde valide |
| D7 | Vélocité asymétrique permanente                 | ⚠ structurel     | ⚠ structurel     | confirme : J+4 = ratio Python/Rust = 2/0 ; en 29 jours = 6/0 sur les capacités |
| **D8** (nouveau) | `PY_TO_RUST` devient single-point-of-truth | — | ⚠ **émerge** | Voir §5 |

---

## 4. Décorrélation score réalisme ↔ moteur — quantifiée J+4

D'après la memory ([`project_2026-06-14_clay_outcrop`](../../memory/project_2026-06-14_clay_outcrop.md), [`project_2026-06-14_limestone_outcrop`](../../memory/project_2026-06-14_limestone_outcrop.md)) :

- **Score géologie Python** : 76 → 77 (C5) → 78 (C6) en 24 h, **+2 points / jour**.
- **Score réalisme global** : ~79,7 % → ~79,9 % en 24 h.
- **Couverture moteur Rust** : aucune crate Rust ne consomme `chunk_geology(...)` côté worldgen → tous les gains sont **invisibles à la production de chunks** par le moteur.

Conséquence : **+2 pts/jour de "réalisme déclaré" sans aucun voxel généré différemment** par le moteur natif. Le score mesure aujourd'hui la qualité de la **couche perception agent côté Python**, pas la qualité du monde généré côté Rust. C'est honnête tant que c'est *dit* — mais ça n'est dit nulle part dans `PROJECT-STATUS.md` ni `ROADMAP.md`.

**Recommandation R-J4-1** : dans `PROJECT-STATUS.md`, ajouter une ligne « **Score réalisme** : 79,9 % (couche perception Python ; couche worldgen Rust gelée depuis Wave 42, cf. ADR-0007) ». Sans ça, un nouveau contributeur lit "80 %" et croit le moteur Rust à 80 %.

---

## 5. D8 (nouveau) — `PY_TO_RUST` comme single-point-of-truth fragile

Observation : le test `runtime/tests/test_geology_cross_language_contract.py` est aujourd'hui le **seul** verrou qui empêche la divergence Python/Rust de géologie. Il fait :

1. Parse texte du Rust (`crates/geology/src/mineral.rs`) → liste enum, palette tell.
2. Fige `MINERAL_COUNT = 16`.
3. Liste statique `PY_TO_RUST: Dict[str, str]` (15 paires).
4. Vérifie byte-exact 4 couleurs « tell » critiques (malachite, charbon, kaolin, calcaire).

Failles à éclairer (pas urgentes, mais à nommer J+4) :

- **F-D8-1** : parsing texte du Rust — un refactor Rust qui change la *forme* (e.g. `impl Mineral` réécrit en macro `enum_dispatch`) **passerait** sans changer la sémantique mais casserait le parse. Le test échouerait sur la *forme*, pas sur le *contrat*.
- **F-D8-2** : `PY_TO_RUST` est statique et figé dans le test. Si un dev ajoute Cap. C7 sans toucher au test, **le contrat ne le voit pas** : la nouvelle palette Python peut exister sans correspondance Rust. La règle CONTRIBUTING.md §« Moratoire » est sociale, pas technique.
- **F-D8-3** : 4 couleurs vérifiées byte-exact sur 16 minéraux × 1-3 tells/minéral ≈ **< 25 % de couverture byte-exact**. Le reste du contrat est nominal (« le nom existe des 2 côtés ») mais pas valeurs.

**Recommandation R-J4-2** : à J+5 (ou J+6), promouvoir le contrat de "parse texte" vers "import du wheel `genesis_world` qui expose `Mineral::all_tells() -> Vec<(name, rgb)>`". Sans `cargo` ici, ça veut dire ajouter une fonction `#[pyfunction] fn mineral_tells() -> Vec<(String, [u8;3])>` à `crates/pybindings/` et la consommer côté test Python via `from genesis_world import mineral_tells`. Le test devient résistant aux refactors Rust.

**Recommandation R-J4-3** : ajouter à `pytest` un hook auto-discovering de toute palette `tell` Python (e.g. `mineral_catalog.py::TELL_<NAME>`) et exiger qu'elle apparaisse dans `PY_TO_RUST`. Ferme F-D8-2 par CI plutôt que par convention.

---

## 6. Axes 1-6 de la mission scheduled task — couverture J+4

Rappel : la tâche planifiée demande un audit sur 6 axes (géologie, climat, écosystème, perf, agent-API, devtools). L'audit complet est dans [`NEXT-LEVEL-AUDIT.md`](./NEXT-LEVEL-AUDIT.md) (2026-05-16, 504 lignes, **toujours valide**). Statut J+4 par axe :

| Axe | Item phare audit 05-16 | Statut J+4 | Commentaire |
|-----|------------------------|-----------|-------------|
| **1 — Géologie** | Tectonique dynamique (B1), SDF caves (B5) | ❌ 0/2 | proposals `axis1_geology/*.rs` toujours hors workspace. Cap. C1-C6 Python ne touchent **pas** la tectonique — c'est de la **perception minéralogique de surface**, pas du worldgen souterrain. |
| **2 — Climat** | Advection humidité (B3), saisons (B4) | ❌ 0/2 | `climate/src/lib.rs` toujours en 3-bandes hardcodées. Wave 44 olfaction tient compte du vent côté Python, mais le vent reste analytique pur. |
| **3 — Écosystème** | Boids (B6), Lotka-Volterra | ❌ 0/2 | `ecosystem/src/lib.rs` toujours seeds-only. |
| **4 — Perf** | Vraie LRU (A2), spatial index (A3), GPU pipeline (C1) | ⚠ 0/3 (A2 partial) | Stagnation J+29 sur A2/A3/A5. |
| **5 — Agent-API** | apply_pending (A1), snapshot (A6), fog-of-war (A7) | ✅⚠ 2/3 | A1 + A6 livrés (Wave 42-43). A3 (entities_in_radius) toujours stub → bloque la perception inter-agents. |
| **6 — Devtools** | Hot-reload biomes (B7), debug overlay (B8) | ❌ 0/2 | proposals `axis6_devtools/*` non promus. |

**Score axes mission** : **2 / 16** items (12,5 %) mergés en 29 jours sur la roadmap audit. **L'angle où ça avance**, en revanche, est *hors roadmap audit* : la **couche perception Python** (Wave 43 → 50 observateurs ; Wave 51+ capacités C1-C6). C'est très bien produit, **mais répond à une question différente** (« comment l'agent perçoit le monde existant ») de celle de l'audit (« comment le moteur produit un monde plus réaliste »).

---

## 7. Procédure recommandée J+5 → J+10

Cadrée sur ce qui est *exécutable sans `cargo`* (cf. D7) :

```
J+5 (2026-06-15) :
  - Choix exclusif :
    (a) Cap. C7 — nouvelle capacité perception (e.g. plant_outcrop, water_source_dowsing)
        ⇒ DOIT enrichir PY_TO_RUST si elle touche un minéral Rust (sinon
           CONTRIBUTING.md §Moratoire).
    (b) R-J4-2 — ouvrir ADR-0008 frontière Python/Rust (BLIND-SPOTS R3 + ce
        delta §4) avant d'ajouter C7.

  Recommandation : (b). À 6 capacités Python livrées et 0 Rust en 29 jours,
  ne pas trancher la frontière revient à *décider par défaut* que Python
  est la couche de simulation. C'est une décision lourde non documentée.

J+6 :
  - Implémentation R-J4-2 : ajouter `mineral_tells()` à pybindings ET
    consommer côté test Python — élimine F-D8-1. Ne demande pas `cargo`
    si on déclenche la rebuild du wheel via CI (workflow `maturin-pybindings`).

J+7 → J+10 :
  - Soit la frontière est tranchée (ADR-0008) → on continue C7-C10 côté Python
    en assumant.
  - Soit elle ne l'est pas → moratoire C7 jusqu'à décision.

  Item Phase A "réactivable cargo-less" : A6.5 — snapshot binaire compact rkyv
  (existe déjà bincode+zstd cf. §A6). Pas urgent.

Tout item Phase A/B nécessitant cargo (A3 rstar, A4 raycast, A5 GPU, B1-B8) :
  reste bloqué structurellement (D7). Programmer une session "cargo dispo"
  hors routine matinale.
```

---

## 8. Honnêteté (ce qui reste dû depuis J+0)

- **Audit incomplet** sur 8 crates ajoutées hors NEXT-LEVEL-AUDIT (R1 du BLIND-SPOTS). À ce jour, statut "active / dormant / orpheline" n'est consigné nulle part en 30 s pour `weather`, `physics`, `laws`, `intent`, `mesh`, `studio`, `macro-bridge`. La crate `geology` est la seule à avoir un statut clair (ADR-0007 = oracle dead-code-utile).
- **Axe 7 — Perception multimodale** (R2 du BLIND-SPOTS) toujours pas formalisé. Wave 44 olfaction + Cap. C1-C6 perception minéralogique constituent *de facto* cet axe, mais ne sont pas reconnus comme tel dans NEXT-LEVEL-AUDIT §5.
- **ADR-0008 frontière Python/Rust** (R3 du BLIND-SPOTS) : toujours non ouvert J+1 après recommandation. C'est aujourd'hui le **plus grand silence stratégique** du projet.
- **Procédure J+3 §5** disait : "J+6 → A3 start (spatial_index rstar)". Sans `cargo`, ce jalon est intenable. Soit on retire le jalon, soit on programme une session CI. Aujourd'hui J+4 → A3 reste à J+29 stagnation.

---

## 9. Métrique J+4

| Métrique                          | J+3       | J+4       | Δ      |
|-----------------------------------|-----------|-----------|--------|
| Commits Rust (`native/world-engine/`) hors audit | 0 | 0 | 0 |
| Commits Python `runtime/`         | 0         | 2         | +2     |
| Tests pytest                       | 488       | 513       | +25    |
| Capacités émergentes (cumul)      | 4 (C1-C4) | 6 (C1-C6) | +2     |
| `PY_TO_RUST` (entrées)            | 11        | 15        | +4     |
| Items Phase A mergés (cumul J+0)  | 2 / 8     | 2 / 8     | 0      |
| Items Phase B mergés (cumul J+0)  | 0 / 8     | 0 / 8     | 0      |
| ADR ouverts (Phase A déférés)     | 1 (0007) | 1 (0007) | 0 (0008 dû) |
| Score géologie Python (memory)    | 76        | 78        | +2     |
| Stagnation A3/A4/A5               | J+28      | **J+29**  | +1 j   |

---

**Fin du delta-audit J+4.** Aucun fichier `proposals/*.rs` ajouté, aucun item Phase A/B mergé, aucune dépendance ajoutée. Trois recommandations nouvelles (R-J4-1 → R-J4-3), zéro risque levé, un risque nouveau (D8) nommé.
