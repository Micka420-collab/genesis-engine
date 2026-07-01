# Tâche planifiée 2026-07-01 (J+21) — run PRODUCTIF (code livré + push)

> **Type :** exécution (code + tests + smoke + docs + push), pas rapport pur.
> **Référence :** [`WORLD_VEILLE_REPORT-2026-06-28.md`](WORLD_VEILLE_REPORT-2026-06-28.md) ·
> [ADR-0009](../../adr/0009-agent-consumer-loop.md) · [ADR-0010](../../adr/0010-agent-driven-mutation.md).
> **Méthode :** veille-first → combo → backlog → code → push (routine « battement de cœur de câblage d'arc »).
> **Sprint doc :** [`docs/sprints/2026-07-01_D12-WIRE-C17-iron-bloomery.md`](../../docs/sprints/2026-07-01_D12-WIRE-C17-iron-bloomery.md).

---

## 0. ÉTAPE 0 — SYNTHÈSE VEILLE (obligatoire, avant code)

- **DÉCOUVERTE_1** — *Emergence World* (arXiv 2606.08367) + *AIvilization v0* (2602.10429), bancs
  long-horizon multi-agents · couche **Social** · **COMBO_BACKLOG P5** (conditionnés LLM tier-2). Aucune
  brique cargo-less intégrable en 7 j → **pas de pivot**, on câble en interne.
- **DÉCOUVERTE_2** — *utility/rule-based action selection sans LLM* (WMAC 2026 · AAAI bridge) · couche
  **Agentic** · l'état de l'art confirme la voie déterministe par règles/utilité → **conforte** le registre
  `_ARC_SEEKS` first-actionable-wins ([ADR-0002](../../adr/0002-no-llm-brain.md)), **0 code**.
- **DÉCOUVERTE_3 (capacité visée)** — archéométrie du bas-fourneau : réduction **solide** au CO
  (Fe₂O₃→Fe₃O₄→FeO→Fe, 1100–1300 °C) ; le fer **ne fond pas** (1538 °C) → **éponge** + scorie de fayalite ;
  chapeau oxyde → fer sain, pyrite → griller (red-short), plomb/zinc → aucun fer. **Vérité-sol** du mensonge
  #8, déjà gravée dans `iron_bloom_yield`.
- **CVE_ACTIVES :** **CVE-2026-48710** (Starlette/FastAPI host-header bypass, fix ≥ 1.0.1) → touche l'extra
  `network`, **pas ce wire** (cognition pure, 0 endpoint) ; noté pour l'extra réseau. **CVE-2026-25580**
  (SSRF Pydantic-AI) → **pydantic-ai non utilisé** (ADR-0002). Aucune surface Genesis de ce wire touchée.
- **PAPER_DU_JOUR :** rien de nouveau intégrable < 7 j sans LLM tier-2 (Rust/GPU gelés, ADR-0008).

**COMBO_RETENU :** `iron_bloomery (C17, bloom_at mutant)` × la boucle cognitive (PROSPECT gossan →
FORCE_DRAUGHT ≥ 1200 °C → BLOOM). **19ᵉ tranche** d'arc, **2ᵉ mutation** agent (le fer). Coût : ~4 h ·
complexité 3 · risque régression **2** (D10 borné au sous-arc métallurgique ; p173/p172 verts). Couche
**Agentic × Substrate**. **ADR requis : NON** — on **étend** [ADR-0010](../../adr/0010-agent-driven-mutation.md)
(C13 prévoyait déjà C17/C19 dans le même sous-arc).

## 1. AUDIT / PHASE

- **PHASE :** post-Phase-4, ère **cargo-less** (ADR-0008), campagne D12/ADR-0009 en fermeture.
- **COUCHES :** Substrate (C1→C20), Agentic (perceive→decide→act→remember, **19** capacités branchées),
  World (Python actif ; Rust gelé).
- **P0_BLOQUANTS :** D12/R0 (arc sans consommateur) — **quasi fermé (19/20)**.
- **TÂCHE_JOUR :** câbler la 19ᵉ capacité, **C17 iron_bloomery** — le seuil de l'âge du fer. **IMPACTÉ_PAR_VEILLE : OUI**
  (vérité-sol du bas-fourneau + confirmation du patron rule-based).

## 2. CE QUI A ÉTÉ LIVRÉ (push `main`)

**D12 wire #19 — `ActionKind.BLOOM = 35` consomme C17 iron_bloomery — la 2ᵉ MUTATION agent (l'âge du fer).**

- 19ᵉ capacité branchée. Un agent (a) `has_forced_draught` (C12, ≥ 1200 °C, paroi réfractaire), (b)
  `"gossan" in prospected_ore_groups` (C1, le chapeau de fer appris), (c) `inv_fuel ≥ 1.0` (C4) voit un
  chapeau **oxyde directement réductible** (`best_bloomery_site_near(require_direct=True)`) et **RÉDUIT** le
  fer. Le monde décide la loupe (`iron_bloom_yield`).
- **Verbe neuf** `BLOOM = 35` (la réduction du fer ≠ la fonte du cuivre C13, qui réutilisait `SMELT = 18`).
- **Mensonge physique** : le fer **ne coule jamais** (1538 °C hors d'atteinte) → `is_solid_bloom = True`
  toujours ; loupe spongieuse à **marteler** (C19), jamais un bouton coulé (vs cuivre).
- **Mensonge #8** : chapeau **oxyde** (hématite/magnétite) → fer sain ; **pyrite** → consommée mais **scorie
  seule** tant que non grillée (red-short) ; **galène/sphalérite** → **aucun fer** (l'oracle refuse le cue).
- **2ᵉ franchissement D10** (`bloom_at → geo.mine_at`, `extracted_kg 0→5`), **borné au sous-arc
  métallurgique** (ADR-0010) ; correction du crédit Wave-1 (seule la loupe entre en `inv_metal`).
- **Réutilise `inv_metal`/`inv_fuel`/`inv_stone`** → **aucun champ `AgentRegistry`, aucune migration**.
  Nouvel état : `BLOOM=35`, `EpisodicMemory.{known_bloom_locations, has_bloomed_iron, last_bloom_mineral,
  last_bloom_iron_kg}`.
- **Auto-limite délibérée** sur `has_bloomed_iron` (posée seulement si `bloom_iron_kg > 0`) plutôt que
  `inv_metal`-saturé → garde `inv_metal` **orthogonal** au cuivre + **ne verrouille pas** sur un échec
  honnête (pyrite/galène). Choix noté (tests #8/#10).
- **Garde-fous :** D8 (`PY_TO_RUST` reste **15**, compose C12×C1, pas de `_PROFILE`) ; D9 (SMELT+BLOOM feu :
  la queue métallurgique C13→C17→C19 est structurellement feu, **aucune** capacité non-feu ne reste à
  intercaler — alternance cède honnêtement) ; D10 (mutation par design, bornée ; précondition gatée ⇒ 0
  géologie mutée, test #4) ; déterminisme (loupe `0.097475` kg bit-identique) ; zéro-régression
  (`bootstrap` n'installe pas C17).
- **Vérif :** `pytest tests/test_iron_bloom_wire.py` → **16 passed** ; `tests/test_arc_seek_registry.py` →
  **6 passed** (registre à 18) ; `ruff` **clean** (fichiers neufs) ; **p175 8/8** (seed `0x1201`, arc vécu
  PROSPECT→FORCE_DRAUGHT→BLOOM). Non-régression : **p173 8/8**, **p172 8/8**. Portail smoke CI étendu à
  **p175** ; `ci.yml` **remis en miroir du Makefile** (p172/p173 oubliés + p175 ajoutés).

## 3. RECOMMANDATIONS — R-J21-x

- **R-J21-1 (P1) — 20ᵉ et dernière bouchée : C19 `bloom_forging`.** Le **martelage** de la loupe (lit la
  sortie de C17 : `inv_metal` fer + `red_short`) → fer forgé, scorie chassée. Même patron **ADR-0010** ;
  préconditions vécues (`has_bloomed_iron` + enclume/percussion). **Clôt l'arc C1→C20 à 20/20.**
- **R-J21-2 (P2) — Corriger la verrue Wave-1 à la source.** `geo.mine_at → _credit_agent_inventory` crédite
  la masse brute ; corrigée **en branche** pour SMELT *et* BLOOM, mais une correction à la source
  (`mine_at`) supprimerait la duplication. Tracé ADR-0010 §b.
- **R-J21-3 (P2) — Registre de capacités : budget de perception.** `_ARC_SEEKS` à 18 entrées,
  `ARC_SEEK_BUDGET = 24` (no-op). Après C19 (19 entrées) l'arc sera complet ; envisager des tiers de
  priorité survie-d'abord avant d'ouvrir les piliers langage/bâtiments.
- **R-J21-4 (P2) — Promouvoir `climate_biome` + `river_discharge`** au set runtime par défaut (inchangé).

## 4. Verdict

| Question scheduled-task | Réponse J+21 |
|---|---|
| Améliorations à signaler ? | **Oui — 19ᵉ capacité branchée (D12 19/20) : l'âge du fer, la 2ᵉ mutation agent (loupe solide).** |
| Faut-il écrire du Rust ? | **Non** (ADR-0008 + env cargo-less inchangés). |
| Push effectué ? | **Oui — `main`** (engine + tests + smoke + Makefile + ci.yml + 2 docs). |
| Prochaine bouchée ? | **R-J21-1** : C19 `bloom_forging` (le martelage) — clôt l'arc à 20/20. |
