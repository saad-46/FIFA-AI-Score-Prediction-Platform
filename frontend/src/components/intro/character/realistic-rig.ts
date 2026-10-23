import * as THREE from "three";
import type { GLTF } from "three/addons/loaders/GLTFLoader.js";
import { clone as cloneSkinned } from "three/addons/utils/SkeletonUtils.js";
import { PLAYERS, lerpStride, type Stride } from "../profiles";
import { BONE, BONE_COUNT } from "./body-geometry";
import { KitMaterial, NOISE_GLSL, createNumberAtlas } from "./kit-material";
import { BALL_RADIUS } from "../ball";
import { RUNS } from "../timeline";
import { sampleContact, sampleRunRotation, sampleShotContact, sampleShotRotation, sampleShotTrack, sampleTrack, type RunClips, type RunCycle, type ShotClip } from "./mocap";
import { computePose, createPose, type Motion } from "./pose";
import type { Identity } from "./rig";

/** The realistic footballers: player 1's meshes, every later player as a morph target. See ASSETS.md. */
export const REALISTIC_PLAYERS_URL = "/intro/players.glb";
/** Skin textures for players 2 onward; they share player 1's UV layout. */
export const PLAYER_SKIN_URLS = [2, 3, 4, 5, 6, 7, 8].map((n) => `/intro/player-${n}-skin.webp`);
/** Players beyond the first keep an unskinned copy of their skeleton, named with this prefix and a number. */
const prefix = (player: number) => `p${player + 1}_`;

/** The pose system's 17 bones, mapped onto the model's skeleton. */
const BONE_NAMES: Record<number, string> = {
  [BONE.HIPS]: "pelvis",
  [BONE.SPINE]: "spine_01",
  [BONE.CHEST]: "spine_03",
  [BONE.NECK]: "neck_01",
  [BONE.HEAD]: "head",
  [BONE.UARM_L]: "upperarm_l",
  [BONE.FARM_L]: "lowerarm_l",
  [BONE.HAND_L]: "hand_l",
  [BONE.UARM_R]: "upperarm_r",
  [BONE.FARM_R]: "lowerarm_r",
  [BONE.HAND_R]: "hand_r",
  [BONE.THIGH_L]: "thigh_l",
  [BONE.SHIN_L]: "calf_l",
  [BONE.FOOT_L]: "foot_l",
  [BONE.THIGH_R]: "thigh_r",
  [BONE.SHIN_R]: "calf_r",
  [BONE.FOOT_R]: "foot_r",
};

/** Radians each finger joint is bent from the model's open-handed rest pose. */
const FINGER_CURL = 0.38;
const FINGERS = /^(index|middle|ring|pinky)_0[123]_[lr]$/;

const KIT_PART: Record<string, number> = { kit_shirt: 1, kit_shorts: 2, kit_socks: 3 };
/** Which player each hairstyle belongs to, by material name, and its tint. */
const HAIR: Record<string, { owner: number; color: string }> = {
  "Human.short02": { owner: 0, color: "#6f5d50" },
  "Human.afro01": { owner: 1, color: "#3b2c22" },
  "Human.short04": { owner: 2, color: "#2a211c" },
  "Human.ponytail01": { owner: 3, color: "#c9a766" },
  "Human.short03": { owner: 4, color: "#9a7a5a" },
  "Human.short01": { owner: 5, color: "#241b15" },
  "Human.afro01_short": { owner: 6, color: "#16100c" },
  "Human.short04_kane": { owner: 7, color: "#5a4632" },
};
/** Which players each captured run can be seen on (including through the morphs at its ends). */
const RUN_PLAYERS: Record<string, readonly number[]> = { runIn: [0], sprint: [1, 2, 3], drive: [2, 3, 6, 7], approach: [4, 5] };
const TAU = Math.PI * 2;
/** The shooter: the captured strike is only ever worn by player 6. */
const SHOT_PLAYER = 5;

/** How much face fill light each player needs under the night lighting (darker skin needs more). */
const FACE_FILL = [0.55, 1.5, 1.3, 0.5, 0.55, 0.65, 1.0, 0.6];

/**
 * Checks a loaded model has everything the rig needs. Returns a reason when
 * it does not, so a bad file can fall back to the procedural figure instead
 * of failing part-way through building the scene.
 */
export function checkPlayersModel(gltf: GLTF, skins: THREE.Texture[]): string | null {
  let body: THREE.Mesh | null = null;
  const skeletons: THREE.Skeleton[] = [];
  gltf.scene.traverse((o) => {
    const mesh = o as THREE.SkinnedMesh;
    if (mesh.isSkinnedMesh) skeletons.push(mesh.skeleton);
    if (mesh.isMesh && (mesh.material as THREE.Material).name === "Human.body") body = mesh;
  });
  if (!body) return "no body mesh";
  const players = ((body as THREE.Mesh).morphTargetInfluences?.length ?? 0) + 1;
  if (players < 2) return "the body has no morph targets";
  if (players - 1 > skins.length) return `${players} players but only ${skins.length + 1} skin textures`;
  if (!skeletons.length) return "no skinned meshes";
  for (const name of Object.values(BONE_NAMES)) if (!gltf.scene.getObjectByName(name)) return `missing bone ${name}`;
  for (let p = 1; p < players; p++) {
    for (const bone of skeletons[0].bones) {
      if (!gltf.scene.getObjectByName(prefix(p) + bone.name)) return `player ${p + 1} has no bone ${bone.name}`;
    }
  }
  return null;
}

/** One bone's rest pose for every player, and the current blend. */
interface BoneRest {
  bone: THREE.Object3D;
  parent: number;
  pos: THREE.Vector3[];
  rot: THREE.Quaternion[];
  scale: THREE.Vector3;
  /** Player 1's rest matrix relative to the model root. */
  relA: THREE.Matrix4;
  /** The blended rest, rebuilt every frame. */
  curPos: THREE.Vector3;
  curRot: THREE.Quaternion;
  rel: THREE.Matrix4;
  relRot: THREE.Quaternion;
}

interface Binding {
  skeleton: THREE.Skeleton;
  rest: number[];
  inverseA: THREE.Matrix4[];
}

/**
 * How much of the key light's shadow the skin shows (1 = all of it). Cast onto
 * skin the shadow of a hanging hand reads as a hard, jagged black patch (on
 * the kicking thigh during the strike), because the shadow map is about a
 * texel per millimetre-scale feature there. The ground and the kit keep full
 * shadows; skin keeps a faint trace so it still sits in the scene's light.
 */
const SKIN_SHADOW = 0.3;

