# Threat Model & Risk Register — Genesis Engine

**Document type** : STRIDE + LINDDUN-augmented threat model with
quantitative risk register.
**Methodology** : Microsoft STRIDE (1999) + LINDDUN (Deng et al.,
2011, KU Leuven) for privacy threats + OWASP Risk Rating Methodology
(Likelihood × Impact, 1–9).
**Version** : 1.0
**Date** : 2026-05-15
**Owner** : Mickaël Delcato (`micka.delcato.rp@gmail.com`).
**Reviewed by** : Claude Opus 4.7 (co-architect).
**Scope** : Genesis Engine runtime (`runtime/engine/*`), CLI scripts
(`runtime/scripts/*`), persistence (`world_library.py`), and dashboard
(`engine/dashboard.py`). Out of scope : downstream visualisation
front-end (Phase 5 deliverable, not built yet) ; LLM-tier cognition
(Phase 5 deferred).

---

## 1. Context and assets

### 1.1 System overview

The Genesis Engine is a Python 3.14 process running on Windows 10
(developer workstation) or Linux (CI). It :
1. Loads / generates Earth-realistic worlds (`engine.earth_loader`,
   `engine.world`).
2. Runs deterministic simulations of agents with biology, chemistry,
   physics, cognition, polity, building, language (Waves 1–11).
3. Persists snapshots to `runtime/worlds/<name>/` as JSON +
   SHA-256 manifest (`engine.world_library`).
4. Exposes a local Flask-style dashboard (`engine.dashboard`) bound to
   `127.0.0.1` by default.

### 1.2 Asset inventory

