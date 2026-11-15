// Renderer, camera, controls, lighting and the ward's shell: tiled floor,
// painted walls, acoustic ceiling with fluorescent fixtures (a couple of them
// flicker), windows, and the nurse station. Beds live in beds.js, people in
// people.js, the lobby and elevator in lobby.js. Units are metres; +x runs
// along the ward, z across it, y up.
//
// The ceiling and the front wall are one-sided, facing inward: you see them
// when the camera is inside (the opening walk-through) and see straight
// through them from the overview, like a doll's house.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { floorTiles, ceilingTiles, wallPaint, wood, blindsLight, windowBlinds } from "./textures.js";

export const UNIT = { length: 44, width: 22, wall: 3.0 };
const LIGHT_ON = new THREE.Color(2.4, 2.45, 2.5); // brighter than white, so fixtures glow

export function createWorld(container) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.82;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.appendChild(renderer.domElement);

  const labels = new CSS2DRenderer();
  labels.domElement.style.position = "absolute";
  labels.domElement.style.inset = "0";
  labels.domElement.style.pointerEvents = "none";
  container.appendChild(labels.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#0b1418");
  scene.fog = new THREE.Fog("#0b1418", 110, 220);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.4;

  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 320);
  camera.position.set(0, 30, 34);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0, 0);
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI * 0.47;
  controls.minDistance = 4;
  controls.maxDistance = 110;

  // soft daylight-white fill plus one shadow-casting key light from above
  scene.add(new THREE.HemisphereLight("#ffffff", "#8e999e", 0.62));
  const key = new THREE.DirectionalLight("#fff6e8", 1.5);
  key.position.set(-12, 30, 14);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -30, right: 46, top: 20, bottom: -20, near: 1, far: 90 });
  key.shadow.bias = -0.0005;
  key.shadow.normalBias = 0.03;
  scene.add(key);

  const frameFns = new Set();
  const world = { THREE, renderer, scene, camera, controls, onFrame: (fn) => frameFns.add(fn) };
  world.fixtures = buildRoom(world);

  // gentle glow on light fixtures, floor rings and the pick beam only
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(1, 1), 0.22, 0.5, 1.4));
  composer.addPass(new OutputPass());

  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    renderer.setSize(w, h);
    composer.setSize(w, h);
    labels.setSize(w, h);
    camera.aspect = w / h;
    // keep the scene centred in the part of the screen the panel doesn't cover
    const panel = document.getElementById("panel");
    if (world.fullView) camera.clearViewOffset();
    else if (w > 860 && panel) camera.setViewOffset(w, h, (panel.offsetWidth + 16) / 2, 0, w, h);
    else camera.setViewOffset(w, h, 0, h * 0.2, w, h);
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);
  world.resize = resize;
  resize();

  const clock = new THREE.Clock();
  renderer.setAnimationLoop(() => {
    const dt = Math.min(clock.getDelta(), 0.1), t = clock.elapsedTime;
    for (const fn of frameFns) fn(dt, t);
    controls.update();
    // zoomed out: bed labels switch to a compact form so they don't overlap
    container.classList.toggle("far", camera.position.distanceTo(controls.target) > 26);
    composer.render();
    labels.render(scene, camera);
  });

  return world;
}

/** A ceiling light: a one-sided glowing panel in a thin housing. Returns its material so it can flicker. */
export function fixture(scene, x, z, { y = UNIT.wall - 0.02, len = 2.4, wide = 0.5, alongX = true } = {}) {
  const mat = new THREE.MeshBasicMaterial({ color: LIGHT_ON.clone(), toneMapped: false });
  const lamp = new THREE.Mesh(new THREE.PlaneGeometry(alongX ? len : wide, alongX ? wide : len), mat);
  lamp.rotation.x = Math.PI / 2; // faces down
  lamp.position.set(x, y - 0.03, z);
  const housing = new THREE.Mesh(new THREE.PlaneGeometry((alongX ? len : wide) + 0.2, (alongX ? wide : len) + 0.2),
    new THREE.MeshStandardMaterial({ color: "#c9cfd2", metalness: 0.5, roughness: 0.4 }));
  housing.rotation.x = Math.PI / 2;
  housing.position.set(x, y - 0.01, z);
  scene.add(housing, lamp);
  return mat;
}

/** Makes a fixture stutter like a failing tube; `light` is an optional point light that follows it. */
export function flicker(world, mat, light, base = 9) {
  let next = 2 + Math.random() * 5, burst = 0, on = true;
  world.onFrame((dt) => {
    next -= dt;
    if (next <= 0) {
      if (burst > 0) { burst--; on = !on; next = 0.03 + Math.random() * 0.11; }
      else if (on) { burst = 3 + ((Math.random() * 5) | 0) * 2; next = 0.02; } // odd count ends back "on"
      if (burst === 0) { on = true; next = 3 + Math.random() * 9; }
    }
    const k = on ? 1 : 0.12;
    mat.color.copy(LIGHT_ON).multiplyScalar(k);
    if (light) light.intensity = base * k;
  });
}

