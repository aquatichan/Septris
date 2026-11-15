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
  plant(23.2, -7.0);
  plant(-21.0, -9.9, 0.9);
  plant(21.0, -9.9, 0.9);

  // lobby bench facing the desk
  const wood = new THREE.MeshStandardMaterial({ color: "#7a6654", roughness: 0.7 });
  add(new THREE.BoxGeometry(3.2, 0.12, 0.7), wood, 30.5, 0.5, 4.2);
  for (const x of [29.2, 31.8]) add(new THREE.BoxGeometry(0.12, 0.5, 0.6), new THREE.MeshStandardMaterial({ color: "#3a4a50" }), x, 0.25, 4.2);

  // ward: supply carts by the end walls and a crash cart near the station
  const steel = new THREE.MeshStandardMaterial({ color: "#aab7bb", metalness: 0.6, roughness: 0.35 });
  const cart = (x, z, color) => {
    add(new THREE.BoxGeometry(0.9, 0.95, 0.6), steel, x, 0.55, z);
    add(new THREE.BoxGeometry(0.92, 0.12, 0.62), new THREE.MeshStandardMaterial({ color, roughness: 0.6 }), x, 1.08, z);
  };
  cart(-21.2, -2.6, "#d9534f");
  cart(-21.2, 2.6, "#4fb3ff");
  cart(5.4, 0, "#d9534f");
  cart(21.0, -4.6, "#4fb3ff");

  // hand-wash stations on the back wall between every second bay
  const basin = new THREE.MeshStandardMaterial({ color: "#e6eef0", roughness: 0.3 });
  for (const x of [-13.2, -4.4, 4.4, 13.2]) {
    add(new THREE.BoxGeometry(0.7, 0.16, 0.42), basin, x, 1.0, -10.6);
    add(new THREE.BoxGeometry(0.5, 0.5, 0.05), new THREE.MeshStandardMaterial({ color: "#16404f", roughness: 0.4 }), x, 1.75, -10.83, false);
  }
}
