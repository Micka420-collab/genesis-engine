/**
 * Earth Console — écoute des agents : proto-langage, bulles, synthèse vocale.
 */
(function (global) {
  const POLL_MS = 320;
  const BUBBLE_MS = 5000;
  const FADE_MS = 900;
  const AGENT_ZOOM_MAX = 22;

  const KIND_ICONS = {
    salutation: '✋', alerte: '⚠', enseignement: '📜', demande: '🙏',
    appel: '📢', 'récit': '📖', accord: '✅', refus: '❌',
    question: '❓', plainte: '😢', chant: '🎵', 'prière': '🙌',
  };

  const KIND_HINT_FR = {
    salutation: 'salutation',
    alerte: 'alerte',
    enseignement: 'transmet un savoir',
    demande: 'demande',
    appel: 'appelle',
    'récit': 'récit',
    accord: 'accord',
    refus: 'refus',
    question: 'question',
    plainte: 'plainte',
    chant: 'chant',
    'prière': 'prière',
  };

  class EarthConsoleSpeech {
    constructor(opts) {
      this.opts = opts || {};
      this.enabled = false;
      this.speakAloud = true;
      this.bubbles = new Map();
      this.history = [];
      this.lastLanguages = null;
      this._pollTimer = null;
      this._spokenIds = new Set();
      this._stylesInjected = false;
    }

    injectStyles() {
      if (this._stylesInjected) return;
      const css = `
        #speechBubbleLayer {
          position: absolute; inset: 0; pointer-events: none; z-index: 28;
          overflow: hidden;
        }
        .ec-speech-bubble {
          position: absolute; transform: translate(-50%, -100%);
          max-width: 220px;
          background: rgba(14, 20, 32, 0.94);
          color: #e8eef6;
          border: 1px solid rgba(61, 214, 198, 0.35);
          border-radius: 10px;
          padding: 6px 10px;
          font-family: "IBM Plex Mono", ui-monospace, monospace;
          font-size: 11px;
          box-shadow: 0 4px 14px rgba(0,0,0,0.45);
          transition: opacity ${FADE_MS}ms ease-out;
        }
        .ec-speech-bubble .ph { font-weight: 600; font-size: 13px; color: #3dd6c6; }
        .ec-speech-bubble .meta { opacity: 0.72; font-size: 10px; margin-top: 2px; }
        .ec-speech-bubble.shout { border-color: rgba(232, 184, 109, 0.7); }
        .ec-speech-bubble.fading { opacity: 0; }
        #speechListenPanel {
          margin-top: 10px; padding: 10px;
          border-radius: 10px;
          border: 1px solid rgba(120, 160, 200, 0.2);
          background: rgba(20, 28, 40, 0.6);
          font-size: 11px;
        }
        #speechListenPanel .speech-log {
          max-height: 140px; overflow-y: auto;
          font-family: "IBM Plex Mono", monospace;
          margin-top: 8px;
        }
        #speechListenPanel .speech-log div {
          padding: 3px 0;
          border-bottom: 1px dashed rgba(120,160,200,0.12);
        }
        #speechListenPanel .lang-chip {
          display: inline-block;
          margin: 2px 4px 2px 0;
          padding: 2px 8px;
          border-radius: 999px;
          background: rgba(61, 214, 198, 0.12);
          border: 1px solid rgba(61, 214, 198, 0.25);
          font-size: 10px;
        }
      `;
      const tag = document.createElement('style');
      tag.id = 'ec-speech-style';
      tag.textContent = css;
      document.head.appendChild(tag);
      this._stylesInjected = true;
    }

    ensureLayer() {
      let layer = document.getElementById('speechBubbleLayer');
      if (layer) return layer;
      const vp = document.getElementById('viewport');
      if (!vp) return null;
      if (getComputedStyle(vp).position === 'static') vp.style.position = 'relative';
      layer = document.createElement('div');
      layer.id = 'speechBubbleLayer';
      vp.appendChild(layer);
      return layer;
    }

    setEnabled(on) {
      this.enabled = !!on;
      if (this.enabled) {
        this.injectStyles();
        this.ensureLayer();
        this.startPoll();
      } else {
        this.stopPoll();
        this.clearBubbles();
      }
      const btn = document.getElementById('btnListen');
      if (btn) btn.classList.toggle('active', this.enabled);
    }

    toggle() {
      this.setEnabled(!this.enabled);
      return this.enabled;
    }

    listenerQuery() {
      const o = this.opts;
      if (typeof o.selectedRow === 'number' && o.selectedRow >= 0) {
        return `listener_row=${o.selectedRow}`;
      }
      const cx = o.camCenterX ?? 0;
      const cy = o.camCenterY ?? 0;
      return `listener_x=${cx.toFixed(1)}&listener_y=${cy.toFixed(1)}`;
    }

    async poll() {
      if (!this.enabled) return;
      const api = this.opts.api || '';
      try {
        const r = await fetch(`${api}/api/audio?${this.listenerQuery()}`);
        if (!r.ok) return;
        const data = await r.json();
        (data.utterances || []).forEach(u => this.onUtterance(u));
      } catch (_) {}
      if (this.opts.camZoom < AGENT_ZOOM_MAX) {
        try {
          const lr = await fetch(`${api}/api/languages`);
          if (lr.ok) {
            this.lastLanguages = await lr.json();
            this.renderLanguagesHud();
          }
        } catch (_) {}
      }
    }

    onUtterance(u) {
      if (!u || this.bubbles.has(u.utterance_id)) return;
      const layer = this.ensureLayer();
      if (!layer) return;
      const el = document.createElement('div');
      el.className = 'ec-speech-bubble';
      if (u.volume === 2) el.classList.add('shout');
      const icon = KIND_ICONS[u.kind] || '💬';
      const hint = KIND_HINT_FR[u.kind] || u.kind || '?';
      const ph = u.phonemes || '···';
      const db = u.perceived_db != null ? `${u.perceived_db.toFixed(0)} dB` : '';
      el.innerHTML = `<span>${icon}</span> <span class="ph">${ph}</span>`
        + `<div class="meta">#${u.speaker_row} · ${hint}${db ? ' · ' + db : ''}</div>`;
      layer.appendChild(el);
      const expires = performance.now() + BUBBLE_MS;
      this.bubbles.set(u.utterance_id, { el, pos: u.pos, expires });
      this.pushLog(u, ph, hint);
      if (this.speakAloud && this.opts.camZoom < AGENT_ZOOM_MAX
          && !this._spokenIds.has(u.utterance_id)) {
        this._spokenIds.add(u.utterance_id);
        if (this._spokenIds.size > 200) {
          this._spokenIds = new Set([...this._spokenIds].slice(-80));
        }
        this.speakPhonemes(ph, u.volume);
      }
    }

    speakPhonemes(phonemes, volume) {
      try {
        const syn = window.speechSynthesis;
        if (!syn) return;
        const u = new SpeechSynthesisUtterance(phonemes);
        u.lang = 'fr-FR';
        u.rate = volume === 2 ? 1.05 : 0.82;
        u.pitch = volume === 0 ? 0.9 : 1.0;
        u.volume = volume === 2 ? 0.85 : 0.55;
        syn.cancel();
        syn.speak(u);
      } catch (_) {}
    }

    pushLog(u, ph, hint) {
      const line = `t${u.tick} #${u.speaker_row} «${ph}» (${hint})`;
      this.history.unshift(line);
      if (this.history.length > 24) this.history.pop();
      const log = document.getElementById('speechLog');
      if (log) {
        log.innerHTML = this.history.map(l => `<div>${l}</div>`).join('') || '—';
      }
    }

    renderLanguagesHud() {
      const el = document.getElementById('speechLangs');
      if (!el || !this.lastLanguages?.cultures?.length) return;
      el.innerHTML = this.lastLanguages.cultures.map(c =>
        `<span class="lang-chip" title="locuteurs ${c.speakers}">`
        + `C${c.culture_id} · ${c.phonemes}</span>`).join('');
    }

    tickBubbles() {
      const w2s = this.opts.w2s;
      if (!w2s) return;
      const now = performance.now();
      this.bubbles.forEach((b, id) => {
        const p = w2s(b.pos[0], b.pos[1]);
        if (p) {
          b.el.style.left = `${p.x}px`;
          b.el.style.top = `${p.y - 22}px`;
        }
        if (now >= b.expires) {
          b.el.classList.add('fading');
          if (now >= b.expires + FADE_MS) {
            b.el.remove();
            this.bubbles.delete(id);
          }
        }
      });
    }

    clearBubbles() {
      this.bubbles.forEach(b => b.el.remove());
      this.bubbles.clear();
    }

    startPoll() {
      this.stopPoll();
      this._pollTimer = setInterval(() => this.poll(), POLL_MS);
      this.poll();
    }

    stopPoll() {
      if (this._pollTimer) {
        clearInterval(this._pollTimer);
        this._pollTimer = null;
      }
    }
  }

  global.EarthConsoleSpeech = EarthConsoleSpeech;
})(typeof window !== 'undefined' ? window : globalThis);
