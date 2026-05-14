# SPRINT 2026-05-14 — P-NEW.17 re-profile + optim #3b (regression fix)

**Priorité attaquée**: P-NEW.17 (re-measure `profile_tick.py` à pop=175 après optim #3)
**Statut**: ✅ livré — régression diagnostiquée et corrigée
**Résultat**: 72.0 s → **69.3 s** (−3.8 %, cible <60 s manquée mais baseline battue)

---

## Découverte

Premier run de `scripts/profile_tick.py` après l'optim #3 (sprint
2026-05-16, `r_chunks` resserré + cache d'indices sparse via
`_chunk_resource_indices`) : **114.3 s** — soit une **régression de +59 %**
contre la baseline 72.0 s post optim #2.

### Diagnostic

`_scan_chunk` :

| Variante | calls | tottime | per-call |
|---|---|---|---|
| Pré optim #3 (dense bool-mask)        | 605 k | 31.4 s | 52 µs |
| Optim #3 sparse (np.nonzero + fancy)  | 569 k | 71.1 s | **125 µs** ⚠ |

La version « sparse » paraissait gagnante : moins de cellules touchées.
En pratique, sur le Léman (~12 % des cellules `water > 5` car lac), les
3 arrays `np.nonzero` font encore quelques centaines d'éléments chacun,
et trois effets enterrent le gain :

1. **3× `np.nonzero` par cache-miss** — coût fixe non amortissable
   par un cache hit-rate ~63 %.
2. **Fancy indexing `XX[wy, wx]` → allocation** pour chaque ressource,
   3× par chunk au lieu d'1× sur le chemin dense.
3. **`d2` calculé séparément pour water / food / shelter** (sparse sur
   des subsets disjoints), alors que la version dense le calcule
   **une seule fois** et le partage entre les 3 masques.

Conclusion : la sparse-table est pertinente quand le taux de
remplissage est très faible. Pour le Léman (lac dense), le dense gagne.

---

## Correctif — optim #3b

Re-écriture de `_scan_chunk` dans `engine/cognition.py` :

```python
def _scan_chunk(chunk, px, py, radius_m, out, tick=None):
    XX, YY = _chunk_cell_world_xy(chunk)
    dx = XX - np.float32(px)
    dy = YY - np.float32(py)
    d2 = dx * dx + dy * dy           # *** unique pour les 3 ressources ***
    r2 = np.float32(radius_m * radius_m)
    in_r = d2 <= r2
    if not in_r.any():
        return

    water_mask = in_r & (chunk.water > np.float32(5.0))
    if water_mask.any():
        d2m = np.where(water_mask, d2, np.float32(np.inf))
        flat_idx = int(np.argmin(d2m))
        ay, ax = divmod(flat_idx, d2.shape[1])
        ...
```

Pour food + shelter, même squelette. Drop complet de
`_chunk_resource_indices` et du cache `_scan_idx`.

L'argument `tick=` est conservé pour la compat API (les sites d'appel
n'ont pas à changer) mais n'est plus consulté.

### Validation

- **Déterminisme** : SHA-256 sur `alive + pos + hunger + thirst` après
  120 ticks, 2 runs même seed → **bit-identique**
  (`5ea89da1466e4c318766e74e81a2ef2a`).
- **Profile** : `python scripts/profile_tick.py` à pop=175,
  warmup 800 + profile 300 ticks.

| Variante | total | _scan_chunk tot | per-call |
|---|---|---|---|
| Optim #2 (baseline)             | 72.04 s | 31.4 s | 52 µs |
| Optim #3 (sparse) ⚠              | 114.28 s | 71.1 s | 125 µs |
| **Optim #3b (dense+shared d2)** | **69.34 s** | **30.7 s** | **54 µs** |

Gain net : **−2.7 s** vs baseline (−3.8 %). Cible <60 s **manquée
de 9.3 s** — `_scan_chunk` reste 44 % du frame, mais la régression est
purgée.

---

## Pourquoi pas <60 s ?

`_scan_chunk` est appelé 569 k × 300 ticks / 30.7 s = **~18 500 calls/s**,
avec ~54 µs chacune. Le dense bool-mask est déjà très près du minimum
absolu pour une opération numpy sur un grid 64×64. Pour descendre
sous 60 s il faudra un changement de structure, pas un sub-optim :

- **batch perceive()** : grouper les agents qui scannent le même
  chunk (jusqu'à ~5 dans un home chunk). Calculer `d2` chunk-wide une
  fois pour le batch, puis sélectionner agent-par-agent. Gain estimé
  ~2× sur les chunks denses en agents.
- **cull global** : indexer par chunk une carte « max water_kcal /
  max food_kcal », et ne pas même charger `XX,YY` si tous les
  thresholds sont sous le minimum d'intérêt pour cet agent.
- **descendre en C** : ré-écrire `_scan_chunk` en cython ou numba.
  Probable −2× to −3× supplémentaire.

Ces 3 pistes sont escaladés en **P-NEW.21** (cf. backlog).

---

## Fichiers touchés

```
runtime/engine/cognition.py     (-95 LOC, +55 LOC — drop _chunk_resource_indices)
runtime/journals/profile_tick.txt   (mis à jour par le run)
docs/sprints/2026-05-14_PHASE7-PROFILE-OPTIM3b.md   (ce fichier)
NEXT-SPRINT.md                  (P-NEW.17 archivé, P-NEW.21 ajouté)
```

---

## Référence

- `runtime/engine/cognition.py:189` — nouveau `_scan_chunk`
- `runtime/scripts/profile_tick.py` — méthode de mesure (warmup 800,
  profile 300 ticks)
- `runtime/journals/profile_tick.txt` — full cProfile post optim #3b
- Sprint pré-optim #3 — `docs/sprints/2026-05-16_SPRINT.md`
