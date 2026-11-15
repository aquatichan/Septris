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

// ---------- clinical look (matches the reference renders) ----------

/** Sheet-vinyl hospital floor: teal-green, faint mottling, welded seams every 2 m. */
export function vinylFloor(repX, repY, base = "#4b7d78") {
  return tex(canvas(512, 512, (g, w, h) => {
    g.fillStyle = base;
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < 90; i++) { // soft clouds of tone variation
      const x = Math.random() * w, y = Math.random() * h, r = 20 + Math.random() * 70;
      const grad = g.createRadialGradient(x, y, 0, x, y, r);
      const c = Math.random() < 0.5 ? "255,255,255" : "0,30,30";
      grad.addColorStop(0, `rgba(${c},0.03)`); grad.addColorStop(1, `rgba(${c},0)`);
      g.fillStyle = grad; g.fillRect(x - r, y - r, r * 2, r * 2);
    }
    speckle(g, w, h, 6000, 0.08);
    speckle(g, w, h, 2500, 0.07, false);
    g.fillStyle = "rgba(20,45,45,0.35)";
    g.fillRect(0, 0, w, 2); // seam
  }), { repeat: [repX, repY] });
}

/**
 * Clean white wall panels with thin vertical joints every 1.2 m. With `dado`,
 * the lower 0.9 m is a grey-teal band (corridor style). Texture spans 2.4 m x 3 m.
 */
export function panelWall(repX, { dado = null } = {}) {
  return tex(canvas(256, 320, (g, w, h) => {
    g.fillStyle = "#eef1f0"; g.fillRect(0, 0, w, h);
    const grad = g.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, "rgba(0,0,0,0.03)"); grad.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = grad; g.fillRect(0, 0, w, h);
    speckle(g, w, h, 300, 0.03);
    g.fillStyle = "rgba(60,75,80,0.55)";
    for (const x of [0, w / 2]) g.fillRect(x, 0, 2, h); // panel joints
    g.fillRect(0, h * 0.27, w, 1.5); // horizontal joint at ~2.2 m
    const y0 = h * (1 - 0.9 / 3);
    if (dado) { g.fillStyle = dado; g.fillRect(0, y0, w, h - y0); }
    g.fillStyle = "#f7f8f8"; g.fillRect(0, h - 10, w, 10); // skirting
    g.fillStyle = "rgba(0,0,0,0.25)"; g.fillRect(0, h - 11, w, 1);
  }), { repeat: [repX, 1] });
}

/** Bed-head service panel: white with a blue stripe, red digital gas readouts, outlets and switches. */
export function headwallPanel() {
  return tex(canvas(1024, 256, (g, w, h) => {
    g.fillStyle = "#f3f5f6"; g.fillRect(0, 0, w, h);
    g.fillStyle = "#2c8fd6"; g.fillRect(0, 150, w, 34);
    g.fillStyle = "rgba(0,0,0,0.12)"; g.fillRect(0, 0, w, 3); g.fillRect(0, h - 3, w, 3);
    const round = (x, y, r, fill, ring = "#9aa6ab") => { g.beginPath(); g.arc(x, y, r, 0, 7); g.fillStyle = fill; g.fill(); g.lineWidth = 3; g.strokeStyle = ring; g.stroke(); };
    // two red LED readouts
    for (const x of [300, 640]) {
      g.fillStyle = "#1c1f22"; g.fillRect(x, 40, 92, 52);
      g.fillStyle = "#ff3b30"; g.font = "700 40px 'IBM Plex Mono', monospace"; g.fillText(x === 300 ? "4.2" : "21", x + 8, 82);
    }
    // gas outlets (white with coloured collars), switches and sockets
    [["#e9ecef", 90], ["#ffffff", 170], ["#f2c94c", 450], ["#4fa3e0", 530], ["#ffffff", 790]].forEach(([c, x]) => round(x, 70, 26, "#fbfbfb", c));
    for (let i = 0; i < 4; i++) { g.fillStyle = "#e3e7ea"; g.fillRect(860 + i * 38, 46, 30, 46); g.fillStyle = "#c2cacf"; g.fillRect(866 + i * 38, 52, 18, 10); }
    for (let i = 0; i < 6; i++) { g.fillStyle = "#ffffff"; g.fillRect(60 + i * 150, 200, 64, 40); g.fillStyle = "#aab4b9"; g.fillRect(80 + i * 150, 212, 6, 14); g.fillRect(98 + i * 150, 212, 6, 14); }
    g.fillStyle = "#e5483f"; g.fillRect(744, 54, 26, 30); // call button
  }));
}

