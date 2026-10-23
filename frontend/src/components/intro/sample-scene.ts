import { BALL_RADIUS } from "./ball";
import { bikeHipHeight, createMotion, type Motion } from "./character/pose";
import type { Identity } from "./character/rig";
import { TAU, bell, clamp01, curve, extend, lerp, range, smooth, smoother, smoothstep } from "./math";
import { PLAYERS } from "./profiles";
import { ENDING, FINISH, MORPHS, MOVES, BEAT_ZOOM, NUMBER_BEATS, PASS, P_MAX, RUNS, SEGMENTS, SHOT, TOUCH, toScene } from "./timeline";

/**
 * The scene as a function of progress.
 *
 * `sampleScene(p)` is the only thing that decides where anything is. It reads
 * no clock and keeps no state between calls: the same `p` always produces the
 * same scene, whichever direction the scroll arrived from. The two lookup
 * tables below are integrals that are fixed functions of `p` (how far through
 * its stride the figure is, and how far the ball has rolled); they are filled
 * once, in order, when the module loads.
 */

export interface SceneState {
  actor: { x: number; z: number; yaw: number };
  motion: Motion;
  identity: Identity;
  ball: { x: number; y: number; z: number; qx: number; qy: number; qz: number; qw: number };
  camera: { x: number; y: number; z: number; tx: number; ty: number; tz: number };
  light: { pool: number; key: number; ambient: number; floodA: number; floodB: number };
  /** Dust kicked up at a morph: 0..1 through the burst, and where. */
  dust: { t: number; x: number; z: number };
  /** Which player's caption shows (-1 for none) and how visible it is. */
  caption: { player: number; alpha: number };
  /** 0..1 soft-focus at a morph seam. */
  blur: number;
  /** The goal: how hard the net is bulging and where, sparks over the goalmouth, floodlight surge. */
  goal: { net: number; netT: number; netX: number; netY: number; netZ: number; burst: number; surge: number };
  /** 0..1: the closing wordmark. */
  brand: number;
  /**
   * The ending: the SIIIUUU word (how visible, and its shake offsets in 0..1
   * units of the shake envelope), the fade to black and the two message lines.
   */
  finale: { shout: number; shoutIn: number; shake: number; shakeX: number; shakeY: number; shakeRot: number; black: number; line1: number; line2: number };
}

export const createSceneState = (): SceneState => ({
  actor: { x: 0, z: 0, yaw: 0 },
  motion: createMotion(),
  identity: { a: 0, b: 0, t: 0 },
  ball: { x: 0, y: 0, z: 0, qx: 0, qy: 0, qz: 0, qw: 1 },
  camera: { x: 0, y: 0, z: 0, tx: 0, ty: 0, tz: 0 },
  light: { pool: 0, key: 0, ambient: 0, floodA: 0, floodB: 0 },
  dust: { t: 0, x: 0, z: 0 },
  caption: { player: -1, alpha: 0 },
  blur: 0,
  goal: { net: 0, netT: 0, netX: 0, netY: 0, netZ: 0, burst: 0, surge: 0 },
  brand: 0,
  finale: { shout: 0, shoutIn: 0, shake: 0, shakeX: 0, shakeY: 0, shakeRot: 0, black: 0, line1: 0, line2: 0 },
});

// ── Who the figure is ──────────────────────────────────────────────────────

export function identityAt(p: number, out: Identity): Identity {
  let a = 0;
  for (const m of MORPHS) {
    if (p >= m.to) {
      a = m.b;
      continue;
    }
    if (p > m.from) {
      out.a = m.a;
      out.b = m.b;
      out.t = smoother(range(p, m.from, m.to));
      return out;
    }
    break;
  }
  out.a = a;
  out.b = a;
  out.t = 0;
  return out;
}

// ── Where the figure is ────────────────────────────────────────────────────

const actorX0 = curve([
  [0, -15.6],
  [0.07, -13.2],
  [0.12, -8.75],
  [0.17, -6.05],
  [0.215, -3.75],
  [0.245, -3.1],
  [0.272, -2.45],
  [0.31, -0.35],
  [0.35, 2.3],
]);
const actorZ0 = curve([
  [0.16, 0],
  [0.178, 0.24],
  [0.196, -0.36],
  [0.218, -0.28],
  [0.272, -0.08],
  [0.35, 0],
]);
// Realistic mode only from here on (p > 0.47): cut inside, drive, drift right
// onto the pass, then the shooting position.
const actorZ = extend(actorZ0, 0.47, [
  [0.49, -0.9],
  [0.52, -0.6],
  [0.59, 0],
  [0.64, 0.4],
  // Barely sideways while the support foot is planted (0.684 to 0.702).
  [0.684, 0.66],
  [0.702, 0.69],
  [0.71, 0.8],
  [0.76, 1.3],
  [0.8, 1.45],
  [0.87, 1.6],
  [1, 1.6],
]);

// Player 3 (realistic mode only) sprints on from where player 2's run ends.
const actorX = extend(actorX0, 0.35, [
  // Player 3's sprint at the captured sprinter's own pace (CMU 143_01, about
  // 6.8 m/s on these legs), so the legs cycle at a real runner's cadence.
  [0.37, 4.0],
  [0.4, 7.2],
  [0.43, 10.1],
  [0.47, 13.9],
  // Player 4: a heavy driving run.
  [0.5, 17.1],
  [0.52, 19.0],
  [0.59, 24.5],
  // Player 5: slows, controls, passes into space.
  [0.62, 26.1],
  [0.64, 26.9],
  [0.67, 27.5],
  // He all but stops to plant beside the ball (the support foot must not
  // slide), strikes, then accelerates into the run onto it.
  [0.684, 27.8],
  [0.7, 27.97],
  [0.71, 28.35],
  [0.72, 28.95],
  // Player 6 runs onto the lob, plants, turns his back on the goal and goes
  // up and back for the bicycle kick; he lands a metre or so behind where he
  // struck it, gets up and runs a few steps toward the corner flag to jump.
  [0.74, 30.2],
  [0.77, 32.0],
  [0.804, 33.5],
  [0.83, 34.3],
  [0.846, 34.4],
  [0.856, 34.7],
  [0.88, 37.2],
  [1, 37.2],
]);

const SPIN = MORPHS[0];
/** Facing after p = 0.47: turns for the cut, the plant, the run onto the pass, the shot and the celebration. */
const yawLater = extend(() => Math.PI / 2, 0.47, [
  [0.48, Math.PI / 2 + 0.45],
  [0.5, Math.PI / 2 + 0.4],
  [0.515, Math.PI / 2],
  [0.6, Math.PI / 2],
  [0.62, Math.PI / 2 + 1.1],
  [0.645, Math.PI / 2 + 0.6],
  [0.66, Math.PI / 2],
  [0.7, Math.PI / 2],
  [0.72, Math.PI / 2 - 0.35],
  [0.74, Math.PI / 2 - 0.9],
  [0.765, -Math.PI / 2 + 0.3],
  [0.78, -Math.PI / 2],
  [0.84, -Math.PI / 2],
  [0.858, Math.PI / 2 - 0.1],
  [0.872, Math.PI / 2],
  [0.878, Math.PI - 0.3],
  [1, Math.PI - 0.3],
]);
/** Facing: +X down the pitch, one full turn inside the first morph, one more in the celebration jump. */
const actorYaw = (p: number) =>
  yawLater(p) +
  TAU * smoother(range(p, SPIN.from - 0.004, SPIN.to + 0.004)) +
  TAU * smoother(range(p, FINISH.jump.from, FINISH.jump.to));

const strideLengthAt = (() => {
  const id: Identity = { a: 0, b: 0, t: 0 };
  return (p: number) => {
    identityAt(p, id);
    return lerp(PLAYERS[id.a].stride.length, PLAYERS[id.b].stride.length, id.t);
  };
})();

const SAMPLES = 2048;

/** Run-cycle phase: distance covered divided by stride length, plus the steps of the spin. */
const PHASE = (() => {
  const table = new Float32Array(SAMPLES + 1);
  for (let i = 0; i < SAMPLES; i++) {
    const p0 = i / SAMPLES;
    const p1 = (i + 1) / SAMPLES;
    // Sideways travel counts too, but only in the realistic-only part of the
    // timeline, so the procedural default keeps exactly the phase it had.
    const dz = p0 >= 0.47 ? actorZ(p1) - actorZ(p0) : 0;
    const dist = Math.hypot(actorX(p1) - actorX(p0), dz);
    const spinSteps = 2.6 * TAU * (smoother(range(p1, SPIN.from, SPIN.to)) - smoother(range(p0, SPIN.from, SPIN.to)));
    table[i + 1] = table[i] + (dist / strideLengthAt(p0)) * TAU + spinSteps;
  }
  return table;
})();

/** Ground covered, in metres: the integral of the figure's path (a fixed function of p). */
const DIST = (() => {
  const table = new Float32Array(SAMPLES + 1);
  for (let i = 0; i < SAMPLES; i++) {
    const p0 = i / SAMPLES;
    const p1 = (i + 1) / SAMPLES;
    table[i + 1] = table[i] + Math.hypot(actorX(p1) - actorX(p0), actorZ(p1) - actorZ(p0));
  }
  return table;
})();

const fromTable = (table: Float32Array, p: number) => {
  const f = clamp01(p) * SAMPLES;
  const i = Math.min(SAMPLES - 1, Math.floor(f));
  return lerp(table[i], table[i + 1], f - i);
};

// ── Where the ball is ──────────────────────────────────────────────────────

/** Rolling in from screen-right and slowing into the light. */
const rollInX = curve([
  [0, 4.4],
  [0.07, 1.6],
  [0.095, -5.4],
  [0.12, -8.08],
  [0.135, -8.12],
]);
/** How far ahead of the figure the ball is, along its facing. */
const ballLead0 = curve([
  [0.12, 0.62],
  [0.198, 0.62],
  [0.214, 1.12],
  [0.236, 0.3],
  [0.264, 0.3],
  [0.278, 0.56],
  [0.31, 0.56],
  [0.318, -0.2],
  [0.348, 1.3],
]);
// Player 3 knocks it well ahead and chases it.
const ballLead = extend(ballLead0, 0.348, [
  [0.358, 0.7],
  [0.374, 0.62],
  [0.392, 1.7],
  [0.41, 0.75],
  [0.428, 0.7],
  [0.442, 1.9],
  [0.46, 0.8],
  [0.47, 0.75],
  // Player 4: close through the cut, then two heavy touches.
  [0.49, 0.5],
  [0.52, 0.62],
  [0.55, 1.6],
  [0.565, 0.8],
  [0.585, 1.7],
  [0.6, 0.9],
  // Player 5: under the feet through the plant and the control.
  [0.62, 0.6],
  [0.64, 0.5],
  // A soft touch at TOUCH.contact: the ball is pushed ahead, then the figure
  // catches it up and plants beside it. It does not move again before PASS.contact.
  [0.646, 0.53],
  [TOUCH.contact, 0.53],
  [0.662, 0.7],
  [0.684, 0.38],
  [PASS.contact, 0.38],
]);
/** Sideways offset, positive to the figure's left. */
const ballSide = extend(
  curve([
    [0.16, 0],
    [0.178, -0.06],
    [0.19, 0.3],
    [0.202, 0.06],
    [0.216, 0],
  ]),
  0.47,
  [
    [0.49, 0.22],
    [0.52, 0],
    // In line with the right foot for the control touch, then tucked a little toward the kicking foot for the pass.
    [0.636, 0],
    [0.646, -0.26],
    [0.658, -0.26],
    [0.684, -0.06],
    [1, -0.06],
  ]
);

function dribblePosition(p: number, out: { x: number; y: number; z: number }) {
  const yaw = actorYaw(p);
  const phase = fromTable(PHASE, p);
  // Touches: the ball runs a little ahead and is caught again each stride,
  // except while it is being dragged through the spin or flicked.
  const touching = (1 - bell(p, 0.2, 0.28)) * (1 - smoothstep(0.3, 0.316, p)) * (1 - smoothstep(0.622, 0.64, p));
  const lead = ballLead(p) + 0.15 * Math.cos(phase) * touching;
  const side = ballSide(p);
  const fx = Math.sin(yaw);
  const fz = Math.cos(yaw);
  const dribbleX = actorX(p) + fx * lead + fz * side;
  const dribbleZ = actorZ(p) + fz * lead - fx * side;
  // The hand-over from rolling freely to being at the figure's feet is a
  // blend between two continuous paths, never a jump.
  const held = smoothstep(0.118, 0.134, p);
  out.x = lerp(rollInX(p), dribbleX, held);
  out.z = lerp(0, dribbleZ, held);
  const flick = range(p, MOVES.flick.from + 0.004, MOVES.flick.to - 0.002);
  out.y = BALL_RADIUS + 1.95 * Math.sin(Math.PI * flick) ** 0.9;
}

// From the pass onward the ball follows its own path: into space, onto the
// sixth player's foot, into the net. It starts exactly where the dribble left it.
const PASS_AT = PASS.contact;
const passStart = (() => {
  const o = { x: 0, y: 0, z: 0 };
  dribblePosition(PASS_AT, o);
  return o;
})();
const NET = { x: 53.2, y: 1.45, z: -1.6 };
// Where the ball lies when it is struck. It arrives here from the pass and
// stays at rest until contact.
const REST = { x: 33.9, z: 1.3 };
/** Height of the ball when the boot meets it (the bicycle kick). */
const CONTACT_Y = 2.55;
/** How high the lob rises above the straight line from the pass to the contact point. */
const LOB = 1.8;
// The pass: a lob. It leaves Modric's boot at PASS.contact, rises and comes
// down onto the striker at SHOT.impact, at constant horizontal speed.
const lobU = (p: number) => range(p, PASS_AT, SHOT.impact);
const restX = (p: number) => lerp(passStart.x, REST.x, lobU(p));
const restZ = (p: number) => lerp(passStart.z, REST.z, lobU(p));
const lobY = (p: number) => {
  const u = lobU(p);
  return BALL_RADIUS + (CONTACT_Y - BALL_RADIUS) * u + 4 * LOB * u * (1 - u);
};

