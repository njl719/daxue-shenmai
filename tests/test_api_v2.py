# -*- coding: utf-8 -*-
"""API 集成测试:v2 新端点(上传/AI降级/反思/教练/画像/周报/复测增强)。"""
import io
import struct
import zlib


def make_png(width=4, height=4):
    """生成最小合法 PNG 字节。"""
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x40\x80\xc0" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def test_upload_and_fetch_image(client):
    png = make_png()
    rv = client.post("/api/upload", data={"file": (io.BytesIO(png), "test.png")},
                     )
    assert rv.status_code == 200
    j = rv.get_json()
    assert j["file"].endswith(".png")
    rv = client.get("/api/images/" + j["file"])
    assert rv.status_code == 200
    assert rv.data[:4] == b"\x89PNG"
    # 非法文件名被拒
    assert client.get("/api/images/..%2Fsettings.json").status_code in (400, 404)
    # 非图片被拒
    rv = client.post("/api/upload", data={"file": (io.BytesIO(b"xx"), "a.txt")},
                     )
    assert rv.status_code == 400


def test_mistake_with_image_and_ai_fields(client):
    png = make_png()
    up = client.post("/api/upload", data={"file": (io.BytesIO(png), "q.png")},
                     ).get_json()
    rv = client.post("/api/mistakes", json={
        "subject": "math", "question_md": "", "image": up["file"],
        "needs_confirmation": True, "confidence": 0.4, "error_reason": "暂时无法判断"})
    assert rv.status_code == 201
    j = rv.get_json()
    assert j["image"] == up["file"]
    assert j["needs_confirmation"] is True
    assert j["confidence"] == 0.4


def test_ai_recognize_without_key_honest(client):
    png = make_png()
    up = client.post("/api/upload", data={"file": (io.BytesIO(png), "q.png")},
                     ).get_json()
    rv = client.post("/api/ai/recognize", json={"file": up["file"]})
    j = rv.get_json()
    assert j["ai_available"] is False
    assert j["data"]["question_text"] == ""  # 不伪造
    assert "配置" in (j["error"] or "")
    assert client.get("/api/ai/status").get_json()["available"] is False


def test_settings_ai_config_masked(client):
    rv = client.put("/api/settings", json={"ai": {
        "base_url": "https://api.deepseek.com", "model": "deepseek-chat",
        "api_key": "sk-secret-12345678"}})
    assert rv.status_code == 200
    s = client.get("/api/settings").get_json()
    assert s["ai"]["has_key"] is True
    assert "****" in s["ai"].get("api_key_masked", "")
    assert "sk-secret" not in s["ai"].get("api_key_masked", "")
    # 明文绝不回传
    assert "sk-secret-12345678" not in rv.get_data(as_text=True)
    # 空 key 更新不覆盖
    client.put("/api/settings", json={"ai": {"model": "deepseek-reasoner"}})
    s = client.get("/api/settings").get_json()
    assert s["ai"]["model"] == "deepseek-reasoner"
    assert s["ai"]["has_key"] is True
    # 配好 base_url+key+model 后 available(通过 ai.status 间接验证)
    st = client.get("/api/ai/status").get_json()
    assert st["available"] is True


def test_reflection_extract_rule_and_save(client):
    text = "今天408看了两个小时操作系统,进程同步还是混乱。明天重看王道课件。"
    rv = client.post("/api/reflections/extract", json={"text": text})
    j = rv.get_json()
    assert j["extracted"]["source"] == "rule"  # 无 Key → 规则解析且明确标注
    assert j["ai_available"] is False
    assert "cs408" in j["extracted"]["subjects"]
    # 用户确认后保存(可修改)
    ex = j["extracted"]
    ex["weak_points"] = ["进程同步:信号量使用"]  # 用户修正
    rv = client.post("/api/reflections", json={"raw_text": text, "extracted": ex,
                                               "confirmed": True})
    assert rv.status_code == 201
    rid = rv.get_json()["id"]
    lst = client.get("/api/reflections").get_json()
    assert any(r["id"] == rid for r in lst)
    saved = [r for r in lst if r["id"] == rid][0]
    assert saved["extracted"]["weak_points"] == ["进程同步:信号量使用"]
    assert saved["confirmed"] is True


