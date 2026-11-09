"""
models.py — MongoDB data access for the body-contouring simulator.

One collection: `sessions`. This file is the single source of truth for
what a session document looks like. No Flask dependency here on purpose —
the future SMPL worker will import this same module.
"""

import os
from datetime import datetime, timezone
from typing import Optional, Literal
from pymongo.collection import Collection
from bson import ObjectId

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "body_contouring_sim"

# Local-dev escape hatch: set USE_MOCK_DB=1 to run against an in-memory
# fake instead of a real MongoDB. Useful before you've installed Mongo
# locally. Data does NOT persist across process restarts in this mode.
USE_MOCK_DB = os.environ.get("USE_MOCK_DB", "0") == "1"

_client = None


def get_db():
    global _client
    if _client is None:
        if USE_MOCK_DB:
            import mongomock
            _client = mongomock.MongoClient()
        else:
            from pymongo import MongoClient
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    return _client[DB_NAME]


def sessions_collection() -> Collection:
    return get_db()["sessions"]


# ---------------------------------------------------------------------------
# Document shape (Mongo is schemaless — this comment is the real contract)
# ---------------------------------------------------------------------------
#
# {
#   "_id": ObjectId,
#   "patient_id": str,
#   "created_at": datetime,
#   "updated_at": datetime,
#   "status": "uploaded" | "processing" | "ready" | "failed",
#   "source_images": { "front": str, "side": str, "back": str },
#   "smpl_params": { "beta": [float], "theta": [float] | None, "gender": str } | None,
#   "mesh_url": str | None,
#   "sculpt_history": [ { op_id, region_label, center_local, radius,
#                          delta_cc, falloff, surgeon_id, timestamp } ],
#   "error": str | None,
# }


def create_session(patient_id: str) -> str:
    doc = {
        "patient_id": patient_id,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "status": "uploaded",
        "source_images": {},
        "smpl_params": None,
        "mesh_url": None,
        "sculpt_history": [],
        "error": None,
    }
    result = sessions_collection().insert_one(doc)
    return str(result.inserted_id)


def set_source_image(session_id: str, view: Literal["front", "side", "back"], stored_path: str):
    sessions_collection().update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {f"source_images.{view}": stored_path, "updated_at": datetime.now(timezone.utc)}},
    )


def mark_processing(session_id: str):
    sessions_collection().update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"status": "processing", "updated_at": datetime.now(timezone.utc)}},
    )


def save_mesh_result(session_id: str, smpl_params: dict, mesh_url: str):
    sessions_collection().update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {
            "status": "ready",
            "smpl_params": smpl_params,
            "mesh_url": mesh_url,
            "updated_at": datetime.now(timezone.utc),
        }},
    )


def mark_failed(session_id: str, error: str):
    sessions_collection().update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"status": "failed", "error": error, "updated_at": datetime.now(timezone.utc)}},
    )


def append_sculpt_op(session_id: str, op: dict):
    op["timestamp"] = datetime.now(timezone.utc)
    sessions_collection().update_one(
        {"_id": ObjectId(session_id)},
        {"$push": {"sculpt_history": op}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )


def get_session(session_id: str) -> Optional[dict]:
    doc = sessions_collection().find_one({"_id": ObjectId(session_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc