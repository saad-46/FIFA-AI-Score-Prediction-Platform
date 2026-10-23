import type { Stride } from "../profiles";
import { curve } from "../math";
import { BONE, BONE_COUNT } from "./body-geometry";

/**
 * Procedural animation.
 *
 * A pose is computed from scratch from the values below: there are no clips,
 * no mixer and no elapsed time. The same inputs always give the same pose,
 * which is what lets the scroll position scrub the figure in both directions.
 *
 * Bone rotations are XYZ Euler angles in the figure's space (+Y up, +Z
 * forward, +X its left). A positive X rotation swings a hanging limb backward
 * and tips the trunk forward.
 */

export interface Motion {
  /** Run-cycle phase in radians; one full turn is two steps. */
  phase: number;
  /** 0 standing, 1 full running stride. */
  run: number;
  /** -1..1: body feint to one side or the other. */
  feint: number;
  /** 0..1: how far into a tight spin the figure is leaning. */
  spin: number;
  /** 0..1 strength of a right-foot push or strike, and where in it we are. */
  kick: number;
  kickT: number;
  /** -1..1: a stepover around the ball, sign picks the leg. */
  stepover: number;
  /** 0..1 strength of a heel flick, and where in it we are. */
  flick: number;
  flickT: number;
  /** Height of the lowest boot above the grass. */
  air: number;
  /** 0..1: arms out, chest up, chin high (the celebration). */
  celebrate: number;
  /** Extra knee bend and lowered hips (0 for none): the gather before the jump and the landing. */
  crouch: number;
  /** Ground covered so far, in metres (a fixed function of progress). */
  distance: number;
  /** 0..1 weight of the keyed pass (see PASS below) and where in it we are (0..1; contact at 0.5). */
  pass: number;
  passT: number;
  /** 0..1 weight of the soft control touch layered on the gait, and where in it we are. */
  touch: number;
  touchT: number;
  /** Captured run in use: index into RUNS, or -1; its weight; and its alignment point. */
  run2: number;
  runWeight: number;
  runAnchorDistance: number;
  runAnchorPhase: number;
  /**
   * Captured shot: seconds from the moment of contact, its weight, and where
   * the ball is (world x, z) and which way it leaves (unit vector) at contact.
   */
  shotT: number;
  shotWeight: number;
  shotBallX: number;
  shotBallZ: number;
  shotAimX: number;
  shotAimZ: number;
  /** 0..1 weight of the bicycle kick, where in it we are (contact at 0.5), and the pelvis height it asks for (metres). */
  bike: number;
  bikeT: number;
  bikeHip: number;
}

export const createMotion = (): Motion => ({
  phase: 0,
  run: 0,
  feint: 0,
  spin: 0,
  kick: 0,
  kickT: 0,
  stepover: 0,
  flick: 0,
  flickT: 0,
  air: 0,
  celebrate: 0,
  crouch: 0,
  distance: 0,
  pass: 0,
  passT: 0,
  touch: 0,
  touchT: 0,
  run2: -1,
  runWeight: 0,
  runAnchorDistance: 0,
  runAnchorPhase: 0,
  shotT: 0,
  shotWeight: 0,
  shotBallX: 0,
  shotBallZ: 0,
  shotAimX: 0,
  shotAimZ: 1,
  bike: 0,
  bikeT: 0,
  bikeHip: 0,
});

