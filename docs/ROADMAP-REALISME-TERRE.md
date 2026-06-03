# Roadmap réalisme Terre — Genesis Engine

**Source de vérité** pour tous les pourcentages « réalisme Terre » du dépôt.  
**Dernière mise à jour :** 3 juin 2026 (Wave 59 — isostasie d'Airy : racine crustale émergente r = ρ_c/(ρ_m−ρ_c)·h sous les reliefs, anti-racine océanique, profondeur du Moho et épaisseur de croûte dérivées du champ d'altitude émergent ; invariant équipression à la profondeur de compensation, résidu ≈ 1e-16. Intègre aussi Wave 57 (lit mobile Exner) et Wave 58 (open-endedness Bedau–Packard) livrées dans la nuit).

---

## Score global officiel : **~78 %**

| Ce que vous voyiez ailleurs | Signification correcte |
|-----------------------------|------------------------|
| **~68 %** ou **~74 %** | Anciennes estimations ou moyennes partielles — **à ne plus utiliser** |
| **~80 %** | **Objectif cible** utilisateur, ou score **climat / biomes** seul — **pas** le global |
| **~76 %** | Ancienne moyenne (Wave 49) — **remplacée** par ~77 % après Waves 50–51 (géologie) |
| **~77 %** | Moyenne Wave 53 — **remplacée** par ~78 % après Wave 54 (géologie 64→66) |
| **~78,6 %** | **Moyenne des 7 dimensions** ci-dessous (référence unique) — 78,0 % (Wave 56) → 78,4 % (Wave 57 : géologie 68→70, hydrologie 72→73) → **78,6 %** après Wave 59 (isostasie d'Airy, géologie 70→71) |

**Recalcul transparent :**  
(80 + 71 + 73 + 76 + 82 + 86 + 82) ÷ 7 = **78,57 %** → arrondi **~78,6 %**. Géologie 58 → 61 (Wave 50 cryoclastie) → **64** (Wave 51 datation absolue radiométrique) → **66** (Wave 54 compaction diagénétique : Terzaghi, porosité φ(σ′)) → **68** (Wave 56 géotherme + faciès métamorphiques) → **70** (Wave 57 lit mobile / transport sédimentaire Exner : ΣE=ΣD+export) → **71** (Wave 59 isostasie d'Airy : racine crustale, Moho et épaisseur de croûte émergentes, invariant équipression résidu ≈ 1e-16). Hydrologie 70 → **72** (Wave 53 routage de débit LTI) → **73** (Wave 57 boucle eau→sédiment→relief fermée). Le saut suivant (érosion GPU dynamique pleinement transitoire, flexure lithosphérique élastique) reste pour 75 %+ sur ces dimensions.

> L’objectif **80 % global** (simulation « publication-grade ») reste une **cible** : il faudrait NWP 3D, hydrologie bassin complet, géologie dynamique GPU, et WorldGraph Rust en hot path production.

---

## Grille de maturité (7 dimensions)

| Dimension | % | Justification | Gap vers 80 % |
|-----------|---|---------------|---------------|
| Climat / biomes | **80** | Circulation L1 + colonne 3D + GraphCast-lite prior + vent 2D | NWP 3D numérique, validation Beck 2018 |
| Géologie / relief | **71** | Tectonique live + stratigraphie + **datation relative** (`age_ma`) + cryoclastie (Wave 50) + **datation absolue radiométrique** (Wave 51) + **compaction diagénétique** (Wave 54 : Terzaghi σ′, porosité φ(σ′)) + **géotherme + faciès métamorphiques** (Wave 56 : T(z), grade Barrovien, branche haute-P) + **lit mobile / transport sédimentaire Exner** (Wave 57 : capacité stream-power sur le débit LTI, ΣE=ΣD+export) + **isostasie d'Airy** (Wave 59 : racine crustale r = ρ_c/(ρ_m−ρ_c)·h, anti-racine océanique, Moho et épaisseur de croûte dérivés du champ d'altitude émergent, invariant équipression à la profondeur de compensation, résidu ≈ 1e-16) | Érosion GPU dynamique pleinement transitoire ; flexure lithosphérique élastique (Airy → Vening-Meinesz) |
| Écologie / hydrologie | **73** | Earth Console `sv1d` + overlay flux 2D ; **Wave 49 quantification réseau** (Strahler, Horton Rb/Rl, drainage density, intégrale hypsométrique) ; **Wave 53 routage de débit LTI** (conservation de masse exacte) ; **Wave 55 hydrogramme transitoire** (réservoir linéaire) ; **Wave 57 boucle eau→sédiment→relief fermée** (Exner sur graphe D8) | Biogéochimie, hydrologie de bassin complète, érosion GPU |
| Sociétés / agents | **76** | NEAT + latent_action ; memetic + lexique ; construction émergente ; parole `/api/audio` | `ActionKind` encore enum ; pas de LLM tier-2 |
| Rendu visuel | **82** | Earth Console globe + iso 2.5D + humains + ombres soleil + 2D lite | Volumétrique GPU, photoréalisme |
| Observation IA | **86** | Earth Console SSE + replay JSONL + observer_feed + WebGPU agents | Fog-of-war mmap Rust, multi-tenant |
| Pont Python↔Rust | **82** | GENM macro-bridge + mutations write-back + snapshot zstd | WorldGraph hot path prod |

**Moyenne (global) :** **~78,6 %** (78,0 % Wave 56 → 78,4 % Wave 57 → 78,6 % après Wave 59)

### Deux moteurs (ne pas confondre avec le global)

| Stack | % | Note |
|-------|---|------|
| **Continent Python** (Genesis, climat, civ, Earth Console) | **~78** | Aligné sur la moyenne globale ci-dessus |
| **Pont Rust** (GENM, agent-api, Köppen crates) | **82** | Dimension « Pont » — pas le score monde entier |
| **Chunk procgen Rust seul** (sans align Genesis) | **~45** | Intégration partielle — voir [`GOD-ENGINE-ARCHITECTURE.md`](GOD-ENGINE-ARCHITECTURE.md) |

---

## Livrables récents (mai 2026)

| Livrable | Statut | Fichiers |
|----------|--------|----------|
| Earth Console (globe, iso, sky, écoute) | ✅ | `earth_console.html`, `run_earth_console.py`, `docs/EARTH-CONSOLE.md` |
| Monde autonome (dynamo, plaques, construction émergente) | ✅ | `autonomous_world.py`, `emergent_construction.py` |
| Parole agents → SoundField | ✅ | `speech_audio_bridge.py`, `/api/audio`, `/api/languages` |
| GraphCast-lite + prior monde | ✅ | `deepmind_world_prior.py` |
| Datation relative (chronostratigraphie, superposition) | ✅ | `geology.py` (`age_ma`, `stratigraphic_chronology`, `superposition_ok`), smoke `p34` |
| Cryoclastie / frost weathering (Walder & Hallet) | ✅ | `frost_weathering.py`, smoke `p119` |
| Datation absolue radiométrique (multi-systèmes + concordance) | ✅ | `radiometric_dating.py`, smoke `p120`, tests `test_radiometric_dating.py` (19) |
| Watershed observer (Strahler + Horton + drainage density) | ✅ | `watershed_observer.py`, smoke `p118`, tests `test_watershed_observer.py` |
| Routage de débit LTI (ruissellement D8, conservation de masse) | ✅ | `discharge_observer.py`, smoke `p122`, tests `test_discharge_observer.py` (11) |
| Compaction diagénétique + pression lithostatique (Terzaghi, porosité φ(σ′)) | ✅ | `compaction_observer.py`, smoke `p123`, tests `test_compaction_observer.py` |
| Géotherme conductif + faciès métamorphiques (P–T, grade Barrovien, blueschist/éclogite) | ✅ | `geotherm_observer.py`, smoke `p125`, tests `test_geotherm_observer.py` (15) |
| Lit mobile / transport sédimentaire Exner (stream-power, ΣE=ΣD+export) | ✅ | `sediment_observer.py`, smoke `p126`, tests `test_sediment_observer.py` |
| Isostasie d'Airy / racine crustale (Moho, épaisseur de croûte, invariant équipression) | ✅ | `isostasy_observer.py`, smoke `p128`, tests `test_isostasy_observer.py` (12) |
| Köppen FAIR + MultiRateCoupler | ✅ | `koeppen_grid.py`, `multi_rate_coupler.py` |
| Pont Rust GENM + write-back | ✅ | `macro-bridge`, `macro_grid_export.py` |

---

## Prochain sprint (vers 80 % global)

1. **CI maturin** : wheel + smoke verts → monter WorldGraph en prod.
2. **Köppen** : validation 50 stations (Beck 2018).
3. **Hydrologie** : LBM 2D ou D8 accumulation cross-macro.
4. **Géologie** : datation relative ✅, cryoclastie ✅, datation absolue ✅, compaction diagénétique ✅ (Wave 54), géotherme + faciès métamorphiques ✅ (Wave 56), lit mobile Exner ✅ (Wave 57), isostasie d'Airy ✅ (Wave 59 : Moho + épaisseur de croûte émergentes) → reste **érosion GPU pleinement transitoire** et **flexure lithosphérique élastique** (généralisation d'Airy local vers Vening-Meinesz) comme prochains paliers.
5. **Observation** : fog mmap Rust ; reste JSONL live ✅.

