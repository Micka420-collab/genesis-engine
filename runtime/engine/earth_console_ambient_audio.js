/**
 * Sons procéduraux au zoom agent (pas de fichiers externes).
 */
(function (global) {
  const BUILD_ACTION = 11;
  const SMELT_ACTION = 18;

  class EarthConsoleAmbientAudio {
    constructor() {
      this.ctx = null;
      this.master = null;
      this.enabled = false;
      this._lastFoot = 0;
      this._lastHammer = 0;
      this._windGain = null;
      this._windOsc = null;
    }

    async unlock() {
      if (this.ctx) return true;
      try {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return false;
        this.ctx = new AC();
        this.master = this.ctx.createGain();
        this.master.gain.value = 0.35;
        this.master.connect(this.ctx.destination);
        this._initWind();
        this.enabled = true;
        if (this.ctx.state === 'suspended') await this.ctx.resume();
        return true;
      } catch (_) {
        return false;
      }
    }

    _initWind() {
      if (!this.ctx) return;
      this._windOsc = this.ctx.createOscillator();
      this._windOsc.type = 'sine';
      this._windOsc.frequency.value = 42;
      const filt = this.ctx.createBiquadFilter();
      filt.type = 'lowpass';
      filt.frequency.value = 180;
      this._windGain = this.ctx.createGain();
      this._windGain.gain.value = 0;
      this._windOsc.connect(filt);
      filt.connect(this._windGain);
      this._windGain.connect(this.master);
      this._windOsc.start();
    }

    _tone(freq, dur, type, vol) {
      if (!this.ctx || !this.enabled) return;
      const t0 = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const g = this.ctx.createGain();
      osc.type = type || 'sine';
      osc.frequency.setValueAtTime(freq, t0);
      g.gain.setValueAtTime(0, t0);
      g.gain.linearRampToValueAtTime(vol, t0 + 0.01);
      g.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
      osc.connect(g);
      g.connect(this.master);
      osc.start(t0);
      osc.stop(t0 + dur + 0.02);
    }

    footstep() {
      const now = performance.now();
      if (now - this._lastFoot < 280) return;
      this._lastFoot = now;
      this._tone(90 + Math.random() * 40, 0.06, 'triangle', 0.12);
    }

    hammer() {
      const now = performance.now();
      if (now - this._lastHammer < 420) return;
      this._lastHammer = now;
      this._tone(220, 0.04, 'square', 0.08);
      this._tone(140, 0.08, 'sine', 0.06);
    }

    smeltCrackle() {
      this._tone(60 + Math.random() * 30, 0.1, 'sawtooth', 0.05);
    }

    update(sun, camZoom, agents, feed) {
      if (!this.enabled || !this.ctx) return;
      const agentZoom = camZoom < 18;
      if (!agentZoom) {
        if (this._windGain) this._windGain.gain.value = 0;
        return;
      }
      const df = sun?.day_factor ?? 0.5;
      if (this._windGain) {
        const target = 0.02 + df * 0.04;
        this._windGain.gain.value += (target - this._windGain.gain.value) * 0.05;
      }
      let walking = 0;
      let building = 0;
      for (const a of agents || []) {
        const spd = Math.hypot(a.vx ?? 0, a.vy ?? 0);
        if (spd > 0.15 && (a.posture === 'walk' || a.posture === 'run')) walking++;
        if (a.action === BUILD_ACTION || a.posture === 'build') building++;
        if (a.action === SMELT_ACTION || a.posture === 'smelt') building++;
      }
      if (walking > 0) this.footstep();
      if (building > 0) this.hammer();
      const sites = feed?.sites?.length ?? 0;
      if (sites > 0 && Math.random() < 0.08) this.hammer();
      if ((feed?.workers || []).some(w => w.posture === 'smelt')) {
        if (Math.random() < 0.12) this.smeltCrackle();
      }
    }
  }

  global.EarthConsoleAmbientAudio = EarthConsoleAmbientAudio;
})(typeof window !== 'undefined' ? window : globalThis);
