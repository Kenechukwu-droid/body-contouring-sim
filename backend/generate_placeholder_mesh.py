"""
generate_placeholder_mesh.py

Produces a rough humanoid mesh (capsules for torso/limbs, sphere for head)
and exports it as .gltf. NOT anatomically accurate — exists purely so the
Three.js viewer and sculpting tool can be built against a real mesh file
before the SMPL/STAR fitting spike lands.

When the real pipeline exists, worker.py calls that instead of this file,
and nothing about app.py, models.py, or the frontend contract changes:
the session doc still gets a mesh_url and smpl_params, same shape either way.

Usage:
    python generate_placeholder_mesh.py --out meshes/sample_average.gltf --variant average
"""

import argparse
from typing import cast

import numpy as np
import trimesh
from trimesh.visual.color import ColorVisuals


def build_body(scale=1.0):
    parts = []

    torso = trimesh.creation.capsule(radius=0.18 * scale, height=0.5, count=[32, 32])
    torso.apply_translation([0, 1.1, 0])
    parts.append(torso)

    head = trimesh.creation.icosphere(subdivisions=3, radius=0.12)
    head.apply_translation([0, 1.75, 0])
    parts.append(head)

    hips = trimesh.creation.capsule(radius=0.20 * scale, height=0.25, count=[32, 32])
    hips.apply_translation([0, 0.85, 0])
    parts.append(hips)

    for side in (-1, 1):
        upper_arm = trimesh.creation.capsule(radius=0.05, height=0.35, count=[16, 16])
        upper_arm.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.1, [0, 0, 1]))
        upper_arm.apply_translation([side * 0.32, 1.25, 0])
        parts.append(upper_arm)

    for side in (-1, 1):
        leg = trimesh.creation.capsule(radius=0.09, height=0.75, count=[24, 24])
        leg.apply_translation([side * 0.12, 0.35, 0])
        parts.append(leg)

    body = cast(trimesh.Trimesh, trimesh.util.concatenate(parts))
    body.visual = ColorVisuals(
        mesh=body, vertex_colors=[232, 184, 156, 255]
    )
    return body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--variant", default="average", choices=["average", "fuller", "athletic"])
    args = parser.parse_args()

    scale = {"average": 1.0, "fuller": 1.15, "athletic": 0.92}[args.variant]
    mesh = build_body(scale=scale)
    mesh.export(args.out)
    print(f"Exported -> {args.out}  ({len(mesh.vertices)} verts, {len(mesh.faces)} faces)")


if __name__ == "__main__":
    main()