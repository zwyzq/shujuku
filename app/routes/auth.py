from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from bson import ObjectId

from app.db import get_db

bp = Blueprint("auth", __name__)


def _user_public(u):
    return {
        "id": str(u["_id"]),
        "username": u["username"],
        "email": u.get("email"),
        "created_at": u.get("created_at"),
    }


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    email = (data.get("email") or "").strip()

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if len(password) < 6:
        return jsonify({"error": "password too short"}), 400

    db = get_db()
    if db.users.find_one({"username": username}):
        return jsonify({"error": "username taken"}), 409

    doc = {
        "username": username,
        "password_hash": generate_password_hash(password),
        "email": email,
        "created_at": datetime.now(timezone.utc),
    }
    res = db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    session["user_id"] = str(res.inserted_id)
    return jsonify({"user": _user_public(doc)}), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    db = get_db()
    u = db.users.find_one({"username": username})
    if not u or not check_password_hash(u["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    session["user_id"] = str(u["_id"])
    return jsonify({"user": _user_public(u)})


@bp.post("/logout")
def logout():
    session.pop("user_id", None)
    return jsonify({"ok": True})


@bp.get("/me")
def me():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"user": None})
    db = get_db()
    u = db.users.find_one({"_id": ObjectId(uid)})
    if not u:
        session.pop("user_id", None)
        return jsonify({"user": None})
    return jsonify({"user": _user_public(u)})
