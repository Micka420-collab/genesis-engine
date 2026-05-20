/**
 * Earth Console — Vue du ciel : humains, chantiers, Terre cultivée.
 */
(function (global) {
  const ACTION_BUILD = 11;
  const ACTION_SMELT = 18;
  const ACTION_PLANT = 15;

  const SITE_COLORS = {
    transform: 'rgba(232, 184, 109, 0.9)',
    real: 'rgba(195, 155, 115, 0.92)',
    structure: 'rgba(175, 195, 215, 0.92)',
    voxel: 'rgba(130, 175, 155, 0.88)',
    registry_project: 'rgba(155, 185, 225, 0.9)',
    emergent_site: 'rgba(232, 184, 109, 0.9)',
  };

  const ICON_RADIUS = {
    fire: 6, hut: 10, shelter: 8, well: 7, granary: 11, workshop: 9,
    kiln: 9, forge: 10, farm: 13, monument: 15, build: 8,
  };

  function skinCss(rgb) {
    if (!rgb || rgb.length < 3) return 'rgb(235, 200, 170)';
    return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
  }

  function clothCss(culture) {
    const hues = [
      'rgba(90, 140, 110, 0.95)',
      'rgba(160, 120, 85, 0.95)',
      'rgba(110, 130, 175, 0.95)',
      'rgba(175, 95, 95, 0.95)',
      'rgba(130, 160, 130, 0.95)',
    ];
    return hues[(culture ?? 0) % hues.length];
  }

  class EarthConsoleObserver {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas ? canvas.getContext('2d') : null;
      this.feed = { sites: [], structures: [], workers: [], terraform: [] };
      this.sunState = null;
      this.phase = 0;
      this.enabled = true;
    }

    setFeed(feed) {
      if (feed) this.feed = feed;
    }

    setSunState(sun) {
      this.sunState = sun;
    }

    advance(dtMs) {
      this.phase = (this.phase + dtMs * 0.002) % 1;
    }

    clear(w, h) {
      if (!this.ctx) return;
      this.ctx.clearRect(0, 0, w, h);
    }

    draw(w2s, mpp, w, h) {
      if (!this.ctx || !this.enabled) return;
      this.clear(w, h);
      const ctx = this.ctx;
      const phase = this.phase;
      const sun = this.sunState;
      const shadowFn = (typeof EarthSunShadow !== 'undefined')
        ? EarthSunShadow.castShadow
        : null;

      if (typeof EarthSunShadow !== 'undefined') {
        EarthSunShadow.applyViewportTint(ctx, w, h, sun);
      }

      for (const t of this.feed.terraform || []) {
        this._drawTerraform(ctx, w2s, t, mpp, phase);
      }
      for (const s of this.feed.structures || []) {
        this._drawStructure(ctx, w2s, s, mpp);
      }
      for (const site of this.feed.sites || []) {
        this._drawSite(ctx, w2s, site, mpp, phase);
      }
      for (const worker of this.feed.workers || []) {
        this._drawHuman(ctx, w2s, worker, mpp, phase);
      }
    }

    _rPx(radiusM, mpp) {
      return Math.max(5, Math.min(56, radiusM / Math.max(mpp, 0.35)));
    }

    _drawTerraform(ctx, w2s, t, mpp, phase) {
      const p = w2s(t.x, t.y);
      const r = this._rPx(t.radius_m || 16, mpp);
      if (t.kind === 'cultivation') {
        const pulse = 0.6 + 0.12 * Math.sin(phase * Math.PI * 2);
        const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r);
        grd.addColorStop(0, `rgba(75, 145, 55, ${0.4 * pulse})`);
        grd.addColorStop(0.5, `rgba(55, 110, 45, ${0.25 * pulse})`);
        grd.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = grd;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = `rgba(100, 180, 70, ${0.3 + 0.12 * Math.sin(phase * 5)})`;
        ctx.lineWidth = 1.2;
        ctx.setLineDash([5, 7]);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = 'rgba(120, 200, 80, 0.5)';
        for (let i = 0; i < 6; i++) {
          const a = (i / 6) * Math.PI * 2 + phase;
          ctx.fillRect(p.x + Math.cos(a) * r * 0.5 - 1, p.y + Math.sin(a) * r * 0.35 - 1, 2, 2);
        }
      }
    }

    _drawStructure(ctx, w2s, s, mpp) {
      const p = w2s(s.x, s.y);
      const icon = s.icon || 'build';
      const r = this._rPx(s.radius_m || ICON_RADIUS[icon] || 8, mpp) * 0.6;
      if (typeof EarthSunShadow !== 'undefined') {
        EarthSunShadow.castShadow(ctx, p.x, p.y, r * 1.4, this.sunState);
      }
      ctx.fillStyle = 'rgba(12, 18, 28, 0.5)';
      ctx.beginPath();
      ctx.ellipse(p.x + 2, p.y + 4, r * 1.2, r * 0.45, 0, 0, Math.PI * 2);
      ctx.fill();
      if (icon === 'fire') {
        const g = ctx.createRadialGradient(p.x, p.y - r * 0.2, 0, p.x, p.y, r * 1.5);
        g.addColorStop(0, 'rgba(255, 230, 150, 0.95)');
        g.addColorStop(0.4, 'rgba(255, 140, 50, 0.75)');
        g.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
      } else if (icon === 'farm') {
        const rows = 4;
        for (let i = 0; i < rows; i++) {
          ctx.fillStyle = i % 2 ? 'rgba(90, 150, 70, 0.8)' : 'rgba(110, 170, 85, 0.8)';
          ctx.fillRect(p.x - r, p.y - r * 0.3 + i * (r * 0.22), r * 2, r * 0.18);
        }
      } else {
        ctx.fillStyle = 'rgba(150, 165, 180, 0.9)';
        ctx.beginPath();
        ctx.moveTo(p.x, p.y - r * 1.1);
        ctx.lineTo(p.x + r * 1.05, p.y + r * 0.55);
        ctx.lineTo(p.x - r * 1.05, p.y + r * 0.55);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = 'rgba(220, 230, 245, 0.55)';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }
    }

    _drawSite(ctx, w2s, site, mpp, phase) {
      const p = w2s(site.x, site.y);
      const prog = site.progress ?? 0;
      const r = this._rPx(site.radius_m || 10, mpp);
      const growH = 6 + prog * 18;
      if (typeof EarthSunShadow !== 'undefined') {
        EarthSunShadow.castShadow(ctx, p.x, p.y, r + growH * 0.15, this.sunState);
      }
      const col = SITE_COLORS[site.channel] || SITE_COLORS.emergent_site;
      ctx.strokeStyle = col;
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.beginPath();
      ctx.arc(p.x, p.y, r + 5 + Math.sin(phase * 6) * 1.5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.strokeStyle = 'rgba(61, 214, 198, 0.95)';
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      ctx.arc(p.x, p.y, r, -Math.PI / 2, -Math.PI / 2 + prog * Math.PI * 2);
      ctx.stroke();
      const nPosts = 5 + Math.floor(prog * 5);
      for (let i = 0; i < nPosts; i++) {
        const ang = (i / nPosts) * Math.PI * 2;
        const sx = p.x + Math.cos(ang) * r * 0.7;
        const sy = p.y + Math.sin(ang) * r * 0.45;
        const h = 6 + prog * 14;
        ctx.fillStyle = 'rgba(170, 145, 110, 0.85)';
        ctx.fillRect(sx - 1.5, sy - h, 3, h);
      }
      if (prog > 0.15 && prog < 0.95) {
        ctx.fillStyle = 'rgba(255, 255, 255, 0.92)';
        ctx.font = '600 10px DM Sans, sans-serif';
        ctx.fillText(`${Math.round(prog * 100)}%`, p.x - 12, p.y - r - 8);
      }
    }

    /**
     * Silhouette humaine top-down (tête, épaules, jambes, outil).
     */
    _drawHuman(ctx, w2s, w, mpp, phase) {
      const p = w2s(w.x, w.y);
      const posture = w.posture || 'idle';
      const gait = w.gait_phase ?? phase * Math.PI * 2;
      const heading = w.heading ?? 0;
      const scale = Math.max(4.5, 7.0 / Math.max(mpp * 0.12, 0.35));
      const skin = skinCss(w.skin);
      const cloth = clothCss(w.culture);

      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(heading);

      const walkSwing = Math.sin(gait) * 0.35;
      const buildSwing = Math.sin(phase * Math.PI * 4) * 0.5;

      if (typeof EarthSunShadow !== 'undefined') {
        EarthSunShadow.castShadow(ctx, 0, 0, scale * 1.2, this.sunState);
      }

      ctx.fillStyle = 'rgba(0, 0, 0, 0.25)';
      ctx.beginPath();
      ctx.ellipse(2, 4, scale * 1.15, scale * 0.42, 0, 0, Math.PI * 2);
      ctx.fill();

      if (posture === 'walk' || posture === 'run') {
        const stride = (posture === 'run' ? 1.4 : 1.0) * walkSwing;
        ctx.strokeStyle = cloth;
        ctx.lineWidth = scale * 0.45;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(-scale * 0.35, scale * 0.15);
        ctx.lineTo(-scale * 0.5 - stride * scale, scale * 0.85);
        ctx.moveTo(scale * 0.35, scale * 0.15);
        ctx.lineTo(scale * 0.5 + stride * scale, scale * 0.85);
        ctx.stroke();
      }

      ctx.fillStyle = cloth;
      ctx.beginPath();
      ctx.ellipse(0, 0, scale * 0.95, scale * 0.5, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = skin;
      ctx.beginPath();
      ctx.arc(scale * 0.62, -scale * 0.08, scale * 0.38, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = skin;
      ctx.lineWidth = scale * 0.22;
      ctx.lineCap = 'round';

      if (posture === 'build' || w.tool === 'hammer') {
        ctx.strokeStyle = skin;
        ctx.beginPath();
        ctx.moveTo(scale * 0.15, scale * 0.05);
        ctx.lineTo(scale * 1.0 + buildSwing * scale * 0.5, -scale * 0.75);
        ctx.stroke();
        ctx.fillStyle = 'rgba(120, 100, 75, 0.95)';
        ctx.fillRect(scale * 0.95 + buildSwing * scale * 0.5, -scale * 0.95, scale * 0.35, scale * 0.3);
        ctx.fillStyle = 'rgba(90, 85, 80, 0.9)';
        ctx.fillRect(scale * 1.05 + buildSwing * scale * 0.5, -scale * 1.15, scale * 0.12, scale * 0.55);
      } else if (posture === 'smelt' || w.tool === 'fire') {
        const flicker = 0.65 + 0.35 * Math.sin(phase * 12);
        const g = ctx.createRadialGradient(scale * 0.2, -scale * 0.6, 0, scale * 0.2, -scale * 0.6, scale * 0.9);
        g.addColorStop(0, `rgba(255, 220, 120, ${flicker})`);
        g.addColorStop(0.5, `rgba(255, 100, 40, ${flicker * 0.7})`);
        g.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(scale * 0.2, -scale * 0.55, scale * 0.75, 0, Math.PI * 2);
        ctx.fill();
      } else if (posture === 'plant' || w.tool === 'seed') {
        ctx.beginPath();
        ctx.moveTo(0, scale * 0.1);
        ctx.lineTo(scale * 0.5, scale * 0.55);
        ctx.stroke();
        ctx.fillStyle = 'rgba(100, 170, 70, 0.9)';
        ctx.beginPath();
        ctx.arc(scale * 0.55, scale * 0.6, scale * 0.15, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.beginPath();
        ctx.moveTo(scale * 0.1, scale * 0.05);
        ctx.lineTo(scale * 0.75, -scale * 0.35);
        ctx.moveTo(-scale * 0.1, scale * 0.05);
        ctx.lineTo(-scale * 0.55, scale * 0.35);
        ctx.stroke();
      }

      ctx.restore();

      if (posture === 'build' || posture === 'smelt' || posture === 'plant') {
        ctx.strokeStyle = 'rgba(61, 214, 198, 0.28)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.arc(p.x, p.y, scale * 2.4, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
  }

  global.EarthConsoleObserver = EarthConsoleObserver;
  global.OBSERVER_ACTION_BUILD = ACTION_BUILD;
})(typeof window !== 'undefined' ? window : globalThis);
