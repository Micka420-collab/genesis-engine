# Preregistration — `<RUN_ID>`

> **Read me first :** ce template doit être rempli **avant** de lancer le run
> (`experimental_run("<name>") as ctx:`). Toute case complétée *après* le run
> est de la pêche aux résultats (HARKing) et invalide la prétention scientifique.
> Voir [`docs/RUNTIME-LAYOUT.md`](../../docs/RUNTIME-LAYOUT.md) et la section
> "Runs longs" de [`CONTRIBUTING.md`](../../CONTRIBUTING.md).

| Champ                          | Valeur                                                              |
|--------------------------------|---------------------------------------------------------------------|
| Run ID                         | `<auto-rempli par experimental_run, e.g. lausanne-trade-001_20260601T103045Z>` |
| Auteur(s)                      | `@<github-handle>`                                                  |
| Date de pré-enregistrement     | `YYYY-MM-DD` (avant tout `world.run()`)                             |
| Date prévue d'exécution        | `YYYY-MM-DD`                                                        |
| Git commit ciblé               | `<full sha avant le run — gravé dans manifest.json provenance.git>` |
| Tags                           | `cluster:B4`, `axis:information-ecology`, `priority:high` (libre)   |

---

## 1. Hypothèse principale (1-2 phrases)

> **Exemple :** « Sur un monde anchored Lausanne, avec 50 fondateurs et 5000 ticks,
> la diffusion d'information mensongère converge vers une bulle épistémique observable
> (≥ 2 clusters d'agents avec `trust[other_cluster] < 0.2`) avant le tick 3000. »

`<remplir>`

## 2. Prédictions chiffrées (refutables)

Lister **au moins 3** observables avec seuils numériques. Un seuil flou
(« la coopération augmente ») est rejeté — il faut un nombre qu'on puisse
contester en lisant le `summary.json`.

| #   | Observable (champ dans `world.summary()` ou métrique dérivée)         | Seuil prédit              | Direction |
|-----|------------------------------------------------------------------------|---------------------------|-----------|
| P1  | `summary.trust_clusters.count`                                         | ≥ 2 au tick 3000          | hausse    |
| P2  | `summary.communication.message_count`                                  | ≥ 10 000                  | hausse    |
| P3  | `summary.communication.veracity_mean`                                  | < 0.6 dans au moins 1 cluster | baisse |

`<adapter à ton expérience>`

## 3. Conditions d'arrêt (stop conditions)

À spécifier **avant** le run. Une condition imprévue ne peut pas être ajoutée
après-coup pour sauver une prédiction.

- [ ] **Arrêt normal** : tick = `<N>` atteint
- [ ] **Arrêt early-success** : `<condition>` (e.g. P1 satisfait avant tick 2000)
- [ ] **Arrêt early-failure** : `<condition>` (e.g. `n_alive < 5` — extinction)
- [ ] **Arrêt timeout** : wall-clock > `<H>` heures

## 4. Configuration cible

```python
WorldBuilder("<name>")
    .anchor(<lat>, <lon>)
    .size_km(<float>)
    .founders(<int>)
    .cultures(<int>)
    .max_agents(<int>)
    .seed(<hex 64-bit>)   # explicite — sinon WorldBuilder default
    .build()
world.run(<ticks>)
```

Modules optionnels activés (cocher) :

- [ ] `with_l1_earth(True)` — Copernicus DEM + WorldCover
- [ ] `with_l2_lift(True)` — vegetation + erosion + slope
- [ ] `with_realism(True)` — 5cd integration
- [ ] custom : `<liste>`

## 5. Analyses prévues (avant le run)

Décrire **ce qui sera fait** des données :

- Quels champs de `summary.json` seront lus ?
- Quel calcul / agrégation produira la métrique de chaque prédiction ?
- Y a-t-il un script `analyze_<run_id>.py` déjà écrit ? (Idéalement oui, sinon
  l'analyse glisse vers la pêche.)

## 6. Hypothèses null / runs de contrôle

Pour chaque prédiction émergente, citer le run de contrôle où le mécanisme
est désactivé (agents random-decision, communication sans mensonge, etc.) :

| Prédiction | Run de contrôle (run_id) | Hypothèse null |
|-----------|---------------------------|-----------------|
| P1        | `<run_id_control>`        | `trust_clusters.count` ne dépasse pas 1 sans mensonge |
| P2        | …                         | … |

## 7. Sign-off (à la fin, après run)

- [ ] **Préenregistré** — ce fichier committé avant `experimental_run`
- [ ] **Exécuté** — `manifest.json` produit, `state_fingerprint` ci-dessous
- [ ] **Analysé** — résultat par prédiction renseigné (P1: ✅/❌, P2: …)
- [ ] **Référencé dans [`FALSIFIABILITY.md`](../../FALSIFIABILITY.md)** si la prédiction tenait

State fingerprint final (copié depuis `manifest.json`) : `<sha256>`

---

## Notes post-run (mise à jour autorisée APRÈS le run)

> Toutes les observations post-hoc, surprises, et hypothèses dérivées qui
> *n'étaient pas* dans la préenregistration. Sépare clairement ce qu'on a
> prédit de ce qu'on a découvert.

`<libre>`
