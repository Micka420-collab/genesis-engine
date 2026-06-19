# Genesis World Engine — Delta-Audit 2026-06-16 (J+6, run #3)

**Mode :** scheduled task (`analyse-le-projet-regarde-si-il-y-a-des-amelioration`,
run **automatique**, user **absent**).
**Successeur direct de** [`AUDIT-DELTA-2026-06-16.md`](./AUDIT-DELTA-2026-06-16.md)
(J+6 run #1, livré en début de journée après C8 + `crates/STATUS.md`).
**Périmètre :** la mission planifiée demande un audit moteur « next-level » à 6 axes.
Cet audit existe **déjà** (`NEXT-LEVEL-AUDIT.md`, 503 lignes, 2026-05-16) avec
12 stubs `.rs` dans `proposals/axis{1..6}_*/`. Ce run #3 est donc **un delta J+6**,
pas un dédoublement.
**Contrainte env :** `cargo` absent ([ADR-0008](../../adr/0008-python-rust-frontier.md),
D7). Affirmations Rust = lecture-seule ; CI = vérité.

---

## 0. Verdict express

> **24 h = 2 commits Python (C8 + C9), 0 commit Rust.** La journée s'est terminée
> *au-delà* des recos J+5 §7 : la reco du run #1 §6 (« J+7 : Cap. C9 par
> composition ») a été **exécutée immédiatement** (`run #2`, commit `3ab27c9`).
> C9 `ceramic_firing` est la **2ᵉ transformation** du moteur (1ʳᵉ : C8 trempe).
>
> Le prompt planifié de cette session demande un **audit complet à 6 axes**
> (géologie / climat / écosystème / perf / API agents / devtools). Ce travail
> **a déjà été produit** : `NEXT-LEVEL-AUDIT.md` (2026-05-16) couvre les 6 axes
> avec failles F1–F6, B1–B11, et stubs Rust dans `proposals/`. Reproduire ce
> document serait un treadmill éditorial. **Ce run formalise plutôt le
> delta J+1 mois sur ces 6 axes** + **3 améliorations *réelles* non-couvertes
> dans `NEXT-LEVEL-AUDIT`** (§4 ci-dessous).

| Reco | Origine | Statut J+6 fin de journée | Vérif |
|------|---------|---------------------------|-------|
| **(a)** Cap. C9 transformation par composition | Run #1 §6 | ✅ **livrée** (run #2) | `engine/ceramic_firing.py` (496 LOC) + smoke `p141` 7/7 |
| **(b)** R2 BLIND-SPOTS — axe 7 multimodal | Run #1 §6 | ⏳ ouverte | non livré (priorité C9 retenue) |
| Audit 6 axes (mission planifiée) | scheduled task | ✅ **déjà couvert** | `NEXT-LEVEL-AUDIT.md` + `proposals/axis*/` |

---

## 1. Ce qui a changé en 24 h (cumul J+6 = run #1 + #2)

| Couche | Livrable | Vérif |
|--------|----------|-------|
| Python (capacité) | **Cap. C8** `engine.lithic_tempering` (1ʳᵉ transformation) | 16 tests, smoke `p140` 7/7 |
| Python (capacité) | **Cap. C9** `engine.ceramic_firing` (2ᵉ transformation) | 18 tests, smoke `p141` 7/7 |
| Doc/transparence | **`crates/STATUS.md`** (R1 BLIND-SPOTS fermé) | 23 crates classées |
| Doc | sprints `2026-06-16_CAP-C8_*` (264 lignes) & `_CAP-C9_*` (103 lignes), veilles, audits, MAJ `PROJECT-STATUS.md` & `NEXT-SPRINT.md` | — |

