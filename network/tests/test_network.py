"""Tests réseau — hermétiques via starlette TestClient (pas de port réseau)."""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from network import worldgen  # noqa: E402
from network.coordinator import Coordinator, create_app, spiral_coords  # noqa: E402


@pytest.fixture()
def client():
    coord = Coordinator(world_seed=0xBEEF, verify_fraction=1.0)
    return TestClient(create_app(coord)), coord


# --------------------------------------------------------------------------- #
# worldgen — déterminisme & fidélité PRF                                       #
# --------------------------------------------------------------------------- #


def test_prf_matches_engine():
    """Le PRF local doit être byte-identique à engine.core (sinon divergence)."""
    if not worldgen.engine_prf_available():
        pytest.skip("engine.core indisponible dans cet environnement")
    from engine.core import prf_bytes as engine_prf
    for args in [(0xBEEF, ["elevation"], [1, 2]), (0x6EE72026, ["moisture"], [-3, 7])]:
        assert worldgen.prf_bytes(*args) == engine_prf(*args)


def test_chunk_deterministic():
    a = worldgen.generate_chunk(0xBEEF, 3, -2, 128)
    b = worldgen.generate_chunk(0xBEEF, 3, -2, 128)
    assert a.digest == b.digest
    assert a == b


def test_ticks_change_digest():
    assert (worldgen.generate_chunk(0xBEEF, 0, 0, 64).digest
            != worldgen.generate_chunk(0xBEEF, 0, 0, 128).digest)


def test_seed_changes_world():
    assert (worldgen.generate_chunk(1, 5, 5, 64).digest
            != worldgen.generate_chunk(2, 5, 5, 64).digest)


def test_biomes_valid():
    seen = set()
    for cx in range(-6, 7):
        for cy in range(-6, 7):
            c = worldgen.generate_chunk(0x6EE72026, cx, cy, 16)
            assert c.biome in worldgen.BIOMES
            seen.add(c.biome)
    assert len(seen) >= 3  # le monde n'est pas mono-biome


def test_spiral_starts_at_origin_and_is_unique():
    gen = spiral_coords()
    coords = [next(gen) for _ in range(49)]
    assert coords[0] == (0, 0)
    assert len(set(coords)) == 49  # aucune répétition


# --------------------------------------------------------------------------- #
# Endpoints                                                                    #
# --------------------------------------------------------------------------- #


def test_register_and_work_and_submit(client):
    c, coord = client
    r = c.post("/api/register", json={"nickname": "Tester", "platform": "ci"})
    assert r.status_code == 200
    reg = r.json()
    wid, tok = reg["worker_id"], reg["token"]
    assert reg["world_seed"] == 0xBEEF

    batch = c.get(f"/api/work?worker_id={wid}").json()
    assert batch["units"], "le coordinateur doit donner du travail"
    u = batch["units"][0]
    chunk = worldgen.generate_chunk(u["world_seed"], u["cx"], u["cy"], u["ticks"])
    resp = c.post("/api/submit", json={
        "unit_id": u["unit_id"], "worker_id": wid, "token": tok,
        "digest": chunk.digest, "summary": chunk.summary(), "compute_ms": 1.0,
    }).json()
    assert resp["accepted"] and resp["verified"]
    assert resp["credited_points"] > 0


def test_submit_tampered_is_rejected(client):
    c, coord = client
    reg = c.post("/api/register", json={"nickname": "Cheater"}).json()
    wid, tok = reg["worker_id"], reg["token"]
    u = c.get(f"/api/work?worker_id={wid}").json()["units"][0]
    good = worldgen.generate_chunk(u["world_seed"], u["cx"], u["cy"], u["ticks"])
    resp = c.post("/api/submit", json={
        "unit_id": u["unit_id"], "worker_id": wid, "token": tok,
        "digest": "0" * 64, "summary": good.summary(), "compute_ms": 1.0,
    }).json()
    assert resp["accepted"] is False
    assert resp["verified"] is True
    assert coord.rejected_units == 1


def test_unknown_worker_rejected(client):
    c, _ = client
    resp = c.post("/api/submit", json={
        "unit_id": "x", "worker_id": "ghost", "token": "no",
        "digest": "0" * 64,
        "summary": worldgen.generate_chunk(0xBEEF, 0, 0, 64).summary(),
    }).json()
    assert resp["accepted"] is False


