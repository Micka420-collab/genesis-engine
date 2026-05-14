# Spec — Pipeline avatar utilisateur

## Objectif

Permettre à un utilisateur de générer son **double numérique** (mesh 3D + texture + animations + identité) à partir de quelques photos, optionnellement vidéo et voix. L'avatar peut ensuite être **inséré comme agent observateur** ou comme « ancêtre fondateur » dans une simulation privée (ne pas confondre avec l'expérience scientifique des 2 agents fondateurs, qui doit rester anonyme).

## Inputs

- 3–10 photos visage (multiples angles)
- 1–3 photos corps entier
- Vidéo 5–10 s (optionnelle, pour les blendshapes)
- Audio 30 s (optionnel, voix neutre)

## Pipeline

```
Inputs ─► [Pre-process]
            ▼
         [Face mesh estimator]    ← MediaPipe 2026 / FLAME 2025
            ▼
         [Body mesh estimator]    ← SMPL-X / Hermes-Body
            ▼
         [Texture synthesis]      ← Stable Diffusion 3 / Flux + ControlNet
            ▼
         [Skeleton rigging]       ← AccuRIG / Mixamo-like
            ▼
         [Blendshapes]            ← ARKit 52 + custom 12
            ▼
         [Animation retargeting]  ← AutoRetarget
            ▼
         [Voice clone]            ← XTTS v2.5 / OpenVoice 2 (E2E encrypted)
            ▼
       Avatar package (.glb + manifest.json signed)
```

## Sortie

```
avatar/
  mesh.glb            (~30 MB, low-poly + high-poly LODs)
  texture/
    diffuse.ktx2
    normal.ktx2
    roughness.ktx2
  rig/
    skeleton.json
    blendshapes.json
  animations/
    walk.glb, run.glb, idle.glb, ...
  voice/
    embedding.bin (chiffré E2E)
  manifest.json (signé Ed25519+Dilithium)
```

## Variantes

- **Réaliste** (PBR fidèle)
- **Stylisé** (cel-shading, low-poly)
- **Voxel** (compatible direct avec le voxel world)

## Confidentialité (CRITIQUE)

- **E2E** : photos/vidéo/audio jamais stockés en clair côté serveur
- Traitement dans **enclave confidentielle** (TDX/SEV-SNP)
- Sortie chiffrée côté client (clé HSM/Yubikey utilisateur)
- **Droit à l'oubli** : suppression cryptographique (destruction de la clé)
- **GDPR DPIA** obligatoire avant rollout
- **Watermarking invisible** : toute exportation reçoit un watermark stéganographique unique pour traçabilité (anti-deepfake)

## Coût d'inférence

- Pipeline complet : ~3 min sur 1 H100 (batch utilisateur)
- Coût marginal : ~$0.20 / avatar généré

## Limitations volontaires

- Pas de génération nu/sexualisée (filtre + politique stricte)
- Pas de génération de **mineurs** (détection d'âge bloquante si <18 estimé)
- Pas d'avatar de personnes publiques (recherche LFW/celebrity match → bloc)
- Pas d'avatar **sans consentement** (PoP : preuve de possession via challenge live)
