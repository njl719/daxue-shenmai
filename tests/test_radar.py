# -*- coding: utf-8 -*-
"""热点雷达(V3.1)测试:全流程 mock 网络,CI 安全。

覆盖:检索→筛选→评分→入库→去重→过期→个性化→反馈→提交→API 端点。
"""
import datetime

import pytest

from app import radar as R


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    """本模块禁用真实 AI 调用:统一走规则引擎,测试快速且不依赖 Ollama。"""
    from app import ai as AI
    monkeypatch.setattr(AI, "get_ai_config", lambda settings: {"available": False})


# ---------------------------------------------------------------- 纯逻辑

def test_dedup_hash_ignores_tracking_and_space():
    a = R.dedup_hash("https://Example.com/x/?utm_source=wb&from=x", "标题 一")
    b = R.dedup_hash("https://example.com/x", "标题一")
    assert a == b


def test_classify_types():
    assert R.classify({"title": "2027年全国硕士研究生招生考试网上报名公告",
                       "snippet": "", "official": True})[0] == "policy"
    assert R.classify({"title": "27考研数学错题复盘三步法", "snippet": ""})[0] == "method"
    assert R.classify({"title": "考研焦虑失眠怎么调整心态", "snippet": ""})[0] == "mindset"
    assert R.classify({"title": "二战跨考上岸经验贴", "snippet": ""})[0] == "exp"
    ctype, hits = R.classify({"title": "保过班不过退费", "snippet": "限时优惠"})
    assert ctype == "warn" and hits


def test_score_item_bounds_and_breakdown():
    item = {"title": "27考研英语阅读方法与复盘技巧", "summary": "正确率提升的步骤清单",
            "url": "https://zhuanlan.zhihu.com/p/1",
            "published_at": datetime.date.today().isoformat(),
            "ctype": "method", "subject": "english", "stage": "强化"}
    sc = R.score_item(item, {"subjects": ["english"], "target_school": "",
                             "stage": "强化", "ctype_weights": {}}, [])
    bd = sc["breakdown"]
    assert 0 <= sc["total"] <= 100
    assert bd["时效"] == 25  # 今天发布
    assert bd["来源"] == 15  # 知乎
    assert sum(v for k, v in bd.items() if k != "偏好修正") <= 100
    assert sc["rationale"]  # 评分依据必须保留


def test_score_penalizes_old_and_unknown_dates():
    fresh = {"title": "t", "summary": "", "url": "https://a.com/1", "ctype": "hot",
             "subject": "general", "stage": "通用",
             "published_at": datetime.date.today().isoformat()}
    old = dict(fresh, url="https://a.com/2", published_at="2020-01-01")
    none_d = {k: v for k, v in fresh.items() if k != "published_at"}
    none_d["url"] = "https://a.com/3"
    ctx = {"subjects": [], "target_school": "", "stage": "", "ctype_weights": {}}
    s_new = R.score_item(fresh, ctx, [])
    s_old = R.score_item(old, ctx, [])
    s_none = R.score_item(none_d, ctx, [])
    assert s_old["breakdown"]["时效"] < s_none["breakdown"]["时效"] < s_new["breakdown"]["时效"]


def test_extract_date_variants():
    page_meta = '<meta property="article:published_time" content="2026-10-20T08:00:00Z">'
    assert R.extract_date(page_meta, "https://x.com/a") == "2026-10-20"
    assert R.extract_date("", "https://x.com/20261022/a/") == "2026-10-22"
    assert R.extract_date("正文里出现 2026/10/18 的日期", "https://x.com/a") == "2026-10-18"
    assert R.extract_date("没有任何日期", "https://x.com/a") is None


def test_keyword_rotation_no_recent_repeat():
    state = {"keywords_used": {}}
    k1 = set(R.pick_keywords(state, 6))
    state["keywords_used"][datetime.date.today().isoformat()] = list(k1)
    k2 = set(R.pick_keywords(state, 6))
    assert not (k1 & k2)  # 池子够大时,同一天二刷不重复
    # 池子全部用尽 → 允许重置(诚实轮转)
    for i in range(30):
        state["keywords_used"][(datetime.date.today() - datetime.timedelta(days=i)).isoformat()] = k1 | k2
    assert R.pick_keywords(state, 6)  # 不崩,返回重置后的池


# ---------------------------------------------------------------- 刷新流程(mock 网络)

