// Smooth camera moves: overview of the whole unit, or a close look at a bed.
import * as THREE from "three";
import { bayPosition } from "./beds.js";

export function createCameraRig(world) {
  const { camera, controls } = world;
  let anim = null;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let path = null;
  function overviewPose() {
    const narrow = window.innerWidth < 860;
    const wide = window.innerWidth / window.innerHeight;
    const d = narrow ? 2.6 : Math.max(1.5, 2.9 / wide); // pull back on tall or narrow windows
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
    /** Opening shot: out of the elevator, through the lobby, into the ward, then up to the overview. */
    intro(lobby, done) {
      const [endPos, endTarget] = overviewPose();
      if (reduce) { camera.position.copy(endPos); controls.target.copy(endTarget); done?.(); return; }
      const V = (x, y, z) => new THREE.Vector3(x, y, z);
      const pos = new THREE.CatmullRomCurve3([V(38.6, 1.7, 0), V(33, 1.75, 0.2), V(26, 1.9, 0.6), V(18, 2.4, 0.4), V(9, 5, 3), V(6, 16, 16), endPos], false, "centripetal");
      const tgt = new THREE.CatmullRomCurve3([V(30, 1.6, -0.5), V(26, 1.5, -2.5), V(16, 1.4, -1), V(6, 1.2, -1.5), V(0, 1, -1), V(3, 0, 0), endTarget], false, "centripetal");
      const maxPolar = controls.maxPolarAngle;
      controls.maxPolarAngle = Math.PI;
      controls.enabled = false;
      camera.position.copy(pos.getPoint(0));
      controls.target.copy(tgt.getPoint(0));
      lobby.setDoors(true);
      let hold = 1.3, t = 0; // hold while the doors open
      const stop = () => { path = null; controls.maxPolarAngle = maxPolar; controls.enabled = true; lobby.setDoors(false); done?.(); };
      path = { step(dt) {
        dt = Math.min(dt, 0.05); // slow devices get a slower, still-smooth ride
        if (hold > 0) { hold -= dt; return; }
        t += dt / 8;
        const k = Math.min(1, t);
        const e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
        camera.position.copy(pos.getPoint(e));
        controls.target.copy(tgt.getPoint(e));
        if (k >= 1) stop();
      }, skip() { camera.position.copy(endPos); controls.target.copy(endTarget); stop(); } };
    },
    skipIntro() { path?.skip(); },
    bed(bed) {
      const p = bayPosition(bed);
      flyTo(new THREE.Vector3(p.x - 2.6, 4.8, p.z + 6.4), new THREE.Vector3(p.x + 0.3, 1.1, p.z));
    },
    flyTo,
  };
}
