# -*- coding: utf-8 -*-
"""账号认证与访问控制测试:初始化/登录/登出/会话吊销/审计/数据删除确认。"""
import json


def test_setup_creates_account_and_session(client):
    rv = client.get("/api/account")
    assert rv.status_code == 200
    assert rv.get_json()["username"] == "tester"


def test_setup_only_once(client):
    rv = client.post("/api/setup", json={"username": "x", "password": "yyy123"})
    assert rv.status_code == 400
    assert "已存在" in rv.get_json()["error"]


def test_gate_requires_session(client):
    """无会话 cookie 的 API 请求一律 401。"""
    # 新的未登录客户端
    from app.server import create_app
    app, store = create_app(data_dir=client.store.data_dir,
                            backup_dir=client.store.backup_dir)
    app.config["TESTING"] = True
    fresh = app.test_client()
    rv = fresh.get("/api/mistakes")
    assert rv.status_code == 401
    assert rv.get_json()["auth_required"] is True
    assert fresh.post("/api/knowledge", json={"subject": "math", "name": "x"}).status_code == 401


def test_login_logout(client):
    client.post("/api/logout")
    rv = client.get("/api/mistakes")
    assert rv.status_code == 401
    # 错误密码
    rv = client.post("/api/login", json={"username": "tester", "password": "wrong!"})
    assert rv.status_code == 401
    # 正确登录
    rv = client.post("/api/login", json={"username": "tester", "password": "secret1"})
    assert rv.status_code == 200
    assert client.get("/api/mistakes").status_code == 200


def test_login_failure_audited(client):
    client.post("/api/login", json={"username": "tester", "password": "wrong!"})
    events = client.get("/api/account/audit").get_json()
    assert any(e["event"] == "login_failed" for e in events)


def test_password_change_revokes_sessions(client):
    client.post("/api/account/password", json={
        "old_password": "secret1", "new_password": "newpass66"})
    # 旧会话已被吊销
    assert client.get("/api/mistakes").status_code == 401
    rv = client.post("/api/login", json={"username": "tester", "password": "newpass66"})
    assert rv.status_code == 200


def test_password_change_requires_old(client):
    rv = client.post("/api/account/password", json={
        "old_password": "wrong!", "new_password": "whatever1"})
    assert rv.status_code == 400


def test_delete_data_requires_confirm(client):
    client.post("/api/records", json={"subject": "math", "total": 5, "correct": 3,
                                      "detail": []})
    rv = client.post("/api/account/delete-data", json={})
    assert rv.status_code == 400
    rv = client.post("/api/account/delete-data", json={"confirm": "DELETE"})
    assert rv.status_code == 200
    assert client.get("/api/records").get_json() == []
    # 账号仍在(未删号)
    assert client.get("/api/account").status_code == 200


def test_migration_runs(tmp_path):
    from app.migrate import run_migrations, SCHEMA_VERSION
    from app.storage import Store
    store = Store(data_dir=str(tmp_path / "d1"), backup_dir=str(tmp_path / "b1"))
    notes = run_migrations(store)
    assert notes, "v1→v2→v3 迁移应执行"
    assert store.load("goals").get("milestones") == []
    # v3:政治目录与英语题型补全
    cat = store.load("catalog")
    assert any(t.get("subject") == "politics" for t in cat["tracks"].values())
    assert "source" in cat  # 目录来源标注
    assert store.load("settings")["subjects"]["politics"]["enabled"] is False
    # 幂等
    assert run_migrations(store) == []
    import json as _json
    ver = _json.load(open(str(tmp_path / "d1") + "/schema_version.json", encoding="utf-8"))
    assert ver["version"] == SCHEMA_VERSION
