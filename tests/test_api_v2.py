# -*- coding: utf-8 -*-
"""API 集成测试:v2 新端点(上传/AI降级/反思/教练/画像/周报/复测增强)。"""
import datetime
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


def test_settings_ai_config_masked(client):
    rv = client.put("/api/settings", json={"ai": {
        "mode": "cloud", "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat", "api_key": "sk-secret-12345678"}})
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
    # 配好 base_url+key+model 即视为可用(has_key 表明 Key 已存;
    # 明文/available 不回传 —— available 由三要素推导,ai/status 已随 Ollama 移除)
    assert s["ai"].get("base_url") and s["ai"].get("model") and s["ai"]["has_key"]


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
    # 当周周一动态计算:写入的记录日期是"今天",查询周必须与之对齐(修复日期硬编码)
    _today = datetime.date.today()
    monday = _today - datetime.timedelta(days=_today.weekday())
    rv = client.get("/api/report/weekly/" + monday.isoformat())
    r = rv.get_json()
    for key in ("week_start", "tasks", "per_subject", "review", "compare",
                "next_week_advice", "data_gaps", "unverified_judgments"):
        assert key in r
    assert r["week_start"] == monday.isoformat()
    assert r["compare"]["this_week"]["total"] == 6
    assert r["compare"]["this_week"]["accuracy"] == 67


def test_weekly_report_week_window_cross_year():
    """周窗口口径:周一为起点、跨年不断裂(2026-12-31 是周四,当周周一为 12-28)。"""
    from app import profile as P
    r = P.weekly_report("2026-12-31", [], [], [], {}, [])
    assert r["week_start"] == "2026-12-28"
    assert r["week_end"] == "2027-01-03"
    assert r["compare"]["this_week"]["total"] == 0  # 空数据不异常


def test_plan_tasks_carry_coach_metadata(client):
    rv = client.post("/api/plan/generate", json={})
    tasks = rv.get_json()["tasks"]
    for t in tasks:
        assert "goal" in t and "standard" in t and "reason" in t


def test_reflections_feed_weak_points(client):
    """反思 + 历史错题联动:同一薄弱点反复出现 → 有证据的薄弱点。
    (第四轮起错题 API 已移除,历史数据经 store 直插,画像逻辑不变)"""
    # 1. 直接注入一条关联 kp-math-0002(等价无穷小)的历史错题,已两次复测忘记
    ms = client.store.load("mistakes")
    ms.append({"id": "mk-x1", "subject": "math", "question_md": "极限题",
               "knowledge_ids": ["kp-math-0002"], "qtype": "计算",
               "difficulty": 2, "options": [], "answer": "",
               "error_reason": "等价无穷小加减误用", "solution_md": "",
               "lapses": 2, "ease": 2.5, "interval_days": 1,
               "reviews": [{"result": "again", "date": "2026-10-03", "duration_sec": 60},
                           {"result": "again", "date": "2026-10-10", "duration_sec": 60}],
               "next_review": None, "archived": False, "seed": False,
               "created": "2026-10-01T08:00:00"})
    client.store.save("mistakes", ms)
    # 2. 反思同一薄弱点
    client.post("/api/reflections", json={
        "raw_text": "积分换元老想不到",
        "extracted": {"source": "rule", "subjects": ["math"],
                      "weak_points": ["等价无穷小替换"], "content": "反思"}})
    prof = client.get("/api/profile").get_json()
    names = [w["name"] for w in prof["weak_points"]]
    assert any("等价无穷小" in n for n in names)
    wp = [w for w in prof["weak_points"] if "等价无穷小" in w["name"]][0]
    assert wp["evidence"], "薄弱点必须携带证据"
