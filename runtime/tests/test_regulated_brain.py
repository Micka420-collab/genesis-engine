"""Wave 52 — heritable decoder wired into the live brain (gated).

These tests assert the property that turns the live policy from an
*observer-declared fixed* genotype→behaviour map into a *heritable, evolvable*
one: the regulatory region R reinterprets the cognition slice the brain reads.

Core properties:
  * the regulated view touches ONLY the cognition slice (additivity),
  * it is pure/deterministic and never mutates its input,
  * the neutral regulatory code (P≡0.5) recovers the legacy brain *byte-for-byte*
    (the formal basis of the zero-regression guarantee),
  * SEMANTIC CLOSURE in behaviour: two genomes identical on the structural
    region S but differing on the regulatory region R give identical legacy
    logits yet different regulated logits,
  * the live loop honours the flag (routes through the regulated view iff
    ``SimConfig.heritable_brain`` is True; default OFF).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from engine.core import prf_rng
from engine.genome import GENOME_SIZE, GENE_GROUP_COGNITION, attach_genome
from engine.genome_decoder import PhenotypeConfig
from engine.neat_brain import forward_policy, genome_action_index, N_INPUTS
from engine.regulated_brain import (
    REGULATION_AMPLITUDE, regulatory_modulation, regulated_genome_view,
    heritable_brain_enabled, regulation_summary,
)
from engine.sim import Simulation, SimConfig

CFG = PhenotypeConfig()
SEED = 0xC0FFEE_121
COG = GENE_GROUP_COGNITION


def _rand_genome(seed, idx):
    return prf_rng(seed, ["test", "genome"], [int(idx)]).random(
        GENOME_SIZE, dtype=np.float32)


def _rand_feats(seed, idx):
    return prf_rng(seed, ["test", "feats"], [int(idx)]).random(
        N_INPUTS, dtype=np.float32)


def test_view_touches_only_cognition_slice():
    g = _rand_genome(SEED, 0)
    v = regulated_genome_view(g, CFG)
    assert v.shape == (GENOME_SIZE,)
    assert not np.array_equal(v[COG], g[COG])           # cognition reinterpreted
    assert np.array_equal(v[:COG.start], g[:COG.start])  # everything else intact
    assert np.array_equal(v[COG.stop:], g[COG.stop:])


def test_view_deterministic_and_input_pure():
    g = _rand_genome(SEED, 1)
    snapshot = g.copy()
    v1 = regulated_genome_view(g, CFG)
    v2 = regulated_genome_view(g, CFG)
    assert np.array_equal(v1, v2)
    assert np.array_equal(g, snapshot)                  # input never mutated


def test_gain_within_bounds():
    gain = regulatory_modulation(_rand_genome(SEED, 2), CFG)
    lo, hi = 1.0 - REGULATION_AMPLITUDE, 1.0 + REGULATION_AMPLITUDE
    assert gain.shape == (COG.stop - COG.start,)
    assert np.all(gain >= lo - 1e-6) and np.all(gain <= hi + 1e-6)


def test_neutral_code_recovers_legacy_brain():
    """R≡0.5 ⇒ W≡0 ⇒ P≡0.5 ⇒ gain≡1 ⇒ regulated brain == legacy brain."""
    g = _rand_genome(SEED, 3)
    g[CFG.reg_start:CFG.reg_end] = 0.5
    v = regulated_genome_view(g, CFG)
    gain = regulatory_modulation(g, CFG)
    feats = _rand_feats(SEED, 0)
    assert float(np.max(np.abs(gain - 1.0))) < 1e-6
    assert np.array_equal(v[COG], g[COG])
    assert np.array_equal(forward_policy(g, feats), forward_policy(v, feats))


def test_semantic_closure_in_behaviour():
    """S identical, R differs ⇒ identical legacy logits, different regulated."""
    base = _rand_genome(SEED, 4)
    a = base.copy()
    b = base.copy()
    b[CFG.reg_start:CFG.reg_end] = _rand_genome(SEED, 5)[CFG.reg_start:CFG.reg_end]
    feats = _rand_feats(SEED, 1)
    # The brain reads only the cognition slice ⊂ S → it cannot see the R change.
    assert np.array_equal(forward_policy(a, feats), forward_policy(b, feats))
    # The regulated brain reinterprets the cognition slice through R → differs.
    la = forward_policy(regulated_genome_view(a, CFG), feats)
    lb = forward_policy(regulated_genome_view(b, CFG), feats)
    assert float(np.sqrt(np.sum((la - lb) ** 2))) > 1e-4


def test_behavioural_pleiotropy():
    """One regulatory change re-weights many cognition genes (emergent)."""
    base = _rand_genome(SEED, 4)
    a = base.copy()
    b = base.copy()
    b[CFG.reg_start:CFG.reg_end] = _rand_genome(SEED, 5)[CFG.reg_start:CFG.reg_end]
    changed = int((regulated_genome_view(a, CFG)[COG]
                   != regulated_genome_view(b, CFG)[COG]).sum())
    assert changed >= 32


def test_flag_defaults_off_and_gate_works():
    assert SimConfig().heritable_brain is False

    class _S:
        pass
    on = _S(); on.cfg = SimConfig(heritable_brain=True)
    off = _S(); off.cfg = SimConfig(heritable_brain=False)
    none = _S()                                          # no cfg at all
    assert heritable_brain_enabled(on) is True
    assert heritable_brain_enabled(off) is False
    assert heritable_brain_enabled(none) is False


def test_real_founder_policies_differ_under_regulation():
    sim = Simulation(SimConfig(
        name="rb_founders", seed=SEED & 0xFFFFFFFFFFFFFFFF,
        founders=8, max_agents=20, bounds_km=(0.5, 0.5),
        spawn_radius_m=50.0, drive_accel=1500.0, cultures=1))
    sim.step()
    attach_genome(sim.agents, int(sim.cfg.seed))
    n = sim.agents.n_active
    assert n >= 2
    feats = _rand_feats(SEED, 2)
    prf_u = float(prf_rng(SEED, ["test", "act"], [0]).random())
    diffs = 0
    for r in range(n):
        g = np.array(sim.agents.genome[r], copy=True)
        leg = genome_action_index(g, feats, prf_u=prf_u)
        reg = genome_action_index(regulated_genome_view(g, CFG), feats, prf_u=prf_u)
        if leg[0] != reg[0] or abs(leg[1] - reg[1]) > 1e-6:
            diffs += 1
    assert diffs >= 1


def test_regulation_summary_coherent():
    g = _rand_genome(SEED, 4)
    s = regulation_summary(g, CFG)
    lo, hi = 1.0 - REGULATION_AMPLITUDE, 1.0 + REGULATION_AMPLITUDE
    assert s["k_traits"] == CFG.k_traits
    assert s["gain_min"] >= lo - 1e-6 and s["gain_max"] <= hi + 1e-6
    assert s["is_neutral_code"] is False
    assert s["semantic_closure"].startswith("behaviour-side")
    gn = _rand_genome(SEED, 3)
    gn[CFG.reg_start:CFG.reg_end] = 0.5
    assert regulation_summary(gn, CFG)["is_neutral_code"] is True


# --- genome-brain decision hook (genome_decide is the genome brain) ---------
#
# The heritable decoder is wired into engine.neat_brain.genome_decide — the
# genome-encoded policy's decision function. These tests drive that function
# directly on real perceived observations (no global decide monkeypatch, so
# no cross-test leakage).

def _brain_sim(seed, heritable):
    sim = Simulation(SimConfig(
        name=f"rb_brain_{seed}", seed=seed & 0xFFFFFFFFFFFFFFFF,
        founders=8, max_agents=20, bounds_km=(0.5, 0.5),
        spawn_radius_m=50.0, drive_accel=1.0, cultures=1,
        heritable_brain=heritable))
    sim.step()                                   # spawn founders
    attach_genome(sim.agents, int(sim.cfg.seed))
    return sim


def _obs(sim, row):
    from engine.cognition import perceive
    return perceive(sim.agents, row, sim.streamer, grid=sim._grid, tick=sim.tick)


def test_genome_decide_honours_flag_on_real_agents():
    """Flipping heritable_brain changes the live policy decision for ≥1 agent;
    the flag-OFF decision is deterministic (zero-regression baseline)."""
    from engine.neat_brain import genome_decide
    sim = _brain_sim(2, heritable=False)
    n = sim.agents.n_active
    assert n >= 2
    diffs = 0
    for row in range(n):
        obs = _obs(sim, row)
        sim.cfg.heritable_brain = False
        d_off = genome_decide(sim.agents, obs, sim)
        sim.cfg.heritable_brain = True
        d_on = genome_decide(sim.agents, obs, sim)
        if d_off.action != d_on.action or abs(d_off.confidence - d_on.confidence) > 1e-9:
            diffs += 1
    assert diffs >= 1
    # flag-OFF path is deterministic.
    sim.cfg.heritable_brain = False
    obs0 = _obs(sim, 0)
    a = genome_decide(sim.agents, obs0, sim)
    b = genome_decide(sim.agents, obs0, sim)
    assert a.action == b.action and abs(a.confidence - b.confidence) < 1e-12


def test_genome_decide_gates_regulation_on_flag(monkeypatch):
    """genome_decide touches the regulated view iff the flag is ON
    (leak-free: monkeypatch auto-restores, no global decide patch)."""
    from engine import regulated_brain as rb
    from engine.neat_brain import genome_decide

    calls = {"n": 0}
    real = rb.regulated_genome_view

    def spy(g, cfg=None):
        calls["n"] += 1
        return real(g, cfg)

    monkeypatch.setattr(rb, "regulated_genome_view", spy)
    sim = _brain_sim(3, heritable=False)
    obs = _obs(sim, 0)

    sim.cfg.heritable_brain = False
    genome_decide(sim.agents, obs, sim)
    assert calls["n"] == 0               # OFF → regulated view never touched

    sim.cfg.heritable_brain = True
    genome_decide(sim.agents, obs, sim)
    assert calls["n"] >= 1               # ON → routed through the regulated view
