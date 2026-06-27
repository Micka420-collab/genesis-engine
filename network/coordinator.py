"""Coordinateur — serveur FastAPI du réseau de calcul mondial.

Responsabilités :
    1. **Assigner** des unités de travail (chunks) en spirale depuis l'origine.
    2. **Vérifier** chaque résultat par recalcul déterministe (anti-triche).
    3. **Créditer** la puissance offerte au classement des contributeurs.
    4. **Faire croître** le monde : plus de puissance vérifiée → rayon plus
       grand + résolution (``ticks_per_unit``) plus haute.
    5. **Diffuser** l'état live au site mondial (SSE + JSON).

Stateless-friendly : tout l'état vit dans une instance ``Coordinator`` ;
pour un VPS self-host on lance simplement ``uvicorn`` dessus.
"""
from __future__ import annotations

import asyncio
import math
import os
import secrets
import threading
import time
from collections import deque
from typing import Deque, Dict, Iterator, List, Optional, Tuple

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

from . import worldgen
from .protocol import (
    ChunkSummary,
    ContributorView,
    QualityState,
    RegisterRequest,
    RegisterResponse,
    SubmitResponse,
    WorkBatch,
    WorkResult,
    WorkUnit,
    WorldState,
    PROTOCOL_VERSION,
)

Coord = Tuple[int, int]
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

DEFAULT_WORLD_SEED = 0x6E_E7_2026  # "GE 2026"
STALE_AFTER_S = 30.0  # une unité assignée non rendue est ré-offerte après ce délai
BATCH_SIZE = 4
TRUST_AFTER = 5  # unités vérifiées-correctes avant de passer en échantillonnage
MAX_CONTRIBUTORS = 10_000  # garde-fou mémoire contre l'inondation d'inscriptions
PRUNE_AFTER_S = 3_600.0    # workers inactifs purgés (scores cumulés conservés)
MAX_BODY_BYTES = 64 * 1024  # taille max d'une requête (anti-DoS payload)


def spiral_coords() -> Iterator[Coord]:
    """(0,0), puis anneaux carrés (Chebyshev) croissants — expansion du monde.

    Chaque anneau de rayon ``r`` contient exactement ``8r`` cases (jamais de
    doublon), et le monde grandit du centre vers l'extérieur.
    """
    yield (0, 0)
    r = 1
    while True:
        for x in range(-r, r + 1):
            for y in range(-r, r + 1):
                if max(abs(x), abs(y)) == r:
                    yield (x, y)
        r += 1


class CapacityError(Exception):
    """Levée quand le réseau refuse de nouvelles inscriptions (anti-DoS)."""


class _Assignment:
    __slots__ = ("unit", "worker_id", "at")

    def __init__(self, unit: WorkUnit, worker_id: str, at: float):
        self.unit = unit
        self.worker_id = worker_id
        self.at = at


