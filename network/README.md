# Genesis Network — réseau de calcul mondial volontaire

> Offrir de la puissance de calcul au monde Genesis avec **une seule commande**,
> sur **n'importe quelle plateforme**, et observer les civilisations IA évoluer
> en direct depuis un **site public**. Plus le réseau donne de puissance
> **vérifiée**, plus le monde devient **grand** et **fin**.

---

## 1. Le principe en une image

```
   Volontaires (1 commande)          Coordinateur (VPS)              Monde public
  ┌──────────────────────┐         ┌─────────────────────┐        ┌──────────────┐
  │ genesis donate       │ ──pull→ │  manifeste monde     │        │  site mondial│
  │  (Win/Lin/Mac)       │         │  (seed, chunks, LOD) │ ─SSE─→ │  carte live  │
  │  calcule des chunks  │ ─push→  │  agrège + VÉRIFIE    │        │  classement  │
  │  soumet un hash      │         │  budget = f(puissance)│       │  fil IA      │
  └──────────────────────┘         └─────────────────────┘        └──────────────┘
```

Un **chunk** est une *fonction pure* de `(world_seed, cx, cy, ticks)` : deux
machines quelconques produisent le **même hash**. Le coordinateur **recalcule**
un échantillon pour vérifier → triche impossible, « le monde ne ment jamais »
s'étend au réseau. Cette discipline reprend la primitive PRF canonique du
moteur (`engine.core.prf_bytes`, BLAKE2b), gardée par `test_prf_matches_engine`.

### Pourquoi « plus de puissance = meilleur monde » ?

| Levier | Mécanisme | Effet observable |
|--------|-----------|------------------|
| **Taille** | `world_radius_chunks = 2 + √(unités vérifiées)/2` | Le monde grandit du centre vers l'extérieur (spirale par anneaux) |
| **Résolution** | `ticks_per_unit = 64·2^(niveau-1)` (niveau ∝ log₂(puissance)) | Chaque chunk est simulé plus longtemps → état plus riche |
| **Vie IA** | population émergente par chunk, agrégée | `agent_budget` = nombre d'agents vivants à l'écran |

---

## 2. Démarrer en local (MVP, zéro déploiement)

```bash
cd genesis-engine

# Terminal 1 — le coordinateur + le site mondial
python -m network coordinator --host 127.0.0.1 --port 8770 --db world.db
#   → site : http://127.0.0.1:8770/
#   --db  : le monde + les scores SURVIVENT aux redémarrages (sinon tout en mémoire)
#   --verify-fraction 0.25 : ne re-vérifie qu'1 unité sur 4 des workers fiables
#                            (décharge le CPU serveur ; 1.0 par défaut = tout vérifié)

# Terminal 2 — offrir de la puissance
python -m network donate --server http://127.0.0.1:8770 --nickname MonPseudo
```

Ouvre **http://127.0.0.1:8770/** : la carte se remplit, le classement bouge,
le fil d'événements raconte l'expansion du monde.

### Vérifier (garde-fous du projet)

```bash
python network/scripts/network_smoke.py     # 9/9 bout-en-bout (vrai serveur + 2 workers)
python -m pytest network/tests -q            # 13 tests hermétiques (TestClient)
python -m ruff check network/                # clean
```

---

## 3. La commande mondiale (« une commande, toute plateforme »)

Une fois le coordinateur en ligne sur un VPS (`http://TON-SERVEUR:8770`), un
volontaire n'a besoin **que de Python** — pas de clone, pas de dépendance : le
coordinateur sert lui-même un client autonome mono-fichier à `/client`.

```bash
# Linux / macOS
curl -s http://TON-SERVEUR:8770/client | python3 - --server http://TON-SERVEUR:8770 --nickname MonPseudo
```

```powershell
# Windows (PowerShell)
irm http://TON-SERVEUR:8770/client -OutFile genesis_donate.py
py genesis_donate.py --server http://TON-SERVEUR:8770 --nickname MonPseudo
```