**Earth Console (live) :**

```bash
make earth-console
# http://127.0.0.1:8090/ — SSE: GET /api/events/stream
```

---

## Commandes de vérification

```bash
# Python (depuis runtime/)
python -m pytest tests/ -q          # 331 tests (juin 2026)
python scripts/p74_koeppen_harness_smoke.py
python scripts/p86_autonomous_world_smoke.py
python scripts/p87_observer_sky_smoke.py

# Rust (si cargo disponible)
cd native/world-engine
cargo test -p genesis-core -p genesis-biome -p genesis-worldgraph
```

---

## Exemple métriques Köppen (FAIR)

```python
from engine.world_genesis import GenesisParams, generate_world
from engine.koeppen_grid import fair_koeppen_manifest
world = generate_world(GenesisParams(seed=42, resolution=128))
print(fair_koeppen_manifest(world))
```

---

## Références

- Synthèse projet : [`PROJECT-STATUS.md`](../PROJECT-STATUS.md)
- Manifeste : [`EMERGENCE-SIM-v2.md`](EMERGENCE-SIM-v2.md)
- Console : [`EARTH-CONSOLE.md`](EARTH-CONSOLE.md)
- README multilingues (14 langues, score **~76 %**) : FR [`README.md`](../README.md) · EN [`README.en.md`](../README.en.md) · ES [`README.es.md`](../README.es.md) · DE [`README.de.md`](../README.de.md) · PT [`README.pt.md`](../README.pt.md) · IT [`README.it.md`](../README.it.md) · ZH [`README.zh-CN.md`](../README.zh-CN.md) · JA [`README.ja.md`](../README.ja.md) · RU [`README.ru.md`](../README.ru.md) · KO [`README.ko.md`](../README.ko.md) · HI [`README.hi.md`](../README.hi.md) · NL [`README.nl.md`](../README.nl.md) · PL [`README.pl.md`](../README.pl.md) · AR [`README.ar.md`](../README.ar.md)
