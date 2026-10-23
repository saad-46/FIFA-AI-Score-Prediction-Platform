import * as THREE from "three";
import { BALL_RADIUS, createBall } from "./ball";
import type { GLTF } from "three/addons/loaders/GLTFLoader.js";
import type { RunClips, ShotClip } from "./character/mocap";
import { RealisticRig } from "./character/realistic-rig";
import { CharacterRig } from "./character/rig";
import { seeded, smoothstep } from "./math";
import type { QualityTier } from "./quality";
import { createSceneState, sampleScene } from "./sample-scene";
import { createStadium } from "./stadium";
import { toScene } from "./timeline";

const BASE_FOV = 32;
const KEY_OFFSET = new THREE.Vector3(-9, 20, 13);
const RIM_OFFSET = new THREE.Vector3(5, 7, -12);
const FILL_OFFSET = new THREE.Vector3(6, 3, 12);
/** Opening pan for narrow screens: metres of pan per metre the half-width of the view falls short of OPENING_PAN_WIDTH. */
const OPENING_PAN = 1.4;
const OPENING_PAN_WIDTH = 4.2;
/** Face fill strength; multiplied by each player's own need (see FACE_FILL). */
const FACE_LIGHT = 2.2;

/** A puff of dust whose every particle position is a function of one number. */
function createDust(count: number) {
  const rnd = seeded(41);
  const dirs = new Float32Array(count * 3);
  const seeds = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    const a = rnd() * Math.PI * 2;
    const r = 0.35 + rnd() * 0.9;
    dirs.set([Math.cos(a) * r, 0.1 + rnd() * 0.75, Math.sin(a) * r], i * 3);
    seeds[i] = rnd();
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  geometry.setAttribute("aDir", new THREE.BufferAttribute(dirs, 3));
  geometry.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 1));
  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    uniforms: { uT: { value: 0 }, uScale: { value: 1 } },
    vertexShader: /* glsl */ `
      attribute vec3 aDir;
      attribute float aSeed;
      uniform float uT;
      uniform float uScale;
      varying float vAlpha;
      void main() {
        float t = clamp(uT * (0.75 + 0.5 * aSeed), 0.0, 1.0);
        float e = 1.0 - (1.0 - t) * (1.0 - t);
        vec3 p = aDir * vec3(e * 1.5, e * (1.0 - 0.45 * t), e * 1.5);
        vAlpha = sin(3.14159 * t) * (0.1 + 0.16 * aSeed);
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = uScale * (0.16 + 0.3 * aSeed) * (0.6 + t) / -mv.z;
      }`,
    fragmentShader: /* glsl */ `
      varying float vAlpha;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        float a = smoothstep(0.5, 0.0, d) * vAlpha;
        gl_FragColor = vec4(vec3(0.62, 0.68, 0.74) * a, a);
      }`,
    blending: THREE.CustomBlending,
    blendSrc: THREE.OneFactor,
    blendDst: THREE.OneMinusSrcAlphaFactor,
  });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  return { points, geometry, material };
}

/**
 * Everything in the 3D scene, built once and then posed from progress.
 * Plain three.js: React only mounts it and asks it to update.
 */
export class IntroWorld {
  readonly root = new THREE.Group();
  readonly state = createSceneState();
  readonly background = new THREE.Color("#04060b");
  readonly fog = new THREE.FogExp2("#060a13", 0.0125);

  private readonly rig: CharacterRig | RealisticRig;
  private readonly ball = createBall();
  private readonly bootProbe = new THREE.Vector3();
  private readonly stadium = createStadium();
  private readonly dust: ReturnType<typeof createDust>;
  /** Sparks over the goalmouth when the ball goes in. */
  private readonly sparks: ReturnType<typeof createDust>;
  private readonly hemi = new THREE.HemisphereLight("#6f8fc4", "#0c1f12", 0);
  private readonly key = new THREE.DirectionalLight("#eef4ff", 0);
  private readonly rim = new THREE.DirectionalLight("#ffffff", 0);
  /** Soft light from the camera side, so the unlit half of a face is not black. */
  private readonly fill = new THREE.DirectionalLight("#9fb6e0", 0);
  private readonly pool = new THREE.SpotLight("#dfeaff", 0, 0, 0.3, 0.75, 0);
  private readonly target = new THREE.Vector3();
  private lastProgress = -1;
  private readonly face: THREE.SpotLight | null = null;
  private readonly facePos = new THREE.Vector3();

