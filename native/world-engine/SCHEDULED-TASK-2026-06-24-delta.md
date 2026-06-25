# Tâche planifiée 2026-06-24 (J+14) — Delta sur le rapport J+13

> **Type :** rapport (pas de modif code, user absent, prompt scheduled-task).
> **Référence :** [`SCHEDULED-TASK-2026-06-23-axe-mapping.md`](SCHEDULED-TASK-2026-06-23-axe-mapping.md)
> reste **valide à 95 %** ; ce delta capture uniquement ce qui a bougé depuis hier soir.
> **Méthode :** lecture seule. Sources : `git log --since="2026-06-23 18:00"`,
> [`AUDIT-DELTA-2026-06-23.md`](AUDIT-DELTA-2026-06-23.md), [`ADR-0009`](../../adr/0009-agent-consumer-loop.md).

---

## 0. TL;DR — J+14 a fermé 4 P0/P1 de J+13

Le prompt scheduled-task **reste obsolète** (R-ST-1 toujours P0), mais le run d'aujourd'hui
**ne tombe pas à vide** : la journée J+14 a fermé 4 items du backlog J+13 et ouvert
un ADR structurel.

| Reco J+13 | Statut J+14 | Trace |
|---|---|---|
| **R-J13-1 (P0)** Brancher l'arc sur la boucle agent | **✅ fermée** (D12 bouchée #2) | `7d4c748` — `ActionKind.KNAP` consomme C2 émergent |
| **R-J13-2 (P0)** Portail smoke p139 → p152 | **✅ fermée** | `131b6ce` — gate étendu, 13 smokes C9–C20 désormais gardés |
| **R-J13-3 (P0)** Brancher `ruff check runtime/` | **✅ fermée** | `131b6ce` — step CI + `make lint` + 2 bugs F821 fixés |
| **R-J13-5 (P1)** Casser UN front immobile | **✅ partielle** (climat dynamique chemin-chunk) | `8ab93c9` — couplage orographique, `macro` ne renvoie plus 0.0 |
| **R-J13-6 (P1)** ADR-0009 « fire-first » ou D9 CI | **♻ pivoté** | `adr/0009-agent-consumer-loop.md` créé (mais traite **D12** pas D9) |
| **R-J13-4 (P1)** Brèche DRINK eau de mer | **✅ déjà fermée 23/06** | `2d0ebd0` (J+13 soir) |
| R-J13-7 (P1) Cadence routine d'audit | **❌ ouverte** | *ce run prouve que la routine n'est toujours pas gatée* |
| R-J13-8..10 (P2/P3) | **❌ ouvertes** (cohérent ADR-0008 / session cargo) | — |

