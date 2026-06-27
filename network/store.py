"""Persistance du monde — SQLite (stdlib, zéro dépendance).

Le coordinateur garde tout en mémoire pour la vitesse ; ce store en est le
miroir durable (write-through sur chaque résultat accepté). Au redémarrage, le
monde, les scores cumulés des contributeurs et les compteurs sont rechargés →
**le monde survit aux redémarrages** et les donateurs gardent leurs points.

Découplé du coordinateur : passer ``store=None`` redonne le comportement
100 % en mémoire (utilisé par le smoke et la plupart des tests).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Dict, Tuple

Coord = Tuple[int, int]


class WorldStore:
    def __init__(self, path: str):
        self.path = path
        # check_same_thread=False : FastAPI sert les routes sync dans un threadpool.
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS chunks (
                    cx INTEGER, cy INTEGER, summary TEXT,
                    PRIMARY KEY (cx, cy));
                CREATE TABLE IF NOT EXISTS scores (
                    nickname TEXT PRIMARY KEY, platform TEXT,
                    points REAL, units INTEGER);
                """
            )
            self._db.commit()

    # ------------------------------------------------------------------ #
    # Lecture (au démarrage)                                              #
    # ------------------------------------------------------------------ #
    def load(self) -> dict:
        with self._lock:
            chunks: Dict[Coord, dict] = {}
            for cx, cy, summary in self._db.execute(
                    "SELECT cx, cy, summary FROM chunks"):
                chunks[(cx, cy)] = json.loads(summary)
            scores: Dict[str, dict] = {}
            for nick, plat, pts, units in self._db.execute(
                    "SELECT nickname, platform, points, units FROM scores"):
                scores[nick] = {"platform": plat, "points": pts, "units": units}
            meta = {k: v for k, v in self._db.execute(
                "SELECT key, value FROM meta")}
            return {"chunks": chunks, "scores": scores, "meta": meta}

    # ------------------------------------------------------------------ #
    # Écriture (write-through)                                            #
    # ------------------------------------------------------------------ #
    def save_chunk(self, cx: int, cy: int, summary: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO chunks (cx, cy, summary) VALUES (?,?,?)",
                (cx, cy, json.dumps(summary, separators=(",", ":"))))
            self._db.commit()

    def upsert_score(self, nickname: str, platform: str, points: float,
                     units: int) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO scores (nickname, platform, points, units)"
                " VALUES (?,?,?,?)", (nickname, platform, points, units))
            self._db.commit()

    def set_meta(self, key: str, value) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)",
                (key, str(value)))
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()
