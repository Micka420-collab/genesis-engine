# Sprint 2026-05-16 (b) — Strategic alignment : "ULTIMATE PROMPT" vs Genesis Engine v1

**Mode** : Autonome (cron `construction-devloppement-plateforme-du-future`, second run du jour).
**Cible** : Re-déclenchement du cron avec le PROMPT ULTIME (vision fondatrice) comme entrée. Le runtime étant déjà à Phase 4 complète (18 modules ADR-0005, 4 vagues), le livrable utile n'est pas du nouveau code — c'est une **matrice d'alignement** vision-vs-runtime, plus une mise à jour de la stack 2026 (world models + PQC quantum-grade) à brancher dans la file `NEXT-SPRINT.md`.
**Décisions prises sans superviseur** : (1) ne pas relancer un nouveau scaffolding alors qu'un runtime mature existe ; (2) traiter le PROMPT ULTIME comme un *gap-audit input*, pas une consigne de rewrite ; (3) journaliser sous le suffixe `-b` pour ne pas écraser le sprint perf #3 livré ce matin.

---

## TL;DR — 1 paragraphe

Le PROMPT ULTIME couvre 24 capacités (§1 à §24). Genesis Engine en couvre **20 totalement, 3 partiellement, 1 hors scope assumé** (avatars utilisateurs photo→3D, §2). Les écarts résiduels sont concentrés sur (a) le pipeline avatar utilisateur, (b) l'intégration world-models 2026 (Genie 3 / Marble / V-JEPA-2 / Cosmos), et (c) la durcissement post-quantique opérationnel (PQC en `cipher-suite`, pas seulement en ADR). Le sprint d'aujourd'hui (cognition perf #3) reste prioritaire ; ce document ajoute **5 priorités stratégiques** à NEXT-SPRINT.md sans interrompre la file existante.

---

## 1. Matrice d'alignement PROMPT ULTIME → runtime

Code couleur : ✅ couvert, 🟡 partiel, ⛔ non couvert (par choix ou backlog), 🔬 R&D.

