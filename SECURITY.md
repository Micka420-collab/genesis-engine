# Genesis Engine — Security Model

> **Threat model includes post-quantum adversaries from day one.**
> "Harvest Now, Decrypt Later" is treated as an active threat in May 2026.

## Compliance baseline

- NIST **FIPS 203** — ML-KEM (key encapsulation)
- NIST **FIPS 204** — ML-DSA (digital signature)
- NIST **FIPS 205** — SLH-DSA (hash-based signature)
- OWASP **ASVS 5.0** Level 2 for user-facing services
- **SLSA Level 3** for supply chain
- **GDPR + CCPA** for human avatar data
- **EU AI Act** — Genesis classified as "limited-risk" (research) initially; "high-risk" classification accepted if regulator decides

## Cryptography — Post-Quantum (PQC)

### Key Encapsulation Mechanism (KEM)
- **ML-KEM-768** (Kyber Level 3, ~AES-192 strength)
- **Hybrid** with X25519 during transition (concat shared secrets)
- Used for: TLS, VPN, end-to-end encryption between services

### Digital Signature
- **ML-DSA-65** (Dilithium Level 3) for:
  - Code signing
  - Transaction signing
  - Snapshot signing
- **SLH-DSA-SHA2-128s** for:
  - Long-term archive signatures (>10 years)
  - Fallback if ML-DSA is broken (hash-based = quantum-safe by reduction)

### Symmetric primitives (already quantum-resistant)
- **AES-256-GCM** for data at rest (256-bit gives ~128-bit post-quantum)
- **ChaCha20-Poly1305** for streaming
- **SHA-3-512** for hashing where collision resistance matters
- **BLAKE3** for non-adversarial fast hashing

### Key management
- **HashiCorp Vault** with KMS backend (AWS KMS / GCP KMS)
- **Automatic rotation:** TLS certs daily, encryption keys hourly for hot data
- **HSM** (Hardware Security Module) for root keys: YubiHSM 2 FIPS or AWS CloudHSM
- **Key escrow:** Shamir's Secret Sharing 3-of-5 for root recovery

## Encryption at rest

| Asset | Cipher | Key management |
| --- | --- | --- |
| K8s volumes | AES-256-GCM | KMS-backed CSI driver |
| PostgreSQL / CockroachDB | TDE | DB-native + KMS |
| Object storage (R2/B2) | ChaCha20-Poly1305 client-side via `age` | Per-bucket keys, rotated weekly |
| Simulation snapshots | AES-256-GCM | Hourly rotation |
| Agent memory (vector DB) | Partial FHE (CKKS) | Allows similarity search on encrypted vectors |
| Backup archives | AES-256-GCM + SLH-DSA sig | Air-gapped key for cold archives |

## Encryption in transit

- **mTLS everywhere** (Linkerd 2.16 auto-provisions)
- **TLS 1.3 only** with PQC hybrid cipher suite (`X25519MLKEM768`)
- **HSTS** + **HPKP** alternative (pinned via cert transparency)
- **Inter-region VPN:** WireGuard + Rosenpass (PQC handshake)
- **gRPC** uses application-level encryption on top of mTLS for double-defense on sensitive endpoints

## Identity & authentication

### User authentication
1. **Passkeys / WebAuthn** — primary method
2. **YubiKey 5 NFC FIPS** required for admin accounts
3. **Adaptive MFA** — prompts based on risk score (IP, device, geo, behavior)
4. **No passwords stored** — period

### Session management
- JWT access tokens: 5-min TTL, signed with ML-DSA
- Refresh tokens: rotating, httpOnly + SameSite=Strict
- Anomaly detection: supervised ML on auth logs (ATO detection)

### Service-to-service
- mTLS with workload identities (SPIFFE / SPIRE)
- Service identities scoped per-namespace
- No long-lived service tokens; auto-rotation every 24h

## Application security

### Shift-left in CI
1. **SAST** — Semgrep + CodeQL on every PR
2. **DAST** — OWASP ZAP on every staging deploy
3. **SCA** — Trivy + Snyk on every container build
4. **License compliance** — FOSSA on every dep change
5. **SBOM** — Syft generates SPDX 2.3 + signs with cosign

