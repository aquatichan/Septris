// The check-in lobby and elevator to the right of the ward, plus the moving
// parts that use them: elevator doors, patient transfers (a gurney rolling
// between a bed and the elevator) and the opening camera path.
import * as THREE from "three";
import { bayPosition } from "./beds.js";

export const LOBBY = { x0: 22, x1: 36, halfZ: 8, door: 3.5, lift: 1.7 };
const ELEVATOR = new THREE.Vector3(37.6, 0, 0);

function sign(text, w = 4, h = 0.7, color = "#4fb3ff") {
  const c = document.createElement("canvas");
  c.width = 512; c.height = Math.round((512 * h) / w);
  const g = c.getContext("2d");
  g.fillStyle = "#0d1d24";
  g.fillRect(0, 0, c.width, c.height);
  g.fillStyle = color;
  g.font = `700 ${Math.round(c.height * 0.56)}px "Space Grotesk", "IBM Plex Sans", sans-serif`;
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillText(text, c.width / 2, c.height / 2 + 2);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex, toneMapped: false }));
}

function person(color) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.24, 0.85, 6, 14), new THREE.MeshStandardMaterial({ color, roughness: 0.8 }));
  body.position.y = 0.9;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.17, 20, 16), new THREE.MeshStandardMaterial({ color: "#c99a7a", roughness: 0.7 }));
  head.position.y = 1.72;
  body.castShadow = head.castShadow = true;
  g.add(body, head);
  return g;
}

function gurney() {
  const g = new THREE.Group();
  const frame = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.12, 2.0), new THREE.MeshStandardMaterial({ color: "#c9d3d6", metalness: 0.6, roughness: 0.35 }));
  frame.position.y = 0.7;
  const legs = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.55, 1.6), new THREE.MeshStandardMaterial({ color: "#56666b", metalness: 0.5, roughness: 0.4 }));
  legs.position.y = 0.35;
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.28, 1.0, 6, 14), new THREE.MeshStandardMaterial({ color: "#6f8f99", roughness: 0.9 }));
  body.rotation.x = Math.PI / 2;
  body.scale.set(1.1, 1, 0.55);
  body.position.set(0, 0.95, 0.15);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.16, 16, 12), new THREE.MeshStandardMaterial({ color: "#c99a7a", roughness: 0.7 }));
  head.position.set(0, 1.02, -0.68);
  const porter = person("#7b8fd4");
  porter.position.set(0, 0, 1.45);
  for (const m of [frame, legs, body, head]) m.castShadow = true;
  g.add(frame, legs, body, head, porter);
  return g;
}

