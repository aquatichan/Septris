// People: a simple jointed figure with a walk cycle, plus the ward's
// background staff who wander between beds, the station and the lobby.
// Nobody here carries data: the only "meaningful" person is the charge nurse
// in beds.js, who walks to the bed Septris picks.
import * as THREE from "three";

const SKIN = ["#eac8ab", "#d2a487", "#b07c5d", "#8a5d43", "#f1d6c0", "#6e4632"];
const HAIR = ["#2b211c", "#4a3426", "#151515", "#7a5a3a", "#c9c2b8", "#a5683a"];
const mat = (color, rough = 0.75) => new THREE.MeshStandardMaterial({ color, roughness: rough });
const EYE = new THREE.MeshStandardMaterial({ color: "#1d1a18", roughness: 0.3 });
const LIP = new THREE.MeshStandardMaterial({ color: "#9a5a50", roughness: 0.6 });

// Shared, smooth body-part geometry. Every part is a lathe (a turned profile) so
// limbs taper like real ones (thigh to knee, calf bulge to ankle) instead of
// being plain cylinders. Profiles are [radius, height] pairs from bottom to top.
const lathe = (pts, seg = 16) => new THREE.LatheGeometry(pts.map(([r, y]) => new THREE.Vector2(r, y)), seg);
const GEO = {
  torso: lathe([[0, 1.0], [0.155, 1.0], [0.148, 1.08], [0.152, 1.18], [0.168, 1.28], [0.176, 1.36], [0.168, 1.42], [0.12, 1.47], [0.06, 1.49], [0, 1.49]], 20),
  pelvis: lathe([[0, 0.86], [0.11, 0.86], [0.16, 0.9], [0.168, 0.97], [0.158, 1.05], [0, 1.05]], 20),
  coat: lathe([[0, 0.6], [0.205, 0.6], [0.19, 0.8], [0.172, 1.0], [0.16, 1.1], [0.172, 1.28], [0.182, 1.36], [0.174, 1.42], [0.125, 1.47], [0.065, 1.5], [0, 1.5]], 20),
  thigh: lathe([[0, -0.44], [0.058, -0.44], [0.064, -0.36], [0.076, -0.2], [0.086, -0.06], [0.08, 0.02], [0, 0.04]]),
  shin: lathe([[0, -0.4], [0.04, -0.4], [0.044, -0.3], [0.058, -0.16], [0.06, -0.08], [0.056, 0], [0, 0.02]]),
  sleeve: lathe([[0, -0.17], [0.058, -0.17], [0.062, -0.08], [0.064, 0.0], [0.05, 0.04], [0, 0.05]]),
  longSleeve: lathe([[0, -0.29], [0.048, -0.29], [0.054, -0.15], [0.06, 0], [0.05, 0.04], [0, 0.05]]),
  upperArm: lathe([[0, -0.29], [0.036, -0.29], [0.042, -0.18], [0.046, -0.1], [0, -0.08]], 12),
  forearm: lathe([[0, -0.25], [0.028, -0.25], [0.034, -0.15], [0.041, -0.04], [0.036, 0.02], [0, 0.03]], 12),
  hand: new THREE.SphereGeometry(0.042, 12, 10),
  head: new THREE.SphereGeometry(0.104, 24, 20),
  jaw: new THREE.SphereGeometry(0.078, 18, 14),
  nose: new THREE.ConeGeometry(0.016, 0.04, 8),
  ear: new THREE.SphereGeometry(0.022, 10, 8),
  eye: new THREE.SphereGeometry(0.011, 8, 6),
  lid: new THREE.BoxGeometry(0.026, 0.004, 0.004),
  brow: new THREE.BoxGeometry(0.03, 0.006, 0.006),
  mouth: new THREE.BoxGeometry(0.034, 0.006, 0.006),
  neck: lathe([[0.048, 0], [0.044, 0.08], [0.046, 0.12]], 12),
  hairCap: new THREE.SphereGeometry(0.112, 22, 14, 0, Math.PI * 2, 0, Math.PI * 0.55),
  bun: new THREE.SphereGeometry(0.05, 12, 10),
  tail: new THREE.CapsuleGeometry(0.035, 0.16, 4, 10),
  shoe: new THREE.CapsuleGeometry(0.045, 0.16, 4, 10),
  shoulder: new THREE.SphereGeometry(0.068, 14, 12),
  pocket: new THREE.BoxGeometry(0.11, 0.1, 0.01),
  badge: new THREE.BoxGeometry(0.05, 0.07, 0.008),
  steth: new THREE.TorusGeometry(0.11, 0.008, 6, 24, Math.PI * 1.25),
};

