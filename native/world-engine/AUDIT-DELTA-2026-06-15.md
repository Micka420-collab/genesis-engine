# Genesis World Engine — Delta-Audit 2026-06-15 (J+5)

**Mode :** scheduled task `analyse-le-projet-regarde-si-il-y-a-des-amelioration` (run automatique, user absent).
**Successeur direct de** [`AUDIT-DELTA-2026-06-14.md`](./AUDIT-DELTA-2026-06-14.md) (J+4)
et clôture des recommandations [`BLIND-SPOTS-AUDIT-2026-06-13.md`](./BLIND-SPOTS-AUDIT-2026-06-13.md) R3.
**Périmètre :** delta 24 h sur `native/world-engine/` (23 crates) + interface Python ↔ Rust.
**Contrainte env :** `cargo` absent (D7, désormais nommé par [ADR-0008](../../adr/0008-python-rust-frontier.md)). Affirmations Rust = lecture-seule ; CI = vérité.

---

## 0. Verdict express

> **24 h = 2 commits Python, 0 commit Rust — mais c'est la première fois en 30 jours que
> les commits du jour ne sont pas qu'une *capacité de plus*** : avant la 7ᵉ capacité,
> on a tranché la frontière (ADR-0008) et durci le contrat de tells en porte CI (D8 / R-J4-3).
>
> **Bilan des recommandations J+4** — 3 sur 4 fermées en 24 h, la 4ᵉ explicitement différée :
>
> | Reco J+4 | Statut J+5 | Vérif immuable |
> |----------|-----------|----------------|
> | **R-J4-1** : ligne « score = couche perception Python » dans `PROJECT-STATUS.md` | ✅ **fermée** | `PROJECT-STATUS.md` L14-19 (« Sémantique du score réalisme … ») |
> | **R-J4-2** : binding compilé `mineral_tells()` (élimine F-D8-1) | ⏳ **différée** session cargo | nommée dans [ADR-0008 §5](../../adr/0008-python-rust-frontier.md) |
> | **R-J4-3** : hook CI auto-discovering `_PROFILE` Python (ferme F-D8-2) | ✅ **fermée** | 3 tests D8 dans `test_geology_cross_language_contract.py`, +`PY_CATALOGUE_ONLY` (10 entrées) |
> | **J+5 option (a) / (b)** : trancher la frontière OU livrer C7 | ✅ **les deux** | `1658e9c` (ADR-0008) puis `0d2ba7a` (Cap. C7) |
>
> **Le « plus grand silence stratégique » identifié J+1 → J+4 (BLIND-SPOTS R3) est levé.**
> D7 change de nature : la vélocité asymétrique Python/Rust **reste réelle** mais cesse d'être
> *implicite* — c'est désormais un choix daté, réversible sous conditions explicites.

---

## 1. Ce qui a changé en 24 h

### 1.1 Commits

| Commit  | Heure CEST     | Couche  | Titre |
|---------|----------------|---------|-------|
| `1658e9c` | 04:22  | Python+ADR | `chore(platform/contract):` ADR-0008 frontière Python/Rust + garde-fou D8 (moratoire tells CI-enforced) |
| `0d2ba7a` | 05:37  | Python  | `feat(substrate/fire):` fire-ignition affordance — emergent strike-a-light / fire-drill discovery (Cap. C7) |

Vérifications immuables (lecture-seule) :

- `git log --since="2026-06-14 23:00" -- native/world-engine/ ':!*AUDIT*' ':!*BLIND*'` → **vide**
  (le seul changement sous `native/world-engine/` est l'**ajout** de l'audit J+4 par le commit
  ADR ; aucune ligne touchée dans `crates/`).
- `grep -c "Mineral::" crates/geology/src/mineral.rs` = **72** (inchangé J+4).
- `pub const MINERAL_COUNT: usize = 16;` (inchangé Wave 43).
- `PY_TO_RUST` (test) : **15 entrées** (inchangé J+4 → J+5 : C7 n'introduit
  aucun nouveau tell, garantie par `test_introduces_no_new_tell` côté C7).
