"""CLI unifiée du réseau Genesis.

    python -m network coordinator [--host H --port P --seed S]
    python -m network donate --server URL --nickname NOM [--max-units N]
"""
from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    # Sortie UTF-8 robuste (console Windows cp1252 sinon).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="genesis-net",
                                description="Réseau de calcul mondial Genesis.")
    sub = p.add_subparsers(dest="cmd", required=True)

    co = sub.add_parser("coordinator", help="Lancer le serveur coordinateur + site.")
    co.add_argument("--host", default="0.0.0.0")
    co.add_argument("--port", type=int, default=8770)
    co.add_argument("--seed", type=lambda s: int(s, 0), default=None,
                    help="world_seed (défaut: 0x6EE72026).")
    co.add_argument("--verify-fraction", type=float, default=1.0,
                    help="Fraction d'unités re-vérifiées (1.0 = toutes ; <1.0 "
                         "décharge le CPU serveur pour les workers fiables).")
    co.add_argument("--db", default=None,
                    help="Fichier SQLite de persistance (le monde survit aux "
                         "redémarrages). Absent = tout en mémoire.")
    co.add_argument("--replication", type=int, default=1,
                    help="Nb de volontaires distincts par chunk (≥2 = mode "
                         "QUORUM : le serveur compare les hash au lieu de "
                         "recalculer ; recommandé 3 en public).")

    do = sub.add_parser("donate", help="Offrir de la puissance (genesis donate).")
    do.add_argument("--server", default="http://127.0.0.1:8770")
    do.add_argument("--nickname", required=True)
    do.add_argument("--max-units", type=int, default=None)
    do.add_argument("--max-seconds", type=float, default=None)

    args = p.parse_args(argv)

    if args.cmd == "coordinator":
        import uvicorn
        from .coordinator import Coordinator, create_app, DEFAULT_WORLD_SEED
        store = None
        if args.db:
            from .store import WorldStore
            store = WorldStore(args.db)
        coord = Coordinator(world_seed=args.seed or DEFAULT_WORLD_SEED,
                            verify_fraction=args.verify_fraction, store=store,
                            replication=args.replication)
        app = create_app(coord)
        if coord.replication > 1:
            print(f"   Mode QUORUM  : {coord.replication} replicas/chunk, "
                  f"consensus à {coord.quorum} (serveur ne recalcule plus)")
        if args.db:
            print(f"   Persistance  : {args.db}  ({len(coord.done)} chunks restaurés)")
        print(f"🌍 Coordinateur Genesis sur http://{args.host}:{args.port}  "
              f"(monde {coord.world_seed:#x})")
        print(f"   Site mondial : http://{args.host}:{args.port}/")
        print(f"   Donner ici   : python -m network donate "
              f"--server http://<IP>:{args.port} --nickname TONNOM")
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
        return 0

    if args.cmd == "donate":
        from .worker import donate
        donate(args.server, args.nickname, max_units=args.max_units,
               max_seconds=args.max_seconds)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
