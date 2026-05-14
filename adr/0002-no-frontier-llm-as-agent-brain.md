# ADR 0002 — Pas de LLM frontier comme cerveau d'agent

- **Statut** : Accepté
- **Date** : 2026-05-10
- **Décideurs** : recherche cognition + architecture

## Contexte

La tentation est forte de brancher un LLM frontier (Claude, GPT, Gemini) comme « cerveau » de chaque agent. Cela donnerait des comportements riches « gratuitement ».

## Décision

**Refusé pour les agents simulés.** Trois raisons :

1. **Coût** : 10⁶ agents × ~30 ticks/s × prompt = budget irréaliste, latence prohibitive.
2. **Casse l'émergence** : un LLM frontier sait déjà ce qu'est une « ville », une « guerre », un « commerce ». Il *importe* la civilisation au lieu de la *créer*. La question scientifique devient triviale et triviale = inintéressante.
3. **Anthropocentrisme** : les agents agissent comme des humains modernes, pas comme des proto-organismes — biais d'observation massif.

## Architecture retenue

Pile **hétérogène et compacte** :
- DINOv3-Small / SigLIP-2 pour perception
- DreamerV3 (modèle du monde) pour rollouts imaginés
- Transformer 50–200 M params pour la politique
- Bayesian Inverse Planning pour théorie de l'esprit
- **Small LM (1–3 B)** **uniquement post-émergence** pour réifier le langage qui a émergé spontanément

## Conséquences

### Positives
- Coût réaliste (~$0.05 / agent / jour Lab tier)
- Préserve la pureté scientifique
- Permet le saut symbolique authentique

### Négatives
- Plus de R&D en interne (DreamerV3 + curriculum + adapters)
- Moins de comportements « impressionnants » en démo précoce
- Risque que rien n'émerge (le pari scientifique)

## Validation

Critère **GO** Phase 4 : convergence d'au moins 5 signaux référents stables sur 3 générations dans une tribu, mesurée par mutual information signal/référent > 0.5 bit.