/** Body texture that cross-fades between two skins sharing one UV layout. */
class BlendedSkinMaterial extends THREE.MeshStandardMaterial {
  readonly uMix = { value: 0 };
  readonly uMapA: { value: THREE.Texture | null };
  readonly uMapB: { value: THREE.Texture | null };
  constructor(map: THREE.Texture | null) {
    super({ map, roughness: 0.58, metalness: 0 });
    this.uMapA = { value: map };
    this.uMapB = { value: map };
    this.onBeforeCompile = (shader) => {
      shader.uniforms.uSkinA = this.uMapA;
      shader.uniforms.uSkinB = this.uMapB;
      shader.uniforms.uSkinMix = this.uMix;
      shader.fragmentShader = shader.fragmentShader
        .replace("#include <lights_fragment_begin>", THREE.ShaderChunk.lights_fragment_begin.replaceAll("directionalLightShadow.shadowIntensity", `( directionalLightShadow.shadowIntensity * ${SKIN_SHADOW} )`))
        .replace("#include <common>", "#include <common>\nuniform sampler2D uSkinA;\nuniform sampler2D uSkinB;\nuniform float uSkinMix;")
        .replace(
          "#include <map_fragment>",
          "#ifdef USE_MAP\n  diffuseColor *= mix(texture2D(uSkinA, vMapUv), texture2D(uSkinB, vMapUv), uSkinMix);\n#endif"
        );
    };
    this.customProgramCacheKey = () => "intro-blended-skin-v3";
  }
}

/**
 * Hair cards with a noisy cut. The outgoing style keeps the pixels whose noise
 * is above the cut and the incoming style the ones below it, from the same
 * noise field: as the cut sweeps, the two exchange coverage patch by patch, so
 * the scalp is never bare.
 */
class CrossfadeHairMaterial extends THREE.MeshStandardMaterial {
  readonly uCut = { value: 0 };
  readonly uIncoming = { value: 0 };
  constructor(map: THREE.Texture | null, color: string) {
    super({ map, color, roughness: 0.8, metalness: 0, alphaTest: 0.4, side: THREE.DoubleSide });
    this.onBeforeCompile = (shader) => {
      shader.uniforms.uCut = this.uCut;
      shader.uniforms.uIncoming = this.uIncoming;
      shader.vertexShader = shader.vertexShader
        .replace("#include <common>", "#include <common>\nvarying vec3 vHairPos;")
        .replace("#include <begin_vertex>", "#include <begin_vertex>\nvHairPos = position;");
      shader.fragmentShader = shader.fragmentShader
        .replace("#include <common>", `#include <common>\nvarying vec3 vHairPos;\nuniform float uCut;\nuniform float uIncoming;\n${NOISE_GLSL}`)
        .replace(
          "#include <alphatest_fragment>",
          "#include <alphatest_fragment>\nfloat hairN = introNoise(vHairPos * 28.0);\nif (uIncoming > 0.5 ? hairN > uCut : hairN < uCut) discard;"
        );
    };
    this.customProgramCacheKey = () => "intro-hair-crossfade-v1";
  }
}

const relOf = (o: THREE.Object3D, root: THREE.Object3D) => root.matrixWorld.clone().invert().multiply(o.matrixWorld);

/**
 * The realistic footballers, loaded from one GLB.
 *
 * Built with MakeHuman/MPFB (see ASSETS.md). What changes between players,
 * and how:
 *  - face, head, body, hands, boots and kit: genuine geometry interpolation.
 *    Every player comes from the same base mesh, so each is a morph target
 *    of player 1 with the same vertices in the same order.
 *  - skeleton: joint positions and rest orientations are blended, with the
 *    inverse bind matrices rebuilt each frame, so the bones stay inside the
 *    morphing body.
 *  - skin: two textures on the same UVs, cross-faded (a texture blend).
 *  - kit colours: the existing kit shader's upward sweep.
 *  - hair: separate meshes exchanged patch by patch (a swap, without a bare
 *    moment); every style follows the morphing head.
 *
 * Everything is a function of the identity and motion passed in, which come
 * from scroll progress alone.
 */
export class RealisticRig {
  readonly actor = new THREE.Group();
  readonly rim = new THREE.Color();
  /** Strength of the face fill light this player needs (0 = none). */
  faceFill = 0;

