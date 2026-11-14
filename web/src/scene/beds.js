// The 20 bed bays: bed, patient, bedside monitor (live canvas texture),
// floor status ring, Septris pick beam and a floating CSS label.
// update() restyles every bay for the current review.
import * as THREE from "three";
import { CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { ordinal } from "../data.js";

const COLOR = {
  pick: new THREE.Color("#4fb3ff"),
  high: new THREE.Color("#ff6b5e"),
  med: new THREE.Color("#f5b84b"),
  low: new THREE.Color("#3ccf8e"),
  snooze: new THREE.Color("#5b6b70"),
  empty: new THREE.Color("#2a3a40"),
};

// beds 1-10 along the back wall, 11-20 along the front, corridor between
export function bayPosition(bed) {
  const row = bed <= 10 ? 0 : 1;
  const i = (bed - 1) % 10;
  return new THREE.Vector3(-19.8 + i * 4.4, 0, row === 0 ? -7 : 7);
}

function roundedBox(w, h, d, r) {
  const shape = new THREE.Shape();
  const x = -w / 2, y = -d / 2;
  shape.moveTo(x + r, y);
  shape.lineTo(x + w - r, y);
  shape.quadraticCurveTo(x + w, y, x + w, y + r);
  shape.lineTo(x + w, y + d - r);
  shape.quadraticCurveTo(x + w, y + d, x + w - r, y + d);
  shape.lineTo(x + r, y + d);
  shape.quadraticCurveTo(x, y + d, x, y + d - r);
  shape.lineTo(x, y + r);
  shape.quadraticCurveTo(x, y, x + r, y);
  const g = new THREE.ExtrudeGeometry(shape, { depth: h, bevelEnabled: true, bevelSize: 0.04, bevelThickness: 0.04, bevelSegments: 2 });
  g.rotateX(-Math.PI / 2);
  return g;
}

const GLOW = 1.9; // rings and beams are brighter than white so only they bloom

function beamAlpha() {
  const c = document.createElement("canvas");
  c.width = 4; c.height = 128;
  const g = c.getContext("2d");
  const grad = g.createLinearGradient(0, 0, 0, 128);
  grad.addColorStop(0, "#000"); grad.addColorStop(0.55, "#555"); grad.addColorStop(1, "#fff");
  g.fillStyle = grad;
  g.fillRect(0, 0, 4, 128);
  return new THREE.CanvasTexture(c);
}
const BEAM_ALPHA = beamAlpha();

const MAT = {
  frame: new THREE.MeshStandardMaterial({ color: "#c9d3d6", metalness: 0.6, roughness: 0.35 }),
  mattress: new THREE.MeshStandardMaterial({ color: "#c9d4d8", roughness: 0.85 }),
  pillow: new THREE.MeshStandardMaterial({ color: "#dfe6e8", roughness: 0.9 }),
  skin: new THREE.MeshStandardMaterial({ color: "#c99a7a", roughness: 0.7 }),
  pole: new THREE.MeshStandardMaterial({ color: "#8a9ba0", metalness: 0.7, roughness: 0.3 }),
  curtain: new THREE.MeshStandardMaterial({ color: "#5e8f9c", roughness: 1, transparent: true, opacity: 0.22, side: THREE.DoubleSide }),
};

function makeMonitor() {
  const canvas = document.createElement("canvas");
  canvas.width = 320;
  canvas.height = 200;
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const screen = new THREE.Mesh(
    new THREE.PlaneGeometry(0.95, 0.6),
    new THREE.MeshBasicMaterial({ map: tex, toneMapped: false }),
  );
  const bezel = new THREE.Mesh(new THREE.BoxGeometry(1.05, 0.7, 0.08), new THREE.MeshStandardMaterial({ color: "#1d2a2f" }));
  screen.position.z = 0.045;
  const g = new THREE.Group();
  g.add(bezel, screen);
  return { group: g, canvas, tex };
}

function drawMonitor(m, bed, row, patient, color) {
  const g = m.canvas.getContext("2d");
  g.fillStyle = "#03090c";
  g.fillRect(0, 0, 320, 200);
  g.font = "600 22px IBM Plex Mono, monospace";
  g.fillStyle = "#8fa6ad";
  g.fillText(`BED ${bed}`, 16, 32);
  if (!row) {
    g.fillText("EMPTY", 16, 110);
    m.tex.needsUpdate = true;
    return;
  }
  const css = `#${color.getHexString()}`;
  g.fillStyle = css;
  g.font = "700 64px IBM Plex Mono, monospace";
  g.fillText(String(row.percentile), 16, 100);
  g.font = "500 18px IBM Plex Mono, monospace";
  g.fillStyle = "#8fa6ad";
  g.fillText("RISK /100", 16, 126);
  // sparkline: risk over the last 24 h up to now
  const series = patient.risk.slice(Math.max(0, row.record_hour - 23), row.record_hour + 1);
  g.strokeStyle = css;
  g.lineWidth = 3;
  g.beginPath();
  series.forEach((v, i) => {
    const x = 150 + (i / 23) * 155, y = 130 - ((v ?? 0) / 100) * 100;
    i ? g.lineTo(x, y) : g.moveTo(x, y);
  });
  g.stroke();
  g.fillStyle = "#cfe0e4";
  g.font = "500 18px IBM Plex Mono, monospace";
  const hr = patient.hr[row.record_hour], map = patient.map[row.record_hour];
  g.fillText(`HR ${hr ?? "--"}   MAP ${map ?? "--"}`, 16, 176);
  m.tex.needsUpdate = true;
}

export function createBeds(world, onSelect) {
  const { scene, camera, renderer } = world;
  const bays = new Map();
  const hitboxes = [];
  const frameGeo = roundedBox(1.15, 0.12, 2.3, 0.12);
  const mattressGeo = roundedBox(1.0, 0.18, 2.1, 0.14);

  for (let bed = 1; bed <= 20; bed++) {
    const g = new THREE.Group();
    const pos = bayPosition(bed);
    g.position.copy(pos);
    scene.add(g);

    const frame = new THREE.Mesh(frameGeo, MAT.frame);
    frame.position.y = 0.55;
    const legs = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.5, 2.0), new THREE.MeshStandardMaterial({ color: "#56666b", metalness: 0.5, roughness: 0.4 }));
    legs.position.y = 0.3;
    const mattress = new THREE.Mesh(mattressGeo, MAT.mattress);
    mattress.position.y = 0.72;
    const pillow = new THREE.Mesh(new THREE.CapsuleGeometry(0.16, 0.5, 6, 12), MAT.pillow);
    pillow.rotation.z = Math.PI / 2;
    pillow.position.set(0, 0.98, -0.82);
    // patient: head + body under a blanket whose colour shows status
    const blanketMat = new THREE.MeshStandardMaterial({ color: "#6f8f99", roughness: 0.9 });
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.3, 1.1, 6, 16), blanketMat);
    body.rotation.x = Math.PI / 2;
    body.scale.set(1.15, 1, 0.55);
    body.position.set(0, 1.0, 0.18);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.17, 20, 16), MAT.skin);
    head.position.set(0, 1.1, -0.72);
    const patientGroup = new THREE.Group();
    patientGroup.add(body, head);
    for (const m of [frame, legs, mattress, pillow, body, head]) m.castShadow = m.receiveShadow = true;

    // bedside monitor on a pole
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.9, 8), MAT.pole);
    pole.position.set(0.95, 0.95, -1.0);
    const monitor = makeMonitor();
    monitor.group.position.set(0.95, 1.85, -0.95);
    monitor.group.rotation.y = -0.35;

    // IV stand with a fluid bag
    const iv = new THREE.Group();
    const ivPole = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 2.1, 8), MAT.pole);
    ivPole.position.y = 1.05;
    const ivBag = new THREE.Mesh(new THREE.CapsuleGeometry(0.09, 0.2, 4, 10), new THREE.MeshStandardMaterial({ color: "#cfeaf5", transparent: true, opacity: 0.75, roughness: 0.2 }));
    ivBag.position.set(0.12, 1.85, 0);
    const ivArm = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.02, 0.02), MAT.pole);
    ivArm.position.set(0.06, 2.08, 0);
    iv.add(ivPole, ivBag, ivArm);
    iv.position.set(-0.9, 0, -0.9);

    // curtain partition on one side
    const curtain = new THREE.Mesh(new THREE.PlaneGeometry(3.0, 2.3), MAT.curtain);
    curtain.rotation.y = Math.PI / 2;
    curtain.position.set(2.2, 1.15, -0.2);

    // floor status ring
    const ringMat = new THREE.MeshBasicMaterial({ color: COLOR.low, transparent: true, opacity: 0.85, toneMapped: false });
    const ring = new THREE.Mesh(new THREE.RingGeometry(1.55, 1.75, 64), ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.012;
    const padMat = new THREE.MeshBasicMaterial({ color: COLOR.low, transparent: true, opacity: 0.08 });
    const pad = new THREE.Mesh(new THREE.CircleGeometry(1.55, 48), padMat);
    pad.rotation.x = -Math.PI / 2;
    pad.position.y = 0.01;

    // pick beam: a soft vertical column of light
    const beamMat = new THREE.MeshBasicMaterial({ color: COLOR.pick, transparent: true, opacity: 0.18, alphaMap: BEAM_ALPHA, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    const beam = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.7, 7, 48, 1, true), beamMat);
    beam.position.y = 3.5;
    beam.visible = false;
    const lamp = new THREE.PointLight("#4fb3ff", 0, 7, 1.6);
    lamp.position.set(0, 3.5, 0);

    const hit = new THREE.Mesh(new THREE.BoxGeometry(3.6, 2.6, 3.6), new THREE.MeshBasicMaterial({ visible: false }));
    hit.position.y = 1.3;
    hit.userData.bed = bed;
    hitboxes.push(hit);

    const el = document.createElement("div");
    el.className = "bed-label";
    el.style.pointerEvents = "auto";
    el.addEventListener("click", () => onSelect(bed));
    const label = new CSS2DObject(el);
    label.position.set(0, 3.0, 0);

    g.add(frame, legs, mattress, pillow, patientGroup, pole, monitor.group, iv, curtain, ring, pad, beam, lamp, hit, label);
    bays.set(bed, { g, ring, ringMat, pad, padMat, beam, beamMat, lamp, patientGroup, blanketMat, monitor, el, state: "low" });
  }

  // click (not drag) to select a bed
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let down = null;
  renderer.domElement.addEventListener("pointerdown", (e) => (down = [e.clientX, e.clientY]));
  renderer.domElement.addEventListener("pointerup", (e) => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 6) return;
    const r = renderer.domElement.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hitObj = ray.intersectObjects(hitboxes, false)[0];
    if (hitObj) onSelect(hitObj.object.userData.bed);
  });

  world.onFrame((dt, t) => {
    for (const b of bays.values()) {
      if (b.state === "pick") {
        const p = 0.5 + 0.5 * Math.sin(t * 3);
        b.beamMat.opacity = 0.1 + 0.12 * p;
        b.lamp.intensity = 6 + 6 * p;
        b.ring.scale.setScalar(1 + 0.04 * p);
      } else if (b.state === "warnKey") {
        b.ringMat.opacity = 0.55 + 0.4 * Math.sin(t * 5) ** 2;
      }
    }
  });

  function update(data, slotRow, bedRows, st) {
    const byBed = new Map(bedRows.map((r) => [r.bed, r]));
    const missBed = st.focus?.kind === "miss" && st.focus.slot === st.slot ? st.focus.bed : null;
    for (const [bed, b] of bays) {
      const r = byBed.get(bed);
      const pat = r ? data.patients[r.p] : null;
      let color, state;
      if (!r) { color = COLOR.empty; state = "empty"; }
      else if (r.picked) { color = COLOR.pick; state = "pick"; }
      else if (r.snoozed) { color = COLOR.snooze; state = "snooze"; }
      else { color = r.tier === 2 ? COLOR.high : r.tier === 1 ? COLOR.med : COLOR.low; state = "rank"; }
      const soon = r && st.showKey && r.hours_to_sepsis != null && r.hours_to_sepsis > 0 && r.hours_to_sepsis <= 12;
      if (soon && state !== "pick") state = "warnKey";
      b.state = state;
      b.ringMat.color.copy(soon && state !== "pick" ? COLOR.high : color).multiplyScalar(state === "snooze" || state === "empty" ? 1 : GLOW);
      b.ringMat.opacity = state === "snooze" || state === "empty" ? 0.35 : 0.85;
      b.ring.scale.setScalar(1);
      b.padMat.color.copy(color);
      b.padMat.opacity = state === "pick" ? 0.18 : 0.07;
      b.beam.visible = state === "pick";
      b.lamp.intensity = 0;
      b.patientGroup.visible = !!r;
      b.blanketMat.color.set(state === "snooze" ? "#55656a" : "#6f8f99");
      drawMonitor(b.monitor, bed, r, pat, color);

      const cls = ["bed-label"];
      if (state === "pick") cls.push("pick");
      if (state === "snooze") cls.push("snooze");
      if (st.selectedBed === bed) cls.push("sel");
      b.el.className = cls.join(" ");
      let line = "empty";
      if (r) line = r.picked ? "Septris's pick" : r.snoozed ? `reviewed ${r.hours_since_check} h ago` : `${ordinal(r.rank)} in line`;
      let extra = "";
      if (r && st.showKey) {
        if (pat.group === "uncertain_onset") extra = "<small class='warn'>septic on arrival</small>";
        else if (soon) extra = `<small class='warn'>⚠ <span class='long'>sepsis in </span>${Math.round(r.hours_to_sepsis)} h</small>`;
        else if (r.hours_to_sepsis != null && r.hours_to_sepsis <= 0) extra = "<small class='warn'>already septic</small>";
      }
      if (bed === missBed) extra += "<small class='warn'>missed</small>";
      b.el.innerHTML = `<span class='long'>Bed </span>${bed}<small class='line'>${line}</small>${extra}`;
    }
  }

  return { update, bayPosition };
}