export function createLobby(world) {
  const { scene } = world;
  const wallMat = new THREE.MeshStandardMaterial({ color: "#22343b", roughness: 0.85 });
  const box = (w, h, d, x, y, z, mat = wallMat) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    m.position.set(x, y, z);
    m.castShadow = m.receiveShadow = true;
    scene.add(m);
    return m;
  };
  const W = LOBBY.x1 - LOBBY.x0, cx = (LOBBY.x0 + LOBBY.x1) / 2;

  // floor: a warmer tone than the ward so the two rooms read as different places
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(W, LOBBY.halfZ * 2), new THREE.MeshStandardMaterial({ color: "#26363a", roughness: 0.5, metalness: 0.05 }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(cx, 0.002, 0);
  floor.receiveShadow = true;
  scene.add(floor);
  const lane = new THREE.Mesh(new THREE.PlaneGeometry(W, 2.4), new THREE.MeshBasicMaterial({ color: "#2f5d6b", transparent: true, opacity: 0.35 }));
  lane.rotation.x = -Math.PI / 2;
  lane.position.set(cx, 0.006, 0);
  scene.add(lane);

  // walls: back wall, and the far wall with the elevator opening
  box(W, 3.2, 0.25, cx, 1.6, -LOBBY.halfZ);
  const seg = (LOBBY.halfZ - LOBBY.lift) ;
  box(0.25, 3.2, seg, LOBBY.x1, 1.6, -(LOBBY.lift + seg / 2));
  box(0.25, 3.2, seg, LOBBY.x1, 1.6, LOBBY.lift + seg / 2);
  box(0.25, 0.7, LOBBY.lift * 2, LOBBY.x1, 2.85, 0);

  // elevator cab behind the opening, with a lit ceiling
  const cabMat = new THREE.MeshStandardMaterial({ color: "#8fa3a8", metalness: 0.7, roughness: 0.35 });
  box(3.4, 0.1, 3.4, LOBBY.x1 + 1.8, 0.0, 0, cabMat);
  box(0.15, 2.6, 3.4, LOBBY.x1 + 3.5, 1.3, 0, cabMat);
  box(3.4, 2.6, 0.15, LOBBY.x1 + 1.8, 1.3, -1.7, cabMat);
  box(3.4, 2.6, 0.15, LOBBY.x1 + 1.8, 1.3, 1.7, cabMat);
  const cabLight = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 2.6), new THREE.MeshBasicMaterial({ color: "#fff3d6", toneMapped: false }));
  cabLight.rotation.x = Math.PI / 2;
  cabLight.position.set(LOBBY.x1 + 1.8, 2.58, 0);
  scene.add(cabLight);
  const cabGlow = new THREE.PointLight("#ffe9c0", 14, 12, 1.6);
  cabGlow.position.set(LOBBY.x1 + 1.5, 2.2, 0);
  scene.add(cabGlow);

  // sliding doors
  const doorMat = new THREE.MeshStandardMaterial({ color: "#b9c7cb", metalness: 0.85, roughness: 0.25 });
  const doors = [-1, 1].map((s) => {
    const d = box(0.08, 2.5, LOBBY.lift, LOBBY.x1 - 0.02, 1.25, (s * LOBBY.lift) / 2, doorMat);
    d.userData.side = s;
    return d;
  });
  const lamp = new THREE.Mesh(new THREE.CircleGeometry(0.12, 20), new THREE.MeshBasicMaterial({ color: "#3ccf8e", toneMapped: false }));
  lamp.rotation.y = -Math.PI / 2;
  lamp.position.set(LOBBY.x1 - 0.15, 2.85, 0);
  scene.add(lamp);
  const liftSign = sign("ELEVATOR", 2.6, 0.42, "#cfe0e4");
  liftSign.rotation.y = -Math.PI / 2;
  liftSign.position.set(LOBBY.x1 - 0.14, 3.02, 0);
  scene.add(liftSign);

  // check-in desk against the back wall, with a clerk and a sign
  const desk = box(6, 1.1, 1.3, cx - 0.5, 0.55, -5.6, new THREE.MeshStandardMaterial({ color: "#aebcc0", roughness: 0.5 }));
  box(6.3, 0.08, 1.6, desk.position.x, 1.14, -5.6, new THREE.MeshStandardMaterial({ color: "#3a5a64" }));
  const deskSign = sign("CHECK-IN", 4.2, 0.72);
  deskSign.position.set(desk.position.x, 2.45, -LOBBY.halfZ + 0.14);
  scene.add(deskSign);
  const front = sign("ICU ADMISSIONS", 3.6, 0.4, "#cfe0e4");
  front.position.set(desk.position.x, 0.6, -4.94);
  scene.add(front);
  const clerk = person("#d08a5b");
  clerk.position.set(desk.position.x, 0, -6.7);
  scene.add(clerk);
  const screen = box(0.9, 0.55, 0.06, desk.position.x + 1.6, 1.5, -5.8, new THREE.MeshStandardMaterial({ color: "#0d1d24", emissive: "#2a87c7", emissiveIntensity: 0.6 }));
  screen.rotation.y = 0.3;
  // waiting chairs along the open side
  for (let i = 0; i < 4; i++) {
    box(0.7, 0.45, 0.7, LOBBY.x0 + 2.2 + i * 1.1, 0.23, 6.6, new THREE.MeshStandardMaterial({ color: "#35606e", roughness: 0.8 }));
    box(0.7, 0.6, 0.1, LOBBY.x0 + 2.2 + i * 1.1, 0.75, 6.95, new THREE.MeshStandardMaterial({ color: "#35606e", roughness: 0.8 }));
  }
  // "ICU" sign over the doorway into the ward
  const ward = sign("ICU · 20 BEDS", 3.4, 0.5, "#cfe0e4");
  ward.rotation.y = Math.PI / 2;
  ward.position.set(LOBBY.x0 + 0.16, 2.75, 0);
  scene.add(ward);
  box(0.25, 0.7, LOBBY.door * 2, LOBBY.x0, 2.85, 0);

  // ---- doors
  let doorTarget = 0, doorNow = 0;
  const transfers = [];
  world.onFrame((dt) => {
    const want = transfers.length ? 1 : doorTarget;
    doorNow += Math.sign(want - doorNow) * Math.min(Math.abs(want - doorNow), dt * 1.6);
    for (const d of doors) d.position.z = d.userData.side * (LOBBY.lift / 2 + doorNow * (LOBBY.lift - 0.1));
    lamp.material.color.set(doorNow > 0.05 ? "#f5b84b" : "#3ccf8e");

    for (let i = transfers.length - 1; i >= 0; i--) {
      const t = transfers[i];
      t.wait -= dt;
      if (t.wait > 0) continue;
      t.mesh.visible = true;
      t.s = Math.min(t.len, t.s + dt * 11);
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