// After the net is hit the ball follows the original curves unchanged.
const freeX = curve([
  [PASS_AT, passStart.x],
  [0.72, passStart.x + 2.2],
  [0.75, passStart.x + 3.9],
  [SHOT.impact, REST.x],
  [FINISH.netHit, NET.x],
  [0.85, 53.9],
  [1, 53.9],
]);
const freeZ = curve([
  [PASS_AT, passStart.z],
  [0.75, 1.45],
  [SHOT.impact, REST.z],
  [FINISH.netHit, NET.z],
  [0.85, -1.5],
  [1, -1.5],
]);
const freeY = curve([
  [SHOT.impact, CONTACT_Y],
  [0.82, 1.7],
  [FINISH.netHit, NET.y],
  [0.846, 0.55],
  [0.856, BALL_RADIUS],
  [1, BALL_RADIUS],
]);

// From contact to the net the ball flies in a straight line along the ground
// plane, at the elevation that puts it at the net's height when the net is hit,
// under gravity; it leaves at the boot's speed times a contact ratio, is
// pushed up to a cruising speed over the contact time, and reaches the net at
// exactly FINISH.netHit (clock: SHOT.seconds per unit of progress).
const G = 9.8;
const FLIGHT = (() => {
  const T = (FINISH.netHit - SHOT.impact) * SHOT.seconds;
  const dx = NET.x - REST.x;
  const dz = NET.z - REST.z;
  const D = Math.hypot(dx, dz);
  const { bootSpeed, ratio, ramp, brake } = SHOT.launch;
  const v0 = bootSpeed * ratio;
  // The ball enters the net at the speed the original post-net curves start
  // from, so the flight hands over to them without a step in velocity.
  const e = 1e-4;
  const ve = Math.hypot(freeX(FINISH.netHit + e) - freeX(FINISH.netHit), freeZ(FINISH.netHit + e) - freeZ(FINISH.netHit)) / (e * SHOT.seconds);
  // Distance covered = ramp (v0 -> vc, smoothstep) + cruise at vc + brake (vc -> ve, smoothstep).
  const vc = (D - (ramp * v0) / 2 - (brake * ve) / 2) / (T - ramp / 2 - brake / 2);
  return { T, D, ux: dx / D, uz: dz / D, v0, vc, ve, ramp, brake, tan: (NET.y - CONTACT_Y + 0.5 * G * T * T) / D };
})();

/** Distance flown along the ground, in metres, t seconds after contact. */
function flown(t: number) {
  const { v0, vc, ve, ramp, brake, T } = FLIGHT;
  // Integral of a smoothstep blend from a to b over `len` seconds, u = elapsed / len.
  const blend = (a: number, b: number, len: number, u: number) => a * len * u + (b - a) * len * (u * u * u - (u * u * u * u) / 2);
  if (t <= ramp) return blend(v0, vc, ramp, t / ramp);
  const cruiseEnd = T - brake;
  const afterRamp = blend(v0, vc, ramp, 1);
  if (t <= cruiseEnd) return afterRamp + vc * (t - ramp);
  return afterRamp + vc * (cruiseEnd - ramp) + blend(vc, ve, brake, Math.min(1, (t - cruiseEnd) / brake));
}

function flightPosition(p: number, out: { x: number; y: number; z: number }) {
  const t = Math.min(FLIGHT.T, (p - SHOT.impact) * SHOT.seconds);
  const s = flown(t);
  out.x = REST.x + FLIGHT.ux * s;
  out.z = REST.z + FLIGHT.uz * s;
  out.y = CONTACT_Y + FLIGHT.tan * s - 0.5 * G * t * t;
}

function ballPosition(p: number, out: { x: number; y: number; z: number }) {
  dribblePosition(p, out);
  if (p <= PASS_AT) return;
  if (p <= SHOT.impact) {
    out.x = restX(p);
    out.z = restZ(p);
    out.y = lobY(p);
    return;
  }
  if (p <= FINISH.netHit) {
    flightPosition(p, out);
    return;
  }
  out.x = freeX(p);
  out.z = freeZ(p);
  out.y = freeY(p);
}

/** Where the ball is when the captured shot strikes it, and the way it leaves (unit vector, ground plane). */
const SHOT_BALL = (() => {
  const a = { x: 0, y: 0, z: 0 };
  const b = { x: 0, y: 0, z: 0 };
  ballPosition(SHOT.impact, a);
  ballPosition(SHOT.impact + 0.02, b);
  const len = Math.hypot(b.x - a.x, b.z - a.z);
  return { x: a.x, z: a.z, aimX: (b.x - a.x) / len, aimZ: (b.z - a.z) / len };
})();