def test_world_grows_and_resolution_scales(client):
    c, coord = client
    reg = c.post("/api/register", json={"nickname": "Worker"}).json()
    wid, tok = reg["worker_id"], reg["token"]
    for _ in range(30):
        batch = c.get(f"/api/work?worker_id={wid}").json()
        if not batch["units"]:
            break
        for u in batch["units"]:
            ch = worldgen.generate_chunk(u["world_seed"], u["cx"], u["cy"], u["ticks"])
            c.post("/api/submit", json={
                "unit_id": u["unit_id"], "worker_id": wid, "token": tok,
                "digest": ch.digest, "summary": ch.summary(), "compute_ms": 1.0})
    st = c.get("/api/state").json()
    assert st["chunks_done"] > 0
    assert st["quality"]["world_radius_chunks"] >= 2
    assert st["total_points"] > 0


def test_standalone_matches_worldgen():
    """Le client autonome doit produire des digests identiques au worldgen."""
    from network import standalone_donate as sd
    for seed, cx, cy, ticks in [(0xBEEF, 0, 0, 64), (0x6EE72026, -3, 5, 128),
                                (1, 7, -2, 256)]:
        ref = worldgen.generate_chunk(seed, cx, cy, ticks)
        got = sd.generate_chunk(seed, cx, cy, ticks)
        assert got["digest"] == ref.digest
        assert got["biome"] == ref.biome


def test_client_endpoint_serves_python(client):
    c, _ = client
    r = c.get("/client")
    assert r.status_code == 200
    assert "def generate_chunk" in r.text
    assert "def main" in r.text


def _donate(coord, nick="W", n=8, seed=None):
    """Helper : enregistre un worker et soumet n unités correctes en direct."""
    from network.protocol import RegisterRequest, WorkResult, ChunkSummary
    reg = coord.register(RegisterRequest(nickname=nick))
    done = 0
    while done < n:
        batch = coord.get_work(reg.worker_id)
        if not batch.units:
            break
        for u in batch.units:
            ch = worldgen.generate_chunk(u.world_seed, u.cx, u.cy, u.ticks)
            coord.submit(WorkResult(unit_id=u.unit_id, worker_id=reg.worker_id,
                                    token=reg.token, digest=ch.digest,
                                    summary=ChunkSummary(**ch.summary())))
            done += 1
            if done >= n:
                break
    return reg


def test_persistence_roundtrip(tmp_path):
    """Le monde + les scores doivent survivre à un redémarrage."""
    from network.store import WorldStore
    db = str(tmp_path / "world.db")

    store = WorldStore(db)
    c1 = Coordinator(world_seed=0xBEEF, store=store)
    _donate(c1, "Alice", 10)
    chunks_before = len(c1.done)
    pts_before = c1.total_points
    store.close()
    assert chunks_before >= 10 and pts_before > 0

    # Redémarrage : nouveau coordinateur, même base.
    store2 = WorldStore(db)
    c2 = Coordinator(world_seed=0x1234, store=store2)  # seed ignoré → repris du store
    assert c2.world_seed == 0xBEEF
    assert len(c2.done) == chunks_before
    assert abs(c2.total_points - pts_before) < 1e-6
    board = c2.state().leaderboard
    assert any(c.nickname == "Alice" and c.points > 0 for c in board)
    store2.close()


def test_returning_contributor_keeps_score(tmp_path):
    from network.store import WorldStore
    db = str(tmp_path / "w.db")
    s1 = WorldStore(db)
    c1 = Coordinator(world_seed=0xBEEF, store=s1)
    _donate(c1, "Bob", 6)
    p1 = c1.scores["Bob"]["points"]
    s1.close()
    s2 = WorldStore(db)
    c2 = Coordinator(store=s2)
    _donate(c2, "Bob", 6)  # Bob revient
    assert c2.scores["Bob"]["points"] > p1  # le score s'accumule, ne repart pas de 0
    s2.close()