  readonly players: number;
  private readonly root: THREE.Object3D;
  private readonly bones: BoneRest[] = [];
  private readonly byName = new Map<string, number>();
  private readonly bindings: Binding[] = [];
  private readonly mapped: number[] = [];
  private readonly fixes: THREE.Quaternion[][] = [];
  private readonly morphing: THREE.Mesh[] = [];
  private readonly hair: { owner: number; material: CrossfadeHairMaterial; mesh: THREE.Mesh }[] = [];
  private readonly feet: { bone: THREE.Object3D; points: THREE.Vector3[] }[] = [];
  private readonly kit: KitMaterial[] = [];
  private readonly skin: BlendedSkinMaterial;
  private readonly skins: (THREE.Texture | null)[];
  private readonly disposables: { dispose(): void }[] = [];
  private readonly shared = new Set<{ dispose(): void }>();
  private readonly fingers: number[] = [];
  private readonly curl = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), FINGER_CURL);
  private readonly pose = createPose();
  private readonly stride: Stride = { ...PLAYERS[0].stride };
  private readonly q = new THREE.Quaternion();
  private readonly qInv = new THREE.Quaternion();
  private readonly fix = new THREE.Quaternion();
  private readonly e = new THREE.Euler();
  private readonly v = new THREE.Vector3();
  private readonly m = new THREE.Matrix4();
  private readonly rimB = new THREE.Color();
  private readonly headBone: THREE.Object3D;
  private readonly topRel: THREE.Matrix4;
  private readonly topRot: THREE.Quaternion;

  constructor(gltf: GLTF, skins: THREE.Texture[], private readonly runClips: RunClips | null = null, private readonly shotClip: ShotClip | null = null) {
    // A clone, so one loaded file can back more than one rig (React mounts
    // components twice in development). Geometry and textures are shared
    // with the cached file, so they are not disposed here.
    this.root = cloneSkinned(gltf.scene);
    this.actor.add(this.root);
    this.root.updateMatrixWorld(true);
    for (const s of skins) {
      s.flipY = false;
      s.colorSpace = THREE.SRGBColorSpace;
    }

    const height = new THREE.Box3().setFromObject(this.root).max.y;
    let skin: BlendedSkinMaterial | null = null;
    let skin1: THREE.Texture | null = null;
    let numbers: THREE.CanvasTexture | null = null;

    this.root.traverse((o) => {
      const mesh = o as THREE.SkinnedMesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.frustumCulled = false;
      if (mesh.morphTargetInfluences?.length) this.morphing.push(mesh);
      const source = mesh.material as THREE.MeshStandardMaterial;
      const name = source.name;
      const map = source.map;
      this.shared.add(mesh.geometry);
      if (map) this.shared.add(map);

      if (name in KIT_PART) {
        // Same shader as the procedural figure: it needs to know which
        // garment a vertex belongs to and where it sits on player 1's body.
        // A copy of the geometry, because these attributes are added here.
        mesh.geometry = mesh.geometry.clone();
        this.disposables.push(mesh.geometry);
        const pos = mesh.geometry.getAttribute("position");
        const part = new Float32Array(pos.count).fill(KIT_PART[name]);
        const pat = new Float32Array(pos.count * 3);
        const num = new Float32Array(pos.count * 3);
        // Through the mesh transform: the file stores quantised positions
        // (Meshopt), so the raw attribute values are not metres.
        const toModel = mesh.matrixWorld;
        const v = new THREE.Vector3();
        for (let i = 0; i < pos.count; i++) {
          v.fromBufferAttribute(pos, i).applyMatrix4(toModel);
          // Metres, in the rest pose: the shirt number's own coordinates (the
          // height division below varies with how the model was measured).
          num.set([v.x, v.y, v.z], i * 3);
          v.divideScalar(height);
          pat.set([v.x, v.y, v.z], i * 3);
        }
        mesh.geometry.setAttribute("aPart", new THREE.BufferAttribute(part, 1));
        mesh.geometry.setAttribute("aPat", new THREE.BufferAttribute(pat, 3));
        mesh.geometry.setAttribute("aNum", new THREE.BufferAttribute(num, 3));
        numbers ??= createNumberAtlas();
        const material = new KitMaterial(numbers);
        material.side = THREE.DoubleSide;
        material.roughness = 0.86;
        this.kit.push(material);
        this.disposables.push(material);
        mesh.material = material;
        return;
      }
      if (name in HAIR) {
        const material = new CrossfadeHairMaterial(map, HAIR[name].color);
        this.hair.push({ owner: HAIR[name].owner, material, mesh });
        this.disposables.push(material);
        mesh.material = material;
        return;
      }
      if (name === "Human.body") {
        skin = new BlendedSkinMaterial(map);
        skin1 = map;
        this.disposables.push(skin);
        mesh.material = skin;
        return;
      }

      const material = new THREE.MeshStandardMaterial({ map, roughness: 0.62, metalness: 0 });
      if (/eyebrow|eyelash/i.test(name)) {
        material.alphaTest = 0.3;
        material.side = THREE.DoubleSide;
        material.color.set("#3a2c24");
        mesh.castShadow = false;
      } else if (/low-poly|eye/i.test(name)) {
        material.roughness = 0.25;
      } else if (/shoes/i.test(name)) {
        material.roughness = 0.45;
      }
      this.disposables.push(material);
      mesh.material = material;
    });
    if (numbers) this.disposables.push(numbers);
    if (!skin) throw new Error("intro: the player model has no body mesh");
    this.skin = skin;
    this.players = Math.min(PLAYERS.length, this.morphing[0].morphTargetInfluences!.length + 1);
    this.skins = [skin1, ...skins];

    // ── Skeleton: every player's rest pose ─────────────────────────────────
    const skinned: THREE.SkinnedMesh[] = [];
    this.root.traverse((o) => {
      if ((o as THREE.SkinnedMesh).isSkinnedMesh) skinned.push(o as THREE.SkinnedMesh);
    });
    const isMain = (o: THREE.Object3D | null) => Boolean(o && (o as THREE.Bone).isBone && !/^p\d+_/.test(o.name));
    const order: THREE.Object3D[] = [];
    skinned[0].skeleton.bones[0].parent?.traverse((o) => {
      if (isMain(o)) order.push(o);
    });
    for (const bone of order) {
      const pos = [bone.position.clone()];
      const rot = [bone.quaternion.clone()];
      for (let p = 1; p < this.players; p++) {
        const other = this.root.getObjectByName(prefix(p) + bone.name)!;
        pos.push(other.position.clone());
        rot.push(other.quaternion.clone());
      }
      if (FINGERS.test(bone.name)) this.fingers.push(this.bones.length);
      this.byName.set(bone.name, this.bones.length);
      this.bones.push({
        bone,
        parent: isMain(bone.parent) ? this.byName.get(bone.parent!.name)! : -1,
        pos,
        rot,
        scale: bone.scale.clone(),
        relA: relOf(bone, this.root),
        curPos: new THREE.Vector3(),
        curRot: new THREE.Quaternion(),
        rel: new THREE.Matrix4(),
        relRot: new THREE.Quaternion(),
      });
    }
    this.topRel = relOf(this.bones[0].bone.parent!, this.root);
    this.topRot = new THREE.Quaternion().setFromRotationMatrix(this.topRel);
    for (const mesh of skinned) {
      this.bindings.push({
        skeleton: mesh.skeleton,
        rest: mesh.skeleton.bones.map((b) => this.byName.get(b.name)!),
        inverseA: mesh.skeleton.boneInverses.map((m) => m.clone()),
      });
    }
    this.root.traverse((o) => {
      if (/^p\d+_/.test(o.name)) o.visible = false;
    });

    for (let i = 0; i < BONE_COUNT; i++) this.mapped.push(this.boneIndex(BONE_NAMES[i]));
    // The model rests with its arms held out; the pose system assumes they
    // hang at the sides. One correction per player, blended.
    const down = new THREE.Vector3(0, -1, 0);
    for (let p = 0; p < this.players; p++) {
      this.blendRest(p, p, 0);
      const list: THREE.Quaternion[] = [];
      for (let i = 0; i < BONE_COUNT; i++) {
        const fix = new THREE.Quaternion();
        if (i === BONE.UARM_L || i === BONE.UARM_R) {
          const a = new THREE.Vector3().setFromMatrixPosition(this.bones[this.mapped[i]].rel);
          const dir = new THREE.Vector3().setFromMatrixPosition(this.bones[this.mapped[i + 1]].rel).sub(a).normalize();
          fix.setFromUnitVectors(dir, down);
        }
        list.push(fix);
      }
      this.fixes.push(list);
    }
    this.headBone = this.bones[this.boneIndex("head")].bone;

    // Sole reference points, stored in each foot bone's own space (player 1).
    this.blendRest(0, 0, 0);
    for (const b of this.bones) {
      b.bone.position.copy(b.curPos);
      b.bone.quaternion.copy(b.curRot);
    }
    this.root.updateMatrixWorld(true);
    for (const side of ["l", "r"]) {
      const foot = this.bones[this.boneIndex(`foot_${side}`)].bone;
      const ball = this.bones[this.boneIndex(`ball_${side}`)].bone;
      const inv = foot.matrixWorld.clone().invert();
      const f = foot.getWorldPosition(new THREE.Vector3());
      const b = ball.getWorldPosition(new THREE.Vector3());
      const toe = b.clone().add(b.clone().sub(f).setY(0).normalize().multiplyScalar(0.07));
      const heel = f.clone().add(f.clone().sub(b).setY(0).normalize().multiplyScalar(0.05));
      this.feet.push({ bone: foot, points: [heel.setY(0).applyMatrix4(inv), toe.setY(0).applyMatrix4(inv)] });
    }
    this.calibrateRuns();
    this.calibrateShot();
  }

  private boneIndex(name: string) {
    const i = this.byName.get(name);
    if (i === undefined) throw new Error(`intro: bone "${name}" is missing from the player model`);
    return i;
  }

  /** Blends two players' rest skeletons, and rebuilds the bind matrices that go with them. */
  private blendRest(a: number, b: number, t: number) {
    for (const r of this.bones) {
      r.curPos.lerpVectors(r.pos[a], r.pos[b], t);
      r.curRot.slerpQuaternions(r.rot[a], r.rot[b], t);
      this.m.compose(r.curPos, r.curRot, r.scale);
      if (r.parent < 0) {
        r.rel.multiplyMatrices(this.topRel, this.m);
        r.relRot.multiplyQuaternions(this.topRot, r.curRot);
      } else {
        const p = this.bones[r.parent];
        r.rel.multiplyMatrices(p.rel, this.m);
        r.relRot.multiplyQuaternions(p.relRot, r.curRot);
      }
    }
    // inverse(blended rest) * player 1's rest * player 1's inverse bind: at the
    // blended rest pose every bone matrix is the identity, so the morphing
    // mesh is not distorted by a skeleton that belongs to a different body.
    for (const binding of this.bindings) {
      for (let k = 0; k < binding.rest.length; k++) {
        const r = this.bones[binding.rest[k]];
        binding.skeleton.boneInverses[k].copy(r.rel).invert().multiply(r.relA).multiply(binding.inverseA[k]);
      }
    }
  }

  update(id: Identity, motion: Motion) {
    const last = this.players - 1;
    const a = Math.min(id.a, last);
    const b = Math.min(id.b, last);
    const t = a === b ? 0 : id.t;

    // ── Geometry: morph target k is player k + 1 ──────────────────────────
    for (const mesh of this.morphing) {
      const inf = mesh.morphTargetInfluences!;
      inf.fill(0);
      if (a > 0) inf[a - 1] += 1 - t;
      if (b > 0) inf[b - 1] += t;
    }

    // ── Skeleton and pose ─────────────────────────────────────────────────
    this.blendRest(a, b, t);
    for (const r of this.bones) {
      r.bone.position.copy(r.curPos);
      r.bone.quaternion.copy(r.curRot);
    }
    lerpStride(PLAYERS[a].stride, PLAYERS[b].stride, t, this.stride);
    computePose(motion, this.stride, this.pose);
    this.useQ = false;
    // Captured running where the timeline asks for it. Its phase comes from
    // the ground covered and this skeleton's own stride for that clip, aligned
    // with the hand-built phase at the segment's anchor.
    const clipName = motion.run2 >= 0 ? RUNS[motion.run2].clip : null;
    const cycle = clipName ? this.runClips?.[clipName] : undefined;
    const weight = cycle ? motion.runWeight : 0;
    let lead = 0;
    let runPhase = motion.phase;
    this.lastRun = { clip: weight > 0 ? clipName : null, weight, contact: 0, phase: 0 };
    if (cycle && weight > 0) {
      const leg = this.legLength();
      const strides = this.runStride[clipName!] ?? [];
      const sa = strides[a] ?? cycle.strideOverLeg * leg;
      const stride = sa + ((strides[b] ?? sa) - sa) * t;
      runPhase = motion.runAnchorPhase + (TAU * (motion.distance - motion.runAnchorDistance)) / stride;
      this.applyRunCycle(cycle, motion, weight, runPhase);
      this.lastRun.contact = sampleContact(cycle, runPhase);
      this.lastRun.phase = runPhase;
      // The captured body speeds up and slows within each stride; add that
      // back along the facing so a planted foot stays planted.
      lead = sampleTrack(cycle, cycle.rootForward, runPhase) * leg * motion.run * weight;
    }
    // The captured shot, worn by the shooter only. It replaces the hand-built
    // strike (and the run) in proportion to its weight; every term is
    // computed from this frame's inputs.
    const shot = this.shotClip;
    const shotWeight = shot && a === SHOT_PLAYER && b === SHOT_PLAYER ? motion.shotWeight : 0;
    this.lastShot = { weight: shotWeight, t: motion.shotT, contact: 0 };
    if (shot && shotWeight > 0) {
      this.applyShot(shot, motion.shotT, shotWeight);
      this.lastShot.contact = sampleShotContact(shot, motion.shotT);
    }
    for (let i = 0; i < BONE_COUNT; i++) {
      const r = this.bones[this.mapped[i]];
      // A rotation given in the figure's axes, re-expressed in the bone's own
      // rest frame: local = rest * (world^-1 * pose * fix * world).
      if (this.useQ) this.q.copy(this.poseQ[i]);
      else this.q.setFromEuler(this.e.set(this.pose[i * 3], this.pose[i * 3 + 1], this.pose[i * 3 + 2]));
      this.fix.slerpQuaternions(this.fixes[a][i], this.fixes[b][i], t);
      this.qInv.copy(r.relRot).invert();
      r.bone.quaternion.copy(r.curRot).multiply(this.qInv).multiply(this.q).multiply(this.fix).multiply(r.relRot);
    }
    // Relaxed hands, on top of the rest pose so the bind matrices still
    // describe the model's real rest pose.
    for (const i of this.fingers) this.bones[i].bone.quaternion.multiply(this.curl);

    // Stand on the grass: lift or lower the whole skeleton so the lowest
    // point of either boot is at the requested height.
    this.root.position.set(0, 0, lead);
    this.root.rotation.y = 0;
    this.actor.updateMatrixWorld(true);
    let lowest = Infinity;
    for (const foot of this.feet) {
      for (const p of foot.points) {
        const y = this.v.copy(p).applyMatrix4(foot.bone.matrixWorld).y;
        if (y < lowest) lowest = y;
      }
    }
    const grounded = motion.air - (lowest - this.actor.position.y);
    let height = grounded;
    if (cycle && clipName && weight > 0 && motion.run > 0) {
      // The captured run carries its own hip height, flight phase included,
      // instead of pinning whichever foot is lowest to the grass. It is
      // only ever lifted, never pushed down, if a boot would go below it.
      const pelvis = this.bones[this.mapped[BONE.HIPS]];
      const restY = pelvis.rel.elements[13];
      const wanted = restY + (sampleTrack(cycle, cycle.hipHeight, runPhase) - cycle.restHipHeight) * this.legLength();
      const now = pelvis.bone.getWorldPosition(this.v).y - this.actor.position.y;
      // Per-frame correction (see calibrateRuns): puts the source runner's
      // planted foot on the grass in every frame where it was planted.
      const corrections = this.runCorrection[clipName] ?? [];
      const ca = corrections[a] ? sampleTrack(cycle, corrections[a], runPhase) : 0;
      const cb = corrections[b] ? sampleTrack(cycle, corrections[b], runPhase) : ca;
      const lift = ca + (cb - ca) * t;
      this.lastCapturedBase = wanted - now;
      const captured = Math.max(wanted - now + lift, grounded - motion.air);
      height = grounded + (captured - grounded) * weight * motion.run;
    }
    if (shot && shotWeight > 0) {
      // The captured body's own hip height, with the planted foot on the grass (see calibrateShot).
      const pelvis = this.bones[this.mapped[BONE.HIPS]];
      const restY = pelvis.rel.elements[13];
      const wanted = restY + (sampleShotTrack(shot, shot.hipHeight, motion.shotT) - shot.restHipHeight) * this.legLength();
      const now = pelvis.bone.getWorldPosition(this.v).y - this.actor.position.y;
      const lift = this.shotCorrection ? sampleShotTrack(shot, this.shotCorrection, motion.shotT) : 0;
      this.lastCapturedBase = wanted - now;
      const captured = Math.max(wanted - now + lift, grounded - motion.air);
      height += (captured - height) * shotWeight;
      this.placeShot(shot, motion, shotWeight, lead);
    }
    if (motion.bike > 0) {
      // The kick sets the pelvis height itself: the boots are no use for grounding a figure laid out in the air.
      const pelvis = this.bones[this.mapped[BONE.HIPS]];
      this.root.position.y = 0;
      this.actor.updateMatrixWorld(true);
      const now = pelvis.bone.getWorldPosition(this.v).y - this.actor.position.y;
      height += (motion.bikeHip - now - height) * motion.bike;
    }
    this.root.position.y = height;

    // ── Surfaces ──────────────────────────────────────────────────────────
    const pa = PLAYERS[a];
    const pb = PLAYERS[b];
    for (const k of this.kit) k.setBlend(pa.kit, pb.kit, pa.skin, pb.skin, t);
    this.skin.uMapA.value = this.skins[a];
    this.skin.uMapB.value = this.skins[b];
    this.skin.uMix.value = THREE.MathUtils.smoothstep(t, 0.2, 0.8);
    // The cut sweeps across the middle of the morph; outgoing and incoming
    // hair cover complementary patches, so there is always hair on the head.
    const cut = THREE.MathUtils.smoothstep(t, 0.25, 0.75);
    for (const h of this.hair) {
      const outgoing = h.owner === a && a !== b;
      const incoming = h.owner === b && a !== b;
      const held = a === b && h.owner === a;
      h.mesh.visible = held || (outgoing && cut < 0.999) || (incoming && cut > 0.001);
      h.material.uIncoming.value = incoming ? 1 : 0;
      h.material.uCut.value = held ? 0 : cut;
    }
    this.faceFill = THREE.MathUtils.lerp(FACE_FILL[a] ?? 1, FACE_FILL[b] ?? 1, t);
    this.rim.set(pa.kit.rim).lerp(this.rimB.set(pb.kit.rim), t);
  }

  /**
   * Hip height does not transfer exactly between two skeletons, so once, on
   * load, run the cycle on this player's own skeleton and find the shift that
   * puts the lowest stance contact exactly on the grass. A constant, so the
   * motion stays a pure function of phase.
   */
  private readonly runCorrection: Record<string, (Float32Array | undefined)[]> = {};
  private lastCapturedBase = 0;
  /** Stride per clip and player, measured on that player's skeleton (see calibrateRuns). */
  private readonly runStride: Record<string, number[]> = {};
  private lastRun: { clip: string | null; weight: number; contact: number; phase: number } = { clip: null, weight: 0, contact: 0, phase: 0 };
  private calibrateRuns() {
    if (!this.runClips) return;
    for (let k = 0; k < RUNS.length; k++) {
      const name = RUNS[k].clip;
      const cycle = this.runClips[name];
      if (!cycle) continue;
      const corrections: (Float32Array | undefined)[] = [];
      this.runCorrection[name] = corrections;
      for (const player of RUN_PLAYERS[name] ?? []) {
        if (player >= this.players) continue;
        const id = { a: player, b: player, t: 0 };
        // Sweep one whole captured stride on this player's skeleton.
        this.blendRest(player, player, 0);
        const stride = cycle.strideOverLeg * this.legLength();
        const motion: Motion = { ...this.plain, run: 1, run2: k, runWeight: 1, runAnchorDistance: 0, runAnchorPhase: Math.PI / 2 };
        corrections[player] = undefined;
        const strides = (this.runStride[name] ??= []);
        strides[player] = stride;
        let lowest = Infinity;
        // Also measure, where the source runner's foot was planted, how far
        // that foot moves backwards relative to the body per radian of phase.
        // The body must cover exactly that, or the planted foot slides.
        let back = 0;
        let span = 0;
        let prev: { z: number[]; contact: number } | null = null;
        const N = 48;
        for (let i = 0; i <= N; i++) {
          motion.distance = (stride * i) / N;
          motion.phase = Math.PI / 2;
          this.update(id, motion);
          this.actor.updateMatrixWorld(true);
          for (const foot of this.feet) for (const pt of foot.points) lowest = Math.min(lowest, this.v.copy(pt).applyMatrix4(foot.bone.matrixWorld).y);
          const z = this.feet.map((f) => (f.points[0].clone().applyMatrix4(f.bone.matrixWorld).z + f.points[1].clone().applyMatrix4(f.bone.matrixWorld).z) / 2);
          const contact = this.lastRun.contact;
          if (prev) {
            for (let f = 0; f < 2; f++) {
              if (prev.contact & contact & (1 << f)) {
                back += prev.z[f] - z[f];
                span += TAU / N;
              }
            }
          }
          prev = { z, contact };
        }
        if (span > 0 && back > 0) strides[player] = (back / span) * TAU;

        // Height: at every baked frame where the source runner had a foot
        // planted, the lift that puts that foot's sole on the grass; between
        // contacts (flight), interpolated. Measured with no correction applied.
        const n = cycle.frames;
        const corr = new Float32Array(n).fill(Number.NaN);
        for (let f = 0; f < n; f++) {
          motion.distance = (strides[player] * f) / n;
          this.update(id, motion);
          this.actor.updateMatrixWorld(true);
          const c = cycle.contact[f];
          let low = Infinity;
          this.feet.forEach((foot, side) => {
            if (!(c & (1 << side))) return;
            for (const pt of foot.points) low = Math.min(low, this.v.copy(pt).applyMatrix4(foot.bone.matrixWorld).y);
          });
          // The lift that puts that sole on the grass, relative to the uncorrected captured height.
          if (low < Infinity) corr[f] = this.root.position.y - low - this.lastCapturedBase;
        }
        const known = [...corr.keys()].filter((f) => !Number.isNaN(corr[f]));
        if (!known.length) {
          corr.fill(-lowest);
        } else {
          for (let f = 0; f < n; f++) {
            if (!Number.isNaN(corr[f])) continue;
            // Nearest known frames before and after, around the loop.
            let i = f;
            let j = f;
            while (Number.isNaN(corr[(i + n) % n])) i--;
            while (Number.isNaN(corr[j % n])) j++;
            const a0 = corr[(i + n) % n];
            const b0 = corr[j % n];
            corr[f] = a0 + ((b0 - a0) * (f - i)) / (j - i);
          }
        }
        corrections[player] = corr;
      }
    }
  }

  private lastShot: { weight: number; t: number; contact: number } = { weight: 0, t: 0, contact: 0 };
  /** Planted-foot height correction per shot frame (see calibrateShot). */
  private shotCorrection: Float32Array | null = null;
  /**
   * Where the ball's centre is at the moment of contact, relative to the root
   * (x left, y along the kick = z; metres): the place where the ball just
   * touches the skinned boot mesh. Measured by calibrateShot.
   */
  private readonly shotBall = new THREE.Vector2();
  private readonly shotTmp = new THREE.Vector3();

  /** A reference point on the kicking boot (just past the toe joint), for the debug snapshot only; the figure is placed by the boot's mesh, see solveContact. */
  private strikePoint(out: THREE.Vector3) {
    const foot = this.bones[this.boneIndex("foot_r")].bone;
    const toe = this.bones[this.boneIndex("ball_r")].bone;
    const f = foot.getWorldPosition(this.shotTmp);
    toe.getWorldPosition(out);
    const dx = out.x - f.x;
    const dz = out.z - f.z;
    const n = Math.hypot(dx, dz) || 1;
    out.x += (dx / n) * 0.03;
    out.z += (dz / n) * 0.03;
    return out;
  }

  private bootMeshes: { mesh: THREE.SkinnedMesh; vertices: number[] }[] | null = null;
  /** Triangles of the right boot and foot, as indices into the packed list of its vertices (see bootPoints). */
  private bootTriangles: Uint32Array = new Uint32Array(0);
  private readonly tri = new THREE.Triangle();
  private readonly triPoint = new THREE.Vector3();

  /** The vertices of the right boot and foot (those mostly weighted to the foot and toe bones), per skinned mesh. */
  private bootVertices() {
    if (this.bootMeshes) return this.bootMeshes;
    this.bootMeshes = [];
    const triangles: number[] = [];
    let offset = 0;
    this.root.traverse((o) => {
      const mesh = o as THREE.SkinnedMesh;
      if (!mesh.isSkinnedMesh) return;
      const bones = mesh.skeleton.bones.map((b) => b.name);
      const own = new Set([bones.indexOf("foot_r"), bones.indexOf("ball_r")].filter((i) => i >= 0));
      const index = mesh.geometry.getAttribute("skinIndex");
      const weight = mesh.geometry.getAttribute("skinWeight");
      if (!index || !weight || !own.size) return;
      const vertices: number[] = [];
      const packed = new Int32Array(index.count).fill(-1);
      for (let v = 0; v < index.count; v++) {
        let w = 0;
        for (let k = 0; k < 4; k++) if (own.has(index.getComponent(v, k))) w += weight.getComponent(v, k);
        if (w >= 0.5) {
          packed[v] = offset + vertices.length;
          vertices.push(v);
        }
      }
      if (!vertices.length) return;
      const idx = mesh.geometry.index;
      const count = idx ? idx.count : index.count;
      for (let t = 0; t + 2 < count; t += 3) {
        const a = packed[idx ? idx.getX(t) : t];
        const b = packed[idx ? idx.getX(t + 1) : t + 1];
        const c = packed[idx ? idx.getX(t + 2) : t + 2];
        if (a >= 0 && b >= 0 && c >= 0) triangles.push(a, b, c);
      }
      offset += vertices.length;
      this.bootMeshes!.push({ mesh, vertices });
    });
    this.bootTriangles = Uint32Array.from(triangles);
    return this.bootMeshes;
  }

  /** World positions (x, y, z, ...) of the right boot's vertices, as skinned right now. */
  private bootPoints(): Float32Array {
    const groups = this.bootVertices();
    const out = new Float32Array(groups.reduce((n, g) => n + g.vertices.length, 0) * 3);
    let i = 0;
    for (const { mesh, vertices } of groups) {
      mesh.updateMatrixWorld(true);
      for (const v of vertices) {
        mesh.getVertexPosition(v, this.shotTmp).applyMatrix4(mesh.matrixWorld);
        out[i++] = this.shotTmp.x;
        out[i++] = this.shotTmp.y;
        out[i++] = this.shotTmp.z;
      }
    }
    return out;
  }

  /** Distance from a point to the surface of the right boot and foot (its triangles), given its packed vertex positions. */
  private distanceToBoot(pts: Float32Array, x: number, y: number, z: number): number {
    const t = this.bootTriangles;
    const q = this.triPoint.set(x, y, z);
    const { a, b, c } = this.tri;
    let best = Infinity;
    for (let i = 0; i < t.length; i += 3) {
      a.set(pts[t[i] * 3], pts[t[i] * 3 + 1], pts[t[i] * 3 + 2]);
      b.set(pts[t[i + 1] * 3], pts[t[i + 1] * 3 + 1], pts[t[i + 1] * 3 + 2]);
      c.set(pts[t[i + 2] * 3], pts[t[i + 2] * 3 + 1], pts[t[i + 2] * 3 + 2]);
      this.tri.closestPointToPoint(q, this.shotTmp);
      best = Math.min(best, this.shotTmp.distanceToSquared(q));
    }
    return Math.sqrt(best);
  }

  /**
   * Debug measurement: the signed distance from the surface of a ball to the
   * surface of the right boot and foot (point-to-triangle, as skinned right
   * now). Positive means apart; negative means the boot is inside the ball.
   */
  bootGap(ball: THREE.Vector3, radius: number): number {
    const pts = this.bootPoints();
    return this.distanceToBoot(pts, ball.x, ball.y, ball.z) - radius;
  }

  /**
   * Debug measurement by a cruder estimator, as a cross-check on bootGap: the
   * distance to the nearest vertex of the boot, which can only over-estimate
   * the distance to its surface.
   */
  bootVertexGap(ball: THREE.Vector3, radius: number): number {
    const pts = this.bootPoints();
    let best = Infinity;
    for (let i = 0; i < pts.length; i += 3) best = Math.min(best, Math.hypot(pts[i] - ball.x, pts[i + 1] - ball.y, pts[i + 2] - ball.z));
    return best - radius;
  }

  /** Replaces the pose with the captured shot, in rotations, by weight. */
  private applyShot(shot: ShotClip, t: number, weight: number) {
    const Q = this.blendQ;
    for (let i = 0; i < BONE_COUNT; i++) {
      if (!this.useQ) Q.full.setFromEuler(this.e.set(this.pose[i * 3], this.pose[i * 3 + 1], this.pose[i * 3 + 2]));
      else Q.full.copy(this.poseQ[i]);
      sampleShotRotation(shot, i, t, Q.cap);
      this.poseQ[i].slerpQuaternions(Q.full, Q.cap, weight);
    }
    this.useQ = true;
  }

  /**
   * Puts the captured body where it strikes the ball: turned so the kick
   * goes the way the ball leaves, and placed so that at the moment of contact
   * the ball just touches the boot (see calibrateShot). The rest of the clip's
   * travel follows from there. Everything is relative to the figure's path in
   * the scene, blended in by weight.
   */
  private placeShot(shot: ShotClip, motion: Motion, weight: number, lead: number) {
    const leg = this.legLength();
    const psi = Math.atan2(motion.shotAimX, motion.shotAimZ);
    const c = Math.cos(psi);
    const s = Math.sin(psi);
    const bx = this.shotBall.x;
    const bz = this.shotBall.y;
    const w0x = motion.shotBallX - (c * bx + s * bz);
    const w0z = motion.shotBallZ - (-s * bx + c * bz);
    const rx = sampleShotTrack(shot, shot.rootX, motion.shotT) * leg;
    const rz = sampleShotTrack(shot, shot.rootZ, motion.shotT) * leg;
    const wx = w0x + c * rx + s * rz;
    const wz = w0z - s * rx + c * rz;
    // Into the figure's own frame.
    const ya = this.actor.rotation.y;
    const dx = wx - this.actor.position.x;
    const dz = wz - this.actor.position.z;
    const lx = Math.cos(ya) * dx - Math.sin(ya) * dz;
    const lz = Math.sin(ya) * dx + Math.cos(ya) * dz;
    let turn = psi - ya;
    turn -= TAU * Math.round(turn / TAU);
    this.root.position.x = lx * weight;
    this.root.position.z = lead * (1 - weight) + lz * weight;
    this.root.rotation.y = turn * weight;
  }

  /**
   * Once, on load, runs the shot on the shooter's own skeleton to measure
   * what the clip cannot tell us: where a ball sitting on the grass touches
   * this boot's mesh at the moment of contact, and, for every frame where the
   * source player had a foot planted, the height shift that puts that sole on
   * the grass. Constants, so the motion stays a pure function of progress.
   */
  private calibrateShot() {
    const clip = this.shotClip;
    if (!clip || this.players <= SHOT_PLAYER) return;
    const id = { a: SHOT_PLAYER, b: SHOT_PLAYER, t: 0 };
    this.blendRest(SHOT_PLAYER, SHOT_PLAYER, 0);
    const motion: Motion = { ...this.plain, shotWeight: 1, shotAimX: 0, shotAimZ: 1, shotBallX: 0, shotBallZ: 0 };
    this.shotBall.set(0, 0);
    this.shotCorrection = null;
    const n = clip.frames;
    const corr = new Float32Array(n).fill(Number.NaN);
    for (let f = 0; f < n; f++) {
      motion.shotT = (f - clip.impact) / clip.fps;
      this.update(id, motion);
      this.actor.updateMatrixWorld(true);
      const c = clip.contact[f];
      let low = Infinity;
      this.feet.forEach((foot, side) => {
        if (!(c & (1 << side))) return;
        for (const pt of foot.points) low = Math.min(low, this.v.copy(pt).applyMatrix4(foot.bone.matrixWorld).y);
      });
      if (low < Infinity) corr[f] = this.root.position.y - low - this.lastCapturedBase;
      if (f === clip.impact) this.solveContact();
    }
    for (let f = 0; f < n; f++) {
      if (!Number.isNaN(corr[f])) continue;
      let i = f;
      let j = f;
      while (i >= 0 && Number.isNaN(corr[i])) i--;
      while (j < n && Number.isNaN(corr[j])) j++;
      if (i < 0 && j >= n) corr[f] = 0;
      else if (i < 0) corr[f] = corr[j];
      else if (j >= n) corr[f] = corr[i];
      else corr[f] = corr[i] + ((corr[j] - corr[i]) * (f - i)) / (j - i);
    }
    this.shotCorrection = corr;
    // The height correction moves the boot a little, so find the touching place again with it in effect.
    motion.shotT = 0;
    this.update(id, motion);
    this.actor.updateMatrixWorld(true);
    this.solveContact();
  }

  /**
   * At the contact frame (figure axes: +z is the kick, the root is at the
   * origin), finds where a ball resting on the grass, in line with the
   * forefoot, just touches the boot mesh: slide the ball along the kick until
   * the nearest boot vertex is exactly one ball radius from its centre.
   */
  private solveContact() {
    const pts = this.bootPoints();
    const joint = this.bones[this.boneIndex("ball_r")].bone.getWorldPosition(this.shotTmp);
    const x = joint.x;
    const z0 = joint.z;
    const gap = (z: number) => this.distanceToBoot(pts, x, BALL_RADIUS, z) - BALL_RADIUS;
    let far = z0 + 0.6;
    let near = z0;
    let z = z0;
    if (gap(far) > 0 && gap(near) < 0) {
      for (let i = 0; i < 40; i++) {
        const mid = (far + near) / 2;
        if (gap(mid) > 0) far = mid;
        else near = mid;
      }
      z = far;
    }
    // Relative to where the root is now (world axes are the figure's here).
    this.shotBall.set(x - this.root.position.x, z - this.root.position.z);
  }

  /** Hip-to-ankle length of the current blended skeleton. */
  private legLength() {
    return this.bones[this.mapped[BONE.SHIN_L]].curPos.length() + this.bones[this.mapped[BONE.FOOT_L]].curPos.length();
  }

  private readonly runOnly = createPose();
  private readonly standing = createPose();
  private readonly plain: Motion = { phase: 0, run: 0, feint: 0, spin: 0, kick: 0, kickT: 0, stepover: 0, flick: 0, flickT: 0, air: 0, celebrate: 0, crouch: 0, distance: 0, pass: 0, passT: 0, touch: 0, touchT: 0, run2: -1, runWeight: 0, runAnchorDistance: 0, runAnchorPhase: 0, shotT: 0, shotWeight: 0, shotBallX: 0, shotBallZ: 0, shotAimX: 0, shotAimZ: 1, bike: 0, bikeT: 0, bikeHip: 0 };

  /**
   * Replaces the hand-built run cycle with the captured one and keeps every
   * hand-built move (touches, feints, the strike) layered on top:
   *   gestures = full - runOnly
   *   result   = lerp(full, lerp(standing, captured, run) + gestures, weight)
   * Every term is computed from this frame's inputs; nothing carries over.
   */
  private applyRunCycle(cycle: RunCycle, motion: Motion, weight: number, runPhase: number) {
    const plain = this.plain;
    plain.phase = motion.phase;
    plain.run = motion.run;
    computePose(plain, this.stride, this.runOnly);
    plain.run = 0;
    computePose(plain, this.stride, this.standing);
    // In rotations, not Euler angles: the captured and hand-built angles can
    // describe similar rotations with very different numbers, and averaging
    // those numbers produces a third, wrong rotation.
    const Q = this.blendQ;
    for (let i = 0; i < BONE_COUNT; i++) {
      const e = (arr: Float32Array, q: THREE.Quaternion) => q.setFromEuler(this.e.set(arr[i * 3], arr[i * 3 + 1], arr[i * 3 + 2]));
      e(this.pose, Q.full);
      e(this.runOnly, Q.run);
      e(this.standing, Q.stand);
      sampleRunRotation(cycle, i, runPhase, Q.cap);
      // gesture = full * run^-1 ; captured base = slerp(standing, captured, run)
      Q.gesture.copy(Q.full).multiply(Q.run.invert());
      Q.base.slerpQuaternions(Q.stand, Q.cap, motion.run);
      Q.mixed.copy(Q.gesture).multiply(Q.base);
      this.poseQ[i].slerpQuaternions(Q.full, Q.mixed, weight);
    }
    this.useQ = true;
  }

  private readonly poseQ = Array.from({ length: BONE_COUNT }, () => new THREE.Quaternion());
  private useQ = false;
  private readonly blendQ = {
    full: new THREE.Quaternion(),
    run: new THREE.Quaternion(),
    stand: new THREE.Quaternion(),
    cap: new THREE.Quaternion(),
    gesture: new THREE.Quaternion(),
    base: new THREE.Quaternion(),
    mixed: new THREE.Quaternion(),
  };

  /** World position of the face, for the face fill light. */
  facePosition(out: THREE.Vector3) {
    return this.headBone.getWorldPosition(out).add(this.v.set(0, 0.06, 0));
  }

  snapshot() {
    return {
      headY: this.headBone.getWorldPosition(this.v).y,
      hipsY: this.root.position.y,
      morph: this.morphing.length ? Array.from(this.morphing[0].morphTargetInfluences!) : [],
      hair: this.hair.filter((h) => h.mesh.visible).map((h) => h.owner),
      run: this.lastRun,
      shot: this.lastShot,
      // The struck point of the kicking boot, in world space.
      strike: this.strikePoint(new THREE.Vector3()).toArray().map((v) => Math.round(v * 1e4) / 1e4),
      // Lowest sole point of each boot, in world space.
      feet: this.feet.map((f) => {
        const pts = f.points.map((p) => p.clone().applyMatrix4(f.bone.matrixWorld));
        // Horizontal position: the middle of the boot (a fixed point, so it
        // does not jump between heel and toe); height: its lowest point.
        const x = (pts[0].x + pts[1].x) / 2;
        const z = (pts[0].z + pts[1].z) / 2;
        return [x, Math.min(pts[0].y, pts[1].y), z].map((v) => Math.round(v * 1e4) / 1e4);
      }),
    };
  }

  /** Debug: the trunk's orientation in the figure's own frame, in radians (twist of the shoulder and hip lines, forward lean). */
  torsoDebug() {
    this.actor.updateMatrixWorld(true);
    const at = (b: number) => this.actor.worldToLocal(this.bones[this.mapped[b]].bone.getWorldPosition(new THREE.Vector3()));
    const line = (l: number, r: number) => {
      const a = at(l);
      const c = at(r);
      return Math.atan2(a.z - c.z, a.x - c.x);
    };
    const hips = at(BONE.HIPS);
    const neck = at(BONE.NECK);
    return {
      shoulderTwist: line(BONE.UARM_L, BONE.UARM_R),
      hipTwist: line(BONE.THIGH_L, BONE.THIGH_R),
      lean: Math.atan2(neck.z - hips.z, neck.y - hips.y),
    };
  }

  dispose() {
    for (const d of this.disposables) d.dispose();
    // Each skinned mesh's skeleton owns a bone texture on the GPU.
    for (const b of this.bindings) b.skeleton.dispose();
    // The cached file's geometry and textures are shared between mounts, but
    // every renderer that drew them attached its own dispose listeners, which
    // keep that renderer reachable after it is gone. Disposing them releases
    // those renderers; the data stays in memory, so the next mount simply
    // uploads it again.
    for (const d of this.shared) d.dispose();
    for (const t of this.skins) t?.dispose();
  }
}
