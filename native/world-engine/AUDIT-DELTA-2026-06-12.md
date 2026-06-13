# Genesis World Engine — Delta-Audit 2026-06-12 (J+2)

**Mode :** suivi automatique (scheduled task `analyse-le-projet-regarde-si-il-y-a-des-amelioration`).
**Successeur direct de** [`AUDIT-DELTA-2026-06-11.md`](./AUDIT-DELTA-2026-06-11.md).
**Périmètre :** ce qui s'est passé en **24 h** sur la zone moteur Rust `native/world-engine/` (23 crates) + runtime Python live (`runtime/engine/`).
**Contrainte env :** `cargo` absent. Toute affirmation Rust est validée par **inspection lecture seule** ; CI = source de vérité.

---

## 0. Verdict express

> En 24 h : **2 commits**, **tous deux Python** (`a6e88e8` Cap. C2 lithic outcrop, `4e70f3a` Cap. C3 water potability). **Zéro diff sous `native/world-engine/`** vérifié par `git log -- native/world-engine/ --since=2026-06-11` → vide. Le runtime Python a livré 2 capacités émergentes en 1 session (record), mais le backlog moteur Rust reste **identique** à J+1.
>
> **A3 (entities_in_radius), A4 (raycast naïf), A5 (genesis-gpu wiring) : J+27 de stagnation.** `D5` (genesis-geology orphelin) : J+1 de stagnation depuis sa requalification de "risque" à "réalisé". **`D6` aggravé pour la 3ᵉ fois** : C2 et C3 ré-implémentent côté Python des signaux dérivés de la **même couche géologie** que `chunk_geology` — et la crate Rust `genesis-geology` reste **toujours** non importée par quiconque hors auto-référence.
>
> **Le pattern dominant** est désormais : *pour chaque ressource émergente nouvelle, le runtime Python crée un signal dérivé de `engine.geology.chunk_geology` (Python) et la crate `genesis-geology` (Rust, 1095 lignes, palette RGB + minéraux + roches + chimie) reste dormante*. Trois sessions, trois capacités, trois fois le même contournement. Ce n'est plus un accident — c'est une **architecture implicite**.
>
> **Recommandation principale (inchangée mais plus pressante) :** flécher J+3 sur **D5-fix** (wiring `genesis-geology` dans `streaming::generate` ou archivage formel de la crate). Maintenir le moratoire Wave 64+. **Ne pas livrer Cap. C4 avant** que D5 soit tranché.

### Score Phase A après 27 jours dev

| Item | 2026-06-11 | 2026-06-12 | Delta J+2 |
|------|------------|------------|-----------|
| A1 apply_pending | ✅ | ✅ | — |
| A2 vraie LRU | ⚠ partial (FIFO + skip pinned) | ⚠ identique | — |
| A3 spatial index | ❌ stub `Vec::new()` | ❌ **stub identique** | **stagnation J+27** |
| A4 raycast chunk-aware | ❌ DDA step=0.5 | ❌ **identique** | **stagnation J+27** |
| A5 GPU erosion wired | ❌ | ❌ (`genesis-gpu` absent de `streaming/Cargo.toml`) | **stagnation J+27** |
| A6 snapshot/restore | ✅ + pin mutées | ✅ identique | — |
| A7 fog-of-war | ⚠ partiel | ⚠ identique | — |

**A1 + A6 livrés (29 %) — score identique à J+1, score identique à 2026-06-10.** 26 jours sans bouger.

### Score Phase B (12 items)

**0 / 12 mergé.** Identique à 2026-06-10, à 2026-06-11. Les stubs `proposals/axis*/` sont J+27 en file d'attente.

---

## 1. Ce qui a changé en 24 h

### 1.1 Commits (ordre chronologique)

| Commit  | Titre                                                                              | Couche | Touche moteur Rust ? |
|---------|------------------------------------------------------------------------------------|--------|----------------------|
| `a6e88e8` | substrate/geology: lithic outcrop cues — Cap. C2                                  | Python | ❌ non |
| `4e70f3a` | substrate/hydrology: water potability cues — Cap. C3                              | Python | ❌ non |

