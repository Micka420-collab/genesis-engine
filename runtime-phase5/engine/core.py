"""Genesis Engine — core primitives.

Determinism contract: every random number used in the simulation must derive
from `prf_rng(seed, ctx, indices)`. Calling `random.random()` directly is a bug.
"""
from __future__ import annotations

import hashlib
import struct
import uuid
from dataclasses import dataclass
from typing import Iterable

import numpy as np

# ---------------------------------------------------------------------------
# Tick / time scale
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Tick:
    n: int

    def next(self) -> "Tick":
        return Tick(self.n + 1)


TICK_DT_S = 1.0          # 1 tick = 1 simulated second (Phase 1)
TICKS_PER_DAY = 86_400
DAYS_PER_YEAR = 365


# ---------------------------------------------------------------------------
# PRF (pseudo-random function): BLAKE2b keyed → seed 64-bit → numpy PCG64
# ---------------------------------------------------------------------------

def _seed_key(world_seed: int) -> bytes:
    """Pack a 128-bit WorldSeed into a 32-byte key for keyed BLAKE2b."""
    ws = world_seed & ((1 << 128) - 1)
    lo = ws & ((1 << 64) - 1)
    hi = ws >> 64
    return struct.pack("<QQ", lo, hi) + struct.pack(">QQ", hi, lo)


def prf_bytes(world_seed: int, ctx: Iterable[str], indices: Iterable[int],
              n_bytes: int = 32) -> bytes:
    """BLAKE2b-keyed PRF returning `n_bytes` deterministic bytes."""
    key = _seed_key(world_seed)
    h = hashlib.blake2b(key=key[:64], digest_size=min(64, max(1, n_bytes)))
    for c in ctx:
        h.update(b"|")
        h.update(c.encode("utf-8"))
    for i in indices:
        h.update(b"|")
        h.update(struct.pack("<Q", int(i) & 0xFFFFFFFFFFFFFFFF))
    out = h.digest()
    while len(out) < n_bytes:
        out += hashlib.blake2b(out, key=key[:64], digest_size=64).digest()
    return out[:n_bytes]


def prf_rng(world_seed: int, ctx: Iterable[str], indices: Iterable[int]) -> np.random.Generator:
    """Return a deterministic numpy Generator (PCG64) seeded from the PRF."""
    raw = prf_bytes(world_seed, ctx, indices, n_bytes=16)
    seed64 = int.from_bytes(raw[:8], "little", signed=False)
    return np.random.Generator(np.random.PCG64(seed64))


# ---------------------------------------------------------------------------
# Agent / Sim identifiers
# ---------------------------------------------------------------------------

def derive_agent_id(world_seed: int, ctx: Iterable[str], indices: Iterable[int]) -> uuid.UUID:
    """Derive a UUIDv8 deterministically from (seed, ctx, indices)."""
    raw = prf_bytes(world_seed, ctx, indices, n_bytes=16)
    b = bytearray(raw)
    b[6] = (b[6] & 0x0F) | 0x80   # version 8
    b[8] = (b[8] & 0x3F) | 0x80   # variant RFC 9562
    return uuid.UUID(bytes=bytes(b))


def new_simulation_id() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Tick-chain hashing (integrity / replay verification)
# ---------------------------------------------------------------------------

def hash_state(arr_bytes: bytes) -> bytes:
    return hashlib.blake2b(arr_bytes, digest_size=32).digest()


def chain_tick_root(prev: bytes, delta: bytes) -> bytes:
    h = hashlib.blake2b(digest_size=32)
    h.update(prev)
    h.update(delta)
    return h.digest()
