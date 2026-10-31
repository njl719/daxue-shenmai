# -*- coding: utf-8 -*-
"""第三阶段后端修复测试:F1 records 校验 / F2 知识删除级联 / F3 difficulty 边界 / F4 恢复工具。"""
import os

from tools.restore_backup import list_backups, mirror_copy, restore


# ---------------- F1 records 参数校验 ----------------

def test_records_reject_negative_and_overflow(client):
    for body in ({"subject": "math", "total": -3, "correct": 0},
                 {"subject": "math", "total": 5, "correct": -1},
                 {"subject": "math", "total": 5, "correct": 9}):
        rv = client.post("/api/records", json=body)
        assert rv.status_code == 400, body
        assert "不能" in rv.get_json()["error"]


def test_records_reject_non_int_and_bad_date(client):
    # 旧实现 int("abc") 直接 500;现在应 400
    rv = client.post("/api/records", json={"subject": "math", "total": "abc", "correct": 0})
    assert rv.status_code == 400
    rv = client.post("/api/records", json={"subject": "math", "total": 3,
                                           "correct": 1, "date": "2026/10/30"})
    assert rv.status_code == 400 and "YYYY-MM-DD" in rv.get_json()["error"]


def test_records_accepts_valid_and_casts(client):
    rv = client.post("/api/records", json={
        "subject": "english", "total": "8", "correct": "6",
        "duration_min": "25", "date": "2026-10-30"})
    assert rv.status_code == 201
    r = rv.get_json()
    assert r["total"] == 8 and r["correct"] == 6 and r["duration_min"] == 25


# ---------------- F2 知识点删除级联 ----------------

def test_knowledge_delete_cleans_references(client):
    """第四轮:错题 API 移除,历史错题经 store 直插验证级联清理。"""
    kid = client.post("/api/knowledge", json={
        "subject": "math", "name": "级联测试点"}).get_json()["id"]
    ms = client.store.load("mistakes")
    ms.append({"id": "mk-c1", "subject": "math", "question_md": "题面",
               "knowledge_ids": [kid], "qtype": "计算", "difficulty": 3,
               "options": [], "answer": "", "error_reason": "", "solution_md": "",
               "lapses": 0, "ease": 2.5, "interval_days": 0, "reviews": [],
               "next_review": None, "archived": False, "seed": False,
               "created": "2026-10-31T08:00:00"})
    client.store.save("mistakes", ms)
    rid = client.post("/api/records", json={
        "subject": "math", "total": 2, "correct": 1, "knowledge_ids": [kid]}).get_json()["id"]
    rv = client.delete("/api/knowledge/" + kid)
    assert rv.status_code == 200
    d = rv.get_json()
    assert d["deleted"] == kid and d["mistakes"] == 1 and d["records"] == 1
    assert all(kid not in (m.get("knowledge_ids") or [])
               for m in client.store.load("mistakes"))
    assert all(kid not in (r.get("knowledge_ids") or [])
               for r in client.store.load("records"))
    # 画像端点不因孤儿/清理异常
    assert client.get("/api/profile").status_code == 200
    assert client.delete("/api/knowledge/" + kid).status_code == 404


# ---------------- F3 difficulty 边界 ----------------

def test_restore_dry_run_and_mirror(tmp_path):
    data_dir = tmp_path / "data"
    backup_root = tmp_path / "backups"
    data_dir.mkdir()
    (data_dir / "a.json").write_text('{"v":1}', encoding="utf-8")
    (data_dir / "images").mkdir()
    (data_dir / "images" / "p.png").write_text("img", encoding="utf-8")
    # 用 Store 制作一份标准备份
    from app.storage import Store
    store = Store(data_dir=str(data_dir), backup_dir=str(backup_root))
    store._maybe_daily_backup = lambda: None
    dest = store.backup("testtag")
    # 改动当前数据,制造"待恢复"差异
    (data_dir / "a.json").write_text('{"v":2}', encoding="utf-8")
    (data_dir / "extra.json").write_text("{}", encoding="utf-8")

    bak_name = os.path.basename(dest)
    assert bak_name in {b[0] for b in list_backups(str(backup_root))}
    # dry-run:不修改任何文件
    plan = restore(str(backup_root), str(data_dir), bak_name, apply=False)
    assert plan["ok"] and plan["files"] == 2
    assert (data_dir / "a.json").read_text(encoding="utf-8") == '{"v":2}'
    # apply:镜像恢复 + 自动安全备份
    plan = restore(str(backup_root), str(data_dir), bak_name, apply=True,
                   backup_dir_root=str(backup_root))
    assert plan["copied"] == 2 and plan["removed"] == 1
    assert (data_dir / "a.json").read_text(encoding="utf-8") == '{"v":1}'
    assert not (data_dir / "extra.json").exists()
    assert plan["safety_backup"] and os.path.isdir(plan["safety_backup"])


def test_restore_rejects_bad_name(tmp_path):
    plan = restore(str(tmp_path / "b"), str(tmp_path / "d"), "not-a-backup")
    assert plan["ok"] is False and "不存在" in plan["error"]
