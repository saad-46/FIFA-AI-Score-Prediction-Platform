/**
 * Player profiles.
 *
 * Each one is an original stylised figure. The name is the footballer whose
 * playing style inspired the profile and is shown only as a caption; nothing
 * here models a real face or likeness, and no real kit, crest or sponsor is
 * reproduced.
 *
 * Shirt numbers (kit.number) are the number each footballer wears for the
 * national team whose colours the profile's kit echoes: Messi 10 (sky blue and
 * white), Neymar 10 (yellow), Mbappe 10 (blue), Modric 10 (red-and-white
 * check), Ronaldo 7 (red). Haaland's sky-blue kit is a club-style colour with
 * no national side to key it to; 9 is the number he wears at both his club and
 * Norway. Mbappe wears 10 for France (9 at his club). The numbers are a
 * caption-level detail: the kits themselves stay original.
 *
 * Kane (index 7) wears 9, the number he wears for England (his club number is 9
 * too), on a white England-style kit; Haaland's 9 follows his Norway-style kit.
 * Salah (index 6) wears 11: the number he wears for Liverpool, whose red the
 * profile's Liverpool-inspired kit echoes (he wears 10 for Egypt, whose kit
 * this is not). The roster's other numbers follow the national side a kit
 * echoes; Salah's follows the club one because the kit is explicitly a
 * Liverpool-style red.
 */

/** Body proportions in metres, standing, feet on the ground. */
export interface BodyShape {
  height: number;
  /** Hip-joint height as a fraction of total height. */
  legFrac: number;
  /** Half-widths (x) and half-depths (z). */
  shoulderHalf: number;
  chestHalf: number;
  chestDepth: number;
  waistHalf: number;
  waistDepth: number;
  hipHalf: number;
  hipDepth: number;
  /** Limb radii. */
  thigh: number;
  calf: number;
  upperArm: number;
  foreArm: number;
  neck: number;
  /** Head half-extents. */
  headX: number;
  headY: number;
  headZ: number;
  /** Arm length multiplier. */
  arm: number;
  /** Sleeve length as a fraction of the upper arm. */
  sleeve: number;
}

export type ShirtPattern = "solid" | "stripes" | "checker";

export interface Kit {
  shirt: string;
  shirt2: string;
  pattern: ShirtPattern;
  shorts: string;
  socks: string;
  boots: string;
  /** Rim-light tint that follows the kit. */
  rim: string;
  /**
   * The shirt number (realistic figures only; the procedural figure has none)
   * and its two colours: the digit and its thin outline.
   */
  number: number;
  numberInk: string;
  numberEdge: string;
}

/** How the figure moves. Blended like the body, so the gait changes too. */
export interface Stride {
  /** Ground covered by one full cycle (two steps), in metres. */
  length: number;
  swing: number;
  knee: number;
  arm: number;
  elbow: number;
  lean: number;
  bounce: number;
  sway: number;
  twist: number;
  crouch: number;
}

export type HairId = "short" | "mohawk";
export type BeardId = "none" | "short";

export interface PlayerProfile {
  /** Caption only. */
  name: string;
  tagline: string;
  body: BodyShape;
  skin: string;
  hair: HairId;
  hairColor: string;
  beard: BeardId;
  kit: Kit;
  stride: Stride;
}

