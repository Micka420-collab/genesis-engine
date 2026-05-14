# ADR 0003 — Cryptographie post-quantique dès J1

- **Statut** : Accepté
- **Date** : 2026-05-10

## Contexte

Le brief impose « cybersécurité même niveau quantique ». Les standards NIST PQC ML-KEM (Kyber), ML-DSA (Dilithium) et SLH-DSA (SPHINCS+) sont finalisés depuis 2024–2025. Les snapshots de simulation peuvent contenir des données scientifiques sensibles à long terme — la menace « Harvest Now, Decrypt Later » est réelle.

## Décision

**Hybride PQC dès J1** :
- TLS 1.3 avec key exchange hybride X25519 + ML-KEM-768
- Signatures duales Ed25519 + ML-DSA-65 sur les tokens et certificats
- SLH-DSA (SPHINCS+) pour les artefacts à très longue durée (snapshots, audit logs, manifests SBOM)
- AES-256-GCM (résiste à Grover par doublement de taille)
- HSM FIPS 140-3 Level 3 pour les KEK
- Confidential Computing (TDX/SEV-SNP + GPU H200 confidentiel) pour les workloads avatars utilisateurs

## Conséquences

### Positives
- Confidentialité long-terme préservée
- Conformité aux directives NIST 2030
- Argument commercial pour secteurs régulés
- EU CRA / NIS2 ready

### Négatives
- Surcoût performance (~5–10 % en TLS handshakes — négligeable hors hot path)
- Surface de complexité accrue (hybrid mode)
- Dépendance à liboqs (audité, mais récent)

## Mitigation

- Hybride uniquement (jamais PQC seul tant que les implémentations ne sont pas plus matures)
- Audit cryptographique externe annuel
- Mise à jour automatisée des suites cipher