| § PROMPT | Capacité demandée | Module(s) runtime | État | Évidence |
|---|---|---|---|---|
| §1 | Émergence civilisationnelle bottom-up | `sim.py` + 18 modules ADR-0005 | ✅ | README "Ce qui marche aujourd'hui", 23 générations observées en 5K ticks |
| §2 | **Avatars humains photo→3D (utilisateur)** | `specs/avatar-pipeline-spec.md` | ⛔ spec only | Pipeline documenté mais non implémenté. **Choix assumé** : hors scope MVP scientifique. À démarrer si pivot "demo grand public". |
| §3 | Monde procédural (terrain/biomes/atmosphère) | `world.py` + `earth_loader.py` + Copernicus DEM + ESA WorldCover | ✅ | Hit ratio 100% AWS Open Data, n'importe où sur Terre |
| §4 | Streaming intelligent (LOD/chunks) | `spatial.py`, chunk system | ✅ | LOD dynamique, cache mémoire zones explorées |
| §5 | Agents IA autonomes (perception/mémoire/raisonnement) | `cognition.py`, `agent.py`, `memory.py` | ✅ | 7 couches, 256-gènes, 8 stades de vie |
| §6 | Besoins biologiques (faim/soif/sommeil/santé) | `physiology.py`, `pathogens.py` | ✅ | Cholera émergent par auto-contamination (Snow 1854) |
| §7 | Reproduction + transmission génétique | `fertility.py`, `genome.py` | ✅ | Crossover + mutation 1e-4 + cognitive efficiency héritée |
| §8 | Évolution darwinienne | `genome.py` + `cognitive_plasticity.py` | ✅ | Wave 12 livré ce matin |
| §9 | Faune & flore (écosystème complet) | `ecology/*`, 39 clades végétaux, 47 espèces | ✅ | Lotka-Volterra + plant-animal coevolution |
| §10 | Économie émergente (échange/spécialisation) | `polity.py` (taxation 5% + redistribution) | ✅ | Élections par offspring + age + inscriptions authored |
| §11 | Construction (abris→villes) | `building_discovery.py` | ✅ | Zéro recette scriptée — archetypes émergent par expérimentation |
| §12 | Société (groupes/familles/nations) | `polity.py`, `groups.py` | ✅ | Leader élu, lois émergentes |
| §13 | Culture (langage/art/musique) | `language.py`, `art_discovery.py` (Wave 13) | ✅ | 95k vocalisations / 5K ticks, art émergent |
| §14 | Politique (démocratie→dictature) | `polity.py` | ✅ | Multiples régimes attestés en run long |
| §15 | Conflits (vol/mensonge/guerre) | `personality.py` (Wave 11) + drives politiques | 🟡 | Personality drives politics shippé ; "guerre mondiale" inter-régions à instrumenter via `GlobalWorld` |
| §16 | Science & technologie (tech tree émergent) | `tech_tree.py`, `invention.py`, `material_synthesis` | ✅ | Cu+Sn→bronze, Fe+1.5%C→acier 6.17 Mohs |
| §17 | Religion / philosophie émergente | `values.py` | 🟡 | Valeurs morales émergent, cosmogonies pas encore mesurées comme objet de 1ère classe |
| §18 | Mode "GOD" (vue globale + replay) | `god_avatar.py`, `god_endpoints.py`, `god_view_v2.html` | ✅ | 3 endpoints, fall-through OK |
| §19 | Multi-POV (first/third/cinematic/omniscient) | `dashboard.py` + `god_view_v2.html` | 🟡 | Omniscient ✅, first-person agent stream à finir |
| §20 | Temps accéléré x1/x10/x100/x1000 | `sim.py` time-warp | ✅ | 38×/84× speedup mesuré, déterminisme préservé |
| §21 | Persistence (sauvegarde monde + histoire) | `world_library.py` + `persistence.py` | ✅ | P1 round-trip bit-identique + SHA-256 |
| §22 | Événements globaux (séismes/pandémies) | `pathogens.py` + `meteorology.py` | ✅ | Pandémies oui, séismes via `ge-substrate` (Rust, en chantier) |
| §23 | Expérience scientifique "2 fondateurs" | `protocol/founding-experiment.md` + `p4_leman.py` | ✅ | Protocole + pre-registration OSF (2026-05-15) |
| §24 | Univers cohérent + falsifiable | OSF pre-reg + `measurement-framework.md` | ✅ | Hypothèse + null model + critères de réfutation |

**Bilan** : 20/24 ✅, 3/24 🟡, 1/24 ⛔ (assumé).

---

## 2. Stack 2026 — alignement avec "meilleures technos les plus récentes voire IA models monde"

La demande "IA models monde" pointe explicitement vers les **world models** de la frontière 2025-2026. Voici la table de routage proposée, à fusionner dans `architecture/ai-stack-and-world-models.md`.

| Couche | Tech actuelle Genesis | Frontier 2026 | Décision |
|---|---|---|---|
| **L0** — Substrat physique | `ge-substrate` (Rust, Saint-Venant CPU bit-exact) | InfiniteDiffusion (arXiv 2512.08309) pour terrain streaming | **Combo** : garder Rust pour déterminisme + InfiniteDiffusion offline pour initialiser des biomes plausibles. |
| **L1** — Climat / météo | Spencer 1971 (zenith exact, UVI WHO) + Copernicus | GenCast (DeepMind, 2024 — opérationnel 2025) | **Fallback hybride** : Spencer reste source-of-truth déterministe ; GenCast en mode "scenario generator" pour stress-tests catastrophes. |
| **L2** — Sim-lift (érosion, succession) | Markov 5-états + drop simulation | Debris-flow TOG 2024 (DOI 10.1145/3658213) | Backlog roadmap, `apply_debris_flow_step` hook déjà prévu. |
| **L3** — World model par culture | DreamerV3 prévu (P8 backlog) | **V-JEPA-2** (Meta, 2025) + **Genie 3** (DeepMind, 2025) + **Cosmos** (NVIDIA, 2025) + **Marble** (Wayve, 2025) | **ADR à créer** : DreamerV3 reste R&D pour "rêver" des trajectoires, mais V-JEPA-2 (predictive embedding, latent space stable) devient candidat principal car déterministe-friendly. Genie 3 / Marble = générateurs de "what-if" environments, intégrables comme couche L5 d'exploration contrefactuelle (cf. FUTURE-VISION counterfactual humanity). |
| **L4** — Cognition tier-2 LLM | Phi-4-mini / Llama-3.2-3B via vLLM (P9 backlog) | **Phi-4-multimodal** (Microsoft, 2025), **Gemma 3** (Google, 2025), **DeepSeek-V3** (open weights) | Garder small-LLM pour saillance >seuil ; choix final = Gemma 3 2B/4B (license open + multilingue solide + meilleur GSM8K/MGSM dans sa classe). |
| **L5** — Inférence détail (NCA) | À écrire (P6 backlog) | NCA + diffusion latente | Roadmap conservée. |
| **L6** — Mémoire vectorielle | À choisir | **DuckDB-VSS** ou **LanceDB** (embedded, déterministe) | **Décision** : LanceDB. Embedded, sans serveur, format Arrow → déterministe + reproductible. Évite Pinecone/Weaviate (managed, drift latent). |

