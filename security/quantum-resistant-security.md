# Sécurité — Niveau quantique (PQC) & Zero Trust

> Genesis Engine adopte une posture **« post-quantique d'abord »** (PQC-first). Tous les nouveaux déploiements en 2026+ utilisent les standards NIST PQC finalisés en 2024–2025 en complément (hybrid) des standards classiques.

## Modèle de menace

| Menace | Vecteur | Impact | Mitigation principale |
|---|---|---|---|
| Vol de snapshot | exfil cloud / compromission insider | reproduction simulation, IP leak | E2E encryption client-side + KMS HSM |
| Modification simulation | injection ticks malveillants | corruption science | Signatures Ed25519+Dilithium + Merkle log |
| Vol d'avatars utilisateur | exfil photos/voix | usurpation identité | E2E, ZK proofs, droits utilisateurs |
| Attaque « Harvest Now, Decrypt Later » | écoute trafic chiffré, déchiffrement futur quantique | violation confidentialité long-terme | TLS hybride PQC dès 2026 |
| Compromission supply-chain | dep malveillante, image vérolée | RCE | SLSA L3+, Sigstore, SBOM, vendoring stricts |
| Insider menace (admin) | accès direct prod | exfil/destruction | dual control, just-in-time access, no-standing-privilege |
| Side-channel sur GPU partagé | leak inférence inter-tenant | leak modèle/données | confidential VM (NVIDIA H100/H200 + Intel TDX/AMD SEV-SNP) |

## Cryptographie — niveaux

### Couche transport

- **TLS 1.3** + **groupes hybrides PQC** (Kyber768 / ML-KEM-768) — supporté Cloudflare, AWS, Google Cloud depuis 2024
- Tous les services internes : **mTLS** via SPIFFE/SPIRE
- **ML-DSA (Dilithium)** pour la signature des certificats
- **SLH-DSA (SPHINCS+)** pour les signatures à très longue durée de vie (snapshots, audit logs)

### Authentification

- **WebAuthn / Passkeys** côté utilisateur (FIDO2)
- **OIDC** + **OAuth 2.1**
- **Tokens d'accès** : JWT signés Ed25519 **et** Dilithium (double signature en transition)
- **Service-to-service** : SPIFFE SVID, rotation toutes les 6 h

### Chiffrement at-rest

- AES-256-GCM (clés symétriques) — résiste à l'attaque quantique par doublement de taille
- KEKs gérées par **HSM FIPS 140-3 Level 3** ou **AWS CloudHSM** / **GCP Cloud HSM**
- KEM hybride **X25519 + ML-KEM-1024** pour wrapping
- Rotation : DEK 7 j, KEK 90 j, MK 1 an

### Sealed snapshots (E2E client)

Pour les utilisateurs scientifiques sensibles :
1. Le client génère une clé locale (HSM ou Yubikey)
2. Snapshot chiffré côté client avant upload
3. Le cloud ne voit jamais le contenu
4. Wrapping hybride X25519 + ML-KEM-1024

## Zero Trust en pratique

### Principes

1. **Never trust, always verify** — chaque requête est authentifiée + autorisée, même intra-cluster
2. **Least privilege** — pas de role permanent admin sur prod
3. **Just-In-Time access** — accès admin obtenu via demande + approbation, durée limitée (15 min), enregistrement vidéo
4. **Assume breach** — détection et confinement plutôt que prévention seule

### Implémentation

- **Service mesh** Istio Ambient avec mTLS partout (PQC-hybrid)
- **OPA / Cedar** pour les politiques d'autorisation
- **Workload identity** SPIFFE
- **Secret zero** : aucun secret en clair dans le code, ni en env vars statiques. Tout via Vault dynamic secrets ou cloud-native (AWS IRSA, GCP Workload Identity)

## Confidential computing

- Sim nodes traitant des avatars utilisateurs : **AMD SEV-SNP** ou **Intel TDX**
- Inference GPU : **NVIDIA H100/H200/B200 Confidential Computing** (mode Hopper Confidential)
- Attestation à chaque démarrage de pod (Veraison / SPIRE attestor)

## Signature & intégrité simulation

Chaque tick produit un **commit Merkle** :
```
tick_root = blake3(prev_tick_root || tick_delta_root)
```
Le `tick_root` est signé en SLH-DSA (SPHINCS+) — quantum-safe sur le très long terme. C'est la **chaîne d'intégrité** de la simulation. Un tiers peut vérifier qu'aucun tick n'a été altéré sans avoir accès au contenu.

## Chiffrement homomorphe (analytics tiers)

Pour les **partenaires analytics externes** (universités, instituts) sans leur donner accès brut aux données :
- **CKKS** (HE approximatif) pour stats agrégées
- **BGV** (HE entier exact) pour comptages
- Lib : **OpenFHE** (open-source, performante)
- Use cases : computing Gini, R₀ pandémie, fitness moyen sans révéler agents

## Audit & conformité

- **Logs d'audit** immutables (Loki + S3 Object Lock + signatures SLH-DSA)
- **Append-only** sur AWS S3 Object Lock ou Azure Immutable Blob
- Conservation 7 ans
- Surveillance temps réel via SIEM (Wazuh)

## Vulnerability management

- **SCA** : Snyk/Trivy par PR, blocage si critique
- **DAST** : OWASP ZAP en pre-prod
- **SAST** : CodeQL + Semgrep
- **Container** : Cosign verify policy admission
- **Dépendances Rust** : `cargo audit` + cargo-deny
- **SBOM signé** : SPDX 3 + CycloneDX 1.6 pour chaque release
- **Patch SLA** : critique 24 h, high 7 j, medium 30 j

## Réponse à incident

- **Runbook** par scénario (compromission node, exfil, ransomware)
- **D1 detect, D2 respond, D3 recover** drilled trimestriel
- **Forensics** : pré-positionnement Velociraptor/GRR
- **Communication** : matrix RACI + statut public stable

## Dépendances externes

- Pas de SDK propriétaire fermé sur le chemin sensible
- Toutes les libs crypto auditées : **AWS-LC**, **BoringSSL**, **liboqs** (avec audit)
- liboqs en mode hybrid uniquement (jamais PQC seul, en attendant maturation)

## Bornes de garantie

| Type d'attaquant | Bornes |
|---|---|
| Script kiddie | bloc complet (WAF + rate limit + auth) |
| Attaquant outillé | bloc en transit (PQC), accès limité (ZT) |
| APT étatique | détection + confinement + perte minimale |
| Adversaire avec ordinateur quantique « cryptographically relevant » (CRQC, projeté ~2030+) | confidentialité longue durée préservée par PQC déjà déployé |

## Conformité visée

- **ISO/IEC 27001:2022**
- **SOC 2 Type II**
- **NIST CSF 2.0**
- **NIST SP 800-208 (stateful hash-based sigs)** pour artefacts longue durée
- **GDPR** — DPIA pour avatars utilisateurs
- **EU AI Act** — classification, documentation modèle, transparence
- **CRA (Cyber Resilience Act EU)** — SBOM, vuln disclosure
