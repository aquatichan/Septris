// Canvas chart of one patient's stay: Septris risk (0-100), heart rate and
// blood pressure, with "now", the future (greyed), sepsis onset and the
// caught-in-time window. Drawn by hand so the page needs no chart library.

const DARK = { future: "#ffffff0d", risk: "#4fb3ff", hr: "#cfe0e4", map: "#f5b84b", now: "#e7f0f2", onset: "#ff6b5e", win: "#3ccf8e", grid: "#2a3f47", muted: "#8fa6ad" };

// a print palette for the paper chart the nurse holds
const LIGHT = { future: "#0000000d", risk: "#1f78c8", hr: "#3b4a52", map: "#c47f0c", now: "#1b2a31", onset: "#d63a2f", win: "#1f9e66", grid: "#d8d1c3", muted: "#7b766c" };
const C = DARK;

export function drawChart(canvas, patient, now, showOutcome = true, light = false) {
  const C = light ? LIGHT : DARK;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  const g = canvas.getContext("2d");
  g.scale(dpr, dpr);
  g.clearRect(0, 0, W, H);

  const n = patient.risk.length;
  const onset = showOutcome ? patient.onset : null;
  const x0 = Math.max(0, now - 48);
  const x1 = showOutcome ? Math.min(n - 1, Math.max(now, onset ?? 0) + 8) : now;
  const L = 34, R = W - 8;
  const X = (h) => L + ((h - x0) / Math.max(1, x1 - x0)) * (R - L);
  const panels = [
    { key: "risk", top: 14, h: H * 0.46, lo: 0, hi: 100, label: "Risk" },
    { key: "hr", top: H * 0.52 + 6, h: H * 0.2, lo: 40, hi: 160, label: "HR" },
    { key: "map", top: H * 0.75 + 6, h: H * 0.2, lo: 30, hi: 130, label: "MAP" },
  ];

  g.font = "11px IBM Plex Mono, monospace";
  for (const p of panels) {
    const Y = (v) => p.top + p.h - ((v - p.lo) / (p.hi - p.lo)) * p.h;
    // future shading and the caught-in-time window
    g.fillStyle = C.future;
    if (showOutcome) g.fillRect(X(now + 0.5), p.top, R - X(now + 0.5), p.h);
    if (onset != null && onset - 6 > x0) {
      g.fillStyle = "#3ccf8e22";
      g.fillRect(X(Math.max(x0, onset - 12)), p.top, X(onset - 6) - X(Math.max(x0, onset - 12)), p.h);
    }
    g.strokeStyle = C.grid;
    g.lineWidth = 1;
    g.strokeRect(L, p.top, R - L, p.h);
    g.fillStyle = C.muted;
    g.fillText(p.label, 2, p.top + 11);
    // series
    const vals = patient[p.key];
    g.strokeStyle = C[p.key];
    g.lineWidth = p.key === "risk" ? 2.2 : 1.4;
    g.beginPath();
    let pen = false;
    for (let h = x0; h <= x1; h++) {
      const v = vals[h];
      if (v == null) { pen = false; continue; }
      const y = Math.min(p.top + p.h, Math.max(p.top, Y(v)));
      pen ? g.lineTo(X(h), y) : g.moveTo(X(h), y);
      pen = true;
    }
    g.stroke();
    // reviews as triangles on the risk panel
    if (p.key === "risk") {
      g.fillStyle = C.risk;
      for (const h of patient.reviews) {
        if (h < x0 || h > x1 || (!showOutcome && h > now)) continue;
        const x = X(h), y = Y(vals[h] ?? 0) - 6;
        g.beginPath();
        g.moveTo(x - 6, y - 9); g.lineTo(x + 6, y - 9); g.lineTo(x, y);
        g.fill();
      }
    }
    // now and onset lines
    g.strokeStyle = C.now;
    g.lineWidth = 1.6;
    g.beginPath(); g.moveTo(X(now), p.top); g.lineTo(X(now), p.top + p.h); g.stroke();
    if (onset != null && onset <= x1) {
      g.strokeStyle = C.onset;
      g.lineWidth = 2;
      g.beginPath(); g.moveTo(X(onset), p.top); g.lineTo(X(onset), p.top + p.h); g.stroke();
    }
  }
  g.fillStyle = C.now;
  g.textAlign = X(now) > R - 30 ? "right" : "left";
  g.fillText("now", X(now) + (X(now) > R - 30 ? -4 : 3), 11);
  g.textAlign = "left";
  if (onset != null && onset <= x1) {
    g.fillStyle = C.onset;
    const right = X(onset) > R - 50;
    g.textAlign = right ? "right" : "left";
    g.fillText("sepsis", X(onset) + (right ? -4 : 3), 11);
    g.textAlign = "left";
  }
  g.fillStyle = C.muted;
  g.fillText(`hour ${x0}`, L, H - 1);
  g.textAlign = "right";
  g.fillText(`hour ${x1}`, R, H - 1);
}

export const chartLegend = (showOutcome) => `
<div class="legend">
  <span><i style="background:${C.risk}"></i>Septris risk</span>
  <span><i style="background:${C.hr}"></i>heart rate</span>
  <span><i style="background:${C.map}"></i>blood pressure</span>
  <span>▼ chart reviewed</span>
  ${showOutcome ? `<span><i style="background:#ffffff33"></i>after this point (from the record)</span>
  <span><i style="background:#3ccf8e66"></i>6–12 h before sepsis</span>
  <span><i style="background:${C.onset}"></i>sepsis recorded</span>` : ""}
</div>`;