_T = datetime.date.today()
FAKE_DDG = [
    {"title": "27考研数学强化错题复盘方法(新)", "url": "https://zhuanlan.zhihu.com/p/new1",
     "snippet": "错题复盘的具体步骤与时间安排"},
    {"title": "27考研数学强化错题复盘方法(旧文)",
     "url": "https://kaoyan.xdf.cn/%s/1.html" % (_T - datetime.timedelta(days=400)).strftime("%Y%m"),
     "snippet": "方法与复盘技巧"},
    {"title": "保过班不过退费限时优惠速抢", "url": "https://shop.example.com/x",
     "snippet": "全程班优惠券"},
]
FAKE_CHSI = [
    {"title": "某大学2027年硕士研究生招生简章发布",
     "url": "https://yz.chsi.com.cn/kyzx/kydt/%s/1.html" % (_T - datetime.timedelta(days=1)).strftime("%Y%m%d"),
     "snippet": "研招网考研资讯栏目官方发布。",
     "published_at": (_T - datetime.timedelta(days=1)).isoformat(), "official": True},
]


@pytest.fixture
def mock_net(monkeypatch):
    calls = {"ddg": 0, "chsi": 0, "pages": 0}

    def fake_search(query, proxy, timeout=15):
        calls["ddg"] += 1
        return [dict(c, via_query=query) for c in FAKE_DDG]

    def fake_chsi(proxy):
        calls["chsi"] += 1
        return [dict(c) for c in FAKE_CHSI]

    def fake_http_text(url, proxy, timeout=12, data=None, referer=None):
        calls["pages"] += 1
        if "zhihu" in url:
            return ('<html><meta property="article:published_time" content="%s">'
                    % (_T - datetime.timedelta(days=2)).isoformat())
        if "xdf" in url:
            return "<html>%s 发布</html>" % (_T - datetime.timedelta(days=400)).isoformat()
        raise PermissionError("403")

    monkeypatch.setattr(R, "search_ddg", fake_search)
    monkeypatch.setattr(R, "fetch_chsi", fake_chsi)
    monkeypatch.setattr(R, "http_text", fake_http_text)
    return calls


def test_refresh_filters_marketing_and_dedups(client, mock_net, monkeypatch):
    monkeypatch.setattr(R.time, "sleep", lambda s: None)  # 测试不等待限速
    store = client.store
    s1 = R.refresh(store, {"radar": {"proxy": None, "max_queries": 2}})
    items = store.load("radar")
    # 2 组关键词×3 条(同内容去重后 3)+ 研招网 1 = 候选 7;营销强命中被拒,入库 3
    assert s1["candidates"] == 7 and s1["added"] == 3
    titles = " ".join(i["title"] for i in items)
    assert "保过" not in titles
    assert any(i["ctype"] == "policy" for i in items)
    assert any(i["ctype"] == "method" for i in items)
    # 原文核验:知乎拿到日期;xdf 页面拿到旧日期 → 更早桶
    zh = next(i for i in items if "zhihu" in i["url"])
    assert zh["published_at"] == (_T - datetime.timedelta(days=2)).isoformat()
    assert zh["verify_status"] == "verified_page"
    # 第二次刷新:已入库的全部判重(含两组关键词之间的组内重复);营销条不入库,走拒绝
    s2 = R.refresh(store, {"radar": {"proxy": None, "max_queries": 2}})
    assert s2["duplicates"] == 5 and s2["added"] == 0
    assert len(store.load("radar")) == 3


def test_refresh_all_fail_keeps_data_and_records_reason(client, monkeypatch):
    store = client.store
    store.save("radar", [{"id": "rd-keep", "title": "旧数据", "summary": "", "url": "https://a.com/1",
                          "platform": "a.com", "ctype": "hot", "dedup_hash": "h1",
                          "feedback": {}, "verify_status": "snippet_only"}])
    def boom(query, proxy, timeout=15):
        raise OSError("网络不可用")

    def boom2(proxy):
        raise OSError("网络不可用")

    monkeypatch.setattr(R, "search_ddg", boom)
    monkeypatch.setattr(R, "fetch_chsi", boom2)
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    stats = R.refresh(store, {"radar": {"proxy": None, "max_queries": 2}})
    assert stats["candidates"] == 0
    state = store.load("radar_state")
    assert state["failure_reason"] and state["last_success"] is None
    assert len(store.load("radar")) == 1  # 旧数据保留,不伪造热点


def test_expire_pass_marks_old(client):
    store = client.store
    old = datetime.date.today() - datetime.timedelta(days=400)
    store.save("radar", [{"id": "rd-old", "title": "过期内容", "summary": "", "url": "https://a.com/1",
                          "platform": "a.com", "ctype": "policy", "dedup_hash": "h1",
                          "feedback": {}, "published_at": old.isoformat(),
                          "expires_at": (old + datetime.timedelta(days=365)).isoformat()}])
    n = R.expire_pass(store)
    assert n == 1 and store.load("radar")[0]["ctype"] == "expired"


# ---------------------------------------------------------------- 个性化

def test_snapshot_and_need_baseline(client):
    store = client.store  # 新库无学习记录
    snap = R.user_snapshot(store, {})
    assert snap["has_records"] is False
    assert R.pick_need(snap) == "baseline"


