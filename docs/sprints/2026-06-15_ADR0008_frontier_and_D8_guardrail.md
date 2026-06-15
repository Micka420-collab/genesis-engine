# Sprint 2026-06-15 (J+5) — ADR-0008 (frontière Python/Rust) + garde-fou D8

**Mode :** morning-routine v3.0 · veille-first · execution-only · run automatique (user absent).
**Décision exécutée :** recommandation **J+5 (b)** de
[`AUDIT-DELTA-2026-06-14.md`](../../native/world-engine/AUDIT-DELTA-2026-06-14.md) §7 —
*ouvrir ADR-0008 (frontière) AVANT toute Cap. C7*, et fermer **F-D8-2** (R-J4-3).

> **Pourquoi pas une Cap. C7 « par défaut » ?** L'audit J+4 a explicitement posé un
> **choix exclusif** : (a) Cap. C7, ou (b) trancher la frontière Python/Rust. Il
> recommandait (b) : *« à 6 capacités Python livrées et 0 Rust en 29 jours, ne pas
> trancher la frontière revient à décider par défaut que Python est la couche de
> simulation. C'est une décision lourde non documentée. »* Empiler une C7 aurait
> approfondi l'asymétrie **D7** que 3 audits flèchent. Le geste senior est
> d'exécuter sa propre recommandation, pas de courir après le compteur de features.

---

## 1. Livré

### 1.1 ADR-0008 — `adr/0008-python-rust-frontier.md` (Accepted)

Nomme la frontière, **réversible sous conditions** :

1. **Couche de simulation active = `runtime/engine/` (Python, déterministe)** pour
   l'ère *cargo-less* — constat assumé (vélocité réelle, 516 tests verts, émergence
   intacte).
2. **`native/world-engine/` = substrat worldgen gelé + oracle de contrat** (le pont
   natif `terrain` fonctionne ; `genesis-geology` reste oracle ADR-0007). Aucun item
   Phase A/B abandonné — **différés** à une « session cargo ».
3. **Frontière = le contrat de tells géologie**, durci par le garde-fou D8 (ci-dessous).
4. **Score honnête (R-J4-1)** : le % réalisme mesure la **couche perception Python**,
   pas le worldgen Rust — désormais dit dans `PROJECT-STATUS.md`.
5. **Réversibilité** : conditions explicites de réactivation Rust (R-J4-2 binding
   `mineral_tells`, D5-wiring, Phase A/B) listées pour la première « session cargo ».

Lève **BLIND-SPOTS R3** (« le plus grand silence stratégique du projet »).

### 1.2 Garde-fou D8 (R-J4-3) — `runtime/tests/test_geology_cross_language_contract.py`

Ferme **F-D8-2** : le moratoire CONTRIBUTING.md *« toute capacité enrichit
`PY_TO_RUST` »* passe de **règle sociale** à **porte CI**.

Les 4 capacités `*_outcrop` (C2/C4/C5/C6) surfacent leurs tells via le même idiome
privé `_PROFILE: {material → Profile}`. On l'**auto-découvre** et on exige que **tout
matériau surfacé soit classé** dans exactement un de :

- **`PY_TO_RUST`** — un tell Rust distinct (obsidian, quartz, coal, peat, oil_shale,
  fine_clay, limestone_pure) ;
- **`PY_CATALOGUE_ONLY`** (nouveau, waiver documenté) — l'enum Rust grossier (16
  variantes) n'a pas de tell distinct ; Python garde l'identité fine et l'agent perçoit
  une **lithologie générique** (slate, shale, basalt, gneiss, granite, sandstone) ou un
  **carbonate** qui bin sur l'unique tell `LimestonePure` (limestone, calcite, marble,
  dolomite).

3 nouveaux tests :

| Test | Ferme |
|------|-------|
| `test_surfaced_capability_modules_all_registered` | un nouveau `engine/*_outcrop.py` non enregistré **casse le build** (force la déclaration C7) |
| `test_every_surfaced_tell_is_classified` | un tell non classé (ni mappé ni waivé) **casse le build** |
| `test_classification_sets_are_disjoint_real_and_live` | pas de double-classement, pas de waiver mort/inexistant |

**Effet net** : la prochaine Cap. C7 ne peut plus ajouter de minéral-tell sans
**décider consciemment** son sort cross-langage. La divergence linéaire que D6/D8
redoutaient (~4000 lignes à C10 sans garde) reste impossible — désormais **par CI**,
plus par convention.

---

## 2. Invariants & discipline

- **Émergence absolue** : 0 contenu scripté ajouté, 0 arbre tech. Pur garde-fou + docs.
- **Capacité ? Non — garde-fou.** Aucun hook `sim.step`, **coût tick nul** → conforme
  au moratoire observateurs (comme `test_observer_budget.py`).
- **Déterminisme** : tests purs (lecture `_PROFILE` + catalogue), bit-stables.
- **cargo-less** : 100 % exécutable ici ; **R-J4-2** (binding compilé `mineral_tells`,
  contre F-D8-1) explicitement **différé** à la session cargo (ADR-0008 §5).

## 3. Tests

```
pytest runtime/tests/test_geology_cross_language_contract.py  → 13/13 ✅ (10 + 3 D8)
pytest runtime/tests                                          → 516/516 ✅ (513 → 516, +3)
                                                                  0 skip · 0 fail · 0 error
```

## 4. Gaps honnêtes (dûs)

- **F-D8-1** non fermé ici (parsing texte du Rust) — demande R-J4-2 (binding), donc
  `cargo`. Différé ADR-0008 §5.
- L'auto-discovery cible la convention `*_outcrop.py` + idiome `_PROFILE`. Une future
  capacité qui surfacerait des tells **hors** de cette convention y échapperait — à
  re-scoper si C7+ change de forme (documenté dans le test).
- **D7 inchangé** : 0 commit Rust. C'est désormais un **choix assumé et daté**
  (ADR-0008), plus une stagnation silencieuse.
- Aucun item Phase A/B Rust fermé (impossible sans `cargo`).

## 5. Suite (J+6+)

- C7 **autorisée** (garde-fou D8 la rend sûre) — devra s'auto-classer ou le build casse.
- Première **session cargo** : exécuter R-J4-2 puis D5-wiring (ADR-0007 étape 2 +
  ADR-0008 §5).
- Recommandation audit **R-J4-1** : appliquée (caveat score dans `PROJECT-STATUS.md`).
