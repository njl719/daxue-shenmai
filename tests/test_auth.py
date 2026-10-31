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
    rv = client.get("/api/records")
    assert rv.status_code == 401
    # 错误密码
    rv = client.post("/api/login", json={"username": "tester", "password": "wrong!"})
    assert rv.status_code == 401
    # 正确登录
    rv = client.post("/api/login", json={"username": "tester", "password": "secret123"})
    assert rv.status_code == 200
    assert client.get("/api/records").status_code == 200


def test_login_failure_audited(client):
    client.post("/api/login", json={"username": "tester", "password": "wrong!"})
    events = client.get("/api/account/audit").get_json()
    assert any(e["event"] == "login_failed" for e in events)


def test_password_change_revokes_sessions(client):
    client.post("/api/account/password", json={
        "old_password": "secret123", "new_password": "newpass66"})
    # 旧会话已被吊销
    assert client.get("/api/records").status_code == 401
    rv = client.post("/api/login", json={"username": "tester", "password": "newpass66"})
    assert rv.status_code == 200


def test_password_change_requires_old(client):
    rv = client.post("/api/account/password", json={
        "old_password": "wrong!", "new_password": "whatever1"})
    assert rv.status_code == 400


def test_password_min_length_boundary(tmp_path):
    """T2:新密码下限 8 位(7 拒 8 收),注册与改密同规则;不影响存量账号登录。"""
    from app.server import create_app
    app, store = create_app(data_dir=str(tmp_path / "d"), backup_dir=str(tmp_path / "b"))
    app.config["TESTING"] = True
    c = app.test_client()
    rv = c.post("/api/setup", json={"username": "u", "password": "short7x"})
    assert rv.status_code == 400 and "至少 8 位" in rv.get_json()["error"]
    rv = c.post("/api/setup", json={"username": "u", "password": "longenough8"})
    assert rv.status_code in (200, 201)
    # 改密同样受限(原密码正确、新密码 7 位)
    c.post("/api/login", json={"username": "u", "password": "longenough8"})
    rv = c.post("/api/account/password", json={
        "old_password": "longenough8", "new_password": "seven7x"})
    assert rv.status_code == 400 and "至少 8 位" in rv.get_json()["error"]
    # 8 位新密码可改成功并重新登录
    rv = c.post("/api/account/password", json={
        "old_password": "longenough8", "new_password": "newpass88"})
    assert rv.status_code == 200
    assert c.post("/api/login", json={
        "username": "u", "password": "newpass88"}).status_code == 200


def test_purge_expired_sessions(tmp_path):
    """T3:purge 只删过期项,幂等,空表安全。"""
    import datetime as dt
    from app import auth as A
    from app.storage import Store
    store = Store(data_dir=str(tmp_path / "d"), backup_dir=str(tmp_path / "b"))
    now = dt.datetime.now()
    store.save("sessions", [
        {"token": "dead", "user": "u",
         "expires": (now - dt.timedelta(hours=1)).isoformat(timespec="seconds")},
        {"token": "alive", "user": "u",
         "expires": (now + dt.timedelta(days=1)).isoformat(timespec="seconds")}])
    assert A.purge_expired_sessions(store) == 1
    assert [s["token"] for s in store.load("sessions")] == ["alive"]
    assert A.purge_expired_sessions(store) == 0  # 幂等
    store.save("sessions", [])
    assert A.purge_expired_sessions(store) == 0  # 空表不异常


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
