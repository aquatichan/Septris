// Quiet set dressing so the ward doesn't float in a void: a plinth under the
// building, a faint site grid fading into fog, plants and a bench in the
// lobby, and a few carts in the ward. Nothing here carries information.
import * as THREE from "three";

export function createDecor(world) {
  const { scene } = world;
  const add = (geo, mat, x, y, z, shadow = true) => {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, y, z);
    m.castShadow = m.receiveShadow = shadow;
    scene.add(m);
    return m;
  };

  // plinth: the building sits on a slab slightly larger than its footprint
  const slab = new THREE.MeshStandardMaterial({ color: "#131f24", roughness: 0.9 });
  const trim = new THREE.MeshStandardMaterial({ color: "#24414b", roughness: 0.6 });
  for (const [w, d, x] of [[46, 24, 0], [18.4, 18, 31.6]]) {
    add(new THREE.BoxGeometry(w, 0.5, d), slab, x, -0.27, 0, false).receiveShadow = true;
    add(new THREE.BoxGeometry(w + 0.6, 0.08, d + 0.6), trim, x, -0.54, 0, false);
  }

  // site grid that fades out with the fog
  const grid = new THREE.GridHelper(400, 100, "#1c3a44", "#14262d");
  grid.position.y = -0.6;
  grid.material.transparent = true;
  grid.material.opacity = 0.55;
  scene.add(grid);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.MeshBasicMaterial({ color: "#0a1216" }));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.62;
  scene.add(ground);

  // plants
  const pot = new THREE.MeshStandardMaterial({ color: "#8d6e5a", roughness: 0.8 });
  const leaf = new THREE.MeshStandardMaterial({ color: "#3f8f6a", roughness: 0.9 });
  const plant = (x, z, s = 1) => {
    add(new THREE.CylinderGeometry(0.32 * s, 0.24 * s, 0.55 * s, 16), pot, x, 0.28 * s, z);
    for (const [dx, dy, dz, r] of [[0, 1.0, 0, 0.5], [0.22, 0.75, 0.1, 0.36], [-0.2, 0.8, -0.12, 0.38], [0.02, 1.35, -0.05, 0.3]]) {
      add(new THREE.IcosahedronGeometry(r * s, 1), leaf, x + dx * s, dy * s, z + dz * s);
    }
  };
  plant(34.8, -7.0, 1.1);
  plant(34.8, 7.0, 1.1);
  plant(23.0, -7.0);
  plant(21.2, 3.2, 0.9);

  // ward: supply carts by the end wall, a crash cart near the station, a linen trolley
  const steel = new THREE.MeshStandardMaterial({ color: "#b9c2c6", metalness: 0.6, roughness: 0.35 });
  const cart = (x, z, color, ry = 0) => {
    const body = add(new THREE.BoxGeometry(0.9, 0.85, 0.55), steel, x, 0.55, z);
    body.rotation.y = ry;
    const top = add(new THREE.BoxGeometry(0.92, 0.1, 0.57), new THREE.MeshStandardMaterial({ color, roughness: 0.6 }), x, 1.03, z);
    top.rotation.y = ry;
    for (let i = 0; i < 3; i++) {
      const d = add(new THREE.BoxGeometry(0.8, 0.02, 0.02), new THREE.MeshStandardMaterial({ color: "#6f7a7f" }), x + Math.sin(ry) * 0.28, 0.35 + i * 0.22, z + Math.cos(ry) * 0.28, false);
      d.rotation.y = ry;
    }
  };
  cart(5.6, -1.0, "#d9534f");
  cart(21.0, -4.4, "#3d6fb6", -Math.PI / 2);

  // hand-wash counter with wall cabinets on the left wall, between the windows
  const oak = new THREE.MeshStandardMaterial({ color: "#cdb89a", roughness: 0.6 });
  const white = new THREE.MeshStandardMaterial({ color: "#f1f4f4", roughness: 0.35 });
  for (const z of [-3.25, 3.25]) {
    add(new THREE.BoxGeometry(0.6, 0.9, 2.4), oak, -21.65, 0.45, z);
    add(new THREE.BoxGeometry(0.64, 0.05, 2.5), white, -21.63, 0.93, z);
    add(new THREE.BoxGeometry(0.36, 0.1, 0.5), new THREE.MeshStandardMaterial({ color: "#aeb8bc", metalness: 0.8, roughness: 0.25 }), -21.6, 0.94, z);
    add(new THREE.BoxGeometry(0.34, 0.6, 2.4), oak, -21.8, 2.1, z);
  }
  // wall clock on the back wall, above the nurse station
  const face = add(new THREE.CylinderGeometry(0.28, 0.28, 0.05, 32), white, 0, 2.5, -10.95, false);
  face.rotation.x = Math.PI / 2;
  const rim = add(new THREE.TorusGeometry(0.28, 0.02, 8, 32), new THREE.MeshStandardMaterial({ color: "#3a4246", roughness: 0.4 }), 0, 2.5, -10.93, false);
  const hand = (len, a) => {
    const h = add(new THREE.BoxGeometry(0.014, len, 0.01), new THREE.MeshBasicMaterial({ color: "#1b2327" }), Math.sin(a) * len / 2, 2.5 + Math.cos(a) * len / 2, -10.915, false);
    h.rotation.z = -a;
  };
  hand(0.2, 0.9); hand(0.14, -1.2);
}
