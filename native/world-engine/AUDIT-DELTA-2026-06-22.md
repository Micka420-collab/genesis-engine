# Genesis World Engine — Delta-Audit 2026-06-22 (J+12, run capacité)

**Mode :** scheduled task `continue-la-creation-de-genesis-engine` (routine
veille-first), run **automatique**, user **absent**.
**Successeur de** [`AUDIT-DELTA-2026-06-19-run2.md`](./AUDIT-DELTA-2026-06-19-run2.md)
(J+9 run #2 ; Cap. C15 `salt_evaporation`).
**Companion du jour :** [`AUDIT-DELTA-2026-06-22-meta.md`](./AUDIT-DELTA-2026-06-22-meta.md)
— audit *méta/hygiène* produit le matin même par une **tâche programmée sœur**
(`analyse-le-projet…`) qui a délibérément **ne rien shippé** et capturé 3 signaux du
gap de 3 jours (silence, dérive FAIR, `Cargo.lock` untracked). Ce delta-ci est le
**run capacité** : il livre **Cap. C16 `food_curing`** et résout 2 des 3 signaux.
**Contrainte env :** `cargo` absent ([ADR-0008](../../adr/0008-python-rust-frontier.md),
D7). Affirmations Rust = lecture-seule ; CI = vérité.

---

## 0. Verdict express

> **J+12 a EXÉCUTÉ la reco `R-J9r2-3 (a)`.** La Cap. **C16 `food_curing`**
> (salaison) est la **1ʳᵉ capacité qui CONSOMME le PRODUIT d'une capacité
> précédente** — le **sel** de C15. C15 avait rendu le sel *récoltable* ; C16
> expose la **vérité physique** de son usage fondateur : saler **arrête la
> pourriture microbienne** (abaissement de l'activité de l'eau a_w par osmose) →
> réserve → surplus → sédentarité → commerce (« or blanc »). **3ᵉ capacité
> non-fire consécutive** (C14 *ramasser*, C15 *sécher au soleil*, C16 *saler*) :
> l'alternance anti-treadmill **tient**, la chaîne fire-based (D9) **reste à 0**.
> C16 fait avancer l'**axe 3 (écosystème vivant / alimentation)**, immobile depuis
> J+0. Non-mutant (preview) → **D10 reste gelé**. Veille J+12 : **0 combo externe
> intégrable** (tous gated) ; 1 signal neuf cargo-less = **DST** → backlog devtools.

## 0bis. ⚠ Collision de concurrence détectée (CONCURRENT_AGENT)

Pendant ce run (~11:12–11:18), une **autre exécution autonome parallèle** a écrit
sur disque, **non commitée**, une capacité **différente** revendiquant *aussi*
« Cap. C16 » et le numéro de smoke « p148 » :

| Fichier | Auteur | Numéro revendiqué | État |
|---|---|---|---|
| `runtime/engine/food_curing.py` (+ test + `p148_food_curing_smoke.py`) | **ce run** | C16 / p148 | **complet, vérifié** (737 verts, smoke 8/8, ruff clean) |
| `runtime/engine/iron_bloomery.py` (+ test + `p148_iron_bloomery_smoke.py`) | run parallèle | C16 / p148 | **untracked, non vérifié par moi**, encore en écriture à 11:18 |

`iron_bloomery` est le **bas-fourneau du fer** (5ᵉ transformation, 2ᵉ métallurgie,
**mutant** → ouvre `MUTATION-FRONTIER.md`/D10) — un jalon plus lourd et *fire-based*
(redémarre D9). C'est précisément le candidat que `R-J9r2-1` anticipait (« la
prochaine **peut** être fire-based »). Décision de **ce run**, sans pouvoir
coordonner l'agent parallèle :

1. **Shipper la capacité vérifiée** (`food_curing`) comme **C16/p148** : elle est
   complète, testée, ruff-clean, et ne mute rien (risque nul).
2. **Ne PAS committer** `iron_bloomery` ni ses fichiers `p148_iron_bloomery_*` :
   c'est le travail in-flight d'un autre agent, **non vérifié** par moi ; committer
   du code tiers incomplet sous mon push serait incorrect. Ils restent **untracked**.
3. **Recommandation pour l'auteur de `iron_bloomery`** (R-J12-3 ci-dessous) :
   renuméroter en **C17 / p149** au rebase (C16/p148 seront pris par `food_curing`),
   ce qui donne une **séquence cohérente** : C16 salaison (non-fire) → C17 fer
   (fire-based, rouvre D9), parfaitement aligné sur `R-J9r2-1`.