/** Spin of the airborne ball, rad/s: the lob turns gently; the bicycle kick sends it off about 8 turns a second. */
const AIR_SPIN = { lob: 12, shot: 50 };

/** Ball orientation: it turns by exactly the distance it has travelled on the ground, and at a set rate in the air. */
const BALL_SPIN = (() => {
  const table = new Float32Array((SAMPLES + 1) * 4);
  let qx = 0;
  let qy = 0;
  let qz = 0;
  let qw = 1;
  const a = { x: 0, y: 0, z: 0 };
  const b = { x: 0, y: 0, z: 0 };
  table[3] = 1;
  ballPosition(0, a);
  for (let i = 0; i < SAMPLES; i++) {
    ballPosition((i + 1) / SAMPLES, b);
    const dx = b.x - a.x;
    const dz = b.z - a.z;
    const dist = Math.hypot(dx, dz);
    if (dist > 1e-7) {
      // Rolling axis is up x direction of travel.
      const ax = dz / dist;
      const az = -dx / dist;
      // On the grass the ball turns by the distance it covers. Once it is in the air (the lob, the shot) that
      // would be far too fast, so it spins at a steady rate instead: gently on the lob, hard off the boot.
      const flying = (i + 1) / SAMPLES >= PASS_AT && a.y > BALL_RADIUS + 0.05 && b.y > BALL_RADIUS + 0.05;
      const spinRate = (i + 1) / SAMPLES > SHOT.impact ? AIR_SPIN.shot : AIR_SPIN.lob;
      const half = flying ? (spinRate * (SHOT.seconds / SAMPLES)) / 2 : dist / BALL_RADIUS / 2;
      const s = Math.sin(half);
      const rx = ax * s;
      const rz = az * s;
      const rw = Math.cos(half);
      // q = r * q
      const nx = rw * qx + rx * qw - rz * qy;
      const ny = rw * qy + rz * qx - rx * qz;
      const nz = rw * qz + rz * qw + rx * qy;
      const nw = rw * qw - rx * qx - rz * qz;
      const len = Math.hypot(nx, ny, nz, nw);
      qx = nx / len;
      qy = ny / len;
      qz = nz / len;
      qw = nw / len;
    }
    table.set([qx, qy, qz, qw], (i + 1) * 4);
    a.x = b.x;
    a.y = b.y;
    a.z = b.z;
  }
  return table;
})();

// ── Camera ─────────────────────────────────────────────────────────────────

// The second morph hides in an acceleration burst: the camera drops and
// pushes in as player 3 takes off, then pulls back to track the sprint.
// Later: low and close for the cut, wide for the drive, tight on the plant,
// behind the shooter for the strike, half an orbit round the celebration,
// a still hold, then a slow pull back and rise into the wordmark.
const camX0 = extend(
  extend(curve([[0, 0.8], [0.12, 0.8], [0.22, 1.5], [0.245, 0.7], [0.27, 1.3], [0.35, 2.1]]), 0.35, [[0.375, 1.0], [0.4, 1.7], [0.47, 2.4]]),
  0.47,
  [[0.5, 1.4], [0.52, 1.8], [0.59, 2.2], [0.62, 1.2], [0.64, 1.4], [0.71, 1.8], [0.76, -1.0], [0.79, -3.2], [0.83, -4.2], [0.87, 1.2], [0.93, 1.2], [0.965, 1.2], [1, 2.0]]);
const camX = extend(camX0, 0.7, [[0.71, 1.8], [0.745, 0.6], [0.77, 0.2], [0.79, 0.3], [0.82, -0.9], [0.845, -2.4], [0.87, 1.2], [0.93, 1.2], [0.965, 1.2], [1, 2.0]]);
const camY0 = extend(
  extend(curve([[0, 0.8], [0.12, 0.8], [0.22, 0.55], [0.245, 0.95], [0.27, 1.0], [0.35, 1.2]]), 0.35, [[0.375, 0.75], [0.4, 0.95], [0.47, 1.1]]),
  0.47,
  [[0.5, 0.8], [0.52, 0.95], [0.59, 1.1], [0.62, 1.0], [0.64, 1.15], [0.71, 1.2], [0.76, 1.3], [0.79, 1.5], [0.83, 1.9], [0.87, 1.3], [0.93, 1.4], [0.965, 1.4], [1, 5.2]]);
