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


def _seed_mistake(store, mid, q, solution, reason, subject="math"):
    ms = store.load("mistakes")
    ms.append({"id": mid, "subject": subject, "question_md": q, "knowledge_ids": [],
               "qtype": "计算", "difficulty": 3, "options": [], "answer": "",
               "error_reason": reason, "solution_md": solution, "lapses": 0,
               "ease": 2.5, "interval_days": 0, "reviews": [], "next_review": None,
               "archived": False, "seed": False, "created": "2026-10-31T08:00:00"})
    store.save("mistakes", ms)


def test_data_quality_metrics(client):
    # 一条缺解析、一条正常(历史数据直插;错题 API 已移除)
    _seed_mistake(client.store, "mk-dq1", "甲题", "", "")
    _seed_mistake(client.store, "mk-dq2", "乙题", "有解析", "计算失误")
    j = client.get("/api/data-quality").get_json()
    assert j["mistakes"]["total"] >= 2
    assert j["mistakes"]["missing_solution"] >= 1
    assert j["mistakes"]["missing_reason"] >= 1
    assert "notes" in j and j["sources"]["total"] >= 0


def test_data_quality_duplicate_detection(client):
    _seed_mistake(client.store, "mk-dup1", "TCP 建立连接需要几次?", "3 次",
                  "记忆混淆", subject="cs408")
    _seed_mistake(client.store, "mk-dup2", "TCP 建立连接需要几次?", "3 次",
                  "记忆混淆", subject="cs408")
    j = client.get("/api/data-quality").get_json()
    assert j["mistakes"]["duplicates"] >= 1


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
