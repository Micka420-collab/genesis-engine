"""P18 CI linter — enforce ADR-0005 capability tags on layer modules.

Runs ``engine.world_model_capabilities.audit_modules`` and exits with a
non-zero code if any required module (earth_loader, sim_lift, realism)
fails to publish ``PIPELINE_LAYER`` + ``WORLD_MODEL_CAPABILITY`` with
allow-listed values.

Wire into CI as::

    python runtime/scripts/p18_capabilities_lint.py

Exit codes
----------
0 — all required modules tagged correctly.
1 — at least one required module is missing tags or has an invalid value.
2 — internal error loading the aggregator (probably a deeper problem,
    surfaces stack trace).

Optional flag ``--strict`` also fails on R&D modules that exist but
forgot to declare their tags. Default is non-strict so partial scaffolds
(``ai_detail``, ``world_model``) don't gate the build.
"""
from __future__ import annotations

import io
import os
import sys
import traceback

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)


def main(argv: list) -> int:
    strict = "--strict" in argv
    try:
        from engine.world_model_capabilities import audit_modules
    except Exception:
        traceback.print_exc()
        return 2

    table, failures = audit_modules(strict=strict)

    rows = table.get("modules", [])  # type: ignore[assignment]
    summary = table.get("summary", {})  # type: ignore[assignment]

    print("=== ADR-0005 capability audit ===")
    print(f"strict={strict}  required-tagged={summary.get('tagged',0)}  "
          f"missing={summary.get('missing',0)}  "
          f"untagged={summary.get('untagged',0)}  "
          f"invalid={summary.get('invalid',0)}")
    print()
    for r in rows:
        mark = {"ok": "OK ", "missing": "-- ", "untagged": "!! ",
                "invalid_capability": "?? "}.get(r["status"], "?? ")
        pl = r.get("pipeline_layer") or "-"
        pc = r.get("world_model_capability") or "-"
        print(f"  {mark}{r['module']:<32}  {pl:<28}  {pc}")
        if r["error"]:
            print(f"        ↳ {r['error']}")

    if failures:
        print()
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print()
    print("OK — all required modules carry valid ADR-0005 tags.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
