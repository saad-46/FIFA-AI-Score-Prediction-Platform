import { Quaternion } from "three";
import { BONE_COUNT } from "./body-geometry";

/** Where the baked running cycles are served from. See ASSETS.md for their sources and licence. */
export const RUN_CYCLES_URL = "/intro/runs.json";

/** The captured runs, by the segment they serve (see RUNS in timeline.ts). */
export type RunClips = Partial<Record<string, RunCycle>>;

/** Validates the file of clips; any unusable clip is left out, and that segment stays hand-built. */
export function parseRunClips(json: unknown): RunClips | null {
  const d = json as { format?: unknown; clips?: unknown } | null;
  if (!d || d.format !== "quaternion" || !d.clips || typeof d.clips !== "object") return null;
  const out: RunClips = {};
  for (const [name, clip] of Object.entries(d.clips as Record<string, unknown>)) {
    const parsed = parseRunCycle(clip);
    if (parsed) out[name] = parsed;
  }
  return Object.keys(out).length ? out : null;
}

/**
 * One stride of motion capture, retargeted offline onto the pose system's 17
 * bones (see ASSETS.md). Each frame holds parent-relative rotations, in the
 * pose system's axes, as quaternions (x, y, z, w). The cycle starts when the
 * left thigh is furthest forward, which is phase pi/2 in the pose system, so
 * it can be indexed by the existing run phase.
 */
export interface RunCycle {
  source: string;
  frames: number;
  /** Ground covered by one cycle, as a multiple of leg length (hip to ankle). */
  strideOverLeg: number;
  /** frames x BONE_COUNT x 4. */
  rotations: Float32Array;
  /** Per frame: how far the body is ahead of an even pace, as a multiple of leg length. */
  rootForward: Float32Array;
  /** Per frame: hip height above the ground, as a multiple of leg length; and the same standing. */
  hipHeight: Float32Array;
  restHipHeight: number;
  /** Per frame: which feet the source runner had planted (bit 1 left, bit 2 right). For measurement only. */
  contact: Uint8Array;
}

const finiteArray = (v: unknown, n: number): v is number[] =>
  Array.isArray(v) && v.length === n && v.every((x) => typeof x === "number" && Number.isFinite(x));

/** Validates the baked file; returns null if it is not usable. */
export function parseRunCycle(json: unknown): RunCycle | null {
  const d = json as Record<string, unknown> | null;
  if (!d || d.format !== "quaternion" || typeof d.frames !== "number" || typeof d.strideOverLeg !== "number") return null;
  const frames = d.frames;
  if (frames < 2 || !Array.isArray(d.bones) || d.bones.length !== BONE_COUNT || !Array.isArray(d.rotations) || d.rotations.length !== frames) return null;
  const rotations = new Float32Array(frames * BONE_COUNT * 4);
  for (let f = 0; f < frames; f++) {
    const row = d.rotations[f];
    if (!finiteArray(row, BONE_COUNT * 4)) return null;
    rotations.set(row, f * BONE_COUNT * 4);
  }
  if (!finiteArray(d.rootForward, frames) || !finiteArray(d.hipHeight, frames) || typeof d.restHipHeight !== "number") return null;
  return {
    source: String(d.source ?? ""),
    frames,
    strideOverLeg: d.strideOverLeg,
    rotations,
    rootForward: Float32Array.from(d.rootForward),
    hipHeight: Float32Array.from(d.hipHeight),
    restHipHeight: d.restHipHeight,
    contact: finiteArray(d.contact, frames) ? Uint8Array.from(d.contact) : new Uint8Array(frames),
  };
}

const TAU = Math.PI * 2;

/** Which two baked frames a run phase falls between, and how far. */
function locate(cycle: RunCycle, phase: number) {
  const n = cycle.frames;
  let frac = (phase - Math.PI / 2) / TAU;
  frac -= Math.floor(frac);
  const f = frac * n;
  const i = Math.floor(f) % n;
  return { i, j: (i + 1) % n, k: f - Math.floor(f) };
}

/** The source runner's planted feet at the frame nearest a run phase. */
export function sampleContact(cycle: RunCycle, phase: number): number {
  const { i, j, k } = locate(cycle, phase);
  return cycle.contact[k < 0.5 ? i : j];
}

/** A per-frame track of the cycle at a run phase, interpolated. */
export function sampleTrack(cycle: RunCycle, track: Float32Array, phase: number): number {
  const { i, j, k } = locate(cycle, phase);
  return track[i] + (track[j] - track[i]) * k;
}

const qa = new Quaternion();
const qb = new Quaternion();

/**
 * The cycle's rotation for one bone at a run phase: a slerp between the two
 * nearest baked frames (the short way round, across the loop seam too). A
 * pure function of the phase.
 */