| Reco J+9 run #2 | Statut J+12 | Vérif |
|---|---|---|
| **R-J9r2-1** (P1) le feu débloqué par l'alternance | ⏸️ **non consommé ici** | C16=non-fire renforce l'alternance ; le fer (run parallèle) le consommerait en C17 |
| **R-J9r2-2** (P2) doc frontière mutation à la 2ᵉ mutation | ⏸️ **non déclenchée par C16** | `food_curing` non-mutant ; *le fer concurrent* serait la 2ᵉ mutation (→ MUTATION-FRONTIER) |
| **R-J9r2-3 (a)** (P2) conservation = salaison | ✅ **EXÉCUTÉ** | `food_curing.py` + smoke `p148` 8/8 + 26 tests |
| **R-J9r2-3 (b)** (P2) commerce du sel | ⏸️ **backlog** (candidat C18) | compose C16 surplus × `trade_exchange` |
| **R-J9r2-4** (P3) axes immobiles | 🟡 **axe 3 entamé** | C16 = 1ʳᵉ lecture agent de la conservation alimentaire |

Résout aussi, depuis le companion meta-audit :
- **R-J12-2 (meta)** dérive FAIR JSON → **revertée** (`git checkout`), timestamps
  remis à l'état committé (métriques byte-identiques, c'était du bruit).
- **R-J12-3 (meta)** `Cargo.lock` untracked → **laissé à l'utilisateur** (décision
  architecturale ADR-0008 : commit vs `.gitignore` — hard-to-reverse, hors scope
  d'un commit de capacité ; non stagé).
- **R-J12-1 (meta)** cadence de la routine → **décision utilisateur** (je n'altère
  pas une tâche programmée sans OK explicite).

---

## 1. ÉTAPE 0 — Veille technologique (avant tout code)

Détail : [`docs/veille/2026-06-22_VEILLE_food_curing.md`](../../docs/veille/2026-06-22_VEILLE_food_curing.md).

- **DÉCOUVERTE_1 :** *Deterministic Simulation Testing* (QCon London + FOSDEM
  2026) — harnais seed-reproductible + injection de fautes ; **calque** de la
  discipline déterminisme/seed de Genesis. **→ BACKLOG cargo-less** (mode DST de
  `runtime/experiments/run_all.py`, ~4 h ; ROADMAP P5).
- **DÉCOUVERTE_2 :** *Bevy 0.18* (mars 2026). **→ BACKLOG** (gated `cargo`).
  ROADMAP mis à jour 0.16 → **0.18**.
- **DÉCOUVERTE_3 :** multi-agent civ (Project Sid / AgentSociety / AIvilization).
  **→ BACKLOG** (gated LLM tier-2).
- **CVE_ACTIVES :** `CVE-2026-22705` (ML-DSA timing, medium, **patchée**) — aucune
  surface live (PQC non compilée). Aucune critique.
- **PAPER_DU_JOUR :** rien d'applicable sous 7 j.

## 2. ÉTAPE 1 — Moteur de combinaison (COMBO-GENESIS)

- **COMBO_RETENU : aucun combo *externe* intégrable** (cargo / LLM tier-2 gated).
- **COMBO_INTERNE retenu :** `salt_evaporation` (C15 — le **produit** sel) **×**
  alimentation/physiologie **×** le champ macro de température (climat). C15 a livré
  une *ressource* ; C16 la **consomme** pour la 1ʳᵉ fois → conservation émergente,
  sans nouveau tell.
- **COMBO_BACKLOG :** DST → harnais `run_all.py` (ROADMAP P5).

## 3. Ce que C16 livre

| Dimension | Avant J+12 (C15) | Après J+12 (C16) |
|---|---|---|
| Capacités émergentes (cumul) | 15 | **16** |
| dont *fire-based* | 7 (chaîne rompue) | **7** (D9 reste à 0) |
| Capacités non-fire consécutives | 2 (C14, C15) | **3** (C14, C15, C16) |
| 1ʳᵉ consommation du **produit** d'une capacité | non | **oui** (le sel de C15) |
| `PY_TO_RUST` | 15 | **15** (D8 par composition, **10ᵉ**) |
| Mutation d'état (D10) | gelée | **gelée** (preview) |
| Axe 3 (écosystème vivant) | **immobile** | **entamé** |

**Le design** (émergence absolue, déterministe, « le monde ne ment jamais ») :

- L'agent ne *sait* pas que le sel conserve. Il **observe** que la chair fraîche
  (appétissante) pourrit en jours, la chair salée (terne) tient des mois.
