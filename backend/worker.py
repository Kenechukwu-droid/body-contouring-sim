"""
worker.py — Step 2: fake mesh-generation job.

Simulates what the real SMPL/STAR pipeline will eventually do:
  1. pose/keypoint detection per view
  2. silhouette segmentation
  3. SMPL/STAR beta+theta regression
  4. multi-view fusion across front/side/back
  5. .gltf export

For now: sleep briefly to simulate processing time, pick a placeholder
mesh, and call models.save_mesh_result() with made-up SMPL params. This
exercises the full status -> mesh_url -> smpl_params contract so the
frontend can be built and tested against something real today.

When the SMPL spike lands, only run_mesh_generation_job()'s internals
change — its signature and what it calls in models.py stay identical.
"""

import time
import random
import threading

import models

PLACEHOLDER_MESHES = ["sample_average.gltf", "sample_fuller.gltf"]


def enqueue_mesh_job(session_id: str):
    """Fire-and-forget background thread. A real deployment would use
    Celery/RQ instead of a bare thread — this is fine for local dev."""
    thread = threading.Thread(target=run_mesh_generation_job, args=(session_id,), daemon=True)
    thread.start()


def run_mesh_generation_job(session_id: str):
    try:
        time.sleep(3)  # simulate regression + export time

        chosen_mesh = random.choice(PLACEHOLDER_MESHES)
        fake_beta = [round(random.uniform(-2, 2), 3) for _ in range(10)]

        models.save_mesh_result(
            session_id,
            smpl_params={"beta": fake_beta, "theta": None, "gender": "unspecified"},
            mesh_url=f"/api/mesh/{chosen_mesh}",
        )
    except Exception as e:
        models.mark_failed(session_id, str(e))