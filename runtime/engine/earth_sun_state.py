"""État solaire simulé — ombres portées cohérentes (earth_dynamo)."""
from __future__ import annotations

import math
from typing import Any, Dict, Tuple

PIPELINE_LAYER = "Genesis-L0 Physics"
WORLD_MODEL_CAPABILITY = "paper-L1 Predictor"


def sun_state_snapshot(sim) -> Dict[str, Any]:
    """Direction soleil + vecteur ombre 2D pour le rendu client."""
    dyn = getattr(sim, "_earth_dynamo", None)
    tick = int(sim.tick)
    dt = float(getattr(sim.cfg, "drive_accel", 1800.0))
    ticks_per_day = max(3600, int(86400.0 / max(dt, 1.0)))

    if dyn is not None:
        phase = float(dyn.diurnal_phase_rad)
        insol = float(dyn.mean_insolation_w_m2)
    else:
        phase = (tick % ticks_per_day) / ticks_per_day * 2.0 * math.pi
        insol = 340.0

    # Soleil NW haute (convention atlas) — modulé par phase jour/nuit.
    az_base = math.radians(315.0)
    alt_base = math.radians(25.0 + 35.0 * max(0.0, math.sin(phase - math.pi / 2.0)))
    az = az_base + 0.15 * math.sin(phase * 0.5)
    alt = max(math.radians(8.0), alt_base)

    # Direction lumière (vers le soleil) en plan XY.
    lx = math.cos(alt) * math.sin(az)
    ly = -math.cos(alt) * math.cos(az)

    # Ombre portée : offset écran = opposé au soleil.
    shadow_len_px = 6.0 + 10.0 * (1.0 - math.sin(alt))
    sx = -lx * shadow_len_px
    sy = -ly * shadow_len_px * 0.55

    day_factor = float(0.25 + 0.75 * max(0.0, math.sin(phase - math.pi / 2.0)))
    is_day = day_factor > 0.35

    return {
        "tick": tick,
        "phase_rad": round(phase, 4),
        "insolation_w_m2": round(insol, 2),
        "day_factor": round(day_factor, 3),
        "is_day": is_day,
        "azimuth_deg": round(math.degrees(az), 2),
        "altitude_deg": round(math.degrees(alt), 2),
        "light_xy": [round(lx, 4), round(ly, 4)],
        "shadow_offset_px": [round(sx, 2), round(sy, 2)],
        "shadow_alpha": round(0.22 + 0.18 * (1.0 - day_factor), 3),
        "ambient_rgb": [
            int(40 + 30 * day_factor),
            int(50 + 40 * day_factor),
            int(70 + 50 * day_factor),
        ],
    }


__all__ = ["sun_state_snapshot"]