def test_daily_brief_uses_real_records(client):
    store = client.store
    today = datetime.date.today()
    store.save("records", [
        {"date": today.isoformat(), "subject": "math", "correct": False, "qid": "q1"},
        {"date": today.isoformat(), "subject": "math", "correct": False, "qid": "q2"},
        {"date": today.isoformat(), "subject": "math", "correct": False, "qid": "q3"},
    ])
    store.save("mistakes", [{"id": "m1", "resolved": False, "due": today.isoformat(),
                             "error_tag": "计算失误", "knowledge_ids": ["k1"]}])
    card = R.build_daily_brief(store, {})
    assert card["need"] in ("math_method", "cs408_method", "shrink", "maintain", "restart")
    assert card["why"] and card["action"] and card["metric"]
    assert card["generator"] in ("rule", "ai")
    state = store.load("radar_state")
    assert state["daily_card"]["date"] == today.isoformat()


# ---------------------------------------------------------------- API 端点

def test_radar_endpoints_flow(client, mock_net, monkeypatch):
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    # 刷新入库
    r = client.post("/api/radar/refresh")
    assert r.status_code == 200 and r.get_json()["stats"]["added"] == 3
    # 列表:7 天桶 = 研招网官方(昨天)+ 知乎方法(2 天前,已核验原文)
    r = client.get("/api/radar?bucket=7")
    d = r.get_json()
    assert d["total"] == 2
    item = d["items"][0]  # 评分排序:官方政策在前
    assert item["ctype"] == "policy"
    assert item["published_at"] and item["verify_status"] == "verified_page"
    assert item["score"]["total"] >= 30
    # 反馈:有用/收藏/隐藏
    rid = item["id"]
    assert client.post("/api/radar/feedback", json={"id": rid, "action": "useful"}).get_json()["ok"]
    assert client.post("/api/radar/feedback", json={"id": rid, "action": "favorite"}).get_json()["favorite"]
    client.post("/api/radar/feedback", json={"id": rid, "action": "hide"})
    d2 = client.get("/api/radar?bucket=7").get_json()
    assert d2["total"] == 1  # 隐藏后不再出现
    # 首页聚合诚实工作
    home = client.get("/api/radar/home").get_json()
    assert home["brief"]["action"] and home["status"]["last_success"]
    # 行动卡反馈
    assert client.post("/api/radar/brief/feedback", json={"action": "useful"}).get_json()["ok"]


def test_radar_settings_validation(client):
    assert client.get("/api/radar/settings").get_json()["max_queries"] == 6
    r = client.post("/api/radar/settings", json={"proxy": "ftp://bad"})
    assert r.status_code == 400
    r = client.post("/api/radar/settings", json={"max_queries": 99})
    assert r.status_code == 400
    r = client.post("/api/radar/settings", json={"proxy": "", "max_queries": 4})
    assert r.get_json()["ok"]


def test_radar_submit_user_link(client):
    r = client.post("/api/radar/submit", json={
        "url": "https://www.xiaohongshu.com/explore/abc123",
        "title": "小红书考研作息帖(用户自录)",
        "note": "评论区讨论很真实", "published_at": "2026-10-22"})
    assert r.status_code == 201
    item = r.get_json()
    assert item["verify_status"] == "user_submitted"
    assert item["platform"] == "小红书"
    assert item["submitted_by"] == "tester"
    # 重复提交被去重拦截
    r2 = client.post("/api/radar/submit", json={
        "url": "https://www.xiaohongshu.com/explore/abc123", "title": "小红书考研作息帖(用户自录)"})
    assert r2.status_code == 400
    # 非法 URL 拒绝
    assert client.post("/api/radar/submit", json={"url": "javascript:alert(1)", "title": "x"}).status_code == 400


def test_radar_reverify_dead_link_marks_expired(client, monkeypatch):
    store = client.store
    store.save("radar", [{"id": "rd-dead", "title": "死链", "summary": "", "url": "https://a.com/404",
                          "platform": "a.com", "ctype": "hot", "dedup_hash": "h9",
                          "feedback": {}, "verify_status": "snippet_only"}])
    import urllib.error
    def not_found(url, proxy, timeout=12, data=None, referer=None):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    monkeypatch.setattr(R, "http_text", not_found)
    r = client.post("/api/radar/reverify", json={"id": "rd-dead"})
    d = r.get_json()
    assert d["ok"] is False and "404" in d["message"]
    assert store.load("radar")[0]["ctype"] == "expired"


def test_unauthenticated_blocked(client):
    # 退出会话后,雷达接口必须 401
    client.store.save("sessions", [])
    assert client.get("/api/radar").status_code == 401
    assert client.post("/api/radar/refresh").status_code == 401
