---
name: ✨ Feature request
about: Suggest a new feature, subsystem, or improvement for Genesis Engine
title: "[FEAT] <short description>"
labels: enhancement
assignees: ''
---

## 🎯 What problem does this solve?

Describe the gap or use case. Reference relevant sections of [`Genesis_Engine_Architecture_v1.0.docx`](../../Genesis_Engine_Architecture_v1.0.docx) if applicable (e.g. §15 economy, §17 trades, §22 religion).

## 💡 Proposed solution

A clear description of what you want to happen.

```python
# Pseudo-code or API sketch
world.set_trade_specialization(enabled=True)
# → agents develop stable roles: hunter / farmer / artisan
```

## 🌐 How it fits the architecture

- [ ] **Phase X** of the roadmap (cite from [`../../ROADMAP.md`](../../ROADMAP.md))
- [ ] **Pillar X** of FUTURE-VISION (cite from [`../../FUTURE-VISION.md`](../../FUTURE-VISION.md))
- [ ] **Layer**: L1 Earth-Seed / L2 Sim-Lift / Reality Engine / Phase 5cd cognition / other ____
- [ ] **Side-system**: orthogonal, no layer impact

## 🔬 Validation criteria

What measurable smoke test would prove this feature works?

```
P-NEW: <smoke test name> in `runtime/scripts/pN_<name>_smoke.py`
- Runs N ticks
- Asserts: <specific event count / value range>
- Expected output: ...
```

## 🎲 Determinism

How will determinism be preserved?

- [ ] Pure arithmetic, no RNG needed
- [ ] RNG via `engine.core.prf_rng(seed, ["my_subsystem", "purpose"], [agent_row, sim.tick])`
- [ ] External data ingestion — describe caching strategy

## ⚠️ Alternatives considered

What other approaches did you consider? Why is the proposed one better?

## 📚 References

Papers, repos, prior art, ADRs in `../../adr/`.

## 💪 I can help implement

- [ ] Yes, I'd like to work on this myself
- [ ] No, just suggesting
- [ ] Maybe — needs guidance
