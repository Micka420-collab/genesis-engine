# Monde autonome — Terre qui tourne toute seule

Le monde **n’a pas besoin d’IA pour évoluer**. Les agents peuvent construire, mais la planète suit ses lois physiques en continu.

## Modules

| Module | Rôle |
|--------|------|
| `earth_dynamo.py` | Noyau, rotation (Ω Terre), géothermie, cycle jour/nuit, Coriolis |
| `plate_tectonics_live.py` | Plaques qui dérivent, frontières, soulèvement, relief macro + chunks |
| `world_physics_registry.py` | Densité, fusion, conductivité, module Young, phases |
| `material_transform.py` | Matériaux → objets (céramique, outils, bronze…) si T/P/stock OK |
| `emergent_construction.py` | **Construction unifiée** : transform + réel + structures + voxels |
| `autonomous_world.py` | Branche tout + coupler tectonique live |

## Construction émergente (tout fusionné)

Un seul moteur sur `ActionKind.BUILD` / `SMELT` :

1. Chantier multi-tick sur place (progression visible)
2. Choix **émergent** parmi : objet (transform), bâtiment minéral (real), structure (hearth, hut…), voxel
3. **Imitation** : les recettes réussies se propagent aux agents proches (~42 m)

Recettes **vides au départ** : l'agent **expérimente** (matériaux + température), découvre
cordage / silex / céramique, puis choisit librement quoi construire. Imitation culturelle
(~42 m). Aucun script « construis une hutte » — seulement `ActionKind.BUILD` du cerveau.

## Transformation matériaux → objets

Recettes **physiques** (pas de quête) :

- `fire_clay_ceramic` — argile + bois, T > ~900 °C  
- `knapp_flint_tool` — silex + pierre  
- `charcoal_fuel`, `cordage_fiber`, `bronze_ingot`  

Sur `ActionKind.BUILD` / `SMELT`, l’agent démarre un projet multi-tick ; succès → artefact en inventaire.

## Activer

```python
SimConfig(..., autonomous_world=True)
wire_emergence_v2(sim, autonomous_world=True)
```

Earth Console : activé par défaut dans `run_earth_console.py`.

## APIs

- `GET /api/autonomous_world` — vue d’ensemble  
- `GET /api/earth_dynamo` — noyau, insolation, Coriolis  
- `GET /api/plate_tectonics` — vitesses plaques, convergences  
- `GET /api/emergent_construction` — chantiers, découvertes, structures
- `GET /api/material_transform` — projets transform en cours  
- `GET /api/world_physics` — registre matériaux + constantes  

## Smoke

```bash
cd runtime && python scripts/p86_autonomous_world_smoke.py
```

## Philosophie ZERO PRE-SCRIPT

- La Terre **tourne** et les **plaques bougent** sans script de civilisation.  
- Les **objets émergent** quand les conditions physiques et les stocks le permettent.  
- Les IA **construisent** en utilisant ces lois, elles ne les remplacent pas.
