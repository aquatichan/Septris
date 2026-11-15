// People: a simple jointed figure with a walk cycle, plus the ward's
// background staff who wander between beds, the station and the lobby.
// Nobody here carries data: the only "meaningful" person is the charge nurse
// in beds.js, who walks to the bed Septris picks.
import * as THREE from "three";

const SKIN = ["#e8c4a6", "#c99a7a", "#a8765a", "#7d5540", "#f0d2b8"];
const HAIR = ["#2b211c", "#4a3426", "#151515", "#7a5a3a", "#b9b3ac"];
const mat = (color, rough = 0.8) => new THREE.MeshStandardMaterial({ color, roughness: rough });

/**
 * Builds a person about 1.72 m tall, facing +z.
 * outfit: "scrubs" (one colour), "coat" (white coat over dark trousers) or "casual".
 * Returns { group, walk(phase, amount), sit(), idle(t) }.
 */
export function makePerson({ outfit = "scrubs", color = "#2f9aa8", seed = Math.random() } = {}) {
  const pick = (arr) => arr[Math.floor(seed * 997) % arr.length];
  const skin = mat(pick(SKIN), 0.7), hair = mat(pick(HAIR), 0.9);
  const top = mat(outfit === "coat" ? "#f2f4f5" : color);
  const bottom = mat(outfit === "scrubs" ? color : outfit === "coat" ? "#39424d" : "#4b5563");
  const shoe = mat("#f1f1f1", 0.6);
  const g = new THREE.Group();
  const body = new THREE.Group(); // everything above the feet, so the whole figure can bob
  g.add(body);

  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.17, 0.36, 4, 12), top);
  torso.position.y = 1.2;
  torso.scale.set(1.15, 1, 0.75);
  const hips = new THREE.Mesh(new THREE.CapsuleGeometry(0.16, 0.1, 4, 10), bottom);
  hips.position.y = 0.93;
  hips.scale.set(1.12, 1, 0.78);
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.06, 0.1, 8), skin);
  neck.position.y = 1.5;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.115, 18, 14), skin);
  head.position.y = 1.62;
  head.scale.set(0.92, 1.08, 1);
  const cap = new THREE.Mesh(new THREE.SphereGeometry(0.122, 18, 12, 0, Math.PI * 2, 0, Math.PI * 0.58), hair);
  cap.position.set(0, 1.635, -0.012);
  body.add(torso, hips, neck, head, cap);
  if (outfit === "coat") {
    const tail = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.42, 0.24), top);
    tail.position.y = 0.86;
    body.add(tail);
  }

  const limb = (len, r, material, endMat, endLen) => {
    const pivot = new THREE.Group();
    const seg = new THREE.Mesh(new THREE.CapsuleGeometry(r, len - 2 * r, 4, 8), material);
    seg.position.y = -len / 2;
    pivot.add(seg);
    if (endMat) {
      const end = new THREE.Mesh(new THREE.BoxGeometry(r * 2.1, r * 1.5, endLen), endMat);
      end.position.set(0, -len - r * 0.4, endLen * 0.22);
      pivot.add(end);
    }
    return pivot;
  };
  const legL = limb(0.82, 0.075, bottom, shoe, 0.24), legR = limb(0.82, 0.075, bottom, shoe, 0.24);
  legL.position.set(-0.09, 0.9, 0); legR.position.set(0.09, 0.9, 0);
  const armL = limb(0.58, 0.05, top, skin, 0.08), armR = limb(0.58, 0.05, top, skin, 0.08);
  armL.position.set(-0.235, 1.42, 0); armR.position.set(0.235, 1.42, 0);
  armL.rotation.z = -0.07; armR.rotation.z = 0.07;
  body.add(legL, legR, armL, armR);
  // lower legs used only when seated (the walking leg is one straight piece)
  const shins = [-0.09, 0.09].map((x) => {
    const s = new THREE.Group();
    const seg = new THREE.Mesh(new THREE.CapsuleGeometry(0.068, 0.3, 4, 8), bottom);
    seg.position.y = -0.2;
    const foot = new THREE.Mesh(new THREE.BoxGeometry(0.15, 0.1, 0.24), shoe);
    foot.position.set(0, -0.42, 0.06);
    s.add(seg, foot);
    s.position.set(x, 0.9, 0.42);
    s.visible = false;
    body.add(s);
    return s;
  });
  g.traverse((m) => { if (m.isMesh) m.castShadow = true; });

  return {
    group: g, body, armL, armR, legL, legR, head,
    /** phase advances with distance walked; amount 0..1 blends between standing and full stride. */
    walk(phase, amount = 1) {
      const s = Math.sin(phase) * 0.55 * amount;
      legL.rotation.x = s; legR.rotation.x = -s;
      armL.rotation.x = -s * 0.8; armR.rotation.x = s * 0.8;
      body.position.y = Math.abs(Math.cos(phase)) * 0.025 * amount;
    },
    /** Seated pose on a chair of normal height. */
    sit() {
      legL.rotation.x = legR.rotation.x = -1.5;
      legL.scale.y = legR.scale.y = 0.52; // thigh only; the shins hang from the knee
      for (const s of shins) s.visible = true;
      body.position.y = -0.4;
      armL.rotation.x = armR.rotation.x = -0.9;
    },
    /** Standing still: slow weight shift and a little head movement. */
    idle(t, k = 1) {
      body.rotation.z = Math.sin(t * 0.7 + seed * 9) * 0.015 * k;
      head.rotation.y = Math.sin(t * 0.33 + seed * 20) * 0.35 * k;
      armL.rotation.x = armR.rotation.x = legL.rotation.x = legR.rotation.x = 0;
    },
  };
}