- **Nouveau** : `PY_CATALOGUE_ONLY` (test) : **10 entrées** (waivers documentés —
  slate/shale/basalt/gneiss/granite/sandstone + carbonates fins).
- `pytest --collect-only -q` : **536 tests** (vs 513 à J+4, soit **+23** :
  +3 D8 guard-rail + +20 fire_ignition, conforme `PROJECT-STATUS.md`).
- `grep -c "sim.step\|register_observer" runtime/engine/fire_ignition.py` = **0**
  → C7 est bien **capacité, pas observateur** (coût tick nul → garde D1 tenue).

### 1.2 Propriétés tenues (rappel J+4 → J+5)

| Garde-fou                       | État J+5   | Vérification immuable |
|---------------------------------|------------|------------------------|
| D1 observer-budget < 10 %       | ✅ tenu     | 0 hook `sim.step` ajouté en 24 h (C7 = capacité ; ADR = test pur) |
| D5 (ADR-0007) oracle de contrat  | ✅ tenu     | crate `geology` toujours dead-code-utile ; aucune crate ne l'importe |
| D6 (divergence Python/Rust)     | ✅ tenu     | `PY_TO_RUST` inchangé ; C7 ne touche pas au catalogue |
| D7 (cargo-less)                 | ⚠ **assumé** | reste 0 commit Rust en 30 j ; **mais désormais nommé** par ADR-0008 |
| **D8** (single-point-of-truth)  | ⚠ partial → durci | F-D8-2 et F-D8-3 fermés par R-J4-3 ; F-D8-1 reste ouvert (parse texte) |
| Émergence (pas de scripting)    | ✅ tenu     | C7 = composition pyrite (C1) × percuteur (C2) × amadou — aucune recette codée |
| Déterminisme bit-à-bit          | ✅ tenu     | seed `0xBEEF` prairie, 144 chunks vérifiés (0 violation) |
| Smoke quotidien `pNNN_*_smoke.py` | ✅ tenu   | `p139_fire_ignition_smoke.py` créé (7/7) |

---

## 2. Scoreboard Phase A / B — delta J+5

### Phase A (extrait NEXT-LEVEL-AUDIT §2)

| Item                          | 2026-06-14 (J+4) | 2026-06-15 (J+5) | Delta |
|-------------------------------|------------------|------------------|-------|
| A1 apply_pending (vrai write) | ✅                | ✅                | — |
| A2 vraie LRU (priority queue) | ⚠ partial         | ⚠ partial         | stagnation **J+30** |
| A3 spatial index (rstar)      | ❌ stub `Vec::new()` | ❌ identique     | stagnation **J+30** |
| A4 raycast accéléré           | ❌ DDA naïf       | ❌ identique      | stagnation **J+30** |
| A5 GPU erosion auto-fallback  | ❌                | ❌                | stagnation **J+30** |
| A6 snapshot/restore           | ✅                | ✅                | — |
| A7 fog-of-war filter          | ⚠ partial         | ⚠ partial         | — |
| **D5-wiring** (issu ADR-0007) | ⏳ ouvert         | ⏳ **explicitement** différé | ADR-0008 §5 le liste comme réactivable |

Score Phase A : **2 ✅ / 3 ⚠ / 3 ❌ + 1 ⏳** — strictement inchangé sur 24 h. **30 jours sans
item Phase A mergé.** Différence J+5 vs J+4 : la stagnation est *nommée et bornée* (ADR-0008
§5 « conditions de réactivation Rust »), plus *muette*.

### Phase B (extrait NEXT-LEVEL-AUDIT §2)

| Item B1 → B8 | 2026-06-14 | 2026-06-15 |
|--------------|-----------|-----------|
| Tous (tectonique dyn, hydro cross-chunk, advection humidité, saisons, SDF caves, boids, hot-reload biomes, debug overlay) | ❌ 0/8 | ❌ 0/8 |

---

## 3. Risques D-series — delta J+5

