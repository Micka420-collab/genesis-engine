/**
 * Ombres portées cohérentes avec /api/sun_state (earth_dynamo).
 */
(function (global) {
  function castShadow(ctx, x, y, scale, sun) {
    if (!sun || sun.is_day === false) return;
    const off = sun.shadow_offset_px || [0, 0];
    const alpha = sun.shadow_alpha ?? 0.28;
    const ox = off[0] * (scale / 8);
    const oy = off[1] * (scale / 8);
    ctx.fillStyle = `rgba(6, 10, 18, ${alpha})`;
    ctx.beginPath();
    ctx.ellipse(x + ox, y + oy + scale * 0.35, scale * 1.05, scale * 0.36, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  function ambientOverlayCss(sun) {
    if (!sun) return null;
    const rgb = sun.ambient_rgb || [50, 60, 80];
    const df = sun.day_factor ?? 0.5;
    const night = 1.0 - df;
    return `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${(0.06 + night * 0.22).toFixed(3)})`;
  }

  function applyViewportTint(ctx, w, h, sun) {
    const css = ambientOverlayCss(sun);
    if (!css || !ctx) return;
    ctx.save();
    ctx.fillStyle = css;
    ctx.fillRect(0, 0, w, h);
    ctx.restore();
  }

  global.EarthSunShadow = { castShadow, ambientOverlayCss, applyViewportTint };
})(typeof window !== 'undefined' ? window : globalThis);
