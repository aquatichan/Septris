// Every surface texture is drawn on a canvas at start-up, so the site ships
// no image files. Each function returns a ready-to-use THREE texture.
import * as THREE from "three";

function canvas(w, h, draw) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  return c;
}

function tex(c, { repeat, srgb = true } = {}) {
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  if (repeat) {
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(repeat[0], repeat[1]);
  }
  t.anisotropy = 8;
  return t;
}

function speckle(g, w, h, n, alpha, dark = true) {
  for (let i = 0; i < n; i++) {
    g.fillStyle = `rgba(${dark ? "0,0,0" : "255,255,255"},${Math.random() * alpha})`;
    g.fillRect(Math.random() * w, Math.random() * h, 1 + Math.random() * 2, 1 + Math.random() * 2);
  }
}

/** Pale ceramic floor tiles, 2x2 tiles per texture repeat. */
export function floorTiles(repX, repY) {
  return tex(canvas(512, 512, (g, w, h) => {
    g.fillStyle = "#c9cdca";
    g.fillRect(0, 0, w, h);
    for (let y = 0; y < 2; y++) for (let x = 0; x < 2; x++) {
      g.fillStyle = `rgb(${196 + Math.random() * 16 | 0},${201 + Math.random() * 14 | 0},${198 + Math.random() * 14 | 0})`;
      g.fillRect(x * 256 + 3, y * 256 + 3, 250, 250);
    }
    speckle(g, w, h, 2500, 0.05);
    g.strokeStyle = "#9da3a0";
    g.lineWidth = 5;
    for (let i = 0; i <= 2; i++) {
      g.beginPath(); g.moveTo(i * 256, 0); g.lineTo(i * 256, h); g.stroke();
      g.beginPath(); g.moveTo(0, i * 256); g.lineTo(w, i * 256); g.stroke();
    }
  }), { repeat: [repX, repY] });
}

/** Speckled acoustic ceiling tiles in a dark metal grid. */
export function ceilingTiles(repX, repY) {
  return tex(canvas(256, 256, (g, w, h) => {
    g.fillStyle = "#e9e9e6";
    g.fillRect(0, 0, w, h);
    speckle(g, w, h, 900, 0.35);
    g.strokeStyle = "#5d6468";
    g.lineWidth = 6;
    g.strokeRect(0, 0, w, h);
  }), { repeat: [repX, repY] });
}

/** Painted wall: white above, a pale blue-grey band and bumper rail below. */
export function wallPaint(repX) {
  return tex(canvas(64, 512, (g, w, h) => {
    g.fillStyle = "#f1f3f2";
    g.fillRect(0, 0, w, h);
    g.fillStyle = "#cfd9de";
    g.fillRect(0, h * 0.62, w, h * 0.38);
    g.fillStyle = "#9fb0b8";
    g.fillRect(0, h * 0.60, w, 10);
    g.fillStyle = "#8d989d";
    g.fillRect(0, h - 22, w, 22);
  }), { repeat: [repX, 1] });
}

/** Brushed stainless steel with vertical panel seams (elevator doors and walls). */
export function brushedSteel(panels = 2) {
  return tex(canvas(512, 512, (g, w, h) => {
    const grad = g.createLinearGradient(0, 0, w, 0);
    grad.addColorStop(0, "#8f9396"); grad.addColorStop(0.5, "#b4b8ba"); grad.addColorStop(1, "#8c9093");
    g.fillStyle = grad;
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 1400; i++) {
      g.fillStyle = `rgba(255,255,255,${Math.random() * 0.06})`;
      g.fillRect(Math.random() * w, 0, 1, h);
    }
    for (let i = 0; i <= panels; i++) {
      const x = (i * w) / panels;
      g.fillStyle = "rgba(20,24,26,.55)"; g.fillRect(x - 2, 0, 3, h);
      g.fillStyle = "rgba(255,255,255,.5)"; g.fillRect(x + 2, 0, 1.5, h);
    }
  }));
}

/** Elevator car operating panel: two columns of floor buttons, door and bell buttons. */
export function buttonPanel(litFloor = 3) {
  return tex(canvas(256, 512, (g, w, h) => {
    g.fillStyle = "#17191b";
    g.fillRect(0, 0, w, h);
    g.font = "600 22px 'IBM Plex Sans', sans-serif";
    g.textAlign = "right";
    g.textBaseline = "middle";
    for (let f = 1; f <= 14; f++) {
      const col = (f - 1) % 2, row = 6 - Math.floor((f - 1) / 2);
      const x = 96 + col * 96, y = 60 + row * 54;
      g.fillStyle = f === litFloor ? "#ffd27a" : "#060707";
      g.beginPath(); g.arc(x + 22, y, 18, 0, Math.PI * 2); g.fill();
      if (f === litFloor) { g.strokeStyle = "#fff1c9"; g.lineWidth = 3; g.stroke(); }
      g.fillStyle = "#b9bfc2";
      g.fillText(String(f), x - 4, y);
    }
    for (const [i, s] of ["◂▸", "🔔"].entries()) {
      const x = 96 + i * 96, y = 60 + 7 * 54;
      g.fillStyle = "#060707"; g.beginPath(); g.arc(x + 22, y, 18, 0, Math.PI * 2); g.fill();
      g.fillStyle = "#b9bfc2"; g.font = "600 18px sans-serif"; g.fillText(s, x - 2, y);
    }
  }));
}

/** Light oak laminate for desks and cabinets. */
export function wood() {
  return tex(canvas(256, 256, (g, w, h) => {
    g.fillStyle = "#cdb89a";
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 260; i++) {
      g.fillStyle = `rgba(110,80,50,${Math.random() * 0.1})`;
      g.fillRect(0, Math.random() * h, w, 1 + Math.random() * 2);
    }
  }));
}

/** Additive floor decal: sunlight through window blinds. */
export function blindsLight() {
  return tex(canvas(256, 256, (g, w, h) => {
    g.fillStyle = "#000";
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 16; i++) {
      const y = 10 + i * 15;
      const grad = g.createLinearGradient(0, 0, w, 0);
      grad.addColorStop(0, "rgba(255,246,225,0.95)"); grad.addColorStop(1, "rgba(255,246,225,0)");
      g.fillStyle = grad;
      g.fillRect(0, y, w, 8);
    }
  }));
}

/** A window with half-open blinds, seen from inside (emissive). */
export function windowBlinds() {
  return tex(canvas(256, 256, (g, w, h) => {
    g.fillStyle = "#eaf4fb";
    g.fillRect(0, 0, w, h);
    for (let y = 0; y < h; y += 14) { g.fillStyle = "#b8c4cb"; g.fillRect(0, y, w, 6); }
    g.strokeStyle = "#7f8a90"; g.lineWidth = 10; g.strokeRect(0, 0, w, h);
    g.fillStyle = "#7f8a90"; g.fillRect(w / 2 - 3, 0, 6, h);
  }));
}

/** Text sign on a dark or light plate. */
export function signTexture(text, { w = 512, h = 96, bg = "#0d1d24", fg = "#4fb3ff", font = "Space Grotesk" } = {}) {
  return tex(canvas(w, h, (g) => {
    g.fillStyle = bg;
    g.fillRect(0, 0, w, h);
    g.fillStyle = fg;
    g.font = `700 ${Math.round(h * 0.56)}px "${font}", "IBM Plex Sans", sans-serif`;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText(text, w / 2, h / 2 + 2);
  }));
}