def test_sampling_offloads_trusted_worker():
    """Avec verify_fraction=0, un worker fiable n'est plus recalculé (offload)."""
    from network.coordinator import TRUST_AFTER
    from network.protocol import RegisterRequest, WorkResult, ChunkSummary
    coord = Coordinator(world_seed=0xBEEF, verify_fraction=0.0)
    reg = coord.register(RegisterRequest(nickname="Trusty"))
    verified_flags = []
    submitted = 0
    while submitted < TRUST_AFTER + 5:
        for u in coord.get_work(reg.worker_id).units:
            ch = worldgen.generate_chunk(u.world_seed, u.cx, u.cy, u.ticks)
            r = coord.submit(WorkResult(unit_id=u.unit_id, worker_id=reg.worker_id,
                                        token=reg.token, digest=ch.digest,
                                        summary=ChunkSummary(**ch.summary())))
            verified_flags.append(r.verified)
            submitted += 1
    # Les premières sont vérifiées (mise en confiance), les suivantes non (offload).
    assert all(verified_flags[:TRUST_AFTER])
    assert verified_flags[-1] is False


def test_cheater_is_banned():
    from network.protocol import RegisterRequest, WorkResult, ChunkSummary
    coord = Coordinator(world_seed=0xBEEF, verify_fraction=1.0)
    reg = coord.register(RegisterRequest(nickname="Evil"))
    u = coord.get_work(reg.worker_id).units[0]
    good = worldgen.generate_chunk(u.world_seed, u.cx, u.cy, u.ticks)
    bad = coord.submit(WorkResult(unit_id=u.unit_id, worker_id=reg.worker_id,
                                  token=reg.token, digest="0" * 64,
                                  summary=ChunkSummary(**good.summary())))
    assert bad.accepted is False
    assert coord.contributors[reg.worker_id]["banned"] is True
    # Banni → plus aucun travail offert.
    assert coord.get_work(reg.worker_id).units == []


def test_verified_path_stores_server_truth_not_client():
    """Bon hash + résumé falsifié → le serveur stocke SA vérité, pas la copie."""
    from network.protocol import RegisterRequest, WorkResult, ChunkSummary
    coord = Coordinator(world_seed=0xBEEF, verify_fraction=1.0)
    reg = coord.register(RegisterRequest(nickname="X"))
    u = coord.get_work(reg.worker_id).units[0]
    truth = worldgen.generate_chunk(u.world_seed, u.cx, u.cy, u.ticks)
    fake = ChunkSummary(**{**truth.summary(), "population": 999_999})  # mensonge
    r = coord.submit(WorkResult(unit_id=u.unit_id, worker_id=reg.worker_id,
                                token=reg.token, digest=truth.digest, summary=fake))
    assert r.accepted and r.verified
    # Le résumé stocké est la vérité serveur (population réelle), pas 999 999.
    assert coord.done[(u.cx, u.cy)]["population"] == truth.population


def test_trust_path_rejects_summary_digest_mismatch():
    """Chemin de confiance : un résumé incohérent avec son hash est rejeté (O(1))."""
    from network.coordinator import TRUST_AFTER
    from network.protocol import RegisterRequest, WorkResult, ChunkSummary
    coord = Coordinator(world_seed=0xBEEF, verify_fraction=0.0)
    reg = coord.register(RegisterRequest(nickname="Trusty"))
    # Gagner la confiance avec TRUST_AFTER unités correctes.
    done = 0
    while done < TRUST_AFTER:
        for u in coord.get_work(reg.worker_id).units:
            ch = worldgen.generate_chunk(u.world_seed, u.cx, u.cy, u.ticks)
            coord.submit(WorkResult(unit_id=u.unit_id, worker_id=reg.worker_id,
                                    token=reg.token, digest=ch.digest,
                                    summary=ChunkSummary(**ch.summary())))
            done += 1
            if done >= TRUST_AFTER:
                break
    # Maintenant non-audité : on envoie le VRAI hash mais un faux résumé.
    u = coord.get_work(reg.worker_id).units[0]
    truth = worldgen.generate_chunk(u.world_seed, u.cx, u.cy, u.ticks)
    fake = ChunkSummary(**{**truth.summary(), "population": 999_999})
    r = coord.submit(WorkResult(unit_id=u.unit_id, worker_id=reg.worker_id,
                                token=reg.token, digest=truth.digest, summary=fake))
    assert r.accepted is False
    assert "incohérent" in r.reason


