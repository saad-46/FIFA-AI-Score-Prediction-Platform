import * as THREE from "three";
import type { BodyShape } from "../profiles";

/**
 * The procedural body.
 *
 * One generator turns a BodyShape into vertex positions. Run for every
 * profile, it always emits the same vertices in the same order, so the
 * results differ only in where the vertices sit. The first profile becomes
 * the mesh and each further profile becomes a morph target: the change from
 * one player to the next is real interpolation of one shared mesh, bound to
 * one skeleton.
 */

export const BONE = {
  HIPS: 0,
  SPINE: 1,
  CHEST: 2,
  NECK: 3,
  HEAD: 4,
  UARM_L: 5,
  FARM_L: 6,
  HAND_L: 7,
  UARM_R: 8,
  FARM_R: 9,
  HAND_R: 10,
  THIGH_L: 11,
  SHIN_L: 12,
  FOOT_L: 13,
  THIGH_R: 14,
  SHIN_R: 15,
  FOOT_R: 16,
} as const;

export const BONE_COUNT = 17;
export const BONE_PARENT = [-1, 0, 1, 2, 3, 2, 5, 6, 2, 8, 9, 0, 11, 12, 0, 14, 15] as const;

/** Which material region a vertex belongs to. */
export const PART = { SKIN: 0, SHIRT: 1, SHORTS: 2, SOCKS: 3, BOOTS: 4 } as const;

const SEG = 14;

type Vec = readonly [number, number, number];
/** bone, weight, [bone, weight] */
type Weights = readonly number[];

/** Joint positions and the few measurements the rig needs, for one shape. */
export interface BodyLayout {
  /** BONE_COUNT * 3, in the figure's own space: +Y up, +Z forward, +X its left. */
  joints: Float32Array;
  headCenterY: number;
  head: Vec;
  /** Sole reference points relative to the ankle joint. */
  ankle: number;
  heel: number;
  toe: number;
}

class Builder {
  pos: number[] = [];
  idx: number[] = [];
  skinIndex: number[] = [];
  skinWeight: number[] = [];
  part: number[] = [];
  private centers: Vec[] = [];
  private us: Vec[] = [];
  private vs: Vec[] = [];

  private vertex(p: Vec, w: Weights, part: number) {
    this.pos.push(p[0], p[1], p[2]);
    this.skinIndex.push(w[0], w[2] ?? 0, 0, 0);
    this.skinWeight.push(w[1], w[3] ?? 0, 0, 0);
    this.part.push(part);
    return this.pos.length / 3 - 1;
  }

  /** An ellipse of SEG vertices: centre + u*cos + v*sin. Returns its ring id. */
  ring(c: Vec, u: Vec, v: Vec, w: Weights, part: number): number {
    const start = this.pos.length / 3;
    for (let i = 0; i < SEG; i++) {
      const a = (i / SEG) * Math.PI * 2;
      const ca = Math.cos(a);
      const sa = Math.sin(a);
      this.vertex([c[0] + u[0] * ca + v[0] * sa, c[1] + u[1] * ca + v[1] * sa, c[2] + u[2] * ca + v[2] * sa], w, part);
    }
    this.centers[start] = c;
    this.us[start] = u;
    this.vs[start] = v;
    return start;
  }

  /** Skin between two rings, wound so the surface faces outward. */
  connect(a: number, b: number) {
    const ca = this.centers[a];
    const cb = this.centers[b];
    const u = this.us[a];
    const v = this.vs[a];
    const ax: Vec = [cb[0] - ca[0], cb[1] - ca[1], cb[2] - ca[2]];
    // (axis x v) should point along u for the default winding.
    const nx = ax[1] * v[2] - ax[2] * v[1];
    const ny = ax[2] * v[0] - ax[0] * v[2];
    const nz = ax[0] * v[1] - ax[1] * v[0];
    const flip = nx * u[0] + ny * u[1] + nz * u[2] < 0;
    for (let i = 0; i < SEG; i++) {
      const j = (i + 1) % SEG;
      if (flip) this.idx.push(a + i, a + j, b + i, a + j, b + j, b + i);
      else this.idx.push(a + i, b + i, a + j, a + j, b + i, b + j);
    }
  }

