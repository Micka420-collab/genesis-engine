# Phase 5e + 5f — God Avatar & Ultra-realistic worldgen
**Date :** 13 mai 2026
**Demande :** mode "dieu jouable" — pouvoir entrer dans le monde, observer caché ou révélé, créer sans coût, plusieurs caméras, et un monde 99 % réaliste.

---

## Vision

Le Genesis Engine devient un laboratoire scientifique où l'utilisateur n'est plus
seulement spectateur d'un dashboard, mais incarne un observateur omniscient
qui peut :

- se déplacer librement dans le monde via un avatar invisible par défaut ;
- créer sans coût (terrain, structures, agents, ressources, événements) ;
- se révéler aux agents pour observer leur réaction à une présence
  "miraculeuse" — graine d'émergence religieuse / mythologique ;
- basculer entre cinq points de vue (top-down, première personne, troisième
  personne, épaule d'un agent, replay) ;
- voir le monde rendu avec une fidélité approchant 99 % d'un vrai paysage
  terrestre via génération réaliste + détails IA.

C'est une expérience scientifique : chaque acte du dieu est journalisé dans
un canal séparé, ce qui permet de comparer le "run naturel" (sans
intervention) avec le "run guidé" (où le dieu agit).

---

## Phase 5e — God Avatar (priorité immédiate)

### 5e.1 — Entité God

Nouvelle classe `GodObserver` séparée de l'AgentRegistry :

```python
@dataclass
class GodObserver:
    pos: np.ndarray              # (3,) float — position monde
    heading: float               # rad
    visible: bool                # False par défaut
    frozen: bool                 # True = sim en pause autour de lui
    elevation_m: float           # peut voler
    speed_ms: float              # 0 (immobile) ou ce qu'on veut
    selected_power: str          # "spawn_agent" | "spawn_structure" | "modify_terrain" | etc.
    intervention_count: int = 0
    visible_to_agents: set = field(default_factory=set)  # agents qui ont vu un miracle
```

Le god n'est **jamais** dans `agents.alive`. Il a sa propre slot. Sa position
est rendue dans la god-view comme une icône distinctive (couronne dorée).

### 5e.2 — Visibilité conditionnelle

Dans `cognition.perceive()`, on ajoute au début :

```python
if streamer.god is not None and streamer.god.visible:
    # Le god est perçu comme un agent ordinaire mais avec un flag
    nearest["divine"] = PerceivedTarget(
        kind="divine", x=god.pos[0], y=god.pos[1],
        distance=..., qty=1.0, other_row=-1)
```

Si `visible = False`, le scan ignore complètement le god. Si visible et
qu'un agent perçoit un acte miraculeux (spawn de ressource, modification
de terrain), son flag `has_witnessed_miracle` s'allume et son vecteur de
valeurs est nudgé vers `LEGACY + COMMUNITY` (graine de transmission orale
d'un mythe). Ces agents propagent ensuite l'information par SPEAK.

### 5e.3 — Pouvoirs sans coût

Endpoints REST :

| Endpoint | Effet |
|---|---|
| `POST /api/god/teleport` `{x, y, z}` | bouge l'avatar |
| `POST /api/god/visibility` `{visible: bool}` | révèle ou masque |
| `POST /api/god/spawn_agent` `{x, y, culture_id}` | crée un fondateur supplémentaire |
| `POST /api/god/spawn_structure` `{kind, x, y}` | crée un bâtiment complet instantané |
| `POST /api/god/spawn_resource` `{material, kg, x, y}` | dépose des matériaux |
| `POST /api/god/modify_terrain` `{x, y, height_delta}` | sculpte l'élévation |
| `POST /api/god/modify_biome` `{x, y, biome}` | change la nature d'une cellule |
| `POST /api/god/grant_tech` `{row, tech}` | offre une tech à un agent |
| `POST /api/god/freeze_time` `{frozen: bool}` | gel global |
| `POST /api/god/rewind` `{to_tick: int}` | rembobine via le journal |
| `POST /api/god/inject_event` `{kind, metadata}` | injecte un événement custom |

Chaque appel émet un `GodInterventionEvent` dans un canal séparé du journal
principal — c'est ce qui permet de distinguer les runs guidés des runs
naturels en analyse post-hoc.

### 5e.4 — Caméras multiples

Dans la god-view HTML, un sélecteur de POV avec 5 modes :

| Mode | Description |
|---|---|
| `TOP_DOWN` | Vue actuelle, pan/zoom/follow |
| `FIRST_PERSON` | Caméra à la position de l'avatar god, looking forward via heading |
| `THIRD_PERSON` | Caméra derrière l'avatar, à ~8 m de hauteur |
| `AGENT_SHOULDER` | Caméra à la position d'un agent sélectionné, voit ce qu'il "voit" (perception_radius limité) |
| `REPLAY` | Pas de live — scrubber temporal sur le journal jsonl, on regarde une tranche figée |

Pour first-person et third-person, on aura besoin d'un vrai rendu 3D (ou un
proxy 2.5D : projection isométrique avec ombrage altitudinal). À ce stade
on peut commencer en 2D oblique (pseudo-3D) et passer à Three.js plus tard.

### 5e.5 — Émergence religieuse

