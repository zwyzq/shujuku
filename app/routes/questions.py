"""题目 CRUD + 跳转/校验字段"""
from flask import Blueprint, request, jsonify, session
from bson import ObjectId
from datetime import datetime, timezone

from app.db import get_db

bp = Blueprint("questions", __name__)

ALLOWED_TYPES = {"single", "multiple", "text", "number", "rating", "date"}


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


def _get_owned_survey(db, survey_id, owner):
    try:
        sid = ObjectId(survey_id)
    except Exception:
        return None, None
    s = db.surveys.find_one({"_id": sid, "owner_id": owner})
    return sid, s


def _q_out(q):
    return {
        "id": str(q["_id"]),
        "survey_id": str(q["survey_id"]),
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
        "created_at": q.get("created_at"),
    }


def _normalize_jump_rules(raw):
    rules = []
    for r in raw or []:
        goto = r.get("goto_question_id")
        if goto not in (None, "end"):
            try:
                goto = ObjectId(goto)
            except Exception:
                raise ValueError("invalid goto_question_id")
        rules.append({"when_value": r.get("when_value"), "goto_question_id": goto})
    return rules


@bp.post("/api/surveys/<survey_id>/questions")
def create_question(survey_id):
    owner = _require_user()
    if not owner:
        return jsonify({"error": "login required"}), 401
    db = get_db()
    sid, s = _get_owned_survey(db, survey_id, owner)
    if not s:
        return jsonify({"error": "not found"}), 404

    data = request.get_json(silent=True) or {}
    qtype = data.get("type")
    title = (data.get("title") or "").strip()
    if qtype not in ALLOWED_TYPES:
        return jsonify({"error": f"type must be one of {sorted(ALLOWED_TYPES)}"}), 400
    if not title:
        return jsonify({"error": "title required"}), 400
    if qtype in ("single", "multiple", "rating") and not data.get("options"):
        return jsonify({"error": "options required for this type"}), 400

    try:
        jump_rules = _normalize_jump_rules(data.get("jump_rules"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    last = db.questions.find_one({"survey_id": sid}, sort=[("order", -1)])
    order = data.get("order")
    if order is None:
        order = (last["order"] + 1) if last else 1

    doc = {
        "survey_id": sid,
        "order": int(order),
        "type": qtype,
        "title": title,
        "required": bool(data.get("required", False)),
        "options": data.get("options") or [],
        "validation": data.get("validation") or {},
        "jump_rules": jump_rules,
        "created_at": _now(),
    }
    res = db.questions.insert_one(doc)
    doc["_id"] = res.inserted_id
    db.surveys.update_one({"_id": sid}, {"$set": {"updated_at": _now()}})
    return jsonify({"question": _q_out(doc)}), 201


@bp.patch("/api/questions/<question_id>")
def update_question(question_id):
    owner = _require_user()
    if not owner:
        return jsonify({"error": "login required"}), 401
    try:
        qid = ObjectId(question_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    db = get_db()
    q = db.questions.find_one({"_id": qid})
    if not q:
        return jsonify({"error": "not found"}), 404
    s = db.surveys.find_one({"_id": q["survey_id"], "owner_id": owner})
    if not s:
        return jsonify({"error": "not found"}), 404
    if q.get("frozen") or s.get("status") == "published":
        return jsonify({
            "error": "published or frozen question cannot be edited in place; create a new bank version and re-add"
        }), 409

    data = request.get_json(silent=True) or {}
    updates = {}
    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title required"}), 400
        updates["title"] = title
    if "type" in data:
        if data["type"] not in ALLOWED_TYPES:
            return jsonify({"error": "invalid type"}), 400
        updates["type"] = data["type"]
    if "required" in data:
        updates["required"] = bool(data["required"])
    if "options" in data:
        updates["options"] = data["options"] or []
    if "validation" in data:
        updates["validation"] = data["validation"] or {}
    if "order" in data:
        updates["order"] = int(data["order"])
    if "jump_rules" in data:
        try:
            updates["jump_rules"] = _normalize_jump_rules(data.get("jump_rules"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    if not updates:
        return jsonify({"error": "nothing to update"}), 400

    db.questions.update_one({"_id": qid}, {"$set": updates})
    db.surveys.update_one({"_id": q["survey_id"]}, {"$set": {"updated_at": _now()}})
    q = db.questions.find_one({"_id": qid})
    return jsonify({"question": _q_out(q)})


@bp.delete("/api/questions/<question_id>")
def delete_question(question_id):
    owner = _require_user()
    if not owner:
        return jsonify({"error": "login required"}), 401
    try:
        qid = ObjectId(question_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    db = get_db()
    q = db.questions.find_one({"_id": qid})
    if not q:
        return jsonify({"error": "not found"}), 404
    s = db.surveys.find_one({"_id": q["survey_id"], "owner_id": owner})
    if not s:
        return jsonify({"error": "not found"}), 404
    db.questions.delete_one({"_id": qid})
    db.surveys.update_one({"_id": q["survey_id"]}, {"$set": {"updated_at": _now()}})
    return jsonify({"ok": True})
