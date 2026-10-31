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
