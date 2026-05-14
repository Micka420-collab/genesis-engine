# ADR 0001 — Cœur de simulation en Rust, pas Unity/Unreal

- **Statut** : Accepté
- **Date** : 2026-05-10
- **Décideurs** : équipe architecture
- **Liens** : `architecture/system-architecture.md`, `architecture/tech-stack-2026.md`

## Contexte

Le brief mentionne « Unity DOTS ou Unreal » pour la simulation. Or notre besoin n'est **pas** un jeu vidéo : c'est une simulation distribuée, déterministe, à 10⁶ agents, avec sharding spatial et replay bit-à-bit. Les engines de jeu classiques sont conçus pour le rendu temps-réel, pas pour ce profil.

## Décision

Le **cœur de simulation** est écrit en **Rust** (Bevy ECS comme runtime data-oriented, Jolt Physics, tonic gRPC, Tokio). Unity et Unreal sont **réservés au rendu high-fidelity côté client immersif optionnel** (hors boucle de simulation).

## Conséquences

### Positives
- Déterminisme strict (no GC, no hidden runtime)
- Performance native (parité C++)
- Memory safety (élimine une classe entière de bugs)
- Concurrence sûre (Send/Sync)
- Tooling de packaging cloud-native (cargo, cross, sigstore)
- Pas de license commerciale Unity/Unreal sur les nodes serveurs

### Négatives
- Recrutement plus difficile (vivier Rust < vivier Unity/Unreal)
- Pas d'éditeur visuel intégré (mais le moteur n'a pas besoin d'éditeur — le monde est procédural)
- Bibliothèques 3D matures plus rares (mitigé : on n'a pas besoin de rendre côté serveur)

## Alternatives considérées

- **Unity DOTS** : ECS performant, mais déterminisme non-strict, Mono GC, scalabilité distribuée non-native, license coûteuse en multi-instance.
- **Unreal Engine 5** : excellent rendu, mais runtime trop monolithique pour 10⁶ agents distribués ; déterminisme partiel.
- **C++ pur** : performance équivalente, perte de memory safety, productivity moindre, écosystème cloud moins mature.
- **Go** : excellent en services, mais GC pénalise le tick chaud.

## Validation

À la fin de Phase 1, mesurer :
- tick rate effectif sur 10 agents
- déterminisme replay (1000 ticks, hash identique)
- coût compute baseline
