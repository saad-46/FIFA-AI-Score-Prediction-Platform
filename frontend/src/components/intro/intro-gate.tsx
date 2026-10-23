"use client";

import { Component, useCallback, useEffect, type ReactNode } from "react";
import dynamic from "next/dynamic";
import { IntroPoster } from "./intro-poster";
import { SKIP_ATTR, SKIP_BOOT_SCRIPT, realisticRequested, setSkipped, useIntroMode } from "./intro-state";
import { BUILT_UNTIL, BUILT_UNTIL_REALISTIC, END_HOLD_VH, FULL_SCROLL_VH } from "./timeline";

// three.js and the scene are a separate chunk, fetched only when the intro
// is actually going to play.
const IntroExperience = dynamic(() => import("./intro-experience"), {
  ssr: false,
  loading: () => <IntroPoster loading />,
});

/** If the 3D scene throws, the still takes its place; the page carries on. */
class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? <IntroPoster /> : this.props.children;
  }
}

const jumpToTop = () => window.scrollTo({ top: 0, behavior: "instant" });

/**
 * Decides what the top of the landing page shows:
 *  - the scroll-driven 3D intro,
 *  - a still, when motion is reduced or WebGL is unavailable,
 *  - nothing but a "Replay intro" link, once the visitor has skipped it.
 */
export function IntroGate() {
  const mode = useIntroMode();
  const playing = mode === "play";
  const skipped = mode === "skipped";

  // Keeps the <html> flag in step when this page is reached by client-side
  // navigation, where the boot script below has not run.
  useEffect(() => {
    if (mode !== "ssr") document.documentElement.toggleAttribute(SKIP_ATTR, skipped);
  }, [mode, skipped]);

  const skip = useCallback(() => {
    setSkipped(true);
    jumpToTop();
    requestAnimationFrame(() => document.getElementById("intro-replay")?.focus());
  }, []);

  const replay = useCallback(() => {
    setSkipped(false);
    jumpToTop();
  }, []);

  return (
    <>
      {mode === "ssr" && <script dangerouslySetInnerHTML={{ __html: SKIP_BOOT_SCRIPT }} />}

      <section
        data-intro-section
        aria-label="Introduction"
        className={`dark relative bg-[#04060b] [html[data-intro-skipped]_&]:hidden ${skipped ? "hidden" : ""}`}
        // One viewport for the pinned frame, plus the scroll that drives it.
        style={playing ? { height: `${100 + FULL_SCROLL_VH * (realisticRequested() ? BUILT_UNTIL_REALISTIC : BUILT_UNTIL) + (realisticRequested() ? END_HOLD_VH : 0)}svh` } : undefined}
      >
        <div className="sticky top-0 h-svh overflow-hidden">
          {playing ? (
            <SceneBoundary>
              <IntroExperience onSkip={skip} />
            </SceneBoundary>
          ) : (
            <IntroPoster />
          )}
        </div>
      </section>

      <div
        className={`mx-auto w-full max-w-7xl justify-end px-4 pt-2 sm:px-6 lg:px-8 [html[data-intro-skipped]_&]:flex ${skipped ? "flex" : "hidden"}`}
      >
        <button
          id="intro-replay"
          type="button"
          onClick={replay}
          className="inline-flex min-h-11 items-center rounded px-2 text-xs font-medium text-fg-muted underline-offset-4 hover:text-foreground hover:underline"
        >
          Replay the 3D intro
        </button>
      </div>
    </>
  );
}