Options : `--max-units N` (s'arrête après N chunks), `--max-seconds S`.

---

## 4. Déploiement VPS (self-host)

Voir [`deploy/`](deploy/) :

```bash
sudo cp deploy/genesis-coordinator.service /etc/systemd/system/
sudo systemctl enable --now genesis-coordinator      # uvicorn sur :8770
sudo cp deploy/nginx-genesis.conf /etc/nginx/sites-available/genesis
sudo ln -s /etc/nginx/sites-available/genesis /etc/nginx/sites-enabled/
sudo systemctl reload nginx                          # TLS + proxy SSE → :80/:443
```

Le coordinateur est sans état externe (tout en mémoire) : pour la persistance
inter-redémarrage, voir « Limites » ci-dessous.

---

## 5. Architecture des fichiers

| Fichier | Rôle |
|---------|------|
| `protocol.py` | Contrat work-unit / résultat (Pydantic v2). |
| `worldgen.py` | Génération déterministe d'un chunk (l'unité de travail). |
| `coordinator.py` | Serveur FastAPI : assigne, vérifie, agrège, diffuse (SSE). |
| `store.py` | Persistance SQLite (monde + scores survivent aux redémarrages). |
| `worker.py` | Client `genesis donate` (du dépôt). |
| `standalone_donate.py` | Client autonome mono-fichier servi à `/client`. |
| `web/index.html` | Site mondial (carte canvas + classement + fil, SSE). |
| `cli.py` | `python -m network coordinator|donate`. |
| `scripts/network_smoke.py` | Smoke bout-en-bout (garde-fou). |
| `tests/test_network.py` | Suite pytest. |

### Endpoints

| Méthode | Route | Usage |
|---------|-------|-------|
| `POST` | `/api/register` | un volontaire rejoint le réseau |
| `GET`  | `/api/work?worker_id=` | tirer un lot d'unités |
| `POST` | `/api/submit` | rendre un résultat (vérifié par recalcul) |
| `GET`  | `/api/state` | snapshot JSON du monde |
| `GET`  | `/api/events` | flux SSE temps réel (site) |
| `GET`  | `/client` | client de don autonome |
| `GET`  | `/` | site mondial |
| `GET`  | `/healthz` | sonde |

---

## 6. Confiance & délestage CPU (modèle de vérification)

Le coordinateur ne fait pas aveuglément confiance, mais ne recalcule pas non
plus tout (sinon il ferait le travail des workers) :

1. **Mise en confiance** — les `TRUST_AFTER` (5) premières unités d'un worker
   sont **toujours recalculées**. Un tricheur est donc démasqué dès sa 1ʳᵉ
   fausse soumission → **banni** (`banned`), plus aucun travail offert. Dégâts
   bornés.
2. **Échantillonnage** — passé ce cap, un worker fiable n'est plus audité qu'à
   la fraction `--verify-fraction` (audit aléatoire déterministe). C'est ce qui
   **décharge réellement le CPU serveur** (vérifié par `test_sampling_offloads_trusted_worker`).

> Limite assumée : pas encore de *clawback* (on n'annule pas a posteriori les
> chunks non-audités d'un worker qui se met à tricher après s'être fait
> confiance — le ban stoppe seulement le futur). La **redondance** (même unité
> à 2 workers, consensus par quorum) est la prochaine étape pour s'en passer.

## 7. Autres limites assumées

- **worldgen autonome** : volontairement découplé du gros `engine.sim` pour
  rester déterministe et cargo-less ici. Le *seam* est prêt
  (`worldgen.engine_prf_available()`) pour brancher des ticks pleine fidélité
  du moteur réel sans changer le contrat (digest content-addressed).
- **Pas d'auth forte** : tokens worker en clair, suffisant pour un réseau
  ouvert observable ; ajouter rate-limit + HTTPS (nginx) avant exposition large.
- **Persistance write-through** : chaque résultat accepté écrit dans SQLite
  (WAL). Pour de très gros débits, batcher les écritures sera utile.

---

## 8. Prochaines itérations

1. ~~Persistance du monde (SQLite) + reprise après redémarrage.~~ ✅ fait (`--db`).
2. ~~Échantillonnage de vérification (vrai délestage CPU).~~ ✅ fait (`--verify-fraction` + réputation).
3. ~~Redondance + quorum (même chunk à N workers, consensus).~~ ✅ fait (`--replication`).
4. Brancher `engine.sim` derrière le seam (chunks « pleine fidélité »).
5. Flux du **narrateur LLM** (`llm_observer`) dans le fil d'événements du site.
6. WebSocket bidirectionnel (quand `websockets`/`wsproto` dispo) en plus du SSE.

### Mode QUORUM (`--replication N`, recommandé `3` en public)

Au lieu de recalculer, le serveur fait calculer **chaque chunk par N volontaires
distincts** et **compare leurs hash** : un chunk n'est finalisé que sur
**consensus** (majorité). Le serveur ne refait alors **aucun calcul**
(délestage total) et un **menteur minoritaire est détecté et banni** par le
consensus lui-même — ce qui ferme le risque du « tricheur dormant » sans
clawback. À combiner avec `--verify-fraction 0` pour zéro recalcul serveur, ou
une petite fraction pour un audit d'intégrité supplémentaire.

```bash
python -m network coordinator --db world.db --replication 3 --verify-fraction 0.1
```