- **Physique a_w** : le sel abaisse l'activité de l'eau par osmose, **plancher
  0,75** (saumure NaCl saturée, fait FIPS d'hygrométrie) ; croissance microbienne
  ∝ `((a_w−0,60)/(0,99−0,60))^5 × Q10^((T−25)/10)` (Q10 = 2,5) ; `shelf_life =
  SHELF_BASE / croissance`. Viande maigre fraîche à 25 °C → ~1,5 j ; salée à
  saturation (≈ 0,27 kg sel/kg) → **~181 j** (dynamique réelle ~100×).
- **Composition C15 dure** : sans marais salant à portée → dose **0** → l'aliment
  reste **frais/périssable** (réciproque honnête). SALAR riche → saturation.
- **Mensonge rendu visible #7** : l'aliment **le plus appétissant** (frais) est le
  **plus périssable** ; « frais = meilleur » est le mensonge. **Compromis** :
  `palatability`/`nutrient_retention` baissent avec la dose → l'agent **arbitre**.
- **Réutilise la lecture climat de C15** (`se._resolve_anchor`/`se._climate_at`) —
  une implémentation, **zéro dérive** (SSOT).
- **Invariant prouvé** sur monde Genesis réel (seed `0x5A17`, même côte aride que
  C15, ancrage déterministe argmax-aridité **sans injection**) : **144/144 marais
  salants permettent la conservation** (best_shelf ~214 j, classe CURED), 0
  violation. smoke `p148` **8/8**, **26 tests**, ruff clean.

## 4. État des 6 axes (J+12)

| Axe | État réel | Δ depuis J+9 r#2 |
|---|---|---|
| 1. Réalisme géologique | inchangé | 0 |
| 2. Climat & météo | C16 relit la température macro (réutilise C15) | +0 |
| 3. **Écosystème vivant / alimentation** | **1ʳᵉ lecture agent de la conservation** | **+1 (entamé)** |
| 4. Performance | statu quo (`gpu` dormant, gated cargo) | 0 |
| 5. API agents IA | **+1 capacité** (salaison) ; 16 caps | **+1** |
| 6. Outils de dév | **DST identifié** (backlog) | 0 (signal posé) |

## 5. Métriques J+12

| Métrique | J+9 r#2 (C15) | **J+12 (C16)** | Δ |
|---|---|---|---|
| Commits Rust (`crates/`) | 0 | **0** | 0 |
| Commits Python `runtime/` | 1 | **1 (C16)** | — |
| Tests pytest (passed) | 688* | **737** | +26 net** |
| Capacités émergentes (cumul) | 15 | **16** | +1 |
| dont *fire-based* | 7 | **7** | 0 |
| Capacités non-fire consécutives | 2 | **3** | +1 |
| `PY_TO_RUST` | 15 | **15** | 0 |
| Mutation (D10) | gelée | **gelée** | 0 |
| 1ʳᵉ consommation d'un produit | non | **oui (sel C15)** | — |

\* Le « 688 » de la doc C15 précède des tests ajoutés dans le commit C15 lui-même.
Mesure J+12 : **711 passed / 1 skip avant C16**. **\*\*** Delta **propre à C16** =
**+26** (`test_food_curing.py`) → **737 passed / 1 skip après**.

## 6. Recos J+12 (pour J+13)

### R-J12-1 (P1) — Coordination multi-agent : éviter la double-numérotation
Deux runs autonomes ont produit deux « C16 » le même jour. **Reco process :** avant
de choisir un numéro de capacité, un run devrait `git status`/`ls runtime/engine`
pour détecter une capacité in-flight non commitée et prendre le **numéro suivant
libre**. À défaut de coordination, le second *pusher* rebase et renumérote (cf. 0bis).

### R-J12-2 (P1) — `iron_bloomery` (run parallèle) : finir + renuméroter C17/p149
Le bas-fourneau du fer est un vrai jalon (2ᵉ métallurgie, **2ᵉ mutation** → ouvre
`MUTATION-FRONTIER.md`, D10). Son auteur doit : (a) vérifier sa suite verte ;
(b) renuméroter **C16→C17**, **p148→p149** ; (c) au commit, ce sera le **1ᵉʳ retour
fire-based** depuis C13 → **D9 redémarre à 1** (prévoir un opérateur orthogonal
ensuite, cf. `R-J9r2-1`).

### R-J12-3 (P2) — `Cargo.lock` untracked + cadence routine = décisions utilisateur
Hérité du meta-audit (R-J12-1/-3). Le lockfile (commit vs `.gitignore`) et
l'espacement de la routine sont **hard-to-reverse / hors scope capacité** : laissés
à l'arbitrage explicite de l'utilisateur. La dérive FAIR JSON, elle, a été
**revertée** ce run (bruit de timestamp).

### R-J12-4 (P2) — Séchage solaire de la chair (charqui) ferme C15×C16
C16 plafonne a_w à 0,75 (sel seul). En climat aride (champ déjà lu par C15), la
chair **sèche** → a_w plus bas (charqui/biltong). Une extension
`cure_food_at(..., solar_dry=True)` composerait C16 × l'aridité de C15 sans nouveau
tell. Backlog.

### R-J12-5 (P3) — DST : promouvoir à la 1ʳᵉ flakiness
Seul combo cargo-less identifié à la veille, le plus aligné sur la discipline. Dort
en backlog tant que la suite reste verte/déterministe ; promouvoir (mode DST de
`run_all.py`) dès une divergence seed-à-seed.

---

**Fin du delta-audit J+12 (run capacité).** Reco `R-J9r2-3 (a)` **exécutée**
(salaison = 1ʳᵉ consommation du produit C15) ; alternance anti-treadmill
**renforcée** (3 non-fire, D9 reste à 0) ; **axe 3 entamé** ; D10 **gelé**.
Collision de concurrence avec un `iron_bloomery` parallèle **documentée et
non-destructive** (laissé untracked pour son auteur → C17/p149). 1 commit Python
(C16), 0 commit Rust. Veille → 0 combo externe (tous gated) ; combo interne C15 ×
climat a porté le run.
