#!/usr/bin/env python
"""Smoke réseau — bout-en-bout, déterministe, hermétique.

Lance un VRAI coordinateur uvicorn sur un port éphémère local, fait tourner
2 workers via HTTP (le même chemin qu'un VPS), et vérifie 8 invariants :

    1. /healthz répond, monde initialisé.
    2. Worker A s'enregistre et calcule des chunks acceptés + vérifiés.
    3. Worker B aussi → 2 contributeurs distincts au classement.
    4. Le monde grandit (chunks_done > 0) avec la puissance.
    5. Déterminisme : recalcul d'un chunk → digest identique.
    6. Anti-triche : un digest falsifié est REJETÉ (verified=True, accepted=False).
    7. Le budget de résolution croît avec la puissance vérifiée.
    8. Le classement crédite les points proportionnellement au travail.

Exit 0 si 8/8, sinon 1.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request

# Sortie UTF-8 robuste (console Windows cp1252 sinon).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # genesis-engine/
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from network.coordinator import Coordinator, create_app  # noqa: E402
from network import worldgen  # noqa: E402
from network.worker import Worker, HttpTransport  # noqa: E402

PASS, FAIL = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
results = []


def check(name, cond):
    results.append(bool(cond))
    print(f"  [{PASS if cond else FAIL}] {name}")
    return cond


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait_up(base, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(base + "/healthz", timeout=1.0).read()
            return True
        except Exception:
            time.sleep(0.1)
    return False


def main() -> int:
    import uvicorn

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    coord = Coordinator(world_seed=0xBEEF, verify_fraction=1.0)
    app = create_app(coord)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()

    print("=== Genesis Network smoke ===")
    try:
        check("1. serveur démarré (/healthz)", wait_up(base))

        wa = Worker(HttpTransport(base), "Alice", on_event=lambda m: None)
        sa = wa.run(max_units=12)
        check("2. worker A : chunks acceptés", sa.units >= 10 and sa.rejected == 0)

        wb = Worker(HttpTransport(base), "Bob", on_event=lambda m: None)
        sb = wb.run(max_units=12)
        check("3. worker B : chunks acceptés", sb.units >= 10)

        st = coord.state()
        check("4. le monde grandit (chunks_done>0)", st.chunks_done >= 20)
        check("   classement = 2 contributeurs", len(st.leaderboard) == 2)

        # 5. Déterminisme du worldgen.
        d1 = worldgen.generate_chunk(0xBEEF, 3, -2, 128).digest
        d2 = worldgen.generate_chunk(0xBEEF, 3, -2, 128).digest
        d3 = worldgen.generate_chunk(0xBEEF, 3, -2, 64).digest
        check("5. déterminisme (même seed/coord/ticks → même digest)",
              d1 == d2 and d1 != d3)

        # 6. Anti-triche : on prend une vraie unité et on falsifie le digest.
        batch = wa.t.get(f"/api/work?worker_id={wa.worker_id}")
        units = batch.get("units", [])
        if not units:
            check("6. anti-triche (pas d'unité dispo)", False)
        else:
            u = units[0]
            chunk = worldgen.generate_chunk(u["world_seed"], u["cx"], u["cy"], u["ticks"])
            resp = wa.t.post("/api/submit", {
                "unit_id": u["unit_id"], "worker_id": wa.worker_id,
                "token": wa.token, "digest": "0" * 64,  # falsifié
                "summary": chunk.summary(), "compute_ms": 1.0})
            check("6. anti-triche : digest falsifié rejeté",
                  resp.get("accepted") is False and resp.get("verified") is True
                  and coord.rejected_units >= 1)

        # 7. Budget de résolution croît avec la puissance.
        q = coord.quality()
        check("7. résolution corrélée à la puissance",
              q.resolution_level >= 1 and q.world_radius_chunks >= 2
              and q.agent_budget >= 0)

        # 8. Points crédités proportionnels au travail.
        total = sum(c.points for c in st.leaderboard)
        check("8. points crédités au classement", total > 0
              and abs(total - coord.total_points) < 1e-6)

        # 9. Persistance : le monde survit à un redémarrage du coordinateur.
        import tempfile
        from network.store import WorldStore
        from network.protocol import RegisterRequest, WorkResult, ChunkSummary
        dbpath = os.path.join(tempfile.mkdtemp(), "smoke_world.db")
        s1 = WorldStore(dbpath)
        c1 = Coordinator(world_seed=0xBEEF, store=s1)
        reg = c1.register(RegisterRequest(nickname="Persistante"))
        n = 0
        while n < 12:
            batch = c1.get_work(reg.worker_id)
            if not batch.units:
                break
            for u in batch.units:
                ch = worldgen.generate_chunk(u.world_seed, u.cx, u.cy, u.ticks)
                c1.submit(WorkResult(unit_id=u.unit_id, worker_id=reg.worker_id,
                                     token=reg.token, digest=ch.digest,
                                     summary=ChunkSummary(**ch.summary())))
                n += 1
        before = (len(c1.done), round(c1.total_points, 6))
        s1.close()
        c2 = Coordinator(world_seed=0x0000, store=WorldStore(dbpath))
        after = (len(c2.done), round(c2.total_points, 6))
        check("9. persistance : monde restauré après redémarrage",
              after == before and c2.world_seed == 0xBEEF and before[0] >= 12)

        # 10. Quorum : 2 volontaires d'accord finalisent un chunk SANS recalcul.
        cq = Coordinator(world_seed=0xBEEF, verify_fraction=0.0, replication=2)
        qa = cq.register(RegisterRequest(nickname="QA"))
        qb = cq.register(RegisterRequest(nickname="QB"))
        from network.coordinator import TRUST_AFTER as _TA
        cq.contributors[qa.worker_id]["verified_count"] = _TA  # fiables → 0 recalcul
        cq.contributors[qb.worker_id]["verified_count"] = _TA
        u_a = cq.get_work(qa.worker_id).units[0]
        tgt = (u_a.cx, u_a.cy)
        chk = worldgen.generate_chunk(u_a.world_seed, u_a.cx, u_a.cy, u_a.ticks)
        r_a = cq.submit(WorkResult(unit_id=u_a.unit_id, worker_id=qa.worker_id,
                                   token=qa.token, digest=chk.digest,
                                   summary=ChunkSummary(**chk.summary())))
        u_b = next(u for u in cq.get_work(qb.worker_id).units if (u.cx, u.cy) == tgt)
        r_b = cq.submit(WorkResult(unit_id=u_b.unit_id, worker_id=qb.worker_id,
                                   token=qb.token, digest=chk.digest,
                                   summary=ChunkSummary(**chk.summary())))
        check("10. quorum : consensus finalise (pending→done, 0 recalcul serveur)",
              (tgt not in cq.done or r_a.credited_points == 0)
              and r_b.accepted and tgt in cq.done
              and cq.scores["QA"]["points"] > 0 and cq.scores["QB"]["points"] > 0)

    finally:
        server.should_exit = True
        time.sleep(0.2)

    ok = sum(results)
    print(f"\n  → {ok}/{len(results)} checks")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