function buildRoom(world) {
  const { scene } = world;
  const L = UNIT.length, W = UNIT.width, H = UNIT.wall;
  const add = (geo, mat, x, y, z, shadow = true) => {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, y, z);
    m.castShadow = shadow; m.receiveShadow = true;
    scene.add(m);
    return m;
  };

  // floor
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(L, W),
    new THREE.MeshStandardMaterial({ map: floorTiles(L / 1.2, W / 1.2), roughness: 0.38, metalness: 0.02 }));
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  // walls: back and left are solid; the right wall has the doorway to the lobby;
  // the front wall is one-sided so the overview can see in
  const paint = (len) => new THREE.MeshStandardMaterial({ map: wallPaint(len / 2), roughness: 0.9 });
  add(new THREE.BoxGeometry(L + 0.5, H, 0.25), paint(L), 0, H / 2, -W / 2 - 0.125);
  add(new THREE.BoxGeometry(0.25, H, W), paint(W), -L / 2 - 0.125, H / 2, 0);
  for (const z of [-7.25, 7.25]) add(new THREE.BoxGeometry(0.25, H, 7.5), paint(7.5), L / 2, H / 2, z);
  add(new THREE.BoxGeometry(0.25, H - 2.4, 7), paint(7), L / 2, 2.4 + (H - 2.4) / 2, 0);
  const front = new THREE.Mesh(new THREE.PlaneGeometry(L, H), paint(L));
  front.rotation.y = Math.PI; // faces into the room
  front.position.set(0, H / 2, W / 2);
  scene.add(front);

  // ceiling (one-sided, faces down)
  const ceiling = new THREE.Mesh(new THREE.PlaneGeometry(L, W),
    new THREE.MeshStandardMaterial({ map: ceilingTiles(L / 1.2, W / 1.2), roughness: 1 }));
  ceiling.rotation.x = Math.PI / 2;
  ceiling.position.y = H;
  scene.add(ceiling);

  // fluorescent fixtures: a row down the corridor and one over each pair of bays
  const fixtures = [];
  for (let x = -18; x <= 18; x += 6) fixtures.push(fixture(scene, x, 0));
  for (const z of [-6.2, 6.2]) for (let x = -17.6; x <= 17.6; x += 8.8) fixtures.push(fixture(scene, x, z, { len: 1.8 }));
  // one tired tube in the corridor flickers and takes a pool of light with it
  const tired = new THREE.PointLight("#f4f8ff", 9, 9, 1.8);
  tired.position.set(-6, H - 0.4, 0);
  scene.add(tired);
  flicker(world, fixtures[2], tired);

  // windows on the left wall, with sunlight falling through the blinds
  const glass = new THREE.MeshBasicMaterial({ map: windowBlinds(), toneMapped: false, color: new THREE.Color(1.5, 1.5, 1.5) });
  for (const z of [-6.5, 0, 6.5]) {
    const win = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 1.5), glass);
    win.rotation.y = Math.PI / 2;
    win.position.set(-L / 2 + 0.02, 1.85, z);
    scene.add(win);
    const sun = new THREE.Mesh(new THREE.PlaneGeometry(5.5, 3.2),
      new THREE.MeshBasicMaterial({ map: blindsLight(), transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false }));
    sun.rotation.x = -Math.PI / 2;
    sun.position.set(-L / 2 + 3.4, 0.015, z + 0.4);
    scene.add(sun);
  }

  // nurse station in the middle of the corridor: an oak desk with a counter, screens and chairs
  const oak = new THREE.MeshStandardMaterial({ map: wood(), roughness: 0.6 });
  const top = new THREE.MeshStandardMaterial({ color: "#eef1f1", roughness: 0.35 });
  add(new THREE.BoxGeometry(7, 1.0, 0.7), oak, 0, 0.5, -0.75);
  add(new THREE.BoxGeometry(7.2, 0.06, 0.9), top, 0, 1.03, -0.75);
  add(new THREE.BoxGeometry(7, 0.74, 0.8), oak, 0, 0.37, 0.1);
  add(new THREE.BoxGeometry(7.1, 0.05, 0.95), top, 0, 0.765, 0.12);
  for (const x of [-3.5, 3.5]) add(new THREE.BoxGeometry(0.12, 1.0, 1.6), oak, x, 0.5, -0.3);
  const screenMat = new THREE.MeshStandardMaterial({ color: "#0d1d24", emissive: "#2a87c7", emissiveIntensity: 0.9 });
  for (const x of [-2.2, 0, 2.2]) {
    const s = add(new THREE.BoxGeometry(0.85, 0.52, 0.05), screenMat, x, 1.12, -0.05, false);
    s.rotation.x = -0.1;
    add(new THREE.BoxGeometry(0.08, 0.22, 0.08), new THREE.MeshStandardMaterial({ color: "#2a3236" }), x, 0.9, -0.08, false);
    add(new THREE.BoxGeometry(0.5, 0.02, 0.18), new THREE.MeshStandardMaterial({ color: "#2a3236" }), x, 0.8, 0.3, false);
  }
  world.station = { seats: [[-2.2, 0.95], [2.2, 0.95]] }; // where seated staff go (x, z)
  for (const [x, z] of [[-2.2, 0.95], [0, 1.2], [2.2, 0.95]]) officeChair(scene, x, z, Math.PI);

  return fixtures;
}

/** A black swivel chair on a five-star base. `ry` is the way the seat faces. */
export function officeChair(scene, x, z, ry = 0) {
  const g = new THREE.Group();
  const black = new THREE.MeshStandardMaterial({ color: "#1f2326", roughness: 0.7 });
  const seat = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.08, 0.5), black);
  seat.position.y = 0.5;
  const back = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.55, 0.06), black);
  back.position.set(0, 0.85, -0.24);
  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.4, 8), black);
  post.position.y = 0.28;
  g.add(seat, back, post);
  for (let i = 0; i < 5; i++) {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.04, 0.05), black);
    leg.position.set(Math.cos((i * Math.PI * 2) / 5) * 0.16, 0.07, Math.sin((i * Math.PI * 2) / 5) * 0.16);
    leg.rotation.y = -(i * Math.PI * 2) / 5;
    g.add(leg);
  }
  g.traverse((m) => { if (m.isMesh) m.castShadow = true; });
  g.position.set(x, 0, z);
  g.rotation.y = ry;
  scene.add(g);
  return g;
}