export function sampleRunRotation(cycle: RunCycle, bone: number, phase: number, out: Quaternion): Quaternion {
  const { i, j, k } = locate(cycle, phase);
  const r = cycle.rotations;
  const a = (i * BONE_COUNT + bone) * 4;
  const b = (j * BONE_COUNT + bone) * 4;
  qa.set(r[a], r[a + 1], r[a + 2], r[a + 3]);
  qb.set(r[b], r[b + 1], r[b + 2], r[b + 3]);
  return out.slerpQuaternions(qa, qb, k);
}

// ── The shot: one non-looping strike ───────────────────────────────────────

/** Where the baked shot is served from. See ASSETS.md for its source and licence. */
export const SHOT_CLIP_URL = "/intro/shot.json";

/**
 * One soccer strike of motion capture, retargeted offline onto the same 17
 * bones as the runs (see ASSETS.md). Unlike a run it is not a cycle: it runs
 * from the approach to the follow-through, with `impact` the frame where the
 * kicking foot is fastest. The figure axes are +Z along the kick.
 */
export interface ShotClip {
  source: string;
  fps: number;
  frames: number;
  /** The frame of ball contact. */
  impact: number;
  /** frames x BONE_COUNT x 4. */
  rotations: Float32Array;
  /** Per frame: hip height above the ground, as a multiple of leg length; and the same standing. */
  hipHeight: Float32Array;
  restHipHeight: number;
  /** Per frame: the body's travel relative to its place at impact, in leg lengths (x left, z along the kick). */
  rootX: Float32Array;
  rootZ: Float32Array;
  /** Per frame: which feet the source player had planted (bit 1 left, bit 2 right). */
  contact: Uint8Array;
}

/** Validates the baked shot; returns null if it is not usable. */
export function parseShotClip(json: unknown): ShotClip | null {
  const d = json as Record<string, unknown> | null;
  if (!d || d.format !== "quaternion" || typeof d.frames !== "number" || typeof d.impact !== "number" || typeof d.fps !== "number") return null;
  const frames = d.frames;
  if (!(d.fps > 0) || frames < 8 || d.impact < 1 || d.impact > frames - 2) return null;
  if (!Array.isArray(d.bones) || d.bones.length !== BONE_COUNT || !Array.isArray(d.rotations) || d.rotations.length !== frames) return null;
  const rotations = new Float32Array(frames * BONE_COUNT * 4);
  for (let f = 0; f < frames; f++) {
    const row = d.rotations[f];
    if (!finiteArray(row, BONE_COUNT * 4)) return null;
    // Every bone must be (close to) a unit quaternion, or the pose would shear.
    for (let b = 0; b < BONE_COUNT; b++) {
      const n = Math.hypot(row[b * 4], row[b * 4 + 1], row[b * 4 + 2], row[b * 4 + 3]);
      if (!(Math.abs(n - 1) < 0.05)) return null;
    }
    rotations.set(row, f * BONE_COUNT * 4);
  }
  if (!finiteArray(d.hipHeight, frames) || !finiteArray(d.rootX, frames) || !finiteArray(d.rootZ, frames) || typeof d.restHipHeight !== "number") return null;
  return {
    source: String(d.source ?? ""),
    fps: d.fps,
    frames,
    impact: d.impact,
    rotations,
    hipHeight: Float32Array.from(d.hipHeight),
    restHipHeight: d.restHipHeight,
    rootX: Float32Array.from(d.rootX),
    rootZ: Float32Array.from(d.rootZ),
    contact: finiteArray(d.contact, frames) ? Uint8Array.from(d.contact) : new Uint8Array(frames),
  };
}

/** Which two baked frames a time (seconds, 0 at impact) falls between, and how far; clamped to the clip. */
function shotLocate(clip: ShotClip, t: number) {
  const f = Math.min(clip.frames - 1, Math.max(0, clip.impact + t * clip.fps));
  const i = Math.min(clip.frames - 2, Math.floor(f));
  return { i, j: i + 1, k: f - i };
}

/** The shot's rotation for one bone at a time relative to impact: a slerp between the two nearest frames. */
export function sampleShotRotation(clip: ShotClip, bone: number, t: number, out: Quaternion): Quaternion {
  const { i, j, k } = shotLocate(clip, t);
  const r = clip.rotations;
  const a = (i * BONE_COUNT + bone) * 4;
  const b = (j * BONE_COUNT + bone) * 4;
  qa.set(r[a], r[a + 1], r[a + 2], r[a + 3]);
  qb.set(r[b], r[b + 1], r[b + 2], r[b + 3]);
  return out.slerpQuaternions(qa, qb, k);
}

/** A per-frame track of the shot at a time relative to impact, interpolated. */
export function sampleShotTrack(clip: ShotClip, track: Float32Array, t: number): number {
  const { i, j, k } = shotLocate(clip, t);
  return track[i] + (track[j] - track[i]) * k;
}

/** The planted feet at the frame nearest a time relative to impact. */
export function sampleShotContact(clip: ShotClip, t: number): number {
  const { i, j, k } = shotLocate(clip, t);
  return clip.contact[k < 0.5 ? i : j];
}
