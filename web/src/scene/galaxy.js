// The night sky behind the building: a drifting, twinkling starfield.
// Shader adapted from the Galaxy background in React Bits by David Haz
// (https://reactbits.dev/backgrounds/galaxy, MIT + Commons Clause), ported
// from a standalone WebGL canvas to a three.js material so it renders inside
// the same scene (behind the ward) instead of as a second canvas.
import * as THREE from "three";

const FRAGMENT = `
precision highp float;
uniform float uTime;
uniform vec2 uResolution;
uniform float uGloss;
uniform float uDepth;
uniform float uDensity;
uniform float uHueShift;
uniform float uSpeed;
uniform float uStarGlow;
uniform float uFlareGain;
uniform float uSaturation;
uniform float uTwinkleIntensity;
uniform float uRotationAngle;
uniform vec2 uPan;
uniform vec3 uBackground;

#define STAR_COLOR_CUTOFF 0.2
#define MAT45 mat2(0.7071, -0.7071, 0.7071, 0.7071)
#define PERIOD 3.0
#define LAYERS 4

float Hash21(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float tri(float x) { return abs(fract(x) * 2.0 - 1.0); }
float tris(float x) { float t = fract(x); return 1.0 - smoothstep(0.0, 1.0, abs(2.0 * t - 1.0)); }
float trisn(float x) { float t = fract(x); return 2.0 * (1.0 - smoothstep(0.0, 1.0, abs(2.0 * t - 1.0))) - 1.0; }
vec3 hsv2rgb(vec3 c) {
  vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
  vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
  return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}
float Star(vec2 uv, float flare) {
  float d = length(uv);
  float m = uStarGlow / d;
  float rays = smoothstep(0.0, 1.0, 1.0 - abs(uv.x * uv.y * 1000.0));
  m += rays * flare * uFlareGain;
  uv *= MAT45;
  rays = smoothstep(0.0, 1.0, 1.0 - abs(uv.x * uv.y * 1000.0));
  m += rays * 0.3 * flare * uFlareGain;
  m *= smoothstep(1.0, 0.2, d);
  return m;
}
vec3 StarLayer(vec2 uv) {
  vec3 col = vec3(0.0);
  vec2 gv = fract(uv) - 0.5;
  vec2 id = floor(uv);
  for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
    vec2 offset = vec2(float(x), float(y));
    vec2 si = id + offset;
    float seed = Hash21(si);
    float size = fract(seed * 345.32);
    float glossLocal = tri(uGloss / (PERIOD * seed + 1.0));
    float flareSize = smoothstep(0.9, 1.0, size) * glossLocal;
    float red = smoothstep(STAR_COLOR_CUTOFF, 1.0, Hash21(si + 1.0)) + STAR_COLOR_CUTOFF;
    float blu = smoothstep(STAR_COLOR_CUTOFF, 1.0, Hash21(si + 3.0)) + STAR_COLOR_CUTOFF;
    float grn = min(red, blu) * seed;
    vec3 base = vec3(red, grn, blu);
    float hue = atan(base.g - base.r, base.b - base.r) / (2.0 * 3.14159) + 0.5;
    hue = fract(hue + uHueShift / 360.0);
    float sat = length(base - vec3(dot(base, vec3(0.299, 0.587, 0.114)))) * uSaturation;
    float val = max(max(base.r, base.g), base.b);
    base = hsv2rgb(vec3(hue, sat, val));
    vec2 pad = vec2(tris(seed * 34.0 + uTime * uSpeed / 10.0), tris(seed * 38.0 + uTime * uSpeed / 30.0)) - 0.5;
    float star = Star(gv - offset - pad, flareSize);
    float twinkle = trisn(uTime * uSpeed + seed * 6.2831) * 0.5 + 1.0;
    twinkle = mix(1.0, twinkle, uTwinkleIntensity);
    col += star * twinkle * size * base;
  }
  return col;
}
void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y + uPan;
  float a = uRotationAngle;
  uv = mat2(cos(a), -sin(a), sin(a), cos(a)) * uv;
  vec3 col = vec3(0.0);
  for (int k = 0; k < LAYERS; k++) {
    float i = float(k) / float(LAYERS);
    float depth = fract(i + uDepth);
    float scale = mix(20.0 * uDensity, 0.5 * uDensity, depth);
    float fade = depth * smoothstep(1.0, 0.9, depth);
    col += StarLayer(uv * scale + vec2(i * 453.32)) * fade;
  }
  gl_FragColor = vec4(uBackground + col, 1.0);
}`;

/** Adds the sky to the scene. It follows the camera, so it is always behind everything. */
export function createGalaxy(world, { density = 1, hueShift = 190, saturation = 0.35, glowIntensity = 0.3, twinkleIntensity = 0.3,
  rotationSpeed = 0.03, starSpeed = 0.35, speed = 1, flareIntensity = 0.12, starGlow = 0.6 } = {}) {
  const { scene, camera, renderer } = world;
  const uniforms = {
    uTime: { value: 0 }, uResolution: { value: new THREE.Vector2(1, 1) }, uGloss: { value: 0 }, uDepth: { value: 0 },
    uDensity: { value: density }, uHueShift: { value: hueShift }, uSpeed: { value: speed }, uStarGlow: { value: 0.05 * glowIntensity * starGlow }, // smaller halo round each star
    uFlareGain: { value: glowIntensity * flareIntensity }, uSaturation: { value: saturation }, uTwinkleIntensity: { value: twinkleIntensity },
    uRotationAngle: { value: 0 }, uPan: { value: new THREE.Vector2() }, uBackground: { value: new THREE.Color("#030a10") },
  };
  const sky = new THREE.Mesh(new THREE.SphereGeometry(200, 24, 16), new THREE.ShaderMaterial({
    uniforms, fragmentShader: FRAGMENT, side: THREE.BackSide, depthWrite: false, fog: false,
    vertexShader: "void main() { gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
  }));
  sky.renderOrder = -1000;
  sky.frustumCulled = false;
  scene.add(sky);
  const size = new THREE.Vector2();
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  world.onFrame((dt) => {
    sky.position.copy(camera.position);
    renderer.getDrawingBufferSize(size);
    uniforms.uResolution.value.copy(size);
    if (reduce) return;
    const flight = starSpeed / 10;
    uniforms.uTime.value += dt;
    uniforms.uGloss.value += dt * flight;
    uniforms.uDepth.value += dt * flight * speed;
    uniforms.uRotationAngle.value += dt * rotationSpeed;
    // a little parallax as the camera orbits, so the sky feels far away rather than painted on
    const az = Math.atan2(camera.position.x - 8, camera.position.z);
    uniforms.uPan.value.set(az * 0.12, camera.position.y * 0.002);
  });
  return sky;
}
