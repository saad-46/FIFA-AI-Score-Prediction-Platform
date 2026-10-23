/**
 * The intro's timeline: the single place where segment boundaries live.
 *
 * Everything is expressed in progress `p`, 0 at the top of the intro and 1 at
 * the end of the full six-player sequence. Tune the choreography here; nothing
 * else in the intro hard-codes when a segment starts or ends.
 */

/** Scroll length of the complete sequence, in viewport heights. */
export const FULL_SCROLL_VH = 700;

/**
 * How much of the sequence is built so far. The pinned section is sized to
 * this fraction of FULL_SCROLL_VH, so one viewport of scrolling already covers
 * the same amount of action it will in the finished intro.
 */
export const BUILT_UNTIL = 0.35;

/**
 * The realistic footballers (opt-in, ?introCharacter=realistic) run the whole
 * sequence: six players, the goal, the celebration and the branding. The
 * procedural default stays at BUILT_UNTIL.
 */
// BUILT_UNTIL_REALISTIC is P_MAX, defined with the stretch below.

export interface MorphWindow {
  /** Index into PLAYERS of the outgoing and incoming profile. */
  a: number;
  b: number;
  from: number;
  to: number;
  /** The move that hides it. */
  cover: "spin" | "burst" | "cut" | "push" | "turn" | "approach";
}

/**
 * Progress has two scales. Every window in this file (and in sample-scene.ts)
 * is written on the *scene scale* `p`, 0 to 1, which is how the six-player
 * sequence was tuned and tested. Kane and Salah (the seventh and eighth
 * players) share Haaland's driving run and the start of the turn, between
 * Haaland and Modric, and need more scroll than that stretch of `p` gave one
 * player: so scroll progress `P` (what the scroll binding writes, 0 to P_MAX)
 * stretches 0.52 to 0.62 by STRETCH.factor and is the identity before it. The
 * scene is then sampled at toScene(P); nothing inside it knows.
 */
export const STRETCH = { from: 0.52, to: 0.62, factor: 2.8 } as const;
/** How much longer the scroll is than the scene scale. */
export const P_EXTRA = (STRETCH.to - STRETCH.from) * (STRETCH.factor - 1);
export const P_MAX = 1 + P_EXTRA;
export const BUILT_UNTIL_REALISTIC = P_MAX;

/** Scroll progress P to scene progress p. */
export function toScene(P: number): number {
  const a = STRETCH.from;
  if (P <= a) return P;
  const len = (STRETCH.to - STRETCH.from) * STRETCH.factor;
  if (P < a + len) return a + (P - a) / STRETCH.factor;
  return P - P_EXTRA;
}

/** Scene progress p to scroll progress P (the inverse of toScene). */
export function fromScene(p: number): number {
  const a = STRETCH.from;
  if (p <= a) return p;
  if (p < STRETCH.to) return a + (p - a) * STRETCH.factor;
  return p + P_EXTRA;
}

/** One entry per player-to-player transformation. */
export const MORPHS: readonly MorphWindow[] = [
  { a: 0, b: 1, from: 0.22, to: 0.27, cover: "spin" },
  { a: 1, b: 2, from: 0.35, to: 0.4, cover: "burst" },
  { a: 2, b: 3, from: 0.47, to: 0.52, cover: "cut" },
  // Kane (index 7) takes over Haaland's drive on the first heavy touch, Salah
  // (6) from Kane on the second, and Salah hands on to Modric through the turn.
  { a: 3, b: 7, from: 0.543, to: 0.557, cover: "push" },
  { a: 7, b: 6, from: 0.576, to: 0.59, cover: "push" },
  { a: 6, b: 4, from: 0.59, to: 0.64, cover: "turn" },
  { a: 4, b: 5, from: 0.71, to: 0.76, cover: "approach" },
];

export interface Segment {
  id: string;
  from: number;
  to: number;
  /** Index into PLAYERS whose caption shows during this segment. */
  player?: number;
}

export const SEGMENTS: readonly Segment[] = [
  { id: "lights", from: 0.0, to: 0.07 },
  { id: "ball-in", from: 0.07, to: 0.12 },
  { id: "player-1", from: 0.12, to: 0.22, player: 0 },
  { id: "morph-1", from: 0.22, to: 0.27 },
  { id: "player-2", from: 0.27, to: 0.35, player: 1 },
  { id: "morph-2", from: 0.35, to: 0.4 },
  { id: "player-3", from: 0.4, to: 0.47, player: 2 },
  { id: "morph-3", from: 0.47, to: 0.52 },
  { id: "player-4", from: 0.52, to: 0.545, player: 3 },
  { id: "morph-4a", from: 0.545, to: 0.552 },
  { id: "player-8", from: 0.552, to: 0.58, player: 7 },
  { id: "morph-4b", from: 0.58, to: 0.586 },
  { id: "player-7", from: 0.586, to: 0.626, player: 6 },
  { id: "morph-4c", from: 0.626, to: 0.64 },
  { id: "player-5", from: 0.64, to: 0.71, player: 4 },
  { id: "morph-5", from: 0.71, to: 0.76 },
  // The caption clears before the landing so the SIIIUUU word has the frame.
  { id: "player-6", from: 0.76, to: 0.91, player: 5 },
  { id: "ending", from: 0.91, to: 1 },
];

/**
 * Segments that use captured running (realistic mode only). Each fades in and
 * out with p; `anchor` is where the captured stride is phase-aligned with the
 * hand-built one, so the legs agree as it fades in. Touches, the pass, the
 * shot and the celebration stay hand-built: these clips contain no ball work.
 */
