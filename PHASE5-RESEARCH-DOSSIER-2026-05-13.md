# Genesis Engine — Phase 5 Research Dossier
**Date:** 13 May 2026
**Question:** Comment rendre le monde du Genesis Engine aussi réaliste que la vraie Terre, pour que les IA puissent découvrir notre monde à travers cette simulation ?

Cette synthèse consolide quatre axes de recherche menés en parallèle :
géospatial (terrain, climat, biomes), cognition IA (agents LLM, world models),
plateformes ALife/civ-sim existantes, et données biologiques/anthropologiques.
Chaque section liste les datasets ou systèmes, leurs licences, leurs loaders
Python, et finit par une recommandation prioritaire.

---

## Verdict exécutif

Pour faire émerger un Genesis Engine qui ressemble au monde réel, il faut
investir **dans cet ordre** :

1. **Earth-anchored world** (Phase 5a, 1–2 semaines). Remplacer la
   génération procédurale fBm de `engine/world.py` par un chargeur géospatial
   réel sur Copernicus DEM GLO-30 + CHELSA climatology + Resolve Ecoregions
   + HydroSHEDS. C'est la couche fondamentale dont tout le reste dépend.
2. **Cognition à trois niveaux** (Phase 5b, 2–3 semaines). Garder la
   policy réflexe Phase 4 pour 95 % des ticks, ajouter un module LLM
   PIANO-style (parallèle, faible coût) pour les événements saillants,
   et un pass de réflexion Haiku/Mistral-Nemo une fois par "nuit" en sim.
3. **Calibration physiologique** (Phase 5c, 1 semaine). USDA FoodData
   Central + équation Mifflin-St Jeor : tous les chiffres
   énergétiques / nutritionnels deviennent réels.
4. **Faune et flore réelles** (Phase 5d, 2 semaines). GBIF + IUCN +
   PanTHERIA + EltonTraits posent un écosystème vivant.
5. **Couche culturelle** (Phase 5e, 2 semaines). D-PLACE/SCCS + PHOIBLE
   + Glottolog pour ancrer les seeds linguistiques et culturelles dans
   l'anthropologie réelle plutôt que dans un lexique 16-D abstrait.

Phases 5b à 5e sont indépendantes une fois 5a posée — on peut paralléliser.

---

## 1. Couche géospatiale — Earth-anchored world

| Couche | Source recommandée | Licence | Résolution | Loader Python | Compte requis ? |
|---|---|---|---|---|---|
| Élévation | **Copernicus DEM GLO-30** (AWS Open Data) | Copernicus, attribution | 30 m global | `rasterio` sur COG | Non |
| Climatologie | **CHELSA v2.1** | CC-BY 4.0 | ~1 km, normales 1981–2010 | `rasterio`/`xarray` | Non |
| Météo réelle | **ERA5 / ERA5-Land** | Copernicus | 0.25° / 0.1°, horaire 1940–présent | `cdsapi` + `xarray` | **Oui (CDS)** |
| Biomes | **Resolve Ecoregions 2017** | CC-BY 4.0 | 846 écorégions vectorielles | `geopandas` | Non |
| Couvert terrestre | **ESA WorldCover 2021 v200** | CC-BY 4.0 | 10 m, 11 classes | `rasterio` | Non |
| Hydrographie | **HydroSHEDS / HydroRIVERS / HydroLAKES** | Free + attribution | ~90 m / rivières + lacs ≥10 ha | `geopandas` | Free reg |
| Sols | **SoilGrids 250 m v2.0** (ISRIC) | CC-BY 4.0 | 250 m | `soilgrids` PyPI | Non |
| Côtes | **Natural Earth** + **GSHHG** | PD / LGPL | 1:10 m vectoriel | `geopandas` | Non |

