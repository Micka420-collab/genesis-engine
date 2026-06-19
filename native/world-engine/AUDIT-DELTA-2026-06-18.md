# Genesis World Engine — Delta-Audit 2026-06-18 (J+8)

**Mode :** scheduled task (`analyse-le-projet-regarde-si-il-y-a-des-amelioration`),
run **automatique**, user **absent**.
**Successeur direct de** [`AUDIT-DELTA-2026-06-17.md`](./AUDIT-DELTA-2026-06-17.md)
(J+7, livré en fin de journée après C10 + C11).
**Périmètre :** la mission planifiée demande un audit moteur « next-level » à
6 axes. Cet audit existe **déjà** (`NEXT-LEVEL-AUDIT.md`, 503 lignes,
2026-05-16) avec 12 stubs `.rs` dans `proposals/axis{1..6}_*/`. Ce run J+8 est
donc — pour la **9ᵉ fois consécutive** — un **delta** (pas un dixième
dédoublement) et il **prend acte** d'une violation P0 manifeste : le **verrou
C12 du J+7** a été **explicitement ignoré**, deux fois en 24 h.
**Contrainte env :** `cargo` absent ([ADR-0008](../../adr/0008-python-rust-frontier.md),
D7). Affirmations Rust = lecture-seule ; CI = vérité.

---

## 0. Verdict express

> **J+8 a livré 2 capacités (C12 forced_draught + C13 copper_smelting),
> 0 commit Rust, et a *violé explicitement le verrou P0 posé hier soir*.**
> La règle **D9** flaggée hier (« 5 capacités fire-based consécutives ») devient
> aujourd'hui **D9 escaladé** : **7 capacités fire-based consécutives
> (C7→C8→C9→C10→C11→C12→C13)**. C13 a livré la **1ʳᵉ métallurgie** —
> séduisant — mais elle réutilise *verbatim* le seuil thermique de C12 qui
> réutilise le seuil de C11 qui réutilise celui de C9. Le **mensonge #4**
> (cuivre natif vs chalcopyrite via tell vert C1) est une vraie victoire
> émergente ; reste qu'**aucun** des 3 recos J+7 (a/b/c) n'est honoré.

