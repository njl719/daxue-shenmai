# -*- coding: utf-8 -*-
"""v3 新功能端点测试:目标/里程碑/激励/梦校/资源来源/搜索记录/成长时间线。"""


def test_goals_roundtrip(client):
    rv = client.put("/api/goals", json={
        "institution": "南京大学", "program": "软件学院 电子信息(待核验当年简章)",
        "subjects": ["数学一", "408", "英语一", "政治"],
        "official_links": ["https://yz.nju.edu.cn/"],
        "prep_status": "信息收集"})
    assert rv.status_code == 200
    g = client.get("/api/goals").get_json()
    assert g["institution"] == "南京大学"
    assert g["official_links"] == ["https://yz.nju.edu.cn/"]


def test_milestones_flow(client):
    rv = client.post("/api/goals/milestones", json={
        "title": "完成高数基础篇", "target_date": "2026-12-31"})
    assert rv.status_code == 201
    mid = rv.get_json()["id"]
    rv = client.put("/api/goals/milestones/" + mid, json={
        "done": True, "done_date": "2026-10-25"})
    assert rv.get_json()["done"] is True
    g = client.get("/api/goals").get_json()
    assert any(m["id"] == mid and m["done"] for m in g["milestones"])
    rv = client.post("/api/goals/milestones", json={})
    assert rv.status_code == 400


def test_motivations_crud_and_daily(client):
    rv = client.post("/api/motivations", json={
        "type": "story", "title": "二本到九的故事(待我核验后补链接)",
        "text": "自述类内容示例", "author": "我"})
    assert rv.status_code == 201
    mid = rv.get_json()["id"]
    items = client.get("/api/motivations").get_json()
    assert any(m["id"] == mid for m in items)
    rv = client.get("/api/motivation/daily")
    j = rv.get_json()
    assert j["style"] in ("rational", "gentle", "sprint")
    assert j["quote"]["text"]
    client.delete("/api/motivations/" + mid)


def test_motivation_style_setting(client):
    client.put("/api/account", json={"motivation_style": "sprint",
                                     "display_name": "大雪深埋"})
    j = client.get("/api/motivation/daily").get_json()
    assert j["style"] == "sprint"
    acc = client.get("/api/account").get_json()
    assert acc["display_name"] == "大雪深埋"


def test_institutions_crud(client):
    rv = client.post("/api/institutions", json={
        "name": "北京大学", "program": "微电子学院(候选,须核验当年招生专业)",
        "official_url": "https://www.pku.edu.cn/",
        "prep_status": "关注中", "verified": False})
    assert rv.status_code == 201
    iid = rv.get_json()["id"]
    rv = client.put("/api/institutions/" + iid, json={"prep_status": "已确认科目"})
    assert rv.get_json()["prep_status"] == "已确认科目"
    assert client.post("/api/institutions", json={}).status_code == 400
    assert client.delete("/api/institutions/" + iid).status_code == 200


def test_sources_and_link_check(client):
    # 三个审计过的真实仓库进入来源清单(仅元数据)
    for url, name, license in [
        ("https://github.com/gtqbhksl/22408", "22408 四合一复习工具", "无许可证"),
        ("https://github.com/04megumi/408", "408 复习笔记(TeX)", "无许可证"),
        ("https://github.com/peng38159-eng/exam-intelligence", "考研智库(MIT)", "MIT")]:
        rv = client.post("/api/sources", json={
            "url": url, "name": name, "kind": "repo", "license": license,
            "status": "仅链接" if license == "无许可证" else "可引用",
            "notes": "审计结论见 docs/RESOURCES.md"})
        assert rv.status_code == 201
    items = client.get("/api/sources").get_json()
    assert len(items) == 3
    sid = items[0]["id"]
    # 链接核验(GitHub 页面可访问;若网络受限,接口也应如实记录结果而非崩溃)
    rv = client.post("/api/sources/%s/check" % sid)
    assert rv.status_code == 200
    j = rv.get_json()
    assert j["last_checked"]
    assert j["check_result"]


def test_sources_validation(client):
    assert client.post("/api/sources", json={}).status_code == 400
    assert client.post("/api/sources/nonexist/check").status_code in (400, 404)


def test_search_github_validation_and_record(client):
    assert client.get("/api/search/github").status_code == 400
    # 真实搜索(公开 API);网络受限时接口应返回 502 而非崩溃
    rv = client.get("/api/search/github?q=考研+408")
    if rv.status_code == 200:
        j = rv.get_json()
        assert isinstance(j["items"], list)
        recs = client.get("/api/search/records").get_json()
        assert recs and recs[0]["provider"] == "github"
    else:
        assert rv.status_code == 502


def test_growth_timeline_and_heatmap(client):
    client.post("/api/records", json={"subject": "math", "total": 5, "correct": 4,
                                      "duration_min": 25, "detail": []})
    client.post("/api/reflections", json={
        "raw_text": "测试反思", "confirmed": True,
        "extracted": {"source": "rule", "content": "测试反思", "subjects": ["math"]}})
    tl = client.get("/api/growth/timeline").get_json()
    assert tl and tl[0]["date"]
    today_entry = [d for d in tl if d["events"]][0]
    assert today_entry["events"]
    hm = client.get("/api/growth/heatmap").get_json()
    assert len(hm["weeks"]) == 26
    assert all(len(w) == 7 for w in hm["weeks"])