  /** Closes a ring with a fan facing `dir`. */
  cap(r: number, dir: Vec, w: Weights, part: number) {
    const c = this.centers[r];
    const u = this.us[r];
    const v = this.vs[r];
    const center = this.vertex(c, w, part);
    const nx = u[1] * v[2] - u[2] * v[1];
    const ny = u[2] * v[0] - u[0] * v[2];
    const nz = u[0] * v[1] - u[1] * v[0];
    const flip = nx * dir[0] + ny * dir[1] + nz * dir[2] < 0;
    for (let i = 0; i < SEG; i++) {
      const j = (i + 1) % SEG;
      if (flip) this.idx.push(center, r + j, r + i);
      else this.idx.push(center, r + i, r + j);
    }
  }

  /** A run of horizontal rings joined into one tube. `rows` are [y, rx, rz, weights, zOffset?]. */
  tube(x: number, rows: readonly (readonly [number, number, number, Weights, number?])[], part: number): number[] {
    const ids = rows.map(([y, rx, rz, w, dz]) => this.ring([x, y, dz ?? 0], [rx, 0, 0], [0, 0, rz], w, part));
    for (let i = 0; i < ids.length - 1; i++) this.connect(ids[i], ids[i + 1]);
    return ids;
  }
}

export function layoutBody(s: BodyShape): BodyLayout {
  const H = s.height;
  const ankleY = 0.055 * H;
  const hipY = s.legFrac * H;
  const kneeY = ankleY + (hipY - ankleY) * 0.49;
  const chinY = H - 2 * s.headY;
  const neckBaseY = chinY - 0.032 * H;
  const shoulderY = neckBaseY - 0.03 * H;
  const hipsJ = hipY + 0.035 * H;
  const torso = neckBaseY - hipsJ;
  const upper = 0.172 * H * s.arm;
  const fore = 0.15 * H * s.arm;
  const hx = s.hipHalf * 0.56;
  const sx = s.shoulderHalf;

  const j = new Float32Array(BONE_COUNT * 3);
  const set = (b: number, x: number, y: number, z = 0) => {
    j[b * 3] = x;
    j[b * 3 + 1] = y;
    j[b * 3 + 2] = z;
  };
  set(BONE.HIPS, 0, hipsJ);
  set(BONE.SPINE, 0, hipsJ + 0.24 * torso);
  set(BONE.CHEST, 0, hipsJ + 0.56 * torso);
  set(BONE.NECK, 0, neckBaseY);
  set(BONE.HEAD, 0, chinY + 0.35 * s.headY);
  for (const [sg, ua, fa, hand, th, sh, ft] of [
    [1, BONE.UARM_L, BONE.FARM_L, BONE.HAND_L, BONE.THIGH_L, BONE.SHIN_L, BONE.FOOT_L],
    [-1, BONE.UARM_R, BONE.FARM_R, BONE.HAND_R, BONE.THIGH_R, BONE.SHIN_R, BONE.FOOT_R],
  ] as const) {
    set(ua, sg * sx, shoulderY);
    set(fa, sg * sx, shoulderY - upper);
    set(hand, sg * sx, shoulderY - upper - fore);
    set(th, sg * hx, hipY);
    set(sh, sg * hx, kneeY);
    set(ft, sg * hx, ankleY);
  }
  return {
    joints: j,
    headCenterY: H - s.headY,
    head: [s.headX, s.headY, s.headZ],
    ankle: ankleY,
    heel: -0.04 * H,
    toe: 0.115 * H,
  };
}