→ **3 P0 fermés en 1 j**, **arc maintenant branché sur agent** (D12 ouvert mais 2/20 capacités câblées),
**substrat dynamique côté chemin chunk** (D11 ouvert mais la branche `macro` n'est plus un placeholder),
**CI durci** (smoke gate complet + ruff actif + 2 bugs latents corrigés).

---

## 1. Ce qui a bougé sur le mapping 6-axes (vs J+13)

| Axe prompt | État J+13 (hier) | État J+14 (aujourd'hui) | Δ |
|---|---|---|---|
| **Axe 1 — Réalisme géologique** | observateurs Waves 50/62/63 lisent sans muter ; mutation tectonique dans boucle disjointe | **inchangé Rust** ; côté Python : la mutation `plate_tectonics_live`/`novel_operators` est désormais **lue par les chunks** via le couplage orographique (`8ab93c9`) | partiel (pont chemin-agent ↔ tectonique vivant via température/biome) |
| **Axe 2 — Climat dynamique** | branche `macro` → 0.0 + TODO ; saisons absentes | branche `macro` recouple `−LAPSE_K_PER_M·Δelev` (SSOT `earth_laws`) ; saisons toujours absentes | **avancée majeure** (P1 #7 J+13 fermé) |
| **Axe 3 — Écosystème vivant** | aucun bouclage prédateur/proie ; arc fournit des affordances jamais consommées | C2 maintenant consommé via `ActionKind.KNAP` (curiosité + meilleur affleurement perçu → `inv_tools` += knap_quality) | **D12 ouvert** mais 1ʳᵉ vraie boucle perceive→decide→act→remember sur une capacité (C3 fix d'hier ne touchait qu'un verbe existant) |
| **Axe 4 — Performance** | Rust gelé ; pas de profil 60fps | inchangé | — |
| **Axe 5 — Interface agents IA** | API read-side existe, aucun agent ne l'appelle | `best_toolstone_near` (C2) appelé dans `decide()` ; pattern canonique ratifié par ADR-0009 | **frontière de consommation ratifiée** |
| **Axe 6 — Outils de dev** | smoke gate ≤p139, ruff off, Cargo.lock untracked | smoke gate p152, ruff actif, Cargo.lock tracké (`131b6ce`) | **trous CI fermés** |

---

## 2. Trous architecturaux dominants au 2026-06-24

### D12 — Toujours R0, mais **mordu** (2/20 capacités câblées)
- **DRINK / C3** (commit `2d0ebd0`) — boucle respecte la salinité (perception + verbe).
- **KNAP / C2** (commit `7d4c748`) — agent rassasié+curieux perçoit, choisit, taille, mémorise.
- **Reste 18/20** à câbler (C1, C4–C20). Le **pattern est désormais figé** par ADR-0009 :
  `perceive → decide (utility) → act (verbe) → remember (épisodique)`, sous les drives de survie,
  émergence préservée (« le monde ne ment jamais » étendu au comportement).

### D11 — Toujours R0, mais **moitié climatique levée**
- Côté **chunk** : la macro du climat n'est plus un placeholder constant. Uplift refroidit,
  érosion réchauffe (`−6,5 °C` par km, exact, SSOT `LAPSE_K_PER_M`). Identique sur monde
  statique → 0 régression ; additif avec `linear_warming` ; opt-out `orographic_coupling`.
- Côté **hydro** : rivières runtime = toujours bande géométrique, `cross_chunk_*` toujours stubs
  auto-déclarés. **C'est la moitié restante de D11.**

### Trou CI — **fermé** (P0 J+13 #2/#3)
- Smoke gate p139 → p152 (13 smokes C9–C20 maintenant gardés).
- `ruff check runtime/` + `make lint` actifs en CI.
- 2 bugs F821 corrigés (latents, non exécutés par les tests existants).
- `Cargo.lock` tracké.

### R-ST-1 / R-J13-7 — **toujours P0 ouverte**
La routine planifiée tire toujours un prompt obsolète (Rust actif, livrable « Code Rust »).
Ce run a produit du delta utile **parce que** la journée J+14 était dense — pas grâce à la
routine. R-J12-1 + R-ST-1 + R-J13-7 demandent toutes la même chose : **gater le run sur
activité** ou **réécrire le prompt** pour pointer sur l'audit-delta du jour.

---

## 3. Recommandations — R-J14-x

### P0 — débloquer
- **R-J14-1 (P0) — Câbler une 3ᵉ capacité agent.** Le pattern ADR-0009 a été
  validé sur C2 (perception riche, verbe net). Le candidat naturel est **C14
  cryoclasty** (même opérateur orthogonal « gather », alternance non-feu, déjà
  ancrée par seed 0xB0 ; permet à un agent en altitude froide de ramasser des
  éclats sans tailler). Ou **C7 fire-ignition** (débloque l'arc combustible
  C4 + transformations C8–C13 vues du joueur, mais ouvre D9). Garder **alternance
  non-feu** : C14 plus prudent.
- **R-J14-2 (P0) — Gater la routine d'audit.** Reco R-J12-1 / R-J13-7 / R-ST-1
  ouverte depuis J+12 (~3 j). Choix simple : (a) condition « ≥1 commit depuis le
  dernier `AUDIT-DELTA-*` » ; (b) réécrire le prompt vers « lire le dernier
  audit-delta et produire un delta ». Le présent rapport est un exemple de (b).

### P1 — haut levier
- **R-J14-3 (P1) — Compléter la moitié hydro de D11.** Substituer la bande-rivière
  + `cross_chunk_*` par un transport de débit conservatif inter-chunks. ~1 wave.
- **R-J14-4 (P1) — Casser un pilier immobile.** Langage ou bâtiments toujours à 0.
  Le pattern ADR-0009 (utility-based action selection + invariant comportemental)
  donne un cadre clair pour les amorcer sans violer l'émergence.

### P2/P3 — inchangé
- Inchangé par rapport au backlog J+13 §3 #8–#21.

---

## 4. Verdict final

| Question scheduled-task | Réponse J+14 |
|---|---|
| Y a-t-il des améliorations à signaler ? | **Oui, J+14 a livré 3 P0 + 1 P1 majeurs ; reste 17/21 items J+13** |
| Le moteur a-t-il bougé depuis le rapport d'hier ? | **Oui, significativement** : arc connecté à l'agent (D12 mordu) ; substrat dynamique côté chunk (moitié climat de D11 levée) ; CI durci |
| Faut-il écrire du Rust ? | **Non, ADR-0008 + env cargo-less inchangés** |
| La routine est-elle utile aujourd'hui ? | **Conditionnellement** : utile cette fois car J+14 était dense ; **toujours pas gatée** → re-flaggée R-J14-2 (P0) |
| Faut-il un AUDIT-DELTA-2026-06-24.md complet ? | **Non** — ce delta court suffit ; le prochain audit-delta complet attendra une vraie nouvelle découverte ou un J+15 dense |

---

**Commit prévu :** aucun (rapport pur, pas de modif code).
**MEMORY :** une ligne courte ajoutée.
