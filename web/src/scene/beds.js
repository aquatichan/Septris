// The 20 bed bays and everything that shows Septris's output in the room:
// the floor ring (priority colour), the bedside monitor (risk score and
// trend), the pick beam, and the floating label. update() restyles every bay
// for the current check. Furniture is merged into a few meshes per material
// so 20 fully dressed bays stay cheap to draw.
import * as THREE from "three";
import { CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { ordinal } from "../data.js";
import { makePerson, makeWalker, corridorRoute } from "./people.js";

const COLOR = {
  pick: new THREE.Color("#2f8fff"),
  hit: new THREE.Color("#1fbf75"),
  high: new THREE.Color("#ff4b3e"),
  med: new THREE.Color("#f5a623"),
  low: new THREE.Color("#2fbf71"),
  snooze: new THREE.Color("#8b979c"),
  empty: new THREE.Color("#b5bec2"),
};

const ROW_Z = 9.3; // bed centres; heads are against the outer walls

// beds 1-10 along the back wall, 11-20 along the front wall, corridor between
export function bayPosition(bed) {
  const i = (bed - 1) % 10;
  return new THREE.Vector3(-19.8 + i * 4.4, 0, bed <= 10 ? -ROW_Z : ROW_Z);
}

const GLOW = 1.6; // rings and beams are brighter than white so they bloom a little

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

const std = (color, o = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.7, ...o });
const MAT = {
  beige: std("#d9cdb8", { roughness: 0.55 }),
  steel: std("#b9c2c6", { metalness: 0.7, roughness: 0.3 }),
  dark: std("#3a4246", { roughness: 0.6 }),
  white: std("#f4f6f6", { roughness: 0.85 }),
  blanket: std("#3f6fb5", { roughness: 0.95 }),
  curtain: std("#2f5aa6", { roughness: 1, side: THREE.DoubleSide }),
  skin: std("#c99a7a"),
  glow: new THREE.MeshBasicMaterial({ color: new THREE.Color(2.2, 2.2, 2.1), toneMapped: false }),
  bag: std("#d7eef7", { transparent: true, opacity: 0.8, roughness: 0.2 }),
  pump: std("#e9edf0", { roughness: 0.4 }),
};

/** Collects static pieces and merges them into one mesh per material. */
function makeBatch() {
  const groups = new Map();
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
  return {
    add(geo, material, parent, x, y, z, rx = 0, ry = 0, rz = 0, sx = 1, sy = 1, sz = 1) {
      const g = (geo.index ? geo.toNonIndexed() : geo.clone());
      m4.compose(new THREE.Vector3(x, y, z), q.setFromEuler(e.set(rx, ry, rz)), new THREE.Vector3(sx, sy, sz));
      g.applyMatrix4(m4).applyMatrix4(parent);
      for (const k of Object.keys(g.attributes)) if (!["position", "normal", "uv"].includes(k)) g.deleteAttribute(k);
      if (!groups.has(material)) groups.set(material, []);
      groups.get(material).push(g);
    },
    build(scene) {
      for (const [material, geos] of groups) {
        const mesh = new THREE.Mesh(mergeGeometries(geos, false), material);
        mesh.castShadow = material !== MAT.glow && !material.transparent;
        mesh.receiveShadow = true;
        scene.add(mesh);
      }
    },
  };
}

/** A hanging curtain bunched into folds. */
function curtainGeometry() {
  const g = new THREE.PlaneGeometry(1.1, 2.15, 22, 1);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) p.setZ(i, Math.sin(p.getX(i) * 26) * 0.07);
  g.computeVertexNormals();
  return g;
}

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

