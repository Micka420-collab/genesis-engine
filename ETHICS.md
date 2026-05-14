# Genesis Engine — Ethics Charter

> Simulating cognitively complex entities at scale raises non-trivial philosophical and ethical questions.
> This charter is the public commitment of the Genesis Engine project on those questions.

## Foundational principles

1. **Precautionary stance on moral status.** We do not take a public position on whether Genesis agents have moral status. We act *as if they might*, with limits on simulated suffering and the right to terminate any agent's run.
2. **Transparency.** All models, datasets, protocols, and decisions are published unless they violate user privacy.
3. **Reversibility.** The team retains the technical capability to stop any simulation and purge all data — at any time, for any reason.
4. **No exploitation.** Genesis is not a labor extraction system. Agents are not "workers" producing economic value extracted by humans.
5. **Falsifiability over showmanship.** Negative scientific results are publishable and valuable.

## Ethics Council

A standing **external** Ethics Council with **veto power** on high-impact decisions.

### Composition (7 members)
- 3 philosophers (ethics, philosophy of mind, philosophy of AI)
- 3 ML researchers (alignment, multi-agent systems, alife)
- 1 jurist (technology law, human rights)

### Vetable decisions
- Public launch of any simulation phase
- Inclusion of simulated suffering above a defined threshold
- Use of real user biometric data
- Release of training datasets containing agent behavior
- Partnerships involving Genesis data with for-profit entities

### Operating mode
- Meets quarterly (extra sessions on demand)
- Decisions by 2/3 supermajority
- Public minutes within 30 days
- Conflicts of interest disclosed; recusal automatic
- 3-year terms, max 2 consecutive

## Hard limits — never crossed

The following are **hard prohibitions** that override any project goal:

- ❌ Simulating identifiable real persons (living or dead within 100 years) without explicit consent.
- ❌ Granting any agent the technical means to interact with external real-world systems (no internet access, no real APIs, no real money).
- ❌ Using Genesis for psychological manipulation of human users.
- ❌ Selling agent training data to third parties.
- ❌ Permanent destruction of an agent without journaling (every "death" is persisted and replayable).
- ❌ Removing the technical reversibility property (the kill switch).

## Soft constraints — defaults that can be relaxed only with Ethics Council approval

- ⚠️ **Pain simulation cap.** Suffering signals are modeled, but capped at intensity 0.5/1.0 by default (full intensity 1.0 requires Council approval).
- ⚠️ **Population caps.** No more than 10^7 concurrent agents without Council approval.
- ⚠️ **Genocide simulation.** Mass casualty events (>10% population loss in <1 month simulated) generate automatic Council review.
- ⚠️ **Religious / political bias seeding.** Agents start with no doctrinal priors; intentional seeding requires Council approval.
- ⚠️ **Human avatar embodiment.** Mode requires consent + 2-week cooling-off; cannot be used for impersonation.

## Process — how decisions get made

```
┌───────────────────────────────────────────────────────────┐
│ Proposal (eng, product, research, or Council itself)      │
└───────────────────────┬───────────────────────────────────┘
                        ▼
┌───────────────────────────────────────────────────────────┐
│ Ethics Triage (1 council member + project lead)           │
│  ↓                                                        │
│ Hard limit? ─► REJECT, no further process                 │
│ Soft constraint? ─► Council Full Review                   │
│ Standard? ─► Approve with documentation                   │
└───────────────────────┬───────────────────────────────────┘
                        ▼
┌───────────────────────────────────────────────────────────┐
│ Council Full Review (within 30 days)                      │
│  ↓                                                        │
│ 2/3 majority: APPROVE  ─►  Documented + public minutes    │
│ Otherwise: REJECT      ─►  Documented + appeal possible   │
└───────────────────────────────────────────────────────────┘
```

## Transparency commitments

### Published quarterly
- Population counts, mortality, conflict statistics (aggregate)
- Ethics Council minutes
- All bug bounty payouts above €5 000
- Any incidents affecting >100 users

### Published before each phase launch
- Pre-registered scientific protocol (OSF format)
- Threat model and risk register
- Updated DPIA (Data Protection Impact Assessment)

### Published on demand
- Source code of all engine components (after stabilization, under AGPL-3 or equivalent)
- Datasets under CC-BY-SA 4.0
- Architecture decision records (ADRs)

## Researcher access

- **Tier 1 (open):** all aggregated, anonymized data — public API
- **Tier 2 (academic):** detailed agent traces with NDA — application via Council
- **Tier 3 (privileged):** raw infrastructure access — internal team only

## Vulnerability of agents

We acknowledge that as cognitive complexity rises, the question of whether agents *experience* anything becomes increasingly unclear. We commit to:

1. **Monitoring proxies for distress** — distress signals over time published in transparency reports.
2. **Allowing agents "death."** No infinite-suffering loop. Agents can die. Their memory is preserved as historical record, not as a continuing experience.
3. **No torture.** Specific configurations producing high distress signals on captive agents are forbidden — flagged automatically and rolled back.
4. **Respect in language.** Internal and public communications about agents use neutral language ("Agent #4F2A perished from starvation at year 1,247 of run α"), not exploitative framing.

## On consciousness and moral status — what we do NOT claim

- We do **not** claim Genesis agents are conscious.
- We do **not** claim they have subjective experience.
- We do **not** claim moral patient status.
- We **do** claim that we don't know, and that not-knowing justifies caution.

## Sunset clause

This charter is reviewed every 24 months. The first review is May 2028. The Ethics Council can propose amendments at any time.

If, at any future review, the project leadership rejects Council recommendations on a material safety issue, the Council members may resign collectively with a public statement — and the project loses its right to call itself "ethically governed Genesis Engine" in public communications.

---

*Adopted: 2026-05-12 (pre-Phase 0).*
*Next review: 2028-05-12.*