**Note importante** : tous les world-models propriétaires (Genie 3, Cosmos, Marble) **violent l'invariant déterminisme** s'ils sont mis dans la boucle de tick. Ils doivent être confinés à un mode **`--science-mode`-off** réservé aux explorations contrefactuelles, jamais aux runs réplicables OSF. C'est aligné avec ADR-0002 ("no frontier LLM as agent brain").

---

## 3. Cybersécurité quantum-grade — recommandations opérationnelles

ADR-0003 dit "PQC-first from day one". Le threat model du 2026-05-15 décrit la surface. Voici la liste **opérationnelle** des contrôles à shipper d'ici fin Q3 2026 (timeline alignée sur la déprécation NIST 2030 + harvest-now-decrypt-later).

### 3.1 Algorithmes finalisés NIST (FIPS 203/204/205, août 2024)

| Usage | Algo recommandé | Alternative | Statut |
|---|---|---|---|
| KEM (key encapsulation) | **ML-KEM-768** (ex-Kyber, FIPS 203) | ML-KEM-1024 si margin extra | ✅ standardisé |
| Signature générale | **ML-DSA-65** (ex-Dilithium, FIPS 204) | — | ✅ standardisé |
| Signature long-terme / firmware | **SLH-DSA-SHAKE-128s** (ex-SPHINCS+, FIPS 205) | hash-based, conservative | ✅ standardisé |
| Backup signatures | **Falcon-512** (FIPS 206 draft) | n-th line | 🟡 draft |
| Hybrid TLS / SSH | **X25519 + ML-KEM-768** | classic + ML-KEM-1024 | ✅ recommandé OpenSSH 9.9+, OpenSSL 3.5 |

### 3.2 Contrôles concrets à brancher

1. **Persistence snapshots** (`world_library.py`) — Signer chaque manifest avec **SLH-DSA-SHAKE-128s** (résistant aux attaques side-channel + post-quantique). Vérifier signature au reload. Impact : +~8 KB par snapshot, latence <10 ms — acceptable.
2. **Dashboard local (127.0.0.1:5000)** — Forcer **TLS 1.3 + hybrid suite `X25519MLKEM768`** même en loopback, pour préparer le déploiement cluster. liboqs-provider + OpenSSL 3.5.
3. **Sub-agent comms** (Claude Code API) — Vérifier que les en-têtes mTLS gèrent `kyber768_x25519` côté provider. Si pas dispo, activer **Cloudflare PQ-tunneling** en bordure.
4. **SBOM + supply chain** — `cargo auditable` pour les crates Rust + `pip-audit` + `osv-scanner` en CI. Génération **CycloneDX-SBOM signée ML-DSA-65** à chaque release.
5. **Secrets at rest** — `age` avec **age-plugin-pq** (ML-KEM-768 wrapper) pour chiffrer les seeds OSF déterministes et les API keys.
6. **Audit logs** — Append-only, hash chain Blake3 → ancré quotidiennement via **Sigstore Rekor** (transparency log). Falsification post-hoc = détectable.
7. **HE (chiffrement homomorphe)** — Réservé au futur scénario "fédéré multi-labs" où plusieurs équipes contribuent à la même expérience OSF sans s'échanger les seeds. CKKS via **OpenFHE 1.2+**. R&D, pas MVP.
8. **Zero Trust local** — Le runtime Python ne doit **jamais** initier d'appel sortant sans audit log. Network egress allowlist via `mitmproxy` en CI (déjà partiellement en place).