Vérification : `git log --oneline --since="2026-06-11" -- native/world-engine/` → **vide**. Zéro diff Rust en 24 h.

### 1.2 Trois ruptures positives (côté Python)

**R1 — Cap. C2 ferme un trou archéologique majeur** (`runtime/engine/lithic_outcrop.py`).
- Hiérarchie obsidienne > silex(chert) > quartzite > basalte > granite, classe de fracture (`CONCHOIDAL`/`TABULAR`/`GROUND`/`SOFT`), socle ≤ 6 m.
- Invariant prouvé : « le monde ne ment jamais » sur seed `0xFACE`, 0 violation, 100 chunks.
- 15 tests + smoke `p134` (7/7), pytest 426/426.
- **Score sociétés 76 → 77.**

**R2 — Cap. C3 ferme un trou physiologique grave** (`runtime/engine/water_potability.py`).
- Le bug racine était une **fausseté physique** : `physiology.DRINK` hydratait depuis n'importe quelle eau, **y compris l'eau de mer**. Le monde mentait.
- Fix : signal salinité (douce < 0,5 ppt / saumâtre / mer 35 ppt / saumure) **perçu par le goût**, dérivé de **trois sources indépendantes** (biome `OCEAN`, halite peu profonde en `chunk_geology`, élévation côtière).
- Invariant prouvé : potable ⇒ ≠ OCEAN & pas de saumure & ppt ≤ seuil. Boucle « goûter douce → `drink_at` hydrate / océan → perçu salé → n'hydrate pas » vérifiée end-to-end.
- 15 tests + smoke `p135` (7/7), pytest **441/441**.
- **Score écologie/hydrologie 73 → 74.**

**R3 — Le moratoire Wave 64+ tient.**
- Ni C2 ni C3 ne sont des observateurs au sens `CONTRIBUTING.md` (pas de hook `sim.step`, coût tick nul, perception paresseuse).
- Les deux commit messages déclarent honnêtement **« closes NO Rust Phase A/B item »**. C'est la 2ᵉ et 3ᵉ instance du pattern de transparence institué hier (cf. recommandation §8.2 du delta J+1).
- Le `observer_budget.py` (livré J+1) **n'a pas eu à intervenir** : zéro nouveau wrapper `sim.step` ajouté en 24 h.

### 1.3 Métrique de vélocité ressource-par-ressource

3 capacités émergentes (C1/C2/C3) livrées en 25/26/27 jours. **C3 livrée en moins de 24 h après C2 dans la même session.** Vélocité Python = très élevée. Vélocité Rust = 0 en 24 h, 0 sur Phase A/B en 27 jours.

---

## 2. Ce qui n'a **pas** bougé (et reste critique)

### 2.1 A3 — `entities_in_radius` toujours stub (`agent-api/src/lib.rs:306-310`)

```rust
fn entities_in_radius(&self, _p: WorldCoord, _r: f32) -> Vec<EntityRef> {
    // Stub — the entity index lives in the agent runtime, not in the
    // world engine. The Python layer will populate this.
    Vec::new()
}
```

J+27. Le commentaire « the Python layer will populate this » est **non tenu** : aucun trait `EntityIndex` exposé via `pybindings`, aucun adapter Python qui injecte un index dans le `WorldClient`. Le bug est dormant et silencieux côté compile.

### 2.2 A4 — raycast naïf (`agent-api/src/lib.rs:312-335`)

```rust
let step = 0.5_f32;
let mut t = 0.0_f32;
while t < max_distance {
    let p = origin + d * t;
    let wc = WorldCoord::new(p.x.floor() as i32, p.y.floor() as i32, p.z.floor() as i32);
    if let Some(v) = self.voxel(wc) {
        if !v.is_air() { return Some(RayHit { ... }); }
    }
    t += step;
}
```

J+27. Toujours O(distance / 0.5) = 200 lookups par 100 m, chaque lookup re-lock un `RwLock` chunk.

### 2.3 A5 — `genesis-gpu` toujours absent de `streaming/Cargo.toml`

