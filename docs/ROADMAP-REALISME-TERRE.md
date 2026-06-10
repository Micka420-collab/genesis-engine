# Roadmap réalisme Terre — Genesis Engine

**Source de vérité** pour tous les pourcentages « réalisme Terre » du dépôt.  
**Dernière mise à jour :** 10 juin 2026 (Wave 62 — hypsométrie / maturité de paysage : courbe + intégrale hypsométriques de Strahler 1952 à l'échelle de la carte sur le relief émergent `elevation_m`. Invariant pivot **identité de Pike-Wilson** `trapz(courbe) == ratio élévation-relief` (résidu réel 8,7e-05) ; invariance affine exacte de HI, rampe linéaire HI=0,5, étages youthful/mature/monadnock + skewness signée. Généralise le HI scalaire *par bassin* déjà exposé par la Wave 49. Antérieur : Wave 61 — flexure lithosphérique élastique, généralisation d'Airy (local) vers Vening-Meinesz (régional), plaque mince D∇⁴w + (ρ_m−ρ_c)g·w = q résolue spectralement, limite d'Airy à Te=0).

---

## Score global officiel : **~78,9 %**

| Ce que vous voyiez ailleurs | Signification correcte |
|-----------------------------|------------------------|
| **~68 %** ou **~74 %** | Anciennes estimations ou moyennes partielles — **à ne plus utiliser** |
| **~80 %** | **Objectif cible** utilisateur, ou score **climat / biomes** seul — **pas** le global |
| **~76 %** | Ancienne moyenne (Wave 49) — **remplacée** par ~77 % après Waves 50–51 (géologie) |
| **~77 %** | Moyenne Wave 53 — **remplacée** par ~78 % après Wave 54 (géologie 64→66) |
| **~78,9 %** | **Moyenne des 7 dimensions** ci-dessous (référence unique) — 78,4 % (Wave 57) → 78,6 % (Wave 59 : isostasie d'Airy, géologie 70→71) → 78,7 % (Wave 61 : flexure élastique, géologie 71→72) → **78,9 %** après Wave 62 (hypsométrie, géologie 72→73) |

**Recalcul transparent :**  
(80 + 73 + 73 + 76 + 82 + 86 + 82) ÷ 7 = **78,86 %** → arrondi **~78,9 %**. Géologie 58 → 61 (Wave 50 cryoclastie) → **64** (Wave 51 datation absolue radiométrique) → **66** (Wave 54 compaction diagénétique : Terzaghi, porosité φ(σ′)) → **68** (Wave 56 géotherme + faciès métamorphiques) → **70** (Wave 57 lit mobile / transport sédimentaire Exner : ΣE=ΣD+export) → **71** (Wave 59 isostasie d'Airy : racine crustale, Moho et épaisseur de croûte émergentes, invariant équipression résidu ≈ 1e-16) → **72** (Wave 61 flexure lithosphérique élastique : compensation régionale Vening-Meinesz, filtre flexural Φ(k), limite d'Airy exacte à Te=0, lissage régional prouvé par Parseval) → **73** (Wave 62 hypsométrie / maturité de paysage : courbe + intégrale de Strahler 1952 à l'échelle carte, identité de Pike-Wilson `trapz(courbe)==HI` comme invariant, étages youthful/mature/monadnock). Hydrologie 70 → **72** (Wave 53 routage de débit LTI) → **73** (Wave 57 boucle eau→sédiment→relief fermée). Le saut suivant (érosion GPU dynamique pleinement transitoire, Te variable / admittance gravimétrique) reste pour 75 %+ sur ces dimensions.

> L’objectif **80 % global** (simulation « publication-grade ») reste une **cible** : il faudrait NWP 3D, hydrologie bassin complet, géologie dynamique GPU, et WorldGraph Rust en hot path production.

---

## Grille de maturité (7 dimensions)

| Dimension | % | Justification | Gap vers 80 % |
|-----------|---|---------------|---------------|
| Climat / biomes | **80** | Circulation L1 + colonne 3D + GraphCast-lite prior + vent 2D | NWP 3D numérique, validation Beck 2018 |
| Géologie / relief | **73** | Tectonique live + stratigraphie + **datation relative** (`age_ma`) + cryoclastie (Wave 50) + **datation absolue radiométrique** (Wave 51) + **compaction diagénétique** (Wave 54 : Terzaghi σ′, porosité φ(σ′)) + **géotherme + faciès métamorphiques** (Wave 56 : T(z), grade Barrovien, branche haute-P) + **lit mobile / transport sédimentaire Exner** (Wave 57 : capacité stream-power sur le débit LTI, ΣE=ΣD+export) + **isostasie d'Airy** (Wave 59 : racine crustale r = ρ_c/(ρ_m−ρ_c)·h, Moho émergent, invariant équipression résidu ≈ 1e-16) + **flexure lithosphérique élastique** (Wave 61 : plaque mince D∇⁴w + Δρg·w = q résolue spectralement, filtre Φ(k), α ≈ 89 km à Te 25 km, limite d'Airy exacte à Te=0, bilan mode zéro résidu ≈ 1e-17) + **hypsométrie / maturité de paysage** (Wave 62 : courbe + intégrale de Strahler 1952 à l'échelle carte, identité de Pike-Wilson `trapz(courbe)==HI`, étages youthful/mature/monadnock, invariance affine) | Érosion GPU dynamique pleinement transitoire ; Te spatialement variable + admittance gravimétrique |
| Écologie / hydrologie | **73** | Earth Console `sv1d` + overlay flux 2D ; **Wave 49 quantification réseau** (Strahler, Horton Rb/Rl, drainage density, intégrale hypsométrique) ; **Wave 53 routage de débit LTI** (conservation de masse exacte) ; **Wave 55 hydrogramme transitoire** (réservoir linéaire) ; **Wave 57 boucle eau→sédiment→relief fermée** (Exner sur graphe D8) | Biogéochimie, hydrologie de bassin complète, érosion GPU |
| Sociétés / agents | **76** | NEAT + latent_action ; memetic + lexique ; construction émergente ; parole `/api/audio` | `ActionKind` encore enum ; pas de LLM tier-2 |
| Rendu visuel | **82** | Earth Console globe + iso 2.5D + humains + ombres soleil + 2D lite | Volumétrique GPU, photoréalisme |
| Observation IA | **86** | Earth Console SSE + replay JSONL + observer_feed + WebGPU agents | Fog-of-war mmap Rust, multi-tenant |
| Pont Python↔Rust | **82** | GENM macro-bridge + mutations write-back + snapshot zstd | WorldGraph hot path prod |

**Moyenne (global) :** **~78,9 %** (78,4 % Wave 57 → 78,6 % Wave 59 → 78,7 % Wave 61 → 78,9 % après Wave 62)

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
| Flexure lithosphérique élastique (Vening-Meinesz, filtre Φ(k), limite d'Airy) | ✅ | `flexure_observer.py`, smoke `p130`, tests `test_flexure_observer.py` (15) |
| Köppen FAIR + MultiRateCoupler | ✅ | `koeppen_grid.py`, `multi_rate_coupler.py` |
| Pont Rust GENM + write-back | ✅ | `macro-bridge`, `macro_grid_export.py` |

---

## Prochain sprint (vers 80 % global)

1. **CI maturin** : wheel + smoke verts → monter WorldGraph en prod.
2. **Köppen** : validation 50 stations (Beck 2018).
3. **Hydrologie** : LBM 2D ou D8 accumulation cross-macro.
4. **Géologie** : datation relative ✅, cryoclastie ✅, datation absolue ✅, compaction diagénétique ✅ (Wave 54), géotherme + faciès métamorphiques ✅ (Wave 56), lit mobile Exner ✅ (Wave 57), isostasie d'Airy ✅ (Wave 59), flexure lithosphérique élastique ✅ (Wave 61 : Vening-Meinesz régional, filtre Φ(k)), hypsométrie / maturité de paysage ✅ (Wave 62 : courbe + intégrale de Strahler, identité de Pike-Wilson) → reste **érosion GPU pleinement transitoire** et **Te spatialement variable + admittance gravimétrique** comme prochains paliers.
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
python -m pytest tests/ -q          # 361 tests (juin 2026)
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
