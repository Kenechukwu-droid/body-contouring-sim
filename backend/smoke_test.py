"""
smoke_test.py — verifies app.py + models.py work end-to-end using
mongomock (no real MongoDB needed for this check). Swap mongomock for
the real pymongo client via MONGO_URI when you have Mongo running.

Run: python smoke_test.py
"""

import io
import time
import mongomock

import models
models._client = mongomock.MongoClient()

import app as flask_app  # noqa: E402

client = flask_app.app.test_client()


def make_image_bytes():
    return io.BytesIO(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
        b"\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def run():
    print("1. POST /api/sessions ...")
    resp = client.post(
        "/api/sessions",
        data={
            "patient_id": "patient_001",
            "front": (make_image_bytes(), "front.png"),
            "side": (make_image_bytes(), "side.png"),
            "back": (make_image_bytes(), "back.png"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 202, resp.get_data(as_text=True)
    session_id = resp.get_json()["session_id"]
    print(f"   OK -> session_id={session_id}, status={resp.get_json()['status']}")

    print("2. GET /api/sessions/<id> ...")
    resp = client.get(f"/api/sessions/{session_id}")
    doc = resp.get_json()
    assert doc["status"] == "processing" and doc["mesh_url"] is None
    print(f"   OK -> status={doc['status']}")

    print("2b. Waiting for the fake worker to finish (~3s) ...")
    time.sleep(3.5)
    resp = client.get(f"/api/sessions/{session_id}")
    doc = resp.get_json()
    assert doc["status"] == "ready", doc
    assert doc["mesh_url"] is not None
    assert doc["smpl_params"] is not None
    print(f"   OK -> status={doc['status']}, mesh_url={doc['mesh_url']}")

    print("2c. GET the mesh file itself ...")
    resp = client.get(doc["mesh_url"])
    assert resp.status_code == 200, resp.status_code
    print(f"   OK -> {len(resp.data)} bytes served")

    print("3. Missing patient_id -> 400 ...")
    resp = client.post("/api/sessions", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    print(f"   OK -> {resp.get_json()}")

    print("4. Unknown session -> 404 ...")
    resp = client.get("/api/sessions/000000000000000000000000")
    assert resp.status_code == 404
    print("   OK")

    print("5. POST sculpt op ...")
    resp = client.post(
        f"/api/sessions/{session_id}/sculpt",
        json={
            "region_label": "left_glute", "center_local": [0.15, 0.85, 0.05],
            "radius": 0.08, "delta_cc": 150, "surgeon_id": "dr_okafor",
        },
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    print(f"   OK -> {resp.get_json()['status']}")

    print("\nAll checks passed.")


if __name__ == "__main__":
    run()