import * as THREE from "three";
import type { BeardId, HairId, PlayerProfile } from "../profiles";
import { NOISE_GLSL } from "./kit-material";

/**
 * Hair and beards.
 *
 * These are separate meshes parented to the head bone, modelled for a head of
 * radius 1 and scaled to the current head. Unlike the body they are NOT
 * interpolated: one piece dissolves out and the next dissolves in, timed to
 * sit inside the move that hides the morph. It is a swap, and is described as
 * one.
 */

class DissolveMaterial extends THREE.MeshStandardMaterial {
  private readonly uDissolve = { value: 0 };

  constructor(color: string) {
    super({ color, roughness: 0.9, metalness: 0, side: THREE.DoubleSide });
    this.onBeforeCompile = (shader) => {
      shader.uniforms.uDissolve = this.uDissolve;
      shader.vertexShader = shader.vertexShader
        .replace("#include <common>", "#include <common>\nvarying vec3 vHairPos;")
        .replace("#include <begin_vertex>", "#include <begin_vertex>\nvHairPos = position;");
      shader.fragmentShader = shader.fragmentShader
        .replace("#include <common>", `#include <common>\nvarying vec3 vHairPos;\nuniform float uDissolve;\nfloat introEdge;\n${NOISE_GLSL}`)
        .replace(
          "#include <color_fragment>",
          /* glsl */ `#include <color_fragment>
float n = introNoise(vHairPos * 9.0);
float cut = uDissolve * 1.15 - 0.075;
if (n < cut) discard;
introEdge = step(0.001, uDissolve) * (1.0 - smoothstep(0.0, 0.07, n - cut));`
        )
        .replace("#include <emissivemap_fragment>", "#include <emissivemap_fragment>\ntotalEmissiveRadiance += vec3(0.75, 0.95, 1.0) * introEdge * 1.4;");
    };
    this.customProgramCacheKey = () => "intro-hair-v1";
  }

  /** 0 fully present, 1 fully gone. */
  set dissolve(v: number) {
    this.uDissolve.value = v;
  }
}

function shortHair(): THREE.BufferGeometry {
  const g = new THREE.SphereGeometry(1.07, 22, 10, 0, Math.PI * 2, 0, Math.PI * 0.5);
  g.rotateX(-0.32);
  g.translate(0, 0.02, -0.02);
  return g;
}

function buzzedSides(): THREE.BufferGeometry {
  const g = new THREE.SphereGeometry(1.03, 22, 8, 0, Math.PI * 2, 0, Math.PI * 0.46);
  g.rotateX(-0.36);
  return g;
}

function mohawkCrest(): THREE.BufferGeometry {
  const g = new THREE.SphereGeometry(1, 16, 10, 0, Math.PI * 2, 0, Math.PI * 0.56);
  g.scale(0.24, 1.3, 1.08);
  g.rotateX(-0.22);
  g.translate(0, 0.04, -0.05);
  return g;
}

function shortBeard(): THREE.BufferGeometry {
  // SphereGeometry puts +Z at phi = PI/2; this is the band around the jaw.
  const g = new THREE.SphereGeometry(1.0, 20, 6, Math.PI / 2 - 1.75, 3.5, Math.PI * 0.6, Math.PI * 0.3);
  g.scale(0.9, 1.02, 1.02);
  g.translate(0, 0.02, 0.07);
  return g;
}

const HAIR: Record<HairId, () => THREE.BufferGeometry[]> = {
  short: () => [shortHair()],
  mohawk: () => [buzzedSides(), mohawkCrest()],
};
const BEARD: Record<BeardId, () => THREE.BufferGeometry[]> = {
  none: () => [],
  short: () => [shortBeard()],
};

export class HairSet {
  readonly group = new THREE.Group();
  private readonly perPlayer: { root: THREE.Group; material: DissolveMaterial }[] = [];
  private readonly disposables: { dispose(): void }[] = [];

  constructor(players: readonly PlayerProfile[]) {
    for (const p of players) {
      const root = new THREE.Group();
      const material = new DissolveMaterial(p.hairColor);
      this.disposables.push(material);
      for (const geo of [...HAIR[p.hair](), ...BEARD[p.beard]()]) {
        this.disposables.push(geo);
        const mesh = new THREE.Mesh(geo, material);
        mesh.castShadow = true;
        root.add(mesh);
      }
      this.group.add(root);
      this.perPlayer.push({ root, material });
    }
  }

  /** `presence[i]` is 1 when player i's hair is fully there, 0 when gone. */
  setPresence(index: number, presence: number) {
    const entry = this.perPlayer[index];
    entry.root.visible = presence > 0.002;
    entry.material.dissolve = 1 - presence;
    entry.root.scale.setScalar(0.9 + 0.1 * presence);
  }

  dispose() {
    for (const d of this.disposables) d.dispose();
  }
}
