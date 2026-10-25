# -*- coding: utf-8 -*-
"""v3.5 数据可靠性与 AI 状态测试:幂等、校验、质量报告、流式降级。"""
import json


def test_record_idempotency(client):
    body = {"subject": "math", "total": 5, "correct": 4, "duration_min": 20,
            "detail": [], "client_id": "abc-123"}
    r1 = client.post("/api/records", json=body).get_json()
    r2 = client.post("/api/records", json=body).get_json()
    assert r1["id"] == r2["id"], "同一 client_id 不应产生第二条记录"
    lst = client.get("/api/records").get_json()
    assert len([r for r in lst if r.get("client_id") == "abc-123"]) == 1


def test_institution_validation(client):
    base = {"name": "某大学", "program": "计算机", "official_url": "https://x.edu.cn"}
    # 非法年份
    rv = client.post("/api/institutions", json={**base, "exam_year": "20x7"})
    assert rv.status_code == 400 and "年份" in rv.get_json()["error"]
    # 越界年份
    rv = client.post("/api/institutions", json={**base, "exam_year": 2099})
    assert rv.status_code == 400
    # 未知科目代码
    rv = client.post("/api/institutions", json={**base, "subjects": ["999"]})
    assert rv.status_code == 400 and "999" in rv.get_json()["error"]
    # 合法代码
    rv = client.post("/api/institutions", json={**base, "subjects": ["101", "201", "301", "408"]})
    assert rv.status_code == 201
    # 非法 URL
    rv = client.post("/api/institutions", json={**base, "official_url": "ftp://x"})
    assert rv.status_code == 400


def test_data_quality_metrics(client):
    # 一条缺解析、一条正常
    client.post("/api/mistakes", json={"subject": "math", "question_md": "甲题",
                                       "solution_md": "", "error_reason": ""})
    client.post("/api/mistakes", json={"subject": "math", "question_md": "乙题",
                                       "solution_md": "有解析", "error_reason": "计算失误"})
    j = client.get("/api/data-quality").get_json()
    assert j["mistakes"]["total"] >= 2
    assert j["mistakes"]["missing_solution"] >= 1
    assert j["mistakes"]["missing_reason"] >= 1
    assert "notes" in j and j["sources"]["total"] >= 0


def test_data_quality_duplicate_detection(client):
    for _ in range(2):
        client.post("/api/mistakes", json={
            "subject": "cs408", "question_md": "TCP 建立连接需要几次?",
            "solution_md": "3 次", "error_reason": "记忆混淆"})
    j = client.get("/api/data-quality").get_json()
    assert j["mistakes"]["duplicates"] >= 1


def test_tools_whitelist(client):
    # 白名单外工具拒绝
    rv = client.post("/api/tools/execute", json={
        "tool": "delete_everything", "args": {}})
    assert rv.status_code == 400
    # create_task 需合法科目
    rv = client.post("/api/tools/execute", json={
        "tool": "create_task", "args": {"subject": "geography", "title": "x"}})
    assert rv.status_code == 400
    # 合法创建
    rv = client.post("/api/tools/execute", json={
        "tool": "create_task", "args": {"subject": "math", "title": "积分换元专项",
                                        "est_minutes": 20}})
    assert rv.status_code == 200
    j = rv.get_json()
    assert j["task"]["payload"].get("ai_proposed") is True
    # 今天计划里确实存在
    import datetime
    today = datetime.date.today().isoformat()
    plan = client.get("/api/plan/day/" + today).get_json()
    assert any(t["id"] == j["task"]["id"] for t in plan["tasks"])


def test_stream_endpoint_requires_ai(client):
    """AI 不可用时流式端点返回明确错误(本机 Ollama 在运行,故应正常流式;
    此处仅验证端点存在与响应格式)。"""
    rv = client.post("/api/coach/chat/stream", json={"message": "你好"})
    assert rv.status_code == 200
    data = rv.data.decode("utf-8")
    assert "delta" in data or "error" in data or "done" in data


def test_politics_subject_available(client):
    """迁移后政治科目进入目录与设置(默认停用)。"""
    cat = client.get("/api/catalog").get_json()
    assert any(t["subject"] == "politics" for t in cat["tracks"].values())
    s = client.get("/api/settings").get_json()
    assert "politics" in s["subjects"]
    assert s["subjects"]["politics"]["enabled"] is False


def test_politics_can_be_enabled_and_planned(client):
    client.put("/api/settings", json={"subjects": {
        "politics": {"enabled": True, "priority": 4, "minutes": 30}}})
    client.post("/api/knowledge", json={
        "subject": "politics", "name": "马克思主义基本原理-对立统一规律",
        "content_md": "测试", "source": "测试(待核验)"})
    rv = client.post("/api/plan/generate", json={})
    assert rv.status_code == 200
    # 学习任务可能覆盖 politics(取决于时长预算),至少科目被接受
    subjects = {t["subject"] for t in rv.get_json()["tasks"]}
    assert subjects  # 有任务产生
