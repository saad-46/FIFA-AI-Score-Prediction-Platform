"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { TextureLoader, type Mesh, type Object3D, type PerspectiveCamera, type Texture, type WebGLRenderer } from "three";
import { GLTFLoader, type GLTF } from "three/addons/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { RUN_CYCLES_URL, SHOT_CLIP_URL, parseRunClips, parseShotClip, type RunClips, type ShotClip } from "./character/mocap";
import { PLAYER_SKIN_URLS, REALISTIC_PLAYERS_URL, checkPlayersModel } from "./character/realistic-rig";

type RealisticPlayers = { gltf: GLTF; skins: Texture[]; runClips: RunClips | null; shotClip: ShotClip | null };

/**
 * The realistic model, loaded once per page and shared by every mount, so
 * navigating away and back does not download and parse it again. A failed
 * or invalid load is not cached: the next mount tries again.
 */
let playersRequest: Promise<RealisticPlayers> | null = null;
function loadRealisticPlayers(): Promise<RealisticPlayers> {
  // The file is Meshopt-compressed (morph targets included); the decoder ships with three.
  playersRequest ??= new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).loadAsync(REALISTIC_PLAYERS_URL).then(async (gltf) => {
    // One extra skin per morph target; fetch only the ones this file uses.
    let targets = 0;
    gltf.scene.traverse((o) => {
      targets = Math.max(targets, (o as Mesh).morphTargetInfluences?.length ?? 0);
    });
    const skins = await Promise.all(PLAYER_SKIN_URLS.slice(0, targets).map((url) => new TextureLoader().loadAsync(url)));
    const problem = checkPlayersModel(gltf, skins);
    if (problem) throw new Error(`intro: the realistic player model is unusable (${problem})`);
    // The motion-capture runs and shot are optional: without them (or with
    // ?introMotion=handbuilt for comparison; ?introMotion=handshot keeps the
    // runs and hand-builds only the shot) the hand-built motion is used.
    let runClips: RunClips | null = null;
    let shotClip: ShotClip | null = null;
    const mode = new URLSearchParams(window.location.search).get("introMotion");
    if (mode !== "handbuilt") {
      const load = <T,>(url: string, parse: (json: unknown) => T | null) =>
        fetch(url)
          .then((r) => (r.ok ? r.json() : null))
          .then(parse)
          .catch(() => null);
      [runClips, shotClip] = await Promise.all([load(RUN_CYCLES_URL, parseRunClips), mode === "handshot" ? null : load(SHOT_CLIP_URL, parseShotClip)]);
      if (!runClips) console.warn("intro: the motion-capture runs are unavailable; using the hand-built runs");
      if (!shotClip && mode !== "handshot") console.warn("intro: the motion-capture shot is unavailable; using the hand-built shot");
    }
    return { gltf, skins, runClips, shotClip };
  });
  playersRequest.catch(() => {
    playersRequest = null;
  });
  return playersRequest;
}
import { IntroPoster } from "./intro-poster";
import {
  bindScroll,
  createProgressStore,
  type ProgressStore,
} from "./progress-store";
import { PLAYERS } from "./profiles";
import { detectTier, type QualityTier } from "./quality";
import type { SceneState } from "./sample-scene";
import { BUILT_UNTIL, BUILT_UNTIL_REALISTIC, END_HOLD_VH } from "./timeline";
import { realisticRequested } from "./intro-state";
import { IntroWorld } from "./world";

interface DebugHook {
  setProgress(p: number | null): void;
  getProgress(): number;
  snapshot(): unknown;
  info(): unknown;
  /** Milliseconds per scene update at progress p, averaged over n runs (CPU cost, no rendering). */
  benchmark(p: number, n: number): number;
  /** Pins the camera (position, look-at) over the timeline's, for close inspection; null releases it. */
  setCamera(o: { position: [number, number, number]; target: [number, number, number] } | null): void;
  /** Prototypes, so a test can count live instances (memory checks). */
  prototypes: Record<string, object>;
}

