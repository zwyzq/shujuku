from flask import Blueprint, jsonify
from app.db import get_db

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health():
    db = get_db()
    # ping
    db.command("ping")
    cols = db.list_collection_names()
    return jsonify({
        "ok": True,
        "db": db.name,
        "collections": sorted(cols),
    })