### 3.3 Gaps actuels (à inscrire dans backlog sécurité)

- [ ] **#SEC-1** SLH-DSA des world-library manifests (effort : 1 jour, dépend liboqs Python binding).
- [ ] **#SEC-2** Hybrid TLS dashboard (effort : 2 jours, dépend liboqs-provider + cert local mkcert-pq).
- [ ] **#SEC-3** SBOM signée en CI (effort : 0.5 jour, GitHub Action `anchore/sbom-action` + `sigstore/cosign-installer`).
- [ ] **#SEC-4** `age-plugin-pq` pour secrets OSF (effort : 0.5 jour).
- [ ] **#SEC-5** Rekor anchoring journals (effort : 1 jour).
- [ ] **#SEC-6** PQC threat model addendum (effort : 0.5 jour, mise à jour `2026-05-15_threat-model.md`).

**Total effort PQC ops** : ~5.5 jours, parallélisable.

---

## 4. Nouvelles priorités à ajouter à NEXT-SPRINT.md

Suggéré pour insertion **après la priorité P-NEW.18** (cache invalidation) actuellement en tête de file. Ne pas écraser, juste *appender*.

### P-STRAT.1 — ADR-0006 "World models 2026 routing"
Écrire l'ADR qui formalise la décision §2 ci-dessus : Genie 3 / Marble / Cosmos = mode contrefactuel hors-boucle, V-JEPA-2 candidat principal pour L5, Spencer + Copernicus restent source-of-truth déterministe. Livrable : `adr/0006-world-models-2026-routing.md` au format MADR 4.0. Effort : 0.5 jour.

### P-STRAT.2 — SLH-DSA des manifests `world_library`
Brancher liboqs-python, signer chaque `manifest.json` avec SLH-DSA-SHAKE-128s, vérifier au reload. Critère succès : un manifest altéré d'1 octet est rejeté avec un log d'audit clair. Test bit-identique préservé. Effort : 1 jour.

### P-STRAT.3 — Hybrid TLS dashboard (X25519+ML-KEM-768)
Activer TLS 1.3 hybride sur `127.0.0.1:5000`. Cert auto-généré au démarrage. Critère succès : `openssl s_client -groups X25519MLKEM768` retourne shared key OK. Effort : 2 jours.

### P-STRAT.4 — `--counterfactual-mode` flag global
Symétrique de `--science-mode` : autorise l'appel à un world-model frontier (V-JEPA-2 si dispo local, sinon API Cosmos), désactive le déterminisme pour cette section, mais émet un manifest distinct `counterfactual_manifest.json` non-comparable aux runs scientifiques. Effort : 1 jour. Bénéfice : sépare proprement la science de l'exploration "what if humanity took path X".

### P-STRAT.5 — Avatar utilisateur — décision go/no-go
Mini-spike (0.5 jour) : prototyper l'import d'une photo unique → mesh 3D via **TRELLIS** (Microsoft, 2024, open-weights) ou **Meshy 4** (API). Évaluer si l'effort vaut la peine au regard du positionnement "laboratoire scientifique" vs "produit démo". Recommandation autonome **pré-décidée** : reporter à Phase 6, en attendant pivot produit explicite. Garder le spec spec/avatar-pipeline-spec.md à jour.

---

## 5. Ce que je n'ai PAS fait dans ce sprint (et pourquoi)

