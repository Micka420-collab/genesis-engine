# Spec — Streaming & LOD

## Objectif

Le monde étant **infini**, on ne peut pas tout charger. Le système doit charger **uniquement ce qui est nécessaire**, le décharger proprement, et offrir une expérience fluide.

## Acteurs

- **Active Frustums** : un par observer humain (caméra) + un par cluster d'agents
- **Chunk Manager** : charge/décharge selon la distance et l'activité
- **LOD Manager** : choisit le niveau de détail rendu selon la distance

## Politique de chargement

```
Pour chaque Active Frustum F:
  chunks_needed = chunks_in_frustum(F) ∪ neighbor_chunks(F, depth=2)

Pour chaque chunk c:
  if c in chunks_needed:
    if not loaded(c): load_async(c)
  else if not loaded_anywhere(c) and idle_for(c) > 60s:
    if c.modified: persist(c) then unload(c)
    else unload(c)
```

## LOD dynamique

| LOD | Distance frustum | Représentation | Coût |
|---|---|---|---|
| L0 | 0–32 m | full voxel + animations | 100 % |
| L1 | 32–128 m | mesh simplifié, anim rares | 30 % |
| L2 | 128–1024 m | impostor 2D | 5 % |
| L3 | 1–10 km | tile statique pré-rendue | 1 % |
| L4 | >10 km | macroblock couleur | 0.1 % |

Transitions par **dithering temporel** (pas de pop visible).

## Cognition LOD

Les agents **hors champ d'observation** mais **dans une simulation active** sont simulés en **mode allégé** :

| Mode | Coût | Détail |
|---|---|---|
| Full cognition | 100 % | observé directement |
| Reduced | 30 % | dans une zone active mais pas observée |
| Statistical | 1 % | population agrégée, individus virtuels échantillonnés |
| Frozen | 0 % | zone idle, agents en sleep |

Bascule automatique selon l'attention humaine + activité économique de la zone.

## Streaming réseau (observer client)

- WebRTC DataChannel pour les deltas de monde
- Ordre de priorité :
  1. Agents proches caméra
  2. Voxels modifiés du frustum
  3. Background entities
  4. LOD lointain
- Compression : delta-encoded + Zstd

## Cache mémoire

- LRU côté client (limite paramétrable, défaut 2 GB)
- LRU côté sim node (cache des chunks voisins)
- Persistant côté serveur : MinIO + index Cockroach

## Bornes hard

| Métrique | Limite |
|---|---|
| Latence ingest delta | < 50 ms p99 |
| FPS observer client | ≥ 60 |
| Time to first paint après teleport | < 1 s |
| Mémoire client | < 4 GB |
| Bande passante par observer | < 10 Mbps |

## Tests

- **Soak test** : 24 h streaming sur 1000 chunks chargés, vérifier zéro fuite mémoire
- **Stress test** : 10 observers simultanés sur la même région
- **Determinism check** : load → unload → reload → hash identique
