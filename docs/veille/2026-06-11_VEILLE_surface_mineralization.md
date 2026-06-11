# WORLD_VEILLE_REPORT — 2026-06-11 (cycle Substrate)

```yaml
WORLD_VEILLE_REPORT:
  date: "2026-06-11"
  duree_recherche: "~25 min"
  axe: "Géologie procédurale & minéraux (RECHERCHE 3) + Découverte agent (SYSTÈME F)"

  contexte_decisif:
    - "Le delta-audit 2026-06-10 (native/world-engine/AUDIT-DELTA-2026-06-10.md §D1)
       a formalisé un MORATOIRE : pas de nouvelle Wave d'OBSERVATEUR (read-only
       wrappant sim.step) tant que Phase A < 5/7 ✅ + 1 item Phase B mergé."
    - "Le backlog moteur (Phase A2/A3/A4/A5/A7, Phase B B1–B8) est 100 % en RUST,
       et l'environnement n'a NI cargo NI rustc (cf. reference_env_no_cargo) : un
       changement Rust ne serait pas compilable/vérifiable ici (CI = vérité)."
    - "Décision : livrer une CAPACITÉ (signal de monde interrogeable que les
       agents consomment pour AGIR) — pas un observateur — dans le runtime Python
       qui exécute réellement la sim, vérifiable par pytest + smoke. Respecte le
       moratoire, l'émergence absolue, et fait avancer la couche capacité côté
       vérifiable. Cible : SYSTÈME C (color_hint) + SYSTÈME F (découverte visuelle)."

  decouvertes:
    - id: D1
      techno: "Gossan / chapeau de fer — expression géochimique de surface des sulfures"
      source: "https://ozgeology.com/en-us/blogs/news/gossans-rusty-clues-to-hidden-ore-beneath-the-surface ; https://www.sciencedirect.com/topics/earth-and-planetary-sciences/gossan"
      telecharge: false
      applicable_a: "engine.surface_mineralization (nouveau) — SYSTÈME C/F"
      gain_estime: "+1 capacité agent réelle : découverte visuelle émergente de minerais (le monde cesse d'être muet sur ses ressources)"
      action: COMBO_TODAY
      note: "Les sulfures (pyrite, chalcopyrite) s'oxydent en surface → chapeau de
             fer : limonite (brun), hématite (rouge), jarosite (jaune). Les
             prospecteurs lisent ces couleurs depuis l'antiquité pour trouver
             Au/Cu/Ag/Zn. Couleurs : rouge=hématite, jaune=jarosite, brun=limonite,
             + tâches vert malachite / bleu azurite (cuivre)."

    - id: D2
      techno: "Malachite/azurite — signature cuivre de surface (« neon sign flashing copper »)"
      source: "https://discoveryalert.com.au/gossans-mineral-exploration-importance-2025/ ; https://uwaterloo.ca/wat-on-earth/news/oxidized-zone-minerals"
      telecharge: false
      applicable_a: "groupe d'expression 'copper' du module"
      gain_estime: "signal diagnostique vert vif (RGB 80,140,70, aligné crate Rust genesis-geology)"
      action: COMBO_TODAY

    - id: D3
      techno: "Limonite / jarosite / goethite — palette d'oxydation Fe(III)"
      source: "https://en.wikipedia.org/wiki/Limonite ; https://en.wikipedia.org/wiki/Jarosite"
      telecharge: false
      applicable_a: "groupe d'expression 'gossan' (fer / chapeau de fer)"
      gain_estime: "couleur véridique brun-rouille pour les corps Fe peu profonds"
      action: COMBO_TODAY

    - id: D4
      techno: "Placers alluviaux (or) + efflorescence saline + croûtes de soufre fumerolliennes"
      source: "veille générale gossan/exploration (synthèse multi-sources ci-dessus)"
      telecharge: false
      applicable_a: "groupes 'gold_placer', 'salt', 'sulfur'"
      gain_estime: "couvre les chaînes de découverte or/sel/soufre du SYSTÈME F"
      action: COMBO_TODAY

    - id: D5
      techno: "Rust crate genesis-geology::sample_surface (color_hint, Wave 43, déjà au repo)"
      source: "native/world-engine/crates/geology/ ; smoke p113"
      telecharge: false
      applicable_a: "concordance visuelle Python↔Rust"
      gain_estime: "le module Python REND LIVE ce que le crate Rust ne fait qu'inspecter statiquement (p113 = grep de source). On aligne RGB (Malachite=[80,140,70])."
      action: COMBO_TODAY
      note: "Le crate Rust n'est PAS branché à la sim live (backend bridge = 'terrain').
             La sim Python n'avait donc AUCUN indice de surface. Comblé aujourd'hui
             côté runtime vérifiable."

  cve_stack:
    - "aucune CVE applicable — pas de nouvelle dépendance (numpy déjà présent)."

  paper_du_jour:
    titre: "Gossans as surface geochemical expressions of supergene sulphide oxidation"
    url: "https://www.sciencedirect.com/topics/earth-and-planetary-sciences/gossan"
    technique: "Cartographie couleur→minéral de la zone d'oxydation supergène ;
                profondeur d'expression liée au battement de nappe / zone vadose."
    effort: "~3 h · complexité 2/5"

  world_model_updates:
    cosmos: "aucune nouveauté retenue ce cycle (axe géochimie, pas world-model)"
    genie3: "aucune"
    autre: "aucun — cycle focalisé substrat géologique"

  combo_retenu:
    techno: "Expression géochimique de surface (gossan/malachite/jarosite/placer/sel/soufre)"
    cible: "engine.surface_mineralization (runtime Python live)"
    gain: "+1 capacité agent : découverte minérale visuelle émergente, invariant
           « le monde ne ment jamais » prouvé (cue ⇒ minerai peu profond réel) ;
           boucle prospecter→creuser→obtenir vérifiée end-to-end ; coût tick nul."
    adr_requis: false   # dérivé du substrat géologique (PIPELINE_LAYER L1) — pas de décision architecturale
    couche: "Substrate"
    moratoire: "CONFORME — capacité (signal actionnable), pas un *_observer.py.
                N'incrémente pas le compteur de Waves observateurs."
```

## Pourquoi ce combo aujourd'hui (et pas un observateur de plus)

La couche d'**observation scientifique** (14 observateurs read-only, Waves 49→63)
mesure de plus en plus finement un monde dont les **capacités d'action restent
intactes depuis 25 jours** (audit §D1, « observer treadmill »). Le moratoire
interdit une Wave 64 observateur. Le backlog moteur est en Rust (non compilable
ici). La bonne action restante : une **capacité** côté runtime Python vérifiable.

`surface_mineralization` est exactement cela : avant lui, un agent n'avait **aucun
moyen de découvrir par la vue** un gisement enfoui — l'action `MINE` partait d'une
profondeur par défaut (3 m), à l'aveugle. Le monde portait la ressource mais
restait **muet**. Désormais il **parle en couleurs véridiques** : vert = cuivre
dessous, brun-rouille = chapeau de fer, jaune = soufre, blanc = sel, doré = placer.
L'agent voit, se souvient, creuse — **l'émergence est respectée** : on n'a jamais
dit « c'est du cuivre », on a rendu le vert détectable (cf. méta-règle du prompt
Substrate). « Le monde est plus vrai ce soir qu'il ne l'était ce matin. »
