# -*- coding: utf-8 -*-
"""API 集成测试:用 Flask test client 走完整请求链。(client fixture 在 conftest.py)"""
import datetime


def test_index_served(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"kaoru" in rv.data or "考研" in rv.data.decode("utf-8")


def test_settings_roundtrip(client):
    rv = client.put("/api/settings", json={"exam_date": "2027-12-25",
                                           "target_school": "待定"})
    assert rv.get_json()["exam_date"] == "2027-12-25"
    rv = client.get("/api/settings")
    assert rv.get_json()["target_school"] == "待定"


def test_settings_rejects_unknown_subject(client):
    rv = client.put("/api/settings", json={
        "subjects": {"geography": {"enabled": True, "priority": 1, "minutes": 10}}})
    assert rv.status_code == 400


def test_catalog_with_progress(client):
    rv = client.get("/api/catalog")
    tracks = rv.get_json()["tracks"]
    assert any(t["name"] == "高等数学" for t in tracks.values())
    gs = next(t for t in tracks.values() if t["name"] == "高等数学")
    assert gs["progress"]["knowledge"] > 0


def test_knowledge_crud(client):
    rv = client.post("/api/knowledge", json={
        "subject": "math", "name": "测试知识点", "content_md": "$x^2$",
        "source": "自测"})
    assert rv.status_code == 201
    kid = rv.get_json()["id"]
    rv = client.get("/api/knowledge?subject=math&q=测试")
    assert any(k["id"] == kid for k in rv.get_json())
    rv = client.put("/api/knowledge/" + kid, json={"status": "mastered"})
    assert rv.get_json()["status"] == "mastered"
    rv = client.delete("/api/knowledge/" + kid)
    assert rv.get_json()["deleted"] == kid
    assert client.get("/api/knowledge/" + kid).status_code == 404


def test_knowledge_validation(client):
    assert client.post("/api/knowledge", json={"subject": "bad", "name": "x"}).status_code == 400
    assert client.post("/api/knowledge", json={"subject": "math", "name": " "}).status_code == 400


def test_mistake_full_lifecycle(client):
    rv = client.post("/api/mistakes", json={
        "subject": "cs408", "question_md": "测试题面", "qtype": "概念",
        "solution_md": "解答过程", "knowledge_ids": []})
    assert rv.status_code == 201
    mid = rv.get_json()["id"]

    # 新错题无 next_review → 应到期
    rv = client.get("/api/mistakes?due=1")
    assert any(m["id"] == mid for m in rv.get_json())

    # 评分 good → 明天到期
    rv = client.post("/api/mistakes/%s/review" % mid, json={"result": "good"})
    j = rv.get_json()
    today = datetime.date.today()
    assert j["next_review"] == (today + datetime.timedelta(days=1)).isoformat()
    assert j["interval_days"] == 1

    # 不再到期
    rv = client.get("/api/mistakes?due=1")
    assert not any(m["id"] == mid for m in rv.get_json())

    # again → lapses+1,回到明天
    rv = client.post("/api/mistakes/%s/review" % mid, json={"result": "again"})
    assert rv.get_json()["lapses"] == 1

    rv = client.delete("/api/mistakes/" + mid)
    assert rv.status_code == 200


def test_mistake_qtype_validation(client):
    rv = client.post("/api/mistakes", json={
        "subject": "math", "question_md": "题", "qtype": "不存在的题型"})
    assert rv.status_code == 400


def test_mistake_choice_question(client):
    # 带选项的选择题:正常创建
    rv = client.post("/api/mistakes", json={
        "subject": "cs408", "question_md": "下列排序中稳定的是?",
        "options": ["快排", "归并", "堆排", "希尔"], "answer": "B",
        "solution_md": "归并排序稳定;其余均不稳定。"})
    assert rv.status_code == 201
    j = rv.get_json()
    assert j["options"] == ["快排", "归并", "堆排", "希尔"]
    assert j["answer"] == "B"
    # answer 非法字母被拒
    rv = client.post("/api/mistakes", json={
        "subject": "cs408", "question_md": "题",
        "options": ["甲", "乙"], "answer": "E"})
    assert rv.status_code == 400
    # 更新选项
    mid = j["id"]
    rv = client.put("/api/mistakes/" + mid, json={"answer": "B"})
    assert rv.get_json()["answer"] == "B"
    client.delete("/api/mistakes/" + mid)


def test_records_and_stats(client):
    client.post("/api/records", json={
        "subject": "math", "session_type": "practice", "total": 10,
        "correct": 7, "duration_min": 25, "detail": []})
    rv = client.get("/api/stats/summary")
    stats = rv.get_json()
    assert stats["subjects"]["math"]["total_attempted"] == 10
    assert stats["subjects"]["math"]["accuracy"] == 70
    assert len(stats["trend_14d"]) == 14


def test_plan_generate_and_task_actions(client):
    # 生成今日计划(种子错题未复习,应产生复习任务)
    rv = client.post("/api/plan/generate", json={})
    assert rv.status_code == 200
    tasks = rv.get_json()["tasks"]
    assert isinstance(tasks, list)

    if tasks:
        tid = tasks[0]["id"]
        # 手动完成一个任务,再重新生成,验证不被覆盖
        rv = client.post("/api/plan/task/" + tid, json={"action": "done",
                                                        "actual_minutes": 12})
        assert rv.get_json()["status"] == "done"
        rv = client.post("/api/plan/generate", json={})
        kept = [t for t in rv.get_json()["tasks"] if t["id"] == tid]
        assert kept and kept[0]["status"] == "done"

        # 顺延
        rv = client.post("/api/plan/task/" + tid, json={"action": "move"})
        assert "moved_to" in rv.get_json()

    rv = client.get("/api/plan/weekly/" + datetime.date.today().isoformat())
    assert rv.status_code == 200 and "week_start" in rv.get_json()


def test_practice_session(client):
    rv = client.get("/api/practice/session")
    j = rv.get_json()
    assert "due_mistakes" in j and "due_vocab" in j and "weak" in j
    # 种子错题从未复习过,应全部到期
    assert len(j["due_mistakes"]) >= 2


def test_vocab_flow(client):
    rv = client.post("/api/vocab", json={"kind": "word", "text": "pivot",
                                         "meaning_md": "n. 支点;vt. 使旋转"})
    vid = rv.get_json()["id"]
    rv = client.post("/api/vocab/%s/review" % vid, json={"result": "easy"})
    assert rv.get_json()["interval_days"] == 3
    rv = client.get("/api/vocab?q=piv")
    assert len(rv.get_json()) == 1
    rv = client.delete("/api/vocab/" + vid)
    assert rv.status_code == 200


def test_export_all(client):
    rv = client.get("/api/export/all")
    assert rv.status_code == 200
    import os
    assert os.path.exists(rv.get_json()["path"])
    rv = client.get("/api/export/mistakes/download")
    assert rv.status_code == 200


def test_backup_endpoint(client):
    rv = client.post("/api/backup")
    assert rv.status_code == 200
    import os
    assert os.path.isdir(rv.get_json()["path"])


def test_graph(client):
    rv = client.get("/api/graph")
    g = rv.get_json()
    assert any(n["name"] == "洛必达法则" for n in g["nodes"])
    # 等价无穷小替换依赖洛必达 → 至少一条边
    assert len(g["edges"]) >= 1


def test_seed_not_overwritten(client):
    # 再次 seed 不应覆盖或重复
    from app.seed import seed_if_empty
    created = seed_if_empty(client.store)
    assert created == []
    rv = client.get("/api/mistakes")
    assert len(rv.get_json()) == 2
