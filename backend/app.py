"""
app.py — Step 1: the upload + session API.

Deliberately does NOT call SMPL/STAR yet. Its job is to:
  1. Accept the 3 patient photos (front/side/back)
  2. Validate them
  3. Create a Mongo session doc
  4. Leave a hook for the mesh-generation job (wired up in the next step)
  5. Serve session status + sculpt-history read/write to the frontend

Run: python app.py
"""

import os
import uuid
from typing import Literal
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

import models
import worker

app = Flask(__name__)
CORS(app)  # dev only — lock this down to the real frontend origin before production

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_CONTENT_LENGTH = 15 * 1024 * 1024  # 15MB per request
UPLOAD_DIR = "/tmp/body_sim_uploads"  # swap for S3/GridFS in production

app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
os.makedirs(UPLOAD_DIR, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/api/sessions", methods=["POST"])
def create_session():
    """
    multipart/form-data body:
      patient_id: str
      front: file
      side: file
      back: file
    """
    patient_id = request.form.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id is required"}), 400

    required_views: tuple[Literal["front", "side", "back"], ...] = ("front", "side", "back")
    for view in required_views:
        if view not in request.files:
            return jsonify({"error": f"missing '{view}' image"}), 400
        f = request.files[view]
        filename = f.filename
        if not filename or not allowed_file(filename):
            return jsonify({"error": f"invalid file for '{view}'"}), 400

    session_id = models.create_session(patient_id)

    for view in required_views:
        f = request.files[view]
        filename = f.filename
        if not filename:
            return jsonify({"error": f"invalid file for '{view}'"}), 400
        ext = filename.rsplit(".", 1)[1].lower()
        stored_name = f"{session_id}_{view}_{uuid.uuid4().hex[:8]}.{ext}"
        stored_path = os.path.join(UPLOAD_DIR, secure_filename(stored_name))
        f.save(stored_path)

        # TODO (later step): real de-identification — crop/blur above the
        # shoulders — before this ever leaves local disk / hits S3.
        # TODO (later step): swap local path for actual S3/GridFS upload.
        models.set_source_image(session_id, view, stored_path)

    models.mark_processing(session_id)
    worker.enqueue_mesh_job(session_id)
    # TODO (later): swap worker.run_mesh_generation_job's internals for the
    # real SMPL/STAR pipeline once the fitting spike lands — nothing here
    # or in the frontend needs to change when that happens.

    return jsonify({"session_id": session_id, "status": "processing"}), 202


@app.route("/api/mesh/<path:filename>", methods=["GET"])
def get_mesh_file(filename):
    mesh_dir = os.path.join(os.path.dirname(__file__), "meshes")
    return send_from_directory(mesh_dir, filename)


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session_status(session_id):
    doc = models.get_session(session_id)
    if not doc:
        return jsonify({"error": "not found"}), 404
    return jsonify(doc), 200


@app.route("/api/sessions/<session_id>/sculpt", methods=["POST"])
def add_sculpt_operation(session_id):
    """
    JSON body:
      {
        "region_label": "left_glute",
        "center_local": [x, y, z],
        "radius": 0.08,
        "delta_cc": 150,
        "falloff": "smoothstep",
        "surgeon_id": "dr_okafor"
      }
    """
    doc = models.get_session(session_id)
    if not doc:
        return jsonify({"error": "not found"}), 404

    body = request.get_json(force=True)
    required_fields = ["region_label", "center_local", "radius", "delta_cc", "surgeon_id"]
    missing = [f for f in required_fields if f not in body]
    if missing:
        return jsonify({"error": f"missing fields: {missing}"}), 400

    op = {
        "op_id": uuid.uuid4().hex,
        "region_label": body["region_label"],
        "center_local": body["center_local"],
        "radius": body["radius"],
        "delta_cc": body["delta_cc"],
        "falloff": body.get("falloff", "smoothstep"),
        "surgeon_id": body["surgeon_id"],
    }
    models.append_sculpt_op(session_id, op)
    return jsonify({"status": "recorded", "op": op}), 201


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)