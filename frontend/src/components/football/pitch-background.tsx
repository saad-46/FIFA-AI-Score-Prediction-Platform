"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

// The 3D pitch is a separate chunk, fetched only on the client and only when the card mounts.
const Pitch3D = dynamic(() => import("./pitch-3d"), { ssr: false });

/**
 * Backdrop of the featured final: a perspective-rendered 3D football pitch (see pitch-3d.tsx) over a CSS/SVG
 * pitch that is always there underneath.
 *
 * The CSS/SVG pitch is what the server renders and what stays if WebGL is missing, fails or the visitor has
 * asked to save data; once the 3D scene has drawn its first frame the 2D one fades out. A light vignette on top
 * (floodlight at the corners, a darker foot) keeps white text readable over either. It fills its positioned
 * parent and ignores pointer events; the content goes on top.
 */
export function FootballPitchBackground({ className }: { className?: string }) {
  // The 3D scene exists only while the card is near the viewport, so a card far below the landing intro never holds
  // a second WebGL context while the intro is playing; it reports back if it cannot run.
  const rootRef = useRef<HTMLDivElement>(null);
  const [near, setNear] = useState(false);
  const [use3d, setUse3d] = useState(true);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    // Watched both ways: when the card is scrolled far away (for example the scroll-driven intro replays from the
    // top) the 3D scene is torn down and its WebGL context released, and the 2D pitch stands in until it returns.
    const io = new IntersectionObserver(
      ([entry]) => {
        setNear(entry.isIntersecting);
        if (!entry.isIntersecting) setReady(false);
      },
      { rootMargin: "300px 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const onReady = useCallback(() => setReady(true), []);
  const onFail = useCallback(() => {
    setReady(false);
    setUse3d(false);
  }, []);

  return (
    <div ref={rootRef} aria-hidden="true" className={cn("pointer-events-none absolute inset-0 overflow-hidden bg-[#2e8140]", className)}>
      <div className={cn("absolute inset-0 transition-opacity duration-700", ready && "opacity-0")}>
        <FlatPitch />
      </div>
      {near && use3d && <Pitch3D onReady={onReady} onFail={onFail} />}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(55% 65% at 5% 0%, rgba(255,246,220,0.2), transparent 70%), radial-gradient(55% 65% at 95% 0%, rgba(255,246,220,0.17), transparent 70%), radial-gradient(ellipse at 50% 45%, transparent 52%, rgba(0,0,0,0.42) 100%), linear-gradient(180deg, rgba(0,0,0,0.0) 0%, rgba(0,0,0,0.24) 100%)",
        }}
      />
    </div>
  );
}

/** The 2D pitch: CSS grass and one SVG of non-scaling-stroke markings. */
function FlatPitch() {
  const line = { stroke: "rgba(255,255,255,0.5)", strokeWidth: 1.5, vectorEffect: "non-scaling-stroke" as const };
  const dot = "rgba(255,255,255,0.55)";
  return (
    <>
      <div
        className="absolute inset-0"
        style={{ backgroundImage: "repeating-linear-gradient(90deg, rgba(255,255,255,0.09) 0 7%, rgba(0,0,0,0.08) 7% 14%)" }}
      />
      <div
        className="absolute inset-0 opacity-70"
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg, rgba(255,255,255,0.035) 0 1px, transparent 1px 3px), repeating-linear-gradient(0deg, rgba(0,0,0,0.04) 0 1px, transparent 1px 5px)",
        }}
      />
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(60% 70% at 8% 0%, rgba(255,255,255,0.2), transparent 70%), radial-gradient(60% 70% at 92% 0%, rgba(255,255,255,0.18), transparent 70%), radial-gradient(90% 60% at 50% 105%, rgba(0,0,0,0.3), transparent 70%)",
        }}
      />
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 800 300" preserveAspectRatio="xMidYMid slice" fill="none">
        <defs>
          <filter id="pitch-grain" x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves="2" seed="7" />
            <feColorMatrix type="saturate" values="0" />
          </filter>
        </defs>
        <rect width="800" height="300" filter="url(#pitch-grain)" opacity="0.1" />
        <path d="M400 0V300" {...line} />
        <ellipse cx="400" cy="150" rx="92" ry="80" {...line} />
        <circle cx="400" cy="150" r="2.5" fill={dot} />
        <path d="M0 34L150 66V234L0 266" {...line} />
        <path d="M0 98L54 110V190L0 202" {...line} />
        <path d="M150 116A58 44 0 0 1 150 184" {...line} />
        <circle cx="106" cy="150" r="2" fill={dot} />
        <path d="M800 34L650 66V234L800 266" {...line} />
        <path d="M800 98L746 110V190L800 202" {...line} />
        <path d="M650 116A58 44 0 0 0 650 184" {...line} />
        <circle cx="694" cy="150" r="2" fill={dot} />
      </svg>
    </>
  );
}