class Coordinator:
    """État partagé du réseau (thread-safe via RLock)."""

    def __init__(self, world_seed: int = DEFAULT_WORLD_SEED,
                 verify_fraction: float = 1.0, clock=time.time, store=None,
                 replication: int = 1):
        self.verify_fraction = verify_fraction
        self.replication = max(1, int(replication))
        self._clock = clock
        self._lock = threading.RLock()
        self.store = store
        # Mode quorum (replication >= 2) : N volontaires distincts calculent le
        # MÊME chunk, le serveur compare leurs hash (consensus) au lieu de
        # recalculer. quorum = majorité ; on autorise quelques replicas en plus
        # pour départager en cas de désaccord.
        self.quorum = max(1, self.replication // 2 + 1)
        self.max_replicas = self.replication if self.replication <= 1 else self.replication + 2
        self.pending: Dict[Coord, dict] = {}  # coord -> état de consensus en cours

        # contributors : session+réputation par worker_id (token, last_seen, bans).
        self.contributors: Dict[str, dict] = {}
        self.tokens: Dict[str, str] = {}
        # scores : cumul DURABLE par pseudo (persisté ; survit aux redémarrages).
        self.scores: Dict[str, dict] = {}
        self.done: Dict[Coord, dict] = {}            # coord -> ChunkSummary dict
        self.assignments: Dict[str, _Assignment] = {}  # unit_id -> assignment
        self.assigned_coords: Dict[Coord, str] = {}    # coord -> unit_id

        self.total_points = 0.0
        self.verified_units = 0
        self.rejected_units = 0
        self._unit_counter = 0
        self.events: Deque[str] = deque(maxlen=60)

        # Restauration depuis le store (le monde survit aux redémarrages).
        restored = 0
        if store is not None:
            snap = store.load()
            self.done = dict(snap["chunks"])
            self.scores = dict(snap["scores"])
            self.total_points = sum(s["points"] for s in self.scores.values())
            meta = snap["meta"]
            world_seed = int(meta.get("world_seed", world_seed))
            self.verified_units = int(meta.get("verified_units", len(self.done)))
            self.rejected_units = int(meta.get("rejected_units", 0))
            restored = len(self.done)
            store.set_meta("world_seed", world_seed)

        self.world_seed = world_seed
        self._spiral = spiral_coords()
        self._frontier: Deque[Coord] = deque()
        self._spiral_pos = 0
        if restored:
            self._emit(f"🌍 Monde {world_seed:#x} restauré : {restored} chunks, "
                       f"{self.total_points:.0f} pts.")
        else:
            self._emit(f"🌍 Monde {world_seed:#x} initialisé — en attente de puissance.")

    # ---------------------------------------------------------------- #
    # Qualité : comment la puissance vérifiée façonne le monde         #
    # ---------------------------------------------------------------- #
    def quality(self) -> QualityState:
        v = self.verified_units
        radius = 2 + int(math.isqrt(v) // 2)
        radius = min(radius, 64)
        level = 1 + int(math.log2(1.0 + self.total_points / 50.0))
        ticks = min(64 * (2 ** (level - 1)), 1024)
        agent_budget = sum(int(c.get("population", 0)) for c in self.done.values())
        return QualityState(resolution_level=level, world_radius_chunks=radius,
                            ticks_per_unit=ticks, agent_budget=agent_budget)

    def _emit(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S", time.gmtime(self._clock()))
        self.events.appendleft(f"[{ts}] {msg}")

    # ---------------------------------------------------------------- #
    # Frontière : coords libres à assigner dans le rayon courant       #
    # ---------------------------------------------------------------- #
    def _refill_frontier(self) -> None:
        radius = self.quality().world_radius_chunks
        # On précharge la spirale jusqu'à couvrir le carré (2r+1)^2.
        target = (2 * radius + 1) ** 2
        while self._spiral_pos < target:
            coord = next(self._spiral)
            self._spiral_pos += 1
            if (abs(coord[0]) <= radius and abs(coord[1]) <= radius
                    and coord not in self.done and coord not in self.assigned_coords):
                self._frontier.append(coord)

    def _reassign_stale(self) -> None:
        now = self._clock()
        stale = [uid for uid, a in self.assignments.items()
                 if now - a.at > STALE_AFTER_S]
        for uid in stale:
            a = self.assignments.pop(uid)
            coord = (a.unit.cx, a.unit.cy)
            self.assigned_coords.pop(coord, None)
            p = self.pending.get(coord)
            if p is not None and not p["finalized"]:
                p["assigned"].pop(a.worker_id, None)  # libère un slot quorum
            if coord not in self.done:
                self._frontier.appendleft(coord)

    # ---------------------------------------------------------------- #
    # API métier                                                       #
    # ---------------------------------------------------------------- #
    def _prune_workers(self) -> None:
        """Purge les sessions worker inactives (les scores cumulés restent)."""
        now = self._clock()
        dead = [wid for wid, c in self.contributors.items()
                if now - c["last_seen"] > PRUNE_AFTER_S]
        for wid in dead:
            self.contributors.pop(wid, None)
            self.tokens.pop(wid, None)

    def register(self, req: RegisterRequest) -> RegisterResponse:
        with self._lock:
            self._prune_workers()
            if len(self.contributors) >= MAX_CONTRIBUTORS:
                raise CapacityError("trop de workers actifs, réessaie plus tard")
            nick = req.nickname[:40]
            worker_id = "w_" + secrets.token_hex(8)
            token = secrets.token_hex(16)
            self.tokens[worker_id] = token
            self.contributors[worker_id] = {
                "nickname": nick, "platform": req.platform,
                "verified_count": 0, "banned": False, "last_seen": self._clock(),
            }
            # Le pseudo retrouve son score cumulé (persisté) s'il revient.
            sc = self.scores.setdefault(
                nick, {"platform": req.platform, "points": 0.0, "units": 0})
            sc["platform"] = req.platform
            sc["last_seen"] = self._clock()
            back = "  (bon retour !)" if sc["units"] else ""
            self._emit(f"⚡ {nick} ({req.platform}) rejoint le réseau.{back}")
            return RegisterResponse(
                worker_id=worker_id, token=token, world_seed=self.world_seed,
                motd="Merci d'offrir ta puissance au monde Genesis.")

    def get_work(self, worker_id: str) -> WorkBatch:
        with self._lock:
            contrib = self.contributors.get(worker_id)
            if contrib is None or contrib.get("banned"):
                return WorkBatch(units=[], poll_after_s=5.0)
            contrib["last_seen"] = self._clock()
            self._reassign_stale()
            self._refill_frontier()
            ticks = self.quality().ticks_per_unit
            coords = (self._pick_quorum_coords(worker_id) if self.replication > 1
                      else self._pick_simple_coords())
            units: List[WorkUnit] = []
            for coord in coords:
                self._unit_counter += 1
                uid = f"{coord[0]},{coord[1]}@{ticks}#{self._unit_counter}"
                unit = WorkUnit(unit_id=uid, world_seed=self.world_seed,
                                cx=coord[0], cy=coord[1], ticks=ticks)
                self.assignments[uid] = _Assignment(unit, worker_id, self._clock())
                self.assigned_coords[coord] = uid
                if self.replication > 1:
                    p = self.pending.setdefault(
                        coord, {"ticks": ticks, "assigned": {}, "subs": {},
                                "finalized": False})
                    p["assigned"][worker_id] = self._clock()
                units.append(unit)
            return WorkBatch(units=units, poll_after_s=0.5 if units else 2.0)

    def _pick_simple_coords(self) -> List[Coord]:
        """Mode simple (replication=1) : 1 worker par chunk."""
        out: List[Coord] = []
        while self._frontier and len(out) < BATCH_SIZE:
            coord = self._frontier.popleft()
            if coord in self.done or coord in self.assigned_coords:
                continue
            out.append(coord)
        return out

    def _pick_quorum_coords(self, worker_id: str) -> List[Coord]:
        """Mode quorum : assigne des chunks que ce worker n'a pas encore touchés
        et qui ont besoin de replicas distincts supplémentaires."""
        out: List[Coord] = []
        # 1) chunks déjà en cours mais manquant de replicas (pas vus par ce worker).
        for coord, p in self.pending.items():
            if len(out) >= BATCH_SIZE:
                break
            if p["finalized"]:
                continue
            seen = set(p["assigned"]) | set(p["subs"])
            if worker_id in seen or len(seen) >= self.max_replicas:
                continue
            out.append(coord)
        # 2) nouveaux chunks de la frontière.
        while self._frontier and len(out) < BATCH_SIZE:
            coord = self._frontier.popleft()
            if coord in self.done or coord in self.pending:
                continue
            out.append(coord)
        return out

    def _should_verify(self, unit_id: str, worker_id: str) -> bool:
        """Décide si on RECALCULE l'unité (coût serveur) ou si on fait confiance.

        Réputation : un worker doit d'abord prouver ``TRUST_AFTER`` unités
        correctes (toutes recalculées) ; ensuite il n'est plus audité qu'à la
        fraction ``verify_fraction`` → c'est ce qui **décharge réellement le
        CPU du serveur** (il ne refait plus tout le travail des workers fiables).
        """
        if self.verify_fraction >= 1.0:
            return True
        if self.contributors.get(worker_id, {}).get("verified_count", 0) < TRUST_AFTER:
            return True  # phase de mise en confiance : tout est vérifié
        # Audit aléatoire déterministe pour les workers fiables.
        seed = int.from_bytes(worldgen.prf_bytes(0, ["verify", unit_id], [], 4), "big")
        return (seed % 1000) / 1000.0 < self.verify_fraction

    def submit(self, res: WorkResult) -> SubmitResponse:
        with self._lock:
            # Authentification du worker (comparaison de token à temps constant).
            contrib = self.contributors.get(res.worker_id)
            tok = self.tokens.get(res.worker_id)
            if (contrib is None or tok is None
                    or not secrets.compare_digest(tok, res.token)):
                return SubmitResponse(accepted=False, verified=False,
                                      reason="worker inconnu ou token invalide")
            if contrib.get("banned"):
                return SubmitResponse(accepted=False, verified=False,
                                      reason="worker banni (triche détectée)")
            a = self.assignments.get(res.unit_id)
            if a is None:
                return SubmitResponse(accepted=False, verified=False,
                                      reason="unité non assignée ou expirée")
            # L'unité doit appartenir au worker qui la rend (pas de vol de crédit).
            if a.worker_id != res.worker_id:
                return SubmitResponse(accepted=False, verified=False,
                                      reason="unité assignée à un autre worker")
            coord = (a.unit.cx, a.unit.cy)
            nick = contrib["nickname"]

            def _reject(reason: str, ban: bool, verified: bool) -> SubmitResponse:
                self.rejected_units += 1
                if ban:
                    contrib["banned"] = True  # tricheur exclu → dégâts bornés
                self.assignments.pop(res.unit_id, None)
                self.assigned_coords.pop(coord, None)
                p = self.pending.get(coord)
                if p is not None and not p["finalized"]:
                    p["assigned"].pop(res.worker_id, None)  # autres replicas continuent
                elif coord not in self.done:
                    self._frontier.appendleft(coord)
                self._emit(f"🚫 {nick} : rejeté @ {coord} ({reason}).")
                if self.store is not None:
                    self.store.set_meta("rejected_units", self.rejected_units)
                return SubmitResponse(accepted=False, verified=verified,
                                      reason=reason)

            verified = False
            truth = None
            if self._should_verify(res.unit_id, res.worker_id):
                # Vérification forte : on recalcule le chunk (coût serveur).
                truth = worldgen.generate_chunk(self.world_seed, a.unit.cx,
                                                a.unit.cy, a.unit.ticks)
                if truth.digest != res.digest:
                    return _reject("digest invalide (recalcul ≠)", ban=True,
                                   verified=True)
                verified = True
                contrib["verified_count"] += 1
            else:
                # Chemin de confiance : on ne recalcule pas, MAIS on lie le résumé
                # à son hash (anti-empoisonnement) — coût O(1), pas la boucle.
                s = res.summary
                expected = worldgen.chunk_digest(
                    self.world_seed, a.unit.cx, a.unit.cy, a.unit.ticks,
                    s.biome, s.food, s.wood, s.stone, s.water, s.population)
                if expected != res.digest:
                    return _reject("résumé incohérent avec le hash", ban=True,
                                   verified=False)

            contrib["last_seen"] = self._clock()
            # Sur le chemin vérifié, on garde la VÉRITÉ serveur (jamais la copie
            # client) : un bon hash + faux résumé ne peut pas passer.
            summary = (truth.summary() if truth is not None
                       else res.summary.model_dump())
            self.assignments.pop(res.unit_id, None)
            self.assigned_coords.pop(coord, None)

            if self.replication <= 1:
                # Mode simple : 1 worker fait foi → crédit + finalisation immédiate.
                points = self._credit(nick, contrib["platform"], a.unit.ticks)
                self._finalize(coord, summary)
                return SubmitResponse(accepted=True, verified=verified,
                                      credited_points=points,
                                      total_points=self.total_points)
            # Mode quorum : on enregistre la voix et on finalise au consensus.
            return self._record_quorum(coord, res, a, contrib, nick,
                                       verified, summary)

    # ---------------------------------------------------------------- #
    # Crédit / finalisation / consensus                                #
    # ---------------------------------------------------------------- #
    def _credit(self, nick: str, platform: str, ticks: int) -> float:
        points = ticks / 64.0
        self.total_points += points
        sc = self.scores.setdefault(
            nick, {"platform": platform, "points": 0.0, "units": 0})
        sc["points"] += points
        sc["units"] += 1
        sc["platform"] = platform
        sc["last_seen"] = self._clock()
        if self.store is not None:
            self.store.upsert_score(nick, sc["platform"], sc["points"], sc["units"])
        return points

    def _finalize(self, coord: Coord, summary: dict) -> None:
        self.done[coord] = summary
        self.verified_units += 1
        self.pending.pop(coord, None)
        if self.store is not None:
            self.store.save_chunk(coord[0], coord[1], summary)
            self.store.set_meta("verified_units", self.verified_units)
        if self.verified_units % 25 == 0:
            q = self.quality()
            self._emit(f"✨ Le monde s'étend : rayon {q.world_radius_chunks} "
                       f"chunks, résolution niveau {q.resolution_level}.")

    def _record_quorum(self, coord, res, a, contrib, nick, verified,
                       summary) -> SubmitResponse:
        p = self.pending.get(coord)
        if p is None or p["finalized"]:
            # Chunk déjà finalisé : replica tardif.
            final = self.done.get(coord)
            if final is not None and final.get("digest") == res.digest:
                pts = self._credit(nick, contrib["platform"], a.unit.ticks)
                return SubmitResponse(accepted=True, verified=verified,
                                      credited_points=pts,
                                      total_points=self.total_points,
                                      reason="consensus déjà atteint")
            contrib["banned"] = True
            self.rejected_units += 1
            self._emit(f"🚫 {nick} : désaccord avec le consensus @ {coord} → banni.")
            return SubmitResponse(accepted=False, verified=verified,
                                  reason="désaccord avec le consensus établi")

        p["assigned"].pop(res.worker_id, None)
        p["subs"][res.worker_id] = {
            "digest": res.digest, "summary": summary, "nick": nick,
            "ticks": a.unit.ticks, "platform": contrib["platform"]}

        tally: Dict[str, int] = {}
        for s in p["subs"].values():
            tally[s["digest"]] = tally.get(s["digest"], 0) + 1
        win_digest, votes = max(tally.items(), key=lambda kv: kv[1])
        distinct = len(set(p["assigned"]) | set(p["subs"]))

        reached = votes >= self.quorum
        exhausted = distinct >= self.max_replicas
        if not (reached or exhausted):
            return SubmitResponse(accepted=True, verified=verified,
                                  credited_points=0.0,
                                  total_points=self.total_points,
                                  reason=f"en attente de consensus ({votes}/{self.quorum})")

        # Finalisation : on crédite les gagnants ; on bannit les dissidents
        # uniquement si un vrai quorum (majorité claire) les contredit.
        win_summary = next(s["summary"] for s in p["subs"].values()
                           if s["digest"] == win_digest)
        credited_self = 0.0
        for wid, s in p["subs"].items():
            c = self.contributors.get(wid)
            if s["digest"] == win_digest:
                pts = self._credit(s["nick"], s["platform"], s["ticks"])
                if wid == res.worker_id:
                    credited_self = pts
            elif reached:
                if c is not None:
                    c["banned"] = True
                self.rejected_units += 1
                self._emit(f"🚫 {s['nick']} : minoritaire vs consensus @ {coord} → banni.")
        p["finalized"] = True
        self._finalize(coord, win_summary)
        why = (f"consensus atteint ({votes}/{self.quorum})" if reached
               else f"finalisé par pluralité ({votes})")
        return SubmitResponse(accepted=True, verified=verified,
                              credited_points=credited_self,
                              total_points=self.total_points, reason=why)

    def state(self, include_chunks: bool = True) -> WorldState:
        with self._lock:
            now = self._clock()
            active = sum(1 for c in self.contributors.values()
                         if not c.get("banned") and now - c["last_seen"] < 60.0)
            board = sorted(self.scores.items(),
                           key=lambda kv: kv[1]["points"], reverse=True)[:20]
            leaderboard = [
                ContributorView(
                    nickname=nick, platform=sc.get("platform", "?"),
                    points=round(sc["points"], 2), units=sc["units"],
                    last_seen_s_ago=round(now - sc.get("last_seen", now), 1))
                for nick, sc in board
            ]
            chunks = ([ChunkSummary(**s) for s in self.done.values()]
                      if include_chunks else [])
            return WorldState(
                world_seed=self.world_seed, total_points=round(self.total_points, 2),
                verified_units=self.verified_units, rejected_units=self.rejected_units,
                active_workers=active, chunks_done=len(self.done),
                quality=self.quality(), leaderboard=leaderboard,
                recent_events=list(self.events)[:20], chunks=chunks)


# --------------------------------------------------------------------------- #
# Application FastAPI                                                          #
# --------------------------------------------------------------------------- #


def create_app(coord: Optional[Coordinator] = None) -> FastAPI:
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse

    coord = coord or Coordinator()
    app = FastAPI(title="Genesis Network Coordinator", version=PROTOCOL_VERSION)
    app.state.coord = coord

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl is not None and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "payload trop volumineux"},
                                status_code=413)
        return await call_next(request)

    @app.post("/api/register", response_model=RegisterResponse)
    def register(req: RegisterRequest) -> RegisterResponse:
        try:
            return coord.register(req)
        except CapacityError as e:
            raise HTTPException(status_code=429, detail=str(e))

    @app.get("/api/work", response_model=WorkBatch)
    def work(worker_id: str = "") -> WorkBatch:
        if len(worker_id) > 64:
            raise HTTPException(status_code=400, detail="worker_id invalide")
        return coord.get_work(worker_id)

    @app.post("/api/submit", response_model=SubmitResponse)
    def submit(res: WorkResult) -> SubmitResponse:
        return coord.submit(res)

    @app.get("/api/state", response_model=WorldState)
    def state(chunks: bool = True) -> WorldState:
        return coord.state(include_chunks=chunks)

    @app.get("/api/events")
    async def events():
        async def gen():
            last = None
            while True:
                snap = coord.state(include_chunks=True)
                payload = snap.model_dump_json()
                if payload != last:
                    yield f"data: {payload}\n\n"
                    last = payload
                await asyncio.sleep(1.0)
        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        path = os.path.join(WEB_DIR, "index.html")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        return "<h1>Genesis Network</h1><p>web/index.html manquant.</p>"

    @app.get("/client")
    def client():
        """Sert le client de don autonome mono-fichier (curl ... | python3 -)."""
        from fastapi.responses import PlainTextResponse
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "standalone_donate.py")
        with open(path, encoding="utf-8") as fh:
            return PlainTextResponse(fh.read(), media_type="text/x-python")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "protocol": PROTOCOL_VERSION}

    return app