function generate(s: BodyShape, b: Builder) {
  const H = s.height;
  const L = layoutBody(s);
  const jy = (bone: number) => L.joints[bone * 3 + 1];
  const hipsJ = jy(BONE.HIPS);
  const neckBaseY = jy(BONE.NECK);
  const shoulderY = jy(BONE.UARM_L);
  const hipY = jy(BONE.THIGH_L);
  const kneeY = jy(BONE.SHIN_L);
  const ankleY = L.ankle;
  const torso = neckBaseY - hipsJ;
  const chinY = H - 2 * s.headY;
  const waistY = hipsJ + 0.22 * torso;
  const { HIPS, SPINE, CHEST, NECK, HEAD } = BONE;

  // Shorts: pelvis up to the waist.
  const shorts = b.tube(
    0,
    [
      [hipY - 0.04 * H, s.hipHalf * 0.78, s.hipDepth * 0.85, [HIPS, 1]],
      [hipY + 0.01 * H, s.hipHalf, s.hipDepth, [HIPS, 1]],
      [hipsJ + 0.03 * H, (s.hipHalf + s.waistHalf) / 2, (s.hipDepth + s.waistDepth) / 2, [HIPS, 1]],
      [waistY, s.waistHalf * 1.02, s.waistDepth * 1.02, [HIPS, 0.5, SPINE, 0.5]],
    ],
    PART.SHORTS
  );
  b.cap(shorts[0], [0, -1, 0], [HIPS, 1], PART.SHORTS);

  // Shirt: waist up to the collar.
  b.tube(
    0,
    [
      [waistY - 0.012 * H, s.waistHalf * 1.06, s.waistDepth * 1.07, [HIPS, 0.5, SPINE, 0.5]],
      [hipsJ + 0.4 * torso, s.waistHalf * 0.45 + s.chestHalf * 0.58, s.waistDepth * 0.4 + s.chestDepth * 0.62, [SPINE, 0.6, CHEST, 0.4]],
      [hipsJ + 0.64 * torso, s.chestHalf, s.chestDepth, [CHEST, 1], 0.006],
      [shoulderY - 0.012 * H, s.shoulderHalf * 0.96, s.chestDepth * 0.9, [CHEST, 1]],
      [shoulderY + 0.026 * H, s.shoulderHalf * 0.6, s.chestDepth * 0.7, [CHEST, 1]],
      [neckBaseY + 0.008 * H, s.neck * 1.4, s.neck * 1.35, [CHEST, 0.6, NECK, 0.4]],
    ],
    PART.SHIRT
  );

  // Neck.
  b.tube(
    0,
    [
      [neckBaseY - 0.012 * H, s.neck * 1.08, s.neck * 1.05, [CHEST, 0.5, NECK, 0.5]],
      [chinY + 0.4 * s.headY, s.neck, s.neck, [NECK, 0.5, HEAD, 0.5]],
    ],
    PART.SKIN
  );

  // Head: an ellipsoid with a narrower, slightly forward jaw.
  const headC = L.headCenterY;
  const RINGS = 9;
  const headRows: [number, number, number, Weights, number][] = [];
  for (let k = 0; k < RINGS; k++) {
    const th = -Math.PI / 2 + (Math.PI * (k + 0.35)) / (RINGS - 0.3);
    const sc = Math.cos(th);
    const up = Math.sin(th);
    const jaw = up < 0 ? 1 + 0.2 * up : 1;
    headRows.push([headC + s.headY * up, s.headX * sc * jaw, s.headZ * sc * (up < 0 ? 1 + 0.08 * up : 1), [HEAD, 1], up < 0 ? -0.1 * up * s.headZ : 0]);
  }
  const head = b.tube(0, headRows, PART.SKIN);
  b.cap(head[0], [0, -1, 0], [HEAD, 1], PART.SKIN);
  b.cap(head[RINGS - 1], [0, 1, 0], [HEAD, 1], PART.SKIN);

  for (const [sg, UA, FA, HAND, TH, SH, FT] of [
    [1, BONE.UARM_L, BONE.FARM_L, BONE.HAND_L, BONE.THIGH_L, BONE.SHIN_L, BONE.FOOT_L],
    [-1, BONE.UARM_R, BONE.FARM_R, BONE.HAND_R, BONE.THIGH_R, BONE.SHIN_R, BONE.FOOT_R],
  ] as const) {
    // ── Arm ────────────────────────────────────────────────────────────────
    const ax = sg * s.shoulderHalf;
    const elbowY = jy(FA);
    const wristY = jy(HAND);
    const upperLen = shoulderY - elbowY;
    const sleeveEnd = shoulderY - upperLen * s.sleeve;
    const ua = s.upperArm;
    const fa = s.foreArm;

    const sleeve = b.tube(
      ax,
      [
        [shoulderY + 0.03 * H, ua * 0.85, ua * 0.9, [CHEST, 0.6, UA, 0.4]],
        [shoulderY, ua * 1.32, ua * 1.3, [UA, 0.7, CHEST, 0.3]],
        [(shoulderY + sleeveEnd) / 2, ua * 1.22, ua * 1.22, [UA, 1]],
        [sleeveEnd, ua * 1.2, ua * 1.2, [UA, 1]],
      ],
      PART.SHIRT
    );
    b.cap(sleeve[0], [0, 1, 0], [CHEST, 0.6, UA, 0.4], PART.SHIRT);

    b.tube(
      ax,
      [
        [sleeveEnd + 0.01 * H, ua, ua, [UA, 1]],
        [elbowY + 0.03 * H, ua * 0.92, ua * 0.92, [UA, 0.8, FA, 0.2]],
        [elbowY, ua * 0.88, ua * 0.9, [UA, 0.5, FA, 0.5]],
        [elbowY - 0.03 * H, fa * 1.06, fa * 1.06, [FA, 0.8, UA, 0.2]],
        [wristY + 0.01 * H, fa * 0.74, fa * 0.72, [FA, 0.7, HAND, 0.3]],
      ],
      PART.SKIN
    );
    const hand = b.tube(
      ax,
      [
        [wristY + 0.012 * H, fa * 0.7, fa * 0.72, [HAND, 1]],
        [wristY - 0.04 * H, fa * 0.52, fa * 1.0, [HAND, 1]],
        [wristY - 0.095 * H, fa * 0.3, fa * 0.62, [HAND, 1]],
      ],
      PART.SKIN
    );
    b.cap(hand[2], [0, -1, 0], [HAND, 1], PART.SKIN);

    // ── Leg ────────────────────────────────────────────────────────────────
    const lx = sg * s.hipHalf * 0.56;
    const th = s.thigh;
    const cf = s.calf;
    const thighLen = hipY - kneeY;
    const shinLen = kneeY - ankleY;
    const shortsEnd = hipY - thighLen * 0.42;

    b.tube(
      lx,
      [
        [hipY + 0.025 * H, th * 1.12, th * 1.15, [HIPS, 0.6, TH, 0.4]],
        [hipY - 0.04 * H, th * 1.24, th * 1.26, [TH, 0.8, HIPS, 0.2]],
        [shortsEnd, th * 1.22, th * 1.24, [TH, 1]],
      ],
      PART.SHORTS
    );
    b.tube(
      lx,
      [
        [shortsEnd + 0.02 * H, th, th * 1.04, [TH, 1]],
        [kneeY + 0.05 * H, th * 0.8, th * 0.82, [TH, 1]],
        [kneeY, th * 0.72, th * 0.74, [TH, 0.5, SH, 0.5]],
        [kneeY - 0.035 * H, cf * 1.06, cf * 1.08, [SH, 0.8, TH, 0.2]],
      ],
      PART.SKIN
    );
    b.tube(
      lx,
      [
        [kneeY - 0.03 * H, cf * 1.1, cf * 1.12, [SH, 1]],
        [kneeY - shinLen * 0.3, cf * 1.16, cf * 1.24, [SH, 1], -0.008 * H],
        [ankleY + 0.07 * H, cf * 0.76, cf * 0.8, [SH, 1]],
        [ankleY + 0.012 * H, cf * 0.66, cf * 0.7, [SH, 0.5, FT, 0.5]],
      ],
      PART.SOCKS
    );

    // Boot: lofted front to back instead of bottom to top.
    const bw = cf * 0.86;
    const bootRows: [number, number, number, number][] = [
      [-0.04, 0.6, 0.026, 0.03],
      [-0.012, 1.0, 0.04, 0.041],
      [0.04, 1.06, 0.03, 0.031],
      [0.085, 0.96, 0.022, 0.023],
      [0.115, 0.55, 0.014, 0.016],
    ];
    const boot = bootRows.map(([z, w, ry, cy]) => b.ring([lx, cy * H, z * H], [bw * w, 0, 0], [0, ry * H, 0], [FT, 1], PART.BOOTS));
    for (let i = 0; i < boot.length - 1; i++) b.connect(boot[i], boot[i + 1]);
    b.cap(boot[0], [0, 0, -1], [FT, 1], PART.BOOTS);
    b.cap(boot[boot.length - 1], [0, 0, 1], [FT, 1], PART.BOOTS);
  }
}