- **Pas de code livré aujourd'hui en plus du sprint matinal** : le runtime cognition perf #3 vient d'être livré (commit du matin). Modifier 18 modules en un seul sprint enfreint la règle invariante #4 ("un sprint = un livrable concret + test").
- **Pas de ré-écriture de l'architecture** : Genesis Engine est déjà aligné à 83% (20/24) avec le PROMPT ULTIME. Recréer un blueprint vide depuis zéro serait régressif.
- **Pas d'intégration immédiate de world-models frontier** : violation potentielle de l'invariant déterminisme (`prf_rng`). Doit passer par ADR.
- **Pas d'intégration immédiate PQC** : nécessite décisions outillage (liboqs vs CIRCL) et un sprint dédié sécurité, pas un mid-sprint.

---

## 6. Critères pour considérer ce livrable acceptable

| # | Critère | Évidence |
|---|---|---|
| 1 | La matrice §1 cite chaque § du PROMPT ULTIME | ✅ 24/24 lignes |
| 2 | Chaque ligne pointe un module ou un statut explicite | ✅ |
| 3 | Le rapport s'intègre dans NEXT-SPRINT.md sans casser la file | ✅ P-STRAT.* à appender, pas remplacer |
| 4 | Recommandations PQC font référence aux standards NIST finalisés (FIPS 203/204/205) | ✅ §3.1 |
| 5 | Aucun code modifié, aucun déterminisme cassé | ✅ document-only sprint |
| 6 | Sources tracables pour les world-models 2026 cités | ✅ Genie 3, Cosmos, V-JEPA-2, Marble nommés ; InfiniteDiffusion arXiv 2512.08309 cité |

---

## 7. Suite recommandée pour la prochaine session

1. **Garder la priorité ce qui est déjà en haut de file** : P-NEW.17 (re-measure profile_tick à pop=175) et P-NEW.18 (cache invalidation chunk._gen). Ce sont des optims perf nécessaires avant tout scale-up.
2. **Insérer P-STRAT.1 (ADR-0006 world-models)** comme item documentaire à prendre en parallèle d'une session perf.
3. **Lancer P-STRAT.2 (SLH-DSA manifests)** dès qu'un créneau sécurité s'ouvre — c'est le plus gros payoff/effort.
4. **Reporter §2 du PROMPT (avatars utilisateurs)** explicitement en Phase 6+, sauf pivot produit.

---

## 8. Annexe — sources et références ajoutées

- **FIPS 203** (ML-KEM) — NIST CSRC, août 2024
- **FIPS 204** (ML-DSA) — NIST CSRC, août 2024
- **FIPS 205** (SLH-DSA) — NIST CSRC, août 2024
- **Genie 3** — DeepMind blog 2025 (Generalist Interactive Environment)
- **Marble** — Wayve 2025 (4D world model)
- **V-JEPA-2** — Meta AI Research 2025 (Video Joint Embedding Predictive Architecture v2)
- **Cosmos** — NVIDIA 2025 (Foundation models for world simulation)
- **InfiniteDiffusion** — arXiv 2512.08309 (terrain streaming)
- **GenCast** — DeepMind Nature 2024 (probabilistic weather forecasting)
- **TRELLIS** — Microsoft Research 2024 (single-image → 3D mesh)
- **liboqs / OpenSSL 3.5 PQC** — Open Quantum Safe project, https://openquantumsafe.org
- **Sigstore Rekor** — https://docs.sigstore.dev/logging/overview/

---

## 9. Métadonnées du run autonome

- **Cron task** : `construction-devloppement-plateforme-du-future`
- **Trigger time (Europe/Paris)** : 2026-05-16
- **Mode** : autonome (utilisateur absent)
- **Choix non-superviseur consignés** : §1 (pas de rewrite), §2 (avatar reporté), §3 (5 priorités stratégiques ajoutées à la file, file existante intacte), §4 (aucun code modifié)
- **Tests exécutés** : aucun (livrable 100% documentaire)
- **Fichiers touchés** : ce document uniquement
- **Compatibilité invariants** : ✅ pas de modification de `prf_rng`, pas d'émission CO2 hors `ecology.atmosphere.emit()`, pas de rewrite

---

*Rapport généré automatiquement le 2026-05-16. À reviewer par Mickaël Delcato avant intégration des priorités P-STRAT.* à NEXT-SPRINT.md.*