| ID | Risque                                              | État J+4         | État J+5         | Commentaire J+5 |
|----|-----------------------------------------------------|------------------|------------------|-----------------|
| D1 | Treadmill observateurs                              | ✅ tenu          | ✅ tenu          | 0 observateur ajouté en 24 h ; 1 capacité + 1 garde-fou |
| D2 | `maybe_evict` O(N)                                  | ❌                | ❌                | stagnation J+30 (cargo) |
| D3 | Stub `entities_in_radius`                           | ❌                | ❌                | stagnation J+30 (cargo) ; bloque perception multi-agent côté Rust |
| D4 | Décorrélation score réalisme ↔ moteur Rust          | ⚠ aggravé       | ⚠ **documenté** | R-J4-1 ferme la dette d'honnêteté : le score est maintenant *dit* « couche perception Python ». La dérive existe encore, mais cesse d'être trompeuse. |
| D5 | `genesis-geology` orphelin                          | ✅ ADR-0007      | ✅ ADR-0007 + 0008 §5 | reste oracle ; câblage relisté dans les items réactivables |
| D6 | Double-source Python/Rust géologie                  | ✅ fermé         | ✅ fermé         | `PY_TO_RUST` inchangé en 24 h (C7 ne touche pas) |
| D7 | Vélocité asymétrique permanente                     | ⚠ structurel     | ⚠ **assumé**     | ADR-0008 le nomme : « ne pas trancher = décider par défaut » ⇒ on tranche en faveur de Python *pour l'ère cargo-less*. Pas une victoire, un *constat daté*. |
| D8 | `PY_TO_RUST` single-point-of-truth                  | ⚠ émergent       | ⚠ **partiellement durci** | R-J4-3 ferme F-D8-2 et F-D8-3 (CI). F-D8-1 (parse texte fragile) reste ouvert, différé R-J4-2 (binding compilé). |

**Lecture stratégique** : le tableau D bouge de gauche à droite **sans aggraver**. Trois
risques (D4, D7, D8) passent de « silencieux/structurel » à « documenté/borné ». Aucun
risque nouveau n'apparaît à J+5.

---

## 4. La voûte C7 — pourquoi ce n'est pas « une 7ᵉ capacité de plus »

C7 mérite une lecture séparée. Cap. C1 → C6 ont rendu *perceptibles* les **matières** de
l'âge de pierre (minerai, pierre taillable, eau potable, combustible, argile, calcaire).
Mais presque toutes demandent ensuite **un feu** pour devenir outil :

| Capacité | Matière débloquée | Voie d'usage qui requiert le feu |
|----------|-------------------|-----------------------------------|
| C1 surface_mineralization | cuivre (malachite/gossan) | **fondre** |
| C4 combustible_outcrop    | charbon / tourbe / schiste | **brûler** durablement |
| C5 clay_outcrop           | argile (kaolin / shale)    | **cuire** (céramique) |
| C6 limestone_outcrop      | calcaire pur               | **calciner** (chaux) |

Sans amorçage *par l'agent*, ces capacités restaient **des matières inertes**. C7
(`engine.fire_ignition`) est la **voûte** qui les rend actionnables — d'où son qualificatif
dans le sprint doc et `PROJECT-STATUS.md`. Deux propriétés saillantes pour l'audit :

1. **Pas de tell nouveau, par décision** — C7 *compose* les tells de C1 (pyrite/gossan) et
   C2 (percuteur), asservi par `test_introduces_no_new_tell`. Le garde-fou D8 est respecté
   par **composition**, pas contourné. C'est la première capacité qui démontre que le
   moratoire est *praticable* sans gonfler `PY_TO_RUST`.
