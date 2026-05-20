/**
 * Interpolation fluide des agents entre polls API.
 */
(function (global) {
  class EarthConsoleAgentAnim {
    constructor() {
      this._states = new Map();
      this._alpha = 1;
    }

    setTargets(agents) {
      const seen = new Set();
      for (const a of agents || []) {
        const row = a.row;
        if (row == null) continue;
        seen.add(row);
        const tx = a.pos?.[0] ?? a.x ?? 0;
        const ty = a.pos?.[1] ?? a.y ?? 0;
        const prev = this._states.get(row);
        if (!prev) {
          this._states.set(row, {
            x: tx, y: ty, tx, ty,
            vx: a.vx ?? 0, vy: a.vy ?? 0,
            heading: a.heading ?? 0,
            posture: a.posture ?? 'idle',
            tool: a.tool ?? '',
            skin: a.skin, culture: a.culture,
            action: a.action ?? 0,
            gait: a.gait ?? 0,
            row,
          });
        } else {
          prev.tx = tx;
          prev.ty = ty;
          prev.vx = a.vx ?? prev.vx;
          prev.vy = a.vy ?? prev.vy;
          prev.heading = a.heading ?? prev.heading;
          prev.posture = a.posture ?? prev.posture;
          prev.tool = a.tool ?? prev.tool;
          prev.skin = a.skin ?? prev.skin;
          prev.culture = a.culture ?? prev.culture;
          prev.action = a.action ?? prev.action;
          prev.gait = a.gait ?? prev.gait;
        }
      }
      for (const row of [...this._states.keys()]) {
        if (!seen.has(row)) this._states.delete(row);
      }
      this._alpha = 0;
    }

    advance(dtMs) {
      const k = 1 - Math.pow(0.001, dtMs / 16);
      this._alpha = Math.min(1, this._alpha + k * 0.35);
      for (const s of this._states.values()) {
        s.x += (s.tx - s.x) * k;
        s.y += (s.ty - s.y) * k;
        if (s.posture === 'walk' || s.posture === 'run') {
          s.gait = (s.gait ?? 0) + dtMs * 0.012;
        }
      }
    }

    displayAgents() {
      return [...this._states.values()].map(s => ({
        row: s.row,
        pos: [s.x, s.y],
        x: s.x, y: s.y,
        vx: s.vx, vy: s.vy,
        heading: s.heading,
        posture: s.posture,
        tool: s.tool,
        skin: s.skin,
        culture: s.culture,
        action: s.action,
        gait: s.gait,
      }));
    }
  }

  global.EarthConsoleAgentAnim = EarthConsoleAgentAnim;
})(typeof window !== 'undefined' ? window : globalThis);
