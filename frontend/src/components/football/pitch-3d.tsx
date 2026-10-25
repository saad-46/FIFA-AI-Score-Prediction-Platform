"use client";

import { useEffect, useRef } from "react";
import type { CircleGeometry, RingGeometry } from "three";

/**
 * The pitch as real geometry: a perspective camera looking down at a grass plane, with the markings, goals and
 * lights modelled in 3D. It is drawn once and again on resize (nothing animates), so it costs no per-frame work.
 *
 * Proportions are stylised for a very wide card: the pitch is 150 long and 56 across, the boxes are scaled to
 * match. The grass texture is generated on a small 2D canvas (stripes, blotches, fine grain) rather than
 * downloaded. three is imported inside the effect so it is only fetched when the card is on screen.
 *
 * `onReady` fires after the first frame; `onFail` when WebGL is unavailable or the context is lost, and the
 * caller keeps showing its CSS/SVG pitch.
 */
const L = 150; // pitch length (x)
const W = 56; // pitch width (z)

export default function Pitch3D({ onReady, onFail }: { onReady: () => void; onFail: () => void }) {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let disposed = false;
    let cleanup = () => {};
    // Visitors who ask to save data keep the 2D pitch.
    if ((navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData) {
      onFail();
      return;
    }

    (async () => {
      try {
        // Probe first: three logs an error of its own when it cannot get a context, and a missing GPU is not one.
        const probe = document.createElement("canvas");
        const gl = probe.getContext("webgl2") ?? probe.getContext("webgl");
        if (!gl) {
          onFail();
          return;
        }
        gl.getExtension("WEBGL_lose_context")?.loseContext();
        const THREE = await import("three");
        if (disposed) return;
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "low-power" });
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 0.95;
        renderer.domElement.style.cssText = "position:absolute;inset:0;width:100%;height:100%;display:block";
        host.appendChild(renderer.domElement);

        const scene = new THREE.Scene();
        scene.background = new THREE.Color("#082414");
        scene.fog = new THREE.Fog("#082414", 60, 135);
        const camera = new THREE.PerspectiveCamera(30, 3, 1, 400);
        camera.position.set(0, 74, 34);
        camera.lookAt(0, 0, -3);

        const disposables: { dispose(): void }[] = [renderer];
        const own = <T extends { dispose(): void }>(o: T) => (disposables.push(o), o);

        // ── grass texture ────────────────────────────────────────────────────
        const TW = 2048;
        const TH = 768;
        const tex = document.createElement("canvas");
        tex.width = TW;
        tex.height = TH;
        const g = tex.getContext("2d")!;
        let seed = 20260719;
        const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
        g.fillStyle = "#1f5c2f";
        g.fillRect(0, 0, TW, TH);
        // understated mowing bands: alternating tone a few percent apart
        const stripes = 20;
        for (let i = 0; i < stripes; i++) {
          g.fillStyle = i % 2 ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.06)";
          g.fillRect((i * TW) / stripes, 0, TW / stripes + 1, TH);
        }
        // gentle large-scale tonal drift, then many small patches so no single blotch reads as a shape
        for (let i = 0; i < 14; i++) {
          const x = rnd() * TW;
          const y = rnd() * TH;
          const r = 260 + rnd() * 320;
          const grad = g.createRadialGradient(x, y, 0, x, y, r);
          const c = rnd() > 0.5 ? "70,140,70" : "10,60,30";
          grad.addColorStop(0, `rgba(${c},0.05)`);
          grad.addColorStop(1, `rgba(${c},0)`);
          g.fillStyle = grad;
          g.fillRect(x - r, y - r, r * 2, r * 2);
        }
        for (let i = 0; i < 700; i++) {
          const x = rnd() * TW;
          const y = rnd() * TH;
          const r = 14 + rnd() * 34;
          const grad = g.createRadialGradient(x, y, 0, x, y, r);
          const c = rnd() > 0.5 ? "90,160,80" : "8,50,24";
          grad.addColorStop(0, `rgba(${c},0.07)`);
          grad.addColorStop(1, `rgba(${c},0)`);
          g.fillStyle = grad;
          g.fillRect(x - r, y - r, r * 2, r * 2);
        }
        // blades: tens of thousands of short, slightly tilted strokes in two tones
        g.lineCap = "round";
        for (let i = 0; i < 70000; i++) {
          const x = rnd() * TW;
          const y = rnd() * TH;
          const len = 5 + rnd() * 9;
          const tilt = (rnd() - 0.5) * 0.7;
          g.strokeStyle = rnd() > 0.45 ? "rgba(150,210,120,0.10)" : "rgba(4,30,12,0.16)";
          g.lineWidth = 0.8 + rnd() * 0.8;
          g.beginPath();
          g.moveTo(x, y);
          g.lineTo(x + Math.sin(tilt) * len, y - Math.cos(tilt) * len);
          g.stroke();
        }
        const img = g.getImageData(0, 0, TW, TH);
        for (let i = 0; i < img.data.length; i += 4) {
          const n = (rnd() - 0.5) * 14;
          img.data[i] += n * 0.7;
          img.data[i + 1] += n;
          img.data[i + 2] += n * 0.6;
        }
        g.putImageData(img, 0, 0);
        const grass = own(new THREE.CanvasTexture(tex));
        grass.colorSpace = THREE.SRGBColorSpace;
        grass.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());

        const ground = new THREE.Mesh(
          new THREE.PlaneGeometry(L, W),
          own(new THREE.MeshStandardMaterial({ map: grass, roughness: 1, metalness: 0 }))
        );
        own(ground.geometry);
        ground.rotation.x = -Math.PI / 2;
        ground.receiveShadow = true;
        scene.add(ground);
        // grass beyond the touchlines, darker, so the edges fall away
        const apron = new THREE.Mesh(
          new THREE.PlaneGeometry(L + 120, W + 120),
          own(new THREE.MeshStandardMaterial({ color: "#0d3519", roughness: 1 }))
        );
        own(apron.geometry);
        apron.rotation.x = -Math.PI / 2;
        apron.position.y = -0.05;
        apron.receiveShadow = true;
        scene.add(apron);

        // ── markings ─────────────────────────────────────────────────────────
        const lineMat = own(
          new THREE.MeshBasicMaterial({ color: "#ffffff", transparent: true, opacity: 0.88, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 })
        );
        const T = 0.5; // line thickness
        const flat = (geo: RingGeometry | CircleGeometry, x: number, z: number) => {
          own(geo);
          const m = new THREE.Mesh(geo, lineMat);
          m.rotation.x = -Math.PI / 2;
          m.position.set(x, 0.03, z);
          m.renderOrder = 2;
          scene.add(m);
        };
        const bar = (x0: number, z0: number, x1: number, z1: number) => {
          const len = Math.hypot(x1 - x0, z1 - z0);
          const geo = new THREE.PlaneGeometry(len + T, T);
          own(geo);
          const m = new THREE.Mesh(geo, lineMat);
          m.rotation.x = -Math.PI / 2;
          m.rotation.z = Math.atan2(-(z1 - z0), x1 - x0);
          m.position.set((x0 + x1) / 2, 0.03, (z0 + z1) / 2);
          m.renderOrder = 2;
          scene.add(m);
        };
        const rect = (x0: number, z0: number, x1: number, z1: number) => {
          bar(x0, z0, x1, z0);
          bar(x1, z0, x1, z1);
          bar(x1, z1, x0, z1);
          bar(x0, z1, x0, z0);
        };
        rect(-L / 2, -W / 2 + 0.3, L / 2, W / 2 - 0.3); // touchlines and goal lines
        bar(0, -W / 2, 0, W / 2); // halfway line
        flat(new THREE.RingGeometry(14 - T / 2, 14 + T / 2, 96), 0, 0); // centre circle
        flat(new THREE.CircleGeometry(0.7, 24), 0, 0);
        for (const s of [-1, 1]) {
          const gx = (s * L) / 2;
          rect(gx, -17, gx - s * 22, 17); // penalty area
          rect(gx, -8, gx - s * 8, 8); // goal area
          flat(new THREE.CircleGeometry(0.7, 24), gx - s * 15, 0); // penalty spot
          // the "D": part of a circle round the spot, outside the box
          const half = Math.acos((22 - 15) / 11);
          const arc = new THREE.RingGeometry(11 - T / 2, 11 + T / 2, 48, 1, s > 0 ? Math.PI - half : -half, half * 2);
          flat(arc, gx - s * 15, 0);
        }

        // ── goals (the only shadow casters) ─────────────────────────────────
        const metal = own(new THREE.MeshStandardMaterial({ color: "#f4f6f4", roughness: 0.5 }));
        const netTex = document.createElement("canvas");
        netTex.width = netTex.height = 64;
        const n = netTex.getContext("2d")!;
        n.strokeStyle = "rgba(255,255,255,0.9)";
        n.lineWidth = 3;
        n.strokeRect(0, 0, 64, 64);
        const net = own(new THREE.CanvasTexture(netTex));
        net.wrapS = net.wrapT = THREE.RepeatWrapping;
        net.repeat.set(10, 4);
        const netMat = own(new THREE.MeshBasicMaterial({ map: net, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false }));
        for (const s of [-1, 1]) {
          const gx = (s * L) / 2;
          const post = own(new THREE.CylinderGeometry(0.22, 0.22, 4.4, 10));
          for (const z of [-5, 5]) {
            const p = new THREE.Mesh(post, metal);
            p.position.set(gx, 2.2, z);
            p.castShadow = true;
            scene.add(p);
          }
          const barGeo = own(new THREE.CylinderGeometry(0.22, 0.22, 10.4, 10));
          const cross = new THREE.Mesh(barGeo, metal);
          cross.rotation.x = Math.PI / 2;
          cross.position.set(gx, 4.4, 0);
          cross.castShadow = true;
          scene.add(cross);
          const back = new THREE.Mesh(own(new THREE.PlaneGeometry(10, 4.4)), netMat);
          back.rotation.y = Math.PI / 2;
          back.position.set(gx + s * 3.2, 2.2, 0);
          scene.add(back);
        }

        // ── light ────────────────────────────────────────────────────────────
        scene.add(new THREE.HemisphereLight("#d6efd8", "#072010", 0.55));
        const key = new THREE.DirectionalLight("#fff3d6", 1.35);
        key.position.set(-40, 70, 30);
        key.castShadow = true;
        key.shadow.mapSize.set(1024, 1024);
        key.shadow.camera.left = -90;
        key.shadow.camera.right = 90;
        key.shadow.camera.top = 40;
        key.shadow.camera.bottom = -40;
        key.shadow.camera.far = 220;
        key.shadow.radius = 6;
        scene.add(key);
        // a soft pool of light on the middle of the pitch; the edges stay dark
        const pool = new THREE.SpotLight("#f2ffe8", 2.0, 0, 0.7, 1, 0);
        pool.position.set(0, 90, 20);
        pool.target.position.set(0, 0, 0);
        scene.add(pool, pool.target);
        // floodlights at the two far corners: a wide, soft wash that lifts the upper edges of the pitch
        for (const s of [-1, 1]) {
          const flood = new THREE.SpotLight("#fff1d0", 0.9, 0, 0.55, 1, 0);
          flood.position.set(s * 80, 60, -40);
          flood.target.position.set(s * 38, 0, -6);
          scene.add(flood, flood.target);
        }

        const size = () => {
          const w = Math.max(1, host.clientWidth);
          const h = Math.max(1, host.clientHeight);
          renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, w < 640 ? 1.25 : 1.5));
          renderer.setSize(w, h, false);
          camera.aspect = w / h;
          // keep the same width of pitch in view on wide cards; narrower cards show the middle of it
          camera.fov = camera.aspect > 2 ? 30 : 30 * Math.min(1.6, 2.4 / camera.aspect);
          camera.updateProjectionMatrix();
          renderer.render(scene, camera);
        };
        size();
        const ro = new ResizeObserver(size);
        ro.observe(host);
        const lost = (e: Event) => {
          e.preventDefault();
          onFail();
        };
        renderer.domElement.addEventListener("webglcontextlost", lost);
        onReady();

        cleanup = () => {
          ro.disconnect();
          renderer.domElement.removeEventListener("webglcontextlost", lost);
          disposables.forEach((d) => d.dispose());
          renderer.forceContextLoss();
          renderer.domElement.remove();
        };
        if (disposed) cleanup();
      } catch {
        if (!disposed) onFail();
      }
    })();

    return () => {
      disposed = true;
      cleanup();
    };
    // onReady/onFail are stable setters from the parent; the scene is built once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={hostRef} className="absolute inset-0" />;
}