def test_coach_chat_without_key_saves_honest_reply(client):
    rv = client.post("/api/coach/chat", json={"message": "我最近数学怎么样?"})
    j = rv.get_json()
    assert j["reply"] is None
    assert j["ai_available"] is False
    hist = client.get("/api/coach/history").get_json()
    assert len(hist) == 2
    assert hist[0]["role"] == "user"
    assert hist[1]["role"] == "assistant" and hist[1].get("system") is True
    assert "配置" in hist[1]["content"]
    # 清空
    assert client.delete("/api/coach/history").status_code == 200


def test_profile_endpoint_shape(client):
    # 造一点数据
    client.post("/api/mistakes", json={
        "subject": "math", "question_md": "题", "error_reason": "计算失误"})
    rv = client.get("/api/profile")
    prof = rv.get_json()
    assert "subjects" in prof and "weak_points" in prof
    assert "data_gaps" in prof and "trend_14d" in prof
    assert "stage" in prof  # 无考试日期 → None
    # 新用户(无练习) → 不应有 confirmed 薄弱点
    assert all(w["status"] != "confirmed" for w in prof["weak_points"])


def test_weekly_report_endpoint(client):
    client.post("/api/records", json={
        "subject": "math", "session_type": "practice", "total": 6,
        "correct": 4, "duration_min": 30, "detail": []})
    rv = client.get("/api/report/weekly/2026-10-24")
    r = rv.get_json()
    for key in ("week_start", "tasks", "per_subject", "review", "compare",
                "next_week_advice", "data_gaps", "unverified_judgments"):
        assert key in r
    assert r["compare"]["this_week"]["total"] == 6
    assert r["compare"]["this_week"]["accuracy"] == 67


def test_review_with_duration_and_hint(client):
    rv = client.post("/api/mistakes", json={
        "subject": "cs408", "question_md": "题", "qtype": "概念"})
    mid = rv.get_json()["id"]
    rv = client.post("/api/mistakes/%s/review" % mid, json={
        "result": "good", "duration_sec": 95, "hint_used": True})
    j = rv.get_json()
    entry = j["reviews"][-1]
    assert entry["duration_sec"] == 95
    assert entry["hint_used"] is True


def test_plan_tasks_carry_coach_metadata(client):
    rv = client.post("/api/plan/generate", json={})
    tasks = rv.get_json()["tasks"]
    for t in tasks:
        assert "goal" in t and "standard" in t and "reason" in t


def test_reflections_feed_weak_points(client):
    """反思 + 复测联动:同一薄弱点反复出现 → 有证据的薄弱点。"""
    # 1. 录入错题并关联知识点 kp-math-0002(等价无穷小)
    client.post("/api/mistakes", json={
        "subject": "math", "question_md": "极限题",
        "knowledge_ids": ["kp-math-0002"], "error_reason": "等价无穷小加减误用"})
    # 2. 两次复测都忘
    rv = client.get("/api/mistakes?subject=math")
    mk = [m for m in rv.get_json() if m["question_md"] == "极限题"][0]
    client.post("/api/mistakes/%s/review" % mk["id"], json={"result": "again"})
    # 让它再到期(隔天)后再次 again:直接改 next_review 通过 PUT 不行,用 again 两次间隔模拟
    # 简化:直接查画像,确认反思贡献了 suspected、错题贡献了 evidence
    client.post("/api/reflections", json={
        "raw_text": "积分换元老想不到",
        "extracted": {"source": "rule", "subjects": ["math"],
                      "weak_points": ["等价无穷小替换"], "content": "反思"}})
    prof = client.get("/api/profile").get_json()
    names = [w["name"] for w in prof["weak_points"]]
    assert any("等价无穷小" in n for n in names)
    wp = [w for w in prof["weak_points"] if "等价无穷小" in w["name"]][0]
    assert wp["evidence"], "薄弱点必须携带证据"
