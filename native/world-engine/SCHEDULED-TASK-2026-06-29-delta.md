# Tâche planifiée 2026-06-29 (J+19) — run PRODUCTIF (code livré + push)

> **Type :** exécution (code + tests + smoke + docs + push), pas rapport pur.
> **Référence :** [`WORLD_VEILLE_REPORT-2026-06-28.md`](WORLD_VEILLE_REPORT-2026-06-28.md) ·
> [ADR-0009](../../adr/0009-agent-consumer-loop.md).
> **Méthode :** veille-first → combo → backlog → code → push (routine v3.0).
> **Sprint doc :** [`docs/sprints/2026-06-29_D12-WIRE-C8-lithic-tempering.md`](../../docs/sprints/2026-06-29_D12-WIRE-C8-lithic-tempering.md).
> **Session :** lancée par l'utilisateur (« analyse, point d'avancement, développe le reste,
> améliore toute la journée par battements de cœur horaires »).

---

## 0. ÉTAPE 0 — SYNTHÈSE VEILLE (obligatoire, avant code)

- **DÉCOUVERTE_1** — *ALIFE 2026* (« la vie = processus émergent à travers les échelles ») +
  *emergent tool use from multi-agent autocurricula* · couche **Agentic** · gain : **valide la
  frontière ADR-0009** (la techno doit être *vécue*, pas prouvée possible) → confirme le câblage
  d'arc, **pas de pivot**.
- **DÉCOUVERTE_2** — *Project Sid / JaxLife / AIvilization* (utility-based action selection **sans
  LLM**, spécialisation émergente) · couche **Agentic** · gain : confortent le patron
  `perceive→decide→act→remember`. Compatible cargo-less + sandboxing (ADR-0002).
- **CVE_ACTIVES :** aucune critique (numpy / PCG64 clean ; 0 surface réseau créée ce jour).
- **PAPER_DU_JOUR :** rien de *nouveau* directement intégrable sous 7 j au-delà de la confirmation
  SID/JaxLife (déjà actée ADR-0009). Bevy/WGPU/ML-KEM → backlog (Rust gelé ADR-0008).

**COMBO_RETENU :** `utility-based action selection` × `C8 lithic_tempering` → 7ᵉ tranche de
consommation d'arc, **premier consommateur en aval du feu** (C7, la VOÛTE câblée le 28-06). Coût :
~1 session · complexité 2 · risque régression **1** (inerte hors `install_lithic_tempering`).
Couche **Agentic**. **ADR requis : NON** (ADR-0009, 7ᵉ application du patron).

## 1. ÉTAPE 2 — AUDIT / PHASE

- **PHASE :** post-Phase-4 (émergence civilisationnelle), ère **cargo-less** (ADR-0008).
- **COUCHES_OPÉRATIONNELLES :** Substrate (C1→C20), Agentic (boucle perceive→decide→act→remember
  + **7** capacités branchées), World (Python actif ; Rust gelé).
- **P0_BLOQUANTS :** D12/R0 (arc sans consommateur) — **en cours de fermeture** (7/20).
- **TÂCHE_JOUR :** câbler une 7ᵉ capacité, le premier étage de la VOÛTE (le feu sert enfin de
  *moyen*). **IMPACTÉ_PAR_VEILLE : OUI** (combo fusionné : C8 TEMPER via le patron SID/JaxLife).

## 2. CE QUI A ÉTÉ LIVRÉ (push `main`)

**D12 wire #7 — `ActionKind.TEMPER` consomme C8 lithic_tempering.**

- 7ᵉ capacité branchée (C3 DRINK → C2 KNAP → C14 GATHER → C18 GRIND → C20 MARK → C7 IGNITE →
  **C8 TEMPER**). **Premier consommateur EN AVAL du feu** : le feu cesse d'être seulement une fin
  (se réchauffer) et devient un **moyen** (traiter la pierre). Referme la boucle entre les deux
  capacités les plus établies : KNAP (pierre) × IGNITE (feu) → TEMPER (meilleur tranchant).
- Dépendance au feu **honorée, pas scriptée** : gate sur `has_made_fire` — un agent qui n'a jamais
  fait de feu ne trempe pas (c'est le monde, pas un arbre tech, qui l'en empêche).
- **Réutilise `inv_tools`** (aucun nouveau champ `AgentRegistry`) → **aucune migration de
  persistance**, risque minimal. Nouvel état : `ActionKind.TEMPER=24`,
  `EpisodicMemory.{known_temper_locations, has_tempered_stone, last_temper_gain}`.
- Mensonge #12 (l'obsidienne, meilleure pierre brute, ne gagne RIEN au feu — déjà du verre ;
  chert Δ≈0,20 > quartzite Δ≈0,12 ; tous émergent de la pétrologie réelle).
- Garde-fous : D8 (`PY_TO_RUST` reste 15, compose C2×C7, pas de `_PROFILE`), D10 (pas de `mine_at`
  dans la branche TEMPER), zéro-régression par construction (`bootstrap` n'installe pas C8).
- Vérif : pytest **vert** (set de l'arc, +14 tests) ; `ruff` clean (fichiers neufs) ; **p162 9/9**
  (dont l'**arc vécu KNAP→IGNITE→TEMPER** sur un seul site). Portail smoke CI p161 → **p162**.

## 3. RECOMMANDATIONS — R-J19-x

- **R-J19-1 (P1) — 8ᵉ bouchée : un précurseur du feu pour rétablir l'alternance.** Après IGNITE
  (C7) + TEMPER (C8), deux câblages « feu » d'affilée. Candidat naturel : **C4
  `combustible_outcrop`** (ramasser du combustible — non-feu, nourrit le foyer) ou **C5/C6**
  (`clay_outcrop` / `limestone_outcrop`, les matières que le feu transformera ensuite), avant les
  transformations à deux ingrédients (C9 cuisson argile, C10 chaux, C13 fonte cuivre).
- **R-J19-2 (P1) — Chaîne pyrotechnologique à deux ingrédients.** Une fois C5/C6 perçus *et* C8
  vécu, brancher C9 `ceramic_firing` (argile + feu) puis C10 `lime_burning` (calcaire + feu) :
  même patron, mais le gate combine deux capacités installées. Premier pas vers la **fonte** (C13).
- **R-J19-3 (P2) — Registre de capacités + budget de perception.** `decide()` est sur le chemin
  chaud ; 7 lectures de capacités y vivent désormais (gate + mémoïsées, mais la dette ADR-0009
  §Conséquences se rapproche du seuil « quelques branchements »). Préparer un dispatch ordonné de
  wrappers + un budget de perception avant la 10ᵉ bouchée.
- **R-J19-4 (P2) — Promouvoir `climate_biome` + `river_discharge`** dans le set runtime par défaut
  (R-J15-4 / R-J17-4, inchangée).

## 4. Verdict

| Question scheduled-task | Réponse J+19 |
|---|---|
| Améliorations à signaler ? | **Oui — 7ᵉ capacité branchée (D12 7/20) : le feu a son premier étage (trempe).** |
| Faut-il écrire du Rust ? | **Non** (ADR-0008 + env cargo-less inchangés). |
| Push effectué ? | **Oui — `main`** (code + tests + smoke + docs). |
| Prochaine bouchée ? | **R-J19-1** : un précurseur non-feu (C4/C5/C6) pour l'alternance, puis les transformations à deux ingrédients (C9/C10/C13). |
