// Renderer, camera, controls, lighting and the room itself (floor, walls,
// nurse station). Beds live in beds.js. Units are metres; +x runs along the
// unit, z across it, y up.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

export const UNIT = { length: 44, width: 22, wall: 3.2 };

export function createWorld(container) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.appendChild(renderer.domElement);

  const labels = new CSS2DRenderer();
  labels.domElement.style.position = "absolute";
  labels.domElement.style.inset = "0";
  labels.domElement.style.pointerEvents = "none";
  container.appendChild(labels.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#0b1418");
  scene.fog = new THREE.Fog("#0b1418", 45, 95);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 300);
  camera.position.set(0, 30, 34);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0, 0);
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI * 0.47;
  controls.minDistance = 4;
  controls.maxDistance = 80;

  // light: dim ambient, cool ceiling panels, one shadow-casting key light
  scene.add(new THREE.HemisphereLight("#bcd7ff", "#1a2a30", 0.55));
  const key = new THREE.DirectionalLight("#e8f2ff", 1.05);
  key.position.set(-14, 26, 12);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -28, right: 28, top: 18, bottom: -18, near: 1, far: 70 });
  key.shadow.bias = -0.0004;
  scene.add(key);

  buildRoom(scene);

  // soft glow on rings, beams and monitors
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.38, 0.6, 1.0);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    renderer.setSize(w, h);
    composer.setSize(w, h);
    labels.setSize(w, h);
    camera.aspect = w / h;
    // keep the scene centred in the part of the screen the panel doesn't cover
    const panel = document.getElementById("panel");
    if (w > 860 && panel) camera.setViewOffset(w, h, (panel.offsetWidth + 16) / 2, 0, w, h);
    else camera.setViewOffset(w, h, 0, h * 0.2, w, h);
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);
  resize();

  const frameFns = new Set();
  const clock = new THREE.Clock();
  renderer.setAnimationLoop(() => {
    const dt = clock.getDelta(), t = clock.elapsedTime;
    for (const fn of frameFns) fn(dt, t);
    controls.update();
    // zoomed out: bed labels switch to a compact form so they don't overlap
    container.classList.toggle("far", camera.position.distanceTo(controls.target) > 26);
    composer.render();
    labels.render(scene, camera);
  });

  return { THREE, renderer, scene, camera, controls, onFrame: (fn) => frameFns.add(fn) };
}

function floorTexture() {
  // subtle vinyl tiles drawn on a canvas, so no image files are needed
  const c = document.createElement("canvas");
  c.width = c.height = 512;
  const g = c.getContext("2d");
  g.fillStyle = "#1b2b31";
  g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 4000; i++) {
    g.fillStyle = `rgba(255,255,255,${Math.random() * 0.025})`;
    g.fillRect(Math.random() * 512, Math.random() * 512, 2, 2);
  }
  g.strokeStyle = "#24383f";
  g.lineWidth = 3;
  g.strokeRect(0, 0, 512, 512);
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(UNIT.length / 2, UNIT.width / 2);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  return tex;
}

function buildRoom(scene) {
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(UNIT.length, UNIT.width),
    new THREE.MeshStandardMaterial({ map: floorTexture(), roughness: 0.55, metalness: 0.05 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  // corridor stripe down the middle
  const stripe = new THREE.Mesh(
    new THREE.PlaneGeometry(UNIT.length - 2, 0.12),
    new THREE.MeshBasicMaterial({ color: "#2f5d6b" }),
  );
  stripe.rotation.x = -Math.PI / 2;
  stripe.position.y = 0.005;
  for (const z of [-2.4, 2.4]) {
    const s = stripe.clone();
    s.position.z = z;
    scene.add(s);
  }

  // low walls on three sides, back wall with a window band
  const wallMat = new THREE.MeshStandardMaterial({ color: "#22343b", roughness: 0.85 });
  const mk = (w, d, x, z) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, UNIT.wall, d), wallMat);
    m.position.set(x, UNIT.wall / 2, z);
    m.receiveShadow = true;
    scene.add(m);
  };
  mk(UNIT.length, 0.25, 0, -UNIT.width / 2);
  mk(0.25, UNIT.width, -UNIT.length / 2, 0);
  mk(0.25, UNIT.width, UNIT.length / 2, 0);
  const glow = new THREE.Mesh(
    new THREE.PlaneGeometry(UNIT.length - 4, 0.5),
    new THREE.MeshBasicMaterial({ color: "#16404f" }),
  );
  glow.position.set(0, 2.2, -UNIT.width / 2 + 0.14);
  scene.add(glow);

  // headwall behind each row: a rail with a warm reading-light strip
  for (const z of [-8.9, 5.1]) {
    const rail = new THREE.Mesh(new THREE.BoxGeometry(UNIT.length - 3, 1.5, 0.18), new THREE.MeshStandardMaterial({ color: "#2c434b", roughness: 0.7 }));
    rail.position.set(0, 0.95, z);
    rail.castShadow = rail.receiveShadow = true;
    scene.add(rail);
    const strip = new THREE.Mesh(new THREE.BoxGeometry(UNIT.length - 3.4, 0.05, 0.06), new THREE.MeshBasicMaterial({ color: "#ffd9a0", toneMapped: false }));
    strip.position.set(0, 1.74, z + 0.07);
    scene.add(strip);
  }

  // nurse station in the centre of the corridor
  const station = new THREE.Group();
  const desk = new THREE.Mesh(
    new THREE.BoxGeometry(7, 1.05, 1.5),
    new THREE.MeshStandardMaterial({ color: "#aebcc0", roughness: 0.5 }),
  );
  desk.position.y = 0.525;
  desk.castShadow = desk.receiveShadow = true;
  station.add(desk);
  const top = new THREE.Mesh(new THREE.BoxGeometry(7.3, 0.08, 1.8), new THREE.MeshStandardMaterial({ color: "#3a5a64" }));
  top.position.y = 1.09;
  station.add(top);
  for (const x of [-2.2, 0, 2.2]) {
    const screen = new THREE.Mesh(
      new THREE.BoxGeometry(1.1, 0.7, 0.06),
      new THREE.MeshStandardMaterial({ color: "#0d1d24", emissive: "#2a87c7", emissiveIntensity: 0.6 }),
    );
    screen.position.set(x, 1.55, -0.3);
    screen.rotation.x = -0.12;
    station.add(screen);
  }
  scene.add(station);
}