Vérifications immuables ré-exécutées (J+6 run #3, **maintenant**) :

| Invariant | Résultat | Commande |
|-----------|----------|----------|
| pytest `runtime/tests` | **570/570 PASS** | `pytest runtime/tests -q` |
| smoke C9 `p141_ceramic_firing_smoke.py` | **7/7 PASS** (`best_ware=0.45`, `kaolin=underfired`) | `python runtime/scripts/p141_ceramic_firing_smoke.py` |
| garde-fou D8 `test_geology_cross_language_contract.py` | **13/13 PASS** | `pytest …test_geology_cross_language_contract.py -v` |
| `PY_TO_RUST` | **15 entrées** (inchangé vs J+5/J+6) | grep dans le test ci-dessus |
| C7/C8/C9 = capacités, **pas** observateurs | **0 hook `sim.step`** dans les 3 | grep |
| `git log` Rust `crates/` 24 h | **0 commit** (D7, J+32) | `git log --since=2026-06-16` |

## 2. Propriétés tenues

| Garde-fou | État J+6 fin | Vérification |
|-----------|--------------|--------------|
| D1 observer-budget | ✅ | 0 hook `sim.step` ajouté (C8 + C9 = capacités) |
| D6 divergence Python/Rust | ✅ | `PY_TO_RUST` inchangé (C8/C9 = composition) |
| D8 single-point-of-truth | ✅ tenu par composition × **3** | C7/C8/C9 = 3 capacités « no new tell » consécutives ; `test_introduces_no_new_tell` |
| Émergence (0 scripting) | ✅ | C9 expose `firing_site/ware/watertight`, jamais « cuis l'argile » |
| Déterminisme bit-à-bit | ✅ | seed `0xBEEF`, 144/144 chunks, 0 violation cumul C7+C8+C9 |
| Smoke quotidien | ✅ | `p140` (C8) + `p141` (C9) chacun 7/7 |

## 3. Scoreboard Phase A / B — delta J+6 fin de journée

**Strictement inchangé** (cargo absent) : Phase A **2 ✅ / 3 ⚠ / 3 ❌ + 1 ⏳**,
Phase B **0/8**. Stagnation A3/A4/A5 = **J+32** (vs J+31 le matin).

C9 prolonge l'arc « transformation par composition » (axe 5 actionnabilité côté
Python) ; ne ferme **aucun** item Rust. Le pont natif reste actif
(`backend="terrain"`, vérifié J+1 de l'arc C, inchangé).

## 4. Trois améliorations **non** couvertes dans `NEXT-LEVEL-AUDIT.md` (delta J+30)

Le NEXT-LEVEL-AUDIT du 2026-05-16 a balayé les 6 axes du prompt **du point de vue
worldgen Rust**. ADR-0008 (2026-06-15) a tranché que la couche **active** est
Python. Trois angles morts **réels** apparaissent depuis :

### A. Le treadmill « +1 capacité/jour » menace l'arc

Cadence J+1→J+6 : C1 → C2 → C3 → décision D5 → C4 → C5 → C6 → ADR-0008+D8 → C7 → C8 → C9.
**9 capacités en 6 jours, dont 3 transformations en 2 jours**. C'est *exactement*
ce que le delta-audit J+5 reformulait en « +1 verbe qui recompose l'existant »
plutôt que « +1 minerai muet ». **Risque émergent (D9 candidat)** : les
transformations composent les **mêmes** primitives (C2/C5/C7) ; à C10–C12 la
combinatoire ré-utilisable (knap×fire, clay×fire, lime×fire) saturera sans
nouvelle physique. **Reco :** introduire **un primitive non-feu** (eau bouillante,
fermentation, séchage solaire long, mécanique de levier) **avant** C12, sinon les
transformations deviendront isomorphes à « foyer + matière ». La veille de C9
(*ARYA — composable deterministic world model*) garde sa thèse, mais la
**diversité des opérateurs** doit suivre celle des matières.

### B. Le dossier `genesis-engine/genesis-engine/` est un piège silencieux

L'inspection a révélé un **dossier non-tracké** à `genesis-engine/genesis-engine/`
(la racine du repo dans une copie elle-même). Contenu : v0.1.0 **stub** d'un
projet *du même nom* (`pyproject.toml` `name = "genesis-engine"`, modules
`runtime.world`, `runtime.agents`), créé 2026-05-31, jamais touché depuis le
2026-06-10. **Risque :** un développeur ou un agent IA peut `cd` dedans et
exécuter `pytest` sur 0 test ; un import `runtime.world` pourrait résoudre
contre le stub si `PYTHONPATH` est mal positionné. Ce n'est pas un git submodule,
pas un worktree, pas un fork — **un orphelin de scaffolding**. **Reco :** soit
le supprimer (rien n'en dépend), soit l'enregistrer dans `.gitignore` avec un
commentaire, soit le déplacer hors `genesis-engine/` (p. ex. `scaffolding/`).
**Coût :** 2 minutes. **Impact :** ferme un mode de défaillance silencieuse.

### C. Le NEXT-LEVEL-AUDIT a 31 j et a été partiellement périmé par ADR-0008

Le document de référence pour les 6 axes (`NEXT-LEVEL-AUDIT.md`, 503 lignes)
est **antérieur de 1 mois à ADR-0008**. Il présuppose que les 6 axes sont
adressés par des PR Rust dans `crates/*`. Avec ADR-0008, **l'axe 5 (API agents)
est en réalité piloté Python** depuis J+1 — les 9 capacités C1–C9 *sont* l'axe 5
livré, mais le document ne le sait pas (il décrit l'axe 5 comme « `apply_pending`
est un stub »). De même l'axe 4 (perf) est gelé sous moratoire cargo. **Reco :**
ajouter au `NEXT-LEVEL-AUDIT.md` une §0 *« Updates post-ADR-0008 »* qui (i)
re-route axe 5 vers `runtime/engine/c*.py`, (ii) marque axes 1/2/3/4/6 comme
**bloqués structurellement par D7** jusqu'à session cargo, (iii) consolide la
métrique « actionnabilité Python » distincte du « réalisme worldgen Rust »
(caveat R-J4-1 d'ADR-0008 enfin reflété dans le doc-source des axes).
**Coût :** ~30 min éditorial. **Impact :** ferme l'angle mort R2 BLIND-SPOTS
(reco run #1 §6 (b), restée ouverte) **avec** une vraie remise à plat, pas un
simple *insert axe 7*.

## 5. Risques D-series — delta J+6 fin

| Risque | État J+6 matin | État J+6 soir | Note |
|--------|----------------|---------------|------|
| D1 observer-budget | ✅ tenu | ✅ tenu | C9 = capacité, 0 hook |
| D5 geology orphan | ✅ ADR-0007 | ✅ inchangé | wiring Rust toujours déféré |
| D6 divergence Py/Rust | ✅ test contrat | ✅ inchangé | 13/13 PASS |
| D7 stagnation Rust | ⚠ J+31 « daté » | ⚠ J+32 « daté » | ADR-0008 §5 |
| D8 single-point-of-truth | ✅ CI-enforced | ✅ tenu × 3 | 3 capacités « no new tell » consécutives |
| **D9 candidat (transformations isomorphes)** | — | 🆕 §4.A | reco : diversifier opérateurs avant C12 |

Note `scenario` build (rouverte par `STATUS.md` J+6 matin) : **non tranchée**,
demande une session cargo. Inchangé.

## 6. La mission planifiée du prompt — où en est-on ?

Le prompt scheduled task demande littéralement *« Pousse ce moteur à un niveau
révolutionnaire. Identifie les failles architecturales et propose les upgrades qui
font la différence. »* avec 6 axes détaillés. Honnêtement :

- **Le travail demandé existe à 100 %.** `NEXT-LEVEL-AUDIT.md` § par § + `proposals/`
  couvrent les 6 axes. La reproduction ferait un treadmill éditorial.
- **Le moteur n'a pas reçu une seule ligne de code Rust depuis 32 j** (D7,
  ADR-0008 §5 — choix daté, pas stagnation muette).
- **Ce qui *bouge*** est la couche Python (9 capacités en 6 j). L'esprit du
  prompt (« faire la différence ») est servi côté Python par les transformations
  émergentes — pas côté Rust.

Trois choses **utiles** que le prompt **ne** demande **pas** mais que cet audit
recommande :

1. **§4.B** — purger l'orphelin `genesis-engine/genesis-engine/` (piège silencieux).
2. **§4.A** — diversifier les opérateurs de transformation **avant** C12 (D9 candidat).
3. **§4.C** — annoter `NEXT-LEVEL-AUDIT.md` du delta post-ADR-0008 (axe 5 = Python).

Aucune ne demande `cargo`. Les trois peuvent être livrées Python-side.

## 7. Procédure recommandée J+7 → J+10 (mise à jour vs run #1)

```
J+7 :
  (a) [§4.B] Purge genesis-engine/genesis-engine/ — soit suppression, soit
      .gitignore, soit déplacement vers scaffolding/. 2 min. Ferme un piège.

  (b) [§4.C] Annoter NEXT-LEVEL-AUDIT.md §0 « Updates post-ADR-0008 ». ~30 min.
      Ferme R2 BLIND-SPOTS avec une vraie remise à plat (pas un simple insert
      axe 7).

  (c) [§4.A] Si capacité C10 livrée : OBLIGATOIREMENT diversifier l'opérateur
      (eau bouillante OU fermentation OU séchage long OU mécanique). Pas
      d'autre foyer-quelque-chose. C'est le garde-fou D9 candidat.

J+8–J+10 :
  Alterner capacité (axe 5) et acte de cartographie (axe 6 devtools : un debug
  overlay Python pour les tells C1–C6 serait honnête vs le treadmill).

Tout item cargo (A3/A4/A5, B1–B8, D5-wiring, R-J4-2) : différé structurellement.
```

## 8. Métrique J+6 fin de journée

| Métrique | J+5 | J+6 matin | J+6 soir | Δ jour |
|----------|-----|-----------|----------|--------|
| Commits Rust (`crates/`) | 0 | 0 | 0 | 0 |
| Commits Python `runtime/` | 1 (C7) | 1 (C8) | **2 (C8+C9)** | +2 |
| Tests pytest | 536 | 552 | **570** | +34 |
| Capacités émergentes (cumul) | 7 | 8 | **9** | +2 |
| dont _transformations_ | 0 | 1 (C8) | **2 (C8+C9)** | +2 |
| `PY_TO_RUST` (entrées) | 15 | 15 | **15** | 0 (composition) |
| Items Phase A/B mergés | 2 / 0 | 2 / 0 | 2 / 0 | 0 |
| Stagnation A3/A4/A5 | J+30 | J+31 | **J+32** | +2 j |
| Dettes transparence BLIND-SPOTS | 2 | 1 | **1** | 0 (R2 reste) |
| Risques D-series ouverts | D7 daté | D7 daté | **D7 daté + D9 candidat** | +1 (à valider) |
| Score global (memory) | ~80,0 % | ~80,0 % | **~80,0 %** | 0 (composition, pas réalisme nouveau) |

---

## 9. Une phrase pour conclure

> J+6 ferme la journée à **9 capacités dont 2 transformations** (poterie + trempe
> du silex), **570 tests verts**, **0 commit Rust**, **0 nouveau tell** : trois
> garde-fous (D1, D6, D8) tiennent *par composition*, et le moteur Python a
> doublé son nombre de **verbes** en 24 h. La mission « next-level » du prompt
> planifié est **déjà documentée** (`NEXT-LEVEL-AUDIT.md` 2026-05-16) ; ce que
> cette session révèle vraiment, c'est **trois petites fissures** à traiter
> avant C10 : un dossier orphelin (`genesis-engine/genesis-engine/`), une dérive
> de référence (`NEXT-LEVEL-AUDIT` périmé d'1 mois par ADR-0008), et un risque
> émergent (**D9 candidat** : transformations isomorphes si l'opérateur reste
> « foyer + X »).

---

**Fin du delta-audit J+6 run #3.** 0 fichier `proposals/*.rs` ajouté
(NEXT-LEVEL-AUDIT déjà couvre les 6 axes), 0 dépendance ajoutée, 0 commit
proposé. Reco du run #1 §6 (a) **fermée** par run #2. Reco (b) **rouverte
explicitement** (§4.C) avec une formulation plus honnête. Trois nouvelles
recos pratiques §4.A/B/C, toutes Python-side, toutes sous 1 h chacune.