### Supply chain (SLSA L3)
- Builds reproducible (same inputs → same outputs, byte-for-byte)
- In-toto attestations on artifacts
- Sigstore for signing without long-lived keys
- Dependency pinning by hash

### Runtime
- **gVisor** for LLM agent containers (kernel attack surface reduction)
- **Firecracker** microVMs for higher isolation (multi-tenant)
- **OPA / Cedar** policy engine: every simulation action passes policy check
- **Prompt injection defense:**
  - Input sanitization
  - Structured output parsing (JSON schema validation)
  - Canary tokens in agent contexts
  - Separate planning and execution prompts

## Network security

### Zero Trust
- No implicit trust between services
- All connections mTLS-authenticated
- Egress through explicit proxy with allowlist
- NetworkPolicies: deny-all default, explicit allowlists

### Edge
- Cloudflare WAF + DDoS protection
- Rate limiting at L7 via Envoy
- Circuit breakers prevent cascade failures
- BGP-level DDoS mitigation via Cloudflare Magic Transit (Phase 4+)

### Internal segmentation
- 3-tier: edge → service mesh → data plane
- Each tier has independent network policies
- Cilium + Hubble for L3-7 observability

## Privacy & governance

### GDPR / CCPA compliance
- **Right to access:** complete data export in standard formats (JSON-LD, glTF, etc.)
- **Right to deletion:** complete purge within 30 days
- **Data Processing Agreements** with all vendors
- **DPO** (Data Protection Officer) appointed in Phase 1
- **DPIA** (Data Protection Impact Assessment) for each major release

### Human avatars
- **Explicit consent** for biometric scan (face, voice)
- **Cryptographic watermark** in all generated outputs (DIY: per-user noise pattern)
- **No training on user data** unless explicit opt-in
- **Pseudonymization** by default; PII never in simulation logs

### Audit trail
- All admin actions logged append-only
- Logs signed with ML-DSA per-day
- Tamper detection via Merkle tree of daily logs
- 7-year retention for audit logs

### Data Loss Prevention (DLP)
- Macie / custom DLP classifier on object storage
- Egress filtering with content inspection
- Alerts on anomalous data movement

## Business continuity

| Metric | Target |
| --- | --- |
| RTO (control plane) | 1 hour |
| RTO (critical shards) | 15 minutes |
| RPO | 30 seconds |
| Geo-redundancy | 3+ regions (US, EU, APAC) |
| DR drill frequency | Quarterly |
| Chaos engineering | Continuous (Chaos Mesh) |

### Post-quantum break plan
1. **Detection:** monitor academic literature + NIST advisories
2. **Trigger:** any peer-reviewed attack reducing ML-KEM-768 security below 128 bits
3. **Response:**
   - Immediate switch to SLH-DSA + ChaCha20-Poly1305 + 384-bit key sizes
   - Re-encrypt all "hot" data within 7 days
   - Re-sign all critical artifacts within 30 days
   - Notify users within 48 hours per breach notification laws

## Bug bounty

- Launches Phase 2 on HackerOne
- Scope: all production services, exclude DDoS, social engineering, physical
- Bounty tiers:
  - **Critical** (RCE, auth bypass, PQC break): €25 000 - €100 000
  - **High** (privilege escalation, sensitive data exposure): €5 000 - €25 000
  - **Medium** (XSS, CSRF, SSRF): €500 - €5 000
  - **Low** (info disclosure, rate limit bypass): €100 - €500

## Red team

- Internal red team forms Phase 3
- External pen-test annually starting Phase 3
- Tabletop exercises quarterly
- Purple-team sessions monthly

## Compliance roadmap

| Standard | Target phase |
| --- | --- |
| SOC 2 Type 2 | Phase 4 |
| ISO 27001 | Phase 4 |
| ISO 27701 (privacy) | Phase 4 |
| FedRAMP Moderate | Phase 5 (if US gov interest) |
| GDPR Code of Conduct | Phase 3 |
