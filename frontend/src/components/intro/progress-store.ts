import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

/**
 * Scroll progress, kept out of React.
 *
 * The scroll position is written here many times a second and read by the
 * render loop; putting it in component state would re-render the tree on every
 * scroll event.
 */
export interface ProgressStore {
  get(): number;
  /** Written by the scroll binding. */
  set(p: number): void;
  /** Pins progress to a value regardless of scroll (debug hook); null releases it. */
  override(p: number | null): void;
  subscribe(listener: () => void): () => void;
}

export function createProgressStore(): ProgressStore {
  let scrolled = 0;
  let forced: number | null = null;
  const listeners = new Set<() => void>();
  const emit = () => listeners.forEach((l) => l());
  return {
    get: () => forced ?? scrolled,
    set(p) {
      if (p === scrolled) return;
      scrolled = p;
      if (forced === null) emit();
    },
    override(p) {
      forced = p;
      emit();
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

/**
 * Ties the store to how far `section` has been scrolled through.
 *
 * Scrolling stays native: the section is simply tall and its content is
 * `position: sticky`, so nothing intercepts the wheel, touch or keyboard.
 * ScrollTrigger only measures the position; `scrub` eases the reported value
 * toward it so a notchy mouse wheel does not make the scene stutter. The value
 * it settles on depends on the scroll position alone. `holdVh` is extra
 * scroll at the end of the section during which progress stays at its maximum.
 */
export function bindScroll(section: HTMLElement, store: ProgressStore, maxProgress: number, holdVh = 0): () => void {
  gsap.registerPlugin(ScrollTrigger);
  const proxy = { v: 0 };
  const tween = gsap.to(proxy, {
    v: 1,
    ease: "none",
    onUpdate: () => store.set(proxy.v * maxProgress),
    scrollTrigger: {
      trigger: section,
      start: "top top",
      // With a hold, progress reaches its end `holdVh` of scrolling before the
      // section's bottom edge, and stays there while the last frame stays pinned.
      end: holdVh > 0 ? () => `+=${Math.max(1, section.offsetHeight - window.innerHeight - (holdVh / 100) * window.innerHeight)}` : "bottom bottom",
      invalidateOnRefresh: holdVh > 0,
      scrub: 0.6,
    },
  });
  return () => {
    tween.scrollTrigger?.kill();
    tween.kill();
  };
}
