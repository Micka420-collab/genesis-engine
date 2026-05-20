"""Emergent action resolution — genome latent → action, not priority scripts.

Replaces the heuristic ``decide()`` ordering when ``wire_emergence_v2`` is
installed. ActionKind remains the execution ABI; *which* action fires is
chosen from DNA + perception, not hardcoded social/mate blocks.
"""
from __future__ import annotations

from typing import Callable, Optional

from engine.cognition import Decision, Observation
from engine.neat_brain import genome_decide


def emergent_decide(agents, obs: Observation, sim,
                    *,
                    fallback: Optional[Callable] = None) -> Decision:
    """Genome brain first; optional legacy fallback if disabled."""
    if sim is not None and getattr(sim, "_genome_brain_enabled", True):
        try:
            return genome_decide(agents, obs, sim)
        except Exception:
            pass
    if fallback is not None:
        return fallback(agents, obs, sim)
    return Decision.idle()


def install_emergent_cognition(sim, *, enable: bool = True) -> None:
    """Patch ``engine.cognition.decide`` once (idempotent)."""
    if getattr(sim, "_emergent_cognition_installed", False):
        sim._genome_brain_enabled = bool(enable)
        return
    import engine.cognition as cog

    original = cog.decide
    sim._cognition_decide_original = original
    sim._genome_brain_enabled = bool(enable)

    def patched(agents, obs, sim_ref=None):
        return emergent_decide(agents, obs, sim_ref, fallback=original)

    cog.decide = patched
    sim._emergent_cognition_installed = True


def restore_legacy_cognition(sim) -> None:
    """Restore heuristic decide (tests)."""
    import engine.cognition as cog
    orig = getattr(sim, "_cognition_decide_original", None)
    if orig is not None:
        cog.decide = orig


__all__ = ["emergent_decide", "install_emergent_cognition", "restore_legacy_cognition"]