/**
 * A head with a simple face (eyes, nose, ears, jaw) and hair, facing +z.
 * cap: a scrub-cap colour instead of hair. closed: sleeping eyes (patients).
 * skin/hair may be materials or omitted (picked from the seed).
 */
export function makeHead({ seed = Math.random(), skin, hair, cap = null, closed = false } = {}) {
  const r = (k) => Math.floor(seed * 997 * (k + 1));
  skin ??= mat(SKIN[r(0) % SKIN.length], 0.62);
  hair ??= mat(HAIR[r(1) % HAIR.length], 0.85);
  const M = (geo, m, x = 0, y = 0, z = 0) => { const o = new THREE.Mesh(geo, m); o.position.set(x, y, z); return o; };
  const head = new THREE.Group();
  const skull = M(GEO.head, skin);
  skull.scale.set(0.9, 1.04, 0.98);
  const jaw = M(GEO.jaw, skin, 0, -0.04, 0.016);
  jaw.scale.set(0.95, 0.85, 1);
  const nose = M(GEO.nose, skin, 0, -0.012, 0.1);
  nose.rotation.x = Math.PI / 2 + 0.3;
  const mouth = M(GEO.mouth, LIP, 0, -0.058, 0.085);
  head.add(skull, jaw, nose, mouth);
  for (const s of [-1, 1]) {
    const ear = M(GEO.ear, skin, s * 0.094, -0.005, -0.005);
    ear.scale.set(0.45, 1, 0.75);
    const eye = closed ? M(GEO.lid, EYE, s * 0.034, 0.012, 0.097) : M(GEO.eye, EYE, s * 0.034, 0.012, 0.094);
    const brow = M(GEO.brow, hair, s * 0.035, 0.04, 0.095);
    brow.rotation.z = s * -0.12;
    head.add(ear, eye, brow);
  }
  if (cap) {
    const c = M(GEO.hairCap, mat(cap, 0.9), 0, 0.02, -0.004);
    c.scale.set(0.98, 0.9, 1.04);
    head.add(c);
  } else {
    const capHair = M(GEO.hairCap, hair, 0, 0.004, -0.018);
    capHair.rotation.x = -0.55; // hairline high on the forehead, hair over the back of the head
    capHair.scale.set(0.97, 1.0, 1.04);
    head.add(capHair);
    const style = r(3) % 4;
    if (style === 1) head.add(M(GEO.bun, hair, 0, 0.05, -0.105));
    if (style === 2) { const t = M(GEO.tail, hair, 0, -0.06, -0.11); t.rotation.x = 0.25; head.add(t); }
  }
  return head;
}

/**
 * Builds a person about 1.72 m tall, facing +z, with jointed hips, knees,
 * shoulders and elbows.
 * outfit: "scrubs", "coat" (doctor: white coat over dark trousers) or "casual".
 * Returns { group, body, armL, armR, legL, legR, head, walk(phase, amount), sit(), idle(t) }.
 */
