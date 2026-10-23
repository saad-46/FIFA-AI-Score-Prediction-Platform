import * as THREE from "three";
import type { Kit, ShirtPattern } from "../profiles";

const PATTERN_ID: Record<ShirtPattern, number> = { solid: 0, stripes: 1, checker: 2 };

/** Cell size of one digit in the number atlas, in pixels. */
const CELL_W = 128;
const CELL_H = 192;

/**
 * The ten digits on one small texture: red is the digit, green its outline.
 * Drawn once with the page's display face (redrawn if that face finishes
 * loading afterwards) and shared by every shirt in the scene.
 */
export function createNumberAtlas(): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = CELL_W * 10;
  canvas.height = CELL_H;
  const ctx = canvas.getContext("2d")!;
  const texture = new THREE.CanvasTexture(canvas);
  texture.generateMipmaps = true;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.anisotropy = 4;
  const family = () => {
    const probe = document.createElement("span");
    probe.className = "font-display";
    document.body.appendChild(probe);
    const resolved = getComputedStyle(probe).fontFamily;
    probe.remove();
    return resolved;
  };
  const draw = () => {
    const font = `800 ${Math.round(CELL_H * 0.78)}px ${family()}`;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.font = font;
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    ctx.lineJoin = "round";
    for (let d = 0; d < 10; d++) {
      const cx = d * CELL_W + CELL_W / 2;
      const base = CELL_H * 0.86;
      ctx.globalCompositeOperation = "source-over";
      ctx.lineWidth = 11;
      ctx.strokeStyle = "#00ff00";
      ctx.fillStyle = "#00ff00";
      ctx.strokeText(String(d), cx, base);
      ctx.fillText(String(d), cx, base);
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = "#ff0000";
      ctx.fillText(String(d), cx, base);
    }
    ctx.globalCompositeOperation = "source-over";
    texture.needsUpdate = true;
  };
  draw();
  void document.fonts?.load(`800 100px ${family()}`).then(draw, () => {});
  return texture;
}

const NOISE_GLSL = /* glsl */ `
float introHash(vec3 p) {
  p = fract(p * 0.3183099 + vec3(0.1, 0.2, 0.3));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float introNoise(vec3 x) {
  vec3 i = floor(x);
  vec3 f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(introHash(i), introHash(i + vec3(1, 0, 0)), f.x), mix(introHash(i + vec3(0, 1, 0)), introHash(i + vec3(1, 1, 0)), f.x), f.y),
    mix(mix(introHash(i + vec3(0, 0, 1)), introHash(i + vec3(1, 0, 1)), f.x), mix(introHash(i + vec3(0, 1, 1)), introHash(i + vec3(1, 1, 1)), f.x), f.y),
    f.z
  );
}
`;

export { NOISE_GLSL };

/**
 * The shirt number, drawn from the digit atlas on the shirt's own surface:
 * `vNum` is each vertex's position in the model's rest pose (metres), so the
 * plate rides on the cloth as the body moves. The model faces +Z. Seen from the
 * front the figure's right is +X; from behind it is -X, so the back is mirrored
 * to read correctly. Back: large, high between the shoulder blades. Front: small,
 * centre chest.
 */
