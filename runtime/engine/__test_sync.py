"""Deprecated dead-code placeholder.

This module used to hold ten unused module-level constants (``LINE_1`` …
``LINE_10``). They were never imported by any engine, test or experiment
file. The 2026-05-18 audit removed them. The module is kept as an empty
stub so any stale ``import engine.__test_sync`` does not break, but it
exposes no public surface.
"""
__all__: list[str] = []
