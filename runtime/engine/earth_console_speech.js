/**
 * Earth Console — écoute des agents : proto-langage, bulles, phonèmes / TTS.
 */
(function (global) {
  const POLL_MS = 280;
  const BUBBLE_MS = 5500;
  const FADE_MS = 900;
  const AGENT_ZOOM_MAX = 28;
  const HISTORY_FOCUS_N = 40;

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
      this.voiceMode = 'phoneme';
      this.bubbles = new Map();
      this.history = [];
      this.focusHistory = [];
      this.focusRow = null;
      this.lastLanguages = null;
      this._pollTimer = null;
      this._spokenIds = new Set();
      this._stylesInjected = false;
      this.phonemeAudio = null;
      if (typeof EarthConsolePhonemeAudio !== 'undefined') {
        this.phonemeAudio = new EarthConsolePhonemeAudio(() => this.opts.getAudioCtx?.());
      }
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
          max-width: 240px;
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
        .ec-speech-bubble.focused {
          border-color: rgba(232, 184, 109, 0.75);
          box-shadow: 0 0 12px rgba(232, 184, 109, 0.25);
        }
        .ec-speech-bubble .ph { font-weight: 600; font-size: 13px; color: #3dd6c6; }
        .ec-speech-bubble .meta { opacity: 0.72; font-size: 10px; margin-top: 2px; }
        .ec-speech-bubble.shout { border-color: rgba(232, 184, 109, 0.7); }
        .ec-speech-bubble.fading { opacity: 0; }
        #speechListenPanel .speech-log,
        #speechListenPanel .speech-focus {
          max-height: 120px; overflow-y: auto;
          font-family: "IBM Plex Mono", monospace;
          margin-top: 6px;
          font-size: 10px;
        }
        #speechListenPanel .speech-log div,
        #speechListenPanel .speech-focus div {
          padding: 3px 0;
          border-bottom: 1px dashed rgba(120,160,200,0.12);
        }
        #speechListenPanel .speech-focus-title {
          font-size: 10px; color: var(--accent-warm, #e8b86d);
          margin-top: 8px; font-weight: 600;
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
      document.getElementById('btnListen')?.classList.toggle('active', this.enabled);
    }

    toggle() {
      this.setEnabled(!this.enabled);
      return this.enabled;
    }

    setVoiceMode(mode) {
      this.voiceMode = mode || 'phoneme';
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
        (data.utterances || []).forEach(u => this.onUtterance(u, false));
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

    async onAgentSelected(row) {
      this.focusRow = row;
      if (!this.enabled) return;
      await this.loadFocusHistory(row);
      this.renderLogs();
    }

    async loadFocusHistory(row) {
      if (row == null || row < 0) {
        this.focusHistory = [];
        this.renderLogs();
        return;
      }
      const api = this.opts.api || '';
      try {
        const r = await fetch(`${api}/api/audio/history?row=${row}&n=${HISTORY_FOCUS_N}`);
        if (!r.ok) return;
        const data = await r.json();
        this.focusHistory = (data.utterances || []).map(u => this._formatLine(u, true));
      } catch (_) {
        this.focusHistory = [];
      }
      this.renderLogs();
    }

    _formatLine(u, isFocus) {
      const ph = u.phonemes || '···';
      const hint = KIND_HINT_FR[u.kind] || u.kind || '?';
      const who = isFocus && u.speaker_row === this.focusRow ? '→' : `#${u.speaker_row}`;
      const cult = u.culture_id != null ? ` C${u.culture_id}` : '';
      return `t${u.tick} ${who}${cult} «${ph}» (${hint})`;
    }

    onUtterance(u, fromHistory = false) {
      if (!u) return;
      const isFocus = this.focusRow != null && u.speaker_row === this.focusRow;
      if (!fromHistory && this.bubbles.has(u.utterance_id)) return;

      if (!fromHistory) {
        const layer = this.ensureLayer();
        if (layer) {
          const el = document.createElement('div');
          el.className = 'ec-speech-bubble' + (isFocus ? ' focused' : '');
          if (u.volume === 2) el.classList.add('shout');
          const icon = KIND_ICONS[u.kind] || '💬';
          const hint = KIND_HINT_FR[u.kind] || u.kind || '?';
          const ph = u.phonemes || '···';
          const db = u.perceived_db != null ? `${u.perceived_db.toFixed(0)} dB` : '';
          el.innerHTML = `<span>${icon}</span> <span class="ph">${ph}</span>`
            + `<div class="meta">#${u.speaker_row}${u.culture_id != null ? ' · C' + u.culture_id : ''} · ${hint}${db ? ' · ' + db : ''}</div>`;
          layer.appendChild(el);
          const expires = performance.now() + BUBBLE_MS;
          this.bubbles.set(u.utterance_id, { el, pos: u.pos, expires });
        }
        this.history.unshift(this._formatLine(u, false));
        if (this.history.length > 28) this.history.pop();
        if (isFocus) {
          this.focusHistory.unshift(this._formatLine(u, true));
          if (this.focusHistory.length > HISTORY_FOCUS_N) this.focusHistory.pop();
        }
        this.renderLogs();
      }

      const near = this.opts.camZoom < AGENT_ZOOM_MAX;
      if (this.speakAloud && near && !this._spokenIds.has(u.utterance_id)) {
        this._spokenIds.add(u.utterance_id);
        if (this._spokenIds.size > 240) {
          this._spokenIds = new Set([...this._spokenIds].slice(-100));
        }
        this.speakPhonemes(u.phonemes, u.volume);
      }
    }

    speakPhonemes(phonemes, volume) {
      if (!phonemes) return;
      const mode = this.voiceMode;
      if (mode === 'phoneme' || mode === 'both') {
        this.phonemeAudio?.play(phonemes, volume);
      }
      if (mode === 'tts' || mode === 'both') {
        try {
          const syn = window.speechSynthesis;
          if (!syn) return;
          const u = new SpeechSynthesisUtterance(phonemes);
          u.lang = 'fr-FR';
          u.rate = volume === 2 ? 1.05 : 0.78;
          u.pitch = volume === 0 ? 0.88 : 1.0;
          u.volume = volume === 2 ? 0.5 : 0.35;
          if (mode !== 'both') syn.cancel();
          syn.speak(u);
        } catch (_) {}
      }
    }

    renderLogs() {
      const log = document.getElementById('speechLog');
      const foc = document.getElementById('speechFocus');
      if (log) {
        log.innerHTML = this.history.map(l => `<div>${l}</div>`).join('') || '—';
      }
      if (foc) {
        const title = this.focusRow != null
          ? `Agent #${this.focusRow} — historique vocal`
          : 'Sélectionne un agent';
        const titEl = document.getElementById('speechFocusTitle');
        if (titEl) titEl.textContent = title;
        foc.innerHTML = this.focusHistory.map(l => `<div>${l}</div>`).join('')
          || '<div style="opacity:0.6">Aucune parole récente à portée.</div>';
      }
    }

    renderLanguagesHud() {
      const el = document.getElementById('speechLangs');
      if (!el || !this.lastLanguages?.cultures?.length) return;
      el.innerHTML = this.lastLanguages.cultures.map(c =>
        `<span class="lang-chip" title="${c.speakers} locuteurs">`
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
      if (this.focusRow != null) this.loadFocusHistory(this.focusRow);
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