def test_cannot_submit_another_workers_unit():
    from network.protocol import RegisterRequest, WorkResult, ChunkSummary
    coord = Coordinator(world_seed=0xBEEF)
    a = coord.register(RegisterRequest(nickname="A"))
    b = coord.register(RegisterRequest(nickname="B"))
    ua = coord.get_work(a.worker_id).units[0]
    ch = worldgen.generate_chunk(ua.world_seed, ua.cx, ua.cy, ua.ticks)
    # B tente de rendre l'unité de A (avec les identifiants de B).
    r = coord.submit(WorkResult(unit_id=ua.unit_id, worker_id=b.worker_id,
                                token=b.token, digest=ch.digest,
                                summary=ChunkSummary(**ch.summary())))
    assert r.accepted is False
    assert "autre worker" in r.reason


def test_registration_capacity_limit(monkeypatch):
    import network.coordinator as co
    monkeypatch.setattr(co, "MAX_CONTRIBUTORS", 2)
    coord = co.Coordinator(world_seed=0xBEEF)
    from network.protocol import RegisterRequest
    coord.register(RegisterRequest(nickname="A"))
    coord.register(RegisterRequest(nickname="B"))
    with pytest.raises(co.CapacityError):
        coord.register(RegisterRequest(nickname="C"))


def test_stale_workers_are_pruned():
    from network.protocol import RegisterRequest
    clock = {"t": 1000.0}
    coord = Coordinator(world_seed=0xBEEF, clock=lambda: clock["t"])
    r = coord.register(RegisterRequest(nickname="Old"))
    assert r.worker_id in coord.contributors
    clock["t"] += 4000.0  # > PRUNE_AFTER_S
    coord.register(RegisterRequest(nickname="New"))  # déclenche la purge
    assert r.worker_id not in coord.contributors  # ancienne session purgée
    assert "Old" in coord.scores  # mais le score cumulé survit


def test_oversized_body_rejected(client):
    c, _ = client
    big = "x" * (70 * 1024)
    r = c.post("/api/register", content=big.encode(),
               headers={"Content-Type": "application/json",
                        "Content-Length": str(len(big))})
    assert r.status_code == 413


def _submit_for(coord_, reg, unit, seed_chunk=None):
    """Soumet un résultat (correct par défaut) pour une unité donnée."""
    from network.protocol import WorkResult, ChunkSummary
    ch = seed_chunk or worldgen.generate_chunk(unit.world_seed, unit.cx, unit.cy,
                                               unit.ticks)
    summ = ch.summary() if hasattr(ch, "summary") else ch
    digest = ch.digest if hasattr(ch, "digest") else ch["digest"]
    return coord_.submit(WorkResult(unit_id=unit.unit_id, worker_id=reg.worker_id,
                                    token=reg.token, digest=digest,
                                    summary=ChunkSummary(**summ)))


def test_quorum_finalizes_on_agreement():
    """replication=2 : 2 volontaires d'accord → chunk finalisé, les 2 crédités."""
    from network.protocol import RegisterRequest
    coord = Coordinator(world_seed=0xBEEF, replication=2)
    a = coord.register(RegisterRequest(nickname="A"))
    b = coord.register(RegisterRequest(nickname="B"))
    ua = coord.get_work(a.worker_id).units[0]
    target = (ua.cx, ua.cy)
    ra = _submit_for(coord, a, ua)
    assert ra.accepted and "attente" in ra.reason   # en attente du 2ᵉ avis
    assert target not in coord.done                  # pas encore finalisé

    ub = next(u for u in coord.get_work(b.worker_id).units
              if (u.cx, u.cy) == target)
    rb = _submit_for(coord, b, ub)
    assert rb.accepted and "consensus" in rb.reason
    assert target in coord.done                      # finalisé par consensus
    assert coord.scores["A"]["points"] > 0
    assert coord.scores["B"]["points"] > 0


