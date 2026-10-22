"""问卷统计：答题数 + 各题选项分布 / 文本抽样"""
from flask import Blueprint, jsonify, session
from bson import ObjectId
from collections import Counter

from app.db import get_db

bp = Blueprint("stats", __name__)


def _require_user():
    uid = session.get("user_id")
    if not uid:
        return None
    try:
        return ObjectId(uid)
    except Exception:
        return None


@bp.get("/api/surveys/<survey_id>/stats")
def survey_stats(survey_id):
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
    responses = list(db.responses.find({"survey_id": sid}))
    total = len(responses)

    # build per-question answer lists
    by_q = {str(q["_id"]): [] for q in questions}
    for r in responses:
        for a in r.get("answers") or []:
            qid = str(a["question_id"])
            if qid in by_q:
                by_q[qid].append(a.get("value"))

    question_stats = []
    for q in questions:
        qid = str(q["_id"])
        values = by_q[qid]
        answered = len(values)
        qtype = q.get("type")
        item = {
            "question_id": qid,
            "title": q.get("title"),
            "type": qtype,
            "answered": answered,
            "skipped": total - answered,
        }
        if qtype in ("single", "multiple", "rating"):
            counter = Counter()
            for v in values:
                if isinstance(v, list):
                    for x in v:
                        counter[str(x)] += 1
                else:
                    counter[str(v)] += 1
            labels = {o["value"]: o.get("label", o["value"]) for o in q.get("options") or []}
            item["distribution"] = [
                {
                    "value": opt["value"],
                    "label": opt.get("label", opt["value"]),
                    "count": counter.get(str(opt["value"]), 0),
                }
                for opt in (q.get("options") or [])
            ]
        elif qtype == "number":
            nums = []
            for v in values:
                try:
                    nums.append(float(v))
                except (TypeError, ValueError):
                    pass
            item["numeric"] = {
                "count": len(nums),
                "avg": (sum(nums) / len(nums)) if nums else None,
                "min": min(nums) if nums else None,
                "max": max(nums) if nums else None,
            }
        elif qtype in ("text", "date"):
            # 最多返回最近 20 条样例
            item["samples"] = [str(v) for v in values[-20:]]
        question_stats.append(item)

    return jsonify({
        "survey_id": str(sid),
        "title": s.get("title"),
        "status": s.get("status"),
        "response_count": total,
        "questions": question_stats,
    })
