# Wave 47 — Heritable genotype→phenotype decoder (semantic closure)

**Date:** 2026-05-29 · **Status:** livré (tests + smoke verts) · **Layer:** strong-ALife / G→P

> Source de vérité projet : [`PROJECT-STATUS.md`](../../PROJECT-STATUS.md) ·
> file de travail : [`NEXT-SPRINT.md`](../../NEXT-SPRINT.md)

## Motivation (Pattee)

Aujourd'hui le génome est décodé par un map **externe et fixe** :
`engine.genome.gene_to_trait(genome, group) = mean(genome[group])`. C'est
*nous* (observateurs) qui décidons que tels loci « signifient » tel trait,
et la règle ne participe jamais à l'évolution. En termes de Howard Pattee
le génome est alors « un niveau de signes dépourvu de dynamique
intrinsèque ». C'est exactement l'écart entre *weak* ALife (nous
interprétons les symboles) et *strong* ALife (le système interprète ses
propres symboles, et cet acte d'interprétation est lui-même héritable et
sélectionnable).

## Ce qui est livré

`engine/genome_decoder.py` — décodeur **pur** et déterministe qui met
l'**interpréteur dans le génome** :

- **Région structurelle** S = loci `[0, 192)` — contenu codant brut.
- **Région régulatrice** R = loci `[192, 256)` — matrice de poids `K×F`,
  le *code* qui décide ce que les gènes structurels **veulent dire**.

```
feats[j] = mean(S sur chunk j)                 j ∈ 0..F-1
W[k,j]   = R reshape(K,F) mappé sur [-gain, +gain]
P[k]     = sigmoid( Σ_j W[k,j] · (feats[j] - 0.5) )
```

R vivant dans le génome, il est hérité et muté par le **même** opérateur
`engine.genome.crossover` que S : le map génotype→phénotype est
per-individu, héritable, et sous sélection. Deux génomes à gènes
structurels **identiques** mais régulation différente produisent des
phénotypes différents — la signification n'est plus fixée de l'extérieur.
Propriétés émergentes vérifiées : **pléiotropie** (1 chunk → plusieurs
traits) et **épistasie** (même variation structurelle, effet différent
selon R). Module **additif** : ne réécrit ni `engine.genome`, ni
`engine.agent`, ni la boucle agent vivante.

## Honnêteté sur le gap restant

Ceci ferme le côté **description→interprétation** de la boucle de Pattee
(le code gènes→traits est maintenu par la lignée). Ça ne ferme **pas**
encore le côté **construction** (auto-reconstruction von Neumann du
décodeur) — travail futur, non revendiqué ici.

## Validation

- `tests/test_genome_decoder.py` — **13/13** verts.
- `scripts/p117_genome_decoder_smoke.py` — **10/10 PASS** (shape/range,
  déterminisme sha256, fermeture sémantique, héritabilité crossover,
  pléiotropie, épistasie, génomes founders réels, decoder_summary cohérent).

## Note de continuité

Run nocturne précédent avait produit ce module + smoke + tests mais a
crashé avant le commit (laissant un `.git/index.lock` périmé). Ce run a
nettoyé le verrou et finalisé le commit. Le wave « neutral-shadow »
(Bedau–Packard) évoqué dans certaines docstrings n'est pas committé dans
`engine.open_endedness` ; il reste un item backlog indépendant.
