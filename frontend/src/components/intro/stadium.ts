import * as THREE from "three";
import { seeded } from "./math";

/**
 * The ground the proof of concept stands on: pitch with markings, a dark
 * stand behind it and four floodlight masts. Deliberately small; the full
 * stadium (crowd, goal, net, flags) is a later stage.
 */

const PITCH_FRAGMENT = /* glsl */ `#include <color_fragment>
vec2 pp = vPitch;
vec2 q = abs(pp) - vec2(52.5, 34.0);
float inside = step(max(q.x, q.y), 0.0);
// Mown bands across the pitch, darker rough outside the touchlines.
float band = step(0.5, fract(pp.x / 11.0));
vec3 grass = mix(vec3(0.03, 0.125, 0.05), vec3(0.04, 0.16, 0.062), band);
// Two octaves of soft noise: enough to stop the turf reading as a flat fill.
grass *= 0.86 + 0.2 * pitchNoise(pp * 1.7) + 0.12 * pitchNoise(pp * 9.0);
grass = mix(vec3(0.02, 0.075, 0.035), grass, inside);

float w = 0.06;
float aa = fwidth(pp.x) + fwidth(pp.y);
#define LINE(d) (1.0 - smoothstep(w - aa, w + aa, abs(d)))
float outline = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0);
float lines = LINE(outline);
lines = max(lines, LINE(pp.x) * inside);
lines = max(lines, LINE(length(pp) - 9.15));
lines = max(lines, 1.0 - smoothstep(0.16 - aa, 0.16 + aa, length(pp)));
// Penalty and goal areas at both ends.
vec2 e = vec2(abs(pp.x) - 52.5, pp.y);
vec2 b1 = abs(e) - vec2(16.5, 20.16);
vec2 b2 = abs(e) - vec2(5.5, 9.16);
lines = max(lines, LINE(max(b1.x, b1.y)) * inside);
lines = max(lines, LINE(max(b2.x, b2.y)) * inside);
// Far lines shimmer at a grazing angle; fade them out with distance.
lines *= 1.0 - smoothstep(0.25, 0.9, aa);
diffuseColor.rgb = mix(grass, vec3(0.86, 0.9, 0.88), lines * 0.9);`;

const LAMP_FRAGMENT = /* glsl */ `
varying vec2 vUv;
uniform float uPower;
void main() {
  vec2 c = (vUv - 0.5) * vec2(13.0, 8.0);
  float halo = exp(-dot(c, c) * 0.16) * 0.55;
  // 6 x 3 lamps in the middle of the quad.
  vec2 g = c / vec2(0.62, 0.62);
  vec2 cell = abs(fract(g + 0.5) - 0.5);
  float inRack = step(abs(c.x), 1.86) * step(abs(c.y), 0.93);
  float dots = inRack * smoothstep(0.42, 0.12, length(cell));
  float a = (halo + dots * 1.6) * uPower;
  gl_FragColor = vec4(vec3(0.78, 0.88, 1.0) * a, a);
}`;

const PITCH_NOISE = /* glsl */ `
float pitchHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float pitchNoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(pitchHash(i), pitchHash(i + vec2(1, 0)), f.x), mix(pitchHash(i + vec2(0, 1)), pitchHash(i + vec2(1, 1)), f.x), f.y);
}`;

