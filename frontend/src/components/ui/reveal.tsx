"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Lets a block ease in (a short rise and fade) the first time it scrolls into view.
 *
 * The block is fully visible in the server HTML and for anyone who is already looking at it, so no content waits
 * on an animation: only a block that starts below the fold is held back, and only until it is about to be seen.
 * Reduced motion disables the effect altogether. `delay` (ms) staggers neighbours.
 */
export function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"shown" | "held" | "entering">("shown");

  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (el.getBoundingClientRect().top < window.innerHeight * 0.92) return;
    // Held until the block is about to be seen. The state change is the point of this effect.
    setState("held");
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setState("entering");
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      style={state === "entering" ? { transitionDelay: `${delay}ms` } : undefined}
      className={cn(
        "transition duration-700 ease-out motion-reduce:transition-none",
        state === "held" ? "translate-y-5 opacity-0" : "translate-y-0 opacity-100",
        className
      )}
    >
      {children}
    </div>
  );
}
