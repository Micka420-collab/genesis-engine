# Tâche planifiée 2026-06-25 (J+15) — run PRODUCTIF (pas un rapport à vide)

> **Type :** exécution (code livré + push), pas rapport pur.
> **Référence :** [`SCHEDULED-TASK-2026-06-24-delta.md`](SCHEDULED-TASK-2026-06-24-delta.md)
> (R-J14-1 P0) · [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Méthode :** veille-first → combo → backlog → code → push (routine v3.0).

---

## 0. ÉTAPE 0 — SYNTHÈSE VEILLE (obligatoire, avant code)

- **DÉCOUVERTE_1** — *Project SID / ALIFE 2026* (économies/sociétés émergentes à
  ~1000 agents, **sélection par utilité, sans planification centrale**) · couche
  **Agentic** · gain : **valide la frontière ADR-0009** (utility-based action selection
  déterministe) → confirme le câblage d'arc, **pas de pivot**.
- **DÉCOUVERTE_2** — *JaxLife / Emergence World* (simulateur open-ended, agents par
  utilité **sans LLM**) · couche **Agentic** · gain : compatible cargo-less + invariant
  sandboxing (ADR-0002) ; le « cerveau LLM » reste écarté.
- **DÉCOUVERTE_3** — Bevy / WGPU / ML-KEM-768 · couches **World/Platform** · **backlog**
  (Rust gelé ADR-0008 ; aucun endpoint réseau créé → PQC N/A ce jour).
- **CVE_ACTIVES :** aucune critique (numpy / PCG64 clean ; 0 surface réseau).
- **PAPER_DU_JOUR :** rien de *nouveau* directement applicable sous 7 j au-delà de la
  confirmation SID/JaxLife (déjà actée ADR-0009).

**COMBO_RETENU :** `utility-based action selection (SID/JaxLife)` × `C14 cryoclasty`
→ 3ᵉ tranche de consommation d'arc. Coût : ~1 session · complexité 2 · risque régression
**1** (inerte hors `install_cryoclasty`). Couche **Agentic**. **ADR requis : NON**
(ADR-0009 déjà acté ; 3ᵉ application du patron).

## 1. ÉTAPE 2 — AUDIT / PHASE

- **PHASE :** post-Phase-4 (émergence civilisationnelle), ère **cargo-less** (ADR-0008).
- **COUCHES_OPÉRATIONNELLES :** Substrate (C1→C20), Agentic (boucle perceive→decide→act→
  remember + 3 capacités branchées), World (Python actif ; Rust gelé).
- **P0_BLOQUANTS :** D12/R0 (arc sans consommateur) — **en cours de fermeture** (3/20).
- **TÂCHE_JOUR :** R-J14-1 (P0) — câbler une 3ᵉ capacité. **IMPACTÉ_PAR_VEILLE : OUI**
  (combo fusionné : C14 GATHER via le patron SID/JaxLife).

## 2. CE QUI A ÉTÉ LIVRÉ (push `main`)

**D12 wire #3 — `ActionKind.GATHER` consomme C14 cryoclasty.** Voir le sprint doc
[`docs/sprints/2026-06-25_D12-WIRE-C14-frost-clast-gather.md`](../../docs/sprints/2026-06-25_D12-WIRE-C14-frost-clast-gather.md).

- 3ᵉ capacité branchée (C3 DRINK → C2 KNAP → **C14 GATHER**), **opérateur orthogonal**
  (ramasser), **non-feu** (D9 reste 0), tranchant ∝ `clast_quality` réelle (mensonge #5).
- Garde-fous : D8 (`PY_TO_RUST` reste 15), D10 (surface → gelé), zéro-régression par
  construction (`bootstrap` n'installe pas C14).
- Vérif : pytest **845** passed / 1 skip ; `ruff` clean ; **p155 8/8** ; non-régression
  live p153/p146/p154/p86. Portail smoke CI p154 → **p155**.

## 3. RECOMMANDATIONS — R-J15-x

- **R-J15-1 (P0) — Gater la routine d'audit** (= R-J12-1 / R-J13-7 / R-J14-2, ouverte
  depuis J+12). Ce run a été **productif** (R-J14-1 fermée), mais la routine tire toujours
  un prompt orienté « Code Rust » obsolète (ADR-0008). Choix : (a) condition « ≥1 commit
  depuis le dernier `AUDIT-DELTA-*` » ; (b) réécrire le prompt vers « lire le dernier
  audit-delta + livrer une tranche verticale ».
- **R-J15-2 (P1) — Brancher une 4ᵉ capacité** (même patron). Candidat naturel **non-feu** :
  C18 `ochre_grinding` (broyer → pigment ; amorce le pilier **symbolique**) ou C15
  `salt_evaporation` (récolter). Garder l'alternance feu/non-feu.
- **R-J15-3 (P1) — Moitié hydro de D11** (rivières peintes → transport de débit
  inter-chunks). Inchangé depuis R-J14-3.

## 4. Verdict

| Question scheduled-task | Réponse J+15 |
|---|---|
| Améliorations à signaler ? | **Oui — R-J14-1 (P0) fermée : 3ᵉ capacité branchée (D12 3/20).** |
| Faut-il écrire du Rust ? | **Non** (ADR-0008 + env cargo-less inchangés). |
| La routine est-elle utile aujourd'hui ? | **Oui** (run productif) mais **toujours pas gatée** → R-J15-1 (P0). |
| Push effectué ? | **Oui — `main`** (code + tests + smoke + docs). |

---

## 5. RUN #2 (J+15, même journée) — R-J15-3 (P1) FERMÉE : moitié hydro de D11

> **Type :** exécution (code livré + push). Routine `world-realism-system-v2.0`
> (axe **Substrate / Eau & Hydrologie**), tirée une 2ᵉ fois le même jour.
> **Veille-first** → combo → code → push respecté.

**Veille :** combo `LTI river routing (Hascoet et al. 2026, JGR-ML)` × `bilan runoff
Budyko (Collignan 2025, WRR)` × `discharge_observer` existant. **Aucun pivot** : le
papier du jour **valide** le solveur LTI CPU déjà présent (la variante GPU/conv
différentiable reste backlog, Rust gelé ADR-0008). CVE : aucune critique.

**Livré — Wave 64 `river_discharge` : couplage de débit de rivière vivant.** Ferme le
« **Reste** » explicite du sprint orographique d'hier (la **moitié hydro** de D11) et
**R-J15-3**. Voir [`docs/sprints/2026-06-25_D11-river-discharge-coupling.md`](../../docs/sprints/2026-06-25_D11-river-discharge-coupling.md).

- Pendant **exact** du couplage orographique : relit le même `elevation_m` vivant →
  canal **température/ET** (SSOT `runoff_field_m3s`) → routage **LTI mass-conservatif**
  (SSOT `route_runoff`) → met à l'échelle la rivière peinte par le débit du bassin.
  Uplift refroidit→**gonfle** (×1,41) ; érosion réchauffe→**rétrécit** (×0,43) /
  **tarit** (×0, oued émergent). Ferme l'observer-treadmill de `discharge_observer`.
- Garde-fous : **no-op strict** sur monde statique (0 régression), read-only macro
  (D10 gelé), `PY_TO_RUST` **inchangé** = 15 (D8), 0 RNG, réversible, **mass-conservatif**
  (résidu 1e-16). Optionnel via `ALL_MODULES` (hors `_DEFAULT_MODULES`, comme `climate_biome`).
- Vérif : pytest **vert** ; `ruff` clean ; **p156 9/9** ; non-régression p47/p49/p52/p122/
  p154/p155/p82. Portail smoke CI **p155 → p156**.

**Recos restantes (R-J15-x) :** R-J15-1 (P0, gater la routine d'audit) **toujours
ouverte**. R-J15-2 (brancher une 4ᵉ capacité agent) toujours ouverte. Nouveau : R-J15-4
— promouvoir `climate_biome` **et** `river_discharge` dans le set runtime par défaut
(les deux moitiés de D11 sont prêtes mais restent optionnelles).