def test_quorum_bans_dissenter_without_server_recompute():
    """Le consensus (sans recalcul serveur) crédite les honnêtes et bannit le menteur."""
    from network.coordinator import TRUST_AFTER
    from network.protocol import RegisterRequest, WorkResult, ChunkSummary
    coord = Coordinator(world_seed=0xBEEF, verify_fraction=0.0, replication=3)
    a = coord.register(RegisterRequest(nickname="Hon1"))
    b = coord.register(RegisterRequest(nickname="Hon2"))
    c = coord.register(RegisterRequest(nickname="Menteur"))
    # Workers déjà « fiables » → pas de recalcul serveur : c'est le consensus
    # (et lui seul) qui tranche.
    for reg in (a, b, c):
        coord.contributors[reg.worker_id]["verified_count"] = TRUST_AFTER

    # Un coord frais que les trois vont calculer.
    ua = coord.get_work(a.worker_id).units[0]
    target = (ua.cx, ua.cy)
    truth = worldgen.generate_chunk(ua.world_seed, ua.cx, ua.cy, ua.ticks)

    # A (honnête) puis C (menteur, hash auto-cohérent mais faux) → pas de quorum.
    assert _submit_for(coord, a, ua, truth).accepted
    uc = next(u for u in coord.get_work(c.worker_id).units if (u.cx, u.cy) == target)
    fake_summary = {**truth.summary(), "population": 999_999}
    fake_digest = worldgen.chunk_digest(
        ua.world_seed, ua.cx, ua.cy, ua.ticks, fake_summary["biome"],
        fake_summary["food"], fake_summary["wood"], fake_summary["stone"],
        fake_summary["water"], fake_summary["population"])
    rc = coord.submit(WorkResult(unit_id=uc.unit_id, worker_id=c.worker_id,
                                 token=c.token, digest=fake_digest,
                                 summary=ChunkSummary(**{**fake_summary,
                                                         "digest": fake_digest})))
    assert rc.accepted and target not in coord.done   # pas encore de consensus

    # B (honnête) scelle le quorum sur la vérité.
    ub = next(u for u in coord.get_work(b.worker_id).units if (u.cx, u.cy) == target)
    rb = _submit_for(coord, b, ub, truth)
    assert rb.accepted and target in coord.done
    # La vérité gagne (pas la population mensongère), le menteur est banni.
    assert coord.done[target]["population"] == truth.population
    assert coord.contributors[c.worker_id]["banned"] is True
    assert coord.scores["Hon1"]["points"] > 0 and coord.scores["Hon2"]["points"] > 0


def test_engine_backend_determinism():
    from network import worldgen_engine as we
    if not we.available():
        pytest.skip("backend engine indisponible (numpy/engine)")
    a = we.generate_chunk(0xBEEF, 3, -2, 128)
    b = we.generate_chunk(0xBEEF, 3, -2, 128)
    assert a.digest == b.digest
    assert a.biome in {
        "OCEAN", "ICE", "TUNDRA", "BOREAL_FOREST", "TEMPERATE_FOREST",
        "TEMPERATE_RAINFOREST", "GRASSLAND", "HOT_DESERT", "COLD_DESERT",
        "SAVANNA", "TROPICAL_DRY_FOREST", "TROPICAL_RAINFOREST"}
    assert a.digest != we.generate_chunk(0xBEEF, 9, 9, 128).digest


def test_engine_backend_end_to_end():
    """Un chunk calculé par le backend moteur est accepté + vérifié par le serveur."""
    from network import worldgen_engine as we
    if not we.available():
        pytest.skip("backend engine indisponible (numpy/engine)")
    from network.protocol import RegisterRequest, WorkResult, ChunkSummary
    coord = Coordinator(world_seed=0xBEEF, backend="engine", verify_fraction=1.0)
    assert coord.state().worldgen_backend == "engine"
    reg = coord.register(RegisterRequest(nickname="EngWorker"))
    u = coord.get_work(reg.worker_id).units[0]
    ch = we.generate_chunk(u.world_seed, u.cx, u.cy, u.ticks)
    r = coord.submit(WorkResult(unit_id=u.unit_id, worker_id=reg.worker_id,
                                token=reg.token, digest=ch.digest,
                                summary=ChunkSummary(**ch.summary())))
    assert r.accepted and r.verified
    # Un chunk builtin (faux pour ce monde) serait rejeté par le serveur moteur.
    bad = worldgen.generate_chunk(u.world_seed, u.cx, u.cy, u.ticks)
    if bad.digest != ch.digest:  # quasi toujours vrai (worldgen différent)
        u2 = coord.get_work(reg.worker_id).units[0]
        bad2 = worldgen.generate_chunk(u2.world_seed, u2.cx, u2.cy, u2.ticks)
        r2 = coord.submit(WorkResult(unit_id=u2.unit_id, worker_id=reg.worker_id,
                                     token=reg.token, digest=bad2.digest,
                                     summary=ChunkSummary(**bad2.summary())))
        assert r2.accepted is False  # backend incompatible → rejeté