/** A green running-man fire-exit sign. */
export function exitSign() {
  return tex(canvas(256, 96, (g, w, h) => {
    g.fillStyle = "#1f9d55"; g.fillRect(0, 0, w, h);
    g.strokeStyle = "#ffffff"; g.lineWidth = 4; g.strokeRect(4, 4, w - 8, h - 8);
    g.fillStyle = "#fff"; g.font = "700 30px Arial, sans-serif"; g.fillText("Fire", 18, 42); g.fillText("exit", 18, 78);
    // running figure
    g.lineWidth = 7; g.lineCap = "round"; g.strokeStyle = "#fff";
    g.beginPath(); g.arc(150, 22, 8, 0, 7); g.fill();
    g.beginPath(); g.moveTo(146, 34); g.lineTo(136, 58); g.lineTo(150, 72); g.lineTo(144, 88);
    g.moveTo(136, 58); g.lineTo(120, 80); g.moveTo(144, 40); g.lineTo(160, 52); g.lineTo(170, 44); g.moveTo(144, 40); g.lineTo(128, 48); g.stroke();
    g.beginPath(); g.moveTo(200, 30); g.lineTo(200, 74); g.moveTo(186, 60); g.lineTo(200, 76); g.lineTo(214, 60); g.stroke(); // arrow
  }));
}

/** Notice board with a few coloured information sheets; `kind` varies the layout. */
export function noticeBoard(kind = 0) {
  return tex(canvas(320, 400, (g, w, h) => {
    g.fillStyle = "#d9dee0"; g.fillRect(0, 0, w, h);
    g.fillStyle = "#ffffff"; g.fillRect(14, 14, w - 28, h - 28);
    g.fillStyle = ["#21a0c9", "#1aa384", "#c94b6d"][kind % 3]; g.fillRect(14, 14, w - 28, 44);
    g.fillStyle = "#fff"; g.font = "700 22px Arial"; g.fillText(["Ward information", "Hand hygiene", "Staff on duty"][kind % 3], 28, 44);
    g.fillStyle = "#b8c2c6";
    for (let i = 0; i < 11; i++) g.fillRect(30, 80 + i * 16, 150 + ((i * 53) % 100), 6);
    const cols = ["#7bc8a4", "#f2a65a", "#8fb8e8", "#e88f8f"];
    for (let i = 0; i < 4; i++) { g.fillStyle = cols[i]; g.fillRect(30 + i * 66, 280, 56, 80); g.fillStyle = "rgba(255,255,255,0.7)"; for (let j = 0; j < 4; j++) g.fillRect(36 + i * 66, 292 + j * 14, 40, 4); }
  }));
}

/** Soft elongated highlight used to fake light reflections on the glossy floor. */
export function floorSheen() {
  return tex(canvas(64, 256, (g, w, h) => {
    const grad = g.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, h / 2);
    grad.addColorStop(0, "rgba(255,255,255,0.9)"); grad.addColorStop(0.35, "rgba(255,255,255,0.35)"); grad.addColorStop(1, "rgba(255,255,255,0)");
    g.setTransform(w / h, 0, 0, 1, 0, 0); // squash the circle into a streak
    g.fillStyle = grad; g.fillRect(0, 0, h, h);
  }), { srgb: false });
}

/** Large painted letters on a wall, transparent background ("THIRD FLOOR / INTENSIVE CARE"). */
export function wallLettering(lines, { w = 1024, h = 360, color = "#26343a", font = "Arial" } = {}) {
  return tex(canvas(w, h, (g) => {
    g.fillStyle = color; g.textAlign = "center"; g.textBaseline = "middle";
    const lh = h / lines.length;
    lines.forEach((t, i) => { g.font = `500 ${Math.floor(lh * 0.62)}px ${font}, sans-serif`; g.fillText(t, w / 2, lh * (i + 0.5)); });
  }));
}
