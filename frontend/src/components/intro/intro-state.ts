import { useSyncExternalStore } from "react";
import { hasWebGL } from "./quality";

/**
 * Whether the intro should play.
 *
 * Only an explicit "Skip intro" is remembered; finishing the intro is not, so
 * it is there again on the next visit and "Replay intro" always brings it
 * back. Storage is optional: if it is blocked the choice simply lasts for the
 * page view.
 */

export const SKIP_KEY = "fifa-ai:intro-skipped";
/** Set on <html> while the intro is skipped; CSS hides the intro from it. */
export const SKIP_ATTR = "data-intro-skipped";

/** The realistic footballers are opt-in while they are being built. */
export function realisticRequested(): boolean {
  return typeof window !== "undefined" && new URLSearchParams(window.location.search).get("introCharacter") === "realistic";
}

export type IntroMode = "ssr" | "play" | "skipped" | "reduced" | "unsupported";

let skippedInMemory: boolean | null = null;
let webgl: boolean | null = null;
const listeners = new Set<() => void>();

function readSkipped(): boolean {
  if (skippedInMemory !== null) return skippedInMemory;
  try {
    skippedInMemory = window.localStorage.getItem(SKIP_KEY) === "1";
  } catch {
    skippedInMemory = false;
  }
  return skippedInMemory;
}

export function setSkipped(skipped: boolean) {
  skippedInMemory = skipped;
  try {
    if (skipped) window.localStorage.setItem(SKIP_KEY, "1");
    else window.localStorage.removeItem(SKIP_KEY);
  } catch {
    // Storage blocked: the in-memory value still applies to this page view.
  }
  document.documentElement.toggleAttribute(SKIP_ATTR, skipped);
  listeners.forEach((l) => l());
}

const REDUCED = "(prefers-reduced-motion: reduce)";

function subscribe(listener: () => void) {
  listeners.add(listener);
  const mq = window.matchMedia(REDUCED);
  mq.addEventListener("change", listener);
  return () => {
    listeners.delete(listener);
    mq.removeEventListener("change", listener);
  };
}

function snapshot(): IntroMode {
  if (readSkipped()) return "skipped";
  if (window.matchMedia(REDUCED).matches) return "reduced";
  if (webgl === null) webgl = hasWebGL();
  return webgl ? "play" : "unsupported";
}

/** "ssr" on the server and during hydration, then the real answer. */
export function useIntroMode(): IntroMode {
  return useSyncExternalStore(subscribe, snapshot, () => "ssr" as const);
}

/**
 * Runs before first paint on a hard load, so a returning visitor who skipped
 * never sees the intro flash in. Kept tiny and free of any quote that would
 * need escaping.
 */
export const SKIP_BOOT_SCRIPT = `try{if(localStorage.getItem("${SKIP_KEY}")==="1")document.documentElement.setAttribute("${SKIP_ATTR}","")}catch(e){}`;
