/*
 * audio_overlay.js — Genesis Engine audio HUD
 *
 * À inclure dans god_view.html via :
 *   <script src="/static/audio_overlay.js"></script>
 *
 * Le snippet est autonome : il crée son propre layer DOM pour les bulles et
 * un panneau latéral "écoute focalisée". Il s'appuie sur les variables
 * globales du god-view (worldToScreen, selectedRow, camCenterX/Y) si elles
 * existent ; sinon il bascule sur des polls absolus.
 */
(function () {
  "use strict";

  const POLL_MS = 500;
  const HISTORY_POLL_MS = 1500;
  const BUBBLE_LIFETIME_MS = 4000;
  const BUBBLE_FADE_MS = 1000;
  const MAX_HISTORY = 20;

  const KIND_ICONS = {
    salutation: "✋",       // waving hand
    alerte: "⚠",           // warning sign
    enseignement: "\u{1F4DC}",  // scroll
    demande: "\u{1F64F}",       // folded hands
    appel: "\u{1F4E2}",         // loudspeaker
    "récit": "\u{1F4D6}",      // book
    accord: "✅",
    refus: "❌",
    question: "❓",
    plainte: "\u{1F622}",
    chant: "\u{1F3B5}",
    "prière": "\u{1F64C}",
  };

  function injectStyles() {
    if (document.getElementById("audio-overlay-style")) return;
    const css = `
      #audioBubbleLayer {
        position: absolute; inset: 0; pointer-events: none;
        z-index: 30; overflow: hidden;
      }
      .speech-bubble {
        position: absolute;
        transform: translate(-50%, -100%);
        background: rgba(20, 24, 32, 0.92);
        color: #e5e9f0;
        border: 1px solid rgba(180, 200, 255, 0.35);
        border-radius: 10px;
        padding: 4px 8px;
        font-family: ui-monospace, Menlo, Consolas, monospace;
        font-size: 12px;
        white-space: nowrap;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.5);
        transition: opacity ${BUBBLE_FADE_MS}ms ease-out;
        opacity: 1;
      }
      .speech-bubble .ico { margin-right: 4px; opacity: 0.85; }
      .speech-bubble .ph { font-weight: 600; }
      .speech-bubble .db {
        margin-left: 6px; opacity: 0.55; font-size: 10px;
      }
      .speech-bubble.fading { opacity: 0; }
      .speech-bubble.whisper { font-style: italic; opacity: 0.7; }
      .speech-bubble.shout {
        font-size: 14px; border-color: #f0a060; color: #ffd9a0;
      }

      #audioFocusPanel {
        position: fixed; right: 12px; bottom: 12px; width: 320px;
        max-height: 50vh; overflow: auto;
        background: rgba(18, 22, 30, 0.94);
        color: #e5e9f0;
        border: 1px solid rgba(180, 200, 255, 0.25);
        border-radius: 10px;
        font-family: ui-monospace, Menlo, Consolas, monospace;
        font-size: 12px;
        z-index: 40;
        display: none;
      }
      #audioFocusPanel header {
        position: sticky; top: 0;
        padding: 6px 10px;
        background: rgba(30, 36, 48, 0.97);
        border-bottom: 1px solid rgba(180, 200, 255, 0.15);
        font-weight: 600;
        display: flex; justify-content: space-between; align-items: center;
      }
      #audioFocusPanel header .close {
        cursor: pointer; opacity: 0.65; padding: 0 4px;
      }
      #audioFocusPanel header .close:hover { opacity: 1; }
      #audioFocusPanel ul { list-style: none; margin: 0; padding: 4px 0; }
      #audioFocusPanel li {
        padding: 4px 10px;
        border-bottom: 1px dashed rgba(180, 200, 255, 0.07);
        display: flex; gap: 6px;
      }
      #audioFocusPanel li .t { opacity: 0.55; min-width: 48px; }
      #audioFocusPanel li .k { min-width: 80px; opacity: 0.85; }
      #audioFocusPanel li .p { font-weight: 600; }
    `;
    const tag = document.createElement("style");
    tag.id = "audio-overlay-style";
    tag.textContent = css;
    document.head.appendChild(tag);
  }

  function ensureBubbleLayer() {
    let layer = document.getElementById("audioBubbleLayer");
    if (layer) return layer;
    const viewport = document.getElementById("viewport") || document.body;
    layer = document.createElement("div");
    layer.id = "audioBubbleLayer";
    // Force the viewport to be a positioning context if not already
    const style = getComputedStyle(viewport);
    if (style.position === "static") viewport.style.position = "relative";
    viewport.appendChild(layer);
    return layer;
  }

  function ensureFocusPanel() {
    let panel = document.getElementById("audioFocusPanel");
    if (panel) return panel;
    panel = document.createElement("div");
    panel.id = "audioFocusPanel";
    panel.innerHTML = `
      <header>
        <span>écoute focalisée <span id="audioFocusRow"></span></span>
        <span class="close" id="audioFocusClose">&times;</span>
      </header>
      <ul id="audioFocusList"></ul>
    `;
    document.body.appendChild(panel);
    panel.querySelector("#audioFocusClose").addEventListener("click", () => {
      panel.style.display = "none";
    });
    return panel;
  }

  // -------------------------------------------------------------------------
  // Position mapping — uses host page's worldToScreen if present.
  // -------------------------------------------------------------------------
  function projectWorld(wx, wy) {
    if (typeof window.worldToScreen === "function") {
      try { return window.worldToScreen(wx, wy); } catch (e) { /* fall back */ }
    }
    return null;
  }

  function getListenerArgs() {
    // Priority: selected agent row → camera center → null.
    if (typeof window.selectedRow !== "undefined" && window.selectedRow !== null) {
      return { listener_row: window.selectedRow };
    }
    if (typeof window.camCenterX !== "undefined"
        && typeof window.camCenterY !== "undefined") {
      return { listener_x: window.camCenterX, listener_y: window.camCenterY };
    }
    return null;
  }

  // -------------------------------------------------------------------------
  // Bubble lifecycle
  // -------------------------------------------------------------------------
  const liveBubbles = new Map(); // utterance_id -> {el, expiresAt}

  function spawnBubble(u) {
    if (liveBubbles.has(u.utterance_id)) return;
    const layer = ensureBubbleLayer();
    const el = document.createElement("div");
    el.className = "speech-bubble";
    if (u.volume === 0) el.classList.add("whisper");
    if (u.volume === 2) el.classList.add("shout");
    const icon = KIND_ICONS[u.kind] || "\u{1F5E8}";
    const phon = (u.phonemes || "...");
    const db = (u.perceived_db !== undefined)
      ? `${u.perceived_db.toFixed(0)} dB` : "";
    el.innerHTML = `<span class="ico">${icon}</span>`
      + `<span class="ph">${phon}</span>`
      + `<span class="db">${db}</span>`;
    layer.appendChild(el);
    liveBubbles.set(u.utterance_id, {
      el, pos: u.pos, expiresAt: performance.now() + BUBBLE_LIFETIME_MS,
    });
  }

  function tickBubbles() {
    const now = performance.now();
    liveBubbles.forEach((b, id) => {
      // Position update based on speaker world coords
      const proj = projectWorld(b.pos[0], b.pos[1]);
      if (proj) {
        b.el.style.left = `${proj.x}px`;
        b.el.style.top = `${proj.y - 18}px`;
      }
      const remaining = b.expiresAt - now;
      if (remaining <= 0) {
        b.el.remove();
        liveBubbles.delete(id);
      } else if (remaining < BUBBLE_FADE_MS) {
        b.el.classList.add("fading");
      }
    });
    requestAnimationFrame(tickBubbles);
  }

  // -------------------------------------------------------------------------
  // Polling
  // -------------------------------------------------------------------------
  async function pollAudio() {
    const args = getListenerArgs();
    if (!args) return;
    const qs = new URLSearchParams(args).toString();
    try {
      const r = await fetch(`/api/audio?${qs}`);
      if (!r.ok) return;
      const data = await r.json();
      (data.utterances || []).forEach(spawnBubble);
    } catch (e) { /* network blips ignored */ }
  }

  function formatTick(t) {
    // approximate "il y a Xt" relative to current tick if visible
    if (typeof window.lastSnap === "object" && window.lastSnap
        && window.lastSnap.tick !== undefined) {
      const dt = window.lastSnap.tick - t;
      if (dt <= 0) return "now";
      return `-${dt}t`;
    }
    return `t=${t}`;
  }

  async function pollHistory() {
    const row = window.selectedRow;
    const panel = ensureFocusPanel();
    if (row === null || row === undefined) {
      panel.style.display = "none";
      return;
    }
    panel.style.display = "block";
    panel.querySelector("#audioFocusRow").textContent = `(agent #${row})`;
    try {
      const r = await fetch(`/api/audio/history?row=${row}&n=${MAX_HISTORY}`);
      if (!r.ok) return;
      const data = await r.json();
      const list = panel.querySelector("#audioFocusList");
      list.innerHTML = "";
      (data.utterances || []).forEach((u) => {
        const li = document.createElement("li");
        const icon = KIND_ICONS[u.kind] || "\u{1F5E8}";
        li.innerHTML =
          `<span class="t">${formatTick(u.tick)}</span>`
          + `<span class="k">${icon} ${u.kind}</span>`
          + `<span class="p">${u.phonemes || "..."}</span>`;
        list.appendChild(li);
      });
      if ((data.utterances || []).length === 0) {
        list.innerHTML = `<li><span class="t"></span>`
          + `<span class="k">silence</span><span class="p">--</span></li>`;
      }
    } catch (e) { /* ignore */ }
  }

  // -------------------------------------------------------------------------
  // Boot
  // -------------------------------------------------------------------------
  function boot() {
    injectStyles();
    ensureBubbleLayer();
    ensureFocusPanel();
    requestAnimationFrame(tickBubbles);
    setInterval(pollAudio, POLL_MS);
    setInterval(pollHistory, HISTORY_POLL_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