// ── The pass: keyed poses ──────────────────────────────────────────────────
//
// Right-footed pass, contact at t = 0.5. Each channel is a monotone cubic
// through its keys (no overshoot, and the leg keeps its speed through contact
// instead of stopping at every key). Angles are the same XYZ Euler angles as
// the rest of this file; values replace the gait's by weight.
type Keys = readonly (readonly [number, number])[];
const ch = (k: Keys) => curve(k);
const PASS_CLIP = {
  thighR: ch([[0, -0.1], [0.12, -0.08], [0.28, 0.3], [0.5, -0.46], [0.66, -0.7], [0.84, -0.45], [1, -0.25]]),
  shinR: ch([[0, 0.3], [0.12, 0.4], [0.28, 0.95], [0.5, 0.3], [0.66, 0.15], [0.84, 0.4], [1, 0.55]]),
  footR: ch([[0, 0], [0.3, 0.25], [0.5, 0.1], [0.64, 0.3], [1, 0]]),
  footRY: ch([[0, 0], [0.3, 0.1], [0.5, 0.25], [0.7, 0.2], [1, 0]]),
  thighRZ: ch([[0, -0.05], [0.4, -0.05], [0.5, -0.07], [0.58, -0.14], [0.75, -0.14], [1, -0.05]]),
  thighL: ch([[0, -0.1], [0.12, -0.18], [0.3, -0.16], [0.7, -0.05], [1, -0.32]]),
  shinL: ch([[0, 0.3], [0.12, 0.5], [0.5, 0.5], [0.7, 0.42], [1, 0.4]]),
  hipsY: ch([[0, 0], [0.3, -0.22], [0.5, 0.1], [0.7, 0.28], [1, 0.1]]),
  spineX: ch([[0, 0.12], [0.3, 0.22], [0.5, 0.2], [1, 0.16]]),
  chestY: ch([[0, 0], [0.3, 0.2], [0.5, -0.1], [0.7, -0.25], [1, -0.1]]),
  armLX: ch([[0, 0], [0.3, -0.35], [0.5, -0.1], [1, 0.2]]),
  armLZ: ch([[0, 0.2], [0.3, 0.6], [0.5, 0.75], [0.8, 0.5], [1, 0.25]]),
  armRX: ch([[0, 0], [0.3, 0.25], [0.5, -0.1], [0.7, -0.5], [1, -0.2]]),
  armRZ: ch([[0, -0.2], [0.3, -0.35], [0.5, -0.45], [1, -0.25]]),
  // Elbows: the arm that swings forward bends more, and the arms soften again on the recovery.
  farmL: ch([[0, 0.35], [0.3, 0.6], [0.5, 0.45], [0.7, 0.8], [1, 0.45]]),
  farmR: ch([[0, 0.3], [0.3, 0.35], [0.5, 0.65], [0.7, 0.9], [1, 0.45]]),
};

/** A soft control touch with the right foot, in place of the gait's right leg by weight: it reaches for the ball at t = 0.4 and draws back. */
const TOUCH_CLIP = {
  thighR: ch([[0, -0.1], [0.4, -0.43], [1, -0.1]]),
  shinR: ch([[0, 0.3], [0.4, 0.08], [1, 0.3]]),
  footR: ch([[0, 0], [0.4, 0.15], [1, 0]]),
  spineX: ch([[0, 0.12], [0.4, 0.22], [1, 0.12]]),
};

/**
 * The bicycle kick, contact at t = 0.5. The figure faces the incoming ball,
 * gathers, springs up and back, lays out almost flat with the left leg
 * thrown up first and the right whipping through the ball, then rolls over
 * onto the ground. `hip` is the pelvis height in metres (replaces the
 * boot-based grounding while the kick is on).
 */
