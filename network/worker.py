"""Worker ``genesis donate`` — offre de la puissance au monde Genesis.

Stdlib pur (``urllib``) → tourne sur Windows / Linux / macOS sans dépendance.
Boucle : s'enregistrer → tirer des unités → calculer les chunks (worldgen
déterministe) → soumettre le hash → recommencer.
"""
from __future__ import annotations

import json
import platform
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from . import worldgen
from .protocol import PROTOCOL_VERSION

# Couleurs ANSI (désactivées si pas un terminal).
import sys as _sys
_TTY = hasattr(_sys.stdout, "isatty") and _sys.stdout.isatty()
def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _TTY else s


class HttpTransport:
    """Transport HTTP minimal (injectable pour les tests)."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def post(self, path: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.base_url + path, data=data,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def get(self, path: str) -> dict:
        req = urllib.request.Request(self.base_url + path, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))


@dataclass
class WorkerStats:
    units: int = 0
    points: float = 0.0
    rejected: int = 0


class Worker:
    def __init__(self, transport, nickname: str,
                 on_event: Optional[Callable[[str], None]] = None):
        self.t = transport
        self.nickname = nickname
        self.on_event = on_event or (lambda m: print(m))
        self.worker_id: Optional[str] = None
        self.token: Optional[str] = None
        self.world_seed: Optional[int] = None
        self.stats = WorkerStats()

    def register(self) -> None:
        resp = self.t.post("/api/register", {
            "nickname": self.nickname,
            "platform": f"{platform.system()}-{platform.machine()}",
            "protocol_version": PROTOCOL_VERSION,
        })
        self.worker_id = resp["worker_id"]
        self.token = resp["token"]
        self.world_seed = resp["world_seed"]
        self.on_event(_c("92", f"✓ Enregistré comme {self.nickname} "
                               f"(monde {self.world_seed:#x}). {resp.get('motd','')}"))

    def _do_unit(self, unit: dict) -> bool:
        t0 = time.perf_counter()
        chunk = worldgen.generate_chunk(unit["world_seed"], unit["cx"],
                                        unit["cy"], unit["ticks"])
        compute_ms = (time.perf_counter() - t0) * 1000.0
        resp = self.t.post("/api/submit", {
            "unit_id": unit["unit_id"], "worker_id": self.worker_id,
            "token": self.token, "digest": chunk.digest,
            "summary": chunk.summary(), "compute_ms": compute_ms,
        })
        if resp.get("accepted"):
            self.stats.units += 1
            self.stats.points += resp.get("credited_points", 0.0)
            return True
        self.stats.rejected += 1
        self.on_event(_c("91", f"  ✗ unité refusée : {resp.get('reason','?')}"))
        return False

    def run(self, max_units: Optional[int] = None, max_seconds: Optional[float] = None,
            poll=time.sleep) -> WorkerStats:
        if self.worker_id is None:
            self.register()
        start = time.time()
        idle = 0
        while True:
            if max_units is not None and self.stats.units >= max_units:
                break
            if max_seconds is not None and time.time() - start >= max_seconds:
                break
            batch = self.t.get(f"/api/work?worker_id={self.worker_id}")
            units = batch.get("units", [])
            if not units:
                idle += 1
                if max_units is not None and idle > 5:
                    break
                poll(min(batch.get("poll_after_s", 1.0), 2.0))
                continue
            idle = 0
            for unit in units:
                if max_units is not None and self.stats.units >= max_units:
                    break
                self._do_unit(unit)
            self.on_event(_c("96", f"  ⚙ {self.nickname}: {self.stats.units} chunks · "
                                   f"{self.stats.points:.1f} pts"))
            poll(batch.get("poll_after_s", 0.5))
        return self.stats


def donate(server: str, nickname: str, max_units: Optional[int] = None,
           max_seconds: Optional[float] = None) -> WorkerStats:
    """Point d'entrée haut niveau de ``genesis donate``."""
    banner = _c("95;1", "  ╔═══════════════════════════════════════════╗\n"
                        "  ║   GENESIS — don de puissance de calcul    ║\n"
                        "  ╚═══════════════════════════════════════════╝")
    print(banner)
    print(_c("90", f"  serveur : {server}   pseudo : {nickname}"))
    w = Worker(HttpTransport(server), nickname)
    try:
        stats = w.run(max_units=max_units, max_seconds=max_seconds)
    except KeyboardInterrupt:
        stats = w.stats
        print(_c("93", "\n  ⏹ arrêt demandé."))
    print(_c("92;1", f"\n  Merci ! {stats.units} chunks calculés · "
                     f"{stats.points:.1f} points offerts au monde."))
    return stats