const camY = extend(camY0, 0.7, [[0.71, 1.2], [0.745, 1.7], [0.77, 1.9], [0.79, 1.8], [0.82, 2.0], [0.845, 1.7], [0.87, 1.3], [0.93, 1.4], [0.965, 1.4], [1, 5.2]]);
const camZ0 = extend(
  extend(curve([[0, 9.6], [0.12, 9.6], [0.22, 5.0], [0.245, 3.5], [0.27, 4.7], [0.35, 5.9]]), 0.35, [[0.375, 3.9], [0.4, 4.9], [0.47, 6.0]]),
  0.47,
  [[0.5, 4.2], [0.52, 5.0], [0.59, 5.8], [0.62, 3.8], [0.64, 4.0], [0.71, 4.8], [0.76, 4.0], [0.79, 3.2], [0.83, 4.4], [0.87, 4.2], [0.93, 4.2], [0.965, 4.2], [1, 12]]);
const camZ = extend(camZ0, 0.7, [[0.71, 4.8], [0.745, 5.6], [0.77, 6.2], [0.79, 6.2], [0.82, 6.8], [0.845, 5.0], [0.87, 4.2], [0.93, 4.2], [0.965, 4.2], [1, 12]]
);
const lookY0 = extend(
  extend(curve([[0, 0.5], [0.12, 0.5], [0.22, 0.75], [0.245, 0.95], [0.35, 1.02]]), 0.35, [[0.375, 0.9], [0.47, 1.0]]),
  0.47,
  [[0.52, 1.0], [0.79, 0.9], [0.83, 1.3], [0.87, 1.1], [0.93, 1.15], [0.965, 1.15], [1, 1.6]]);
const lookY = extend(lookY0, 0.7, [[0.725, 1.0], [0.745, 1.6], [0.77, 1.75], [0.79, 1.65], [0.82, 1.7], [0.845, 1.5], [0.87, 1.1], [0.93, 1.15], [0.965, 1.15], [1, 1.6]]);
/** The half-orbit round the celebration, in radians about the figure. */
const orbit = curve([[0, 0], [0.874, 0], [0.93, Math.PI], [1, Math.PI]]);
/** How much the camera looks at the flying ball rather than the shooter. */
const watchBall = curve([[0, 0], [0.81, 0], [0.822, 1], [0.851, 1], [0.86, 0], [1, 0]]);

/** The extra camera azimuth from the number beats (see NUMBER_BEATS). */
const numberBeat = (p: number, out: { turn: number; zoom: number }) => {
  out.turn = 0;
  out.zoom = 0;
  for (const b of NUMBER_BEATS) {
    if (p <= b.from || p >= b.to) continue;
    const w = bell(p, b.from, b.to);
    out.turn += b.turn * w;
    out.zoom += (b.zoom ?? BEAT_ZOOM) * w;
  }
  return out;
};
const beat = { turn: 0, zoom: 0 };

// ── The sampler ────────────────────────────────────────────────────────────