| ID | Asset | CIA priority | Value rationale |
|---|---|---|---|
| A1 | Simulation source code (engine/*) | **I** > C > A | Loss of integrity invalidates all scientific claims. |
| A2 | Persisted world snapshots (`runtime/worlds/*/`) | C = I > A | Multi-month longitudinal experiments. |
| A3 | Telemetry / smoke transcripts (`runtime/journals/*.jsonl`) | I > A > C | Scientific record ; reproducibility chain of custody. |
| A4 | Seed values + `prf_rng` keys | I > C > A | Determinism contract ; leak doesn't break security but predictability changes are forensic-grade. |
| A5 | Operator credentials (GitHub PAT, `gh` auth, Anthropic API keys) | C > I > A | Account hijack. |
| A6 | Operator personal data (email, IP, OS user) | C > I = A | GDPR Art. 6/9 ; see AIPD. |
| A7 | Sub-agent task descriptions + outputs (Claude Code) | C ≥ I > A | May contain proprietary algorithms or sensitive prompts. |
| A8 | Dashboard local HTTP endpoint | A > I > C | DoS or RCE pivot if exposed. |
| A9 | Calibration constants in module headers | I > A > C | Falsifying e.g. UVI coefficient silently corrupts science. |
| A10 | Network endpoints (Anthropic API, GitHub) | C > A > I | Exfiltration vector. |

(C = Confidentiality, I = Integrity, A = Availability.)

### 1.3 Trust boundaries

```
┌─────────────────────────────────────────────────────────────┐
│ Workstation (Windows 10, single user `micki`)               │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ python.exe — Genesis Engine process                     │ │
│ │   ▸ deterministic computation                           │ │
│ │   ▸ writes to %CWD%/runtime/worlds, journals            │ │
│ │   ▸ binds 127.0.0.1:port for dashboard                  │ │
│ └────────────┬────────────────────────────────────────────┘ │
│              │ stdout / stderr / file system                 │
│ ┌────────────┴────────────────────────────────────────────┐ │
│ │ Claude Code CLI / Agent SDK                             │ │
│ │   ▸ invokes Edit/Read/Bash on engine/ files             │ │
│ │   ▸ spawns sub-agents in worktrees                      │ │
│ └────────────┬────────────────────────────────────────────┘ │
└──────────────│──────────────────────────────────────────────┘
               │ outbound TLS
               ▼
    ┌────────────────────────┐    ┌───────────────────────┐
    │ Anthropic API          │    │ GitHub API (`gh`)     │
    │  (claude.ai/api)       │    │  (api.github.com)     │
    └────────────────────────┘    └───────────────────────┘
```

Trust boundary crossings :
* TB1 : CLI ↔ python process (fs + stdout) — same user, same machine.
* TB2 : python process ↔ Anthropic API (outbound TLS, API key).
* TB3 : CLI ↔ GitHub (outbound TLS, `gh` PAT).
* TB4 : dashboard ↔ browser (loopback HTTP, no auth by default).
* TB5 : worktree ↔ main repo (filesystem, same user).

---

## 2. STRIDE analysis

### 2.1 Spoofing

| ID | Threat | Affected asset | Vector | Existing control |
|---|---|---|---|---|
| S-01 | Forged sim snapshot loaded as authoritative | A2, A3 | Attacker edits JSON in `runtime/worlds/<name>/` | SHA-256 manifest verification on load (`world_library._verify_integrity`) |
| S-02 | Forged co-author trailer in git commits | A1 | Git history manipulation | Commit-signing not yet enforced (gap, see R-S-02) |
| S-03 | LLM identity confusion (Claude vs malicious local agent) | A7 | Process spawns sub-agent CLI not validated | Anthropic API key bound to operator account ; gap = no per-task attestation |
| S-04 | `gh` token impersonation | A5, A10 | Stolen PAT → push to repo | OS-level keyring + PAT scope minimisation |

### 2.2 Tampering

| ID | Threat | Affected asset | Vector | Existing control |
|---|---|---|---|---|
| T-01 | Calibration constant silently altered | A1, A9 | Edit `FARQUHAR_K_M` etc | `engine.world_model_capabilities.audit_modules` lints headers ; gap = no constants hash |
| T-02 | Pre-registered hypothesis result modified post-hoc | A3 | JSONL log edited | Smoke transcripts copied into git ; gap = no append-only log |
| T-03 | `prf_rng` keyed sequence forgery | A4 | Read seed + recompute then re-emit | None ; treated as predictability not security issue |
| T-04 | World snapshot byte-tampered | A2 | Edit `.json` then update manifest | SHA-256 mismatch detection on load |
| T-05 | Dispatch table corruption | A1 | `id(agents)` collisions between sims | Module-level dispatch tables keyed on `id(agents)` ; collision risk minimal but unverified |

### 2.3 Repudiation

| ID | Threat | Affected asset | Vector | Existing control |
|---|---|---|---|---|
| R-01 | Engineer disputes that smoke ran | A3 | "I didn't run p39" | Smoke prints `RESULT: PASS` to stdout, captured in commit log + sprint doc |
| R-02 | Sub-agent action denied | A7 | "I never spawned that worktree" | Agent SDK persists run metadata under `~/.claude/projects/...` |

### 2.4 Information disclosure

| ID | Threat | Affected asset | Vector | Existing control |
|---|---|---|---|---|
| I-01 | API key leaked in commit | A5, A10 | `gh` PAT or Anthropic key pushed to GitHub | `.gitignore` excludes `.env` ; gap = no pre-commit secret scanner |
| I-02 | Operator email in CLAUDE.md leaks to public repo | A6 | Public docs include `micka.delcato.rp@gmail.com` | Email is already public on git commits (Co-Authored-By trailer) ; documented in AIPD §3.2 |
| I-03 | World snapshot includes PII inadvertently embedded by operator | A2, A6 | Operator names worlds with PII | Naming convention `phaseN_topic` ; gap = no validation |
| I-04 | Dashboard binds to `0.0.0.0` accidentally | A8 | Misconfigured deployment | Default `127.0.0.1` ; gap = no port-binding audit at startup |
| I-05 | Sub-agent prompt leaks proprietary IP to Anthropic | A1, A7 | Engine code excerpts in agent prompts | Acceptable under Anthropic Privacy Policy (no training on API by default) |
| I-06 | OS-level `tasklist` reveals running sim | A1, A6 | Local enumeration | Local-only ; acceptable for single-user workstation |

### 2.5 Denial of service

| ID | Threat | Affected asset | Vector | Existing control |
|---|---|---|---|---|
| D-01 | Long-run sim consumes all memory | A1, A8 | photosynthesis chunk cache unbounded | Wave 4 fix : LRU 4096 (P-NEW.24 closed) |
| D-02 | Infinite loop in cognition wiring | A1 | Decision loop without termination | Smoke `p33_cognition_wiring` validates fan-out + frequency |
| D-03 | Disk space exhaustion via JSONL | A8 | Long-run telemetry | Operator-monitored ; gap = no rotation |
| D-04 | Dashboard request flood (local) | A8 | Loop on `127.0.0.1:port` | Flask default rate-limit absent ; loopback-only mitigates |

### 2.6 Elevation of privilege

| ID | Threat | Affected asset | Vector | Existing control |
|---|---|---|---|---|
| E-01 | Hook configuration injects shell on tool call | A1 | Malicious entry in `~/.claude/settings.json` hooks | Hook scripts under operator control ; gap = no integrity check on hooks |
| E-02 | Dependency supply chain (pip install) | A1, A5 | Compromised package | `pip` index is `pypi.org` ; gap = no lockfile + hash pinning |
| E-03 | Python sandbox escape from Blender MCP execution | A1 | `mcp__Blender__execute_blender_code` runs arbitrary Python | Out-of-scope for current sim ; gap if enabled |
| E-04 | Cross-tool privilege via `dangerouslyDisableSandbox` | A1 | Bash tool invoked with sandbox off | Default sandboxed ; only on explicit operator approval |

---

## 3. LINDDUN-augmented privacy threats

For privacy-specific threats (complementing AIPD §4) :

| ID | LINDDUN category | Threat | Affected asset | Vector |
|---|---|---|---|---|
| L-01 | Linkability | Re-identify operator across multiple commits | A6 | Email + UUID linkable across repos |
| L-02 | Identifiability | Static personality seed used as fingerprint | A4 | If a seed is reused as a user identifier |
| L-03 | Non-repudiation (privacy) | Operator cannot deny having run an experiment | A3 | Smoke transcripts archive every action |
| L-04 | Detectability | Local processes detectable from sibling sessions | A1 | OS `ps`/`tasklist` ; out of scope |
| L-05 | Disclosure | Telemetry uploaded by mistake | A2, A3 | If a future Wave 12 adds remote sync |
| L-06 | Unawareness | Operator unaware of Anthropic data flow | A7 | Mitigated by Anthropic Privacy Policy + operator consent |
| L-07 | Non-compliance | Failure to honour DSAR / Art. 17 erasure | A6 | See AIPD §6 mitigation |

---

## 4. Risk register (quantitative)

Scoring : **Likelihood** L = {1: rare, 2: low, 3: moderate, 4: likely,
5: almost certain}. **Impact** I = {1: negligible, 2: minor, 3:
moderate, 4: major, 5: catastrophic for science / privacy / op}.
**Risk score** = L × I (max 25). **Status** = open / mitigated /
accepted.

| ID | Threat | L | I | Score | Status | Mitigation owner | Mitigation plan |
|---|---|---|---|---|---|---|---|
| R-S-01 | Forged sim snapshot loaded as authoritative | 2 | 5 | 10 | Mitigated (SHA-256) | architect | Add 2nd-channel signature (e.g. cosign) by W14 |
| R-S-02 | Forged co-author trailer | 2 | 3 | 6 | Open | architect | Enable `git commit -S` with operator GPG key |
| R-S-03 | LLM identity confusion | 2 | 4 | 8 | Open | operator | Pin Claude model ID per session in transcripts |
| R-T-01 | Calibration constant tampered | 2 | 5 | 10 | Partial | architect | Add `engine.constants_audit` hash check at smoke entry |
| R-T-02 | Hypothesis result modified post-hoc | 2 | 5 | 10 | Partial | architect | Move smoke transcripts to append-only `.txt` ; PGP-sign on release |
| R-T-05 | `id(agents)` collisions in dispatch | 1 | 4 | 4 | Accepted | architect | Add weakref-keyed registry in W12 |
| R-I-01 | API key leaked in commit | 3 | 5 | 15 | Open | operator | Install `git-secrets` / `gitleaks` pre-commit hook |
| R-I-02 | Operator email leak via README | 5 | 1 | 5 | Accepted | operator | Documented in AIPD ; lawful basis = legitimate interest |
| R-I-03 | World snapshot inadvertent PII | 1 | 4 | 4 | Open | operator | Validator in `world_library.save_world` to reject names matching email regex |
| R-I-04 | Dashboard `0.0.0.0` binding | 2 | 4 | 8 | Open | architect | Hard-coded `127.0.0.1` ; refuse env override unless `--public` flag set |
| R-D-01 | Memory exhaustion long-run | 2 | 4 | 8 | Mitigated (LRU 4096) | architect | Add RSS watchdog in `p24_long_run_stability` |
| R-D-03 | Disk space exhaustion JSONL | 3 | 3 | 9 | Open | operator | Rotation policy in `world_library` (default keep latest 10) |
| R-E-01 | Malicious hook injection | 1 | 5 | 5 | Open | operator | Document hook integrity check in CLAUDE.md |
| R-E-02 | Dependency supply chain | 3 | 5 | 15 | Open | architect | `pip-compile --generate-hashes` + lockfile in W14 |
| R-E-04 | Sandbox-off invocation | 1 | 5 | 5 | Mitigated | operator | Default sandboxed ; explicit operator consent per call |
| R-L-01 | Operator linkable across commits | 5 | 2 | 10 | Accepted | operator | Lawful interest (academic attribution) |
| R-L-02 | Seed reused as fingerprint | 1 | 3 | 3 | Accepted | architect | Seeds are documented sentinel values, no PII |
| R-L-05 | Telemetry exfiltration via future remote sync | 1 | 5 | 5 | Open | architect | W12+ feature ; revisit before enabling |
| R-L-07 | DSAR / erasure non-compliance | 2 | 5 | 10 | Open | operator | See AIPD §6 erasure procedure |

### 4.1 Top-5 risks (post-treatment)

1. **R-I-01 — API key leaked in commit** (score 15). Action :
   `gitleaks` pre-commit hook + `--scan` CI step. Target close
   date : 2026-05-31.
2. **R-E-02 — Dependency supply chain** (score 15). Action :
   `requirements.lock` with sha256 hashes ; Dependabot auto-PRs.
   Target : 2026-06-15.
3. **R-T-01 — Constant tampering** (score 10). Action : add SHA-256
   of constants block to `engine.world_model_capabilities` audit.
   Target : 2026-05-30.
4. **R-T-02 — Hypothesis result tampered post-hoc** (score 10).
   Action : append-only release transcripts ; PGP sign each sprint.
   Target : 2026-05-31.
5. **R-S-01 — Forged snapshot** (score 10). Action : cosign-like
   detached signature on `worlds/<name>/manifest.json`.
   Target : 2026-06-30.

---

## 5. Cumulative residual risk

After all open items in §4.1 are mitigated, the cumulative residual
risk for the runtime is estimated **5/25 (low)** : the simulator is
single-user, loopback-only, with deterministic output ; the principal
remaining surface is dependency supply chain (mitigated to ≤ 5 by
hash-pinned lock).

---

## 6. Incident response

Out-of-band alert if any of the following are observed :

| Signal | Action |
|---|---|
| `gitleaks` finds a secret in pre-commit | Block commit, rotate the leaked credential immediately. |
| `world_library` reports manifest SHA-256 mismatch | Refuse load, alert operator, preserve original for forensics. |
| Smoke `p18_capabilities_lint` reports `module_missing` | Treat as integrity event ; do not ship. |
| Dashboard request from non-loopback IP | Kill `dashboard` process, audit logs. |
| Memory > 1.5 GB during a sim (RSS) | Suspend sim, dump heap, file regression bug. |

---

## 7. Compliance mapping

| Framework | Section | Coverage |
|---|---|---|
| ISO/IEC 27005:2022 | §8.2 Risk identification | §2 STRIDE + §3 LINDDUN |
| ISO/IEC 27005:2022 | §8.4 Risk analysis | §4 quantitative L × I |
| NIST SP 800-30 r1 | Table I-7 Threat sources | mapped per asset in §1.2 |
| OWASP ASVS 4.0.3 | V14 Configuration | §1.3 trust boundaries |
| RGPD Art. 32 | Security of processing | §4.1 top-5 + §6 IR |
| RGPD Art. 35 (3) (a) | Systematic monitoring | linked to AIPD §3 |

---

## 8. Revision history

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | 2026-05-15 | M. Delcato + Claude Opus 4.7 | Initial publication post Wave 11 |

---

## 9. References

- Shostack, A. (2014). *Threat Modeling : Designing for Security.* Wiley.
- Deng, M., Wuyts, K., Scandariato, R., Preneel, B., Joosen, W. (2011).
  *A privacy threat analysis framework : supporting the elicitation
  and fulfillment of privacy requirements.* Requirements Engineering,
  16(1).
- Microsoft Security Development Lifecycle (2024). *STRIDE Threats.*
- OWASP Risk Rating Methodology (2024).
- NIST SP 800-30 Rev. 1, *Guide for Conducting Risk Assessments.*
- ISO/IEC 27005:2022, *Information security risk management.*
- CNIL (2021). *Logiciel PIA — Méthode et bases de connaissances.*
