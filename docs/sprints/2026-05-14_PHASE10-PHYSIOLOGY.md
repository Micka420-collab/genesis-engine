# SPRINT 2026-05-14 — Wave 3 physiology ultra-réaliste

**Priorité attaquée**: Wave 3 humaine — excrétion (urine/feces), hygiène,
maladies de peau, pathogènes contagieux.
**Statut**: ✅ livré
**Cible**: agents ultra-réalistes avec boucle de rétroaction
corps↔environnement↔disease, déterministe, testable.

---

## Émergence observée

**Smoke `p20_physiology_smoke.py` (800 ticks, pop=20→80, drive_accel=1500)** :

```
n_active=80   alive=12   relief_total=1513   bathe_total=136
contaminations actives sur 12 chunks
cholera_max=0.66   infected_cholera=10/12 agents survivants

means:
  bladder   = 0.11  (juste après relief moyen)
  bowel     = 0.40  (fill plus lent)
  hygiene   = 0.48  (décay partiellement compensé par 136 bains)
  sunburn   = 0.00  (thermal modéré à Léman en mai)
  frostbite = 0.00  (pas de freezing)
```

**Constat scientifiquement intéressant** : sans même qu'on les programme
pour cela, les agents qui se soulagent près de l'eau (premier point
d'eau disponible quand la vessie urge) contaminent le lac où ils boivent
ensuite — et déclenchent une **épidémie de choléra émergente** dès 800
ticks. 10 des 12 survivants ont une charge cholérique > 0.1. C'est le
mécanisme historique réel des épidémies du XIXe siècle (J. Snow, Soho
1854) reproduit par pure simulation physique.

---

## Architecture

### Module `engine/physiology.py` (~500 LOC)

```
PhysioFields (side-table, sized like AgentRegistry.capacity)
├── Excretion : bladder, bowel
├── Hygiène  : hygiene
├── Peau     : sunburn, frostbite, parasites, dermatitis
├── Pathogènes : cholera_load, flu_load, wound_load
├── Immunité : immune_cholera/flu/wound + immune_baseline
├── Génome-derivé : melanin, body_fat (loci 120-143)
└── Compteurs : relief_events, bathe_events, diseases_caught

water_contamination: Dict[chunk_coord, float] — pollution per chunk
```

### Sous-ticks (post `sim.step`)

| Sous-tick | Action |
|---|---|
| `_tick_excretion` | bladder + bowel ↑ à taux métaboliques calibrés (4 h / 14 h fill) ; over-fill → pain + stress |
| `_tick_hygiene` | hygiene ↓ avec temps + sweat + parasites |
| `_tick_skin` | sunburn (thermal hot × low melanin), frostbite (cold × low body fat), parasites (low hygiene), dermatitis (allergens) |
| `_tick_pathogens` | croissance **logistique** `r·load·(1-load)` modulée par immunité ; clearance proportionnelle ; gain mémoire post-infection |
| `_tick_airborne_transmission` | flu se propage aux agents dans rayon 2 m via la spatial grid |
| `_tick_contamination_decay` | water_contamination → demi-vie 3 jours |
| `_tick_auto_relief_and_bathe` | relief autonome dès bladder/bowel ≥ urge ; contamination si eau adjacente ; bain si hygiene < 0.4 + eau ≥ 50 |

### Action hooks (DRINK / FORAGE / EAT)

`engine.cognition.apply_decision` est wrappé **une fois par processus**.
Le wrapper utilise une table de dispatch `id(agents) → (sim, fields)`
permettant à plusieurs sims de cohabiter sans corruption.

| Action | Effet physio |
|---|---|
| DRINK Δthirst > 0 | bladder += 0.6×Δ ; **ingestion de choléra** déterministe via `prf_rng` si water_contamination > 0.05 |
| FORAGE / EAT Δhunger > 0 | bowel += 0.5×Δ |
| post.injuries > pre+0.01 | wound_load += (1 - hygiene) × 0.10 (infection bactérienne sur plaie sale) |

### Endpoint + HUD