/** The lookup texture three.js gives every physically based material, found through one that has been drawn. */
function sharedLookupTexture(gl: WebGLRenderer, root: Object3D): Texture | null {
  let lut: Texture | null = null;
  root.traverse((o) => {
    const material = (o as Mesh).material;
    if (lut || !material || Array.isArray(material)) return;
    const uniforms = (gl.properties.get(material) as { uniforms?: { dfgLUT?: { value?: Texture } } }).uniforms;
    lut = uniforms?.dfgLUT?.value ?? null;
  });
  return lut;
}

function Scene({
  store,
  tier,
  player,
  onFrame,
}: {
  store: ProgressStore;
  tier: QualityTier;
  player: RealisticPlayers | null;
  onFrame: (s: SceneState, progress: number) => void;
}) {
  const world = useMemo(
    () => new IntroWorld(tier, player ?? undefined),
    [tier, player],
  );
  const invalidate = useThree((s) => s.invalidate);
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const warmed = useRef<IntroWorld | null>(null);
  const cameraOverride = useRef<{ position: [number, number, number]; target: [number, number, number] } | null>(null);

  useEffect(() => {
    // Render on demand: a frame is drawn when progress changes and at no other
    // time, so an idle intro costs nothing.
    const unsubscribe = store.subscribe(() => invalidate());
    invalidate();

    let removeDebug = () => {};
    if (
      process.env.NODE_ENV !== "production" &&
      new URLSearchParams(window.location.search).has("introDebug")
    ) {
      const hook: DebugHook = {
        setProgress: (p) => store.override(p),
        getProgress: () => store.get(),
        snapshot: () => world.snapshot(),
        setCamera: (o) => {
          cameraOverride.current = o;
          invalidate();
        },
        prototypes: { world: Object.getPrototypeOf(world), renderer: Object.getPrototypeOf(gl) },
        benchmark: (p, n) => {
          const t0 = performance.now();
          for (let i = 0; i < n; i++) world.update(p, camera as PerspectiveCamera, 1.6, 900);
          const ms = (performance.now() - t0) / n;
          invalidate();
          return ms;
        },
        info: () => ({
          tier: tier.name,
          ...gl.info.render,
          geometries: gl.info.memory.geometries,
          textures: gl.info.memory.textures,
        }),
      };
      const w = window as unknown as { __intro?: DebugHook };
      w.__intro = hook;
      removeDebug = () => {
        if (w.__intro === hook) delete w.__intro;
      };
    }

    return () => {
      unsubscribe();
      removeDebug();
      const lut = sharedLookupTexture(gl, world.root);
      world.dispose();
      // three.js (r182) shares one lookup texture between every renderer on
      // the page, and each renderer that uses it hangs a dispose listener on
      // it, so an unmounted renderer was never freed. Disposing the texture
      // detaches those listeners; the next renderer simply uploads it again.
      lut?.dispose();
    };
  }, [store, world, invalidate, gl, tier, camera]);

  useFrame((state) => {
    const p = store.get();
    const s = world.update(
      p,
      state.camera as PerspectiveCamera,
      state.size.width / state.size.height,
      state.size.height * state.viewport.dpr,
    );
    const pinned = cameraOverride.current;
    if (pinned) {
      state.camera.position.set(...pinned.position);
      state.camera.lookAt(...pinned.target);
    }
    if (warmed.current !== world) {
      warmed.current = world;
      world.prewarm(state.gl, state.scene, state.camera);
    }
    onFrame(s, p);
  });

  return (
    <>
      <color attach="background" args={[world.background]} />
      <primitive object={world.fog} attach="fog" />
      <primitive object={world.root} />
    </>
  );
}

/**
 * The 3D intro: a canvas pinned to the viewport and posed from scroll.
 * Loaded on the client only, and only on the landing page.
 */