/** `progress` is scroll progress P (0 to P_MAX); the scene itself is written on the scene scale p (see STRETCH). */
export function sampleScene(progress: number, s: SceneState): SceneState {
  const p = clamp01(toScene(Math.min(Math.max(progress, 0), P_MAX)));

  identityAt(p, s.identity);

  // Figure
  s.actor.x = actorX(p);
  s.actor.z = actorZ(p);
  s.actor.yaw = actorYaw(p);
  const m = s.motion;
  m.phase = fromTable(PHASE, p);
  m.distance = fromTable(DIST, p);
  // Captured running, where the timeline asks for it (realistic mode uses it).
  m.run2 = -1;
  m.runWeight = 0;
  m.runAnchorDistance = 0;
  m.runAnchorPhase = 0;
  for (let k = 0; k < RUNS.length; k++) {
    const r = RUNS[k];
    if (p < r.fadeIn[0] || p > r.fadeOut[1]) continue;
    const w = (r.fadeIn[0] < 0 ? 1 : smoothstep(r.fadeIn[0], r.fadeIn[1], p)) * (1 - smoothstep(r.fadeOut[0], r.fadeOut[1], p));
    if (w <= 0) continue;
    m.run2 = k;
    m.runWeight = w;
    m.runAnchorDistance = fromTable(DIST, r.anchor);
    m.runAnchorPhase = fromTable(PHASE, r.anchor);
  }
  // The captured strike: its clock runs from the moment of contact.
  // The captured strike is not used: the finish is the hand-built bicycle kick.
  m.shotWeight = 0;
  m.shotT = (p - SHOT.impact) * SHOT.seconds;
  m.shotBallX = SHOT_BALL.x;
  m.shotBallZ = SHOT_BALL.z;
  m.shotAimX = SHOT_BALL.aimX;
  m.shotAimZ = SHOT_BALL.aimZ;
  const spin = bell(p, SPIN.from - 0.004, SPIN.to + 0.004);
  m.spin = spin;
  m.run = 1 - 0.45 * spin - 0.35 * bell(p, MOVES.stepovers.from, MOVES.stepovers.to) - 0.6 * bell(p, MOVES.flick.from, MOVES.flick.to);
  m.feint = bell(p, MOVES.feint.from, 0.188) - 0.85 * bell(p, 0.184, MOVES.feint.to);
  m.pass = 0;
  m.passT = 0;
  m.touch = 0;
  m.touchT = 0;
  m.kick = 0.55 * bell(p, MOVES.push.from, MOVES.push.to);
  m.kickT = range(p, MOVES.push.from, MOVES.push.to);
  for (const push of MOVES.pushes) {
    if (p > push.from && p < push.to) {
      m.kick = 0.7 * bell(p, push.from, push.to);
      m.kickT = range(p, push.from, push.to);
    }
  }
  const so = range(p, MOVES.stepovers.from, MOVES.stepovers.to);
  m.stepover = Math.sin(so * TAU * 1.5) * bell(p, MOVES.stepovers.from, MOVES.stepovers.to);
  m.flick = bell(p, MOVES.flick.from - 0.004, MOVES.flick.to - 0.008);
  m.flickT = range(p, MOVES.flick.from - 0.004, MOVES.flick.to - 0.008);
  m.air = 0.16 * bell(p, MOVES.flick.from, MOVES.flick.to - 0.012);
  if (p > TOUCH.from && p < TOUCH.to) {
    m.touch = bell(p, TOUCH.from, TOUCH.to);
    m.touchT = range(p, TOUCH.from, TOUCH.to);
  }
  if (p > PASS.from && p < PASS.to) {
    m.passT = range(p, PASS.from, PASS.to);
    // Fully in the pass from just before the plant until the captured run takes over.
    m.pass = smoothstep(PASS.from, PASS.from + 0.008, p) * (1 - smoothstep(PASS.to - 0.014, PASS.to, p));
  }
  // Player 5 slows to control; player 6 stops after the shot and celebrates.
  if (p > 0.47) {
    m.run *= Math.max(0, 1 - 0.7 * bell(p, 0.64, 0.7) - 0.6 * smoothstep(0.8, 0.83, p) - 0.4 * smoothstep(0.85, 0.87, p));
  }
  // The bicycle kick, contact at SHOT.impact; the sprint into it stops and the gait is left behind.
  m.bike = smoothstep(FINISH.strike.from, FINISH.strike.from + 0.01, p) * (1 - smoothstep(FINISH.strike.to - 0.012, FINISH.strike.to, p));
  m.bikeT = range(p, FINISH.strike.from, FINISH.strike.to);
  m.bikeHip = bikeHipHeight(m.bikeT);
  // The run-up stops at the plant; a few strides then take him to the jump.
  m.run = m.run * (1 - smoothstep(0.745, 0.765, p)) + 0.85 * smoothstep(0.848, 0.858, p) * (1 - smoothstep(0.872, 0.882, p));
  m.celebrate = smoothstep(FINISH.celebrate.from, 0.9, p);
  m.air = Math.max(m.air, 0.55 * bell(p, FINISH.jump.from, FINISH.jump.to));
  // Gather before take-off and give a little on landing.
  m.crouch = 0.7 * bell(p, FINISH.jump.from - 0.014, FINISH.jump.from + 0.004) + 0.55 * bell(p, FINISH.jump.to - 0.004, FINISH.jump.to + 0.012);

  // Ball
  ballPosition(p, s.ball);
  const f = p * SAMPLES;
  const i = Math.min(SAMPLES - 1, Math.floor(f));
  const k = f - i;
  // Neighbouring samples are a fraction of a degree apart, so a normalised
  // lerp is indistinguishable from a slerp here.
  const o = i * 4;
  let qx = lerp(BALL_SPIN[o], BALL_SPIN[o + 4], k);
  let qy = lerp(BALL_SPIN[o + 1], BALL_SPIN[o + 5], k);
  let qz = lerp(BALL_SPIN[o + 2], BALL_SPIN[o + 6], k);
  let qw = lerp(BALL_SPIN[o + 3], BALL_SPIN[o + 7], k);
  const len = Math.hypot(qx, qy, qz, qw);
  qx /= len;
  qy /= len;
  qz /= len;
  qw /= len;
  s.ball.qx = qx;
  s.ball.qy = qy;
  s.ball.qz = qz;
  s.ball.qw = qw;

  // Camera: fixed on the spot the ball rolls to, then tracking the figure.
  // From the cut onward it also follows the figure sideways, glances at the
  // ball in flight, and orbits half round the celebration.
  const follow = smoothstep(0.11, 0.18, p);
  const watch = watchBall(p);
  const focusX = lerp(lerp(-8.1, s.actor.x + 0.55, follow), s.ball.x, watch * 0.92);
  const breathe = (1 - follow) * 0.035;
  const sideways = smoothstep(0.47, 0.5, p);
  numberBeat(p, beat);
  const a = orbit(p) + beat.turn;
  const ox = camX(p) * (1 - beat.zoom);
  const oz = camZ(p) * (1 - beat.zoom);
  s.camera.x = focusX + ox * Math.cos(a) + oz * Math.sin(a) + Math.sin(p * 60) * breathe;
  s.camera.y = camY(p) + Math.cos(p * 47) * breathe * 0.6;
  s.camera.z = s.actor.z * sideways + oz * Math.cos(a) - ox * Math.sin(a);
  s.camera.tx = focusX;
  s.camera.ty = lerp(lookY(p), s.ball.y, watch * 0.8);
  s.camera.tz = lerp(s.actor.z * lerp(0.5, 1, sideways) * follow, s.ball.z, watch * 0.92);

  // Lights come up one bank at a time, then hold steady for the whole run.
  s.light.pool = smoothstep(0.012, 0.03, p) * (1 - 0.55 * smoothstep(0.05, 0.1, p));
  s.light.floodA = smoothstep(0.016, 0.034, p);
  s.light.floodB = smoothstep(0.04, 0.058, p);
  s.light.key = smoothstep(0.045, 0.075, p);
  s.light.ambient = 0.12 + 0.88 * smoothstep(0.03, 0.08, p);

  // The goal: the net bulges where the ball hits it, sparks rise over the
  // goalmouth and the floodlights surge for the celebration.
  // 1 from the moment the ball touches the net until the cloth has settled (about 1.5 s); netT is the seconds since.
  s.goal.net = p > FINISH.netHit ? 1 - smoothstep(FINISH.netHit + 0.1, FINISH.netHit + 0.11, p) : 0;
  s.goal.netT = Math.max(0, p - FINISH.netHit) * SHOT.seconds;
  s.goal.netX = NET.x;
  s.goal.netY = NET.y;
  s.goal.netZ = NET.z;
  s.goal.burst = range(p, FINISH.netHit, FINISH.netHit + 0.07);
  s.goal.surge = bell(p, FINISH.netHit, 0.95);
  s.light.floodA += 0.7 * s.goal.surge;
  s.light.floodB += 0.7 * s.goal.surge;
  s.brand = smoothstep(FINISH.brand.from, FINISH.brand.to, p);

  // The ending. The shake is a fixed function of progress (a decaying burst of
  // incommensurate sines), so scrolling back through it reproduces it exactly.
  const fin = s.finale;
  const sh = ENDING.shake;
  fin.shake = smoothstep(sh.from, sh.from + 0.003, p) * (1 - smooth(range(p, sh.from + 0.003, sh.to))) ** 2;
  fin.shakeX = fin.shake * Math.sin(p * 2900);
  fin.shakeY = fin.shake * Math.cos(p * 2300);
  fin.shakeRot = fin.shake * Math.sin(p * 3300);
  fin.shoutIn = smoothstep(ENDING.shout.in[0], ENDING.shout.in[1], p);
  fin.shout = fin.shoutIn * (1 - smoothstep(ENDING.shout.out[0], ENDING.shout.out[1], p));
  fin.black = smooth(range(p, ENDING.black.from, ENDING.black.to));
  fin.line1 = smooth(range(p, ENDING.line1.from, ENDING.line1.to));
  fin.line2 = smooth(range(p, ENDING.line2.from, ENDING.line2.to));
  // A small camera impulse on the landing, from the same envelope.
  s.camera.x += 0.03 * fin.shakeX;
  s.camera.y += 0.03 * fin.shakeY;

  // Morph cover
  // Each morph kicks up dust where it starts and softens focus briefly.
  let cover = MORPHS[0];
  for (const w of MORPHS) if (p >= w.from - 0.03) cover = w;
  s.dust.t = range(p, cover.from - 0.002, cover.to + 0.012);
  s.dust.x = actorX(cover.from + 0.02);
  s.dust.z = actorZ(cover.from + 0.02);
  s.blur = bell(p, cover.from, cover.to);

  // Caption
  s.caption.player = -1;
  s.caption.alpha = 0;
  for (const seg of SEGMENTS) {
    if (seg.player === undefined || p < seg.from || p > seg.to) continue;
    s.caption.player = seg.player;
    s.caption.alpha = smooth(range(p, seg.from, seg.from + 0.012)) * (1 - smooth(range(p, seg.to - 0.012, seg.to)));
  }

  return s;
}
