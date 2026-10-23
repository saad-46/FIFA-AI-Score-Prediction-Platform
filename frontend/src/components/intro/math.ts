/** Small numeric helpers shared by the intro. All of them are pure. */

export const TAU = Math.PI * 2;

export const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/** 0 before `a`, 1 after `b`, linear between. */
export const range = (p: number, a: number, b: number) => clamp01((p - a) / (b - a));

export const smooth = (t: number) => {
  const x = clamp01(t);
  return x * x * (3 - 2 * x);
};

export const smoother = (t: number) => {
  const x = clamp01(t);
  return x * x * x * (x * (x * 6 - 15) + 10);
};

export const smoothstep = (a: number, b: number, p: number) => smooth(range(p, a, b));

/** Rises from 0 at `a` to 1 at the midpoint and back to 0 at `b`. */
export const bell = (p: number, a: number, b: number) => {
  const t = range(p, a, b);
  return Math.sin(Math.PI * t) ** 2;
};

export type Key = readonly [p: number, value: number];

/**
 * Monotone cubic interpolation through keyframes (Fritsch-Carlson).
 *
 * Unlike a smoothstep between each pair of keys, the value does not stop at
 * every key, and unlike a Catmull-Rom spline it never overshoots: a path keyed
 * to always move forward always moves forward. Clamped outside the key range.
 */
export function curve(keys: readonly Key[]): (p: number) => number {
  const n = keys.length;
  const xs = keys.map((k) => k[0]);
  const ys = keys.map((k) => k[1]);
  const d: number[] = [];
  for (let i = 0; i < n - 1; i++) d.push((ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]));
  const m: number[] = new Array(n).fill(0);
  m[0] = d[0];
  m[n - 1] = d[n - 2];
  for (let i = 1; i < n - 1; i++) m[i] = d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2;
  for (let i = 0; i < n - 1; i++) {
    if (d[i] === 0) {
      m[i] = 0;
      m[i + 1] = 0;
      continue;
    }
    const a = m[i] / d[i];
    const b = m[i + 1] / d[i];
    const s = a * a + b * b;
    if (s > 9) {
      const t = 3 / Math.sqrt(s);
      m[i] = t * a * d[i];
      m[i + 1] = t * b * d[i];
    }
  }
  return (p: number) => {
    if (p <= xs[0]) return ys[0];
    if (p >= xs[n - 1]) return ys[n - 1];
    let i = 0;
    while (p > xs[i + 1]) i++;
    const h = xs[i + 1] - xs[i];
    const t = (p - xs[i]) / h;
    const t2 = t * t;
    const t3 = t2 * t;
    return (
      (2 * t3 - 3 * t2 + 1) * ys[i] +
      (t3 - 2 * t2 + t) * h * m[i] +
      (-2 * t3 + 3 * t2) * ys[i + 1] +
      (t3 - t2) * h * m[i + 1]
    );
  };
}

/**
 * Continues a curve past `from` with more keys. Everything up to `from` is
 * left exactly as it was, and the speed carries on smoothly across the join.
 */
export function extend(base: (p: number) => number, from: number, keys: readonly Key[]): (p: number) => number {
  const v = base(from);
  const slope = (v - base(from - 1e-4)) / 1e-4;
  const h = 0.004;
  const next = curve([[from, v], [from + h, v + slope * h], ...keys]);
  return (p: number) => (p <= from ? base(p) : next(p));
}

/** Deterministic pseudo-random numbers, so every load builds the same scene. */
export function seeded(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