export default function IntroExperience({ onSkip }: { onSkip: () => void }) {
  const [store] = useState(createProgressStore);
  const [tier] = useState(detectTier);
  const [ready, setReady] = useState(false);
  // The realistic footballer is the default (?introCharacter=procedural opts out). If the model fails to load, the
  // procedural figure takes over rather than leaving the scene empty.
  const [wantsRealistic] = useState(realisticRequested);
  const builtUntil = wantsRealistic ? BUILT_UNTIL_REALISTIC : BUILT_UNTIL;
  const [player, setPlayer] = useState<RealisticPlayers | null | "loading">(
    wantsRealistic ? "loading" : null,
  );

  useEffect(() => {
    if (!wantsRealistic) return;
    let cancelled = false;
    loadRealisticPlayers().then(
      (players) => !cancelled && setPlayer(players),
      (error: unknown) => {
        // Fall back to the procedural figure; say why, once, for whoever is debugging.
        console.warn(error instanceof Error ? error.message : error);
        if (!cancelled) setPlayer(null);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [wantsRealistic]);

  const rootRef = useRef<HTMLDivElement>(null);
  const canvasWrapRef = useRef<HTMLDivElement>(null);
  const captionRef = useRef<HTMLDivElement>(null);
  const nameRef = useRef<HTMLParagraphElement>(null);
  const taglineRef = useRef<HTMLParagraphElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const hintRef = useRef<HTMLParagraphElement>(null);
  const brandRef = useRef<HTMLDivElement>(null);
  const blackRef = useRef<HTMLDivElement>(null);
  const shoutRef = useRef<HTMLDivElement>(null);
  const shoutImgRef = useRef<HTMLImageElement>(null);
  const line1Ref = useRef<HTMLParagraphElement>(null);
  const line2Ref = useRef<HTMLParagraphElement>(null);
  const shown = useRef({ player: -2, ready: false });

  // The SIIIUUU bitmap: the two halves, drawn once per size (and again when the display face has loaded).
  useEffect(() => {
    const img = shoutImgRef.current;
    const wrap = shoutRef.current;
    if (!img || !wrap) return;
    // An image, not a second <canvas>: the scene's WebGL canvas stays the only one in the intro.
    const canvas = document.createElement("canvas");
    let url = "";
    const draw = () => {
      const w = window.innerWidth;
      const fs = Math.min(272, Math.max(68, 0.17 * w));
      const h = Math.round(fs * 1.5);
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      img.style.height = `${h}px`;
      wrap.style.bottom = `calc(15svh - ${(0.3 * fs).toFixed(1)}px)`;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const probe = document.createElement("span");
      probe.className = "font-display";
      wrap.appendChild(probe);
      const family = getComputedStyle(probe).fontFamily;
      probe.remove();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.font = `700 ${fs}px ${family}`;
      ctx.letterSpacing = `${(-0.025 * fs).toFixed(2)}px`;
      ctx.textBaseline = "alphabetic";
      const ink = getComputedStyle(wrap).color;
      const base = h - 0.35 * fs;
      const pad = 0.03 * w;
      for (const [text, x, align] of [["SIII", pad, "left"], ["UUU!", w - pad, "right"]] as const) {
        ctx.save();
        ctx.translate(x, base);
        // skewX(-6deg), about the baseline
        ctx.transform(1, 0, Math.tan((-6 * Math.PI) / 180), 1, 0, 0);
        ctx.textAlign = align;
        // the cyan offset, then the glow and the dark lift under it, then the face
        ctx.fillStyle = "#22c8e6";
        ctx.fillText(text, 0.045 * fs, 0.045 * fs);
        ctx.shadowColor = "rgba(34,200,230,0.4)";
        ctx.shadowBlur = 0.45 * fs;
        ctx.fillStyle = ink;
        ctx.fillText(text, 0, 0);
        ctx.shadowColor = "rgba(4,6,11,0.8)";
        ctx.shadowBlur = 0.2 * fs;
        ctx.shadowOffsetY = 0.03 * fs;
        ctx.fillText(text, 0, 0);
        ctx.restore();
      }
      canvas.toBlob((blob) => {
        if (!blob) return;
        const next = URL.createObjectURL(blob);
        img.src = next;
        if (url) URL.revokeObjectURL(url);
        url = next;
      });
    };
    draw();
    // The display face is fetched lazily: ask for it, and draw again once it is in.
    const fs0 = Math.min(272, Math.max(68, 0.17 * window.innerWidth));
    const probe = document.createElement("span");
    probe.className = "font-display";
    wrap.appendChild(probe);
    const family0 = getComputedStyle(probe).fontFamily;
    probe.remove();
    void document.fonts?.load(`700 ${fs0}px ${family0}`, "SIIIUUU!").then(draw, () => {});
    window.addEventListener("resize", draw);
    return () => {
      window.removeEventListener("resize", draw);
      if (url) URL.revokeObjectURL(url);
    };
  }, []);

  useEffect(() => {
    const section = rootRef.current?.closest<HTMLElement>(
      "[data-intro-section]",
    );
    if (!section) return;
    return bindScroll(section, store, builtUntil, wantsRealistic ? END_HOLD_VH : 0);
  }, [store, builtUntil, wantsRealistic]);

  // Runs inside the render loop: writes straight to the DOM, never to state.
  const onFrame = useCallback(
    (s: SceneState, p: number) => {
      const caption = captionRef.current;
      if (caption) {
        caption.style.opacity = String(s.caption.alpha);
        if (
          s.caption.player !== shown.current.player &&
          s.caption.player >= 0
        ) {
          shown.current.player = s.caption.player;
          if (nameRef.current)
            nameRef.current.textContent = PLAYERS[s.caption.player].name;
          if (taglineRef.current)
            taglineRef.current.textContent = PLAYERS[s.caption.player].tagline;
        }
      }
      if (barRef.current)
        barRef.current.style.transform = `scaleX(${p / builtUntil})`;
      if (hintRef.current)
        hintRef.current.style.opacity = String(Math.max(0, 1 - p / 0.02));
      if (brandRef.current) {
        // The closing wordmark: rises into focus as the camera pulls away.
        brandRef.current.style.opacity = String(s.brand);
        brandRef.current.style.transform = `translateY(${(1 - s.brand) * 24}px) scale(${0.96 + 0.04 * s.brand})`;
        brandRef.current.style.filter = s.brand > 0 && s.brand < 1 ? `blur(${((1 - s.brand) * 6).toFixed(1)}px)` : "";
      }
      // The ending (all of it a function of progress, written straight to the DOM).
      const f = s.finale;
      if (blackRef.current) blackRef.current.style.opacity = String(f.black);
      if (shoutRef.current) {
        const el = shoutRef.current;
        el.style.opacity = String(f.shout);
        // Slams in from larger, then shakes and settles on a diagonal.
        const scale = 1 + 0.35 * (1 - f.shoutIn) ** 2;
        el.style.transform = `rotate(${(-8 + 1.6 * f.shakeRot).toFixed(2)}deg) translate(${(18 * f.shakeX).toFixed(1)}px, ${(11 * f.shakeY).toFixed(1)}px) scale(${scale.toFixed(3)})`;
      }
      for (const [ref, v] of [[line1Ref, f.line1], [line2Ref, f.line2]] as const) {
        const el = ref.current;
        if (!el) continue;
        el.style.opacity = String(v);
        el.style.transform = `translateY(${((1 - v) * 14).toFixed(1)}px)`;
        el.style.letterSpacing = `${(0.14 + (1 - v) * 0.12).toFixed(3)}em`;
      }
      if (tier.seamBlur && canvasWrapRef.current) {
        canvasWrapRef.current.style.filter =
          s.blur > 0.02 ? `blur(${(s.blur * 2.2).toFixed(2)}px)` : "";
      }
      if (!shown.current.ready) {
        shown.current.ready = true;
        setReady(true);
      }
    },
    [tier, builtUntil],
  );

  return (
    <div ref={rootRef} className="relative h-full w-full">
      <div ref={canvasWrapRef} className="absolute inset-0">
        {player !== "loading" && (
          <Canvas
            frameloop="demand"
            dpr={[1, tier.dpr]}
            shadows={tier.shadowMap > 0 ? "percentage" : false}
            gl={{
              antialias: tier.antialias,
              powerPreference: "high-performance",
            }}
            camera={{ fov: 32, near: 0.1, far: 400, position: [0, 1, 10] }}
            aria-hidden="true"
          >
            <Scene
              store={store}
              tier={tier}
              player={player}
              onFrame={onFrame}
            />
          </Canvas>
        )}
      </div>

      {/* The still covers the canvas until the first frame has been drawn. */}
      {!ready && (
        <div className="absolute inset-0">
          <IntroPoster loading />
        </div>
      )}

      <p className="sr-only">
        An animated introduction: a football rolls onto a floodlit pitch and a
        stylised player dribbles it down the field, changing from one original
        character into the next.
        {wantsRealistic
          ? " It ends on a goal celebration, the word SIIIUUU and a closing message: no live-action footage, no shortcuts, just code."
          : ""}{" "}
        It is decorative; scroll past it, or use Skip intro or Enter the site.
      </p>

      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between gap-3 p-4 sm:p-6">
        <span className="font-display text-xl font-bold uppercase leading-none tracking-wider text-foreground">
          FIFA 26 <span className="text-primary">Intelligence</span>
        </span>
        <div className="pointer-events-auto flex items-center gap-2">
          <button
            type="button"
            onClick={onSkip}
            className="inline-flex h-11 items-center rounded-lg border border-white/25 bg-black/40 px-4 text-sm font-medium text-foreground backdrop-blur transition-colors hover:bg-black/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Skip intro
          </button>
          <a
            href="#main"
            className="inline-flex h-11 items-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-ink transition-colors hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-black"
          >
            Enter the site
          </a>
        </div>
      </div>

      <div
        ref={captionRef}
        className="pointer-events-none absolute bottom-10 left-4 opacity-0 sm:bottom-14 sm:left-8"
        aria-hidden="true"
      >
        <p className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-fg-muted">
          Inspired by the playing style of
        </p>
        <p
          ref={nameRef}
          className="font-display text-6xl font-bold uppercase leading-none tracking-wide text-foreground sm:text-8xl"
        />
        <p
          ref={taglineRef}
          className="mt-1 text-sm font-medium uppercase tracking-[0.12em] text-primary"
        />
      </div>

      {/* The closing card sits on a black veil that fades up over the picture. */}
      <div ref={blackRef} className="pointer-events-none absolute inset-0 bg-[#02030a] opacity-0" aria-hidden="true" />

      {/* SIIIUUU: slams in on the landing, shakes briefly and settles on a diagonal; the figure stands between the two halves.
          Drawn once into a bitmap and then only moved: live DOM text here was rasterised slightly differently depending on
          how the page had been scrolled to the same position (the chrome compositor, reproducible on a plain page). */}
      <div
        ref={shoutRef}
        data-shout
        className="pointer-events-none absolute inset-x-0 opacity-0 text-foreground"
        aria-hidden="true"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img ref={shoutImgRef} alt="" className="block w-full" />
      </div>

      <div
        className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-6 text-center"
        aria-hidden="true"
      >
        <p
          ref={line1Ref}
          className="max-w-[26rem] text-balance font-display text-3xl font-bold uppercase leading-tight text-foreground opacity-0 sm:max-w-3xl sm:text-5xl"
        >
          No live-action footage. No shortcuts. Just code.
        </p>
        <p
          ref={line2Ref}
          className="mt-5 text-base font-medium tracking-[0.14em] text-primary opacity-0 sm:text-lg"
        >
          Crafted frame by frame with code.
        </p>
        <div ref={brandRef} className="mt-12 text-center opacity-0">
          <p className="font-display text-balance text-4xl font-bold uppercase leading-none tracking-wider text-foreground sm:text-7xl">
            FIFA 26 <span className="text-primary">Intelligence</span>
          </p>
          <p className="mt-3 max-w-[22rem] text-balance text-[0.6875rem] font-medium uppercase tracking-[0.16em] text-fg-muted sm:max-w-none sm:text-xs">
            The Game, Predicted.
          </p>
          <p className="mx-auto mt-6 max-w-md text-balance text-[0.6875rem] leading-relaxed text-fg-muted/80">
            Motion built on open-licensed assets: MakeHuman (CC0) bodies and CMU motion-capture data.
          </p>
        </div>
      </div>

      <p
        ref={hintRef}
        className="pointer-events-none absolute inset-x-0 bottom-8 text-center text-xs font-semibold uppercase tracking-[0.2em] text-fg-muted"
        aria-hidden="true"
      >
        Scroll
      </p>

      <div
        className="absolute inset-x-0 bottom-0 h-0.5 bg-white/10"
        aria-hidden="true"
      >
        <div ref={barRef} className="h-full origin-left scale-x-0 bg-primary" />
      </div>
    </div>
  );
}