**Pattern de chargement uniforme** — tous les datasets ci-dessus se ramènent
à un seul contrat : `(lat_min, lon_min, lat_max, lon_max) → numpy.ndarray`.
Quelques lignes suffisent par couche grâce à `rasterio.windows.from_bounds`
sur les COG :

```python
import rasterio
from rasterio.windows import from_bounds
url = "s3://copernicus-dem-30m/Copernicus_DSM_COG_10_N47_00_E008_00_DEM/..."
with rasterio.open(url) as src:
    dem = src.read(1, window=from_bounds(8.0, 47.0, 8.5, 47.5, src.transform))
```

**Si un seul investissement est fait :** **Copernicus DEM GLO-30 via `rasterio`
sur le bucket AWS Open Data**. L'élévation est la base sur laquelle tout
s'accroche (biomes, hydrologie, climat lapse-rate, ligne de visée). Aucun
compte, ~30 m global, COG donc tile reads en millisecondes.

---

## 2. Couche cognition — IA pour agents et world models

### Architecture recommandée (cible 2026)

> **PIANO-style decomposed agent + LangGraph state machine + Letta memory
> + vLLM self-host (Phi-4-mini / Llama-3.2-3B) + Haiku 4.5 ou Mistral Nemo
> en batch pour la réflexion + DreamerV3 en option pour "imagination" en
> espace latent.**

Trois niveaux :
- **Tick-level reflex** — pas de LLM, politique utilitaire existante. 95 % des décisions.
- **Event-triggered cognition** — petits LLM locaux (~3 B params) batchés par vLLM ; modules PIANO concurrents (parole, mise-à-jour de but, jugement social).
- **Reflection / planning** — passe Haiku ou Nemo une fois par "nuit" sim, sur batch API.

### Références clé