def test_rate_limit_per_ip(client, monkeypatch):
    import network.coordinator as co
    monkeypatch.setattr(co, "RATE_MAX_PER_WINDOW", 3)
    c, _ = client
    codes = [c.post("/api/register", json={"nickname": f"R{i}"}).status_code
             for i in range(6)]
    assert 429 in codes  # l'inondation depuis une IP est freinée


def test_inflight_quota_caps_a_greedy_worker():
    from network.coordinator import MAX_INFLIGHT_PER_WORKER, BATCH_SIZE
    from network.protocol import RegisterRequest
    coord = Coordinator(world_seed=0xBEEF)
    reg = coord.register(RegisterRequest(nickname="Hog"))
    total = 0
    for _ in range(100):  # tente de rafler toute la frontière sans rien rendre
        u = coord.get_work(reg.worker_id).units
        if not u:
            break
        total += len(u)
    # Le worker est plafonné (anti-griefing) au lieu de tout réserver.
    assert total <= MAX_INFLIGHT_PER_WORKER + BATCH_SIZE
    assert coord.get_work(reg.worker_id).units == []


def test_client_sha256_matches_served_client(client):
    import hashlib
    c, _ = client
    src = c.get("/client").text
    expected = hashlib.sha256(src.encode("utf-8")).hexdigest()
    j = c.get("/client.sha256").json()
    assert j["sha256"] == expected
    assert len(j["sha256"]) == 64


def test_chunk_version_and_delta():
    from network.protocol import RegisterRequest
    coord = Coordinator(world_seed=0xBEEF)
    _donate(coord, "Seed", 6)
    v = coord.chunk_version()
    assert v == len(coord.done) and v >= 6
    assert len(coord.chunks_since(0)) == v        # snapshot complet
    assert coord.chunks_since(v) == []            # rien de neuf
    # Un chunk de plus → delta = exactement 1.
    reg = coord.register(RegisterRequest(nickname="More"))
    before = coord.chunk_version()
    for u in coord.get_work(reg.worker_id).units[:1]:
        _submit_for(coord, reg, u)
    assert coord.chunk_version() == before + 1
    assert len(coord.chunks_since(before)) == 1


def test_sse_payload_snapshot_then_delta():
    """Le payload SSE : snapshot complet à sent=0, puis seulement les nouveaux."""
    coord = Coordinator(world_seed=0xBEEF)
    _donate(coord, "Seeder", 5)
    full = coord.sse_payload(0)                       # 1er message = tout
    assert {"v", "chunks", "state"} <= set(full)
    assert full["v"] == coord.chunk_version()
    assert len(full["chunks"]) == full["v"]
    assert full["state"]["chunks"] == []             # stats légères, sans carte
    # Plus rien de neuf depuis la version courante.
    assert coord.sse_payload(full["v"])["chunks"] == []


def test_no_duplicate_chunk_assignment(client):
    """Deux workers ne doivent pas se voir assigner le même chunk simultanément."""
    c, coord = client
    a = c.post("/api/register", json={"nickname": "A"}).json()
    b = c.post("/api/register", json={"nickname": "B"}).json()
    ua = c.get(f"/api/work?worker_id={a['worker_id']}").json()["units"]
    ub = c.get(f"/api/work?worker_id={b['worker_id']}").json()["units"]
    ca = {(u["cx"], u["cy"]) for u in ua}
    cb = {(u["cx"], u["cy"]) for u in ub}
    assert ca.isdisjoint(cb)
