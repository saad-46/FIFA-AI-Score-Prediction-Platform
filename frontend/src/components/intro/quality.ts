/** Rendering budgets. Picked once when the intro mounts. */
export interface QualityTier {
  name: "high" | "medium" | "low";
  /** Upper bound on device pixel ratio. */
  dpr: number;
  /** Shadow map size; 0 turns shadows off. */
  shadowMap: number;
  antialias: boolean;
  dust: number;
  /** Brief soft-focus at a morph seam (a CSS filter on the canvas). */
  seamBlur: boolean;
}

const TIERS: Record<QualityTier["name"], QualityTier> = {
  high: { name: "high", dpr: 1.5, shadowMap: 2048, antialias: true, dust: 90, seamBlur: true },
  medium: { name: "medium", dpr: 1.25, shadowMap: 1024, antialias: true, dust: 60, seamBlur: true },
  low: { name: "low", dpr: 1, shadowMap: 0, antialias: false, dust: 30, seamBlur: false },
};

/** Chooses a tier from what the browser reports about the device. */
export function detectTier(): QualityTier {
  const nav = navigator as Navigator & { deviceMemory?: number };
  const cores = nav.hardwareConcurrency ?? 4;
  const memory = nav.deviceMemory ?? 8;
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const small = Math.min(window.innerWidth, window.innerHeight) < 600;
  if (coarse || small || cores <= 4 || memory <= 4) return TIERS.low;
  if (cores >= 8 && memory >= 8) return TIERS.high;
  return TIERS.medium;
}

export function hasWebGL(): boolean {
  try {
    const gl = document.createElement("canvas").getContext("webgl2");
    if (!gl) return false;
    // Only a probe: hand the context straight back so it does not count
    // against the browser's limit on live WebGL contexts.
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return true;
  } catch {
    return false;
  }
}
