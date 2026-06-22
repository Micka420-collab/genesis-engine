# Genesis Engine — Frontière de mutation cross-langage (D10)

**Créé :** 2026-06-22 (J+12 run #2, Cap. C17 `iron_bloomery`).
**Déclencheur :** reco `R-J9-2` / `R-J9r2-2` des audits J+9 — *« ouvrir
`crates/MUTATION-FRONTIER.md` à la 2ᵉ mutation après `smelt_at` (C13) »*. Cette
2ᵉ mutation est arrivée : `iron_bloomery.bloom_at` (C17).
**Contrainte env :** `cargo` absent ([ADR-0008](../../../adr/0008-python-rust-frontier.md),
D7) ; le côté Rust est **gelé** (Wave 42) ; CI = vérité. Ce document **nomme** la
frontière ; il ne câble rien côté Rust (différé Phase A, ADR-0008 §5).

---

## 1. Qu'est-ce que D10 ?

La quasi-totalité des capacités `runtime/engine/` (C1..C12, C14..C16) sont des
**oracles non mutants** : elles *lisent* le substrat (seed → géologie → climat) et
exposent un **signal véridique** (`*_cue_for_chunk`, `*_preview`), sans jamais
modifier l'état du monde. Le déterminisme et le coût-tick-nul en découlent
trivialement.

**D10** est le risque/chantier de la **frontière de mutation** : le jour où une
capacité agent **modifie réellement** l'état du substrat (consomme une ressource,
dépose un produit), cette mutation doit rester **cohérente cross-langage** — car le
substrat worldgen canonique vit côté **Rust** (`native/world-engine`, gelé Wave 42)
et le runtime de simulation active vit côté **Python** (`runtime/engine`,
cargo-less). Tant que les mutations ne touchent que des champs **purement Python**
dérivés du seed (jamais ré-sérialisés vers le worldgen Rust), la frontière reste
**gelée et sûre**.

---

## 2. Inventaire des mutations (état J+12 run #2)

| # | Capacité | Point d'entrée mutant | Ce qui est muté | SSOT d'extraction | Réversible ? |
|---|---|---|---|---|---|
| 1 | **C13** `copper_smelting` | `smelt_at(sim, row, …)` | `StrataLayer.extracted_kg` (minerai de cuivre retiré de la colonne) + compteurs `geology.state` | `geo.mine_at` | non (extraction cumulative) |
| 2 | **C17** `iron_bloomery` | `bloom_at(sim, row, …)` | `StrataLayer.extracted_kg` (minerai de fer gossan retiré) + compteurs `geology.state` | `geo.mine_at` | non (extraction cumulative) |

**Les deux mutations passent par le MÊME unique point** : `engine.geology.mine_at`
(la SSOT d'extraction). Aucune capacité n'écrit `extracted_kg` directement : elles
**délèguent** toutes à `mine_at`, qui :
- soustrait la masse de `layer.extracted_kg` (borné par la masse disponible) ;
- incrémente `state.cumulative_extracted` + le compteur par-minéral du chunk ;
- crédite l'inventaire de l'agent via les rendements d'éléments (pont Wave 1).

C'est la **seule surface de mutation** de tout l'arc C1→C17. Tant qu'elle le reste,
D10 est **maîtrisé par construction** : une seule fonction à auditer.

---

## 3. Pourquoi la frontière reste GELÉE (D10 sûr aujourd'hui)

1. **Le champ muté est purement Python et dérivé du seed.** `chunk_geology` est
   calculé à la demande par `prf_rng` (déterministe, fonction du seed) ; `mine_at`
   ne fait que **comptabiliser** ce qui a été retiré dans l'état de session
   Python. **Rien n'est ré-écrit vers le worldgen Rust** (`native/world-engine`),
   qui reste la source canonique en lecture seule (oracle de contrat, ADR-0007).
2. **Déterminisme préservé.** À seed + séquence d'actions égales, l'état muté est
   bit-identique entre deux runs (l'extraction est une fonction pure de la colonne
   géologique déterministe + des actions). Les **oracles** (`*_cue_for_chunk`)
   restent eux purs et non mutants : seuls `smelt_at` / `bloom_at` mutent, et **par
   choix explicite de l'agent**, jamais dans un hook de tick.
3. **Pas de divergence Python↔Rust introduite.** La mutation ne crée aucune
   nouvelle matière ni aucun nouveau *tell* (garde-fou **D8** : `PY_TO_RUST` reste
   **15**, prouvé par `test_geology_cross_language_contract`). Elle ne fait que
   **retirer** une matière déjà au catalogue partagé.

---

## 4. Quand la frontière DEVRA être câblée (Phase A, gated cargo)

Le câblage cross-langage **réel** de la mutation devient nécessaire **seulement si**
l'une de ces conditions apparaît (toutes différées, ADR-0008 §5) :

- **(D10-a)** Le worldgen Rust devient **persistant/mutable** (un chunk extrait doit
  rester extrait après un rechargement depuis le substrat Rust) → besoin d'un canal
  `extracted_kg` Python → Rust (sérialisation d'état d'extraction).
- **(D10-b)** Une mutation **dépose** une matière nouvelle dans la colonne (p.ex. la
  scorie de fayalite re-déposée, un remblai) → besoin d'enrichir le contrat
  `PY_TO_RUST` (et donc D8) côté dépôt, pas seulement retrait.
- **(D10-c)** Deux runtimes (Python sim + Rust worldgen) tournent **simultanément**
  sur le même monde et doivent réconcilier l'extraction.

**Aucune de ces conditions n'est réunie aujourd'hui** (`cargo` absent, Rust gelé,
runtime unique Python). La frontière reste donc **nommée et gelée**, conformément à
ADR-0008. Ce document est le point d'ancrage à rouvrir lors d'une « session cargo ».

---

## 5. Garde-fous actifs (ce qui empêche la dérive D10 dès maintenant)

- **Un seul point de mutation** (`geo.mine_at`) — toute nouvelle capacité mutante
  DOIT y déléguer (revue de code : interdiction d'écrire `extracted_kg` en direct).
- **Tests d'effet** : `test_copper_smelting` (C13) et `test_iron_bloomery` (C17)
  prouvent que `*_at` consomme bien le minerai (`extracted_kg` croît) ET que le
  métal/loupe rendu **égale** ce que l'oracle non-mutant promettait (« le monde ne
  ment jamais » au sens FORT).
- **D8 inchangé** : `PY_TO_RUST == 15` (la mutation n'introduit aucun tell).
- **Déterminisme** : suites vertes seed-à-seed (737 passed / 1 skip J+12 run #2).

---

## 6. Reco de suivi

- **R-D10-1** : à la **3ᵉ** mutation (ou à la 1ʳᵉ mutation **de dépôt** plutôt que
  de retrait), réévaluer (D10-b) — un dépôt touche le contrat `PY_TO_RUST`.
- **R-D10-2** : ne JAMAIS muter dans un hook `sim.step` (garderait le coût-tick-nul
  et le moratoire observateurs) — la mutation reste un **acte d'agent** explicite.
- **R-D10-3** : à l'ouverture d'une session `cargo`, traiter (D10-a) en priorité
  (persistance d'extraction) avant tout dépôt (D10-b).

---

**État J+12 run #2 :** 2 mutations (C13 cuivre, C17 fer), **un seul** point d'entrée
(`geo.mine_at`), **0 divergence** cross-langage introduite, frontière **gelée et
sûre**. Document ouvert ; câblage Rust **différé** (ADR-0008, gated cargo).
