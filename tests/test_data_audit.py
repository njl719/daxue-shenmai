# -*- coding: utf-8 -*-
"""数据真实性与来源字段测试:F-A 复试线来源强制 / v6→v7 统一来源字段迁移。"""


def test_university_retest_line_requires_source(client):
    unis = client.store.load("universities")
    uid = unis[0]["id"]
    # 只填复试线+年份,无来源 → 400(红线:分数线必须可追溯)
    rv = client.put("/api/universities/" + uid, json={
        "retest_line": "350", "retest_line_year": "2025"})
    assert rv.status_code == 400 and "来源" in rv.get_json()["error"]
    # 补上来源 → 通过,且 updated_at 落值
    rv = client.put("/api/universities/" + uid, json={
        "retest_line": "350", "retest_line_year": "2025",
        "admission_source": "清华大学研究生院官网 2025 招生简章"})
    assert rv.status_code == 200
    u = [x for x in client.store.load("universities") if x["id"] == uid][0]
    assert u["retest_line"] == "350" and u["admission_source"]
    assert u.get("updated_at")
    # 招生人数同样强制来源(既有规则回归;换一所未带来源的院校)
    uid2 = unis[1]["id"]
    rv = client.put("/api/universities/" + uid2, json={
        "enrollment": 100, "enrollment_year": "2025"})
    assert rv.status_code == 400 and "来源" in rv.get_json()["error"]


def test_migration_v7_source_fields(tmp_path):
    from app.migrate import run_migrations, SCHEMA_VERSION
    from app.storage import Store
    store = Store(data_dir=str(tmp_path / "d"), backup_dir=str(tmp_path / "b"))
    notes = run_migrations(store)
    import json as J
    ver = J.load(open(str(tmp_path / "d") + "/schema_version.json", encoding="utf-8"))
    assert ver["version"] == SCHEMA_VERSION == 7
    assert any("v6→v7" in n for n in notes)
    # 院校:source_url 空串(未核验)+ source_type=official_pending
    for u in store.load("universities"):
        assert u["source_url"] == "" and u["source_type"] == "official_pending"
        assert u["updated_at"] is None  # 不编造核验时间
    # 题目:全部拿到统一字段;来源链接一律为空(不编造),核验时间为空
    qs = store.load("questions")
    assert qs
    assert all("source_url" in q and "verified_at" in q and "updated_at" in q
               and q["source_url"] == "" and q["verified_at"] is None
               for q in qs)
    # 语录/经验帖:迁移函数对三种 license 如实分标(直接单测迁移逻辑)
    from app import migrate as M
    store.save("motivations", [
        {"id": "mo-t1", "text": "a", "author": "荀子·劝学", "license": "公版古籍"},
        {"id": "mo-t2", "text": "b", "author": "大雪深埋", "license": "平台原创"},
        {"id": "mo-t3", "text": "c", "author": "佚名", "license": "来源待核验"},
        {"id": "mo-t4", "text": "d", "author": "我", "license": "自述/公共领域"}])
    store.save("experience_posts", [
        {"id": "ep-t1", "title": "外部", "url": "https://x.com/1"},
        {"id": "ep-t2", "title": "原创", "url": ""}])
    M._v6_to_v7(store)
    types = {m["id"]: m["source_type"] for m in store.load("motivations")}
    assert types["mo-t1"] == "public_classic"
    assert types["mo-t2"] == "platform_original"
    assert types["mo-t3"] == "unverified"
    assert types["mo-t4"] == "user_note"  # 未知 license 不猜
    eps = {p["id"]: p["source_type"] for p in store.load("experience_posts")}
    assert eps == {"ep-t1": "public_experience", "ep-t2": "platform_original"}
    # 幂等:重跑无新增迁移
    assert run_migrations(store) == []


def test_new_content_carries_source_fields(client):
    # 新建语录:source_type 随 license 推导
    rv = client.post("/api/motivations", json={
        "text": "错题是免费的增长点。", "author": "tester",
        "license": "平台原创"})
    assert rv.status_code == 201
    m = rv.get_json()
    assert m["source_type"] == "platform_original" and "updated_at" in m
    # 新建经验帖:带链接=公开经验,无链接=平台原创
    rv = client.post("/api/experience", json={
        "title": "外部经验", "url": "https://zhuanlan.zhihu.com/p/1",
        "author": "路人"})
    assert rv.get_json()["source_type"] == "public_experience"
    rv = client.post("/api/experience", json={"title": "我的方法", "author": "tester"})
    assert rv.get_json()["source_type"] == "platform_original"