| Reco J+7 (run §7) | Statut soir J+8 | Vérif |
|---|---|---|
| **§7.A** (P0) **Gel C12** jusqu'à opérateur non-thermique | ❌ **VIOLÉ** | C12 commit `1228665` (fire+bellows) **+** C13 commit `ff666af` (fire→metal) — 2 violations en 24 h |
| **§7.B** Purger `genesis-engine/genesis-engine/` (orphelin J−3) | ❌ **non livrée** | `git status` : encore `Untracked files: genesis-engine/` (3ᵉ jour) |
| **§7.C** Annoter `NEXT-LEVEL-AUDIT.md` §0 post-ADR-0008 | ❌ **non livrée** | en-tête inchangé (`Date : 2026-05-16`, « 15 crates » alors qu'on en a 23) |

Pour mémoire, la cadence du run automatique est désormais **+2 caps/jour
constant sur 8 jours**, soit **13 capacités cumulées en 8 jours**, dont
**4 transformations** (C8/C9/C10/**C13**) et **2 apparatus** (C11/C12) —
**toutes alimentées par le foyer C7**. Le verrou C12 du J+7 a *littéralement*
été franchi le matin même, sans débat. La fonction sélectionnant la prochaine
capacité côté Python ne consomme manifestement pas les recos d'audit (3ᵉ
preuve consécutive).

---

## 1. Ce qui a changé en 24 h (J+7 fin → J+8 fin)

| Couche | Livrable | Vérif |
|---|---|---|
| Python (capacité) | **Cap. C12** `engine.forced_draught` (2ᵉ apparatus, soufflet+charbon → 1100–1400 °C, vitrification kaolin **enfin True**, ouvre cuivre métallurgie) | commit `1228665`, 21 tests, smoke `p144` 7/7 |
| Python (capacité) | **Cap. C13** `engine.copper_smelting` (4ᵉ transformation, **1ʳᵉ métallurgique**, mensonge #4 native_copper vs chalcopyrite) | commit `ff666af`, 19 tests, smoke `p145` 7/7 |
| Rust (`crates/`) | aucun | `git log --since=2026-06-17 -- native/world-engine/crates` : 0 hit |
| Doc | sprints CAP-C12 / CAP-C13, MAJ `PROJECT-STATUS.md`, mémoires `project_2026-06-18_forced_draught.md` et `project_2026-06-18_copper_smelting.md` | — |
| Mutation monde | **1ʳᵉ apparition** d'un opérateur **mutant** (`smelt_at` consomme le minerai via `geo.mine_at`) — auparavant tout était perception/inspection | commit `ff666af` corps |

**Invariants ré-exécutés (J+8 fin, *maintenant*, run live) :**

| Invariant | Cible | Observation | Commande |
|---|---|---|---|
| pytest `runtime/tests` | vert | **653 passed, 1 skipped** (run J+8 fin, exit 0, 261 s) | `pytest runtime/tests` |
| commits Rust 24 h | 0 (D7) | **0** | `git log --since=2026-06-17 -- native/world-engine/crates` |
| commits Python 24 h | ≥ 1 | **2** (C12 + C13) | `git log --since=2026-06-17 -- runtime/engine` |
| capacités cumul | ≥ 13 | **13** | memory `MEMORY.md` |
| `PY_TO_RUST` entrées | reste 15 (D8 par composition) | **15** (cf. `project_2026-06-18_*` — `*_outcrop.py` toujours hors glob pour C7→C13) | grep `test_geology_cross_language_contract.py` |
| `genesis-engine/genesis-engine/` orphelin | absent ou justifié | **toujours untracked** (`README.md`, `Makefile`, `runtime/`, `docs/`…) | `git status genesis-engine/` |
| `NEXT-LEVEL-AUDIT.md §0 post-ADR-0008` | présent | **absent** | header `Date : 2026-05-16` inchangé |
| `crates/` orphelin nouveau | aucun | **aucun** (`STATUS.md` toujours 23 crates) | `ls crates/` |

## 2. La règle D9 escaladée — l'opérateur unique « foyer + X » s'auto-renforce

Hier soir (J+7 §2) D9 était *confirmé* à 5 fire-based consécutives. Le
verrou-recommandation P0 (§7.A) demandait explicitement : **« gel C12 jusqu'à
ajout d'un opérateur non-thermique »**, avec 5 candidats orthogonaux nommés
(eau bouillante / fermentation / séchage solaire / levier / cryoclastie). Le
run J+8 a livré :

| Cap | Pattern | Opérateur principal | Réutilise du J+7 ? |
|---|---|---|---|
| C12 forced_draught | **feu C11** boosté par soufflet+charbon → ~1100–1400 °C | **toujours du foyer**, juste soufflé | OUI — `kiln_peak_temp_c` |
| C13 copper_smelting | minerai + **feu C12** → métal | **toujours du foyer** + 1ʳᵉ mutation | OUI — `fd.COPPER_SMELT_TEMP_C` |

→ **7/7 capacités sur 8 jours enchaînées sont fire-based** (C7–C13).
→ Le mémo de sprint C12 admet textuellement : « pendant de C11, pas une
transformation » et celui de C13 : « réutilise verbatim le seuil `fd.COPPER_SMELT_TEMP_C` ».
La chaîne mensonge-du-kaolin promise par C12 (firedness 0,64→0,86→1,00 sur
C9→C11→C12) est élégante, mais c'est *toujours la même équation*
`peak_temp_c × maturation × refractarité` au numérateur, paramétrée
différemment au dénominateur.

**Risque concret (re-formulé) :** le moteur expose désormais **13 verbes
Python**, mais seulement **6 primitives réellement orthogonales** (sentir /
voir / tâter / casser / boire / allumer). Toutes les capacités J+0→J+8
empilent sur le 6ᵉ (allumer), 7 fois de suite. À mesure que C14, C15 viendront
(bronze ? fer ?), l'arbre se déséquilibre et la combinatoire devient
**isomorphe** : la simulation aura beau exposer « cuire la calcite »,
« cuire l'argile », « cuire le silex », « cuire le minerai natif »…
toutes les transformations passent par *le même opérateur unique*. C'est
exactement le piège que le watchdog C9 (« ARYA — composable deterministic
world model ») mettait en garde de J+6.

**Note honnête (audit, pas user) :** C13 est *malgré tout* la meilleure cap
de la semaine au sens scientifique pur — c'est la première **mutation**
(`smelt_at` consomme `geo.mine_at`), le premier test au **sens FORT** du
« monde ne ment jamais », et la pré-condition de tout l'âge des métaux. Mais
ce mérite scientifique ne lève pas D9 ; il en augmente le coût de réparation
(plus on empile sur fire, plus le pivot vers un opérateur orthogonal demande
de refactor des SSOT empilées C11→C12→C13).

**Reco J+9 P0 (verrou réitéré, **non-négociable**) :** gel C14 **et**
choix explicite entre deux issues :

- **(a)** ouvrir le 7ᵉ opérateur orthogonal (un des 5 candidats J+7) — la
  cryoclastie reste la moins chère (Wave 50 frost weathering observer est
  déjà *écrit*, jamais *vu par un agent*).
- **(b)** ratifier la stratégie « feu d'abord, diversifier après bronze/fer »
  par un **ADR-0009** explicite. Un audit ne peut pas demander un verrou que
  la roadmap n'a pas. Si la roadmap *est* « foyer jusqu'à l'acier », alors
  D9 n'est pas une dette, c'est un design choice — mais il faut le **écrire**,
  pas le laisser implicite.

L'inaction n'est *plus* une troisième option : le coût de séparation
augmente strictement avec chaque cap fire-based supplémentaire.

## 3. La nouveauté qui *mérite* d'être saluée — la 1ʳᵉ mutation

C13 introduit `smelt_at(world, geo, x, y, ore_kg=1.0, roasted=False)` qui
est, à ma lecture, le **premier opérateur du moteur Python qui modifie l'état
du monde** (jusqu'ici tout était `perceive_*`/`inspect_*`/`oracle_*`). Le
mémo C13 le revendique comme tel : « `smelt_at` est le **seul point d'entrée
MUTANT** de l'arc C1→C13 ».

Conséquences architecturales (côté audit) :

1. **Le contrat « monde ne ment jamais » devient testable au sens fort.**
   Auparavant, tout test passait parce qu'on ne *touchait* jamais le monde.
   Maintenant on peut écrire un test du type :
   `assert smelt_at(...) == oracle_yield_for_site(...)`
   et **prouver** que la perception du joueur (C1 tell vert) correspond au
   résultat de l'action (bouton de Cu rendu). C'est la moitié manquante du
   contrat D5 (`test_geology_cross_language_contract.py`).
2. **Mais ça ouvre aussi le 1ᵉʳ vrai risque de divergence Python ↔ Rust.**
   `geo.mine_at` mute le monde côté Python ; la fonte côté Rust n'existe pas
   encore (PY_TO_RUST reste 15, hors glob `*_outcrop.py`). Si demain
   l'utilisateur réactive `cargo` (R-J4-2 différé J+33) et compile le pont,
   le Rust *ignorera* la consommation Python. C'est le 1ᵉʳ candidat **D10**
   (« divergence d'état mutant cross-langage »).
3. **Recommandation forte (R-J8-bis, non-bloquante) :** documenter dans
   `crates/STATUS.md` (ou un nouveau `crates/MUTATION-FRONTIER.md`) le fait
   que `smelt_at` est le *premier* mutateur Python, et que la roadmap doit
   décider si la métallurgie sera **portée** côté Rust ou **gelée** côté
   Python comme C7–C12 (ce serait le 8ᵉ étage du moratoire).

## 4. Les 3 petites fissures non-traitées de J+7 (3ᵉ jour consécutif)

### 4.1 Orphelin `genesis-engine/genesis-engine/` (§7.B du J+7)

`git status` au moment de cet audit :

```
?? genesis-engine/
```

Le dossier contient désormais 12 entrées top-level (`Makefile`,
`NEXT-SPRINT.md`, `PROJECT-STATUS.md`, `README.md`, `ROADMAP.md`,
`_diag2.log`, `_recovery.log`, `docs/`, `pyproject.toml`,
`pytest-cache-files-o071x6za`, `runtime/`, `scripts/`) — c'est désormais
manifestement un **clone partiel ou un mauvais cd** d'il y a plusieurs jours.
J+5 / J+6 / J+7 / J+8 : 4 audits successifs flaggent ce piège silencieux.
**Une commande** suffit : `rm -rf genesis-engine/`. **0 reco prise**.

### 4.2 `NEXT-LEVEL-AUDIT.md §0` (§7.C du J+7)

Header inchangé :

```
**Date :** 2026-05-16
**Périmètre :** workspace Rust `native/world-engine/` (15 crates)
```

État réel J+8 : **23 crates** (STATUS.md du J+6), ADR-0008 actif (frontière
Python/Rust tranchée), 4 violations P0 entre J+5 et J+8. Un §0 d'une page
suffirait. **3ᵉ jour, 0 ligne ajoutée.**

### 4.3 `err1.txt` et `err2.txt` à la racine (nouveau J+8)

`git status` montre maintenant **deux fichiers de logs d'erreur vides**
(`err1.txt`, `err2.txt`, datés 2026-06-01) qui n'ont jamais été nettoyés.
0 octet chacun. Probablement un essai shell raté. Coût de nettoyage :
`rm err1.txt err2.txt`. **Ajouté au passif du J+9.**

## 5. État des 6 axes de la mission planifiée (re-évaluation post-ADR-0008)

La mission planifiée demande explicitement un audit selon 6 axes. Voici l'état
au J+8, **réactualisé à la lumière de la réalité Python-pivot** (l'audit
original `NEXT-LEVEL-AUDIT.md` est rédigé pour un moteur Rust actif ; il n'est
pas faux, il est *daté*) :

| Axe | Demande mission | État réel J+8 | Δ depuis 2026-05-16 |
|---|---|---|---|
| **1. Réalisme géologique** (tectonique, érosion, SDF 3D caves) | Refactor tectonique Voronoi → drift réel ; érosion cross-chunk ; SDF | **Côté Rust :** gelé Wave 42 (stub Voronoi inchangé). **Côté Python :** énorme avance via C1/C4–C6/C13 + observateurs Waves 50/62/63 (frost / hypsometry / concavity). | 6 capacités Python ; 0 commit Rust |
| **2. Climat & météo dynamique** (atmosphère, précipitations, saisons) | Modèle atmosphérique, ombre pluviométrique, LOD climatique | **Statu quo total.** `climate/src/lib.rs:128-136` (vent 3-bandes hardcodé) inchangé. **0 capacité Python** ne touche au climat. R2 BLIND-SPOTS toujours ouverte (J+30+). | **0 mouvement** |
| **3. Écosystème vivant** (faune émergente, flore, chaîne alimentaire, ECS) | `ecosystem` reçoit un runtime ; benchmark Bevy/hecs/Legion | **Statu quo total.** `ecosystem/src/lib.rs` toujours « seeds-only ». 0 capacité Python ne touche flore/faune. | **0 mouvement** |
| **4. Performance extrême** (streaming async, GPU compute, 10 k entités @60 fps) | Wire GPU erosion, profile, monde infini | **Statu quo total.** `gpu` crate toujours **dormant** (STATUS.md J+6). 0 bench. 0 Rust commit J−27. | **0 mouvement** |
| **5. API agents IA** (déterminisme, snapshots, fog of war, actions monde) | API REST/IPC, snapshot/restore RL, écriture monde | **Énorme avance Python.** Pont Rust `terrain` live depuis J+0 (7ac4280). 13 verbes agent désormais exposés. C13 livre le **1ᵉʳ mutateur d'état** (`smelt_at`). Mais : `apply_pending` toujours stub côté `agent-api` (F5 du `NEXT-LEVEL-AUDIT`). | **+13 verbes Python**, 0 changement Rust |
| **6. Outils de développement** (éditeur biomes hot-reload, debug overlay, replay) | Hot-reload, overlay, replay | **Statu quo total.** `dashboard.html` inchangé J−45. ROADMAP/PROJECT-STATUS/NEXT-SPRINT toujours markdown plats. | **0 mouvement** |

**Lecture honnête :** 1 axe sur 6 progresse massivement (le 5), 1 axe sur 6
progresse partiellement et *seulement côté Python* (le 1), 4 axes sur 6
sont **strictement immobiles depuis 33 jours**. C'est le **R2 BLIND-SPOTS**
de l'audit du 2026-06-13 — toujours ouvert, mentionné J+5/J+6/J+7/J+8 sans
action.

## 6. Mini-bench (lecture-seule) — où le Python pivot tient, et où il craque

Mesures faites à l'instant (`pytest runtime/tests`, 261 s pour 653 tests) :

| Métrique | Valeur observée | Interprétation |
|---|---|---|
| Tests `runtime/tests/` | **74 fichiers .py** | +6 fichiers en 8 jours (cap C7→C13 + dérivés) |
| Lignes `runtime/engine/` | **171 fichiers .py** | corpus métier énorme, surtout perception + capacités |
| Durée pytest full | **261 s** | était ~180 s à J+0, +45 % en 8 jours, à surveiller |
| Capacités émergentes | **13** | 6 outcrop + 1 fire + 3 cuissons + 2 apparatus + 1 métallurgie |
| Verbes orthogonaux | **6** | sentir / voir / tâter / casser / boire / allumer |
| Verbes fire-based | **7** (C7–C13) | D9 escaladé |
| `PY_TO_RUST` couverture | **15 entrées** | inchangé J+6 (D8 par composition tient pour C7–C13) |

**Signal faible à 8 jours :** la durée pytest croît de ~30 s/semaine.
Extrapolé à 12 semaines (≈ 80 capacités) → 8 min de CI. Ce n'est pas encore
critique, mais c'est le 1ᵉʳ symptôme que la composition empilée monolithique
sans tagging (`@pytest.mark.slow`, `@pytest.mark.cap_smoke`) commence à
peser. **Reco J+9 P2 :** poser les marks pytest avant C14, pour qu'on puisse
sortir un set rapide « cap + invariants » et un set lourd « monde complet ».

## 7. Recos J+8 (4 items, priorisés)

### R-J8-1 (P0, **non-négociable**) — Gel ferme de C14 + décision écrite

Le verrou C12 du J+7 a été franchi sans débat. Réitérer le même verrou pour
C14 sans contrainte serait dénué de sens. Donc :

- **Gel ferme C14** jusqu'à l'un des deux livrables :
  - **(a)** un commit qui introduit un 7ᵉ opérateur orthogonal (cryoclastie
    recommandée — c'est la branche la moins chère car Wave 50 est déjà
    écrite). Un seul `runtime/engine/cryoclasty.py` + 1 sprint memo + 1
    smoke `p146` suffit ; il *ferme* aussi le R-J4-1 dette transparence
    (l'observer Wave 50 n'a jamais été *vu par un agent*).
  - **(b)** un commit qui dépose `adr/0009-fire-first-strategy.md` ratifiant
    explicitement la stratégie « foyer jusqu'à l'acier ». Si le user choisit
    cette branche, D9 cesse d'être un risque et devient un design choice
    documenté. Mais le doc doit dater le pivot vers la diversification (par
    exemple : « après cap métallurgie du fer, ouverture obligatoire d'un
    opérateur orthogonal »).

Si ni (a) ni (b) au soir J+9, **D9 sera escaladé R0** (au-dessus de P0,
risque architectural certifié) et l'audit J+10 le portera dans `STATUS.md`.

### R-J8-2 (P1, 1 commande shell) — Nettoyage de la racine

```bash
rm -rf genesis-engine/      # orphelin J−3
rm err1.txt err2.txt        # logs vides J−18
```

3 lignes, 4ᵉ jour de mention sans action. Devient embarrassant à partir du
J+9.

### R-J8-3 (P1, 5 minutes) — `NEXT-LEVEL-AUDIT.md §0`

Ajouter au sommet :

```markdown
> **§0 post-ADR-0008 (annoté 2026-06-XX).** Cet audit a été rédigé pour un
> moteur Rust *actif*. Depuis le 2026-06-15 (ADR-0008), le runtime/engine est
> Python et le workspace `crates/` est **gelé Wave 42** (oracle de contrat
> lecture-seule). Les sections 2/4 ci-dessous sont en stase ; l'axe 5
> (agent-API) est livré côté Python via 13 capacités émergentes C1–C13.
> Le périmètre réel est **23 crates** (cf. `crates/STATUS.md`), pas 15.
```

3ᵉ jour de mention sans action.

### R-J8-4 (P2) — Documenter la frontière mutation Python ↔ Rust

C13 a introduit le **1ᵉʳ mutateur d'état**. Le risque **D10** candidat est
posé : si demain le pont Rust est réactivé, `smelt_at` côté Python diverge
silencieusement de la lecture côté Rust. Une page (`crates/MUTATION-FRONTIER.md`
ou ajout à `STATUS.md`) suffit pour figer la décision « Python = mutation,
Rust = perception ». Coût : 30 minutes.

### R-J8-5 (P2) — Tagging pytest avant explosion

Avant C14 : poser `@pytest.mark.cap_smoke` sur les ~13 tests « cap + smoke »
et un `pytest -m cap_smoke` qui finit en <30 s. Le full reste à 4 min mais
sera utilisable en boucle interactive.

## 8. Métrique J+8 fin de journée

| Métrique | J+6 soir | J+7 soir | **J+8 soir** | Δ jour | Δ semaine |
|---|---|---|---|---|---|
| Commits Rust (`crates/`) | 0 | 0 | **0** | 0 | 0 |
| Commits Python `runtime/` | 2 (C8+C9) | 2 (C10+C11) | **2 (C12+C13)** | 0 | — |
| Tests pytest | 570 | 613 | **653 passed, 1 skip** (run live exit 0) | +40 | +117 (vs J+1) |
| Capacités émergentes (cumul) | 9 | 11 | **13** | +2 | +6 (vs J+2) |
| dont *transformations* | 2 (C8+C9) | 3 (+C10) | **4 (+C13)** | +1 | +4 |
| dont *apparatus* | 0 | 1 (C11) | **2 (+C12)** | +1 | +2 |
| dont *mutateurs* | 0 | 0 | **1 (C13 `smelt_at`)** | +1 | +1 |
| `PY_TO_RUST` (entrées) | 15 | 15 | **15** | 0 | 0 (composition × 7) |
| Items Phase A/B mergés | 2 / 0 | 2 / 0 | **2 / 0** | 0 | 0 |
| Stagnation A3/A4/A5 | J+32 | J+33 | **J+34** | +1 j | +7 j |
| Dettes transparence BLIND-SPOTS | 1 (R2) | 1 (R2) | **1 (R2)** | 0 | 0 |
| Risques D-series ouverts | D7 daté + D9 confirmé | D7 daté + D9 confirmé + D10 candidat | **D7 daté + D9 *escaladé* + D10 candidat** | 0 | +2 |
| Recos audit non-honorées (cumul) | 3 (J+6) | 3 (J+7) | **3 (J+8, **3ᵉ jour ouvertes**)** | 0 | +3 |
| Score global (memory) | ~80,0 % | ~80,0 % | **~80,1 %** (géologie 78→78 ; sociétés 77→78 plafond) | +0,1 | +0,6 |

## 9. Trois lignes pour conclure

> J+8 ferme la semaine à **13 capacités cumulées dont 7 fire-based
> consécutives** (C7–C13), **0 commit Rust depuis J−27**, **0 reco J+7
> honorée** (3ᵉ jour), et **C12 verrou P0 explicitement franchi**. La
> nouveauté qui *mérite* d'être saluée est C13 : 1ʳᵉ mutation du monde, 1ᵉʳ
> test au sens fort de « le monde ne ment jamais ». Mais 4 axes sur 6 de la
> mission planifiée sont strictement immobiles depuis 33 jours — la
> stagnation est devenue un **pattern documenté**, pas un accident. Le verrou
> C14 (recommandation R-J8-1) est désormais **non-négociable** : si J+9
> reproduit le pattern « verrou audit ignoré, +2 caps fire-based », D9 sera
> escaladé R0 et porté dans `STATUS.md` à charge d'auditeur humain.

---

**Fin du delta-audit J+8.** 0 fichier `proposals/*.rs` ajouté
(NEXT-LEVEL-AUDIT couvre déjà les 6 axes — voir §5 pour leur état J+8 réel),
0 dépendance ajoutée, 0 commit proposé, **0 capacité C14 recommandée tant
qu'un opérateur non-thermique n'est pas posé OU qu'un ADR-0009 ne ratifie
pas la stratégie « foyer d'abord » par écrit** (verrou D9 escaladé). Les 3
recos J+7 (a/b/c) sont **toutes encore ouvertes au 3ᵉ jour** ; cet audit
les re-formalise en 5 recos J+8 (R-J8-1 à R-J8-5).
