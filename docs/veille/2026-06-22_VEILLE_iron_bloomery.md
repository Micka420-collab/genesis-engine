# Veille technologique — 2026-06-22 (J+12 run #2, `iron_bloomery`)

**Mode :** scheduled task `genesis-engine--world-realism-system-v20` (routine
veille-first), run **automatique**, user **absent**. **Contrainte env :**
`cargo`/`rustc` absents ([ADR-0008](../../adr/0008-python-rust-frontier.md), D7) ;
Python 3.14 seul ; CI = vérité pour toute affirmation Rust. La veille **précède**
tout code (règle d'or). **Companion :** veille du jour
[`2026-06-22_VEILLE_food_curing.md`](2026-06-22_VEILLE_food_curing.md) (run sœur
C16) — axes 1/2/3 inchangés ; ce run cible l'**archéométrie du bas-fourneau** (la
physique de C17).

---

## ÉTAPE 0 — Recherche ciblée (la transformation du jour : la réduction du fer)

La capacité du jour est le **bas-fourneau** (réalisation du `reaches_iron_bloomery_temp`
exposé par C12 et explicitement différé par C13). La veille a donc porté sur la
**physique** que le module va calculer — jamais inventer (méta-règle du substrat).

### Axe substrat — métallurgie du fer ancienne (archéométrie)

Deux recherches Web menées (résultats datés, sources ci-dessous) :

1. **« bloomery iron smelting temperature solid state reduction wüstite slag
   fayalite »** — convergence des sources d'archéométallurgie :
   - **Réduction à l'état SOLIDE** : le bas-fourneau opère **~1100–1300 °C**
     (théorique 1150–1200 °C), **sous** le point de fusion du fer (1538 °C). Le CO
     issu de la combustion incomplète du charbon **diffuse** à travers l'oxyde de
     fer chaud et le réduit en métal **sans le fondre** → une **loupe** (bloom)
     spongieuse.
   - **Scorie = fayalite** (`Fe₂SiO₄`), liquidus ~1150–1200 °C, qui **s'écoule** de
     l'éponge ; la **wüstite** (FeO) dendritique signe une atmosphère réductrice.
     La scorie **retient beaucoup de fer** → rendement primitif **lossy** (< 1).
   - La loupe doit être **martelée** (forge de consolidation) pour expulser la
     scorie résiduelle.

2. **« pyrite iron ore red short sulfur brittle bloomery »** — convergence :
   - La **pyrite** (`FeS₂`, riche en fer à 47 %) est un **mauvais** minerai de fer :
     le **soufre est quasi impossible à chasser** au bas-fourneau → loupe
     **cassante à chaud** (*red-short*). Historiquement utilisée pour le soufre,
     **pas** pour le fer.
   - Les **vrais** minerais sont les **oxydes** (hématite `Fe₂O₃`, magnétite
     `Fe₃O₄`), plus abondants et propres.

→ **DIRECTEMENT APPLICABLE** : ces faits calibrent la SSOT `iron_bloom_yield`
(seuil 1200 °C, jamais de fusion, rendement plafonné < 1, fayalite, pyrite
red-short). Aucune constante n'est inventée.

### Axes 1/2/3 (IA / Rust / crypto)

Inchangés depuis la veille C16 du même jour : **0 combo externe intégrable**
(Bevy 0.18, multi-agent LLM tier-2, ML-KEM — tous *gated* cargo/LLM/endpoint).
`CVE-2026-22705` (ML-DSA timing, medium, patchée) sans surface live. Pas de
nouveau paper applicable sous 7 j.

---

## WORLD_VEILLE_REPORT

