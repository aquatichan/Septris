// The check-in lobby and elevator to the right of the ward, plus the moving
// parts that use them: elevator doors and floor display, patient transfers
// (a porter wheeling a gurney between a bed and the elevator) and seated
// visitors. The lobby ceiling and front wall are one-sided, like the ward's.
import * as THREE from "three";
import { bayPosition } from "./beds.js";
import { fixture, flicker, officeChair, floorMaterial, floorReflections, alarmBell } from "./world.js";
import { makePerson } from "./people.js";
import { ceilingTiles, wood, brushedSteel, buttonPanel, signTexture, panelWall, exitSign, noticeBoard, wallLettering } from "./textures.js";

export const LOBBY = { x0: 22, x1: 36, halfZ: 8, door: 3.5, lift: 1.7 };
const ELEVATOR = new THREE.Vector3(37.9, 0, 0);
const H = 3.0;

function sign(text, w = 4, h = 0.7, opts = {}) {
  return new THREE.Mesh(new THREE.PlaneGeometry(w, h),
    new THREE.MeshBasicMaterial({ map: signTexture(text, { w: 512, h: Math.round((512 * h) / w), ...opts }), toneMapped: false }));
}

function gurney() {
  const g = new THREE.Group();
  const steel = new THREE.MeshStandardMaterial({ color: "#b9c2c6", metalness: 0.7, roughness: 0.3 });
  const frame = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.08, 1.95), steel);
  frame.position.y = 0.72;
  const pad = new THREE.Mesh(new THREE.BoxGeometry(0.74, 0.1, 1.9), new THREE.MeshStandardMaterial({ color: "#f4f6f6", roughness: 0.85 }));
  pad.position.y = 0.8;
  g.add(frame, pad);
  for (const [x, z] of [[-0.33, -0.8], [0.33, -0.8], [-0.33, 0.8], [0.33, 0.8]]) {
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.62, 6), steel);
    leg.position.set(x, 0.39, z);
    const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.04, 10), new THREE.MeshStandardMaterial({ color: "#2a3033" }));
    wheel.rotation.z = Math.PI / 2;
    wheel.position.set(x, 0.07, z);
    g.add(leg, wheel);
  }
  const blanket = new THREE.MeshStandardMaterial({ color: "#e9eef0", roughness: 0.95 });
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.2, 1.0, 6, 14), blanket);
  body.rotation.x = Math.PI / 2;
  body.scale.set(1.2, 1, 0.6);
  body.position.set(0, 0.93, 0.15);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 12), new THREE.MeshStandardMaterial({ color: "#c99a7a", roughness: 0.7 }));
  head.position.set(0, 0.98, -0.72);
  g.add(body, head);
  const porter = makePerson({ color: "#5e6fb8" });
  porter.group.position.set(0, 0, 1.5);
  porter.group.rotation.y = Math.PI; // pushing: faces the way the gurney travels (-z local)
  porter.armL.rotation.x = porter.armR.rotation.x = -0.7;
  g.add(porter.group);
  g.traverse((m) => { if (m.isMesh) m.castShadow = true; });
  g.userData.porter = porter;
  return g;
}

