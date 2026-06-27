#!/usr/bin/env python3
"""Genesis — client de don autonome (mono-fichier, ZÉRO dépendance).

Ce fichier est servi par le coordinateur à l'adresse ``/client`` pour qu'un
volontaire puisse offrir sa puissance avec une seule commande, sur n'importe
quelle plateforme, sans cloner le dépôt :

    # Linux / macOS
    curl -s http://SERVEUR:8770/client | python3 - --nickname TONNOM

    # Windows (PowerShell)
    irm http://SERVEUR:8770/client -OutFile gd.py; py gd.py --server http://SERVEUR:8770 --nickname TONNOM

Le worldgen ci-dessous est byte-identique à ``network/worldgen.py`` (gardé par
``test_standalone_matches_worldgen``) : les digests produits ici sont vérifiés
par recalcul côté coordinateur exactement comme ceux du worker du dépôt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import struct
import sys
import time
import urllib.request

PROTOCOL_VERSION = "ge-net/1"

# --------------------------------------------------------------------------- #
# PRF + worldgen — copie fidèle de network/worldgen.py                         #
# --------------------------------------------------------------------------- #


def _seed_key(world_seed):
    ws = world_seed & ((1 << 128) - 1)
    lo = ws & ((1 << 64) - 1)
    hi = ws >> 64
    return struct.pack("<QQ", lo, hi) + struct.pack(">QQ", hi, lo)


def prf_bytes(world_seed, ctx, indices, n_bytes=32):
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


def _prf_float(world_seed, ctx, indices):
    b = prf_bytes(world_seed, ctx, indices, 8)
    return (struct.unpack("<Q", b)[0] >> 11) / float(1 << 53)


BIOMES = {
    "OCEAN": ("#1c3d5a", (0, 0, 0, 6)), "BEACH": ("#d8c89a", (1, 0, 1, 1)),
    "GRASSLAND": ("#6f9c4a", (6, 2, 1, 1)), "FOREST": ("#2f6b35", (10, 12, 1, 2)),
    "DESERT": ("#cBA868", (1, 0, 3, 0)), "TUNDRA": ("#9fb3b8", (2, 1, 2, 1)),
    "MOUNTAIN": ("#7d7d85", (1, 1, 8, 1)),
}


def _classify(elevation, moisture, temperature):
    if elevation < 0.32:
        return "OCEAN"
    if elevation < 0.36:
        return "BEACH"
    if elevation > 0.82:
        return "MOUNTAIN"
    if temperature < 0.25:
        return "TUNDRA"
    if moisture < 0.28:
        return "DESERT"
    if moisture > 0.62:
        return "FOREST"
    return "GRASSLAND"


def chunk_digest(world_seed, cx, cy, ticks, biome, food, wood, stone, water, pop):
    canon = "|".join([
        "ge-chunk/1", str(world_seed), str(cx), str(cy), str(ticks), biome,
        f"{food:.6f}", f"{wood:.6f}", f"{stone:.6f}", f"{water:.6f}", str(pop)])
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def generate_chunk(world_seed, cx, cy, ticks=64):
    elev = _prf_float(world_seed, ["elevation"], [cx, cy])
    moist = _prf_float(world_seed, ["moisture"], [cx, cy])
    temp = _prf_float(world_seed, ["temperature"], [cx, cy])
    biome = _classify(elev, moist, temp)
    color, (fc, wc, sc, watc) = BIOMES[biome]
    height = round((elev - 0.32) * 4000.0, 3)
    food = float(fc) * 8.0
    wood = float(wc) * 15.0
    stone = float(sc) * 50.0
    water = float(watc) * 1e3
    food_cap, wood_cap = float(fc) * 10.0, float(wc) * 20.0
    carry = _prf_float(world_seed, ["carry"], [cx, cy])
    pop = int((food + wood) * carry)
    for t in range(max(1, ticks)):
        if food < food_cap:
            food = min(food_cap, food + food_cap / 7200.0)
        if wood < wood_cap:
            wood = min(wood_cap, wood + wood_cap / 86400.0)
        demand = pop * 0.01
        food = max(0.0, food - demand)
        if t % 16 == 0:
            if food > demand * 4:
                pop += 1 + (pop // 50)
            elif food < demand:
                pop = max(0, pop - 1)
    # Arrondi AVANT le digest (cf. worldgen.generate_chunk) : le résumé transmis
    # détermine exactement le hash → le serveur lie résumé↔hash sans tout recalculer.
    food = round(food, 3)
    wood = round(wood, 3)
    stone = round(stone, 3)
    water = round(water, 3)
    digest = chunk_digest(world_seed, cx, cy, ticks, biome, food, wood, stone, water, pop)
    return {
        "cx": cx, "cy": cy, "ticks": ticks, "biome": biome, "color": color,
        "height_m": round(height, 2), "food": food, "wood": wood,
        "stone": stone, "water": water, "population": pop,
        "digest": digest,
    }


# --------------------------------------------------------------------------- #
# Worker minimal (urllib)                                                      #
# --------------------------------------------------------------------------- #


def _post(base, path, payload):
    req = urllib.request.Request(base + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _get(base, path):
    with urllib.request.urlopen(urllib.request.Request(base + path), timeout=30) as r:
        return json.loads(r.read().decode())


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    p = argparse.ArgumentParser(description="Don de puissance au monde Genesis.")
    p.add_argument("--server", default="http://127.0.0.1:8770")
    p.add_argument("--nickname", required=True)
    p.add_argument("--max-units", type=int, default=None)
    p.add_argument("--max-seconds", type=float, default=None)
    a = p.parse_args(argv)
    base = a.server.rstrip("/")

    print(f"  GENESIS — don de puissance · serveur {base} · pseudo {a.nickname}")
    reg = _post(base, "/api/register", {
        "nickname": a.nickname, "platform": f"{platform.system()}-{platform.machine()}",
        "protocol_version": PROTOCOL_VERSION})
    wid, tok = reg["worker_id"], reg["token"]
    print(f"  ✓ enregistré (monde {reg['world_seed']:#x}). {reg.get('motd','')}")

    units_done, points, start = 0, 0.0, time.time()
    try:
        while True:
            if a.max_units and units_done >= a.max_units:
                break
            if a.max_seconds and time.time() - start >= a.max_seconds:
                break
            batch = _get(base, f"/api/work?worker_id={wid}")
            units = batch.get("units", [])
            if not units:
                time.sleep(min(batch.get("poll_after_s", 1.0), 2.0))
                continue
            for u in units:
                ch = generate_chunk(u["world_seed"], u["cx"], u["cy"], u["ticks"])
                resp = _post(base, "/api/submit", {
                    "unit_id": u["unit_id"], "worker_id": wid, "token": tok,
                    "digest": ch["digest"], "summary": ch, "compute_ms": 0.0})
                if resp.get("accepted"):
                    units_done += 1
                    points += resp.get("credited_points", 0.0)
            print(f"  ⚙ {a.nickname}: {units_done} chunks · {points:.1f} pts")
            time.sleep(batch.get("poll_after_s", 0.5))
    except KeyboardInterrupt:
        print("\n  ⏹ arrêt demandé.")
    print(f"\n  Merci ! {units_done} chunks · {points:.1f} points offerts au monde.")


if __name__ == "__main__":
    main()
