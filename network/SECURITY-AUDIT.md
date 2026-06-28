# Audit de sécurité — le pont client → serveur

> Périmètre : tout ce qui traverse la frontière entre un **client donateur**
> (non fiable par nature : n'importe qui sur Internet) et le **coordinateur**.
> Date : 2026-06-27. Code audité : `network/{protocol,coordinator,worker,store,standalone_donate}.py`, `web/index.html`.

## Modèle de menace

Le client est **hostile par défaut**. Il peut : forger des requêtes, mentir sur
ses résultats, rejouer, inonder, envoyer des charges géantes, tenter
d'empoisonner le monde affiché, voler le crédit d'autrui, injecter du HTML/SQL.
Le coordinateur ne doit jamais faire confiance à une donnée client sans contrôle.

## Constats & corrections

| # | Sévérité | Constat | Statut |
|---|----------|---------|--------|
| 1 | **Élevée** | **Empoisonnement du monde** : le résumé (biome, population…) n'était pas lié au hash. Un client pouvait envoyer un hash correct mais un résumé falsifié → carte/classement corrompus. | ✅ Corrigé |
| 2 | Moyenne | **Vol de crédit** : `submit` ne vérifiait pas que l'unité appartenait au worker qui la rendait → un worker pouvait rendre l'unité d'un autre. | ✅ Corrigé |
| 3 | Moyenne | **DoS par inscriptions** : `register` illimité → `contributors`/`tokens` croissent sans borne (épuisement mémoire). | ✅ Corrigé |
| 4 | Moyenne | **DoS par charge** : aucune limite de taille de requête. | ✅ Corrigé |
| 5 | Faible | **Bornes d'entrée absentes** : champs numériques/chaînes non cadrés (population géante, chaînes énormes). | ✅ Corrigé |
| 6 | Faible | **Comparaison de token non constante** (fuite temporelle théorique). | ✅ Corrigé |
| 7 | Faible | **XSS** via pseudo affiché sur le site. | ✅ Déjà sûr (échappement vérifié) |
| 8 | — | **Injection SQL** dans la persistance. | ✅ Déjà sûr (requêtes paramétrées) |
| 9 | — | **Path traversal** sur `/` et `/client`. | ✅ Déjà sûr (chemins fixes) |

### Détail des corrections

1. **Liaison résumé ↔ hash** (`coordinator.submit`) :
   - Chemin **vérifié** (recalcul) : on stocke désormais la **vérité serveur**
     (`truth.summary()`), jamais la copie client. Bon hash + faux résumé → écrasé.
   - Chemin **de confiance** (non recalculé) : contrôle **O(1)** que le résumé
     reproduit bien son hash (`worldgen.chunk_digest(...)`), sinon rejet + ban.
   - Prérequis technique : les valeurs sont **arrondies avant** le calcul du hash
     (`worldgen`/`standalone` alignés, gardés par `test_standalone_matches_worldgen`),
     pour que le résumé transmis détermine exactement le hash.
   - Tests : `test_verified_path_stores_server_truth_not_client`,
     `test_trust_path_rejects_summary_digest_mismatch`.

2. **Propriété de l'unité** : `submit` rejette si `assignment.worker_id != res.worker_id`.
   Test : `test_cannot_submit_another_workers_unit`.

3. **Anti-inondation** : purge des sessions inactives (`PRUNE_AFTER_S=3600`,
   scores cumulés conservés) + plafond `MAX_CONTRIBUTORS=10000` → `CapacityError`
   → HTTP 429. Tests : `test_registration_capacity_limit`, `test_stale_workers_are_pruned`.

4. **Taille de requête** : middleware rejetant tout corps > `MAX_BODY_BYTES=64 KiB` (HTTP 413).
   Test : `test_oversized_body_rejected`.

5. **Bornes Pydantic** (`protocol.ChunkSummary`/`WorkResult`) : `cx/cy` ±1e6,
   `ticks` 1..1e6, `population` 0..1e9, ressources ≥ 0, `digest` exactement 64 hex,
   `nickname` ≤ 40, `worker_id/token` ≤ 64. + `worker_id` de requête borné.

6. **Token à temps constant** : `secrets.compare_digest`.

## Garanties anti-triche (rappel du modèle)

- Mise en confiance : les `TRUST_AFTER=5` premières unités sont **toujours
  recalculées** → un tricheur est démasqué dès sa 1ʳᵉ fausse soumission et **banni**.
- Au-delà : audit aléatoire à `--verify-fraction` (délestage CPU réel).
- Le calcul serveur est **borné** (`ticks ≤ 1024`, fixés par le serveur, jamais
  par le client) → pas d'amplification CPU pilotée par le client.

## Risques résiduels (assumés)

| Risque | Impact | Atténuation actuelle / piste |
|--------|--------|------------------------------|
| **Tricheur « dormant »** : honnête puis faux résultats sur unités non auditées | Quelques chunks faux avant détection (mode simple) | ✅ **Résolu en mode quorum** (`--replication 3`) : le consensus détecte et bannit le minoritaire, le faux chunk n'est jamais finalisé. En mode simple : audit aléatoire + ban bornent les dégâts. |
| **Griefing de la frontière** : un worker réserve beaucoup d'unités sans rendre | Ralentit l'expansion ~30 s | Ré-assignation auto après `STALE_AFTER_S=30`. Piste : quota d'unités en cours par worker. |
| **Confiance amont du donateur** : `curl /client \| python` exécute du code du serveur | Le donateur doit faire confiance à l'opérateur | Inhérent au volontariat. Recommander : ne donner qu'à des serveurs de confiance ; publier un hash du client. |
| **Pas d'auth d'identité** : un pseudo peut être usurpé | Score attribué au mauvais pseudo | Acceptable pour un réseau ouvert observable. Piste : clé par contributeur. |
| **Transport** : trafic en clair entre client et serveur local | — | **TLS assuré par Cloudflare Tunnel / nginx** (terminaison externe). Toujours partager une URL `https://`. |

## Avant exposition large (recommandations)

1. ✅ **Rate-limiting par IP** (register/work/submit, fenêtre glissante → 429 ; X-Forwarded-For). Fait 2026-06-28.
2. ✅ **Redondance + quorum** disponible (`--replication 3`) — l'activer en public.
3. ✅ **Quota d'unités en cours** par worker (`MAX_INFLIGHT_PER_WORKER`, anti-griefing). Fait 2026-06-28.
4. ✅ **SHA-256 du client** exposé (`GET /client.sha256`) pour vérification avant exécution. Fait 2026-06-28.
5. Garder `--verify-fraction` raisonnable (ex. 0.1–0.3) : audit d'intégrité en plus du quorum.

> Tout le trio pré-lancement (1, 3, 4) est livré + testé, et le module est
> désormais gardé en CI (`make network`). Reste surtout du *scaling* (SSE en
> deltas) et de l'observabilité — pas de faille ouverte connue sur le pont.
