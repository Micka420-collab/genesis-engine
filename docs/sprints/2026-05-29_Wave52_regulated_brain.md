# Wave 52 — Décodeur héritable branché dans le cerveau génomique (gated)

**Date:** 2026-05-29 · **Status:** livré (tests + smoke verts) · **Layer:** strong-ALife / G→comportement

> Source de vérité projet : [`PROJECT-STATUS.md`](../../PROJECT-STATUS.md) ·
> file de travail : [`NEXT-SPRINT.md`](../../NEXT-SPRINT.md)

## Motivation (Pattee, côté comportement)

La Wave 47 a livré un décodeur génotype→phénotype **héritable** (`engine.genome_decoder`),
mais l'a explicitement laissé **débranché** du comportement : « wiring it in is a separate,
gated wave ». Voici cette wave.

Le cerveau vivant (`engine.neat_brain`) lit le génome par une règle **fixe, externe,
déclarée par l'observateur** : la tranche cognition `[64, 128)` est passée dans `tanh`
puis tuilée en un MLP 2-couches. C'est *nous* qui avons décidé que ces 64 loci « veulent
dire » les poids de la politique, et cette règle est identique pour chaque individu, pour
toujours — exactement le « niveau de signes dépourvu de dynamique intrinsèque » de Pattee,
mais cette fois côté **comportement** et non côté trait.

## Ce qui est livré

`engine/regulated_brain.py` — module **additif** et **pur** qui laisse le **code
régulateur héritable** R = loci `[192, 256)` réinterpréter la tranche cognition *avant* que
le cerveau ne la lise :

```
P          = decode_phenotype(genome)          # (16,) ∈ (0,1), dépend de R
gain[k]    = 1 + A·(2·P[k] − 1)                # A = 0.6 → gain ∈ (0.4, 1.6)
gain_cog   = tile(gain, 64)                    # un gain par gène cognition
cognition' = cognition · gain_cog              # tranche réinterprétée
```

`regulated_genome_view(genome)` renvoie une **copie** du génome dont la seule tranche
cognition est modulée par le phénotype décodé — pur, déterministe, n'altère jamais l'entrée.

**Branchement gated** dans `engine.neat_brain.genome_decide` : quand
`SimConfig.heritable_brain` est `True`, la décision est prise sur la *vue régulée* ; défaut
`False` → chemin hérité **inchangé**.

### Le code neutre **récupère** le cerveau hérité, octet pour octet

Quand R décode au phénotype neutre P ≡ 0.5, chaque gain vaut exactement 1.0, la vue égale
le génome d'origine, et le cerveau régulé est **identique au bit** au cerveau hérité. La
règle fixe historique n'est donc que le **cas particulier neutre** d'une famille héritable —
et l'évolution peut s'en éloigner. C'est la base formelle de la non-régression (par-dessus
le flag à OFF par défaut).

### Fermeture sémantique vérifiée dans le comportement

Deux génomes **identiques sur toute la région structurelle** S = `[0, 192)` (qui contient la
tranche cognition que le cerveau lit) mais **différant uniquement sur le code régulateur**
R = `[192, 256)` :

- produisent des logits **identiques** sous le cerveau hérité (il ne regarde jamais R) ;
- produisent des logits **différents** sous le cerveau régulé (R réinterprète la cognition).

La signification des gènes cognitifs n'est plus fixée de l'extérieur : elle est portée et
évoluée par l'organisme. Propriété émergente : **pléiotropie comportementale** (un changement
de R repondère plusieurs gènes cognitifs à la fois, jamais assigné à la main).

## Honnêteté sur les gaps restants

1. **Côté construction non fermé.** Ceci ferme le côté *description→interprétation* de la
   boucle de Pattee **pour le comportement** (le code gène→politique est héritable). Ça ne
   ferme **pas** le côté *construction* (auto-reconstruction von Neumann du décodeur) —
   travail futur, non revendiqué.

2. **Borne EXPLORE.** L'offset de marche EXPLORE dans `neat_brain._targets_for_action` lit
   encore le latent du génome **brut** ; la vue régulée gouverne *quelle* action est choisie,
   pas ce détail de locomotion.

3. **Le cerveau génomique n'est pas (encore) atteint par `Simulation.step()`.** Constat
   honnête de cette wave : `sim.py` fait `from engine.cognition import decide` à l'import, si
   bien que le patch de `cognition.decide` posé par `install_emergent_cognition`
   (via `wire_emergence_v2`) **n'atteint pas** la boucle vivante de `Simulation.step`. Le
   cerveau génomique `genome_decide` n'est donc joignable qu'en appelant `cognition.decide`
   dynamiquement. Le branchement de cette wave agit **dans `genome_decide`** (la fonction de
   décision de la politique génomique) — vérifié : le flag y change la décision pour 8/8
   founders réels. Recâbler `Simulation.step` sur le cerveau génomique est un correctif
   **pré-existant et hors périmètre** (risque de régression sur la suite) ; signalé séparément.

## Validation

- `tests/test_regulated_brain.py` — **11/11** verts (vue additive, déterminisme/pureté,
  bornes de gain, récupération octet-pour-octet du cerveau neutre, fermeture sémantique
  comportementale, pléiotropie, gating du flag, founders réels, `genome_decide` honore le flag).
- `scripts/p121_regulated_brain_smoke.py` — **10/10 PASS**.
- Suite complète : **245 passed, 1 skipped** — non-régression confirmée (flag OFF par défaut).

## Note de continuité

Wave additive : ne réécrit ni `engine.genome`, ni `engine.genome_decoder`, ni
`engine.neat_brain` (un seul hook gated), ni la boucle agent. Numérotation Wave 52 / p121
choisie au-dessus du maximum occupé par la piste géologie (Waves 49–51, smokes p118–p120).
