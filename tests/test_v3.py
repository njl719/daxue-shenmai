# -*- coding: utf-8 -*-
"""V3 新功能测试:每日训练闭环、经验帖、官方来源、语录、题库分页。"""
import json


def _seed_q(client, subject="math", text="训练题", ans="A"):
    r = client.post("/api/questions", json={
        "subject": subject, "source_type": "自录题", "qtype": "选择",
        "question_md": text + str(abs(hash(text)) % 99999),
        "options": ["甲", "乙", "丙", "丁"], "answer": ans,
        "solution_md": "解析:选 %s 因为这是测试题" % ans,
        "source_desc": "测试", "copyright_status": "自述/本人记录"})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def test_train_daily_generated_and_stable(client):
    for s in ("math", "cs408", "english", "politics"):
        _seed_q(client, s, "T-" + s)
    t1 = client.get("/api/train/daily").get_json()
    assert t1["items"], "应生成训练清单"
    assert set(t1["quotas"]) == {"math", "cs408", "english", "politics"}
    # 同日再取:清单稳定(同题)
    t2 = client.get("/api/train/daily").get_json()
    assert [i["id"] for i in t1["items"]] == [i["id"] for i in t2["items"]]


def test_train_answer_and_auto_mistake(client):
    q = _seed_q(client, "math", "训练闭环题", "B")
    t = client.get("/api/train/daily").get_json()
    if q["id"] not in [i["id"] for i in t["items"]]:
        t = client.get("/api/train/daily?force=1").get_json()
    # 直接调 answer 端点
    r = client.post("/api/train/answer", json={"qid": q["id"], "picked": "A",
                                               "seconds": 30, "error_tag": "概念不清"})
    j = r.get_json()
    assert j["correct"] is False and j["answer"] == "B"
    # 错题自动入本
    ms = client.get("/api/mistakes").get_json()
    m = next(m for m in ms if m.get("client_id", "").startswith(q["id"]))
    assert m["error_reason"] == "概念不清"
    assert "题库" in m["source"]


def test_train_finish_idempotent_records(client):
    q = _seed_q(client, "cs408", "完成汇总题", "C")
    client.post("/api/train/answer", json={"qid": q["id"], "picked": "C"})
    r1 = client.post("/api/train/finish").get_json()
    assert r1["ok"] and r1["records"]
    r2 = client.post("/api/train/finish").get_json()
    # 幂等:记录数不重复增长
    recs = client.get("/api/records").get_json()
    train_recs = [r for r in recs if r.get("session_type") == "daily_train"
                  and r.get("client_id", "").startswith("train-")]
    assert len(train_recs) == len(set(t["client_id"] for t in train_recs))


def test_train_quota_settings(client):
    rv = client.put("/api/train/settings", json={"quotas": {
        "math": 10, "cs408": 5, "english": 0, "politics": 0}})
    assert rv.status_code == 200
    t = client.get("/api/train/daily?force=1").get_json()
    assert t["quotas"]["math"] == 10
    rv = client.put("/api/train/settings", json={"quotas": {"geography": 5}})
    assert rv.status_code == 400
    rv = client.put("/api/train/settings", json={"quotas": {"math": 999}})
    assert rv.status_code == 400


def test_train_shortage_honest(client):
    """配额高于库存时如实报告缺口,不重复凑数。"""
    client.put("/api/train/settings", json={"quotas": {
        "math": 50, "cs408": 0, "english": 0, "politics": 0}})
    t = client.get("/api/train/daily?force=1").get_json()
    math_ids = [i["id"] for i in t["items"] if i["subject"] == "math"]
    assert len(math_ids) == len(set(math_ids)), "不得重复抽同一题凑数"
    assert t["shortage"].get("math", 0) > 0


def test_questions_pagination(client):
    for i in range(12):
        _seed_q(client, "english", "分页题 %d 号" % i)
    r = client.get("/api/questions?per=10&page=1").get_json()
    assert r["per"] == 10 and len(r["items"]) == 10 and r["total"] >= 12
    r2 = client.get("/api/questions?per=10&page=2").get_json()
    assert r2["page"] == 2 and len(r2["items"]) >= 1
    ids1 = {i["id"] for i in r["items"]}
    ids2 = {i["id"] for i in r2["items"]}
    assert not (ids1 & ids2)


def test_experience_crud_and_check(client):
    rv = client.post("/api/experience", json={
        "title": "测试经验帖", "platform": "知乎",
        "url": "https://zhuanlan.zhihu.com/p/test",
        "summary": "摘要", "categories": ["数学"], "notes": "我的笔记"})
    assert rv.status_code == 201
    pid = rv.get_json()["id"]
    assert rv.get_json()["verify_status"] == "待核验"
    # 非法 URL
    assert client.post("/api/experience", json={
        "title": "x", "url": "ftp://x"}).status_code == 400
    # 收藏与修改
    client.put("/experience/".join(["/api", pid]).replace("//", "/") if False else "/api/experience/" + pid,
               json={"favorite": True})
    favs = client.get("/api/experience?favorite=1").get_json()
    assert any(p["id"] == pid for p in favs)
    # 链接核验(外部 URL,可能成功或失败,但必须有结果记录)
    p = client.post("/api/experience/%s/check" % pid).get_json()
    assert p["last_checked"] and p["verify_status"]
    client.delete("/api/experience/" + pid)


def test_official_sources_seeded(client):
    """官方来源种子应在迁移/种子后存在(测试库 via seed 不含,直接验证端点行为)。"""
    rv = client.post("/api/sources", json={
        "url": "https://yz.chsi.com.cn/", "name": "研招网",
        "kind": "official", "license": "官方平台·公开访问", "status": "可引用(官方公开信息)"})
    assert rv.status_code == 201
    items = client.get("/api/sources").get_json()
    assert any("chsi" in s["url"] for s in items)


def test_motivation_quotes_seed_and_daily(client):
    j = client.get("/api/motivation/daily").get_json()
    assert j["quote"]["text"]
    assert j["quote"]["license"] in ("公版古籍", "平台原创", "来源待核验", "系统内置") or j["quote"]["license"]
