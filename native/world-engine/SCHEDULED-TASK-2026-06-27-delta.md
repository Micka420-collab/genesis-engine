# Tâche planifiée 2026-06-27 (J+17) — run PRODUCTIF (code livré + push)

> **Type :** exécution (code + tests + smoke + docs + push), pas rapport pur.
> **Référence :** [`SCHEDULED-TASK-2026-06-25-delta.md`](SCHEDULED-TASK-2026-06-25-delta.md)
> (R-J15-2) · [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Méthode :** veille-first → combo → backlog → code → push (routine v3.0).
> **Sprint doc :** [`docs/sprints/2026-06-27_D12-WIRE-C18-ochre-grinding.md`](../../docs/sprints/2026-06-27_D12-WIRE-C18-ochre-grinding.md).

---

## 0. ÉTAPE 0 — SYNTHÈSE VEILLE (obligatoire, avant code)

- **DÉCOUVERTE_1** — *AIvilization v0* (arXiv 2602.10429 ; architecture d'agent unifiée +
  profils adaptatifs, simulation sociale à grande échelle) · couche **Agentic** · gain :
  **valide la frontière ADR-0009** (spécialisation émergente par utilité, sans direction
  explicite) → confirme le câblage d'arc, **pas de pivot**.
- **DÉCOUVERTE_2** — *Project Sid / PIANO* + *TerraLingua* (open-endedness en écologies
  d'agents) · couche **Agentic** · gain : confirment l'émergence comme **processus**, pas
  script — exactement le patron `perceive→decide→act→remember`.
- **DÉCOUVERTE_3** — *JaxLife / Emergence World* (utility-based action selection **sans
  LLM**) · couche **Agentic** · gain : compatible cargo-less + sandboxing (ADR-0002) ; le
  « cerveau LLM décisionnel » reste écarté. Bevy/WGPU/ML-KEM → **backlog** (Rust gelé
  ADR-0008 ; aucun endpoint réseau → PQC N/A ce jour).
- **CVE_ACTIVES :** aucune critique (numpy / PCG64 clean ; 0 surface réseau).
- **PAPER_DU_JOUR :** rien de *nouveau* directement applicable sous 7 j au-delà de la
  confirmation SID/AIvilization/JaxLife (déjà actée ADR-0009).

**COMBO_RETENU :** `utility-based action selection (SID/AIvilization/JaxLife)` × `C18
ochre_grinding` → 4ᵉ tranche de consommation d'arc, **1ʳᵉ sur le pilier symbolique**.
Coût : ~1 session · complexité 2 · risque régression **1** (inerte hors
`install_ochre_grinding`). Couche **Agentic**. **ADR requis : NON** (ADR-0009, 4ᵉ
application du patron).

## 1. ÉTAPE 2 — AUDIT / PHASE

- **PHASE :** post-Phase-4 (émergence civilisationnelle), ère **cargo-less** (ADR-0008).
- **COUCHES_OPÉRATIONNELLES :** Substrate (C1→C20), Agentic (boucle perceive→decide→act→
  remember + **4** capacités branchées), World (Python actif ; Rust gelé).
- **P0_BLOQUANTS :** D12/R0 (arc sans consommateur) — **en cours de fermeture** (4/20).
- **TÂCHE_JOUR :** R-J15-2 — câbler une 4ᵉ capacité, amorçant un pilier immobile.
  **IMPACTÉ_PAR_VEILLE : OUI** (combo fusionné : C18 GRIND via le patron SID/JaxLife).

## 2. CE QUI A ÉTÉ LIVRÉ (push `main`)

**D12 wire #4 — `ActionKind.GRIND` consomme C18 ochre_grinding.**

- 4ᵉ capacité branchée (C3 DRINK → C2 KNAP → C14 GATHER → **C18 GRIND**), **opérateur
  orthogonal** (broyer), **inventaire dédié** `inv_pigment`, **non-feu**. **1ʳᵉ
  consommation agent du pilier SYMBOLIQUE** (immobile depuis J0) : le pigment est le
  substrat de la future marque.
- Pigment ∝ `pigment_quality` réelle ; mensonge #9 (le chapeau rouille ment au peintre :
  oxyde hématite/magnétite → peint ; pyrite/plomb-zinc → ne peint pas ; rouille ≠ rouge).
- Garde-fous : D8 (`PY_TO_RUST` reste 15, pas de `_PROFILE`), D10 (surface → gelé, pas de
  `mine_at` dans la branche GRIND), D9 (non-feu), zéro-régression par construction
  (`bootstrap` n'installe pas C18). Nouveau champ `inv_pigment` ajouté aux listes de
  migration/persistance (chargement défensif → anciennes sauvegardes compatibles), exclu
  de `_INVENTORY_MASS_FIELDS` (comme `inv_tools`).
- Vérif : pytest **vert** (1 skipped) ; `ruff` clean (arc + `test_ochre_grinding_loop.py`,
  glob `p15[0-8]`) ; **p158 8/8** ; non-régression live p153 (KNAP) / p155 (GATHER) / p150
  (C18) / p146 / p86. Portail smoke CI p157 → **p158**.

## 3. RECOMMANDATIONS — R-J17-x

- **R-J17-1 (P0) — Gater la routine d'audit** (= R-J12-1 / R-J13-7 / R-J14-2 / R-J15-1,
  ouverte depuis J+12). Ce run est **productif** (R-J15-2 fermée), mais la routine tire
  toujours un prompt orienté « Code Rust » obsolète (ADR-0008). Choix : (a) condition
  « ≥1 commit depuis le dernier `AUDIT-DELTA-*` » ; (b) réécrire le prompt vers « lire le
  dernier delta + livrer une tranche verticale ».
- **R-J17-2 (P1) — Brancher le GESTE symbolique** : un verbe `MARK`/`PAINT` qui consomme
  `inv_pigment` (C18) sur une paroi calcaire durable (`rock_canvas` C20) → ferme la boucle
  pigment→support→dessin. Émergent : *de quoi* et *où*, jamais *quoi* dessiner. Ce serait
  la **2ᵉ brique vivante du pilier symbolique** et la 5ᵉ bouchée de D12.
- **R-J17-3 (P1) — Brancher une capacité-feu** pour rétablir l'alternance D9 (4 wires
  non-feu d'affilée). Candidat : C7 fire_ignition ou C13 copper_smelting (consommateur de
  `inv_stone`/minerai). 
- **R-J17-4 (P2) — Promouvoir `climate_biome` + `river_discharge`** dans le set runtime par
  défaut (R-J15-4, inchangée : les deux moitiés de D11 sont prêtes mais optionnelles).

## 4. Verdict

| Question scheduled-task | Réponse J+17 |
|---|---|
| Améliorations à signaler ? | **Oui — R-J15-2 fermée : 4ᵉ capacité branchée (D12 4/20), pilier symbolique amorcé.** |
| Faut-il écrire du Rust ? | **Non** (ADR-0008 + env cargo-less inchangés). |
| La routine est-elle utile aujourd'hui ? | **Oui** (run productif) mais **toujours pas gatée** → R-J17-1 (P0). |
| Push effectué ? | **Oui — `main`** (code + tests + smoke + docs). |