  /** `player` is the loaded realistic footballer; without it the procedural figure is used. */
  constructor(
    private readonly tier: QualityTier,
    player?: { gltf: GLTF; skins: THREE.Texture[]; runClips: RunClips | null; shotClip: ShotClip | null }
  ) {
    this.rig = player ? new RealisticRig(player.gltf, player.skins, player.runClips, player.shotClip) : new CharacterRig();
    if (this.rig instanceof RealisticRig) {
      // Only the realistic figure has a face worth lighting; adding the light
      // only here leaves the procedural scene exactly as it was.
      this.face = new THREE.SpotLight("#ffe6d2", 0, 4.5, 0.32, 0.85, 1.4);
      this.root.add(this.face, this.face.target);
    }
    this.dust = createDust(tier.dust);
    this.sparks = createDust(tier.dust * 2);
    this.sparks.points.scale.set(2.6, 2.4, 2.6);
    this.root.add(this.stadium.group, this.rig.actor, this.ball.mesh, this.dust.points, this.sparks.points);

    this.key.castShadow = tier.shadowMap > 0;
    if (tier.shadowMap > 0) {
      this.key.shadow.mapSize.set(tier.shadowMap, tier.shadowMap);
      const cam = this.key.shadow.camera;
      cam.left = -5;
      cam.right = 5;
      cam.top = 5;
      cam.bottom = -5;
      cam.near = 1;
      cam.far = 60;
      this.key.shadow.bias = -0.0004;
      this.key.shadow.normalBias = 0.02;
    }
    this.pool.position.set(-8.1, 19, 5);
    this.pool.target.position.set(-8.1, 0, 0);
    this.root.add(this.hemi, this.key, this.key.target, this.rim, this.rim.target, this.fill, this.fill.target, this.pool, this.pool.target);
  }

  /**
   * Draws everything once with culling and visibility overridden, so every
   * shader program (goal posts, net, sparks, their shadow variants) links
   * while the still covers the canvas. Otherwise each links the first frame
   * its object enters view, a synchronous 200-300ms stall mid-scroll.
   * Call after `update`, so the figure is posed.
   */
  prewarm(gl: THREE.WebGLRenderer, scene: THREE.Scene, camera: THREE.Camera) {
    const culled: THREE.Object3D[] = [];
    this.root.traverse((o) => {
      if (o.frustumCulled) {
        o.frustumCulled = false;
        culled.push(o);
      }
    });
    const dust = this.dust.points.visible;
    const sparks = this.sparks.points.visible;
    this.dust.points.visible = this.sparks.points.visible = true;
    try {
      gl.render(scene, camera);
    } finally {
      for (const o of culled) o.frustumCulled = true;
      this.dust.points.visible = dust;
      this.sparks.points.visible = sparks;
    }
  }

