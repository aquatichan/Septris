// First-person views.
//  walk:  you are a visitor on the ward. W A S D (or arrows) to move, drag to
//         look around, Shift to hurry. Walls, beds, the station and the
//         check-in desk are solid.
//  nurse: you see through the charge nurse's eyes. She walks to whichever bed
//         Septris picks, so there is nothing to control.
// Both turn the ceilings on (world.indoor) and take the camera away from the
// orbit controls (world.manualCamera) until exit().
import * as THREE from "three";
import { bayPosition } from "./beds.js";
import { LOBBY } from "./lobby.js";

const EYE = 1.62, R = 0.3;

// solid rectangles on the floor plan: [x0, x1, z0, z1]
function obstacles() {
  const o = [];
  for (let bed = 1; bed <= 20; bed++) {
    const p = bayPosition(bed), back = p.z < 0;
    o.push([p.x - 0.6, p.x + 0.6, back ? -11 : p.z - 1.15, back ? p.z + 1.15 : 11]); // bed and head wall
    o.push([p.x - 1.05, p.x - 0.75, back ? p.z - 0.95 : p.z + 0.6, back ? p.z - 0.6 : p.z + 0.95]); // IV stand
  }
  o.push([-3.7, 3.7, -1.2, 1.45]); // nurse station and its chairs
  o.push([25.3, 31.7, -7.2, -4.7]); // check-in desk and clerk
  o.push([23.8, 27.4, 6.0, 8]); // waiting seats
  return o;
}

function walkable(x, z, obs) {
  const inWard = x > -22 + R && x < 22 - R && z > -11 + R && z < 11 - R;
  const inDoor = x >= 21 && x <= 23 && z > -3.5 + R && z < 3.5 - R;
  const inLobby = x > LOBBY.x0 + R && x < LOBBY.x1 - R - 0.1 && z > -LOBBY.halfZ + R && z < LOBBY.halfZ - R;
  if (!inWard && !inDoor && !inLobby) return false;
  return !obs.some(([x0, x1, z0, z1]) => x > x0 - R && x < x1 + R && z > z0 - R && z < z1 + R);
}

export function createViews(world, { nurse, onChange }) {
  const { camera, controls, renderer } = world;
  const obs = obstacles();
  const keys = new Set();
  let mode = null; // null | "walk" | "nurse"
  let yaw = 0, pitch = 0, drag = null;
  const look = new THREE.Vector3(), want = new THREE.Vector3(), head = new THREE.Vector3();

  const typing = (e) => ["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName);
  window.addEventListener("keydown", (e) => {
    if (!mode || typing(e)) return;
    if (e.key === "Escape") { exit(); return; }
    const k = e.key.toLowerCase();
    if (["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright", "shift"].includes(k)) { keys.add(k); e.preventDefault(); }
  });
  window.addEventListener("keyup", (e) => keys.delete(e.key.toLowerCase()));
  window.addEventListener("blur", () => keys.clear());
  const el = renderer.domElement;
  el.addEventListener("pointerdown", (e) => { if (mode === "walk") drag = [e.clientX, e.clientY]; });
  window.addEventListener("pointerup", () => (drag = null));
  window.addEventListener("pointermove", (e) => {
    if (mode !== "walk" || !drag) return;
    yaw -= (e.clientX - drag[0]) * 0.004;
    pitch = Math.max(-1.1, Math.min(0.9, pitch - (e.clientY - drag[1]) * 0.004));
    drag = [e.clientX, e.clientY];
  });

  world.onFrame((dt) => {
    if (mode === "walk") {
      const fwd = (keys.has("w") || keys.has("arrowup") ? 1 : 0) - (keys.has("s") || keys.has("arrowdown") ? 1 : 0);
      const side = (keys.has("d") ? 1 : 0) - (keys.has("a") ? 1 : 0);
      yaw += ((keys.has("arrowleft") ? 1 : 0) - (keys.has("arrowright") ? 1 : 0)) * dt * 1.8; // arrows turn
      if (fwd || side) {
        const speed = (keys.has("shift") ? 3.2 : 1.6) * dt;
        const sx = Math.sin(yaw), cz = Math.cos(yaw);
        const len = Math.hypot(fwd, side);
        const dx = ((sx * fwd - cz * side) / len) * speed, dz = ((cz * fwd + sx * side) / len) * speed;
        const p = camera.position;
        if (walkable(p.x + dx, p.z, obs)) p.x += dx; // slide along walls
        if (walkable(p.x, p.z + dz, obs)) p.z += dz;
        world.stepT = (world.stepT || 0) + speed * 5.5;
      }
      camera.position.y = EYE + Math.sin(world.stepT || 0) * 0.018; // footsteps
      look.set(Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch));
      controls.target.copy(camera.position).add(look);
      camera.lookAt(controls.target);
    } else if (mode === "nurse") {
      const n = nurse.person.group;
      const walking = nurse.idleFor() === 0;
      const ry = walking ? n.rotation.y : nurse.facing();
      want.set(Math.sin(ry), walking ? -0.12 : -0.42, Math.cos(ry)).normalize(); // standing still: look down at the patient
      look.lerp(want, Math.min(1, dt * 3)).normalize();
      head.set(n.position.x + Math.sin(n.rotation.y) * 0.1, EYE - 0.04 + (walking ? Math.sin(performance.now() / 160) * 0.015 : 0), n.position.z + Math.cos(n.rotation.y) * 0.1);
      camera.position.lerp(head, Math.min(1, dt * 8));
      controls.target.copy(camera.position).add(look);
      camera.lookAt(controls.target);
    }
  });

  function enter(m) {
    if (mode === m) return;
    exit(false);
    mode = m;
    world.manualCamera = true;
    world.indoor = true;
    controls.enabled = false;
    document.body.classList.add(m === "walk" ? "walking" : "nursing");
    if (m === "walk") {
      camera.position.set(19.5, EYE, 0.6); // just inside the doorway, looking down the corridor
      yaw = -Math.PI / 2; pitch = -0.05;
    } else {
      nurse.person.group.visible = false; // we are her: hide her body from her own eyes
      const n = nurse.person.group;
      camera.position.set(n.position.x, EYE, n.position.z);
      look.set(Math.sin(n.rotation.y), -0.1, Math.cos(n.rotation.y)).normalize();
    }
    onChange?.(mode);
  }

  function exit(notify = true) {
    if (!mode) return;
    document.body.classList.remove("walking", "nursing");
    nurse.person.group.visible = true;
    keys.clear();
    mode = null;
    world.manualCamera = false;
    world.indoor = false;
    controls.enabled = true;
    // put the orbit target in front of the camera so the hand-back is seamless
    camera.getWorldDirection(look);
    controls.target.copy(camera.position).addScaledVector(look, 6);
    if (notify) onChange?.(null);
  }

  return { walk: () => enter("walk"), nurse: () => enter("nurse"), exit, get mode() { return mode; } };
}