- `GET /api/physiology_state` — moyennes, max, infected counts, events
- `#observatory-panel` — 2 nouvelles lignes :
  - `💧bld · 💩bwl · 🧼hyg · ☀️sun · ❄️frz · 🐛par · 🩹der`
  - `🦠 cho/flu/wnd infected · relief · bath · caught`

### ADR-0005

`engine.physiology` publie ses constantes :
```python
PIPELINE_LAYER = "Genesis-L4 Feedback"
WORLD_MODEL_CAPABILITY = "paper-L2 Simulator"
```

Ajouté à `_REQUIRED_MODULES` du linter CI. `p18_capabilities_lint`
passe avec **4/4** modules requis taggés OK.

---

## Calibration réaliste

| Phénomène | Constante | Référence réelle |
|---|---|---|
| Bladder full | 4 h sim | 250-500 mL → 4-8 h |
| Bowel full | 14 h sim | 1-2 relief/jour |
| Hygiene decay sans bain | 5 jours sim | ~ semaine |
| Sunburn (UV unprotected, fair skin) | ~3600 s | ~1 h direct sun |
| Frostbite (-10°C, low fat) | ~1800 s | ~30 min |
| Cholera doublement | 3 h | ID50 ≈ 10⁶, doublement 1-4 h |
| Flu doublement | 6 h | R0 ≈ 1.3, doublement 4-8 h |
| Wound infection | 12 h | ~12 h post-injury onset |
| Airborne flu radius | 2 m | gouttelettes |

---

## Déterminisme

Tous les RNG via `engine.core.prf_rng` keyed sur :
- `["physiology", "init_traits"], [row]` (fallback si pas de genome)
- `["physiology", "cholera_ingest"], [tick, row]`

**Smoke step C** : deux sims construits avec même seed dans le même
processus, 800 ticks chacun. Hash physio :

```
27dff46e878183dc1aad3f92  vs  27dff46e878183dc1aad3f92  ✓ bit-identique
```

Dispatch table `_PHYSIO_DISPATCH[id(agents)]` empêche la corruption
cross-sim (bug initial : le 2e wrapping capturait le 1er comme inner,
toutes les actions du sim2 atterrissaient dans les fields du sim1).

---

## Smoke results (7/7 PASS)

```
[OK] step A — bladder mean grew          0.000 -> 0.112
[OK] step A — bowel mean grew            0.000 -> 0.404
[OK] step A — hygiene in [0, 1]          hygiene=0.482
[OK] step A — auto-relief fired          relief=1513
[OK] step A — bathe_total non-negative   bathe=136
[OK] step B — ADR-0005 lists physiology  status=ok
[OK] step C — physiology determinism     bit-identical hash
```

---

## Fichiers touchés

```
runtime/engine/physiology.py                       (nouveau, ~520 LOC)
runtime/engine/dashboard.py                        (+8 LOC, endpoint + import)
runtime/engine/god_view_v2.html                    (+45 LOC, 2 HUD lines)
runtime/engine/world_model_capabilities.py         (+1 LOC, _REQUIRED_MODULES)
runtime/scripts/p20_physiology_smoke.py            (nouveau, 175 LOC, 7/7 PASS)
docs/sprints/2026-05-14_PHASE10-PHYSIOLOGY.md      (ce fichier)
NEXT-SPRINT.md                                     (Wave 3 archivé)
```

---

## Pistes Wave 4 (au-delà)

- **Wounds détaillées** : type, profondeur, localisation (jambe / bras /
  tronc) avec impact sur walk_speed / forage_skill.
- **Grossesse + lactation** : femelles enceintes augmentent les besoins
  caloriques, lactation modifie immune_strength des nourrissons.
- **Vaccination culturelle** : recettes de remèdes (herbes anti-fièvre,
  poultices anti-infection) découvertes par invention.py et transmises
  à la `MaterialRegistry`. Boost de `immune_*` direct.
- **Mémoire trauma** : agents qui ont vu des morts par cholera évitent
  les chunks contaminés → comportement adaptatif sans entraînement.
- **Cycle sommeil REM** : les SLEEP successifs consolident les memoires
  EpisodicMemory et baissent stress plus efficacement.
