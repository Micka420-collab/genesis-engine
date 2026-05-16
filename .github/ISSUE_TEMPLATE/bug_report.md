---
name: 🐛 Bug report
about: Report a bug, crash, or unexpected behavior in Genesis Engine
title: "[BUG] <short description>"
labels: bug
assignees: ''
---

## 📝 Description

A clear, concise description of what the bug is.

## 🔁 Reproduction steps

```python
# Minimal repro code — paste here
from engine.world_builder import WorldBuilder
world = (WorldBuilder("repro").anchor(46.51, 6.63).build())
world.run(...)  # ← error happens here
```

1. Step 1
2. Step 2
3. ...

## ✅ Expected behavior

What you expected to happen.

## ❌ Actual behavior

What actually happened. Include full traceback if applicable:

```
Traceback (most recent call last):
  ...
```

## 🌍 Environment

- **OS**: (e.g. Windows 11 / Ubuntu 22.04 / macOS 14.4)
- **Python**: (e.g. 3.14.0)
- **NumPy**: (run `python -c "import numpy; print(numpy.__version__)"`)
- **rasterio**: (run `python -c "import rasterio; print(rasterio.__version__)"` — or "not installed")
- **pyproj**: (similarly)
- **Genesis Engine commit**: (run `git rev-parse HEAD` — or branch name)

## 📋 Smoke test status

Did you run the smoke tests? If yes, which passed/failed?

- [ ] `runtime/scripts/p0_smoke.py` — PASS / FAIL
- [ ] `runtime/scripts/p12_integration_full.py` — PASS / FAIL
- [ ] Other: ____

## 🔬 Determinism

Is the bug reproducible with the same seed?

- [ ] Yes, same seed → same crash
- [ ] No, seed-dependent
- [ ] Not tested

## 💡 Additional context

Any other context, screenshots, journal logs (`runtime/journals/...`) that might help.
