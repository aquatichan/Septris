// Smooth camera moves: overview of the whole unit, or a close look at a bed.
import * as THREE from "three";
import { bayPosition } from "./beds.js";
import { freeSpan } from "./world.js";

export function createCameraRig(world) {
  const { camera, controls } = world;
  let anim = null;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let path = null, held = false;
  function overviewPose() {
    const narrow = window.innerWidth < 860;
    const span = freeSpan();
    const wide = (span.right - span.left) / window.innerHeight; // the part of the screen the ward can use
    const d = narrow ? 2.6 : Math.max(1.1, 1.9 / wide); // pull back on tall or narrow views
    const cx = 8; // centre of ward + lobby
    return [new THREE.Vector3(cx, 34 * d, 36 * d), new THREE.Vector3(cx, 0, 1.5)];
  }
  world.onFrame((dt) => {
    if (path) { path.step(dt); return; }
    if (!anim) return;
    anim.t = Math.min(1, anim.t + dt / anim.dur);
    const k = anim.t < 0.5 ? 4 * anim.t ** 3 : 1 - (-2 * anim.t + 2) ** 3 / 2; // easeInOutCubic
    camera.position.lerpVectors(anim.fromPos, anim.toPos, k);
    controls.target.lerpVectors(anim.fromTarget, anim.toTarget, k);
    if (anim.t >= 1) anim = null;
  });

  function flyTo(pos, target, dur = 1.2) {
    if (reduce) {
      camera.position.copy(pos);
      controls.target.copy(target);
      return;
    }
    anim = { t: 0, dur, fromPos: camera.position.clone(), toPos: pos.clone(), fromTarget: controls.target.clone(), toTarget: target.clone() };
  }

  return {
    overview() {
      const [pos, target] = overviewPose();
      flyTo(pos, target);
    },
    /**
     * Opening shot. The camera rides the elevator (floor display counts up),
     * the doors open, and it walks through the lobby, past check-in, down the
     * ward corridor, then lifts off to the overview.
     * hooks: { onFloor(n), onArrive(), onDoors(), onWalk(), done() }
     */
    intro(lobby, hooks = {}) {
      const [endPos, endTarget] = overviewPose();
      const finish = () => { world.fullView = false; world.indoor = false; world.resize?.(); hooks.done?.(); };
      if (reduce) { camera.position.copy(endPos); controls.target.copy(endTarget); finish(); return; }
      const V = (x, y, z) => new THREE.Vector3(x, y, z);
      const pos = new THREE.CatmullRomCurve3([V(39.6, 1.6, 0), V(36.8, 1.62, 0), V(32, 1.62, -0.4), V(26, 1.62, -0.3), V(21.5, 1.62, 0),
        V(14, 1.65, 1.9), V(6, 1.7, 2.3), V(-2, 2.6, 2.6), V(-4, 9, 12), V(4, 22, 26), endPos], false, "centripetal");
      const tgt = new THREE.CatmullRomCurve3([V(33, 1.5, 0), V(30, 1.5, -1.5), V(26, 1.4, -4), V(20, 1.4, -1.5), V(12, 1.3, 0),
        V(4, 1.2, -2), V(-6, 1.1, -5), V(-12, 1.0, -4), V(-4, 0.5, -2), V(4, 0, 0), endTarget], false, "centripetal");
      const maxPolar = controls.maxPolarAngle;
      controls.maxPolarAngle = Math.PI;
      controls.enabled = false;
      world.fullView = true; // centre the picture while the side panel is hidden
      world.indoor = true;
      world.resize?.();
      camera.position.copy(pos.getPoint(0));
      controls.target.copy(tgt.getPoint(0));
      lobby.setDoors(false);
      lobby.setDisplay("1");
      let ride = 0, t = 0, floor = 1, opened = false, walking = false;
      const RIDE = 3.4, OPEN = 1.5, WALK = 15;
      const stop = () => { path = null; controls.maxPolarAngle = maxPolar; controls.enabled = true; lobby.setDoors(false); finish(); };
      path = { step(dt) {
        if (held) return;
        dt = Math.min(dt, 0.05); // slow devices get a slower, still-smooth ride
        if (ride < RIDE + OPEN) {
          ride += dt;
          const f = Math.min(3, 1 + Math.floor((ride / RIDE) * 3));
          if (f !== floor) { floor = f; lobby.setDisplay(String(f)); hooks.onFloor?.(f); }
          camera.position.y = 1.62 + (ride < RIDE ? Math.sin(ride * 40) * 0.0025 : 0); // a little motor shake
          if (ride >= RIDE && !opened) { opened = true; lobby.setDisplay("3"); lobby.setDoors(true); hooks.onArrive?.(); }
          return;
        }
        if (!walking) { walking = true; hooks.onWalk?.(); }
        t += dt / WALK;
        const k = Math.min(1, t);
        const e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
        camera.position.copy(pos.getPoint(e));
        if (e < 0.62) camera.position.y += Math.abs(Math.sin(e * 150)) * 0.022; // footsteps
        controls.target.copy(tgt.getPoint(e));
        if (k >= 1) stop();
      }, skip() { camera.position.copy(endPos); controls.target.copy(endTarget); stop(); } };
    },
    skipIntro() { held = false; path?.skip(); },
    pause(on) { held = on; },
    bed(bed) {
      const p = bayPosition(bed);
      const s = p.z < 0 ? 1 : -1; // always look from the corridor side
      flyTo(new THREE.Vector3(p.x - 2.4 * s, 4.4, p.z + 7.2 * s), new THREE.Vector3(p.x + 0.2 * s, 1.0, p.z + 0.2 * s));
    },
    flyTo,
  };
}