export const RUNS = [
  // Player 1 running in out of the dark, onto the ball.
  { clip: "runIn", fadeIn: [-1, 0], fadeOut: [0.112, 0.128], anchor: 0 },
  // Player 3: the burst and the sprint.
  { clip: "sprint", fadeIn: [0.352, 0.398], fadeOut: [0.47, 0.488], anchor: 0.375 },
  // Player 4: the driving run, until he slows for the turn.
  { clip: "drive", fadeIn: [0.49, 0.512], fadeOut: [0.586, 0.604], anchor: 0.501 },
  // Players 5 and 6: running onto the pass, up to the strike.
  { clip: "approach", fadeIn: [0.706, 0.728], fadeOut: [0.772, 0.786], anchor: 0.709 },
] as const;

/**
 * The captured strike (realistic mode only): player 6's shot. The pose is
 * driven by the clip around `impact`, which is where the ball leaves the
 * ground; it fades in as the captured approach run fades out and fades out
 * into the hand-built stop and celebration. `seconds` is the clip time that
 * one unit of progress covers.
 */
export const SHOT = {
  impact: 0.804,
  fadeIn: [0.772, 0.786],
  fadeOut: [0.842, 0.866],
  seconds: 14,
  /**
   * How the ball leaves the boot (all modes, so the goal arrival is shared):
   * `bootSpeed` is the struck point's speed at contact in the captured clip
   * (m/s, measured on the retargeted boot); the ball leaves at `ratio` times
   * that, in the direction of the strike, and is pushed up to its cruising
   * speed over `ramp` seconds (the time the ball is in contact with the boot),
   * and slowed over the last `brake` seconds as the net takes it.
   */
  launch: { bootSpeed: 14, ratio: 1.25, ramp: 0.025, brake: 0.03 },
} as const;

/** The finish: strike, ball in the net, celebration. */
export const FINISH = {
  strike: { from: 0.773, to: 0.835 },
  /** The ball crosses the line and hits the net. */
  netHit: 0.84,
  jump: { from: 0.88, to: 0.908 },
  celebrate: { from: 0.868, to: 0.93 },
  /** The wordmark: the last thing on the closing card, after the message. */
  brand: { from: 0.986, to: 1 },
} as const;

/**
 * The ending, after Ronaldo lands (FINISH.jump.to = 0.908): the SIIIUUU
 * typography slams in with a short shake, holds and clears, the picture fades
 * to black, then the two lines of the closing message appear. Every value is a
 * progress window; nothing is timed in seconds.
 */
export const ENDING = {
  /** The word punches in over `in`, is gone by `out`. */
  shout: { in: [0.906, 0.917], out: [0.946, 0.96] },
  /** The shake: a burst that decays to nothing over this window (also a tiny camera impulse). */
  shake: { from: 0.906, to: 0.926 },
  /** The scene goes to black. */
  black: { from: 0.944, to: 0.968 },
  /** The message. */
  line1: { from: 0.966, to: 0.98 },
  line2: { from: 0.978, to: 0.99 },
} as const;

/**
 * Realistic mode holds its last frame, the closing card, for this much extra
 * scroll (in viewport heights) before the page below scrolls into view, so the
 * message can be read. Progress stays at 1 throughout.
 */
export const END_HOLD_VH = 80;

/**
 * One short swing of the camera round the figure per player, to give their
 * shirt number a readable moment (the rest of each segment is filmed from the
 * side). `turn` is the extra camera azimuth in radians at the middle of the
 * window (sin-squared in and out, so it starts and ends at rest); the sign
 * picks front or back. The camera also moves in by `zoom` (default BEAT_ZOOM) at the middle.
 * Scene scale p, like everything here.
 */
export const BEAT_ZOOM = 0.3;
export const NUMBER_BEATS: { player: number; from: number; to: number; turn: number; zoom?: number }[] = [
  { player: 0, from: 0.172, to: 0.206, turn: -1.4 },
  { player: 1, from: 0.285, to: 0.315, turn: 1.0 },
  { player: 2, from: 0.405, to: 0.435, turn: -1.4 },
  // Haaland's front number was small: his beat moves in further.
  { player: 3, from: 0.522, to: 0.545, turn: 1.0, zoom: 0.45 },
  { player: 7, from: 0.555, to: 0.578, turn: -1.4 },
  { player: 6, from: 0.588, to: 0.612, turn: 1.0 },
  { player: 4, from: 0.66, to: 0.69, turn: 0.9 },
];

/** Signature moves inside the player segments. */
export const MOVES = {
  feint: { from: 0.162, to: 0.206 },
  push: { from: 0.196, to: 0.222 },
  stepovers: { from: 0.276, to: 0.31 },
  flick: { from: 0.312, to: 0.348 },
  /** Big touches ahead during player 3's sprint; the first is inside the burst. */
  pushes: [
    { from: 0.382, to: 0.396 },
    { from: 0.432, to: 0.446 },
    // Player 4: two heavy touches on the driving run.
    { from: 0.543, to: 0.556 },
    { from: 0.577, to: 0.59 },
  ],
} as const;

/**
 * Player 5's pass into space (realistic mode only, p > 0.47): a keyed pose
 * sequence (see PASS in character/pose.ts) with the contact exactly halfway
 * through `from`..`to`. The ball is at rest until `contact` and leaves at that
 * progress; the captured approach run takes over as the pass recovers.
 */
export const PASS = { from: 0.673, to: 0.717, contact: 0.695 } as const;

/** Player 5's soft control touch on the way in: the right foot meets the ball at `contact`. */
export const TOUCH = { from: 0.642, to: 0.664, contact: 0.652 } as const;