/** Rows of seated spectators as specks of colour. A placeholder for the instanced crowd. */
function crowdTexture(): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 128;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#04060a";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const rnd = seeded(7);
  for (let row = 0; row < 16; row++) {
    for (let x = 0; x < canvas.width; x += 5) {
      if (rnd() < 0.18) continue;
      const v = 10 + Math.floor(rnd() * 24);
      ctx.fillStyle = rnd() < 0.06 ? `rgb(${v + 40},${v + 30},${v})` : `rgb(${v},${v + 4},${v + 12})`;
      ctx.fillRect(x + Math.floor(rnd() * 2), row * 8 + 2, 3, 4);
    }
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = THREE.RepeatWrapping;
  tex.repeat.set(2, 1);
  tex.anisotropy = 4;
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/** The goal the last player scores in, at the +X end of the pitch. */
export const GOAL = { x: 52.5, halfWidth: 3.66, height: 2.44, depth: 2.0 };

const NET_VERTEX = /* glsl */ `
uniform vec3 uHit;
uniform float uPush;
uniform float uT;
varying vec2 vUv;
void main() {
  vUv = uv;
  vec4 world = modelMatrix * vec4(position, 1.0);
  if (uPush > 0.0) {
    // A pure function of the time since the ball struck: the cloth is shoved
    // out where it hit and the dent widens as it travels outward, a ring runs
    // across the panel, the netting is pulled in toward the dent (the stretch),
    // then it springs back past rest, rebounds and settles.
    float d = distance(world.xyz, uHit);
    float t = max(uT, 0.0);
    float spring = (1.0 - exp(-t * 38.0)) * exp(-4.0 * t) * cos(9.0 * t);
    float width = 0.9 + 1.7 * (1.0 - exp(-t * 3.0));
    float dent = exp(-d * d / width);
    float ring = sin(7.0 * (d - 4.2 * t)) * exp(-2.4 * t) * exp(-d * 0.55) * (1.0 - exp(-t * 20.0));
    world.x += uPush * (1.15 * spring * dent + 0.16 * ring);
    vec3 toHit = uHit - world.xyz;
    world.yz += toHit.yz * (0.14 * spring * dent) * uPush;
  }
  gl_Position = projectionMatrix * viewMatrix * world;
}`;
const NET_FRAGMENT = /* glsl */ `
varying vec2 vUv;
uniform vec2 uCells;
void main() {
  vec2 g = abs(fract(vUv * uCells) - 0.5);
  float line = 1.0 - smoothstep(0.38, 0.47, max(g.x, g.y));
  if (line < 0.05) discard;
  gl_FragColor = vec4(vec3(0.86, 0.9, 0.94), line * 0.5);
}`;

export interface Stadium {
  group: THREE.Group;
  /** Net bulge: 0..1 strength at a world point. */
  setNetImpact(strength: number, x: number, y: number, z: number, seconds: number): void;
  /** 0..1 per bank of floodlights (near-left pair, far-right pair). */
  setFloodlights(a: number, b: number): void;
  dispose(): void;
}

export function createStadium(): Stadium {
  const group = new THREE.Group();
  const disposables: { dispose(): void }[] = [];
  const keep = <T extends { dispose(): void }>(d: T) => {
    disposables.push(d);
    return d;
  };

  // ── Pitch ───────────────────────────────────────────────────────────────
  const pitchMat = keep(new THREE.MeshStandardMaterial({ roughness: 0.95, metalness: 0 }));
  pitchMat.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec2 vPitch;")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\nvPitch = (modelMatrix * vec4(position, 1.0)).xz;");
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", `#include <common>\nvarying vec2 vPitch;\n${PITCH_NOISE}`)
      .replace("#include <color_fragment>", PITCH_FRAGMENT);
  };
  pitchMat.customProgramCacheKey = () => "intro-pitch-v1";
  const pitch = new THREE.Mesh(keep(new THREE.PlaneGeometry(190, 130)), pitchMat);
  pitch.rotation.x = -Math.PI / 2;
  pitch.receiveShadow = true;
  group.add(pitch);

  // ── Far stand ───────────────────────────────────────────────────────────
  const crowd = keep(crowdTexture());
  const standMat = keep(new THREE.MeshBasicMaterial({ map: crowd, fog: true }));
  const stand = new THREE.Mesh(keep(new THREE.PlaneGeometry(210, 13)), standMat);
  stand.position.set(0, 5.6, -50);
  stand.rotation.x = 0.42;
  group.add(stand);

  // ── Stand behind the goal ───────────────────────────────────────────────
  const endStand = new THREE.Mesh(keep(new THREE.PlaneGeometry(140, 13)), standMat);
  endStand.position.set(68, 5.6, 0);
  endStand.rotation.y = -Math.PI / 2;
  endStand.rotateX(0.42);
  group.add(endStand);

  // ── Goal ────────────────────────────────────────────────────────────────
  const postMat = keep(new THREE.MeshStandardMaterial({ color: "#f3f5f8", roughness: 0.35 }));
  const postGeo = keep(new THREE.CylinderGeometry(0.06, 0.06, GOAL.height, 12));
  const barGeo = keep(new THREE.CylinderGeometry(0.06, 0.06, GOAL.halfWidth * 2 + 0.12, 12));
  for (const z of [-GOAL.halfWidth, GOAL.halfWidth]) {
    const post = new THREE.Mesh(postGeo, postMat);
    post.position.set(GOAL.x, GOAL.height / 2, z);
    post.castShadow = true;
    group.add(post);
  }
  const bar = new THREE.Mesh(barGeo, postMat);
  bar.rotation.x = Math.PI / 2;
  bar.position.set(GOAL.x, GOAL.height, 0);
  bar.castShadow = true;
  group.add(bar);
  const netUniforms = { uHit: { value: new THREE.Vector3() }, uPush: { value: 0 }, uT: { value: 0 }, uCells: { value: new THREE.Vector2(1, 1) } };
  const netMats: THREE.ShaderMaterial[] = [];
  const net = (w: number, h: number, cells: [number, number], place: (m: THREE.Mesh) => void) => {
    const material = keep(
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        side: THREE.DoubleSide,
        uniforms: { ...netUniforms, uCells: { value: new THREE.Vector2(...cells) } },
        vertexShader: NET_VERTEX,
        fragmentShader: NET_FRAGMENT,
      })
    );
    material.uniforms.uHit = netUniforms.uHit;
    material.uniforms.uPush = netUniforms.uPush;
    material.uniforms.uT = netUniforms.uT;
    netMats.push(material);
    const mesh = new THREE.Mesh(keep(new THREE.PlaneGeometry(w, h, 24, 10)), material);
    place(mesh);
    group.add(mesh);
  };
  // The roof of the net slopes down from the crossbar to a lower back edge.
  const back = GOAL.x + GOAL.depth;
  const drop = 0.6;
  net(GOAL.halfWidth * 2, GOAL.height - drop, [52, 15], (m) => {
    m.position.set(back, (GOAL.height - drop) / 2, 0);
    m.rotation.y = Math.PI / 2;
  });
  net(Math.hypot(GOAL.depth, drop), GOAL.halfWidth * 2, [13, 52], (m) => {
    m.position.set(GOAL.x + GOAL.depth / 2, GOAL.height - drop / 2, 0);
    m.rotation.x = -Math.PI / 2;
    m.rotateOnWorldAxis(new THREE.Vector3(0, 0, 1), -Math.atan2(drop, GOAL.depth));
  });
  for (const z of [-GOAL.halfWidth, GOAL.halfWidth]) {
    net(GOAL.depth, GOAL.height, [12, 15], (m) => m.position.set(GOAL.x + GOAL.depth / 2, GOAL.height / 2, z));
  }

  // ── Floodlights ─────────────────────────────────────────────────────────
  const lampGeo = keep(new THREE.PlaneGeometry(13, 8));
  const beamGeo = keep(new THREE.ConeGeometry(17, 62, 24, 1, true));
  beamGeo.translate(0, -31, 0);
  const banks: { lamp: THREE.ShaderMaterial; beam: THREE.ShaderMaterial }[] = [];
  const masts: [x: number, bank: number][] = [
    [-34, 0],
    [-11, 0],
    [12, 1],
    [35, 1],
  ];
  for (const [x, bank] of masts) {
    if (!banks[bank]) {
      banks[bank] = {
        // A rack of lamps drawn as a grid of soft dots inside a wider glow.
        lamp: keep(
          new THREE.ShaderMaterial({
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
            uniforms: { uPower: { value: 0 } },
            vertexShader: "varying vec2 vUv;\nvoid main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
            fragmentShader: LAMP_FRAGMENT,
          })
        ),
        beam: keep(
          new THREE.ShaderMaterial({
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
            side: THREE.DoubleSide,
            uniforms: { uPower: { value: 0 } },
            vertexShader: "varying vec2 vUv;\nvoid main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
            fragmentShader:
              "varying vec2 vUv;\nuniform float uPower;\nvoid main(){ float a = pow(vUv.y, 2.4) * 0.11 * uPower; gl_FragColor = vec4(vec3(0.72, 0.84, 1.0) * a, a); }",
          })
        ),
      };
    }
    const lamp = new THREE.Mesh(lampGeo, banks[bank].lamp);
    lamp.position.set(x, 15.5, -56);
    lamp.lookAt(x * 0.2, 0, 0);
    group.add(lamp);
    // The cone is a stand-in for light scattering in the haze, not real volumetrics.
    const beam = new THREE.Mesh(beamGeo, banks[bank].beam);
    beam.position.copy(lamp.position);
    beam.lookAt(x * 0.2, 0, 0);
    beam.rotateX(-Math.PI / 2);
    group.add(beam);
  }

  return {
    group,
    setNetImpact(strength, x, y, z, seconds) {
      netUniforms.uPush.value = strength;
      netUniforms.uT.value = seconds;
      netUniforms.uHit.value.set(x, y, z);
    },
    setFloodlights(a, b) {
      [a, b].forEach((power, i) => {
        banks[i].lamp.uniforms.uPower.value = power;
        banks[i].beam.uniforms.uPower.value = power;
      });
    },
    dispose() {
      for (const d of disposables) d.dispose();
    },
  };
}