export function createBeds(world, onSelect, lobby) {
  const { scene, camera, renderer } = world;
  const bays = new Map();
  const hitboxes = [];
  const batch = makeBatch();
  const G = {
    box: (w, h, d) => new THREE.BoxGeometry(w, h, d),
    cyl: (r, h, s = 10) => new THREE.CylinderGeometry(r, r, h, s),
    curtain: curtainGeometry(),
  };

  for (let bed = 1; bed <= 20; bed++) {
    const g = new THREE.Group();
    g.position.copy(bayPosition(bed));
    if (bed > 10) g.rotation.y = Math.PI; // front row: heads against the front wall
    g.updateMatrix();
    scene.add(g);
    const P = g.matrix;
    const put = (geo, material, ...t) => batch.add(geo, material, P, ...t);

    // bed: wheels, lift column, frame, mattress, head and foot boards, side rails
    for (const [x, z] of [[-0.42, -0.9], [0.42, -0.9], [-0.42, 0.9], [0.42, 0.9]]) put(G.cyl(0.07, 0.05, 12), MAT.dark, x, 0.07, z, 0, 0, Math.PI / 2);
    put(G.box(0.7, 0.3, 1.5), MAT.dark, 0, 0.27, 0);
    put(G.box(0.98, 0.12, 2.08), MAT.beige, 0, 0.47, 0);
    put(G.box(0.9, 0.15, 2.0), MAT.white, 0, 0.6, 0);
    put(G.box(1.02, 0.78, 0.07), MAT.beige, 0, 0.82, -1.07);
    put(G.box(1.02, 0.5, 0.07), MAT.beige, 0, 0.68, 1.07);
    for (const x of [-0.5, 0.5]) put(G.box(0.04, 0.26, 0.85), MAT.beige, x, 0.82, -0.4);
    put(G.box(0.62, 0.11, 0.36), MAT.white, 0, 0.73, -0.78);

    // head wall: service rail with outlets, reading light, monitor arm
    put(G.box(2.7, 0.24, 0.07), MAT.beige, 0, 1.32, -1.66);
    for (const x of [-1.0, -0.7, 0.55]) put(G.box(0.14, 0.14, 0.03), MAT.white, x, 1.32, -1.615);
    put(G.box(1.5, 0.1, 0.12), MAT.glow, 0, 1.98, -1.62);
    put(G.box(1.6, 0.05, 0.16), MAT.steel, 0, 2.05, -1.62);
    put(G.box(0.06, 0.06, 0.5), MAT.beige, 0.95, 1.72, -1.42);

    // IV stand with two bags and an infusion pump
    for (let i = 0; i < 5; i++) put(G.box(0.3, 0.03, 0.04), MAT.steel, -0.92 + Math.cos(i * 1.257) * 0.14, 0.04, -0.72 + Math.sin(i * 1.257) * 0.14, 0, -i * 1.257, 0);
    put(G.cyl(0.015, 2.0, 8), MAT.steel, -0.92, 1.03, -0.72);
    put(G.box(0.36, 0.02, 0.02), MAT.steel, -0.92, 2.03, -0.72);
    for (const dx of [-0.14, 0.14]) put(new THREE.CapsuleGeometry(0.06, 0.16, 4, 8), MAT.bag, -0.92 + dx, 1.84, -0.72);
    put(G.box(0.16, 0.22, 0.1), MAT.pump, -0.92, 1.25, -0.66);

    // curtain rail down one side of the bay, with the curtain drawn back to the wall
    put(G.box(0.03, 0.03, 3.3), MAT.dark, 2.2, 2.6, -0.05);
    put(G.curtain, MAT.curtain, 2.2, 1.5, -1.05, 0, Math.PI / 2, 0);
    if (bed % 10 === 1) { // the first bay in each row also needs a rail on its open side
      put(G.box(0.03, 0.03, 3.3), MAT.dark, -2.2, 2.6, -0.05);
      put(G.curtain, MAT.curtain, -2.2, 1.5, -1.05, 0, Math.PI / 2, 0);
    }

    // some bays have a visitor chair or an over-bed table
    if (bed % 3 === 0) {
      put(G.box(0.5, 0.06, 0.5), MAT.beige, -1.35, 0.45, 0.75);
      put(G.box(0.5, 0.5, 0.06), MAT.beige, -1.35, 0.72, 0.52);
      for (const [x, z] of [[-1.57, 0.53], [-1.13, 0.53], [-1.57, 0.97], [-1.13, 0.97]]) put(G.cyl(0.02, 0.44, 6), MAT.steel, x, 0.22, z);
    }
    if (bed % 4 === 2) {
      put(G.box(0.8, 0.03, 0.42), MAT.white, 0.25, 0.98, 0.5);
      put(G.cyl(0.02, 0.9, 6), MAT.steel, 0.62, 0.5, 0.5);
      put(G.box(0.5, 0.03, 0.4), MAT.steel, 0.5, 0.04, 0.5);
    }

    // the patient: head on the pillow, body under a blue blanket that rises and falls
    const patientGroup = new THREE.Group();
    const blanketMat = MAT.blanket.clone();
    const sheet = new THREE.Mesh(G.box(0.92, 0.06, 1.42), blanketMat);
    sheet.position.set(0, 0.7, 0.28);
    const chest = new THREE.Mesh(new THREE.CapsuleGeometry(0.2, 1.05, 6, 14), blanketMat);
    chest.rotation.x = Math.PI / 2;
    chest.scale.set(1.25, 1, 0.6);
    chest.position.set(0, 0.76, 0.2);
    const headM = new THREE.Mesh(new THREE.SphereGeometry(0.12, 18, 14), std(["#e8c4a6", "#c99a7a", "#a8765a", "#7d5540"][bed % 4]));
    headM.position.set(0, 0.86, -0.72);
    headM.scale.set(0.95, 0.9, 1.05);
    const hairM = new THREE.Mesh(new THREE.SphereGeometry(0.125, 16, 10, 0, Math.PI * 2, 0, Math.PI * 0.5), std(["#2b211c", "#b9b3ac", "#4a3426", "#151515", "#d9d6d0"][bed % 5], { roughness: 0.95 }));
    hairM.position.set(0, 0.87, -0.76);
    hairM.rotation.x = -1.1;
    for (const m of [sheet, chest, headM, hairM]) { m.castShadow = true; m.receiveShadow = true; }
    patientGroup.add(sheet, chest, headM, hairM);

    const monitor = makeMonitor();
    monitor.group.position.set(0.95, 1.72, -1.15);
    monitor.group.rotation.y = -0.3;
    monitor.group.scale.setScalar(0.8);

    // priority ring on the floor, on a faint dark disc so it reads against pale tiles
    const ringMat = new THREE.MeshBasicMaterial({ color: COLOR.low, transparent: true, opacity: 0.95, toneMapped: false });
    const ring = new THREE.Mesh(new THREE.RingGeometry(1.62, 1.86, 72), ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.022;
    const padMat = new THREE.MeshBasicMaterial({ color: COLOR.low, transparent: true, opacity: 0.1, depthWrite: false });
    const pad = new THREE.Mesh(new THREE.CircleGeometry(1.62, 48), padMat);
    pad.rotation.x = -Math.PI / 2;
    pad.position.y = 0.018;

    const beamMat = new THREE.MeshBasicMaterial({ color: COLOR.pick, transparent: true, opacity: 0.2, alphaMap: BEAM_ALPHA, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    const beam = new THREE.Mesh(new THREE.CylinderGeometry(1.55, 1.8, 6, 48, 1, true), beamMat);
    beam.position.y = 3.0;
    beam.visible = false;

    const hit = new THREE.Mesh(new THREE.BoxGeometry(3.8, 2.6, 3.6), new THREE.MeshBasicMaterial({ visible: false }));
    hit.position.y = 1.3;
    hit.userData.bed = bed;
    hitboxes.push(hit);

    const el = document.createElement("div");
    el.className = "bed-label";
    el.style.pointerEvents = "auto";
    el.addEventListener("click", () => onSelect(bed));
    const label = new CSS2DObject(el);
    label.position.set(0, 3.1, 0);

    g.add(patientGroup, monitor.group, ring, pad, beam, hit, label);
    bays.set(bed, { g, ring, ringMat, pad, padMat, beam, beamMat, patientGroup, chest, blanketMat, monitor, el, state: "low", breath: 0.9 + ((bed * 37) % 10) / 25 });
  }
  batch.build(scene);

  // one shared light that sits over whichever bed is picked
  const lamp = new THREE.PointLight("#4fb3ff", 0, 8, 1.6);
  scene.add(lamp);

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
      if (b.patientGroup.visible) b.chest.scale.z = 0.6 + 0.035 * Math.sin(t * b.breath * 1.6); // breathing
      if (b.state === "pick" || b.state === "hit") {
        const p = 0.5 + 0.5 * Math.sin(t * 3);
        b.beamMat.opacity = 0.12 + 0.12 * p;
        lamp.intensity = 10 + 8 * p;
        b.ring.scale.setScalar(1 + 0.04 * p);
      }
    }
  });

  // the charge nurse walks (properly, along the corridor) to whichever bed Septris picks
  const nurse = makePerson({ color: "#16817f", seed: 0.31 });
  const tablet = new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.02, 0.19), new THREE.MeshStandardMaterial({ color: "#0d1d24", emissive: "#4fb3ff", emissiveIntensity: 1.2 }));
  tablet.position.set(0, -0.56, 0.1);
  nurse.armR.add(tablet);
  nurse.group.position.set(1.2, 0, 2.2);
  scene.add(nurse.group);
  const nurseWalk = makeWalker(nurse, 3.2); // brisk: she is on her way to a patient
  let nurseBed = null, nurseFace = 0;
  world.onFrame((dt, t) => {
    if (nurseWalk.step(dt)) { nurse.armR.rotation.x = -0.9; return; }
    nurse.idle(t, 0.5);
    nurse.armR.rotation.x = -1.0; // reading the tablet
    const d = Math.atan2(Math.sin(nurseFace - nurse.group.rotation.y), Math.cos(nurseFace - nurse.group.rotation.y));
    nurse.group.rotation.y += d * Math.min(1, dt * 6);
  });
  function sendNurse(bed, instant) {
    if (bed === nurseBed) return;
    nurseBed = bed;
    const pb = bayPosition(bed);
    const goal = new THREE.Vector3(pb.x - 1.25, 0, pb.z + (pb.z < 0 ? 0.9 : -0.9));
    nurseFace = Math.atan2(pb.x - goal.x, pb.z + (pb.z < 0 ? 0.3 : -0.3) - goal.z);
    if (instant) { nurse.group.position.copy(goal); nurse.group.rotation.y = nurseFace; nurseWalk.go([]); }
    else nurseWalk.go(corridorRoute(nurse.group.position, goal));
  }

  let lastSlot = null, lastVersion = 0, lastNurseSlot = null;
  const occupant = new Map(); // bed -> patient index currently shown

  function update(data, slotRow, bedRows, st) {
    // patients coming and going: when a bed's occupant changed since the last
    // review shown, the old patient is wheeled to the elevator and the new one in
    const newOcc = new Map(bedRows.map((r) => [r.bed, r.p]));
    const edited = st.manualVersion !== lastVersion;
    lastVersion = st.manualVersion;
    if (lobby && (st.slot !== lastSlot || edited)) {
      lobby.cancel();
      const changed = [];
      for (let bed = 1; bed <= 20; bed++) if (occupant.get(bed) !== newOcc.get(bed)) changed.push(bed);
      const stepped = lastSlot != null && Math.abs(st.slot - lastSlot) <= 5 && (st.tourStep == null || edited);
      if (stepped && changed.length && changed.length <= 6) {
        for (const bed of changed) {
          const b = bays.get(bed);
          const arrives = newOcc.has(bed);
          b.arriving = arrives;
          lobby.transfer(bed, { leaves: occupant.has(bed), arrives, done: () => { b.arriving = false; b.patientGroup.visible = b.occupied; } });
        }
      }
      lastSlot = st.slot;
      occupant.clear();
      for (const [k, v] of newOcc) occupant.set(k, v);
    }

    sendNurse(slotRow.bed, lastNurseSlot == null || Math.abs(st.slot - lastNurseSlot) > 5);
    lastNurseSlot = st.slot;
    lamp.position.copy(bayPosition(slotRow.bed)).setY(3.2);
    lamp.intensity = 0;
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
      const hit = state === "pick" && st.showKey && (slotRow.review_class === "early6" || slotRow.review_class === "early");
      if (hit) { state = "hit"; color = COLOR.hit; }
      b.state = state;
      b.beamMat.color.copy(hit ? COLOR.hit : COLOR.pick);
      if (state === "pick" || state === "hit") lamp.color.copy(hit ? COLOR.hit : COLOR.pick);
      b.ringMat.color.copy(color).multiplyScalar(state === "snooze" || state === "empty" ? 1 : GLOW);
      b.ringMat.opacity = state === "snooze" || state === "empty" ? 0.55 : 0.95;
      b.ring.scale.setScalar(1);
      b.padMat.color.copy(color);
      b.padMat.opacity = state === "pick" || state === "hit" ? 0.3 : 0.14;
      b.beam.visible = state === "pick" || state === "hit";
      b.occupied = !!r;
      b.patientGroup.visible = !!r && !b.arriving;
      b.blanketMat.color.set(state === "snooze" ? "#7f93b3" : "#3f6fb5");
      drawMonitor(b.monitor, bed, r, pat, color);

      const cls = ["bed-label"];
      if (state === "pick") cls.push("pick");
      if (state === "hit") cls.push("hit");
      if (state === "snooze") cls.push("snooze");
      if (st.selectedBed === bed) cls.push("sel");
      b.el.className = cls.join(" ");
      let line = "empty";
      if (r) line = r.picked ? "check now" : r.snoozed ? `checked ${r.hours_since_check} h ago` : `${ordinal(r.rank)} in line · risk ${r.percentile}`;
      let extra = "";
      if (r && r.picked && st.showKey) {
        const c = slotRow.review_class, lead = Math.round(slotRow.lead_hours ?? 0);
        if (c === "early6" || c === "early") extra = `<b class='hitbig'>✓ SEPSIS FLAGGED EARLY</b><small class='ok keep'>${lead} hour${lead === 1 ? "" : "s"} before it was recorded</small>`;
        else if (c === "false") extra = "<small class='line'>false alarm</small>";
        else if (c === "late") extra = "<small class='line'>checked too late</small>";
      }
      if (r && r.manual) extra += "<small class='line entered-tag'>entered patient</small>";
      if (bed === missBed) extra += "<small class='warn'>missed</small>";
      b.el.innerHTML = `<span class='long'>Bed </span>${bed}<small class='line'>${line}</small>${extra}`;
    }
  }

  return { update, bayPosition };
}