const BIKE_CLIP = {
  pitch: ch([[0, 0], [0.16, -0.12], [0.3, -0.55], [0.42, -1.2], [0.5, -1.6], [0.6, -1.78], [0.72, -1.55], [0.84, -0.7], [0.93, -0.25], [1, 0]]),
  hip: ch([[0, 0.95], [0.16, 0.8], [0.3, 1.08], [0.42, 1.5], [0.5, 1.62], [0.6, 1.5], [0.72, 1.0], [0.82, 0.5], [0.88, 0.32], [0.94, 0.55], [1, 0.9]]),
  thighL: ch([[0, -0.1], [0.16, -0.2], [0.34, -1.5], [0.5, -2.0], [0.62, -1.2], [0.78, -0.35], [1, -0.1]]),
  shinL: ch([[0, 0.3], [0.16, 0.5], [0.34, 0.3], [0.5, 0.15], [0.7, 0.6], [1, 0.3]]),
  thighR: ch([[0, -0.1], [0.16, -0.25], [0.3, -0.5], [0.4, -1.55], [0.5, -1.75], [0.6, -2.0], [0.72, -1.3], [0.86, -0.5], [1, -0.1]]),
  shinR: ch([[0, 0.3], [0.16, 0.9], [0.3, 1.5], [0.42, 1.0], [0.5, 0.05], [0.6, 0.05], [0.72, 0.5], [1, 0.3]]),
  footR: ch([[0, 0], [0.4, -0.2], [0.5, -0.65], [0.6, -0.5], [1, 0]]),
  armLX: ch([[0, 0], [0.3, -0.5], [0.5, 0.25], [0.7, 0.5], [1, 0]]),
  armLZ: ch([[0, 0.2], [0.3, 0.9], [0.5, 1.15], [0.8, 0.9], [1, 0.25]]),
  armRX: ch([[0, 0], [0.3, -0.6], [0.5, 0.2], [0.7, 0.55], [1, 0]]),
  armRZ: ch([[0, -0.2], [0.3, -0.9], [0.5, -1.15], [0.8, -0.95], [1, -0.25]]),
  farm: ch([[0, 0], [0.3, 0.5], [0.5, 0.35], [0.8, 0.5], [1, 0]]),
  spineX: ch([[0, 0.1], [0.3, -0.1], [0.5, -0.25], [0.7, -0.05], [1, 0.1]]),
  headX: ch([[0, 0], [0.3, 0.3], [0.5, 0.45], [0.75, 0.2], [1, 0]]),
};

const blend = (out: Float32Array, bone: number, axis: number, target: number, w: number) => {
  const i = bone * 3 + axis;
  out[i] += (target - out[i]) * w;
};

export const createPose = () => new Float32Array(BONE_COUNT * 3);

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const smooth = (t: number) => t * t * (3 - 2 * t);

export const bikeHipHeight = (t: number) => BIKE_CLIP.hip(t);

