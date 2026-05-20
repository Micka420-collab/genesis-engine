"""P55 — Wave 25 offline NCA training smoke.

Validates that :func:`engine.nca_training.train_nca_weights` performs
real finite-difference gradient descent on the multi-channel NCA
hyperparameters, producing a learned config with lower loss than the
hand-tuned starting point.

  1. Public API surface present.
  2. Deterministic training : two runs with same seed -> identical
     loss_history.
  3. Training set built : n_chunks_used > 0.
  4. Initial loss > 0 (the student really differs from the teacher).
  5. Final loss < initial loss (learning improves).
  6. Improvement >= 5 % (significant, not noise).
  7. All learned weights are non-negative (clamped correctly).
  8. Applying learned config to a fresh chunk yields a different
     output than applying hand-tuned defaults.
  9. ``LEARNED_NCA_CONFIG`` is a valid ``NCAMultiChannelConfig``
     usable directly with ``refine_chunk_multichannel``.
"""
from __future__ import annotations

import io
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

import numpy as np                                                      # noqa: E402

from engine.world import generate_chunk, TerrainParams                  # noqa: E402
from engine.nca_multichannel import (NCAMultiChannelConfig,             # noqa: E402
                                      refine_chunk_multichannel)
from engine.nca_training import (                                       # noqa: E402
    NCATrainingConfig, NCATrainingResult,
    train_nca_weights, refresh_learned_weights,
    LEARNED_NCA_CONFIG,
)


def _row(label, ok, detail=""):
    return f"  [{'OK  ' if ok else 'FAIL'}] {label:62s} {detail}"


def main() -> int:
    print("=" * 78)
    print("P55 — Wave 25 offline NCA training smoke")
    print("=" * 78)
    failures = 0

    # Step 1 — API surface.
    ok = all(name in globals() for name in (
        "NCATrainingConfig", "NCATrainingResult",
        "train_nca_weights", "refresh_learned_weights",
        "LEARNED_NCA_CONFIG"))
    print(_row("step 1 - public API exposed", ok, ""))
    if not ok:
        failures += 1

    # Step 2 — deterministic training.
    tcfg = NCATrainingConfig(
        n_chunks=2, reference_iters=12, student_iters=6,
        n_gradient_steps=4, learning_rate=8e-3,
        seed=0xC0FFEE_55 & 0xFFFFFFFFFFFFFFFF,
    )
    print("        running training (may take ~15-30s)...")
    res_a = train_nca_weights(tcfg)
    res_b = train_nca_weights(tcfg)
    ok = (res_a.loss_history == res_b.loss_history
          and res_a.learned_weights == res_b.learned_weights)
    print(_row("step 2 - deterministic training (same seed)",
               ok, f"len_hist={len(res_a.loss_history)} "
                   f"initial={res_a.initial_loss:.4f}"))
    if not ok:
        failures += 1

    # Step 3 — training set built.
    ok = res_a.n_chunks_used > 0
    print(_row("step 3 - training set built",
               ok, f"n_chunks_used={res_a.n_chunks_used} "
                   f"(requested {tcfg.n_chunks})"))
    if not ok:
        failures += 1

    # Step 4 — initial loss > 0.
    ok = res_a.initial_loss > 0.0
    print(_row("step 4 - initial loss > 0 (student != teacher)",
               ok, f"initial_loss={res_a.initial_loss:.4f}"))
    if not ok:
        failures += 1

    # Step 5 — final loss < initial loss.
    ok = res_a.final_loss < res_a.initial_loss
    print(_row("step 5 - final < initial (learning works)",
               ok, f"initial={res_a.initial_loss:.4f} "
                   f"final={res_a.final_loss:.4f}"))
    if not ok:
        failures += 1

    # Step 6 — improvement >= 5 %.
    ok = res_a.improvement_pct >= 5.0
    print(_row("step 6 - improvement >= 5%",
               ok, f"improvement={res_a.improvement_pct:.1f}%"))
    if not ok:
        failures += 1

    # Step 7 — all learned weights non-negative.
    ok = all(v >= 0.0 for v in res_a.learned_weights.values())
    print(_row("step 7 - all learned weights non-negative",
               ok, f"min_weight={min(res_a.learned_weights.values()):.4f}"))
    if not ok:
        failures += 1

    # Step 8 — applying learned config produces different output than default.
    seed = 0xCAFEBABE_42 & 0xFFFFFFFFFFFFFFFF
    params = TerrainParams()
    # Pick a land chunk
    test_coord = None
    for c in [(100, 100, 0), (50, 50, 0), (200, 50, 0)]:
        probe = generate_chunk(seed, c, params)
        if (probe.height > 0).mean() > 0.3:
            test_coord = c
            break
    assert test_coord is not None
    ch_default = generate_chunk(seed, test_coord, params)
    ch_learned = generate_chunk(seed, test_coord, params)
    refine_chunk_multichannel(ch_default, NCAMultiChannelConfig(iterations=6))
    refine_chunk_multichannel(ch_learned, res_a.learned_config)
    diff = float(np.abs(ch_default.height - ch_learned.height).mean())
    ok = diff > 1e-4
    print(_row("step 8 - learned config produces different output",
               ok, f"mean_diff={diff:.4f}m"))
    if not ok:
        failures += 1

    # Step 9 — LEARNED_NCA_CONFIG is usable.
    ch_emb = generate_chunk(seed, test_coord, params)
    try:
        dec = refine_chunk_multichannel(ch_emb, LEARNED_NCA_CONFIG)
        ok = (dec.iterations == LEARNED_NCA_CONFIG.iterations
              and isinstance(LEARNED_NCA_CONFIG, NCAMultiChannelConfig))
    except Exception as e:
        ok = False
        print(f"        error: {e}")
    print(_row("step 9 - LEARNED_NCA_CONFIG usable out-of-the-box",
               ok, f"iters={dec.iterations if ok else '?'} "
                   f"h_diffuse={LEARNED_NCA_CONFIG.h_diffuse:.4f}"))
    if not ok:
        failures += 1

    # Diagnostics dump.
    print(f"\nLearned weights after {tcfg.n_gradient_steps} GD steps:")
    for w, v in res_a.learned_weights.items():
        init_v = getattr(res_a.initial_config, w)
        delta = v - init_v
        print(f"  {w:30s}  init={init_v:7.4f}  learned={v:7.4f}  "
              f"Δ={delta:+.4f}")
    print(f"\nLoss history: {[f'{l:.4f}' for l in res_a.loss_history]}")
    print(f"Initial loss : {res_a.initial_loss:.4f}")
    print(f"Final loss   : {res_a.final_loss:.4f}")
    print(f"Improvement  : {res_a.improvement_pct:.1f} %")

    total = 9
    passed = total - failures
    print("=" * 78)
    if failures == 0:
        print(f"RESULT: {total}/{total} PASS")
        return 0
    else:
        print(f"RESULT: {passed}/{total} PASS, {failures} FAIL")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
