# 🚀 Mettre Genesis Network en ligne (VPS Linux + Cloudflare Tunnel)

Objectif : faire tourner le monde sur ton VPS et donner **une commande** que
n'importe qui peut lancer pour offrir sa puissance de calcul.

Le dossier `network/` est **autonome** : il ne dépend que de
`fastapi / uvicorn / pydantic` (pas du reste du dépôt Genesis).

---

## Étape 1 — Envoyer le code sur le VPS

Depuis ta machine **Windows** (PowerShell), dans `genesis-engine/` :

```powershell
ssh UTILISATEUR@IP_DU_VPS "mkdir -p ~/genesis"
scp -r network UTILISATEUR@IP_DU_VPS:~/genesis/
```

> `network/` n'étant pas encore commité, on le copie directement. (Si tu le
> pousses sur GitHub plus tard, un `git clone` fera aussi l'affaire.)

---

## Étape 2 — Préparer le VPS (une seule fois)

En **SSH** sur le VPS :

```bash
cd ~/genesis
chmod +x network/deploy/setup-vps.sh
./network/deploy/setup-vps.sh
```

Le script crée un venv et installe les dépendances.

---

## Étape 3 — Lancer le coordinateur

```bash
cd ~/genesis
. .venv-genesis/bin/activate
python -m network coordinator --host 127.0.0.1 --port 8770 --db world.db
```

- `--db world.db` : le monde et les scores **survivent aux redémarrages**.
- `--verify-fraction 0.25` (optionnel) : décharge le CPU du serveur une fois
  les donateurs jugés fiables.

Laisse ce terminal ouvert (ou voir Étape 6 pour systemd).

---

## Étape 4 — Exposer publiquement avec Cloudflare Tunnel (gratuit)

Installer `cloudflared` (une fois) :

```bash
# Ubuntu/Debian (amd64)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared && sudo mv cloudflared /usr/local/bin/
```

Dans un **second terminal SSH** :

```bash
cloudflared tunnel --url http://localhost:8770
```

Cloudflare affiche une URL publique, par ex. :

```
https://random-words-1234.trycloudflare.com
```

👉 **C'est l'adresse de ton monde.** Ouvre-la dans un navigateur : tu vois le
site mondial en direct. (URL temporaire, change à chaque lancement — voir
« Tunnel permanent » plus bas pour une URL fixe sur ton domaine.)

---

## Étape 5 — La commande à donner aux autres

Remplace `URL` par ton adresse Cloudflare. Chacun choisit son pseudo.

**Linux / macOS :**
```bash
curl -s URL/client | python3 - --server URL --nickname SON_PSEUDO
```

**Windows (PowerShell) :**
```powershell
irm URL/client -OutFile genesis_donate.py
py genesis_donate.py --server URL --nickname SON_PSEUDO
```

Exemple concret :
```bash
curl -s https://random-words-1234.trycloudflare.com/client | \
  python3 - --server https://random-words-1234.trycloudflare.com --nickname Alice
```

La personne n'a besoin **que de Python** — aucun téléchargement du dépôt,
aucune dépendance. Elle voit ses chunks calculés défiler ; toi et tout le monde
voyez son pseudo grimper au classement sur le site.

---

## Étape 6 — Rester en ligne 24/7 (optionnel, systemd)

```bash
sudo cp network/deploy/genesis-coordinator.service /etc/systemd/system/
sudo nano /etc/systemd/system/genesis-coordinator.service   # ajuster User= et chemins
sudo systemctl daemon-reload
sudo systemctl enable --now genesis-coordinator
```

Pour un **tunnel permanent** avec URL fixe sur ton domaine (nécessite un compte
Cloudflare + un domaine) :

```bash
cloudflared tunnel login
cloudflared tunnel create genesis
cloudflared tunnel route dns genesis genesis.ton-domaine.com
# config ingress → service: http://localhost:8770
cloudflared tunnel run genesis
```

---

## Dépannage

| Symptôme | Cause / solution |
|----------|------------------|
| `python -m network` : *No module named network* | Lance la commande depuis `~/genesis` (le dossier qui **contient** `network/`). |
| Le site charge mais reste vide | Normal tant que personne ne donne — lance un worker (Étape 5). |
| Le donateur a une erreur SSL | Utilise bien l'URL `https://…trycloudflare.com` (pas l'IP brute). |
| L'URL change à chaque fois | Tunnel rapide = temporaire. Voir « Tunnel permanent ». |
| Port déjà utilisé | Change `--port` (ex. 8771) et adapte `cloudflared --url`. |