export interface BodyGeometry {
  geometry: THREE.BufferGeometry;
  layouts: BodyLayout[];
}

/** Builds the shared mesh: shapes[0] is the base, every other shape a morph target. */
export function buildBodyGeometry(shapes: readonly BodyShape[]): BodyGeometry {
  const builds = shapes.map((s) => {
    const b = new Builder();
    generate(s, b);
    return b;
  });
  const base = builds[0];
  const vertexCount = base.pos.length / 3;
  for (const b of builds) {
    if (b.pos.length !== base.pos.length || b.idx.length !== base.idx.length) {
      throw new Error("intro: body generator produced a different topology for one profile");
    }
  }

  const normalsOf = (positions: number[]) => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    g.setIndex(base.idx);
    g.computeVertexNormals();
    const n = (g.getAttribute("normal").array as Float32Array).slice();
    g.dispose();
    return n;
  };

  const geometry = new THREE.BufferGeometry();
  geometry.setIndex(base.idx);
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(base.pos, 3));
  const baseNormals = normalsOf(base.pos);
  geometry.setAttribute("normal", new THREE.BufferAttribute(baseNormals, 3));
  geometry.setAttribute("skinIndex", new THREE.Uint16BufferAttribute(base.skinIndex, 4));
  geometry.setAttribute("skinWeight", new THREE.Float32BufferAttribute(base.skinWeight, 4));
  geometry.setAttribute("aPart", new THREE.Float32BufferAttribute(base.part, 1));

  // Pattern coordinates: the base shape, in units of its own height. The kit
  // pattern is laid out in these, so it stretches with the body like fabric
  // instead of swimming across it while the figure moves or morphs.
  const baseH = shapes[0].height;
  geometry.setAttribute("aPat", new THREE.Float32BufferAttribute(base.pos.map((v) => v / baseH), 3));

  const morphPositions: THREE.BufferAttribute[] = [];
  const morphNormals: THREE.BufferAttribute[] = [];
  for (let k = 1; k < builds.length; k++) {
    const dp = new Float32Array(vertexCount * 3);
    const dn = new Float32Array(vertexCount * 3);
    const n = normalsOf(builds[k].pos);
    for (let i = 0; i < dp.length; i++) {
      dp[i] = builds[k].pos[i] - base.pos[i];
      dn[i] = n[i] - baseNormals[i];
    }
    morphPositions.push(new THREE.BufferAttribute(dp, 3));
    morphNormals.push(new THREE.BufferAttribute(dn, 3));
  }
  geometry.morphAttributes.position = morphPositions;
  geometry.morphAttributes.normal = morphNormals;
  geometry.morphTargetsRelative = true;

  return { geometry, layouts: shapes.map(layoutBody) };
}