```yaml
date: "2026-06-22"
duree_recherche: "~15 min (ciblée archéométrie bas-fourneau)"

decouvertes:
  - id: D1
    techno: "Archéométrie du bas-fourneau — réduction solide-état + fayalite"
    source: "Wikipedia Ancient iron production ; npj Heritage Science 2024 ; MDPI Metals 12(8):1307"
    telecharge: false
    applicable_a: "engine.iron_bloomery (Cap. C17) — SSOT iron_bloom_yield"
    gain_estime: "réalisme : la réduction du fer devient physiquement vraie (solide, jamais fondue)"
    action: "COMBO_TODAY"

  - id: D2
    techno: "Pyrite = mauvais minerai de fer (red-short, soufre indéracinable)"
    source: "galleries.com/minerals pyrite ; Britannica pyrite ; Riverborn Knives bloomery I"
    telecharge: false
    applicable_a: "engine.iron_bloomery — la classe sulfure_iron (mensonge #8)"
    gain_estime: "+1 voie au mensonge du gossan : tell rouille → fer sain / red-short / non-fer"
    action: "COMBO_TODAY"

cve_stack:
  - "CVE-2026-22705 (ML-DSA timing, medium, patchée) — aucune surface live Genesis (PQC non compilée)."

paper_du_jour:
  titre: "rien de nouvel applicable sous 7 j (au-delà de l'archéométrie ci-dessus)"

world_model_updates:
  cosmos: "aucune (gated cargo)"
  genie3: "aucune"
  autre: "Bevy 0.18 — BACKLOG cargo (déjà inscrit ROADMAP via la veille C16)"

combo_retenu:
  techno: "Archéométrie bas-fourneau (D1) + pyrite red-short (D2)"
  cible: "engine.iron_bloomery — réalise C12 reaches_iron_bloomery_temp × C1 gossan"
  gain: "Cap. C17 : 2ᵉ métallurgie (âge du fer), 78/144 sites émergents seed 0x42, 0 viol."
  adr_requis: false   # composition pure ; mais 2ᵉ mutation → ouvre crates/MUTATION-FRONTIER.md
```

---

## ÉTAPE 1 — COMBO retenu

- **COMBO_RETENU : aucun combo *externe* intégrable** (cargo / LLM tier-2 gated).
- **COMBO_INTERNE (le vrai combo du jour)** : C12 `forced_draught`
  (`reaches_iron_bloomery_temp`, four ≥1200 °C paroi réfractaire) **×** C1
  `surface_mineralization` (le **chapeau de fer** gossan) **×** le catalogue
  minéral (`yields_per_kg_ore["Fe"]`, `category`). Effet **1+1>2** : la réduction
  effective du fer n'émerge que là où **un four réfractaire ET un gossan ferreux**
  coexistent — exactement comme C13 (cuivre) émergeait de four soufflé × tell vert.
- **COMBO_BACKLOG :** Bevy 0.18 / multi-agent LLM (déjà ROADMAP P5).

**Décision :** Cap. **C17 `iron_bloomery`** — le bas-fourneau du fer, **réalisant**
le potentiel `reaches_iron_bloomery_temp` que C12 différait. 2ᵉ transformation
métallurgique après C13 (cuivre) ; **fire-based** → redémarre D9 (cf. `R-J9r2-1`
qui débloquait le retour au feu après l'alternance C14/C15/C16) ; **2ᵉ mutation**
de l'arc (après `smelt_at` C13) → ouvre `crates/MUTATION-FRONTIER.md` (R-J9-2).

---

## Sources

- [Archaeometallurgical slag / Ancient iron production — Wikipedia](https://en.wikipedia.org/wiki/Ancient_iron_production)
- [Bloomery iron production in the Holy Cross Mountains — npj Heritage Science 2024](https://www.nature.com/articles/s40494-024-01266-6)
- [Analysis on Ancient Bloomery Ironmaking Technology — MDPI Metals 12(8):1307](https://www.mdpi.com/2075-4701/12/8/1307)
- [Why isn't pyrite considered an ore for iron? — discussion](https://www.quora.com/Why-isnt-pyrite-considered-as-the-ore-for-iron)
- [Pyrite (Iron Sulfide) — galleries.com](https://galleries.com/minerals/sulfides/pyrite/pyrite.htm)
- [Bloomery Iron Smelting Part I — Riverborn Knives](https://riverbornknives.com/index.php/2023/02/05/bloomery-iron-smelting-part-i-raw-material-tools-and-concept/)
