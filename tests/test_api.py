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