const NUMBER_GLSL = /* glsl */ `
varying vec3 vNum;
uniform sampler2D uNumAtlas;
uniform vec2 uNum[2];
uniform vec3 uNumInk[2];
uniform vec3 uNumEdge[2];
vec3 introNumber(vec3 shirt, int slot) {
  float front = step(0.0, vNum.z);
  float cy = mix(0.72, 0.79, front);
  float h = mix(0.36, 0.19, front);
  float ux = mix(-vNum.x, vNum.x, front);
  vec2 dg = slot == 0 ? uNum[0] : uNum[1];
  float n = dg.x < 0.0 ? 1.0 : 2.0;
  float u = ux / (h * 0.6 * n) + 0.5;
  float v = (vNum.y - cy) / h + 0.5;
  // Sampled everywhere (uniform control flow keeps the mip level right at the plate's edge) and masked after.
  float inside = step(0.0, u) * step(u, 1.0) * step(0.0, v) * step(v, 1.0);
  float k = floor(clamp(u, 0.0, 0.999) * n);
  float digit = (n > 1.5 && k < 0.5) ? dg.x : dg.y;
  // Kept inside the cell: the filter must not reach the neighbouring digit.
  float fu = clamp(fract(clamp(u, 0.0, 0.999) * n), 0.04, 0.96);
  vec4 g = texture2D(uNumAtlas, vec2((digit + fu) / 10.0, clamp(v, 0.02, 0.98))) * inside;
  vec3 edge = slot == 0 ? uNumEdge[0] : uNumEdge[1];
  vec3 ink = slot == 0 ? uNumInk[0] : uNumInk[1];
  return mix(mix(shirt, edge, g.g), ink, g.r);
}`;

interface KitUniforms {
  uShirt1: THREE.IUniform<THREE.Color[]>;
  uShirt2: THREE.IUniform<THREE.Color[]>;
  uShorts: THREE.IUniform<THREE.Color[]>;
  uSocks: THREE.IUniform<THREE.Color[]>;
  uBoots: THREE.IUniform<THREE.Color[]>;
  uPattern: THREE.IUniform<number[]>;
  uSkin: THREE.IUniform<THREE.Color>;
  uSweep: THREE.IUniform<number>;
  uNumAtlas: THREE.IUniform<THREE.Texture | null>;
  uNum: THREE.IUniform<THREE.Vector2[]>;
  uNumInk: THREE.IUniform<THREE.Color[]>;
  uNumEdge: THREE.IUniform<THREE.Color[]>;
}

/**
 * The figure's surface: skin and kit on one material.
 *
 * Two kits are loaded at once (slot 0 outgoing, slot 1 incoming). `uSweep`
 * moves a noisy boundary from the boots to the collar; below it the incoming
 * kit shows. Stripes and checkers are computed in the shader, so no texture is
 * swapped at any point.
 */
export class KitMaterial extends THREE.MeshStandardMaterial {
  private readonly u: KitUniforms;
  private readonly skinA = new THREE.Color();
  private readonly skinB = new THREE.Color();

