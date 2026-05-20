/**
 * Synthèse procédurale des pseudo-phonèmes (Web Audio, pas de TTS navigateur).
 */
(function (global) {
  const VOWELS = 'aiueoə';
  const CONS_FREQ = {
    k: 220, t: 280, n: 360, m: 320, p: 200, s: 0, l: 380, r: 340,
    h: 0, j: 520, w: 300, 'ŋ': 180,
  };
  const VOW_FREQ = { a: 440, i: 560, u: 330, e: 410, o: 370, 'ə': 350 };

  function syllabify(raw) {
    const s = (raw || '').toLowerCase().replace(/[^a-zəŋ]/g, '');
    const out = [];
    let i = 0;
    while (i < s.length) {
      if (s[i] === 'ŋ' && i + 1 < s.length && VOWELS.includes(s[i + 1])) {
        out.push(s[i] + s[i + 1]);
        i += 2;
        continue;
      }
      if (i + 1 < s.length && VOWELS.includes(s[i + 1])) {
        out.push(s[i] + s[i + 1]);
        i += 2;
        continue;
      }
      i += 1;
    }
    return out;
  }

  class EarthConsolePhonemeAudio {
    constructor(getCtx) {
      this._getCtx = getCtx;
      this._queue = [];
      this._playing = false;
    }

    _ctx() {
      const g = this._getCtx?.();
      return g?.ctx || g;
    }

    _master() {
      const g = this._getCtx?.();
      return g?.master || g;
    }

    async _ensure() {
      const g = this._getCtx?.();
      if (g?.unlock) await g.unlock();
      const ctx = this._ctx();
      if (ctx?.state === 'suspended') await ctx.resume();
      return !!ctx;
    }

    play(phonemes, volume = 1) {
      if (!phonemes) return;
      const sylls = syllabify(phonemes);
      if (!sylls.length) return;
      this._queue.push({ sylls, vol: volume === 2 ? 1.0 : volume === 0 ? 0.35 : 0.65 });
      if (!this._playing) this._drain();
    }

    async _drain() {
      this._playing = true;
      while (this._queue.length) {
        const job = this._queue.shift();
        if (!(await this._ensure())) break;
        for (const syll of job.sylls) {
          await this._playSyllable(syll, job.vol);
        }
      }
      this._playing = false;
    }

    _playSyllable(syll, vol) {
      return new Promise(resolve => {
        const ctx = this._ctx();
        const master = this._master();
        if (!ctx || !master) {
          resolve();
          return;
        }
        const c = syll[0] === 'ŋ' ? 'ŋ' : syll[0];
        const v = syll.length > 1 ? syll[syll.length - 1] : 'a';
        const t0 = ctx.currentTime;
        const dur = 0.11 + (vol * 0.04);
        const g = ctx.createGain();
        g.gain.setValueAtTime(0, t0);
        g.gain.linearRampToValueAtTime(0.14 * vol, t0 + 0.012);
        g.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
        g.connect(master);

        if (c === 's' || c === 'h') {
          const buf = ctx.createBuffer(1, ctx.sampleRate * 0.05, ctx.sampleRate);
          const d = buf.getChannelData(0);
          for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * 0.4;
          const src = ctx.createBufferSource();
          src.buffer = buf;
          const bp = ctx.createBiquadFilter();
          bp.type = 'bandpass';
          bp.frequency.value = c === 's' ? 5200 : 900;
          src.connect(bp);
          bp.connect(g);
          src.start(t0);
          src.stop(t0 + dur);
        } else {
          const osc = ctx.createOscillator();
          osc.type = 'triangle';
          const f0 = (CONS_FREQ[c] || 260) * 0.5 + (VOW_FREQ[v] || 400) * 0.5;
          osc.frequency.setValueAtTime(f0, t0);
          osc.frequency.exponentialRampToValueAtTime(
            (VOW_FREQ[v] || 400) * (1.0 + 0.08 * Math.random()), t0 + dur * 0.7);
          const filt = ctx.createBiquadFilter();
          filt.type = 'lowpass';
          filt.frequency.value = 2200;
          osc.connect(filt);
          filt.connect(g);
          osc.start(t0);
          osc.stop(t0 + dur + 0.01);
        }
        setTimeout(resolve, dur * 1000 + 25);
      });
    }
  }

  global.EarthConsolePhonemeAudio = EarthConsolePhonemeAudio;
  global.syllabifyPhonemes = syllabify;
})(typeof window !== 'undefined' ? window : globalThis);