Quand `god.visible == True` et qu'un agent perçoit un acte miraculeux
(spawn d'objet, terrain modifié à courte distance) :

1. L'agent émet un événement `MIRACLE_WITNESSED` dans le journal naturel.
2. Son vecteur `values` est nudgé vers `legacy + community`.
3. Une nouvelle entrée arrive dans son `memory.long_term`.
4. Lors des SPEAK suivants, son lexicon dérive vers une signature partagée
   avec d'autres témoins → émergence d'un "mythe partagé".
5. Quand assez d'agents partagent ce mythe, l'annalist émet un événement
   `BELIEF_FORMED` (nouveau type d'événement).

C'est une vraie graine de religion artificielle, sans hard-code.

---

## Phase 5f — Worldgen ultra-réaliste

Deux chemins, on choisit selon ton appétit en temps :

### Chemin A — Earth-anchored (Phase 5a, déjà planifié)
Charger le vrai relief / climat / biomes / hydrographie depuis Copernicus
DEM + WorldClim + Resolve Ecoregions + HydroSHEDS. **Le plus réaliste qu'on
puisse faire** : c'est littéralement la Terre. Voir
`PHASE5A-PLAN.md` pour les détails.

### Chemin B — Worldgen procédural inspiré de la science (5f.1)
Si on préfère un monde inventé mais "Terre-like" :

1. **Plate tectonics** : 6-12 plaques Voronoi, vitesses de dérive, frontières
   convergentes (montagnes), divergentes (vallées), transformantes (failles).
2. **Génération de relief** : superposition fBm sur les frontières de plaques
   pour créer chaînes de montagnes cohérentes (pas du noise pur).
3. **Érosion hydraulique** : algorithme classique (drop simulation ou
   slope-based), itéré ~100 passes, génère des vallées et deltas réalistes.
4. **Réseau hydrographique** : flow accumulation à partir de l'élévation
   érodée, seuils → rivières, lacs dans dépressions fermées.
5. **Biomes Holdridge** : classification précise selon température +
   précipitation + altitude (déjà partiellement en place).
6. **Climat global** : cellules de Hadley/Ferrel/polaires, vents zonaux,
   shadow rain effect sur les montagnes.

Effort estimé : ~2-3 semaines pour un pipeline complet, single-threaded
numpy. Librairies existantes utilisables sans copie : `scipy.ndimage` pour
érosion, `scipy.spatial.Voronoi` pour plaques, `richdem` pour flow
accumulation (BSD).

### Chemin C — IA générative pour détails (5f.2)
Pour atteindre 99 % de réalisme visuel :

- **NCA (Neural Cellular Automata)** légère pour la texture par cellule
  (variations de végétation, patches de roches). Tournable sur CPU avec un
  modèle de 100k params.
- **Diffusion model latent** pour générer des "patches détaillés" sur
  demande (sentiers, clairières, structures cachées) — single-GPU.
- **DreamerV3** comme world model interne aux agents pour qu'ils imaginent
  des trajectoires possibles avant d'agir.

C'est un sprint de recherche / R&D plutôt qu'un livrable garanti.

---

## Plan d'attaque

Je propose cet ordre, le plus haut-impact d'abord :

1. **5e.1 + 5e.2 — God Avatar + visibilité** (1-2 sessions)
   Tu peux te déplacer, te révéler ou te cacher. Pas encore de pouvoirs,
   juste la présence. Test : agent qui voit le god se met à faire dériver
   son lexicon vers une signature "religieuse".

2. **5e.3 — Pouvoirs** (2 sessions)
   Spawn agent, spawn structure, modify terrain, freeze time, grant tech.
   Toolbar dans la god-view.

3. **5e.4 — POV multi-caméras** (1 session)
   Au minimum top-down, first-person 2.5D, agent-shoulder, replay.

4. **5e.5 — Émergence religieuse** (1 session, intégration cognition)
   Wire `MIRACLE_WITNESSED` → values → mythe partagé → `BELIEF_FORMED`.

5. **Phase 5a (Earth-anchored)** ou **5f.B (worldgen procédural)** au choix.
   Si tu veux la vraie Terre, c'est 1.5 semaine et tu vois littéralement
   le Léman. Si tu veux un monde inventé "Terre-like", c'est 2-3 semaines.

6. **Phase 5f.2 (IA générative)** en R&D continu.

---

## Sécurité scientifique

Toutes les interventions du god sont étiquetées dans un canal séparé
(`journals/god_interventions.jsonl`). Les expériences scientifiques
doivent pouvoir affirmer : "sur ce run, 0 intervention divine, donc tous
les comportements observés sont émergents naturels". Le serveur refuse
toute commande god si la sim a démarré avec `--science-mode` jusqu'à ce
qu'un déverrouillage explicite soit envoyé.

---

## Question pour la suite

Tu veux que j'attaque **5e.1 (God Avatar + visibilité) tout de suite**, ou
tu préfères que je termine d'abord l'intégration Phase 5c + 5d
(matériaux/construction/écologie/invention/valeurs branchés au tick loop) ?
Les deux sont valides — 5e te donne le contrôle interactif visible
immédiatement, mais sans 5c-5d tu n'auras pas grand-chose à observer
puisque les agents n'auront pas encore les comportements de construction
et d'invention que tu m'as demandés.

**Ma reco : terminer 5c-5d d'abord (intégration au tick loop), puis 5e.**
Ça te donne dans l'ordre : un monde où les agents construisent et inventent
vraiment, puis le pouvoir d'y entrer en tant que dieu pour observer ou
intervenir.
