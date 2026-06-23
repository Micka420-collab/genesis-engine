# Veille technologique — 2026-06-23 (J+13 run #3, `rock_canvas`)

**Mode :** scheduled task `genesis-engine--world-realism-system-v20` (Substrate
Layer), continuation manuelle (« continue »), user présent. **Contrainte env :**
`cargo`/`rustc` absents ([ADR-0008](../../adr/0008-python-rust-frontier.md), D7) ;
Python 3.14 seul ; CI = vérité pour toute affirmation Rust. La veille **précède**
tout code (règle d'or). Internet libre disponible.

---

## ÉTAPE 0 — Veille (5 axes + ciblée archéologie du support pariétal)

### Axes 1–5 (IA / Rust / crypto / infra / arXiv)
Inchangés depuis J+13 run #1/#2 : **0 combo externe intégrable** (Bevy 0.18,
multi-agent LLM tier-2, ML-KEM-768, Neo4j vecteurs natifs, mémoire agent
LightMem/Memory3 — tous **gated** cargo / LLM / endpoint). Aucune CVE à surface
live Genesis (aucun endpoint réseau prod ; PQC non compilée).

### Axe substrat — la physique du SUPPORT pariétal (la physique de C20)

C18 a livré le **pigment** (la matière de la marque) ; il manquait le **support**
(la paroi qui *tient* la marque). La veille a donc porté sur **pourquoi** l'art
pariétal a survécu — recherche ciblée *« why cave paintings survived limestone
calcite veil pigment adhesion porosity rock substrate Lascaux preservation »* —
convergence des sources :

- **Substrat = calcaire poreux** : *« the limestone cave walls themselves provided
  a suitable porous substrate for the mineral pigments to bond effectively »*. La
  porosité fine du carbonate **agrippe** le pigment minéral (≠ granite, peu poreux).
- **Voile de calcite (préservation)** : *« the pigments were overlain by whitish
  calcite deposits … a protective veil »*. L'eau de grotte saturée en CaCO₃ dépose
  un film de calcite qui **scelle** la peinture → permanence (Lascaux ~17 000 ans).
- **Environnement scellé/stable** : *« the sealed limestone environment maintained
  stable temperature and humidity, preventing the oxidation and fading »*. La
  **stabilité** du site (paroi saine, abritée) — pas seulement le matériau — décide
  de la survie de la marque.
- **Corollaire (le mensonge)** : une paroi calcaire **instable** (dissolution
  karstique active, gélifraction) **détruit** la marque (écaillage / desquamation)
  même si le calcaire « accepte » le pigment. *« Looks markable ≠ holds a mark. »*

→ **DIRECTEMENT APPLICABLE** : ces faits calibrent la SSOT `canvas_quality` —
**adhésion** (porosité du carbonate, byte-égale au support `bedrock_calcite` de
`engine.art_discovery`, pont L1↔L4) × **persistance environnementale** (réemploi
des états d'altération de C6 `limestone_outcrop` : SOUND → voile de calcite,
durable ; KARST/FROST → écaillage, la marque ne tient pas). Aucune constante n'est
inventée.

### Le combo interne du jour — combler le trou L1 sous l'art L4

`engine.art_discovery` (L4 Feedback, Wave 13) modélise déjà l'**acte** de dessin
(pigment + surface + N traits → empreinte → archétype émergent) avec un dictionnaire
**abstrait** `PAINTABLE_SURFACES` (`bedrock_calcite` 0,95, `bedrock_granite` 0,55,
`bedrock_sandstone` 0,80…). **Mais rien ne rend perceptible, par lieu, QUELLE paroi
est là, ni si une marque y DURE.** C'est exactement le trou que C20 comble — comme
C18 a comblé « quel pigment est ici » (la matière), C20 comble « quel support est
ici, et la marque y tiendra-t-elle » (le substrat). C20 **fonde** la chaîne de
caractères abstraite de l'art L4 dans la géologie + le climat réels (pont vérifié
par un test de contrat L1↔L4). Le geste (tracer, signifier) reste **émergent** —
c'est `art_discovery` qui le gère ; C20 n'expose que la **vérité physique du mur**.

---

## WORLD_VEILLE_REPORT