  /** Poses the whole scene for `progress`. Safe to call with any value in any order. */
  update(progress: number, camera: THREE.PerspectiveCamera, aspect: number, viewportHeight: number) {
    const s = sampleScene(progress, this.state);
    this.lastProgress = progress;

    this.rig.actor.position.set(s.actor.x, 0, s.actor.z);
    this.rig.actor.rotation.y = s.actor.yaw;
    this.rig.update(s.identity, s.motion);

    this.ball.mesh.position.set(s.ball.x, s.ball.y, s.ball.z);
    this.ball.mesh.quaternion.set(s.ball.qx, s.ball.qy, s.ball.qz, s.ball.qw);

    // Lights. The key light keeps one direction for the whole run and only
    // follows the action so its shadow stays sharp; it never betrays a morph.
    this.target.set(s.camera.tx, 0, 0);
    this.key.position.copy(this.target).add(KEY_OFFSET);
    this.key.target.position.copy(this.target);
    this.key.intensity = 2.5 * s.light.key;
    this.rim.position.copy(this.target).add(RIM_OFFSET);
    this.rim.target.position.copy(this.target);
    this.rim.color.copy(this.rig.rim).lerp(WHITE, 0.45);
    this.rim.intensity = 1.5 * s.light.key;
    this.fill.position.copy(this.target).add(FILL_OFFSET);
    this.fill.target.position.copy(this.target);
    this.fill.intensity = 0.55 * s.light.key;
    this.hemi.intensity = 0.5 * s.light.ambient;
    this.pool.intensity = 3.2 * s.light.pool;
    this.stadium.setFloodlights(s.light.floodA, s.light.floodB);

    this.dust.points.position.set(s.dust.x, 0.05, s.dust.z);
    this.dust.points.visible = s.dust.t > 0 && s.dust.t < 1;
    this.dust.material.uniforms.uT.value = s.dust.t;
    this.dust.material.uniforms.uScale.value = viewportHeight;
    this.sparks.points.position.set(s.goal.netX - 1.2, 0.2, s.goal.netZ);
    this.sparks.points.visible = s.goal.burst > 0 && s.goal.burst < 1;
    this.sparks.material.uniforms.uT.value = s.goal.burst;
    this.sparks.material.uniforms.uScale.value = viewportHeight * 1.6;
    this.stadium.setNetImpact(s.goal.net, s.goal.netX, s.goal.netY, s.goal.netZ, s.goal.netT);

    // On a portrait screen a fixed vertical field of view would crop the
    // action to a sliver, so widen it to keep the horizontal view.
    const hFov = 2 * Math.atan(Math.tan((BASE_FOV * Math.PI) / 360) * 1.6);
    const fov = aspect >= 1.6 ? BASE_FOV : Math.min(58, (2 * Math.atan(Math.tan(hFov / 2) / aspect) * 180) / Math.PI);
    if (camera.fov !== fov) {
      camera.fov = fov;
      camera.updateProjectionMatrix();
    }
    // The camera waits on the spot the ball rolls to while the first player
    // runs in from further left. On a narrow screen that spot is nearer the
    // edge of the view than the player is, so the opening was empty until he
    // was almost on the ball; pan the whole shot left until the follow-cam
    // takes over. Zero on any screen at least as wide as the base 1.6 aspect.
    const halfWidth = Math.tan((fov * Math.PI) / 360) * aspect * Math.hypot(s.camera.x - s.camera.tx, s.camera.y - s.camera.ty, s.camera.z - s.camera.tz);
    const pan = -OPENING_PAN * Math.max(0, OPENING_PAN_WIDTH - halfWidth) * (1 - smoothstep(0.08, 0.17, progress));
    camera.position.set(s.camera.x + pan, s.camera.y, s.camera.z);
    camera.lookAt(s.camera.tx + pan, s.camera.ty, s.camera.tz);
    if (this.face && this.rig instanceof RealisticRig) {
      // A restrained fill aimed at the face from the camera side: it lifts the
      // shadowed half of the face without raising the stadium's ambient light.
      // Placed after the camera is set: it reads the camera's position, and
      // before this was moved it read the previous frame's, so the same progress
      // lit the face differently depending on which way the viewer had come.
      this.rig.facePosition(this.facePos);
      this.face.target.position.copy(this.facePos);
      this.face.position.set(camera.position.x, camera.position.y + 0.5, camera.position.z).sub(this.facePos).setLength(2.2).add(this.facePos);
      this.face.intensity = FACE_LIGHT * this.rig.faceFill * s.light.key;
    }

    return s;
  }

  /** A compact, comparable description of the current pose, for the debug hook. */
  snapshot() {
    const s = this.state;
    const scenePos = toScene(this.lastProgress);
    const r = (v: number) => Math.round(v * 1e5) / 1e5;
    return {
      progress: this.lastProgress,
      actor: [r(s.actor.x), r(s.actor.z), r(s.actor.yaw)],
      ball: [r(s.ball.x), r(s.ball.y), r(s.ball.z), r(s.ball.qx), r(s.ball.qy), r(s.ball.qz), r(s.ball.qw)],
      camera: [r(s.camera.x), r(s.camera.y), r(s.camera.z)],
      identity: [s.identity.a, s.identity.b, r(s.identity.t)],
      phase: r(s.motion.phase),
      rig: this.rig.snapshot(),
      torso: this.rig instanceof RealisticRig ? this.rig.torsoDebug() : null,
      // Debug only: how far the ball's surface is from the right boot's mesh (negative: overlapping), near the strike.
      bootGap:
        this.rig instanceof RealisticRig && ((scenePos > 0.63 && scenePos < 0.73) || (scenePos > 0.77 && scenePos < 0.87))
          ? this.rig.bootGap(this.bootProbe.set(s.ball.x, s.ball.y, s.ball.z), BALL_RADIUS)
          : null,
      // Debug only: the same, by nearest vertex (a cross-check).
      bootVertexGap:
        this.rig instanceof RealisticRig && ((scenePos > 0.63 && scenePos < 0.73) || (scenePos > 0.77 && scenePos < 0.87))
          ? this.rig.bootVertexGap(this.bootProbe.set(s.ball.x, s.ball.y, s.ball.z), BALL_RADIUS)
          : null,
    };
  }

  dispose() {
    this.rig.dispose();
    this.ball.dispose();
    this.stadium.dispose();
    this.dust.geometry.dispose();
    this.dust.material.dispose();
    this.sparks.geometry.dispose();
    this.sparks.material.dispose();
    this.key.shadow.map?.dispose();
    this.key.dispose();
    this.rim.dispose();
    this.fill.dispose();
    this.face?.dispose();
    this.pool.dispose();
    this.hemi.dispose();
  }
}

const WHITE = new THREE.Color("#ffffff");
