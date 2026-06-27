# 🌍 Genesis Network — un monde qui tourne grâce à la communauté

Genesis Network transforme le moteur Genesis en un **monde vivant partagé** :
des civilisations IA évoluent en continu, et **plus la communauté offre de
puissance de calcul, plus le monde grandit et gagne en résolution**. Tout le
monde peut le regarder évoluer en direct depuis un site public.

C'est un projet **ouvert, volontaire et observable** — inspiré de
Folding@home / BOINC, mais pour faire émerger une civilisation.

---

## Les 4 façons de participer

### 👁️ 1. Observer (rien à installer)

Ouvre simplement l'URL du monde dans un navigateur. Tu vois en temps réel :
la carte des biomes, la vie des agents IA, le classement des donateurs et le
fil des événements (« le monde s'étend », « X a rejoint le réseau »…).

### ⚡ 2. Donner sa puissance de calcul (une commande)

Tu n'as besoin **que de Python**. Aucun dépôt à cloner, aucune dépendance.

**Linux / macOS**
```bash
curl -s URL/client | python3 - --server URL --nickname TON_PSEUDO
```
**Windows (PowerShell)**
```powershell
irm URL/client -OutFile genesis_donate.py
py genesis_donate.py --server URL --nickname TON_PSEUDO
```

Ta machine calcule des « chunks » du monde et les renvoie ; ton pseudo grimpe
au classement. Tu peux arrêter à tout moment (Ctrl-C), ou limiter avec
`--max-seconds 300` / `--max-units 100`.

### 🖥️ 3. Héberger un coordinateur (faire tourner un monde)

**N'importe qui peut héberger son propre monde Genesis.** Le serveur
(`coordinator`) est autonome (Python + 3 paquets), tient sur un petit VPS, et
s'expose au monde entier gratuitement via un **tunnel Cloudflare**.

Guide complet : **[`deploy/QUICKSTART-VPS.md`](deploy/QUICKSTART-VPS.md)**

```bash
# sur ton serveur
python -m network coordinator --db world.db --replication 3 --verify-fraction 0.1
# dans un autre terminal : URL publique instantanée
cloudflared tunnel --url http://localhost:8770
```

Tu obtiens une URL `https://…` à partager. Ton monde a son propre `world_seed`
→ chaque hébergeur fait vivre **son** univers déterministe ; la communauté peut
en faire tourner plusieurs en parallèle (fédération de mondes).

### 🛠️ 4. Contribuer au code

Le module vit dans [`network/`](.) et suit la discipline du projet : tests
pytest, smoke vert, `ruff` clean, déterminisme. Voir [`../CONTRIBUTING.md`](../CONTRIBUTING.md).
Pistes ouvertes : brancher le moteur pleine fidélité, le narrateur LLM dans le
fil, rate-limiting par IP, quota anti-griefing. (Voir [`README.md`](README.md) §8.)

---

## Confiance, sécurité & éthique

Le réseau est ouvert : le client donateur est **non fiable par construction**.
Le coordinateur ne fait donc jamais confiance aveuglément :

- **Déterminisme** : un chunk est une fonction pure de `(world_seed, coord)` —
  deux machines produisent le même résultat, donc tout est **vérifiable**.
- **Consensus (mode quorum)** : `--replication 3` fait calculer chaque chunk par
  3 volontaires distincts et compare leurs hash. Un menteur **minoritaire est
  détecté et banni** par le consensus, son faux résultat n'est jamais retenu.
- **Réputation + audit** : en complément, un audit aléatoire recalcule une
  fraction des résultats ; toute fraude est **bannie**, dégâts bornés.
- **Aucune donnée personnelle** : on ne demande qu'un pseudo. Pas de compte,
  pas de tracking. Participation **opt-in**, arrêtable à tout instant.
- **Audit de sécurité** complet du pont client→serveur :
  **[`SECURITY-AUDIT.md`](SECURITY-AUDIT.md)**.
- **Éthique** du projet (observation réfutable, non-nuisance) :
  [`../ETHICS.md`](../ETHICS.md) · règles de communauté : [`../CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md).

> Avertissement honnête : donner sa puissance via `curl … | python` exécute le
> client servi par l'hébergeur. **Ne donne qu'à des serveurs de confiance.** Les
> hébergeurs sont encouragés à publier le SHA-256 du client (`/client`).

---

## Ressources

| Doc | Contenu |
|-----|---------|
| [`README.md`](README.md) | Architecture, endpoints, lancement, modèle de confiance |
| [`deploy/QUICKSTART-VPS.md`](deploy/QUICKSTART-VPS.md) | Héberger pas à pas (VPS + Cloudflare Tunnel) |
| [`SECURITY-AUDIT.md`](SECURITY-AUDIT.md) | Audit de sécurité client → serveur |
| [`deploy/`](deploy/) | `systemd`, `nginx`, `setup-vps.sh` |

**Rejoins l'aventure : observe, donne, héberge, contribue.** 🌱
