"""问卷 CRUD / 发布 / 公开链接"""
from flask import Blueprint, request, jsonify, session
from bson import ObjectId
from datetime import datetime, timezone
import secrets

from app.db import get_db

bp = Blueprint("surveys", __name__)


def _require_user():
    uid = session.get("user_id")
    if not uid:
        return None
    try:
        return ObjectId(uid)
    except Exception:
        return None


def _now():
    return datetime.now(timezone.utc)


def _survey_public(s, include_token=True):
    out = {
        "id": str(s["_id"]),
        "title": s.get("title"),
        "description": s.get("description", ""),
        "status": s.get("status"),
        "created_at": s.get("created_at"),
        "updated_at": s.get("updated_at"),
        "published_at": s.get("published_at"),
        "allow_anonymous": s.get("allow_anonymous", True),
        "deadline": s.get("deadline"),
    }
    if include_token:
        out["public_token"] = s.get("public_token")
        if s.get("public_token"):
            out["fill_url"] = f"/fill/{s['public_token']}"
            out["survey_path"] = f"/survey/{s['public_token']}"
    return out


@bp.get("/")
def list_surveys():
    owner = _require_user()
    if not owner:
        return jsonify({"error": "login required"}), 401
    db = get_db()
    items = [_survey_public(s) for s in db.surveys.find({"owner_id": owner}).sort("updated_at", -1)]
    return jsonify({"surveys": items})


@bp.post("/")
def create_survey():
    owner = _require_user()
    if not owner:
        return jsonify({"error": "login required"}), 401
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    description = (data.get("description") or "").strip()
    now = _now()
    doc = {
        "owner_id": owner,
        "title": title,
        "description": description,
        "status": "draft",
        "public_token": None,
        "allow_anonymous": bool(data.get("allow_anonymous", True)),
        "deadline": data.get("deadline"),  # ISO 字符串或 null
        "created_at": now,
        "updated_at": now,
        "published_at": None,
    }
    db = get_db()
    res = db.surveys.insert_one(doc)
    doc["_id"] = res.inserted_id
    return jsonify({"survey": _survey_public(doc)}), 201


@bp.get("/<survey_id>")
def get_survey(survey_id):
    owner = _require_user()
    if not owner:
        return jsonify({"error": "login required"}), 401
    try:
        sid = ObjectId(survey_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    db = get_db()
    s = db.surveys.find_one({"_id": sid, "owner_id": owner})
    if not s:
        return jsonify({"error": "not found"}), 404
    questions = list(db.questions.find({"survey_id": sid}).sort("order", 1))
    q_out = []
    for q in questions:
        q_out.append({
            "id": str(q["_id"]),
            "order": q.get("order"),
            "type": q.get("type"),
            "title": q.get("title"),
            "required": q.get("required", False),
            "options": q.get("options", []),
            "validation": q.get("validation", {}),
            "jump_rules": [
                {
                    "when_value": r.get("when_value"),
                    "goto_question_id": (
                        str(r["goto_question_id"])
                        if r.get("goto_question_id") not in (None, "end")
                        else r.get("goto_question_id")
                    ),
                }
                for r in q.get("jump_rules", [])
            ],
        })
    return jsonify({"survey": _survey_public(s), "questions": q_out})


@bp.patch("/<survey_id>")
def update_survey(survey_id):
    owner = _require_user()
    if not owner:
        return jsonify({"error": "login required"}), 401
    try:
        sid = ObjectId(survey_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    data = request.get_json(silent=True) or {}
    db = get_db()
    s = db.surveys.find_one({"_id": sid, "owner_id": owner})
    if not s:
        return jsonify({"error": "not found"}), 404
    updates = {"updated_at": _now()}
    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title required"}), 400
        updates["title"] = title
    if "description" in data:
        updates["description"] = (data.get("description") or "").strip()
    if "allow_anonymous" in data:
        updates["allow_anonymous"] = bool(data.get("allow_anonymous"))
    if "deadline" in data:
        updates["deadline"] = data.get("deadline") or None
    db.surveys.update_one({"_id": sid}, {"$set": updates})
    s = db.surveys.find_one({"_id": sid})
    return jsonify({"survey": _survey_public(s)})


@bp.delete("/<survey_id>")
def delete_survey(survey_id):
    owner = _require_user()
    if not owner:
        return jsonify({"error": "login required"}), 401
    try:
        sid = ObjectId(survey_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    db = get_db()
    s = db.surveys.find_one({"_id": sid, "owner_id": owner})
    if not s:
        return jsonify({"error": "not found"}), 404
    db.questions.delete_many({"survey_id": sid})
    db.responses.delete_many({"survey_id": sid})
    db.surveys.delete_one({"_id": sid})
    return jsonify({"ok": True})


@bp.post("/<survey_id>/publish")
def publish_survey(survey_id):
    owner = _require_user()
    if not owner:
        return jsonify({"error": "login required"}), 401
    try:
        sid = ObjectId(survey_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    db = get_db()
    s = db.surveys.find_one({"_id": sid, "owner_id": owner})
    if not s:
        return jsonify({"error": "not found"}), 404
    qcount = db.questions.count_documents({"survey_id": sid})
    if qcount == 0:
        return jsonify({"error": "cannot publish empty survey"}), 400
    token = s.get("public_token") or secrets.token_urlsafe(12)
    now = _now()
    db.surveys.update_one(
        {"_id": sid},
        {"$set": {
            "status": "published",
            "public_token": token,
            "published_at": now,
            "updated_at": now,
        }},
    )
    # 阶段二：已发布问卷中的题目冻结，避免就地修改影响已收集数据语义
    db.questions.update_many({"survey_id": sid}, {"$set": {"frozen": True}})
    s = db.surveys.find_one({"_id": sid})
    return jsonify({"survey": _survey_public(s)})


@bp.post("/<survey_id>/close")
def close_survey(survey_id):
    owner = _require_user()
    if not owner:
        return jsonify({"error": "login required"}), 401
    try:
        sid = ObjectId(survey_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    db = get_db()
    s = db.surveys.find_one({"_id": sid, "owner_id": owner})
    if not s:
        return jsonify({"error": "not found"}), 404
    db.surveys.update_one(
        {"_id": sid},
        {"$set": {"status": "closed", "updated_at": _now()}},
    )
    s = db.surveys.find_one({"_id": sid})
    return jsonify({"survey": _survey_public(s)})


@bp.post("/<survey_id>/reopen")
def reopen_survey(survey_id):
    """重新发布已关闭问卷（沿用原 public_token）"""
    owner = _require_user()
    if not owner:
        return jsonify({"error": "login required"}), 401
    try:
        sid = ObjectId(survey_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    db = get_db()
    s = db.surveys.find_one({"_id": sid, "owner_id": owner})
    if not s:
        return jsonify({"error": "not found"}), 404
    if not s.get("public_token"):
        return jsonify({"error": "never published"}), 400
    db.surveys.update_one(
        {"_id": sid},
        {"$set": {"status": "published", "updated_at": _now()}},
    )
    s = db.surveys.find_one({"_id": sid})
    return jsonify({"survey": _survey_public(s)})