```yaml
date: "2026-06-23"
duree_recherche: "~16 min (5 axes inchangés + ciblée archéologie du support pariétal)"

decouvertes:
  - id: D1
    techno: "Support pariétal = calcaire poreux ; adhésion du pigment par porosité fine (Lascaux/Altamira/Cosquer)"
    source: "EBSCO Lascaux ; RSC Education Prehistoric pigments ; Bradshaw Foundation ; archeologie.culture.gouv.fr/lascaux"
    telecharge: false
    applicable_a: "engine.rock_canvas (Cap. C20) — SSOT canvas_quality (adhésion), pont L1↔L4 vers art_discovery.PAINTABLE_SURFACES"
    gain_estime: "réalisme : le SUPPORT du dessin devient physiquement vrai (porosité→adhésion, calcite→voile protecteur)"
    action: "COMBO_TODAY"
  - id: D2
    techno: "Voile de calcite + environnement scellé/stable = persistance ; karst/gel = écaillage (la marque ne dure pas)"
    source: "EBSCO Lascaux ; Wikipedia Lascaux ; World History Encyclopedia Lascaux Cave"
    telecharge: false
    applicable_a: "engine.rock_canvas — persistance environnementale (réemploi des états SOUND/KARST/FROST de C6)"
    gain_estime: "mensonge rendu visible #11 : paroi pâle conspicue mais karst/gel → la marque s'écaille (looks markable ≠ holds a mark)"
    action: "COMBO_TODAY"

cve_stack:
  - "Aucune CVE critique à surface live Genesis (aucun endpoint réseau prod ; PQC non compilée)."

paper_du_jour:
  titre: "rien de nouvel applicable cargo-less sous 7 j (inchangé J+13)"

world_model_updates:
  cosmos: "aucune (gated cargo)"
  autre: "Bevy 0.18 / ML-KEM-768 / Neo4j vecteurs / mémoire agent — BACKLOG ROADMAP P5"

combo_retenu:
  techno: "Archéologie du support pariétal (D1) + voile de calcite / stabilité (D2)"
  cible: "engine.rock_canvas — la paroi carbonatée C6 devient un SUPPORT de marque perceptible, fonde le bedrock_calcite abstrait de l'art L4"
  gain: "Cap. C20 : 2e brique de l'axe SYMBOLIQUE (le support après le pigment) ; non-fire, non mutant ; pont L1↔L4 vérifié."
  adr_requis: false   # composition pure (D8, 14e) ; non mutant (D10 gelé)
```

---

## ÉTAPE 1 — COMBO retenu

- **COMBO_RETENU : aucun combo *externe* intégrable** (tous gated — inchangé).
- **COMBO_INTERNE (le vrai combo du jour)** : C6 `limestone_outcrop` (la paroi
  carbonatée + ses états d'altération SOUND/KARST/FROST) **×** l'archéologie du
  support pariétal (D1/D2) **×** le pigment C18 (pour le contraste/visibilité).
  Effet **« une vérité de substrat, deux lectures »** : C6 calculait l'altération
  pour la **pierre de taille** (se dresse-t-elle en blocs ?) ; C20 relit la **même**
  vérité pour une **autre** question (une marque peinte y **dure**-t-elle ?). SOUND
  → voile de calcite, durable ; KARST/FROST → écaillage.
- **COMBO_BACKLOG :** Bevy 0.18 / multi-agent LLM / ML-KEM-768 / Neo4j / mémoire
  agent (déjà ROADMAP P5).

**Décision :** Cap. **C20 `rock_canvas`** — la **2ᵉ brique de l'axe symbolique**
(le **support** de la marque, après le **pigment** C18). **Non-fire** (D9 1 → 0
après le fire-based C19 — alternance honorée), **non mutant** (D10 gelé),
**D8 par composition** (14ᵉ ; `PY_TO_RUST` reste 15, hors `*_outcrop.py`). **Fonde
le `bedrock_calcite` abstrait de l'art L4** dans la géologie réelle (pont L1↔L4
testé). Mensonge rendu visible **#11** : une paroi pâle conspicue mais
karst-fissurée / gélive **n'tient pas** la marque (elle s'écaille) — *« looks
markable ≠ holds a lasting mark »*.

---

## Sources

- [Lascaux Cave Paintings — EBSCO Research Starters](https://www.ebsco.com/research-starters/anthropology/lascaux-cave-paintings)
- [Prehistoric pigments — RSC Education](https://edu.rsc.org/resources/prehistoric-pigments/1540.article)
- [The Cave Art Paintings of the Lascaux Cave — Bradshaw Foundation](https://www.bradshawfoundation.com/lascaux/)
- [The techniques — Lascaux cave (Ministère de la Culture)](https://archeologie.culture.gouv.fr/lascaux/en/techniques)
- [Lascaux — Wikipedia](https://en.wikipedia.org/wiki/Lascaux)
- [Lascaux Cave — World History Encyclopedia](https://www.worldhistory.org/Lascaux_Cave/)
