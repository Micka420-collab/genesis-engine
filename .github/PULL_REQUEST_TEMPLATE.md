## 📝 Summary

<!-- 1-3 sentences. What does this PR change and why? -->

Fixes #<issue-number> <!-- or "No issue" -->

## 🎯 Type of change

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 🚀 New subsystem (e.g. new L2 module, new Reality Engine tick)
- [ ] 🔥 Breaking change (fix or feature that would cause existing behavior to not work as expected)
- [ ] 📚 Documentation update
- [ ] 🧪 Test / smoke addition
- [ ] ♻️ Refactor (no behavior change)

## 🧪 How was this tested?

- [ ] `runtime/scripts/p0_smoke.py` — PASS / FAIL / N/A
- [ ] `runtime/scripts/p12_integration_full.py` — PASS / FAIL / N/A
- [ ] New smoke test in `runtime/scripts/pN_<name>_smoke.py` — describe:
  - **Pass criteria**: ...
  - **Result**: ...
- [ ] Manual run on Earth-anchored world (Lausanne / Sahara / Amazon / Reykjavík)
- [ ] Multi-region demo (`runtime/scripts/multi_region_demo.py`)

## 🎲 Determinism preserved?

- [ ] Yes — same seed produces identical results
- [ ] No RNG involved
- [ ] N/A (docs / refactor only)

Method (if applicable): `prf_rng(seed, ["<namespace>"], [<params>])`

## 🏗️ Architecture conformity

Reference relevant section of `Genesis_Engine_Architecture_v1.0.docx`:

§____ <topic> — <briefly how this PR aligns>

## 📋 Checklist

- [ ] My code follows the [contributing guidelines](../CONTRIBUTING.md)
- [ ] I have used `engine.core.prf_rng` (no unseeded `random.*` or `np.random.*`)
- [ ] I have followed the **no-rewrite rule** (minimal Edit > Write for existing files)
- [ ] My smoke test has UTF-8 forced stdout (Windows cp1252 emoji breakage)
- [ ] I have updated `NEXT-SPRINT.md` if this completes a queued task
- [ ] I have linked the relevant ADR if architecture changes
- [ ] My commits follow conventional commits (`feat:`, `fix:`, `docs:`, `perf:`, ...)

## 🔭 Out-of-scope but related

What did I notice but intentionally did NOT touch in this PR? (Future issues to file.)

## 📸 Screenshots / journal excerpts

<!-- Paste key numbers from your run: agent counts, vocalizations, inventions, etc. -->

```
P0 SMOKE PASS
30/30 alive, 492 vocalizations, 7 innovations
```
