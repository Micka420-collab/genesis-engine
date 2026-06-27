"""Contrat réseau coordinateur ↔ worker (schémas Pydantic v2)."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

PROTOCOL_VERSION = "ge-net/1"


class RegisterRequest(BaseModel):
    nickname: str = Field(min_length=1, max_length=40)
    platform: str = "unknown"
    protocol_version: str = PROTOCOL_VERSION


class RegisterResponse(BaseModel):
    worker_id: str
    token: str
    world_seed: int
    protocol_version: str = PROTOCOL_VERSION
    motd: str = ""


class WorkUnit(BaseModel):
    unit_id: str
    world_seed: int
    cx: int
    cy: int
    ticks: int


class WorkBatch(BaseModel):
    units: List[WorkUnit] = Field(default_factory=list)
    poll_after_s: float = 1.0


class ChunkSummary(BaseModel):
    # Bornes anti-abus : un client est non fiable, on cadre tout ce qu'il envoie.
    cx: int = Field(ge=-1_000_000, le=1_000_000)
    cy: int = Field(ge=-1_000_000, le=1_000_000)
    ticks: int = Field(ge=1, le=1_000_000)
    biome: str = Field(max_length=32)
    color: str = Field(max_length=16)
    height_m: float
    food: float = Field(ge=0)
    wood: float = Field(ge=0)
    stone: float = Field(ge=0)
    water: float = Field(ge=0)
    population: int = Field(ge=0, le=1_000_000_000)
    digest: str = Field(min_length=64, max_length=64)


class WorkResult(BaseModel):
    unit_id: str = Field(max_length=128)
    worker_id: str = Field(max_length=64)
    token: str = Field(max_length=64)
    digest: str = Field(min_length=64, max_length=64)
    summary: ChunkSummary
    compute_ms: float = Field(default=0.0, ge=0)


class SubmitResponse(BaseModel):
    accepted: bool
    verified: bool
    credited_points: float = 0.0
    total_points: float = 0.0
    reason: str = ""


class QualityState(BaseModel):
    """Comment la puissance vérifiée se traduit en qualité du monde."""

    resolution_level: int
    world_radius_chunks: int
    ticks_per_unit: int
    agent_budget: int


class ContributorView(BaseModel):
    nickname: str
    platform: str
    points: float
    units: int
    last_seen_s_ago: float


class WorldState(BaseModel):
    world_seed: int
    protocol_version: str = PROTOCOL_VERSION
    total_points: float
    verified_units: int
    rejected_units: int
    active_workers: int
    chunks_done: int
    quality: QualityState
    leaderboard: List[ContributorView] = Field(default_factory=list)
    recent_events: List[str] = Field(default_factory=list)
    chunks: List[ChunkSummary] = Field(default_factory=list)
