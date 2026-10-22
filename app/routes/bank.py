"""阶段二：题库 / 版本 / 共享 / 选用 / 引用查询 / 跨问卷统计"""
from flask import Blueprint, request, jsonify, session
from bson import ObjectId
from datetime import datetime, timezone
from collections import Counter

from app.db import get_db

bp = Blueprint("bank", __name__)


def _now():
    return datetime.now(timezone.utc)


def _uid():
    u = session.get("user_id")
    if not u:
        return None
    try:
        return ObjectId(u)
    except Exception:
        return None


def _require():
    uid = _uid()
    if not uid:
        return None, (jsonify({"error": "login required"}), 401)
    return uid, None


def _can_read_item(item, uid):
    if item["owner_id"] == uid:
        return True
    if item.get("is_public_share"):
        return True
    return uid in (item.get("shared_with") or [])


def _version_public(v):
    return {
        "id": str(v["_id"]),
        "item_id": str(v["item_id"]),
        "version": v.get("version"),
        "parent_version_id": str(v["parent_version_id"]) if v.get("parent_version_id") else None,
        "type": v.get("type"),
        "title": v.get("title"),
        "required": v.get("required", False),
        "options": v.get("options", []),
        "validation": v.get("validation", {}),
        "created_at": v.get("created_at"),
    }


