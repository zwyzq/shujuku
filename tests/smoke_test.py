"""阶段一冒烟测试：注册/登录 → 建问卷 → 加题 → 发布 → 填写 → 统计"""
import json
import sys
import urllib.request
import urllib.error
import http.cookiejar

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5001"


def main():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def req(method, path, data=None):
        body = None
        headers = {}
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode()
            headers["Content-Type"] = "application/json"
        r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
        try:
            with opener.open(r) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    st, h = req("GET", "/api/health")
    assert st == 200 and h.get("ok"), h
    print("health ok", h["db"])

    user = f"smoke_{__import__('time').time_ns() % 10_000_000}"
    st, body = req("POST", "/api/auth/register", {"username": user, "password": "smoke1234"})
    assert st == 201, body
    print("register", user)

    st, body = req("POST", "/api/surveys/", {"title": "冒烟问卷", "description": "auto"})
    assert st == 201, body
    sid = body["survey"]["id"]

    st, body = req(
        "POST",
        f"/api/surveys/{sid}/questions",
        {
            "type": "single",
            "title": "是否愿意推荐？",
            "required": True,
            "options": [{"value": "y", "label": "是"}, {"value": "n", "label": "否"}],
            "jump_rules": [{"when_value": "n", "goto_question_id": "end"}],
        },
    )
    assert st == 201, body
    q1 = body["question"]["id"]

    st, body = req(
        "POST",
        f"/api/surveys/{sid}/questions",
        {"type": "text", "title": "推荐理由", "required": False, "validation": {"max_length": 100}},
    )
    assert st == 201, body
    q2 = body["question"]["id"]

    st, body = req("POST", f"/api/surveys/{sid}/publish")
    assert st == 200, body
    token = body["survey"]["public_token"]
    print("published", token)

    st, body = req("POST", f"/api/fill/{token}", {"answers": [{"question_id": q1, "value": "y"}, {"question_id": q2, "value": "很好"}]})
    assert st == 201, body

    # jump to end: q2 skipped, should still succeed without q2
    st, body = req("POST", f"/api/fill/{token}", {"answers": [{"question_id": q1, "value": "n"}]})
    assert st == 201, body

    st, stats = req("GET", f"/api/surveys/{sid}/stats")
    assert st == 200 and stats["response_count"] == 2, stats
    print("stats", stats["response_count"], "OK")
    print("SMOKE PASS")


if __name__ == "__main__":
    main()