| Référence | Année | Repo | Licence | Idée centrale |
|---|---|---|---|---|
| **Generative Agents (Smallville)** | 2023 | [joonspk-research/generative_agents](https://github.com/joonspk-research/generative_agents) | Apache-2.0 | Memory stream + reflection + plan ; recette canonique encore référence. |
| **Voyager** | 2023 | [MineDojo/Voyager](https://github.com/minedojo/voyager) | MIT | Bibliothèque de compétences = code généré + curriculum auto-proposé. |
| **Project Sid / PIANO** | 2024 | [altera-al/project-sid](https://github.com/altera-al/project-sid) | Research-permissive | 1000+ agents Minecraft ; modules cognitifs concurrents arbitrés par contrôleur. |
| **SOTOPIA** | 2024 | [sotopia-lab/sotopia](https://github.com/sotopia-lab/sotopia) | MIT | Schéma personnage avec but / secret / relation ; rubrique d'évaluation multi-axe. |
| **DreamerV3** | 2025 (*Nature*) | [danijar/dreamerv3](https://github.com/danijar/dreamerv3) | MIT | World model latent (RSSM), single-GPU, hyperparams fixes sur 150+ tâches. |
| **Letta (ex-MemGPT)** | 2024 | [letta-ai/letta](https://github.com/letta-ai/letta) | Apache-2.0 | Mémoire hiérarchique OS-style : core / recall / archival, agent paginé. |
| **LangGraph v1.0** | 2025 | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | MIT | Runtime à graphe d'états ; standard 2026 pour orchestrer cycles et reprises. |
| **V-JEPA 2** | 2025 | [facebookresearch/vjepa2](https://github.com/facebookresearch/vjepa2) | CC-BY-NC (research) | World model prédictif latent à partir de vidéo, 1.2B params. |

**Fermés / non utilisables directement :** Genie 3 (Google, gated), SIMA 2
(DeepMind, closed), Tesla World Sim (interne). Inspiration uniquement.

### Économie d'inférence en 2026

Mistral Nemo ~ $0.02/M tokens in. GPT-4.1 Nano ~ $0.05/$0.40. Haiku 4.5 ~ $1/$5.
Auto-hébergé Llama-3.x-8B sur vLLM avec continuous batching tourne à >90 %
d'utilisation GPU sur un A100 unique. Un sim de 500 agents à 1 tick/s avec
~5 % d'agents firing tier-2 par tick + tier-3 nightly tient sur **un GPU 24 GB
local OU $5–10/heure-sim** sur endpoint hébergé.

---

## 3. Prior art — Ce qu'on peut piller

| Projet | Date | Repo | Licence | Ce qu'on vole |
|---|---|---|---|---|
| **Project Sid / PIANO** | 2024 | [altera-al/project-sid](https://github.com/altera-al/project-sid) | Permissive | Layout PIANO (modules concurrents arbitrés) — colle au tick déterministe. |
| **Generative Agents** | 2023 | [joonspk-research/generative_agents](https://github.com/joonspk-research/generative_agents) | Apache-2.0 | Schéma `{text, timestamp, last_access, importance, embedding}` + score recency × importance × relevance. |
| **OASIS (CAMEL-AI)** | 2024–25 | [camel-ai/oasis](https://github.com/camel-ai/oasis) | Apache-2.0 | Split modulaire **Environment / RecSys / Time Engine / Agent** — pattern de modularisation pour ticks déterministes. |
| **SOTOPIA** | 2024 | [sotopia-lab/sotopia](https://github.com/sotopia-lab/sotopia) | MIT | Personnage = goal + secret + relationship ; rubrique d'évaluation. |
| **Flow-Lenia** | 2025 | github.com/Chakazul/Lenia | MIT | Conservation de masse pour champs de ressources (food, water). |
| **JaxLife** | 2024 | [luchris429/jaxlife](https://github.com/luchris429/jaxlife) | MIT | Robots-programmables-dans-le-monde — fabrication d'outils sans hard-code. |
| **CAX** | ICLR 2025 Oral | [maxencefaldor/cax](https://github.com/maxencefaldor/cax) | MIT | Implémentation NCA + CA classiques sur GPU JAX — substrat rapide pour diffusion climatique CA. |
| **ASAL (Sakana)** | 2024 | [SakanaAI/asal](https://github.com/SakanaAI/asal) | Apache-2.0 | Foundation-model-as-fitness pour worldgen "intéressant". |
| **Neural MMO 2.0** | 2023 | [neuralmmo](https://github.com/NeuralMMO) | MIT | DSL task/curriculum — utilisable comme harness d'évaluation Genesis. |
| **JaxMARL** | NeurIPS 2024 | [FLAIROx/JaxMARL](https://github.com/FLAIROx/JaxMARL) | Apache-2.0 | API PettingZoo-compatible + rollouts JAX vectorisés ; 12 500× plus rapide qu'un non-JAX. |
| **MettaGrid** | 2024–25 | [Metta-AI](https://github.com/Metta-AI) | MIT | Reward-sharing kinship ("love-as-reward") pour modéliser familles/tribus. |
| **Avida** | 2025 (ontology in *Sci Data* 2023) | [devosoft/avida](https://github.com/devosoft/avida) | GPL-2.0 | Ontologie controlled-vocabulary pour logs de lignée machine-readable. |
| **Dwarf Fortress** (design docs) | 2002–en cours | wiki | — | Worldgen en deux phases : géologie déterministe puis histoire stochastique avec journal d'événements. |
| **Crusader Kings II** (Fåhraeus GDC 2014) | 2014 | — | — | Detecteur de "narrativement intéressant" qui biaise le RNG vers l'amplification. |

> **Top 3 à étudier maintenant :** Project Sid / PIANO, Generative Agents,
> OASIS. Ensemble ils répondent à toutes les questions d'architecture qu'on
> va rencontrer dans les 6 prochains mois (cognition multi-modulaire,
> mémoire épisodique, modularité déterministe à grande échelle).

> **Gap notable** — aucun projet 2024–26 ne combine agents culture-bearing
> + terrain géo réel + couplage climat. C'est un créneau ouvert que Genesis
> Engine peut occuper.

---

## 4. Couche biologie / nutrition / anthropologie

### Espèces et traits

- **GBIF Occurrence** ([gbif.org](https://www.gbif.org)) — 2.6 G+ records géoréférencés ; loader `pygbif`. CC0 / CC-BY pour ~80 % des records.
- **IUCN Red List API v4** — statut de conservation + range ; ~160 k taxons assesssés ; token requis.
- **TRY Plant Trait Database v6** — ~15 M records de traits sur ~280 k taxons végétaux ; CC-BY 4.0 (public) avec request.
- **EltonTraits** — diet/foraging/activité pour ~9 993 oiseaux + ~5 400 mammifères ; CC0.
- **AmphiBIO** — 6 776 amphibiens ; CC-BY 4.0.
- **PanTHERIA** — 30 variables d'histoire de vie pour 5 416 mammifères.
- **AnAge / HAGR** — longévité, croissance, reproduction de ~4 000 vertébrés.

### Plantes / agriculture

- **EcoCrop (FAO/GAEZ)** — seuils climatiques pour ~2 500 cultures ; loader `ecocrop` PyPI.
- **USDA PLANTS** — ~50 k plantes N. américaines ; domaine public US.
- **Open Tree of Life** — phylogénie synthétique de ~2.6 M tips ; CC0 ; loader `opentree`.

### Physiologie humaine

- **USDA FoodData Central** ([fdc.nal.usda.gov](https://fdc.nal.usda.gov)) — ~400 k aliments × ~150 nutriments ; domaine public US ; API key gratuite.
- **Mifflin-St Jeor BMR** (Am J Clin Nutr 1990 ; doi:10.1093/ajcn/51.2.241). Formule pure : `BMR_M = 10·kg + 6.25·cm − 5·age + 5`, `BMR_F = 10·kg + 6.25·cm − 5·age − 161`. À multiplier par PAL (FAO/WHO/UNU 2004).
- **WHO Growth Standards / Reference 5–19** — paquet officiel `anthro` (2024) ; z-scores LMS pour poids/taille/BMI selon âge et sexe.
- **ANSUR II** — 93 dimensions anthropométriques sur 6 068 soldats US ; DoD public.

### Langues et culture

- **PHOIBLE 2.0** — 3 020+ inventaires phonologiques sur ~2 186 langues ; CC-BY-SA-3.0 ; CSV direct sur GitHub.
- **WALS Online** — 2 679 langues × 192 traits structurels ; CC-BY 4.0 ; loader `pycldf`.
- **Glottolog 5.x** — catalogue de 26 000+ languoids avec généalogie ; CC-BY 4.0.
- **Standard Cross-Cultural Sample (SCCS)** — 186 sociétés pré-industrielles × ~2 000 variables.
- **D-PLACE** ([d-place.org](https://d-place.org)) — agrège SCCS + EA + Binford H-G + WNAI, croisé avec Glottolog + géo ; CC-BY 4.0.

### Maladies et épidémiologie

- **WHO Global Health Observatory** — 2 000+ indicateurs par pays/année ; OData.
- Bibliothèques Python : **`epydemic`** (compartimental sur networkx), **`epipack`** (ODE + stochastique + réseau, maintenu), **`pyross`** (Bayesian + SEIR âgé), **`mesa-epidemics`** (agent-based).

### Matériaux et tech tree

- **Materials Project** — DFT-computed pour 150 k+ composés inorganiques ; CC-BY 4.0 ; client `mp-api` + `pymatgen`.
- **Seshat Global History Databank** ([seshatdatabank.info](https://seshatdatabank.info)) — 1 500+ polities × ~1 500 variables incluant métallurgie/agriculture/militaire ; CC-BY-NC, CSV public. **Seule source machine-readable cross-culturelle pour l'adoption de technologies.**
- Seuils de métallurgie à encoder en dur d'après Tylecote *History of Metallurgy* : Cu @ 1085 °C, Sn alloying, Fe bloomery @ 1200 °C, blast furnace @ 1500 °C.

### Top 3 à intégrer en premier

1. **GBIF + IUCN** — roster planétaire d'espèces avec aires et statut.
2. **USDA FoodData Central + Mifflin-St Jeor** — boucle physiologique minimale viable (calories in/out → croissance, travail, mortalité).
3. **D-PLACE + SCCS + Glottolog** — prior empirique sur la variation culturelle (subsistance, parenté, complexité politique, famille linguistique) déjà géoréférencé.

---

## Phase 5a — Plan de démarrage concret

Le starter de Phase 5a est dans `PHASE5A-PLAN.md`. Résumé : on garde
l'architecture Phase 4 intacte, on ajoute un nouveau module
`engine/earth.py` qui charge Copernicus DEM + WorldCover + HydroRIVERS
pour une bbox lat/lon, et on adapte `world.generate_chunk` pour
optionnellement consommer ces données réelles au lieu du fBm.
Détails dans le plan dédié.

---

## Sources

### Géospatial
- [Copernicus DEM on AWS](https://registry.opendata.aws/copernicus-dem/) · [CHELSA](https://chelsa-climate.org/) · [cdsapi (ECMWF)](https://github.com/ecmwf/cdsapi) · [Resolve Ecoregions 2017](https://ecoregions.appspot.com/) · [ESA WorldCover](https://esa-worldcover.org/en/data-access) · [HydroSHEDS](https://www.hydrosheds.org/products) · [SoilGrids](https://soilgrids.org/) · [Natural Earth](https://www.naturalearthdata.com/)

### Cognition
- [Generative Agents (arXiv:2304.03442)](https://arxiv.org/abs/2304.03442) · [Voyager (arXiv:2305.16291)](https://arxiv.org/abs/2305.16291) · [Project Sid (arXiv:2411.00114)](https://arxiv.org/abs/2411.00114) · [SOTOPIA](https://github.com/sotopia-lab/sotopia) · [DreamerV3 (Nature 2025)](https://github.com/danijar/dreamerv3) · [Letta](https://github.com/letta-ai/letta) · [LangGraph](https://github.com/langchain-ai/langgraph) · [V-JEPA 2](https://github.com/facebookresearch/vjepa2) · [Genie 3](https://deepmind.google/blog/genie-3-a-new-frontier-for-world-models/) · [SIMA 2 (arXiv:2512.04797)](https://arxiv.org/abs/2512.04797)

### Prior art
- [OASIS (CAMEL-AI)](https://github.com/camel-ai/oasis) · [AgentTorch](https://github.com/AgentTorch/AgentTorch) · [Flow-Lenia](https://arxiv.org/abs/2506.08569) · [JaxLife](https://github.com/luchris429/jaxlife) · [CAX (ICLR 2025)](https://github.com/maxencefaldor/cax) · [ASAL](https://github.com/SakanaAI/asal) · [Neural MMO](https://neuralmmo.github.io) · [JaxMARL](https://github.com/FLAIROx/JaxMARL) · [MettaGrid](https://github.com/Metta-AI) · [Avida ontology](https://www.nature.com/articles/s41597-023-02514-3)

### Bio / anthro
- [GBIF](https://www.gbif.org) · [IUCN Red List API v4](https://api.iucnredlist.org) · [USDA FoodData Central](https://fdc.nal.usda.gov) · [Mifflin & St Jeor 1990](https://doi.org/10.1093/ajcn/51.2.241) · [WHO Anthro](https://www.who.int/tools/child-growth-standards) · [PHOIBLE](https://phoible.org) · [WALS](https://wals.info) · [Glottolog](https://glottolog.org) · [D-PLACE](https://d-place.org) · [Materials Project](https://materialsproject.org) · [Seshat Databank](https://seshatdatabank.info)