def _item_public(item, head=None):
    return {
        "id": str(item["_id"]),
        "owner_id": str(item["owner_id"]),
        "title_hint": item.get("title_hint"),
        "shared_with": [str(x) for x in item.get("shared_with") or []],
        "is_public_share": item.get("is_public_share", False),
        "head_version_id": str(item["head_version_id"]) if item.get("head_version_id") else None,
        "head": _version_public(head) if head else None,
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


@bp.get("/api/bank/items")
def list_items():
    uid, err = _require()
    if err:
        return err
    db = get_db()
    q = {"$or": [
        {"owner_id": uid},
        {"shared_with": uid},
        {"is_public_share": True},
    ]}
    items = []
    for it in db.question_items.find(q).sort("updated_at", -1):
        head = db.question_versions.find_one({"_id": it["head_version_id"]}) if it.get("head_version_id") else None
        items.append(_item_public(it, head))
    return jsonify({"items": items})


@bp.post("/api/bank/items")
def create_item():
    """创建题库题（同时生成 v1）"""
    uid, err = _require()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    qtype = data.get("type")
    title = (data.get("title") or "").strip()
    if not qtype or not title:
        return jsonify({"error": "type and title required"}), 400
    db = get_db()
    now = _now()
    item = {
        "owner_id": uid,
        "title_hint": title,
        "shared_with": [],
        "is_public_share": bool(data.get("is_public_share", False)),
        "head_version_id": None,
        "created_at": now,
        "updated_at": now,
    }
    ir = db.question_items.insert_one(item)
    item_id = ir.inserted_id
    ver = {
        "item_id": item_id,
        "version": 1,
        "parent_version_id": None,
        "type": qtype,
        "title": title,
        "required": bool(data.get("required", False)),
        "options": data.get("options") or [],
        "validation": data.get("validation") or {},
        "created_at": now,
        "created_by": uid,
    }
    vr = db.question_versions.insert_one(ver)
    db.question_items.update_one({"_id": item_id}, {"$set": {"head_version_id": vr.inserted_id}})
    ver["_id"] = vr.inserted_id
    item["_id"] = item_id
    item["head_version_id"] = vr.inserted_id
    return jsonify({"item": _item_public(item, ver)}), 201


@bp.get("/api/bank/items/<item_id>")
def get_item(item_id):
    uid, err = _require()
    if err:
        return err
    try:
        iid = ObjectId(item_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    db = get_db()
    item = db.question_items.find_one({"_id": iid})
    if not item or not _can_read_item(item, uid):
        return jsonify({"error": "not found"}), 404
    versions = list(db.question_versions.find({"item_id": iid}).sort("version", 1))
    head = next((v for v in versions if v["_id"] == item.get("head_version_id")), None)
    # usage
    usage = []
    for q in db.questions.find({"bank_item_id": iid}):
        s = db.surveys.find_one({"_id": q["survey_id"]}, {"title": 1, "status": 1, "owner_id": 1})
        if s:
            usage.append({
                "survey_id": str(s["_id"]),
                "survey_title": s.get("title"),
                "survey_status": s.get("status"),
                "question_id": str(q["_id"]),
                "bank_version_id": str(q["bank_version_id"]) if q.get("bank_version_id") else None,
            })
    return jsonify({
        "item": _item_public(item, head),
        "versions": [_version_public(v) for v in versions],
        "used_by_surveys": usage,
    })


@bp.post("/api/bank/items/<item_id>/versions")
def fork_version(item_id):
    """基于某版本（默认最新）创建新版本；不修改旧版本内容。"""
    uid, err = _require()
    if err:
        return err
    try:
        iid = ObjectId(item_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    db = get_db()
    item = db.question_items.find_one({"_id": iid})
    if not item or item["owner_id"] != uid:
        return jsonify({"error": "not found or not owner"}), 404
    data = request.get_json(silent=True) or {}
    parent_id = data.get("from_version_id") or item.get("head_version_id")
    try:
        parent_id = ObjectId(parent_id)
    except Exception:
        return jsonify({"error": "invalid from_version_id"}), 400
    parent = db.question_versions.find_one({"_id": parent_id, "item_id": iid})
    if not parent:
        return jsonify({"error": "parent version not found"}), 404
    last = db.question_versions.find_one({"item_id": iid}, sort=[("version", -1)])
    new_ver_num = (last["version"] + 1) if last else 1
    title = (data.get("title") or parent.get("title") or "").strip()
    now = _now()
    ver = {
        "item_id": iid,
        "version": new_ver_num,
        "parent_version_id": parent_id,
        "type": data.get("type") or parent.get("type"),
        "title": title,
        "required": bool(data["required"]) if "required" in data else parent.get("required", False),
        "options": data["options"] if "options" in data else parent.get("options", []),
        "validation": data["validation"] if "validation" in data else parent.get("validation", {}),
        "created_at": now,
        "created_by": uid,
    }
    vr = db.question_versions.insert_one(ver)
    ver["_id"] = vr.inserted_id
    db.question_items.update_one(
        {"_id": iid},
        {"$set": {"head_version_id": vr.inserted_id, "title_hint": title, "updated_at": now}},
    )
    return jsonify({"version": _version_public(ver)}), 201


@bp.post("/api/bank/items/<item_id>/share")
def share_item(item_id):
    uid, err = _require()
    if err:
        return err
    try:
        iid = ObjectId(item_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    data = request.get_json(silent=True) or {}
    db = get_db()
    item = db.question_items.find_one({"_id": iid})
    if not item or item["owner_id"] != uid:
        return jsonify({"error": "not found or not owner"}), 404
    updates = {"updated_at": _now()}
    if "is_public_share" in data:
        updates["is_public_share"] = bool(data["is_public_share"])
    if "username" in data and data["username"]:
        u = db.users.find_one({"username": data["username"].strip()})
        if not u:
            return jsonify({"error": "user not found"}), 404
        db.question_items.update_one({"_id": iid}, {"$addToSet": {"shared_with": u["_id"]}, "$set": updates})
    else:
        db.question_items.update_one({"_id": iid}, {"$set": updates})
    item = db.question_items.find_one({"_id": iid})
    head = db.question_versions.find_one({"_id": item["head_version_id"]}) if item.get("head_version_id") else None
    return jsonify({"item": _item_public(item, head)})


@bp.post("/api/surveys/<survey_id>/questions/from-bank")
def add_from_bank(survey_id):
    """从题库某版本拷贝快照到问卷（阶段一 questions 文档，带溯源字段）"""
    uid, err = _require()
    if err:
        return err
    try:
        sid = ObjectId(survey_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        vid = ObjectId(data.get("version_id"))
    except Exception:
        return jsonify({"error": "version_id required"}), 400
    db = get_db()
    s = db.surveys.find_one({"_id": sid, "owner_id": uid})
    if not s:
        return jsonify({"error": "survey not found"}), 404
    ver = db.question_versions.find_one({"_id": vid})
    if not ver:
        return jsonify({"error": "version not found"}), 404
    item = db.question_items.find_one({"_id": ver["item_id"]})
    if not item or not _can_read_item(item, uid):
        return jsonify({"error": "no access to bank item"}), 403
    last = db.questions.find_one({"survey_id": sid}, sort=[("order", -1)])
    order = (last["order"] + 1) if last else 1
    frozen = s.get("status") == "published"
    doc = {
        "survey_id": sid,
        "order": order,
        "type": ver.get("type"),
        "title": ver.get("title"),
        "required": ver.get("required", False),
        "options": ver.get("options") or [],
        "validation": ver.get("validation") or {},
        "jump_rules": [],
        "bank_item_id": ver["item_id"],
        "bank_version_id": ver["_id"],
        "frozen": frozen,
        "created_at": _now(),
    }
    res = db.questions.insert_one(doc)
    doc["_id"] = res.inserted_id
    db.surveys.update_one({"_id": sid}, {"$set": {"updated_at": _now()}})
    return jsonify({
        "question": {
            "id": str(doc["_id"]),
            "survey_id": str(sid),
            "order": order,
            "type": doc["type"],
            "title": doc["title"],
            "required": doc["required"],
            "options": doc["options"],
            "validation": doc["validation"],
            "jump_rules": [],
            "bank_item_id": str(doc["bank_item_id"]),
            "bank_version_id": str(doc["bank_version_id"]),
            "frozen": frozen,
        }
    }), 201


@bp.get("/api/bank/items/<item_id>/stats")
def item_cross_stats(item_id):
    """跨问卷：某逻辑题在所有引用它的答卷中的分布"""
    uid, err = _require()
    if err:
        return err
    try:
        iid = ObjectId(item_id)
    except Exception:
        return jsonify({"error": "invalid id"}), 400
    db = get_db()
    item = db.question_items.find_one({"_id": iid})
    if not item or not _can_read_item(item, uid):
        return jsonify({"error": "not found"}), 404

    # all survey questions referencing this item
    qdocs = list(db.questions.find({"bank_item_id": iid}))
    qids = [q["_id"] for q in qdocs]
    if not qids:
        return jsonify({
            "item_id": str(iid),
            "title_hint": item.get("title_hint"),
            "response_answer_count": 0,
            "survey_count": 0,
            "distribution": [],
            "samples": [],
            "numeric": None,
        })

    # collect answers
    values = []
    survey_ids = set()
    for r in db.responses.find({"answers.question_id": {"$in": qids}}):
        survey_ids.add(r["survey_id"])
        for a in r.get("answers") or []:
            if a.get("question_id") in qids:
                values.append(a.get("value"))

    # use head version type for presentation
    head = db.question_versions.find_one({"_id": item["head_version_id"]}) if item.get("head_version_id") else None
    qtype = (head or {}).get("type") or (qdocs[0].get("type") if qdocs else "text")
    out = {
        "item_id": str(iid),
        "title_hint": item.get("title_hint"),
        "type": qtype,
        "response_answer_count": len(values),
        "survey_count": len(survey_ids),
        "question_refs": len(qdocs),
    }
    if qtype in ("single", "multiple", "rating"):
        counter = Counter()
        for v in values:
            if isinstance(v, list):
                for x in v:
                    counter[str(x)] += 1
            else:
                counter[str(v)] += 1
        opts = (head or qdocs[0]).get("options") or []
        out["distribution"] = [
            {"value": o["value"], "label": o.get("label", o["value"]), "count": counter.get(str(o["value"]), 0)}
            for o in opts
        ] or [{"value": k, "label": k, "count": c} for k, c in counter.items()]
    elif qtype == "number":
        nums = []
        for v in values:
            try:
                nums.append(float(v))
            except (TypeError, ValueError):
                pass
        out["numeric"] = {
            "count": len(nums),
            "avg": (sum(nums) / len(nums)) if nums else None,
            "min": min(nums) if nums else None,
            "max": max(nums) if nums else None,
        }
    else:
        out["samples"] = [str(v) for v in values[-30:]]
    return jsonify(out)

