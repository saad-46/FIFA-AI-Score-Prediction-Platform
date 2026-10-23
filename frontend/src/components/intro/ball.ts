import * as THREE from "three";

export const BALL_RADIUS = 0.11;

/** The twelve vertices of an icosahedron: where the dark panels sit. */
function panelCentres(): THREE.Vector3[] {
  const t = (1 + Math.sqrt(5)) / 2;
  const raw = [
    [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
    [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
    [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1],
  ];
  return raw.map(([x, y, z]) => new THREE.Vector3(x, y, z).normalize());
}

/** A football with a procedural panel pattern. No texture, no external asset. */
export function createBall(): { mesh: THREE.Mesh; dispose(): void } {
  const geometry = new THREE.SphereGeometry(BALL_RADIUS, 32, 20);
  const material = new THREE.MeshStandardMaterial({ color: "#f3f5f8", roughness: 0.42, metalness: 0 });
  const centres = { value: panelCentres() };
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uPanels = centres;
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vBallN;")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\nvBallN = normalize(position);");
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vBallN;\nuniform vec3 uPanels[12];")
      .replace(
        "#include <color_fragment>",
        /* glsl */ `#include <color_fragment>
vec3 bn = normalize(vBallN);
float nearest = 0.0;
float second = 0.0;
for (int i = 0; i < 12; i++) {
  float d = dot(bn, uPanels[i]);
  if (d > nearest) { second = nearest; nearest = d; } else if (d > second) { second = d; }
}
float panel = smoothstep(0.928, 0.936, nearest);
// Thin seams where two panel regions meet.
float seam = 1.0 - smoothstep(0.0, 0.012, nearest - second);
diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.05, 0.06, 0.08), max(panel, seam * 0.55));`
      );
  };
  material.customProgramCacheKey = () => "intro-ball-v1";
  const mesh = new THREE.Mesh(geometry, material);
  mesh.castShadow = true;
  // Never culled: the first frame the ball enters the key light's shadow frustum
  // would otherwise compile a new shadow-depth program, a stall mid-scroll.
  mesh.frustumCulled = false;
  return {
    mesh,
    dispose() {
      geometry.dispose();
      material.dispose();
    },
  };
}
