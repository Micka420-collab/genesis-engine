"""P157 — LLM observer/narrator connection smoke (Ollama tier-2, read-only).

Vérifie la COUCHE D'OBSERVATION LLM locale sans jamais exiger qu'Ollama
tourne (le smoke reste vert hors-ligne). La connexion est testée pour de
vrai si un serveur Ollama répond sur ``OLLAMA_HOST`` ; sinon les étapes
réseau sont marquées SKIP, pas FAIL — le module doit dégrader proprement.

Garde-fou émergence : le narrateur est read-only. On vérifie ici qu'il
n'expose AUCUNE fonction de décision/action — il décrit, il ne pilote pas.

Steps :
  1. API publique présente (LlmObserver, narrate, available, connection_report).
  2. Defaults : host 127.0.0.1:11434, modèle llama3.2:3b, surcharge par env.
  3. connection_report() bien formé + rôle 'observer-narrator (read-only...)'.
  4. Contrat read-only : le module n'expose pas de fonction d'action d'agent.
  5. narrate() ne lève jamais (retourne None si Ollama injoignable).
  6. [réseau, SKIP si offline] available() True ⇒ narrate() rend un texte.
"""
from __future__ import annotations

import io
import os
import sys

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from engine.llm_observer import (                                       # noqa: E402
    DEFAULT_HOST, DEFAULT_MODEL, LlmObserver, connection_report,
)


def _row(label, ok, detail=""):
    tag = "OK  " if ok else ("SKIP" if ok is None else "FAIL")
    return f"  [{tag}] {label:58s} {detail}"


# Petit échantillon de world.summary() — pas besoin de lancer un monde réel.
_FAKE_SUMMARY = {
    "tick": 1200, "agents": 37, "biome_dominant": "grassland",
    "temp_mean_c": 14.2, "rivers": 5, "founders": 12,
}


def main() -> int:
    print("=" * 78)
    print("P157 — LLM observer/narrator smoke (Ollama tier-2)")
    print("=" * 78)
    failures = 0

    # ----- Step 1 — API publique ---------------------------------------
    ok = all(callable(getattr(LlmObserver, m, None))
             for m in ("available", "models", "narrate")) \
        and callable(connection_report)
    print(_row("step 1 - public API surface", ok))
    failures += 0 if ok else 1

    # ----- Step 2 — defaults + surcharge env ---------------------------
    # Sauve puis vide l'env pour tester les vrais defaults, restaure ensuite.
    saved = {k: os.environ.pop(k, None) for k in ("OLLAMA_HOST", "GENESIS_LLM_MODEL")}
    try:
        obs = LlmObserver()
        ok = (obs.host == DEFAULT_HOST and obs.model == DEFAULT_MODEL
              and DEFAULT_HOST.endswith(":11434"))
        os.environ["OLLAMA_HOST"] = "http://example:9999/"
        os.environ["GENESIS_LLM_MODEL"] = "test-model:1b"
        obs2 = LlmObserver()
        ok = ok and obs2.host == "http://example:9999" \
            and obs2.model == "test-model:1b"
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    print(_row("step 2 - defaults + env override", ok,
               f"{DEFAULT_HOST} / {DEFAULT_MODEL}"))
    failures += 0 if ok else 1

    # ----- Step 3 — connection_report bien formé -----------------------
    rep = connection_report()
    ok = (rep.get("host") and rep.get("model")
          and rep.get("role", "").startswith("observer-narrator")
          and isinstance(rep.get("reachable"), bool))
    print(_row("step 3 - connection_report() well-formed", ok,
               f"reachable={rep.get('reachable')}"))
    failures += 0 if ok else 1

    # ----- Step 4 — contrat read-only (pas de pilotage d'agents) -------
    banned = ("decide", "act", "choose_action", "drive", "command",
              "set_action", "control_agent")
    exposed = [n for n in dir(LlmObserver) if not n.startswith("_")]
    leaks = [n for n in exposed if any(b in n.lower() for b in banned)]
    ok = not leaks
    print(_row("step 4 - read-only: exposes no agent-driving fn", ok,
               f"leaks={leaks}" if leaks else "observer-only"))
    failures += 0 if ok else 1

    # ----- Step 5 — narrate() ne lève jamais ---------------------------
    try:
        # Pointe sur un hôte mort : doit retourner None, pas exploser.
        dead = LlmObserver(host="http://127.0.0.1:1", timeout_s=1.0)
        res = dead.narrate(_FAKE_SUMMARY)
        ok = res is None
    except Exception as exc:  # noqa: BLE001
        ok = False
        print("      narrate a leve :", exc)
    print(_row("step 5 - narrate() degrade proprement (offline -> None)", ok))
    failures += 0 if ok else 1

    # ----- Step 6 — réseau réel (SKIP si Ollama offline) ---------------
    live = LlmObserver()
    if live.available():
        text = live.narrate(_FAKE_SUMMARY)
        ok = bool(text)
        print(_row("step 6 - live Ollama narration", ok,
                   (text or "")[:48].replace("\n", " ")))
        failures += 0 if ok else 1
    else:
        print(_row("step 6 - live Ollama narration", None,
                   f"Ollama injoignable sur {live.host} (lancer 'ollama serve')"))

    print("-" * 78)
    checks = 5  # steps 1-5 toujours comptés ; step 6 optionnel
    passed = checks - failures
    print(f"  RESULT: {passed}/{checks} checks passed"
          + ("" if live.available() else "  (+1 SKIP: Ollama offline)"))
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