/** Moves a person along a list of points at walking pace. Call step(dt) each frame; returns true while moving. */
export function makeWalker(person, speed = 1.35) {
  let path = [], phase = 0;
  const pos = person.group.position;
  return {
    go(points) { path = points.map((p) => p.clone()); },
    get moving() { return path.length > 0; },
    step(dt) {
      if (!path.length) return false;
      const to = path[0];
      const dx = to.x - pos.x, dz = to.z - pos.z;
      const dist = Math.hypot(dx, dz);
      const stepLen = speed * dt;
      if (dist <= stepLen) { pos.x = to.x; pos.z = to.z; path.shift(); }
      else {
        pos.x += (dx / dist) * stepLen; pos.z += (dz / dist) * stepLen;
        const want = Math.atan2(dx, dz);
        let d = want - person.group.rotation.y;
        d = Math.atan2(Math.sin(d), Math.cos(d));
        person.group.rotation.y += d * Math.min(1, dt * 9);
      }
      phase += stepLen * 4.6;
      person.walk(phase, 1);
      if (!path.length) person.walk(0, 0);
      return true;
    },
  };
}

/** A route along the corridor lanes so walkers don't cut through beds or the station. */
export function corridorRoute(from, to) {
  const lane = (z) => (z < 0 ? -2.1 : 2.1);
  const V = (x, z) => new THREE.Vector3(x, 0, z);
  const pts = [];
  const inWard = (p) => p.x < 21.5;
  if (inWard(from) && Math.abs(from.z) > 3) pts.push(V(from.x, lane(from.z)));
  const a = pts.length ? pts[pts.length - 1] : from;
  if (inWard(a) !== inWard(to)) pts.push(V(21, lane(a.z) * 0.6), V(23.5, 0)); // through the doorway
  if (inWard(to) && Math.abs(to.z) > 3) {
    const l = lane(to.z);
    if (inWard(a) && Math.sign(a.z || l) !== Math.sign(l) && Math.abs((a.x + to.x) / 2) < 4.6) pts.push(V(a.x < 0 ? -5 : 5, 0)); // go round the station
    pts.push(V(to.x, l));
  }
  pts.push(V(to.x, to.z));
  return pts;
}

/**
 * Background staff: a few nurses and a doctor who walk to a random bed-side,
 * pause as if checking something, then move on; two who sit at the station.
 */
export function createStaff(world, bayPosition) {
  const { scene } = world;
  const SCRUBS = ["#2f9aa8", "#3d6fb6", "#8a4f7d", "#2e8b6f"];
  const spots = () => {
    const r = Math.random();
    if (r < 0.7) {
      const bed = 1 + Math.floor(Math.random() * 20), p = bayPosition(bed);
      return new THREE.Vector3(p.x + 1.25, 0, p.z + (p.z < 0 ? 1.0 : -1.0)); // beside the bed, opposite the charge nurse's spot
    }
    if (r < 0.88) return new THREE.Vector3(-3 + Math.random() * 6, 0, 2.0 + Math.random() * 0.4); // station counter
    return new THREE.Vector3(25 + Math.random() * 6, 0, -3.4 + Math.random() * 1.2); // check-in desk
  };
  const walkers = [];
  for (let i = 0; i < 4; i++) {
    const p = makePerson(i === 3 ? { outfit: "coat" } : { color: SCRUBS[i] });
    const start = spots();
    p.group.position.copy(start);
    scene.add(p.group);
    walkers.push({ p, w: makeWalker(p, 1.2 + Math.random() * 0.35), wait: 2 + Math.random() * 8 });
  }
  for (const [i, [x, z]] of (world.station?.seats || []).entries()) {
    const p = makePerson({ color: SCRUBS[(i + 1) % SCRUBS.length] });
    p.sit();
    p.group.position.set(x, 0, z - 0.05);
    p.group.rotation.y = Math.PI;
    scene.add(p.group);
    walkers.push({ p, seated: true });
  }
  world.onFrame((dt, t) => {
    for (const s of walkers) {
      if (s.seated) { // typing: small forearm movement, the odd glance up
        s.p.armL.rotation.x = -0.9 + Math.sin(t * 7 + s.p.group.position.x) * 0.05;
        s.p.armR.rotation.x = -0.9 + Math.cos(t * 6 + s.p.group.position.x) * 0.05;
        s.p.head.rotation.y = Math.sin(t * 0.25 + s.p.group.position.x) * 0.3;
        continue;
      }
      if (s.w.step(dt)) continue;
      s.p.idle(t);
      s.wait -= dt;
      if (s.wait <= 0) {
        s.w.go(corridorRoute(s.p.group.position, spots()));
        s.wait = 4 + Math.random() * 10;
      }
    }
  });
}