Vérifié `crates/streaming/Cargo.toml:8-17` :

```toml
[dependencies]
genesis-core, genesis-noise, genesis-terrain, genesis-climate,
genesis-biome, genesis-hydrology, genesis-ecosystem, genesis-persist,
genesis-macro-bridge
```

J+27. Le code wgpu (`crates/gpu/src/erosion.{rs,wgsl}`) reste dormant.

### 2.4 D2 — `maybe_evict` O(N) scan

Inchangé J+1. Vérifié `streaming/src/manager.rs:207-234`.

### 2.5 D5 — `genesis-geology` orphelin

Vérification fraîche J+2 :

```
grep -l "genesis-geology" native/world-engine/**/Cargo.toml
→ native/world-engine/crates/geology/Cargo.toml   (auto-référence uniquement)
```

J+1 depuis requalification de "risque" à "réalisé". **1095 lignes de code Rust** (`chemical.rs` 278, `mineral.rs` 317, `rock.rs` 149, `visual.rs` 305, `lib.rs` 46) **non appelées par quiconque**. C'est désormais le plus gros poste de dette technique latente du moteur.

### 2.6 12 stubs `proposals/axis*/` toujours en file d'attente

J+27. `axis1_geology/{dynamic_tectonics.rs, sdf_caves.rs}`, `axis2_climate/{advected_humidity.rs, seasons.rs}`, `axis3_ecosystem/{boids.rs, food_web.rs}`, `axis4_performance/{lru.rs, spatial_index.rs, gpu_pipeline.rs}`, `axis5_agent_api/{mutation_apply.rs, snapshot.rs, fog_of_war.rs}`, `axis6_devtools/{hot_reload.rs, debug_overlay.rs}`.

---

## 3. D6 aggravé pour la 3ᵉ fois — désormais un *pattern architectural*

### 3.1 Constat factuel

| Capacité | Fichier Python | Source vérité Rust côté | Bridgé via `genesis-geology` ? |
|----------|----------------|--------------------------|--------------------------------|
| C1 (`1779687`, 2026-06-11) | `surface_mineralization.py` | `chunk_geology` (Python) | ❌ non |
| C2 (`a6e88e8`, 2026-06-12) | `lithic_outcrop.py:93` | `chunk_geology` (Python) | ❌ non |
| C3 (`4e70f3a`, 2026-06-12) | `water_potability.py:106` | `chunk_geology` (Python) | ❌ non |

Vérifié par grep sur les trois fichiers : aucune référence à `rust_bridge`, `genesis_world`, ou `backend`. Tous importent `engine.geology.chunk_geology` — qui est la **réimplémentation Python** de ce que `crates/geology` fait côté Rust.

### 3.2 Interprétation

Trois sessions, trois fois le même contournement. Ce n'est plus un accident — c'est devenu **l'architecture implicite** du projet. La règle non-écrite est :

> *Quand un signal émergent doit être perçu par un agent, on le dérive en Python depuis `engine.geology.chunk_geology` (réimpl Python) — jamais via la crate Rust `genesis-geology`.*

Cette règle a un mérite : **elle marche aujourd'hui** (441 tests verts, 0 violation d'invariant). Elle a un coût : **`genesis-geology` (1095 lignes) est dead-code**, et toute modification à la palette / hiérarchie minérale Rust ne sera jamais visible côté agent.

### 3.3 Pourquoi le coût va grandir

Quatre raisons concrètes :

1. **Surface de divergence en croissance linéaire.** Chaque capacité ajoute ~400 lignes Python de logique géologie. À C10, on aura ~4000 lignes de logique géo en Python qui devraient *par définition* être cohérentes avec `crates/geology/src/*.rs`. Sans test cross-langage, rien ne le garantit.
2. **Cap. C3 a déjà ré-utilisé `halite`** depuis `engine.geology` (l'équivalent Python de `crates/geology/src/mineral.rs`). C2 a fait pareil avec `obsidian`, `quartz`, etc. Le couplage Python-géologie ↔ Rust-géologie est de fait **un protocole non documenté** — il faut qu'ils s'accordent sur les noms de minéraux, les seuils de profondeur, les présences en strate, etc.
3. **La capacité C1 importait déjà** `chunk_geology` mais c'était excusable comme "première itération" (réécrite en Python parce que personne n'avait câblé Rust). Aujourd'hui c'est la troisième fois consécutive. Le geste devient l'architecture.
4. **PROJECT-STATUS.md** ligne 54 reconnaît déjà honnêtement : *« ce score mesure le réalisme **observé** ; le sous-score "capacité moteur Rust" (A3/A4/A5/B1–B8) reste à 0/7 »*. La transparence est bonne. Mais la divergence empire à chaque commit.

