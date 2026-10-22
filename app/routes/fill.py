"""公开填写：拉取问卷 + 提交答卷（登录/匿名、截止、校验、跳转）"""
from flask import Blueprint, request, jsonify, session
from bson import ObjectId
from datetime import datetime, timezone
import re

from app.db import get_db

bp = Blueprint("fill", __name__)


def _now():
    return datetime.now(timezone.utc)


def _parse_deadline(s):
    if not s:
        return None
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    text = str(s).strip()
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _survey_open(s):
    if s.get("status") != "published":
        return False, "survey not open"
    deadline = _parse_deadline(s.get("deadline"))
    if deadline and _now() > deadline:
        return False, "survey expired"
    return True, None


def _current_user_id():
    uid = session.get("user_id")
    if not uid:
        return None
    try:
        return ObjectId(uid)
    except Exception:
        return None


def _validate_answer(q, value):
    required = q.get("required", False)
    empty = value is None or value == "" or value == []
    if required and empty:
        return "required"
    if empty:
        return None

    qtype = q.get("type")
    v = q.get("validation") or {}
    opts = {o["value"] for o in q.get("options") or []}

    if qtype == "single":
        if value not in opts:
            return "invalid option"
    elif qtype == "multiple":
        if not isinstance(value, list):
            return "must be list"
        if not set(value).issubset(opts):
            return "invalid option"
        n = len(value)
        if v.get("min_select") is not None and n < int(v["min_select"]):
            return "too few selected"
        if v.get("max_select") is not None and n > int(v["max_select"]):
            return "too many selected"
        if v.get("exact_select") is not None and n != int(v["exact_select"]):
            return "exact select mismatch"
    elif qtype == "text":
        if not isinstance(value, str):
            return "must be string"
        if v.get("min_length") is not None and len(value) < int(v["min_length"]):
            return "too short"
        if v.get("max_length") is not None and len(value) > int(v["max_length"]):
            return "too long"
        if v.get("pattern") and not re.search(v["pattern"], value):
            return "pattern mismatch"
    elif qtype == "number":
        try:
            if v.get("integer"):
                if isinstance(value, bool) or (isinstance(value, str) and not re.fullmatch(r"-?\d+", str(value).strip())):
                    return "must be integer"
                num = int(value)
            else:
                num = float(value)
        except (TypeError, ValueError):
            return "must be number"
        if v.get("min") is not None and num < float(v["min"]):
            return "below min"
        if v.get("max") is not None and num > float(v["max"]):
            return "above max"
    elif qtype == "rating":
        if value not in opts:
            return "invalid rating"
    elif qtype == "date":
        if not isinstance(value, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            return "date must be YYYY-MM-DD"
    return None


def _match_rule(when, ans):
    if isinstance(ans, list):
        if isinstance(when, list):
            return set(when).issubset(set(ans))
        return when in ans
    # 数字填空：支持 {"op":">=","value":18} 或直接相等
    if isinstance(when, dict) and "op" in when:
        try:
            left = float(ans)
            right = float(when.get("value"))
        except (TypeError, ValueError):
            return False
        op = when.get("op")
        return {
            ">": left > right,
            ">=": left >= right,
            "<": left < right,
            "<=": left <= right,
            "==": left == right,
            "!=": left != right,
        }.get(op, False)
    return ans == when


def _reachable_question_ids(questions, answers_by_qid):
    by_id = {str(q["_id"]): q for q in questions}
    ordered = sorted(questions, key=lambda q: q.get("order", 0))
    if not ordered:
        return set()

    reachable = set()
    current = str(ordered[0]["_id"])
    visited = set()
    id_to_next = {}
    for i, q in enumerate(ordered):
        nid = str(ordered[i + 1]["_id"]) if i + 1 < len(ordered) else "end"
        id_to_next[str(q["_id"])] = nid

    while current and current != "end" and current not in visited:
        visited.add(current)
        if current not in by_id:
            break
        reachable.add(current)
        q = by_id[current]
        ans = answers_by_qid.get(current)
        jumped = False
        for rule in q.get("jump_rules") or []:
            if _match_rule(rule.get("when_value"), ans):
                goto = rule.get("goto_question_id")
                current = "end" if goto == "end" else (str(goto) if goto is not None else id_to_next[current])
                jumped = True
                break
        if not jumped:
            current = id_to_next.get(current, "end")
    return reachable


def _q_public(q):
    return {
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
    }


def _load_published(token):
    db = get_db()
    s = db.surveys.find_one({"public_token": token})
    if not s:
        return None, None, (jsonify({"error": "not found"}), 404)
    ok, reason = _survey_open(s)
    if not ok:
        return None, None, (jsonify({"error": reason}), 403)
    return db, s, None


def _auth_gate(s):
    """需求：填写者需登录；若允许匿名则可跳过。"""
    if s.get("allow_anonymous", True):
        return None
    if not _current_user_id():
        return jsonify({"error": "login required to fill"}), 401
    return None


@bp.get("/api/fill/<token>")
def get_public_survey(token):
    db, s, err = _load_published(token)
    if err:
        return err
    gate = _auth_gate(s)
    if gate:
        return gate
    questions = list(db.questions.find({"survey_id": s["_id"]}).sort("order", 1))
    return jsonify({
        "survey": {
            "title": s.get("title"),
            "description": s.get("description", ""),
            "status": s.get("status"),
            "allow_anonymous": s.get("allow_anonymous", True),
            "deadline": s.get("deadline"),
        },
        "questions": [_q_public(q) for q in questions],
    })


@bp.post("/api/fill/<token>")
def submit_response(token):
    db, s, err = _load_published(token)
    if err:
        return err
    gate = _auth_gate(s)
    if gate:
        return gate

    data = request.get_json(silent=True) or {}
    raw_answers = data.get("answers") or []
    answers_by_qid = {}
    for a in raw_answers:
        qid = a.get("question_id")
        if qid:
            answers_by_qid[str(qid)] = a.get("value")

    questions = list(db.questions.find({"survey_id": s["_id"]}).sort("order", 1))
    reachable = _reachable_question_ids(questions, answers_by_qid)

    errors = []
    cleaned = []
    for q in questions:
        qid = str(q["_id"])
        if qid not in reachable:
            continue
        value = answers_by_qid.get(qid)
        err_msg = _validate_answer(q, value)
        if err_msg:
            errors.append({"question_id": qid, "error": err_msg})
        elif value is not None and value != "" and value != []:
            cleaned.append({"question_id": ObjectId(qid), "value": value})

    if errors:
        return jsonify({"error": "validation failed", "details": errors}), 400

    doc = {
        "survey_id": s["_id"],
        "answers": cleaned,
        "submitted_at": _now(),
        "respondent_id": _current_user_id(),
        "meta": {
            "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": request.headers.get("User-Agent", "")[:200],
        },
    }
    res = db.responses.insert_one(doc)
    return jsonify({"ok": True, "response_id": str(res.inserted_id)}), 201