export const PLAYERS: readonly PlayerProfile[] = [
  {
    name: "Messi",
    tagline: "Close control",
    body: {
      height: 1.66,
      legFrac: 0.495,
      shoulderHalf: 0.215,
      chestHalf: 0.172,
      chestDepth: 0.118,
      waistHalf: 0.152,
      waistDepth: 0.108,
      hipHalf: 0.168,
      hipDepth: 0.115,
      thigh: 0.086,
      calf: 0.06,
      upperArm: 0.05,
      foreArm: 0.041,
      neck: 0.056,
      headX: 0.094,
      headY: 0.116,
      headZ: 0.102,
      arm: 0.97,
      sleeve: 0.55,
    },
    skin: "#dba884",
    hair: "short",
    hairColor: "#2a1c14",
    beard: "short",
    kit: {
      shirt: "#7cc4f2",
      shirt2: "#f4f7fb",
      pattern: "stripes",
      shorts: "#141a2b",
      socks: "#f4f7fb",
      boots: "#e9edf3",
      rim: "#7cc4f2",
      number: 10,
      numberInk: "#0b1f3a",
      numberEdge: "#ffffff",
    },
    stride: {
      length: 1.85,
      swing: 0.58,
      knee: 1.15,
      arm: 0.55,
      elbow: 1.3,
      lean: 0.24,
      bounce: 0.02,
      sway: 0.05,
      twist: 0.2,
      crouch: 0.42,
    },
  },
  {
    name: "Neymar",
    tagline: "Flair",
    body: {
      height: 1.81,
      legFrac: 0.535,
      shoulderHalf: 0.2,
      chestHalf: 0.152,
      chestDepth: 0.1,
      waistHalf: 0.124,
      waistDepth: 0.09,
      hipHalf: 0.146,
      hipDepth: 0.1,
      thigh: 0.07,
      calf: 0.049,
      upperArm: 0.045,
      foreArm: 0.038,
      neck: 0.049,
      headX: 0.088,
      headY: 0.114,
      headZ: 0.097,
      arm: 1.04,
      sleeve: 0.42,
    },
    skin: "#b98258",
    hair: "mohawk",
    hairColor: "#3a2616",
    beard: "none",
    kit: {
      shirt: "#f7d436",
      shirt2: "#f7d436",
      pattern: "solid",
      shorts: "#124a3a",
      socks: "#f7d436",
      boots: "#17c7b1",
      rim: "#f7d436",
      number: 10,
      numberInk: "#0b6b34",
      numberEdge: "#ffffff",
    },
    stride: {
      length: 2.5,
      swing: 0.72,
      knee: 1.3,
      arm: 0.78,
      elbow: 1.0,
      lean: 0.12,
      bounce: 0.05,
      sway: 0.12,
      twist: 0.28,
      crouch: 0.1,
    },
  },
  {
    name: "Mbappé",
    tagline: "Pace",
    body: {
      height: 1.78,
      legFrac: 0.53,
      shoulderHalf: 0.205,
      chestHalf: 0.158,
      chestDepth: 0.104,
      waistHalf: 0.126,
      waistDepth: 0.092,
      hipHalf: 0.148,
      hipDepth: 0.102,
      thigh: 0.076,
      calf: 0.052,
      upperArm: 0.046,
      foreArm: 0.038,
      neck: 0.052,
      headX: 0.09,
      headY: 0.113,
      headZ: 0.099,
      arm: 1.0,
      sleeve: 0.45,
    },
    skin: "#8a5a3c",
    hair: "short",
    hairColor: "#1f1712",
    beard: "none",
    kit: {
      shirt: "#2449c8",
      shirt2: "#2449c8",
      pattern: "solid",
      shorts: "#0f1a3d",
      socks: "#2449c8",
      boots: "#f2f4f7",
      rim: "#4f7dff",
      number: 10,
      numberInk: "#ffffff",
      numberEdge: "#0c1f66",
    },
    stride: {
      length: 2.9,
      swing: 0.8,
      knee: 1.35,
      arm: 0.85,
      elbow: 0.95,
      lean: 0.2,
      bounce: 0.04,
      sway: 0.06,
      twist: 0.22,
      crouch: 0.12,
    },
  },
  {
    name: "Haaland",
    tagline: "Power",
    body: {
      height: 1.94,
      legFrac: 0.535,
      shoulderHalf: 0.235,
      chestHalf: 0.19,
      chestDepth: 0.128,
      waistHalf: 0.16,
      waistDepth: 0.115,
      hipHalf: 0.17,
      hipDepth: 0.12,
      thigh: 0.09,
      calf: 0.064,
      upperArm: 0.054,
      foreArm: 0.045,
      neck: 0.06,
      headX: 0.092,
      headY: 0.116,
      headZ: 0.1,
      arm: 1.0,
      sleeve: 0.48,
    },
    skin: "#e8c3a4",
    hair: "short",
    hairColor: "#c9a766",
    beard: "none",
    kit: {
      shirt: "#8fcdf2",
      shirt2: "#8fcdf2",
      pattern: "solid",
      shorts: "#f2f5f9",
      socks: "#8fcdf2",
      boots: "#1b2233",
      rim: "#8fcdf2",
      number: 9,
      numberInk: "#10325a",
      numberEdge: "#ffffff",
    },
    stride: {
      length: 3.0,
      swing: 0.85,
      knee: 1.2,
      arm: 0.7,
      elbow: 1.1,
      lean: 0.25,
      bounce: 0.06,
      sway: 0.05,
      twist: 0.18,
      crouch: 0.15,
    },
  },
  {
    name: "Modrić",
    tagline: "Vision",
    body: {
      height: 1.72,
      legFrac: 0.52,
      shoulderHalf: 0.2,
      chestHalf: 0.152,
      chestDepth: 0.1,
      waistHalf: 0.126,
      waistDepth: 0.09,
      hipHalf: 0.145,
      hipDepth: 0.1,
      thigh: 0.07,
      calf: 0.05,
      upperArm: 0.042,
      foreArm: 0.036,
      neck: 0.05,
      headX: 0.092,
      headY: 0.116,
      headZ: 0.1,
      arm: 1.0,
      sleeve: 0.48,
    },
    skin: "#e2b494",
    hair: "short",
    hairColor: "#b49270",
    beard: "none",
    kit: {
      shirt: "#f4f4f4",
      shirt2: "#d7263d",
      pattern: "checker",
      shorts: "#f4f4f4",
      socks: "#24357d",
      boots: "#f2f4f7",
      rim: "#ff5a6e",
      number: 10,
      numberInk: "#14224f",
      numberEdge: "#ffffff",
    },
    stride: {
      length: 2.4,
      swing: 0.62,
      knee: 1.1,
      arm: 0.6,
      elbow: 1.2,
      lean: 0.05,
      bounce: 0.03,
      sway: 0.06,
      twist: 0.2,
      crouch: 0.05,
    },
  },
  {
    name: "Ronaldo",
    tagline: "The finish",
    body: {
      height: 1.87,
      legFrac: 0.54,
      shoulderHalf: 0.225,
      chestHalf: 0.175,
      chestDepth: 0.118,
      waistHalf: 0.14,
      waistDepth: 0.1,
      hipHalf: 0.155,
      hipDepth: 0.108,
      thigh: 0.082,
      calf: 0.058,
      upperArm: 0.05,
      foreArm: 0.042,
      neck: 0.056,
      headX: 0.092,
      headY: 0.116,
      headZ: 0.1,
      arm: 1.0,
      sleeve: 0.48,
    },
    skin: "#d3a07c",
    hair: "short",
    hairColor: "#1d1611",
    beard: "none",
    kit: {
      shirt: "#c8102e",
      shirt2: "#c8102e",
      pattern: "solid",
      shorts: "#7d0b1d",
      socks: "#c8102e",
      boots: "#f2f4f7",
      rim: "#ff4a5e",
      number: 7,
      numberInk: "#ffffff",
      numberEdge: "#5a0a14",
    },
    stride: {
      length: 2.7,
      swing: 0.75,
      knee: 1.25,
      arm: 0.8,
      elbow: 1.0,
      lean: 0.1,
      bounce: 0.05,
      sway: 0.05,
      twist: 0.24,
      crouch: 0.1,
    },
  },
  {
    // Index 6: the seventh character was added after the first six, so it is the
    // last morph target in players.glb; the timeline puts him between Haaland and
    // Modric (see MORPHS), which keeps Ronaldo last.
    name: "Salah",
    tagline: "Movement",
    body: {
      height: 1.75,
      legFrac: 0.53,
      shoulderHalf: 0.205,
      chestHalf: 0.16,
      chestDepth: 0.108,
      waistHalf: 0.128,
      waistDepth: 0.092,
      hipHalf: 0.145,
      hipDepth: 0.1,
      thigh: 0.075,
      calf: 0.054,
      upperArm: 0.046,
      foreArm: 0.038,
      neck: 0.052,
      headX: 0.088,
      headY: 0.112,
      headZ: 0.096,
      arm: 0.98,
      sleeve: 0.5,
    },
    skin: "#b58762",
    hair: "short",
    hairColor: "#16100c",
    beard: "none",
    kit: {
      // A Liverpool-inspired red, kept apart from Ronaldo's (c8102e) by a warmer
      // red; no crest, sponsor or official detail.
      shirt: "#e4232d",
      shirt2: "#e4232d",
      pattern: "solid",
      shorts: "#d41e29",
      socks: "#e4232d",
      boots: "#1b1f27",
      rim: "#ff5a52",
      number: 11,
      numberInk: "#ffffff",
      numberEdge: "#6d0c15",
    },
    stride: {
      // Haaland's stride length on purpose: the run phase is the integral of ground covered over
      // stride length, so sharing it keeps every later foot placement (the pass, the plant) where it was tuned.
      length: 3.0,
      swing: 0.7,
      knee: 1.2,
      arm: 0.7,
      elbow: 1.1,
      lean: 0.14,
      bounce: 0.04,
      sway: 0.05,
      twist: 0.22,
      crouch: 0.08,
    },
  },
  {
    // Index 7: the eighth character, added after Salah, so it is the last morph
    // target in players.glb; the timeline puts him between Haaland and Salah
    // (see MORPHS). Ronaldo stays last.
    name: "Kane",
    tagline: "The finisher",
    body: {
      height: 1.88,
      legFrac: 0.53,
      shoulderHalf: 0.222,
      chestHalf: 0.17,
      chestDepth: 0.115,
      waistHalf: 0.138,
      waistDepth: 0.098,
      hipHalf: 0.152,
      hipDepth: 0.105,
      thigh: 0.08,
      calf: 0.057,
      upperArm: 0.049,
      foreArm: 0.041,
      neck: 0.056,
      headX: 0.092,
      headY: 0.116,
      headZ: 0.1,
      arm: 1.0,
      sleeve: 0.5,
    },
    skin: "#e0b498",
    hair: "short",
    hairColor: "#5a4632",
    beard: "none",
    kit: {
      // England-inspired: white shirt, navy shorts, white socks; no crest or official detail.
      shirt: "#f3f5f9",
      shirt2: "#f3f5f9",
      pattern: "solid",
      shorts: "#16245a",
      socks: "#f3f5f9",
      boots: "#202633",
      rim: "#cfe0ff",
      number: 9,
      numberInk: "#16245a",
      numberEdge: "#ffffff",
    },
    stride: {
      // Haaland's stride length on purpose (see Salah): it keeps the run phase, and with it every later foot placement, as tuned.
      length: 3.0,
      swing: 0.72,
      knee: 1.15,
      arm: 0.75,
      elbow: 1.1,
      lean: 0.12,
      bounce: 0.04,
      sway: 0.05,
      twist: 0.22,
      crouch: 0.08,
    },
  },
];

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export function lerpStride(a: Stride, b: Stride, t: number, out: Stride): Stride {
  out.length = lerp(a.length, b.length, t);
  out.swing = lerp(a.swing, b.swing, t);
  out.knee = lerp(a.knee, b.knee, t);
  out.arm = lerp(a.arm, b.arm, t);
  out.elbow = lerp(a.elbow, b.elbow, t);
  out.lean = lerp(a.lean, b.lean, t);
  out.bounce = lerp(a.bounce, b.bounce, t);
  out.sway = lerp(a.sway, b.sway, t);
  out.twist = lerp(a.twist, b.twist, t);
  out.crouch = lerp(a.crouch, b.crouch, t);
  return out;
}