export function makePerson({ outfit = "scrubs", color = "#2f9aa8", seed = Math.random(), cap = false, steth = false } = {}) {
  const r = (k) => Math.floor(seed * 997 * (k + 1)) ;
  const pick = (arr, k = 0) => arr[r(k) % arr.length];
  const skin = mat(pick(SKIN), 0.62), hair = mat(pick(HAIR, 1), 0.85);
  const topColor = outfit === "coat" ? "#f4f6f7" : color;
  const top = mat(topColor, outfit === "scrubs" ? 0.85 : 0.7);
  const bottom = mat(outfit === "scrubs" ? new THREE.Color(color).multiplyScalar(0.9).getStyle() : outfit === "coat" ? "#38414b" : pick(["#3b4f6b", "#4b4f55", "#5d4a3a"], 2));
  const shoeM = mat(outfit === "casual" ? "#2a2c2e" : "#f2f3f3", 0.5);
  const g = new THREE.Group();
  const body = new THREE.Group(); // everything above the floor, so the whole figure can bob or sit
  g.add(body);
  const M = (geo, m, x = 0, y = 0, z = 0, shadow = true) => { const o = new THREE.Mesh(geo, m); o.position.set(x, y, z); o.castShadow = shadow; return o; };

  // torso and hips (shoulders wider than deep)
  const torso = M(outfit === "coat" ? GEO.coat : GEO.torso, top);
  torso.scale.set(1.12, 1, 0.68);
  const pelvis = M(GEO.pelvis, bottom);
  pelvis.scale.set(1.08, 1, 0.72);
  body.add(torso, pelvis);
  for (const s of [-1, 1]) { const sh = M(GEO.shoulder, top, s * 0.175, 1.405, 0); sh.scale.set(0.95, 0.8, 0.9); body.add(sh); }
  if (outfit !== "casual") {
    const pk = M(GEO.pocket, mat(new THREE.Color(topColor).multiplyScalar(0.93).getStyle()), -0.075, 1.26, 0.118);
    body.add(pk);
    const badge = M(GEO.badge, mat("#ffffff", 0.4), 0.08, 1.3, 0.12);
    body.add(badge);
  }
  if (steth) {
    const st = M(GEO.steth, mat("#2b3135", 0.4), 0, 1.4, 0.02);
    st.rotation.x = Math.PI / 2 - 0.35;
    st.rotation.z = Math.PI * 0.62;
    st.scale.set(1, 1.15, 1);
    body.add(st);
  }

  // neck and head with a simple face
  const neck = M(GEO.neck, skin, 0, 1.46, 0);
  const head = makeHead({ skin, hair, seed, cap: cap ? new THREE.Color(color).multiplyScalar(1.12).getStyle() : null });
  head.position.set(0, 1.62, 0.005);
  body.add(neck, head);

  // arms: shoulder pivot > upper arm (sleeve + skin) > elbow pivot > forearm > hand
  const arm = (s) => {
    const shoulder = new THREE.Group();
    shoulder.position.set(s * 0.205, 1.4, 0);
    const longSleeve = outfit !== "scrubs";
    shoulder.add(M(longSleeve ? GEO.longSleeve : GEO.sleeve, top));
    if (!longSleeve) shoulder.add(M(GEO.upperArm, skin));
    const elbow = new THREE.Group();
    elbow.position.y = -0.29;
    elbow.rotation.x = -0.18;
    const fore = M(GEO.forearm, skin);
    const hand = M(GEO.hand, skin, 0, -0.29, 0.01);
    hand.scale.set(0.7, 1.25, 0.95);
    elbow.add(fore, hand);
    shoulder.add(elbow);
    shoulder.rotation.z = s * 0.06;
    shoulder.userData.elbow = elbow;
    return shoulder;
  };
  const armL = arm(-1), armR = arm(1);

  // legs: hip pivot > thigh > knee pivot > shin > shoe
  const leg = (s) => {
    const hip = new THREE.Group();
    hip.position.set(s * 0.085, 0.9, 0);
    hip.add(M(GEO.thigh, bottom));
    const knee = new THREE.Group();
    knee.position.y = -0.44;
    knee.add(M(GEO.shin, bottom));
    const shoe = M(GEO.shoe, shoeM, 0, -0.42, 0.045);
    shoe.rotation.x = Math.PI / 2;
    shoe.scale.set(1.05, 1, 0.8);
    knee.add(shoe);
    hip.add(knee);
    hip.userData.knee = knee;
    return hip;
  };
  const legL = leg(-1), legR = leg(1);
  body.add(armL, armR, legL, legR);

  const E = (a) => a.userData.elbow, K = (l) => l.userData.knee;
  let seated = false;
  return {
    group: g, body, armL, armR, legL, legR, head,
    /** phase advances with distance walked; amount 0..1 blends between standing and full stride. */
    walk(phase, amount = 1) {
      const s = Math.sin(phase) * 0.42 * amount;
      legL.rotation.x = s; legR.rotation.x = -s;
      // the knee bends as the leg swings through, straight on contact
      K(legL).rotation.x = Math.max(0, Math.sin(phase + 1.2)) * 0.75 * amount;
      K(legR).rotation.x = Math.max(0, Math.sin(phase + 1.2 + Math.PI)) * 0.75 * amount;
      armL.rotation.x = -s * 0.75; armR.rotation.x = s * 0.75;
      E(armL).rotation.x = -0.25 - Math.max(0, -s) * 0.4; E(armR).rotation.x = -0.25 - Math.max(0, s) * 0.4;
      body.position.y = Math.abs(Math.cos(phase)) * 0.022 * amount;
      body.rotation.y = Math.sin(phase) * 0.05 * amount; // a little hip and shoulder counter-swing
    },
    /** Seated pose on a chair of normal height (seat ~0.47 m). */
    sit() {
      seated = true;
      legL.rotation.x = legR.rotation.x = -1.45;
      K(legL).rotation.x = K(legR).rotation.x = 1.42;
      legL.rotation.z = -0.06; legR.rotation.z = 0.06;
      body.position.y = -0.42;
      armL.rotation.x = armR.rotation.x = -0.35;
      E(armL).rotation.x = E(armR).rotation.x = -0.9;
    },
    /** Standing still: slow weight shift and a little head movement. */
    idle(t, k = 1) {
      if (seated) return;
      body.rotation.z = Math.sin(t * 0.7 + seed * 9) * 0.012 * k;
      body.rotation.y = 0;
      head.rotation.y = Math.sin(t * 0.33 + seed * 20) * 0.35 * k;
      legL.rotation.x = legR.rotation.x = 0;
      K(legL).rotation.x = K(legR).rotation.x = 0;
      armL.rotation.x = armR.rotation.x = 0;
      E(armL).rotation.x = E(armR).rotation.x = -0.15;
      body.position.y = 0;
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
      const s = p.z < 0 ? 1 : -1; // foot-right corner of the bay (front row is mirrored)
      return new THREE.Vector3(p.x + 0.95 * s, 0, p.z + 1.55 * s);
    }
    if (r < 0.88) return new THREE.Vector3(-3 + Math.random() * 6, 0, 2.0 + Math.random() * 0.4); // station counter
    return new THREE.Vector3(25 + Math.random() * 6, 0, -3.4 + Math.random() * 1.2); // check-in desk
  };
  const walkers = [];
  for (let i = 0; i < 4; i++) {
    const p = makePerson(i === 3 ? { outfit: "coat", steth: true, seed: 0.77 } : { color: SCRUBS[i], cap: i === 1, steth: i === 2, seed: 0.13 + i * 0.21 });
    const start = spots();
    p.group.position.copy(start);
    scene.add(p.group);
    walkers.push({ p, w: makeWalker(p, 1.2 + Math.random() * 0.35), wait: 2 + Math.random() * 8 });
  }
  for (const [i, [x, z]] of (world.station?.seats || []).entries()) {
    const p = makePerson({ color: SCRUBS[(i + 1) % SCRUBS.length], seed: 0.41 + i * 0.3 });
    p.sit();
    p.group.position.set(x, 0, z - 0.05);
    p.group.rotation.y = Math.PI;
    scene.add(p.group);
    walkers.push({ p, seated: true });
  }
  world.onFrame((dt, t) => {
    for (const s of walkers) {
      if (s.seated) { // typing: small forearm movement, the odd glance up
        s.p.armL.rotation.x = -0.45 + Math.sin(t * 7 + s.p.group.position.x) * 0.04;
        s.p.armL.userData.elbow.rotation.x = -1.15 + Math.sin(t * 9 + s.p.group.position.x) * 0.06;
        s.p.armR.rotation.x = -0.45 + Math.cos(t * 6 + s.p.group.position.x) * 0.04;
        s.p.armR.userData.elbow.rotation.x = -1.15 + Math.cos(t * 8 + s.p.group.position.x) * 0.06;
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
