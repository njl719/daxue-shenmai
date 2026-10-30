# -*- coding: utf-8 -*-
"""第四阶段学习闭环测试:L1 任务→学习记录 / L2 政治科目 OCR 支持 / L3 检索过滤。"""
import json

from app import ai as AI


# ---------------- L1 任务完成落学习记录(幂等) ----------------

def test_task_done_creates_linked_record(client):
    # 生成当日计划,取第一个任务
    tasks = client.post("/api/plan/generate", json={"date": "2026-10-30"}).get_json()["tasks"]
    assert tasks, "计划应产出任务"
    t = tasks[0]
    rv = client.post("/api/plan/task/" + t["id"], json={"action": "done"})
    assert rv.status_code == 200
    task = rv.get_json()
    assert task["status"] == "done" and task["record_id"]
    recs = [r for r in client.store.load("records") if r["id"] == task["record_id"]]
    assert len(recs) == 1
    rec = recs[0]
    assert rec["client_id"] == "task-" + t["id"]
    assert rec["session_type"] == "study_task"
    assert rec["total"] == 0 and rec["correct"] == 0  # 不虚构做题结果
    assert rec["subject"] == t["subject"]
    assert rec["detail"][0]["task_id"] == t["id"]


def test_task_done_idempotent_after_reset(client):
    tasks = client.post("/api/plan/generate", json={"date": "2026-10-30"}).get_json()["tasks"]
    t = tasks[0]
    client.post("/api/plan/task/" + t["id"], json={"action": "done"})
    client.post("/api/plan/task/" + t["id"], json={"action": "reset"})
    client.post("/api/plan/task/" + t["id"], json={"action": "done"})
    n = sum(1 for r in client.store.load("records")
            if r.get("client_id") == "task-" + t["id"])
    assert n == 1  # reset 再 done 不产生重复记录
    # done → skip → done 也不重复
    client.post("/api/plan/task/" + t["id"], json={"action": "skip"})
    client.post("/api/plan/task/" + t["id"], json={"action": "done"})
    n = sum(1 for r in client.store.load("records")
            if r.get("client_id") == "task-" + t["id"])
    assert n == 1


def test_task_done_links_duration(client):
    tasks = client.post("/api/plan/generate", json={"date": "2026-10-30"}).get_json()["tasks"]
    t = tasks[0]
    client.post("/api/plan/task/" + t["id"],
                json={"action": "done", "actual_minutes": 42})
    rec = next(r for r in client.store.load("records")
               if r.get("client_id") == "task-" + t["id"])
    assert rec["duration_min"] == 42  # 用真实上报时长,不用预估


# ---------------- L2 政治科目(11408)OCR/提取支持 ----------------

def test_recognition_normalizes_chinese_subject(monkeypatch):
    """模型返回中文科目名时,识别结果必须归一化为枚举(否则保存 400)。"""
    monkeypatch.setattr(AI, "_post_chat", lambda cfg, msgs, timeout=90, json_mode=False:
                        (json.dumps({"question_text": "实践是检验真理的唯一标准",
                                     "subject": "政治", "chapter_guess": "马原",
                                     "knowledge_names": ["认识论"], "qtype": "选择",
                                     "difficulty": 2, "error_reason": "概念不清",
                                     "solution_draft": "", "user_work_seen": "",
                                     "confidence": 0.8, "notes": ""}), None))
    monkeypatch.setattr(AI, "get_ai_config",
                        lambda s: {"available": True, "model": "m", "vision_model": "m",
                                   "base_url": "http://x", "api_key": "k"})
    out = AI.recognize_mistake(b"img", "政治选择题", {"available": True, "model": "m"})
    assert out["ok"] is True
    assert out["data"]["subject"] == "politics"
    assert out["data"]["needs_confirmation"] is True


def test_recognition_unknown_subject_left_blank(monkeypatch):
    monkeypatch.setattr(AI, "_post_chat", lambda cfg, msgs, timeout=90, json_mode=False:
                        (json.dumps({"question_text": "?", "subject": "农学",
                                     "confidence": 0.5}), None))
    monkeypatch.setattr(AI, "get_ai_config",
                        lambda s: {"available": True, "model": "m", "vision_model": "m",
                                   "base_url": "http://x", "api_key": "k"})
    out = AI.recognize_mistake(b"img", "", {"available": True, "model": "m"})
    assert out["data"]["subject"] == ""  # 无法归一化就置空,不猜


def test_reflection_normalizes_politics():
    out = AI.normalize_extraction(
        {"subjects": ["政治"], "knowledge_names": ["肖四马原部分"], "minutes": 60})
    assert "politics" in out["subjects"]


def test_recognize_prompt_includes_politics():
    assert "politics" in AI.RECOGNIZE_PROMPT
    assert "选择|分析" in AI.RECOGNIZE_PROMPT


# ---------------- L3 错题检索过滤 ----------------

def test_mistake_filters_error_reason_and_knowledge(client):
    kid = client.post("/api/knowledge", json={
        "subject": "math", "name": "过滤测试点"}).get_json()["id"]
    m1 = client.post("/api/mistakes", json={
        "subject": "math", "question_md": "题A", "knowledge_ids": [kid],
        "error_reason": "计算失误"}).get_json()
    m2 = client.post("/api/mistakes", json={
        "subject": "math", "question_md": "题B", "error_reason": "概念不清"}).get_json()
    r = client.get("/api/mistakes?error_reason=计算失误").get_json()
    assert [m["id"] for m in r] == [m1["id"]]
    r = client.get("/api/mistakes?knowledge_id=" + kid).get_json()
    assert [m["id"] for m in r] == [m1["id"]]
    r = client.get("/api/mistakes?error_reason=不存在的原因").get_json()
    assert r == []