2. **N'aggrave pas le treadmill** que J+4 §6 craignait — la séquence C1 → C7 cesse d'être
   « 7 minerais muets de plus » et devient un **arc d'affordance émergente**. Si C8 suit
   la même règle (utiliser ce qui existe au lieu d'ajouter un tell), l'arc reste tenu.

⚠️ **Honnêteté** : C7 reste de la **perception agent**, pas du worldgen Rust. Il ne ferme
aucun item Phase A/B. Le caveat R-J4-1 s'applique : « 80,0 % » mesure ce que l'agent
*perçoit / peut faire*, pas ce que le moteur Rust *génère*.

---

## 5. Honnêteté (ce qui reste dû depuis J+0)

- **R1 du BLIND-SPOTS — audit des 8 crates non lues** (`weather`, `physics`, `laws`,
  `intent`, `mesh`, `studio`, `macro-bridge`, `worldgraph` ré-évalué). **Toujours dû.**
  Un fichier `crates/STATUS.md` (30-s par crate : active/dormant/orpheline) reste à écrire.
- **R2 du BLIND-SPOTS — axe 7 « perception multimodale »** non formalisé. Wave 44 olfaction +
  C1-C7 perception minéralogique constituent *de facto* cet axe. L'amender dans
  `NEXT-LEVEL-AUDIT.md` §5 prend < 30 min ; **toujours dû**.
- **R3 du BLIND-SPOTS — ADR-0008 frontière**. ✅ **fermé J+5** (ce qu'on documente ici).
- **F-D8-1** (parse texte du Rust pour vérifier le contrat) — différé explicitement à
  ADR-0008 §5 / R-J4-2 (binding `mineral_tells`). Reste ouvert tant que pas de session cargo.

---

## 6. Axes 1-6 de la mission scheduled task — couverture J+5

Rappel : la tâche planifiée demande un audit sur 6 axes. L'audit complet est dans
[`NEXT-LEVEL-AUDIT.md`](./NEXT-LEVEL-AUDIT.md) (2026-05-16). Statut J+5 par axe :

| Axe | Item phare audit 05-16 | Statut J+5 | Commentaire |
|-----|------------------------|------------|-------------|
| **1 — Géologie** | Tectonique dynamique (B1), SDF caves (B5) | ❌ 0/2 | proposals `axis1_geology/*.rs` toujours hors workspace ; cap. C7 = perception, pas worldgen |
| **2 — Climat** | Advection humidité (B3), saisons (B4) | ❌ 0/2 | `climate/src/lib.rs` inchangé ; C7 lit humidité d'amadou *via* `chunk.water`, ne la fabrique pas |
| **3 — Écosystème** | Boids (B6), Lotka-Volterra | ❌ 0/2 | `ecosystem/src/lib.rs` toujours seeds-only |
| **4 — Perf** | Vraie LRU (A2), spatial index (A3), GPU pipeline (A5) | ⚠ 0/3 (A2 partial) | Stagnation J+30 sur A2/A3/A5. Items maintenant **listés réactivables** dans ADR-0008 §5. |
| **5 — Agent-API** | apply_pending (A1), snapshot (A6), fog-of-war (A7) | ✅⚠ 2/3 | A1 + A6 livrés (Wave 42-43). A7 ⚠ partial. **C7 enrichit indirectement l'axe** : actionnabilité de la perception (allumer un feu), pas seulement lecture. |
| **6 — Devtools** | Hot-reload biomes (B7), debug overlay (B8) | ❌ 0/2 | proposals `axis6_devtools/*` non promus |

**Score axes mission** : **2 / 16** items mergés en 30 jours sur la roadmap audit.
Strictement identique à J+4. **L'angle qui avance** — la couche perception/capacité Python
— continue d'enrichir l'**axe 5** (côté actionnabilité) plus que les autres. C'est cohérent
avec ADR-0008 §1.

---

## 7. Procédure recommandée J+6 → J+10

Cadrée sur ce qui est *exécutable sans `cargo`* (D7 assumé par ADR-0008) :

```
J+6 (2026-06-16) :
  Options non exclusives (ADR-0008 ayant levé le moratoire C7) :

  (a) Cap. C8 — première capacité de TRANSFORMATION (pas de perception).
      C7 a livré l'amorçage du feu ; C8 = première utilisation actionnable :
      e.g. drying_loop (sécher l'amadou C7 → durabiliser combustible C4)
      ou tempering (chauffer pierre C2 pour la rendre taillable).
      RÈGLE : aucune nouvelle entrée PY_TO_RUST, composition pure (C7 a montré
      que c'est faisable). Test test_introduces_no_new_tell à dupliquer.

  (b) R1 BLIND-SPOTS — écrire crates/STATUS.md (30-s/crate, état active/dormant).
      Dette de transparence J+30, < 1 h de travail. Permet à un nouveau
      contributeur de comprendre le périmètre en 5 min.

  (c) R2 BLIND-SPOTS — formaliser l'axe 7 « perception multimodale » dans
      NEXT-LEVEL-AUDIT.md §5. Reconnaît rétroactivement Wave 44 + C1-C7
      comme un axe à part entière. Dette éditoriale.

  Recommandation : (b) en priorité (30 jours sans audit des 8 crates =
  risque de dette croissante invisible), puis (a) si capacité dispo dans
  la journée.

J+7 → J+10 :
  - Tant qu'on reste cargo-less : alterner capacité (axe 5 perception/actionnabilité)
    et dette éditoriale (R1/R2). Refuser de tomber dans la cadence « 1 capacité/jour »
    qui réintroduit le risque de C7 inverse (matière sans utilisation).
  - Item « réactivable cargo-less » : aucun nouveau cette session.
    A6.5 (snapshot rkyv) reste candidat mais non urgent.

Tout item Phase A/B nécessitant cargo (A3 rstar, A4 raycast, A5 GPU, B1-B8 / D5-wiring) :
  bloqué structurellement par D7 (assumé). ADR-0008 §5 les liste. Programmer une
  session « cargo dispo » hors routine matinale reste la voie unique.
```

---

## 8. Métrique J+5

| Métrique                                  | J+4       | J+5       | Δ      |
|-------------------------------------------|-----------|-----------|--------|
| Commits Rust (`native/world-engine/crates/`) | 0     | 0         | 0      |
| Commits Python `runtime/`                  | 2 (C5+C6) | 1 (C7)   | -1     |
| Commits ADR / contrat                      | 0         | 1 (0008+D8) | +1   |
| Tests pytest                               | 513       | **536**   | **+23** |
| Capacités émergentes (cumul)               | 6 (C1-C6) | **7 (C1-C7)** | +1 |
| `PY_TO_RUST` (entrées)                     | 15        | **15**    | **0** (C7 par composition) |
| `PY_CATALOGUE_ONLY` (entrées)              | —         | **10**    | nouveau |
| `_CAPABILITY_TELL_MODULES` (entrées)       | —         | **4**     | nouveau |
| Items Phase A mergés (cumul J+0)           | 2 / 8     | 2 / 8     | 0      |
| Items Phase B mergés (cumul J+0)           | 0 / 8     | 0 / 8     | 0      |
| ADR ouverts (Phase A déférés)              | 1 (0007) | **2 (0007+0008)** | +1 |
| Score sociétés Python (memory)             | 78        | **78**    | 0 (C7 = actionnabilité, pas point réalisme) |
| Score réalisme global (memory)             | ~79,9 %   | **~80,0 %** (cible) | +0,1 pt |
| Recommandations J+4 fermées                | —         | **3 / 4** (R-J4-2 différée) | — |
| Stagnation A3/A4/A5                        | J+29      | **J+30**  | +1 j   |
| **Silences stratégiques (BLIND-SPOTS R3)** | 1 ouvert  | **0**     | **-1** |

---

## 9. Une phrase pour conclure

> La journée J+5 a fait ce que **J+1 → J+4 demandaient sans pouvoir l'imposer** :
> trancher la frontière (ADR-0008), durcir le contrat par CI (D8/R-J4-3), corriger
> l'ambiguïté du score (R-J4-1) — *puis seulement* livrer la 7ᵉ capacité, sous garde-fou
> de composition. Pour la première fois en 30 jours, **les commits Python ne sont pas
> seuls** : ils s'accompagnent d'une décision de plateforme datée. Le moteur Rust ne
> progresse toujours pas, **mais cette stagnation est désormais un choix réversible
> sous conditions explicites**, plus un silence.

---

**Fin du delta-audit J+5.** Aucun fichier `proposals/*.rs` ajouté, aucun item Phase A/B
mergé, aucune dépendance ajoutée. Trois recommandations J+4 fermées (R-J4-1, R-J4-3, BLIND-SPOTS R3),
une explicitement différée (R-J4-2 → session cargo). Zéro risque nouveau, deux risques
durcis (D4 documenté, D7 assumé), un risque partiellement fermé (D8 : F-D8-2 + F-D8-3
clos par CI ; F-D8-1 reste ouvert).
