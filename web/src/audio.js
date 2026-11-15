// audio.js - procedural "busy ICU ward" ambience, Web Audio only (no sample files).
// Everything is generated from a few pre-built noise buffers, oscillators and gain envelopes.
// Public API: createAudio() -> { start, setEnabled, isEnabled, setProximity, elevatorHum, elevatorDing, elevatorDoors, chime }

const KEY = 'septris_sound';
const MASTER = 0.9;     // master gain when enabled
const PROX_MIN = 0.35;  // close-layer level when the camera is far above the ward

const rand = (a, b) => a + Math.random() * (b - a);
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const quiet = (p) => { if (p && p.catch) p.catch(() => {}); };
const safe = (fn) => (...a) => { try { return fn(...a); } catch (e) { return undefined; } };

function readPref() {
  try { const v = localStorage.getItem(KEY); return v === null ? true : v !== '0'; } catch (e) { return true; }
}
function savePref(on) { try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (e) { /* ignore */ } }

export function createAudio() {
  const AC = typeof window !== 'undefined' ? (window.AudioContext || window.webkitAudioContext) : null;
  let ctx = null, started = false, enabled = readPref(), hidden = false, running = false;
  let master, prox, close, ui, white, brown;
  let bands = [], monitors = [], voiceBoost = 1;
  let proxLast = -1, proxWanted = 0, hum = null, wantHum = false;
  const timers = new Set();

  // ---- helpers ------------------------------------------------------------------------------
  const gainNode = (v = 0) => { const g = ctx.createGain(); g.gain.value = v; return g; };
  const filt = (type, freq, q = 1) => {
    const f = ctx.createBiquadFilter(); f.type = type; f.frequency.value = freq; f.Q.value = q; return f;
  };
  const drop = (secs, ...nodes) => setTimeout(() => nodes.forEach((n) => { try { n.disconnect(); } catch (e) { /* ignore */ } }), secs * 1000);

  // Timer that only fires while the ambience is running; all are cleared when it stops.
  const later = (fn, ms) => {
    const id = setTimeout(() => { timers.delete(id); if (running) fn(); }, ms);
    timers.add(id);
  };

  // Noise buffer, generated once. colour: 'white' | 'brown'.
  function noiseBuffer(seconds, colour) {
    const buf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * seconds), ctx.sampleRate);
    const d = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < d.length; i++) {
      const w = Math.random() * 2 - 1;
      if (colour === 'brown') { last = (last + 0.02 * w) / 1.02; d[i] = last * 3.5; } else d[i] = w;
    }
    return buf;
  }
  // Short decaying-noise impulse response for a tiny room reverb.
  function impulseBuffer(seconds) {
    const n = Math.floor(ctx.sampleRate * seconds);
    const buf = ctx.createBuffer(2, n, ctx.sampleRate);
    for (let c = 0; c < 2; c++) {
      const d = buf.getChannelData(c);
      for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, 3);
    }
    return buf;
  }
  const loopSrc = (buf) => {
    const s = ctx.createBufferSource(); s.buffer = buf; s.loop = true; s.start(0, rand(0, buf.duration - 0.1)); return s;
  };

  // Attack / hold / exponential release envelope on a gain node. Returns end time.
  function env(g, t0, attack, hold, release, peak) {
    const p = g.gain;
    p.setValueAtTime(0, t0);
    p.linearRampToValueAtTime(peak, t0 + attack);
    p.setValueAtTime(peak, t0 + attack + hold);
    p.exponentialRampToValueAtTime(0.0001, t0 + attack + hold + release);
    return t0 + attack + hold + release;
  }
  // Stereo placement; passes straight through when StereoPannerNode is missing.
  function panTo(p, dest, ttl) {
    if (!ctx.createStereoPanner) return dest;
    const n = ctx.createStereoPanner(); n.pan.value = p; n.connect(dest);
    if (ttl) drop(ttl, n);
    return n;
  }
  // One enveloped oscillator, stopped and disconnected when done.
  function tone(freq, start, dur, gain, type, dest, attack = 0.005) {
    const o = ctx.createOscillator(), g = gainNode(0);
    o.type = type; o.frequency.value = freq;
    env(g, start, attack, 0, dur - attack, gain);
    o.connect(g); g.connect(dest);
    o.start(start); o.stop(start + dur + 0.05);
    o.onended = () => { o.disconnect(); g.disconnect(); };
    return o;
  }
  // Bell-ish note: fundamental plus a short inharmonic partial.
  function bell(freq, start, dur, gain, dest) {
    tone(freq, start, dur, gain, 'sine', dest, 0.01);
    tone(freq * 2.76, start, dur * 0.35, gain * 0.25, 'sine', dest, 0.005);
  }
  // Low thump: sine with a quick pitch drop.
  function thump(start, f0, dur, gain, dest) {
    const o = ctx.createOscillator(), g = gainNode(0);
    o.frequency.setValueAtTime(f0, start);
    o.frequency.exponentialRampToValueAtTime(f0 * 0.5, start + dur);
    env(g, start, 0.005, 0, dur, gain);
    o.connect(g); g.connect(dest);
    o.start(start); o.stop(start + dur + 0.05);
    o.onended = () => { o.disconnect(); g.disconnect(); };
  }
  // Filtered one-shot noise burst. Returns { f, g } so callers can sweep the filter.
  function burst(start, dur, gain, type, freq, q, dest, attack = 0.01) {
    const s = ctx.createBufferSource(), f = filt(type, freq, q), g = gainNode(0);
    s.buffer = white;
    env(g, start, attack, 0, dur - attack, gain);
    s.connect(f); f.connect(g); g.connect(dest);
    s.start(start, rand(0, Math.max(0, white.duration - dur - 0.1))); s.stop(start + dur + 0.05);
    s.onended = () => { s.disconnect(); f.disconnect(); g.disconnect(); };
    return { f, g };
  }

  // ---- graph construction (once, on first start()) ------------------------------------------
  function build() {
    ctx = new AC();
    master = gainNode(0);
    const comp = ctx.createDynamicsCompressor(); // safety limiter
    comp.threshold.value = -14; comp.knee.value = 20; comp.ratio.value = 8; comp.attack.value = 0.005; comp.release.value = 0.2;
    master.connect(comp); comp.connect(ctx.destination);
    ui = gainNode(1); ui.connect(master);
    prox = gainNode(PROX_MIN + (1 - PROX_MIN) * proxWanted); prox.connect(master);
    close = gainNode(1); close.connect(prox);          // "close" layers: dry + tiny reverb
    const send = gainNode(0.18), conv = ctx.createConvolver();
    conv.buffer = impulseBuffer(1.2);                   // built once
    close.connect(send); send.connect(conv); conv.connect(prox);
    white = noiseBuffer(4, 'white'); brown = noiseBuffer(4, 'brown');

    // Layer 1: room tone / HVAC - brown noise lowpassed at 220 Hz plus a faint 120 Hz hum.
    const room = loopSrc(brown), roomLp = filt('lowpass', 220, 0.7), roomG = gainNode(0.35);
    room.connect(roomLp); roomLp.connect(roomG); roomG.connect(master);
    const mains = ctx.createOscillator(), mainsG = gainNode(0.007);
    mains.frequency.value = 120; mains.connect(mainsG); mainsG.connect(master); mains.start();

    // Layer 2: distant voices - two bandpassed noise bands, level and centre re-targeted irregularly.
    bands = [[450, 650, 0.22], [650, 900, 0.16]].map(([lo, hi, max]) => {
      const src = loopSrc(white), bp = filt('bandpass', (lo + hi) / 2, 1), g = gainNode(0);
      src.connect(bp); bp.connect(g); g.connect(close);
      return { g, bp, lo, hi, max, retarget() {
        const t = ctx.currentTime;
        g.gain.setTargetAtTime(rand(0.08, 1) * max * voiceBoost, t, 0.25);
        bp.frequency.setTargetAtTime(rand(lo, hi), t, 0.4);
      } };
    });

    // Layer 3: bedside monitors - each with its own pitch, tempo, pan and level.
    monitors = [[880, -0.7, 0.05], [932, -0.25, 0.04], [988, 0.3, 0.045], [1047, 0.75, 0.035]]
      .map(([f, pan, lvl]) => ({ f, lvl, bpm: rand(62, 98), out: panTo(pan, close) }));
  }

  // ---- ambience scheduling ------------------------------------------------------------------
  const voiceLoop = (b) => { b.retarget(); later(() => voiceLoop(b), rand(600, 2000)); };

  const beat = (m) => {
    tone(m.f, ctx.currentTime + 0.03, 0.07, m.lvl, 'sine', m.out, 0.004);
    m.bpm = clamp(m.bpm + rand(-0.4, 0.4), 62, 98); // tiny drift
    later(() => beat(m), 60000 / m.bpm);
  };

  // Layer 4: random events (one every ~6-18 s), each quiet and panned randomly.
  const events = [
    function pa(t, out) { // overhead PA ding-dong through a ceiling-speaker bandpass
      const bp = filt('bandpass', 1300, 0.6); bp.connect(out); drop(4, bp);
      bell(659.25, t, 1.0, 0.09, bp); bell(523.25, t + 0.55, 1.4, 0.09, bp);
      if (Math.random() < 0.5) later(() => {
        voiceBoost = 1.8; bands.forEach((b) => b.retarget());
        later(() => { voiceBoost = 1; bands.forEach((b) => b.retarget()); }, 1100);
      }, 1200);
    },
    function ivAlert(t, out) { for (let i = 0; i < 3; i++) tone(2000, t + i * 0.17, 0.09, 0.035, 'sine', out, 0.004); },
    function phone(t, out) { // two warbling rings, muffled by distance
      const lp = filt('lowpass', 2400); lp.connect(out); drop(4, lp);
      for (let r = 0; r < 2; r++) {
        const s = t + r * 0.9, o = tone(1500, s, 0.4, 0.04, 'triangle', lp, 0.02);
        for (let k = 0; k < 8; k++) o.frequency.setValueAtTime(k % 2 ? 1500 : 1900, s + k * 0.05);
      }
    },
    function footsteps(t) { // 4-7 soft thumps drifting across the stereo field
      const n = 4 + Math.floor(Math.random() * 4), a = rand(-0.9, 0.9), b = -a * rand(0.4, 1);
      const out = panTo(a, close, 8);
      if (out.pan) { out.pan.setValueAtTime(a, t); out.pan.linearRampToValueAtTime(b, t + n * 0.55); }
      for (let i = 0; i < n; i++) {
        const s = t + i * 0.55 + rand(0, 0.03);
        thump(s, 110, 0.12, 0.09, out); burst(s, 0.07, 0.3, 'lowpass', 400, 0.7, out, 0.003);
      }
    },
    function trolley(t, out) { // bandpassed noise with tremolo
      const tr = gainNode(0.5), lfo = ctx.createOscillator(), depth = gainNode(0.5);
      lfo.frequency.value = rand(22, 32); lfo.connect(depth); depth.connect(tr.gain);
      tr.connect(out); burst(t, 1.0, 0.35, 'bandpass', 1800, 2, tr, 0.15);
      lfo.start(t); lfo.stop(t + 1.1); lfo.onended = () => { lfo.disconnect(); depth.disconnect(); };
      drop(3, tr);
    },
    function door(t, out) { thump(t, 70, 0.18, 0.16, out); burst(t + 0.02, 0.35, 0.4, 'lowpass', 500, 0.7, out, 0.005); },
  ];
  const eventLoop = (first) => later(() => {
    const t = ctx.currentTime + 0.05;
    pick(events)(t, panTo(rand(-0.9, 0.9), close, 8));
    eventLoop();
  }, first || rand(6000, 18000));

  // Layer 5: ventilator-like slow breath every ~40-90 s.
  const ventLoop = (first) => later(() => {
    const t = ctx.currentTime + 0.05, { f } = burst(t, 3, 0.2, 'lowpass', 350, 0.7, close, 1.4);
    f.frequency.linearRampToValueAtTime(800, t + 1.4); f.frequency.linearRampToValueAtTime(300, t + 3);
    ventLoop();
  }, first || rand(40000, 90000));

  function startLoops() {
    if (running) return;
    running = true;
    bands.forEach(voiceLoop);
    monitors.forEach((m) => later(() => beat(m), rand(0, 900)));
    eventLoop(rand(2500, 7000)); ventLoop(rand(10000, 25000));
  }
  function stopLoops() {
    running = false; voiceBoost = 1;
    timers.forEach(clearTimeout); timers.clear();
  }
  const sync = () => ((started && enabled && !hidden) ? startLoops() : stopLoops());

  // ---- elevator hum -------------------------------------------------------------------------
  function applyHum() {
    if (!ctx) return;
    const t = ctx.currentTime;
    if (wantHum && !hum) {
      const g = gainNode(0), lp = filt('lowpass', 180, 0.7), srcs = [];
      [[55, 'sawtooth'], [55.6, 'sawtooth'], [110, 'sine']].forEach(([f, type]) => {
        const o = ctx.createOscillator(); o.type = type; o.frequency.value = f; o.connect(lp); o.start(); srcs.push(o);
      });
      const n = loopSrc(brown), ng = gainNode(0.25); n.connect(ng); ng.connect(lp); srcs.push(n);
      lp.connect(g); g.connect(ui);
      g.gain.setTargetAtTime(0.045, t, 0.1);
      hum = { g, lp, srcs };
    } else if (!wantHum && hum) {
      const h = hum; hum = null;
      h.g.gain.setTargetAtTime(0, t, 0.1);
      setTimeout(() => { h.srcs.forEach((s) => { try { s.stop(); s.disconnect(); } catch (e) { /* ignore */ } }); h.lp.disconnect(); h.g.disconnect(); }, 1000);
    }
  }

  // ---- visibility: pause scheduling (and the context) while the tab is hidden ----------------
  if (typeof document !== 'undefined' && document.addEventListener) {
    document.addEventListener('visibilitychange', safe(() => {
      hidden = !!document.hidden;
      if (ctx && started) quiet(hidden ? ctx.suspend() : ctx.resume());
      sync();
    }));
  }

  const ready = () => !!(ctx && started && enabled && !hidden);

  // ---- public API ---------------------------------------------------------------------------
  return {
    start: safe(() => {
      if (!ctx) { if (!AC) return; build(); }
      quiet(ctx.resume());
      started = true; hidden = typeof document !== 'undefined' && !!document.hidden;
      master.gain.setTargetAtTime(enabled ? MASTER : 0, ctx.currentTime, 0.1);
      applyHum(); sync();
    }),

    setEnabled: safe((on) => {
      enabled = !!on; savePref(enabled);
      if (ctx) master.gain.setTargetAtTime(enabled ? MASTER : 0, ctx.currentTime, 0.1); // ~0.4 s fade
      sync();
    }),

    isEnabled: () => enabled,

    setProximity: safe((p) => {
      p = clamp(+p || 0, 0, 1);
      if (Math.abs(p - proxLast) < 0.02) return;
      proxLast = p; proxWanted = p;
      if (prox) prox.gain.setTargetAtTime(PROX_MIN + (1 - PROX_MIN) * p, ctx.currentTime, 0.3);
    }),

    elevatorHum: safe((on) => { wantHum = !!on; applyHum(); }),

    // Classic two-note arrival chime (high then lower), bell-like, ~1.2 s decay.
    elevatorDing: safe(() => {
      if (!ready()) return;
      const t = ctx.currentTime + 0.02;
      bell(1318.5, t, 1.2, 0.14, ui); bell(987.8, t + 0.38, 1.3, 0.14, ui);
    }),

    // ~1.6 s sliding doors: filtered noise swell with a sweeping band, then a soft thunk.
    elevatorDoors: safe(() => {
      if (!ready()) return;
      const t = ctx.currentTime + 0.02, { f } = burst(t, 1.5, 0.6, 'bandpass', 400, 0.8, ui, 0.7);
      f.frequency.setValueAtTime(400, t); f.frequency.linearRampToValueAtTime(1100, t + 0.8); f.frequency.linearRampToValueAtTime(500, t + 1.5);
      thump(t + 1.5, 85, 0.14, 0.18, ui); burst(t + 1.5, 0.12, 0.3, 'lowpass', 600, 0.7, ui, 0.003);
    }),

    chime: safe((kind) => {
      if (!ready()) return;
      const t = ctx.currentTime + 0.01;
      if (kind === 'caught') {
        [523.25, 659.25, 783.99].forEach((f, i) => {
          tone(f, t + i * 0.11, 0.4, 0.09, 'sine', ui, 0.008); tone(f * 2, t + i * 0.11, 0.25, 0.025, 'sine', ui, 0.008);
        });
      } else if (kind === 'select') {
        tone(1800, t, 0.04, 0.03, 'sine', ui, 0.002);
      } else if (kind === 'admit') {
        thump(t, 190, 0.08, 0.14, ui); thump(t + 0.13, 170, 0.1, 0.12, ui); burst(t, 0.05, 0.25, 'bandpass', 1200, 1, ui, 0.002);
      } else if (kind === 'alarm') {
        tone(523.25, t, 0.25, 0.07, 'triangle', ui, 0.01); tone(392, t + 0.25, 0.35, 0.07, 'triangle', ui, 0.01);
      }
    }),
  };
}
