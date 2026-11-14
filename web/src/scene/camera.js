// Smooth camera moves: overview of the whole unit, or a close look at a bed.
import * as THREE from "three";
import { bayPosition } from "./beds.js";

export function createCameraRig(world) {
  const { camera, controls } = world;
  let anim = null;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  world.onFrame((dt) => {
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
      const narrow = window.innerWidth < 860;
      const wide = window.innerWidth / window.innerHeight;
      const d = narrow ? 1.9 : Math.max(1.08, 1.9 / wide); // pull back on tall or narrow windows
      flyTo(new THREE.Vector3(0, 34 * d, 36 * d), new THREE.Vector3(0, 0, 2.5));
    },
    bed(bed) {
      const p = bayPosition(bed);
      flyTo(new THREE.Vector3(p.x - 2.6, 4.8, p.z + 6.4), new THREE.Vector3(p.x + 0.3, 1.1, p.z));
    },
    flyTo,
  };
}
