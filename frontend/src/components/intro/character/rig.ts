import * as THREE from "three";
import { PLAYERS, lerpStride, type Stride } from "../profiles";
import { BONE, BONE_COUNT, BONE_PARENT, buildBodyGeometry, type BodyLayout } from "./body-geometry";
import { HairSet } from "./hair";
import { KitMaterial } from "./kit-material";
import { computePose, createPose, type Motion } from "./pose";

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const smoothstep = (a: number, b: number, v: number) => {
  const t = Math.min(1, Math.max(0, (v - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

/** What the figure is at a given moment: which two profiles, and how far between them. */
export interface Identity {
  a: number;
  b: number;
  t: number;
}

/**
 * One skinned mesh, one skeleton, every player.
 *
 * Changing player does three different things, and they are not equally
 * "morphs":
 *  - body: genuine interpolation. Morph targets move the shared vertices and
 *    the joints move with them, so height, limb length and build all change.
 *  - kit and skin: one material; colours blend and a boundary sweeps upward.
 *  - hair and beard: separate meshes that dissolve out and in (a swap).
 */
export class CharacterRig {
  /** Position and facing of the figure. Feet are at this group's origin. */
  readonly actor = new THREE.Group();
  readonly rim = new THREE.Color();

  private readonly mesh: THREE.SkinnedMesh;
  private readonly material = new KitMaterial();
  private readonly bones: THREE.Bone[] = [];
  private readonly skeleton: THREE.Skeleton;
  private readonly layouts: BodyLayout[];
  private readonly hair: HairSet;
  private readonly face = new THREE.Group();
  private readonly faceParts: { dispose(): void }[] = [];
  private readonly joints = new Float32Array(BONE_COUNT * 3);
  private readonly pose = createPose();
  private readonly stride: Stride = { ...PLAYERS[0].stride };
  private readonly tmp = new THREE.Vector3();
  private readonly rimB = new THREE.Color();

  constructor() {
    const { geometry, layouts } = buildBodyGeometry(PLAYERS.map((p) => p.body));
    this.layouts = layouts;

    for (let i = 0; i < BONE_COUNT; i++) {
      const bone = new THREE.Bone();
      this.bones.push(bone);
      if (BONE_PARENT[i] >= 0) this.bones[BONE_PARENT[i]].add(bone);
    }
    this.skeleton = new THREE.Skeleton(
      this.bones,
      this.bones.map(() => new THREE.Matrix4())
    );

    this.mesh = new THREE.SkinnedMesh(geometry, this.material);
    this.mesh.castShadow = true;
    this.mesh.receiveShadow = true;
    // The bounding volume is for the rest pose of one profile; never cull.
    this.mesh.frustumCulled = false;
    this.mesh.bind(this.skeleton, new THREE.Matrix4());
    this.actor.add(this.bones[BONE.HIPS], this.mesh);

    this.hair = new HairSet(PLAYERS);
    this.bones[BONE.HEAD].add(this.hair.group, this.face);
    this.buildFace();
  }

  /** Two eyes and a nose: enough to read which way the head faces, nothing more. */
  private buildFace() {
    const dark = new THREE.MeshStandardMaterial({ color: "#12151c", roughness: 0.4 });
    const eye = new THREE.SphereGeometry(0.085, 10, 8);
    this.faceParts.push(dark, eye);
    for (const x of [-0.36, 0.36]) {
      const m = new THREE.Mesh(eye, dark);
      m.position.set(x, 0.12, 0.9);
      m.scale.set(1.25, 0.7, 0.5);
      this.face.add(m);
    }
    const noseGeo = new THREE.ConeGeometry(0.11, 0.34, 6);
    const noseMat = new THREE.MeshStandardMaterial({ roughness: 0.8 });
    this.faceParts.push(noseGeo, noseMat);
    const nose = new THREE.Mesh(noseGeo, noseMat);
    nose.name = "nose";
    nose.position.set(0, -0.08, 1.02);
    nose.rotation.x = 0.35;
    this.face.add(nose);
  }

  update(id: Identity, motion: Motion) {
    const la = this.layouts[id.a];
    const lb = this.layouts[id.b];
    const t = id.t;
    const pa = PLAYERS[id.a];
    const pb = PLAYERS[id.b];

    // ── Body: morph targets (index 0 of the influences is profile 1) ────────
    const inf = this.mesh.morphTargetInfluences!;
    inf.fill(0);
    if (id.a > 0) inf[id.a - 1] += 1 - t;
    if (id.b > 0) inf[id.b - 1] += t;

    // ── Skeleton: joints follow the same blend ──────────────────────────────
    const j = this.joints;
    for (let i = 0; i < j.length; i++) j[i] = lerp(la.joints[i], lb.joints[i], t);
    for (let i = 0; i < BONE_COUNT; i++) {
      const p = BONE_PARENT[i];
      const bone = this.bones[i];
      if (p < 0) bone.position.set(j[0], j[1], j[2]);
      else bone.position.set(j[i * 3] - j[p * 3], j[i * 3 + 1] - j[p * 3 + 1], j[i * 3 + 2] - j[p * 3 + 2]);
      // The rest pose has no rotation, so the inverse bind matrix is just the
      // joint's position negated. Rebuilt every frame because the joints move.
      this.skeleton.boneInverses[i].makeTranslation(-j[i * 3], -j[i * 3 + 1], -j[i * 3 + 2]);
    }

    // ── Pose ────────────────────────────────────────────────────────────────
    lerpStride(pa.stride, pb.stride, t, this.stride);
    computePose(motion, this.stride, this.pose);
    for (let i = 0; i < BONE_COUNT; i++) {
      this.bones[i].rotation.set(this.pose[i * 3], this.pose[i * 3 + 1], this.pose[i * 3 + 2]);
    }

    // Stand the figure on the grass: find the lowest point of either boot and
    // move the hips so it sits at the requested height.
    const ankle = lerp(la.ankle, lb.ankle, t);
    const heel = lerp(la.heel, lb.heel, t);
    const toe = lerp(la.toe, lb.toe, t);
    this.actor.updateMatrixWorld(true);
    let lowest = Infinity;
    for (const foot of [this.bones[BONE.FOOT_L], this.bones[BONE.FOOT_R]]) {
      for (const z of [heel, toe]) {
        const y = this.tmp.set(0, -ankle, z).applyMatrix4(foot.matrixWorld).y;
        if (y < lowest) lowest = y;
      }
    }
    this.bones[BONE.HIPS].position.y += motion.air - (lowest - this.actor.position.y);
    if (motion.bike > 0) {
      // The kick sets the pelvis height itself (see the realistic rig).
      this.actor.updateMatrixWorld(true);
      const now = this.tmp.setFromMatrixPosition(this.bones[BONE.HIPS].matrixWorld).y - this.actor.position.y;
      this.bones[BONE.HIPS].position.y += (motion.bikeHip - now) * motion.bike;
    }

    // ── Head attachments ────────────────────────────────────────────────────
    const hx = lerp(la.head[0], lb.head[0], t);
    const hy = lerp(la.head[1], lb.head[1], t);
    const hz = lerp(la.head[2], lb.head[2], t);
    const headY = lerp(la.headCenterY, lb.headCenterY, t) - j[BONE.HEAD * 3 + 1];
    this.hair.group.position.set(0, headY, 0);
    this.hair.group.scale.set(hx, hy, hz);
    this.face.position.set(0, headY, 0);
    this.face.scale.set(hx, hy, hz);

    // Hair is a swap: the old piece is gone before the new one arrives.
    for (let i = 0; i < PLAYERS.length; i++) {
      let presence = 0;
      if (id.a === id.b) presence = i === id.a ? 1 : 0;
      else if (i === id.a) presence = 1 - smoothstep(0.08, 0.5, t);
      else if (i === id.b) presence = smoothstep(0.5, 0.92, t);
      this.hair.setPresence(i, presence);
    }

    // ── Kit and skin ────────────────────────────────────────────────────────
    this.material.setBlend(pa.kit, pb.kit, pa.skin, pb.skin, t);
    const nose = this.face.getObjectByName("nose") as THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>;
    nose.material.color.set(pa.skin).lerp(this.rimB.set(pb.skin), t).multiplyScalar(0.92);
    this.rim.set(pa.kit.rim).lerp(this.rimB.set(pb.kit.rim), t);
  }

  /** Numbers for the debug hook and the determinism check. */
  snapshot() {
    const head = this.tmp.setFromMatrixPosition(this.bones[BONE.HEAD].matrixWorld);
    return { headY: head.y, hipsY: this.bones[BONE.HIPS].position.y, morph: Array.from(this.mesh.morphTargetInfluences!) };
  }

  dispose() {
    this.mesh.geometry.dispose();
    this.material.dispose();
    this.skeleton.dispose();
    this.hair.dispose();
    for (const d of this.faceParts) d.dispose();
  }
}