### 3.4 Décision recommandée — à trancher cette semaine

Le delta J+1 (§3.3) proposait deux options. Je précise maintenant :

**Option (a) — Promouvoir `genesis-geology`** [recommandé].
- Ajouter dep dans `crates/streaming/Cargo.toml`.
- Appeler `geology::sample_at(wx, wy, wz)` dans `Chunk::generate()`.
- Hashed dans le content-key du `worldgraph` Pass.
- Exposer la palette via `pybindings` → un test Python invariant `test_geology_palette_matches_rust()`.
- **Coût estimé : 2 j dev** (J+1 audit estimait 1,5 j ; je revise à 2 j parce qu'il faut aussi exposer 2 enums via pybindings pour C2 et C3).

**Option (b) — Archiver formellement.**
- Créer `crates/geology/DEPRECATED.md` documentant : *« couvert par le runtime Python `surface_mineralization` / `lithic_outcrop` / `water_potability` »*.
- Retirer la crate de `Cargo.toml` workspace `[workspace.members]`.
- Garder le code dans `git history` pour ré-import futur si besoin.
- **Coût : 1 h.**
- **Risque** : si jamais un futur axe veut servir la palette depuis le GPU (pour un debug overlay coloré, par exemple), il faudra ré-écrire — perte de 1095 lignes de travail.

**Critère de choix simple :** si l'équipe pense livrer ≥ 3 capacités supplémentaires (C4, C5, C6) avant que le moteur Rust soit ré-attaqué sérieusement, **option (b)**. Si la prochaine Wave moteur (post-A3/A4/A5) est attendue dans le mois, **option (a)**.

**Mon avis** (basé sur la vélocité observée) : **option (a)**. La vélocité Python prouve que l'équipe livre vite — donc le mois prochain verra probablement C4–C7. Mais elle prouve aussi que la dette s'accumule vite. Refermer maintenant coûte 2 j, refermer à C10 coûtera 1 semaine.

---

## 4. Roadmap mise à jour (recommandation 2026-06-12)

### Priorité 0 — Avant Cap. C4 (= geler les capacités Python tant que D5 n'est pas tranché)

| Item       | Effort  | Source                                                              | Pourquoi maintenant                                                                       |
|------------|---------|---------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| **D5-fix** | 2 j     | (nouveau) wiring `genesis-geology` dans `streaming::generate()` + test `geology_pass_deterministic` + expose palette pybindings | Stopper la divergence avant C4. **Bloque Cap. C4 par contrat.**                            |
| **A3**     | 2 j     | `proposals/axis4_performance/spatial_index.rs` (en queue J+27)      | Débloque perception multi-agent. **27 jours d'attente.**                                   |
| **A4**     | 2 j     | (à coder)                                                            | Vision agent ÷10 en latence. **Bloque toute amélioration `observe_area`.**                 |
| **A5**     | 1 j     | `proposals/axis4_performance/gpu_pipeline.rs`                       | Throughput chunk ×5. Quick win pur.                                                        |

Recommandation forte : **geler Cap. C4 jusqu'à D5-fix**. La 4ᵉ capacité qui ré-implémente une couche Rust dormante serait le signal que le projet a renoncé au moteur natif.

### Priorité 1 — Phase B (post-Priorité 0, 5–10 j)

**Inchangé vs J+1 :** B6 (boids + Lotka-Volterra), source `proposals/axis3_ecosystem/{boids,food_web}.rs`. Débloque la dimension écologie 74 → 78.

### Priorité 2 — Tri des proposals

J+27 en file d'attente. **Décision à prendre cette semaine.** Promouvoir A3 + B6. Archiver les 10 autres dans `proposals/ARCHIVED-2026-06.md` si non attaqués d'ici fin juin.

---

## 5. Risques **D-series** : delta 2026-06-12

| ID  | Risque                                                              | État 2026-06-11 | État 2026-06-12 |
|-----|---------------------------------------------------------------------|------------------|------------------|
| D1  | Treadmill observateurs                                              | ✅ clôturé       | ✅ tenu — 2 capacités, 0 nouvel observateur |
| D2  | `maybe_evict` O(N) scan                                              | ❌ identique     | ❌ identique     |
| D3  | Coupling implicite agent-runtime ↔ moteur via stub `entities_in_radius` | ❌ identique  | ❌ identique J+27 |
| D4  | Décorrélation score réalisme ↔ capacités moteur Rust                 | ⚠ aggravé      | ⚠ **aggravé encore** (+2 capacités Python, 0 capacité Rust) |
| D5  | `genesis-geology` orphelin                                           | ❌ réalisé       | ❌ identique J+1 — **aucune décision (a) ou (b) prise** |
| D6  | Double-source-of-truth Python/Rust pour la géologie                  | nouveau          | ⚠ **aggravé** — 3 instances confirmées, pattern architectural établi |

**Nouveau risque D7 — vélocité asymétrique permanente.**
- Vélocité Python : 3 capacités en 3 sessions consécutives (≈ 1 capacité / session quand l'équipe code).
- Vélocité Rust Phase A/B : 0 item en 27 jours.
- Ce déséquilibre **n'est pas conjoncturel** (contrainte env. `cargo` absent), il est **structurel** (la CI valide les diffs Rust, mais ne les *écrit* pas — il faut un dev humain). Sans **agenda dédié Rust** (1 jour / semaine bloqué pour Phase A), Phase A restera 2/7 indéfiniment.
- **Fix proposé** : durcir `CONTRIBUTING.md` avec une règle « pas plus de 3 capacités Python consécutives sans 1 item Rust Phase A mergé ». Auto-applicable côté CI (parse `git log` sur fenêtre glissante).

---

## 6. Procédure suggérée pour J+2 → J+8

```
J+2 (2026-06-12) : audit (= ce document)
J+3              : DÉCISION D5 (a) ou (b). Si (a) : start D5-fix
J+4              : D5-fix fin + test geology_pass_deterministic + expose palette pybindings
J+5              : test cross-langage palette (D6 fermé)
J+6              : A3 start (spatial_index rstar) — promote `proposals/axis4_performance/spatial_index.rs`
J+7              : A3 fin + bench `entities_in_radius_with_1000_entities` < 100 µs
J+8              : bilan D5/D6/A3 — si 3/3 ✅, autoriser Cap. C4
```

**Cap. C4 reste interdite jusqu'à D5 tranché.** C'est la seule barrière qui empêche le pattern « réimplémente en Python, oublie le Rust » de devenir permanent.

**Note env** : aucune compilation Rust possible localement. Tout déroulé suppose un push par feature + cycle CI complet.

---

## 7. Métriques à ajouter au harness de bench

Inchangé vs J+1 §7, plus :

| Bench / metric                                  | Cible          | Crate                |
|-------------------------------------------------|----------------|----------------------|
| `geology_pass_is_content_addressable`           | bit-stable     | worldgraph + geology |
| `geology_palette_matches_python_runtime`        | strict eq RGB  | pybindings + Python tests |
| `lithic_hierarchy_matches_python_runtime`       | strict eq enum | pybindings + Python tests (D6 anti-régression C2) |
| `salinity_bands_match_python_runtime`           | strict eq seuil ppt | pybindings + Python tests (D6 anti-régression C3) |
| `python_capability_velocity_vs_rust_velocity`   | < 3 capacités sans 1 Rust Phase A | CI sur `git log` (D7) |

---

## 8. Recommandations stratégiques

1. **Le moratoire Wave 64+ tient. Ne pas le rouvrir.** 2 capacités Python livrées sans aucun nouvel observateur ajouté → la garde D1 marche. Maintenir.

2. **Trancher D5 cette semaine.** Soit on bridge `genesis-geology` (option a, 2 j), soit on l'archive (option b, 1 h). Le statu quo aggrave D6 à chaque commit. **Indécision = pire option.**

3. **Geler Cap. C4 tant que D5 n'est pas tranché.** Sans cette barrière, le pattern devient permanent. Cette barrière est temporaire — quelques jours seulement.

4. **D7 (vélocité asymétrique) est le vrai risque long-terme.** Le projet a une réalité simple : 1 jour de code Python = 1 capacité émergente livrée + score réalisme +1 pt. 1 jour de code Rust = 0 capacité, 0 score, mais comble une dette technique. Sans agenda dédié, l'incitatif court-terme l'emporte toujours. **Proposer un sprint Rust hebdomadaire (1 j / 7).**

5. **Honnêteté audit institutionnalisée.** Les commits C2 et C3 portent tous deux la mention *« closes NO Rust Phase A/B item »*. C'est exactement le pattern de transparence recommandé hier (J+1 §8.2). À conserver comme pratique standard.

6. **Trier les `proposals/`.** J+27, 12 stubs en file d'attente. Décision attendue depuis le 2026-06-10. **Promouvoir A3 + B6 cette semaine ; archiver les autres dans `proposals/ARCHIVED-2026-06.md`.**

---

## 9. Annexe — Inventaire 23 crates (inchangé vs J+1)

```
agent-api      biome        cache        climate      core
ecosystem      geology★     gpu          hydrology    intent
laws           macro-bridge mesh         noise        persist
physics        pybindings   scenario     streaming    studio
terrain        weather      worldgraph
```

★ = **orphelin confirmé J+1, identique J+2**. 1095 lignes, 0 appelant.

---

## 10. Annexe — Diffs depuis 2026-06-11

### 10.1 Diffs Rust moteur (`native/world-engine/`)

```
git log --oneline --since="2026-06-11" -- native/world-engine/
→ (vide)
```

Aucun diff Rust en 24 h. Tous les pointeurs §2.1–2.6 du delta J+1 sont **identiques au caractère près**.

### 10.2 Diffs Python (`runtime/engine/`)

```
a6e88e8  lithic_outcrop.py (NEW)           + 15 tests + smoke p134
4e70f3a  water_potability.py (NEW)          + 15 tests + smoke p135
4e70f3a  world_model_capabilities.py (+1 line — register C3)
```

Total : +800 lignes Python + ~660 lignes tests + 2 docs sprint + 1 docs veille.

---

## 11. Annexe — Score réalisme : décomposition transparente

```
Climat / biomes         80     ←inchangé
Géologie / relief       75     ←inchangé (Cap. C1 du 2026-06-11)
Écologie / hydrologie   74     ←+1 via Cap. C3 (2026-06-12)
Sociétés / agents       77     ←+1 via Cap. C2 (2026-06-12)
Rendu visuel            82     ←inchangé
Observation IA          86     ←inchangé
Pont Python ↔ Rust      82     ←inchangé (artificiel, cf. §8.3 J+1)

Global = (80+75+74+77+82+86+82) / 7 = 79,4 %
Objectif Phase 5 : 80 %.
Reste à gagner : +0,6 pt.
```

**Le score "Pont Python ↔ Rust = 82 %" reste artificiellement élevé.** À chaque capacité Python qui ne touche pas la crate Rust correspondante, ce score *devrait* baisser. La décorrélation D4 est désormais quantifiable : trois capacités Python ont gagné +3 pts sur autres dimensions sans déclencher aucun ajustement sur "Pont". À fixer dans le prochain reporting honnête.

---

**Fin du delta-audit J+2.**
Document généré automatiquement par tâche planifiée `analyse-le-projet-regarde-si-il-y-a-des-amelioration`.
Successeur attendu : prochaine exécution, à compléter avec la décision D5 (a/b), l'état A3, et le sort des 12 proposals.