export function computePose(m: Motion, s: Stride, out: Float32Array): Float32Array {
  out.fill(0);
  const add = (bone: number, x: number, y = 0, z = 0) => {
    out[bone * 3] += x;
    out[bone * 3 + 1] += y;
    out[bone * 3 + 2] += z;
  };
  const a = m.run;
  const crouch = s.crouch + 0.35 * Math.abs(m.feint) + 0.4 * m.spin + 0.25 * m.flick + m.crouch;

  // ── Legs ────────────────────────────────────────────────────────────────
  const leg = (thigh: number, shin: number, foot: number, phase: number) => {
    const sw = Math.sin(phase);
    const thighX = -s.swing * a * sw - 0.36 * crouch - 0.04;
    // The knee folds as the leg swings through, a little before mid-swing.
    const fold = Math.max(0, Math.cos(phase + 0.5)) ** 1.3;
    const kneeX = 0.1 + 0.74 * crouch + s.knee * a * fold;
    add(thigh, thighX);
    add(shin, kneeX);
    // Keep the boot near level through the stance, toes down in the swing.
    add(foot, -(thighX + kneeX) * 0.72 + 0.3 * a * fold);
  };
  leg(BONE.THIGH_L, BONE.SHIN_L, BONE.FOOT_L, m.phase);
  leg(BONE.THIGH_R, BONE.SHIN_R, BONE.FOOT_R, m.phase + Math.PI);
  add(BONE.THIGH_L, 0, 0, 0.05);
  add(BONE.THIGH_R, 0, 0, -0.05);

  // ── Arms: opposite the legs, elbows bent ────────────────────────────────
  const sw = Math.sin(m.phase);
  const out2 = 0.14 + 0.55 * m.spin + 0.3 * Math.abs(m.feint) + 0.5 * m.flick;
  add(BONE.UARM_L, s.arm * a * sw, 0, out2);
  add(BONE.UARM_R, -s.arm * a * sw, 0, -out2);
  const elbow = s.elbow * (0.35 + 0.65 * a);
  add(BONE.FARM_L, -elbow - 0.3 * a * Math.max(0, -sw));
  add(BONE.FARM_R, -elbow - 0.3 * a * Math.max(0, sw));

  // ── Trunk ───────────────────────────────────────────────────────────────
  add(BONE.HIPS, 0, -0.5 * s.twist * a * sw, s.sway * a * sw);
  add(BONE.SPINE, s.lean * (0.35 + 0.65 * a) + 0.12 * crouch, 0, -s.sway * a * sw);
  add(BONE.CHEST, 0.08 * crouch, s.twist * a * sw);
  add(BONE.NECK, -0.3 * s.lean);
  add(BONE.HEAD, -0.35 * s.lean - 0.1 * crouch);

  // ── Feint: drop the shoulder and roll the hips to one side ──────────────
  if (m.feint !== 0) {
    const f = m.feint;
    add(BONE.HIPS, 0, 0.25 * f, -0.2 * f);
    add(BONE.SPINE, 0, 0, -0.3 * f);
    add(BONE.CHEST, 0.1 * Math.abs(f), 0.45 * f, -0.12 * f);
    add(BONE.HEAD, 0, -0.3 * f, 0.15 * f);
  }

  // ── Push or strike with the right foot ──────────────────────────────────
  if (m.kick > 0) {
    const t = smooth(m.kickT);
    const k = m.kick;
    add(BONE.THIGH_R, k * lerp(0.75, -1.05, t));
    add(BONE.SHIN_R, k * lerp(0.95, -0.05, t));
    add(BONE.FOOT_R, k * lerp(0.2, 0.55, t));
    add(BONE.SPINE, -0.12 * k * t);
    add(BONE.UARM_L, k * lerp(0.3, -0.6, t), 0, 0.25 * k);
    add(BONE.UARM_R, k * lerp(-0.3, 0.5, t));
  }

  // ── Control touch: the right foot reaches for the ball ──────────────────
  if (m.touch > 0) {
    const t = m.touchT;
    const w = m.touch;
    const thigh = TOUCH_CLIP.thighR(t);
    const shin = TOUCH_CLIP.shinR(t);
    blend(out, BONE.THIGH_R, 0, thigh, w);
    blend(out, BONE.SHIN_R, 0, shin, w);
    blend(out, BONE.FOOT_R, 0, -(thigh + shin) * 0.72 + TOUCH_CLIP.footR(t), w);
    blend(out, BONE.SPINE, 0, TOUCH_CLIP.spineX(t), w);
  }

  // ── The pass: plant, backswing, contact, follow-through, recovery ───────
  if (m.pass > 0) {
    const t = m.passT;
    const w = m.pass;
    const P = PASS_CLIP;
    const thighR = P.thighR(t);
    const shinR = P.shinR(t);
    const thighL = P.thighL(t);
    const shinL = P.shinL(t);
    blend(out, BONE.THIGH_R, 0, thighR, w);
    blend(out, BONE.THIGH_R, 2, P.thighRZ(t), w);
    blend(out, BONE.SHIN_R, 0, shinR, w);
    blend(out, BONE.FOOT_R, 0, -(thighR + shinR) * 0.72 + P.footR(t), w);
    blend(out, BONE.FOOT_R, 1, P.footRY(t), w);
    blend(out, BONE.THIGH_L, 0, thighL, w);
    blend(out, BONE.SHIN_L, 0, shinL, w);
    blend(out, BONE.FOOT_L, 0, -(thighL + shinL) * 0.72, w);
    blend(out, BONE.HIPS, 1, P.hipsY(t), w);
    blend(out, BONE.SPINE, 0, P.spineX(t), w);
    blend(out, BONE.CHEST, 1, P.chestY(t), w);
    blend(out, BONE.UARM_L, 0, P.armLX(t), w);
    blend(out, BONE.UARM_L, 2, P.armLZ(t), w);
    blend(out, BONE.UARM_R, 0, P.armRX(t), w);
    blend(out, BONE.UARM_R, 2, P.armRZ(t), w);
    blend(out, BONE.FARM_L, 0, -P.farmL(t), w);
    blend(out, BONE.FARM_R, 0, -P.farmR(t), w);
  }

  // ── Bicycle kick ────────────────────────────────────────────────────────
  if (m.bike > 0) {
    const t = m.bikeT;
    const w = m.bike;
    const B = BIKE_CLIP;
    blend(out, BONE.HIPS, 0, B.pitch(t), w);
    blend(out, BONE.THIGH_L, 0, B.thighL(t), w);
    blend(out, BONE.SHIN_L, 0, B.shinL(t), w);
    blend(out, BONE.FOOT_L, 0, -(B.thighL(t) + B.shinL(t)) * 0.4, w);
    blend(out, BONE.THIGH_R, 0, B.thighR(t), w);
    blend(out, BONE.SHIN_R, 0, B.shinR(t), w);
    blend(out, BONE.FOOT_R, 0, B.footR(t), w);
    blend(out, BONE.SPINE, 0, B.spineX(t), w);
    blend(out, BONE.HEAD, 0, B.headX(t), w);
    blend(out, BONE.UARM_L, 0, B.armLX(t), w);
    blend(out, BONE.UARM_L, 2, B.armLZ(t), w);
    blend(out, BONE.UARM_R, 0, B.armRX(t), w);
    blend(out, BONE.UARM_R, 2, B.armRZ(t), w);
    blend(out, BONE.FARM_L, 0, -B.farm(t), w);
    blend(out, BONE.FARM_R, 0, -B.farm(t), w);
  }

  // ── Stepover: the leading leg circles outside the ball ──────────────────
  if (m.stepover !== 0) {
    const so = m.stepover;
    const mag = Math.abs(so);
    const thigh = so > 0 ? BONE.THIGH_L : BONE.THIGH_R;
    const shin = so > 0 ? BONE.SHIN_L : BONE.SHIN_R;
    add(thigh, -0.75 * mag, 0, 0.5 * so);
    add(shin, 0.45 * mag);
    add(BONE.HIPS, 0, 0.3 * so, -0.12 * so);
    add(BONE.CHEST, 0, -0.35 * so, -0.1 * so);
  }

  // ── Flick: both heels snap up behind, trunk tips forward ────────────────
  if (m.flick > 0) {
    const up = Math.sin(Math.PI * Math.min(1, m.flickT * 1.6)) * m.flick;
    add(BONE.SHIN_L, 1.5 * up);
    add(BONE.SHIN_R, 1.25 * up);
    add(BONE.THIGH_L, 0.25 * up);
    add(BONE.THIGH_R, 0.2 * up);
    add(BONE.SPINE, 0.3 * up);
    add(BONE.HEAD, -0.25 * up);
  }

  // ── Celebration: arms spread wide, chest out, chin up ───────────────────
  if (m.celebrate > 0) {
    const c = m.celebrate;
    add(BONE.UARM_L, -0.1 * c, 0, 1.3 * c);
    add(BONE.UARM_R, -0.1 * c, 0, -1.3 * c);
    add(BONE.FARM_L, 0.9 * elbow * c);
    add(BONE.FARM_R, 0.9 * elbow * c);
    add(BONE.SPINE, -0.3 * c);
    add(BONE.CHEST, -0.12 * c);
    add(BONE.HEAD, -0.3 * c);
    add(BONE.THIGH_L, 0, 0, 0.14 * c);
    add(BONE.THIGH_R, 0, 0, -0.14 * c);
  }

  return out;
}