  /** `numbers` is the digit atlas (createNumberAtlas): the shirt then carries its number, front and back. */
  constructor(numbers: THREE.Texture | null = null) {
    super({ roughness: 0.78, metalness: 0 });
    const pair = () => [new THREE.Color(), new THREE.Color()];
    this.u = {
      uShirt1: { value: pair() },
      uShirt2: { value: pair() },
      uShorts: { value: pair() },
      uSocks: { value: pair() },
      uBoots: { value: pair() },
      uPattern: { value: [0, 0] },
      uSkin: { value: new THREE.Color() },
      uSweep: { value: 0 },
      uNumAtlas: { value: numbers },
      uNum: { value: [new THREE.Vector2(-1, 0), new THREE.Vector2(-1, 0)] },
      uNumInk: { value: pair() },
      uNumEdge: { value: pair() },
    };
    const withNumbers = numbers !== null;

    this.onBeforeCompile = (shader) => {
      Object.assign(shader.uniforms, this.u);
      shader.vertexShader = shader.vertexShader
        .replace("#include <common>", "#include <common>\nattribute float aPart;\nattribute vec3 aPat;\nvarying float vPart;\nvarying vec3 vPat;" + (withNumbers ? "\nattribute vec3 aNum;\nvarying vec3 vNum;" : ""))
        .replace("#include <begin_vertex>", "#include <begin_vertex>\nvPart = aPart;\nvPat = aPat;" + (withNumbers ? "\nvNum = aNum;" : ""));
      shader.fragmentShader = shader.fragmentShader
        .replace(
          "#include <common>",
          /* glsl */ `#include <common>
varying float vPart;
varying vec3 vPat;
uniform vec3 uShirt1[2];
uniform vec3 uShirt2[2];
uniform vec3 uShorts[2];
uniform vec3 uSocks[2];
uniform vec3 uBoots[2];
uniform float uPattern[2];
uniform vec3 uSkin;
uniform float uSweep;
float introSweepGlow;
${NOISE_GLSL}
${withNumbers ? NUMBER_GLSL : "vec3 introNumber(vec3 shirt, int slot) { return shirt; }"}
vec3 introKit(vec3 c1, vec3 c2, float pattern, vec3 shorts, vec3 socks, vec3 boots, int slot) {
  vec3 shirt = c1;
  if (pattern > 1.5) {
    vec2 cell = floor(vPat.xy * 11.0);
    shirt = mix(c1, c2, mod(cell.x + cell.y, 2.0));
  } else if (pattern > 0.5) {
    float s = fract(vPat.x * 13.0 + 0.5);
    float aa = fwidth(vPat.x * 13.0);
    shirt = mix(c1, c2, smoothstep(0.5 - aa, 0.5 + aa, s) * (1.0 - smoothstep(1.0 - aa, 1.0, s)));
  }
  if (vPart < 1.5) return introNumber(shirt, slot);
  if (vPart < 2.5) return shorts;
  if (vPart < 3.5) return socks;
  return boots;
}`
        )
        .replace(
          "#include <color_fragment>",
          /* glsl */ `#include <color_fragment>
introSweepGlow = 0.0;
if (vPart < 0.5) {
  diffuseColor.rgb = uSkin;
} else {
  vec3 kitA = introKit(uShirt1[0], uShirt2[0], uPattern[0], uShorts[0], uSocks[0], uBoots[0], 0);
  vec3 kitB = introKit(uShirt1[1], uShirt2[1], uPattern[1], uShorts[1], uSocks[1], uBoots[1], 1);
  // Height along the body, 0 at the sole and 1 at the crown, with a ragged edge.
  float h = vPat.y + (introNoise(vPat * 46.0) - 0.5) * 0.09;
  float edge = uSweep * 1.24 - 0.12;
  float d = edge - h;
  diffuseColor.rgb = mix(kitA, kitB, smoothstep(-0.008, 0.008, d));
  float live = step(0.001, uSweep) * step(uSweep, 0.999);
  introSweepGlow = live * pow(1.0 - clamp(abs(d) / 0.03, 0.0, 1.0), 2.0);
}`
        )
        .replace("#include <emissivemap_fragment>", "#include <emissivemap_fragment>\ntotalEmissiveRadiance += vec3(0.75, 0.95, 1.0) * introSweepGlow * 1.6;");
    };
    this.customProgramCacheKey = () => (withNumbers ? "intro-kit-v1-numbers" : "intro-kit-v1");
  }

  private setSlot(slot: 0 | 1, kit: Kit) {
    this.u.uShirt1.value[slot].set(kit.shirt);
    this.u.uShirt2.value[slot].set(kit.shirt2);
    this.u.uShorts.value[slot].set(kit.shorts);
    this.u.uSocks.value[slot].set(kit.socks);
    this.u.uBoots.value[slot].set(kit.boots);
    this.u.uPattern.value[slot] = PATTERN_ID[kit.pattern];
    const tens = Math.floor(kit.number / 10);
    this.u.uNum.value[slot].set(tens > 0 ? tens : -1, kit.number % 10);
    this.u.uNumInk.value[slot].set(kit.numberInk);
    this.u.uNumEdge.value[slot].set(kit.numberEdge);
  }

  /** `t` is 0 for all of `a` and 1 for all of `b`. */
  setBlend(a: Kit, b: Kit, skinA: string, skinB: string, t: number) {
    this.setSlot(0, a);
    this.setSlot(1, b);
    this.u.uSweep.value = t;
    this.u.uSkin.value.copy(this.skinA.set(skinA)).lerp(this.skinB.set(skinB), t);
  }
}