export function createLobby(world) {
  const { scene } = world;
  const W = LOBBY.x1 - LOBBY.x0, cx = (LOBBY.x0 + LOBBY.x1) / 2, Z = LOBBY.halfZ;
  const box = (w, h, d, x, y, z, mat, shadow = true) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    m.position.set(x, y, z);
    m.castShadow = shadow; m.receiveShadow = true;
    scene.add(m);
    return m;
  };
  const paint = (len) => new THREE.MeshStandardMaterial({ map: panelWall(len / 2.4, { dado: "#7f9e9d" }), roughness: 0.55 });
  const oak = new THREE.MeshStandardMaterial({ map: wood(), roughness: 0.6 });

  // floor, ceiling (one-sided), walls
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(W, Z * 2), floorMaterial(W / 4, (Z * 2) / 4, "#628f90"));
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(cx, 0.002, 0);
  floor.receiveShadow = true;
  scene.add(floor);
  const ceiling = new THREE.Mesh(new THREE.PlaneGeometry(W, Z * 2), new THREE.MeshStandardMaterial({ map: ceilingTiles(W / 1.2, (Z * 2) / 1.2), roughness: 1 }));
  ceiling.rotation.x = Math.PI / 2;
  ceiling.position.set(cx, H, 0);
  scene.add(ceiling);
  box(W, H, 0.25, cx, H / 2, -Z - 0.125, paint(W));
  const seg = Z - LOBBY.lift;
  for (const s of [-1, 1]) box(0.25, H, seg, LOBBY.x1 + 0.125, H / 2, s * (LOBBY.lift + seg / 2), paint(seg));
  box(0.25, H - 2.4, LOBBY.lift * 2, LOBBY.x1 + 0.125, 2.4 + (H - 2.4) / 2, 0, paint(3));
  const front = new THREE.Mesh(new THREE.PlaneGeometry(W, H), paint(W));
  front.rotation.y = Math.PI;
  front.position.set(cx, H / 2, Z);
  scene.add(front);
  // lights; the one by the elevator has a failing tube
  fixture(scene, cx - 3, -2.5, { len: 2 });
  fixture(scene, cx - 3, 3.5, { len: 2 });
  const tired = new THREE.PointLight("#f4f8ff", 8, 9, 1.8);
  tired.position.set(cx + 3.5, H - 0.4, 2.5);
  scene.add(tired);
  flicker(world, fixture(scene, cx + 3.5, 2.5, { len: 2 }), tired, 8);
  fixture(scene, cx + 3.5, -3, { len: 2 });
  floorReflections(scene, [[cx - 3, -2.5], [cx - 3, 3.5], [cx + 3.5, 2.5], [cx + 3.5, -3]], 2);
  // grey-teal hand rail on the dado line
  const railMat = new THREE.MeshStandardMaterial({ color: "#6d8b8a", roughness: 0.4 });
  box(W, 0.14, 0.08, cx, 0.92, -Z + 0.04, railMat, false);

  // elevator: steel cab seen from inside during the opening shot
  const steelTex = brushedSteel(3);
  const cabMat = new THREE.MeshStandardMaterial({ map: steelTex, metalness: 0.75, roughness: 0.38, side: THREE.DoubleSide });
  const cabX = LOBBY.x1 + 0.25, cabD = 3.6, cabW = LOBBY.lift * 2 + 0.6;
  box(cabD, 0.08, cabW, cabX + cabD / 2, 0.0, 0, new THREE.MeshStandardMaterial({ color: "#3b4144", roughness: 0.5 }), false);
  box(0.1, 2.7, cabW, cabX + cabD, 1.35, 0, cabMat);
  for (const s of [-1, 1]) box(cabD, 2.7, 0.1, cabX + cabD / 2, 1.35, s * (cabW / 2), cabMat);
  box(cabD, 0.1, cabW, cabX + cabD / 2, 2.7, 0, cabMat, false);
  const rail = new THREE.MeshStandardMaterial({ color: "#d5dadc", metalness: 0.9, roughness: 0.2 });
  for (const s of [-1, 1]) box(cabD - 0.6, 0.05, 0.05, cabX + cabD / 2, 0.95, s * (cabW / 2 - 0.12), rail, false);
  const cabLight = new THREE.Mesh(new THREE.PlaneGeometry(cabD - 1, cabW - 1.2), new THREE.MeshBasicMaterial({ color: new THREE.Color(2, 1.95, 1.8), toneMapped: false }));
  cabLight.rotation.x = Math.PI / 2;
  cabLight.position.set(cabX + cabD / 2, 2.64, 0);
  scene.add(cabLight);
  const cabGlow = new THREE.PointLight("#fff1d8", 3.2, 9, 1.4);
  cabGlow.position.set(cabX + cabD / 2, 2.2, 0);
  scene.add(cabGlow);
  // the inside of the door wall: dark operating panel with floor buttons, and a floor display
  const jamb = new THREE.MeshStandardMaterial({ color: "#17191b", roughness: 0.45, metalness: 0.3 });
  for (const s of [-1, 1]) {
    const p = new THREE.Mesh(new THREE.PlaneGeometry(0.3, 2.7), jamb);
    p.rotation.y = Math.PI / 2;
    p.position.set(cabX + 0.01, 1.35, s * (LOBBY.lift + 0.15));
    scene.add(p);
  }
  const buttons = new THREE.Mesh(new THREE.PlaneGeometry(0.26, 0.52), new THREE.MeshBasicMaterial({ map: buttonPanel(3), toneMapped: false }));
  buttons.rotation.y = Math.PI / 2;
  buttons.position.set(cabX + 0.02, 1.25, -(LOBBY.lift + 0.15));
  scene.add(buttons);
  const displayCanvas = document.createElement("canvas");
  displayCanvas.width = 256; displayCanvas.height = 96;
  const displayTex = new THREE.CanvasTexture(displayCanvas);
  displayTex.colorSpace = THREE.SRGBColorSpace;
  const drawDisplay = (text) => {
    const g = displayCanvas.getContext("2d");
    g.fillStyle = "#050607"; g.fillRect(0, 0, 256, 96);
    g.fillStyle = "#ff9f2e"; g.font = "700 64px 'IBM Plex Mono', monospace"; g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText(text, 128, 52);
    displayTex.needsUpdate = true;
  };
  drawDisplay("3");
  const lintel = new THREE.Mesh(new THREE.PlaneGeometry(LOBBY.lift * 2 + 0.6, 0.3), jamb);
  lintel.rotation.y = Math.PI / 2;
  lintel.position.set(cabX + 0.01, 2.55, 0);
  const display = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.19), new THREE.MeshBasicMaterial({ map: displayTex, toneMapped: false }));
  display.rotation.y = Math.PI / 2;
  display.position.set(cabX + 0.02, 2.55, 0);
  scene.add(lintel, display);

  // sliding doors (brushed steel on both faces)
  const doorMat = new THREE.MeshStandardMaterial({ map: brushedSteel(2), color: "#9fb7b8", metalness: 0.55, roughness: 0.36 });
  const logoTex = new THREE.TextureLoader().load("assets/septris-logo.png", (t) => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; });
  const stickerMat = new THREE.MeshStandardMaterial({ map: logoTex, transparent: true, roughness: 0.4, metalness: 0.1, polygonOffset: true, polygonOffsetFactor: -2 });
  const halfSticker = (leftHalf) => {
    const g = new THREE.PlaneGeometry(1.25, 0.29);
    const uv = g.attributes.uv;
    for (let i = 0; i < uv.count; i++) uv.setX(i, uv.getX(i) * 0.5 + (leftHalf ? 0 : 0.5));
    return new THREE.Mesh(g, stickerMat);
  };
  const doors = [-1, 1].map((s) => {
    const d = box(0.07, 2.4, LOBBY.lift, LOBBY.x1 + 0.12, 1.2, (s * LOBBY.lift) / 2, doorMat);
    d.userData.side = s;
    // lobby face (-x): the left half of the logo sits on the -z leaf
    const out = halfSticker(s < 0);
    out.rotation.y = -Math.PI / 2;
    out.position.set(-0.037, 0.42, -s * (LOBBY.lift / 2 - 0.625));
    // cab face (+x): seen from inside, left is +z
    const inn = halfSticker(s > 0);
    inn.rotation.y = Math.PI / 2;
    inn.position.set(0.037, 0.42, -s * (LOBBY.lift / 2 - 0.625));
    d.add(out, inn);
    return d;
  });
  // painted surround with a floor number plate, like the reference lobby
  const surround = new THREE.MeshStandardMaterial({ color: "#5f7b7c", roughness: 0.45, metalness: 0.2 });
  for (const s2 of [-1, 1]) box(0.1, 2.55, 0.14, LOBBY.x1 - 0.03, 1.275, s2 * (LOBBY.lift + 0.07), surround);
  box(0.1, 0.5, LOBBY.lift * 2 + 0.28, LOBBY.x1 - 0.03, 2.8, 0, surround);
  const plate = sign("3", 0.45, 0.16, { bg: "#c9d3d4", fg: "#26343a" });
  plate.rotation.y = -Math.PI / 2;
  plate.position.set(LOBBY.x1 - 0.085, 2.8, 0.55);
  scene.add(plate);
  // wall lettering and lift sign to the right of the doors
  const letters = new THREE.Mesh(new THREE.PlaneGeometry(3.6, 1.1), new THREE.MeshBasicMaterial({ map: wallLettering(["THIRD FLOOR", "INTENSIVE CARE"]), transparent: true, color: new THREE.Color(0.9, 0.9, 0.9) }));
  letters.rotation.y = -Math.PI / 2;
  letters.position.set(LOBBY.x1 - 0.01, 1.95, 4.55);
  scene.add(letters);
  const callBtn = box(0.03, 0.26, 0.1, LOBBY.x1 - 0.015, 1.15, 2.2, new THREE.MeshStandardMaterial({ color: "#b9c4c6", metalness: 0.8, roughness: 0.25 }), false);
  callBtn.castShadow = false;
  const exit = new THREE.Mesh(new THREE.PlaneGeometry(0.75, 0.28), new THREE.MeshBasicMaterial({ map: exitSign(), toneMapped: false, color: new THREE.Color(1.3, 1.3, 1.3) }));
  exit.rotation.y = -Math.PI / 2;
  exit.position.set(LOBBY.x1 - 0.02, 2.62, -4.5);
  scene.add(exit);
  // notice board and internal window on the back wall, alarm bells
  const board = new THREE.Mesh(new THREE.BoxGeometry(1.0, 1.25, 0.04), [0, 1, 2, 3, 4, 5].map((i) => i === 4 ? new THREE.MeshStandardMaterial({ map: noticeBoard(2), roughness: 0.6 }) : new THREE.MeshStandardMaterial({ color: "#c3cbcd", metalness: 0.4, roughness: 0.4 })));
  board.position.set(LOBBY.x0 + 1.4, 1.75, -Z + 0.03);
  scene.add(board);
  const pane = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 1.0), new THREE.MeshStandardMaterial({ color: "#9fb5bb", metalness: 0.9, roughness: 0.08 }));
  pane.position.set(LOBBY.x1 - 1.6, 1.75, -Z + 0.02);
  const paneFrame = new THREE.Mesh(new THREE.BoxGeometry(1.75, 1.15, 0.05), new THREE.MeshStandardMaterial({ color: "#c3cbcd", metalness: 0.4, roughness: 0.4 }));
  paneFrame.position.set(LOBBY.x1 - 1.6, 1.75, -Z + 0.005);
  scene.add(paneFrame, pane);
  alarmBell(scene, LOBBY.x1 - 0.02, 2.5, -2.4, -Math.PI / 2);
  const lamp = new THREE.Mesh(new THREE.CircleGeometry(0.1, 20), new THREE.MeshBasicMaterial({ color: "#3ccf8e", toneMapped: false }));
  lamp.rotation.y = -Math.PI / 2;
  lamp.position.set(LOBBY.x1 - 0.085, 2.8, -0.55);
  scene.add(lamp);
  const liftSign = sign("LIFT", 0.7, 0.24, { bg: "#dde3e4", fg: "#26343a" });
  liftSign.rotation.y = -Math.PI / 2;
  liftSign.position.set(LOBBY.x1 - 0.02, 2.62, -2.6);
  scene.add(liftSign);

  // check-in desk against the back wall: oak front, white counter, screen, clerk, sign
  const dx = cx - 0.5;
  box(6, 1.05, 0.9, dx, 0.525, -5.3, oak);
  box(6.2, 0.06, 1.15, dx, 1.08, -5.3, new THREE.MeshStandardMaterial({ color: "#eef1f1", roughness: 0.35 }));
  const deskSign = sign("CHECK-IN", 4.2, 0.72, { bg: "#16384a", fg: "#ffffff" });
  deskSign.position.set(dx, 2.3, -Z + 0.02);
  scene.add(deskSign);
  const frontSign = sign("ICU ADMISSIONS", 3.4, 0.36, { bg: "#16384a", fg: "#dbe9ef" });
  frontSign.position.set(dx, 0.62, -4.84);
  scene.add(frontSign);
  const screen = box(0.8, 0.5, 0.05, dx + 1.4, 1.42, -5.45, new THREE.MeshStandardMaterial({ color: "#0d1d24", emissive: "#2a87c7", emissiveIntensity: 0.9 }), false);
  screen.rotation.y = Math.PI + 0.25;
  officeChair(scene, dx - 0.2, -6.7, 0);
  const clerk = makePerson({ outfit: "casual", color: "#b5653f", seed: 0.62 });
  clerk.sit();
  clerk.group.position.set(dx - 0.2, 0, -6.65);
  scene.add(clerk.group);

  // waiting area: a row of seats along the open side, two visitors
  const seatMat = new THREE.MeshStandardMaterial({ color: "#5f9a86", roughness: 0.7 });
  const chrome = new THREE.MeshStandardMaterial({ color: "#d7dde0", metalness: 0.95, roughness: 0.18 });
  const tube = (pts) => {
    const m = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts.map((p) => new THREE.Vector3(...p)), false, "catmullrom", 0.05), 24, 0.016, 6), chrome);
    m.castShadow = true; scene.add(m);
  };
  for (let i = 0; i < 5; i++) {
    const x = LOBBY.x0 + 2.2 + i * 0.72;
    const seat = box(0.6, 0.09, 0.56, x, 0.47, 6.5, seatMat);
    const back = box(0.6, 0.56, 0.08, x, 0.8, 6.84, seatMat);
    back.rotation.x = -0.12;
    for (const sx of [-0.27, 0.27]) tube([[x + sx, 0.42, 6.22], [x + sx, 0.02, 6.25], [x + sx, 0.02, 6.86], [x + sx, 0.45, 6.82], [x + sx, 1.05, 6.92]]);
  }
  const visitors = [];
  for (const [i, col] of [[0, "#8a6d4f"], [3, "#55708a"]]) {
    const v = makePerson({ outfit: "casual", color: col, seed: 0.2 + i * 0.17 });
    v.sit();
    v.group.position.set(LOBBY.x0 + 2.2 + i * 0.72, 0, 6.45);
    v.group.rotation.y = Math.PI;
    scene.add(v.group);
    visitors.push(v);
  }
  // sign over the doorway into the ward
  const ward = sign("INTENSIVE CARE · 20 BEDS", 4.6, 0.42, { bg: "#16384a", fg: "#ffffff" });
  ward.rotation.y = Math.PI / 2;
  ward.position.set(LOBBY.x0 + 0.14, 2.7, 0);
  scene.add(ward);

  world.onFrame((dt, t) => {
    clerk.armL.rotation.x = -0.45 + Math.sin(t * 6) * 0.04; clerk.armL.userData.elbow.rotation.x = -1.15 + Math.sin(t * 9) * 0.06;
    clerk.armR.rotation.x = -0.45 + Math.cos(t * 7) * 0.04; clerk.armR.userData.elbow.rotation.x = -1.15 + Math.cos(t * 8) * 0.06;
    clerk.head.rotation.y = Math.sin(t * 0.3) * 0.4;
    for (const [i, v] of visitors.entries()) v.head.rotation.y = Math.sin(t * 0.21 + i * 2) * 0.5;
  });

  let doorTarget = 0, doorNow = 0, doorsWereOpen = false;
  const transfers = [];
  world.onFrame((dt) => {
    const want = transfers.length ? 1 : doorTarget;
    doorNow += Math.sign(want - doorNow) * Math.min(Math.abs(want - doorNow), dt * 1.6);
    for (const d of doors) d.position.z = d.userData.side * (LOBBY.lift / 2 + doorNow * (LOBBY.lift - 0.1));
    lamp.material.color.set(doorNow > 0.05 ? "#f5b84b" : "#3ccf8e");
    if ((doorNow > 0.02) !== doorsWereOpen) { doorsWereOpen = doorNow > 0.02; world.onDoors?.(doorsWereOpen); }

    for (let i = transfers.length - 1; i >= 0; i--) {
      const t = transfers[i];
      t.wait -= dt;
      if (t.wait > 0) continue;
      t.mesh.visible = true;
      t.s = Math.min(t.len, t.s + dt * 6.5);
      t.mesh.userData.porter.walk(t.s * 4.6, 1);
      for (const a of [t.mesh.userData.porter.armL, t.mesh.userData.porter.armR]) { a.rotation.x = -0.75; a.userData.elbow.rotation.x = -0.7; }
      const p = t.curve.getPointAt(t.s / t.len);
      const q = t.curve.getPointAt(Math.min(1, t.s / t.len + 0.01));
      t.mesh.position.copy(p);
      if (q.distanceToSquared(p) > 1e-6) t.mesh.rotation.y = Math.atan2(q.x - p.x, q.z - p.z) + Math.PI;
      if (t.s >= t.len) {
        scene.remove(t.mesh);
        transfers.splice(i, 1);
        t.done?.();
      }
    }
  });

  function route(bed, leaving) {
    const b = bayPosition(bed);
    const laneZ = b.z < 0 ? -2.3 : 2.3;
    const pts = [
      new THREE.Vector3(b.x, 0, b.z + (b.z < 0 ? 2.6 : -2.6)),
      new THREE.Vector3(b.x + 1.2, 0, laneZ),
      new THREE.Vector3(LOBBY.x0 - 1, 0, laneZ * 0.8),
      new THREE.Vector3(LOBBY.x0 + 4, 0, leaving ? 0.6 : -2.2), // arrivals pass the check-in desk
      new THREE.Vector3(LOBBY.x1 - 2.5, 0, 0),
      ELEVATOR.clone(),
    ];
    return new THREE.CatmullRomCurve3(leaving ? pts : pts.reverse(), false, "catmullrom", 0.2);
  }

  return {
    setDoors(open) { doorTarget = open ? 1 : 0; },
    setDisplay: drawDisplay,
    /** One patient leaves a bed and (optionally) a new one arrives. done() fires when the new patient reaches the bed. */
    transfer(bed, { leaves, arrives, done }) {
      const add = (leaving, wait, cb) => {
        const curve = route(bed, leaving);
        const mesh = gurney();
        mesh.visible = false;
        scene.add(mesh);
        transfers.push({ mesh, curve, len: curve.getLength(), s: 0, wait, done: cb });
      };
      if (leaves) add(true, 0, arrives ? null : done);
      if (arrives) add(false, leaves ? 0.9 : 0.2, done);
      else if (!leaves) done?.();
    },
    cancel() {
      for (const t of transfers) { scene.remove(t.mesh); t.done?.(); }
      transfers.length = 0;
    },
    busy: () => transfers.length > 0,
  };
}
