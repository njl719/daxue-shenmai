# -*- coding: utf-8 -*-
"""V2.0 决策与情报中心测试:persona/模拟成绩/决策引擎/十类分类/可信度等级/招生数据校验。"""
import json

from app import decision as D
from app import trust as T


# ---------------- persona ----------------

def test_persona_defaults_and_update(client):
    p = client.get("/api/persona").get_json()
    assert p["exam_year"] == 2028 and p["bachelor_school"] == "武汉商学院"
    assert p["bachelor_major"] == "软件工程" and p["plan"] == "11408"
    rv = client.put("/api/persona", json={"exam_year": 2029, "directions": ["人工智能"]})
    assert rv.get_json()["exam_year"] == 2029
    assert client.put("/api/persona", json={"exam_year": 2099}).status_code == 400
    assert client.put("/api/persona", json={"directions": "不是列表"}).status_code == 400


# ---------------- mock scores ----------------

def test_mock_scores_crud_and_validation(client):
    assert client.post("/api/mock-scores", json={
        "subject": "math", "month": "2026-09", "score": 98}).status_code == 201
    assert client.post("/api/mock-scores", json={
        "subject": "cs408", "month": "2026-09", "score": 88}).status_code == 201
    # 校验:坏月份 / 非数字 / 超满分 / 非法科目
    assert client.post("/api/mock-scores", json={
        "subject": "math", "month": "2026/09", "score": 90}).status_code == 400
    assert client.post("/api/mock-scores", json={
        "subject": "math", "month": "2026-10", "score": "abc"}).status_code == 400
    assert client.post("/api/mock-scores", json={
        "subject": "math", "month": "2026-10", "score": 999}).status_code == 400
    assert client.post("/api/mock-scores", json={
        "subject": "bad", "month": "2026-10", "score": 90}).status_code == 400
    d = client.get("/api/mock-scores").get_json()
    assert len(d["items"]) == 2 and "math" in d["summary"]


# ---------------- decision engine:诚实性优先 ----------------

def test_probability_honest_when_insufficient(client):
    d = client.get("/api/decision/probability/tsinghua").get_json()
    assert d["ok"] and d["reliable"] is False
    assert d["reasons"] and any("复试线" in r for r in d["reasons"])
    assert any("模拟" in r for r in d["reasons"])


def test_match_score_separate_from_probability(client):
    rec = client.get("/api/decision/recommend").get_json()
    assert rec["items"] and "匹配度" in rec["note"]
    tsinghua = next(i for i in rec["items"] if i["name"] == "清华大学")
    assert tsinghua["tier"] is None  # 无官方数据 → 不分层(不编造)
    assert tsinghua["match"]["score"] is not None  # 但匹配度可算


def test_probability_with_data_is_explainable(client):
    store = client.store
    # 注入测试用"已核验官方数据"(测试装置,非生产数据)
    recs = store.load("admission_records")
    tid = next(r["uni_id"] for r in recs if r["uni_name"] == "清华大学")
    for r in recs:
        if r["uni_id"] == tid:
            r["retest_line"] = {"2026": 352, "2027": 358}.get(str(r["year"]))
            r["plan_total"] = 20
            r["source_name"] = "测试官方数据"
    store.save("admission_records", recs)
    for sub, sc in (("math", 105), ("cs408", 108), ("english", 72), ("politics", 68)):
        store.save("mock_scores", store.load("mock_scores") + [{
            "id": "mkx-" + sub, "month": "2026-10", "subject": sub, "score": sc,
            "full_mark": D.FULL_MARKS[sub]}])
    d = client.get("/api/decision/probability/" + tid).get_json()
    assert d["ok"] and d["reliable"] is True
    assert 0 <= d["p_pass_line"] <= 1 and 0 <= d["p_final"] <= d["p_pass_line"]
    assert d["assumptions"] and d["confidence"] in ("低", "中", "高")
    assert d["targets"]["retest_line_mean"] == 355
    assert set(d["scenarios"]) == {"乐观", "基准", "保守"}


def test_higher_score_higher_probability(client):
    """模型单调性:分数越高,录取概率不降(可解释模型的基本性质)。"""
    store = client.store
    recs = store.load("admission_records")
    tid = next(r["uni_id"] for r in recs if r["uni_name"] == "清华大学")
    for r in recs:
        if r["uni_id"] == tid:
            r["retest_line"] = {"2026": 352, "2027": 358}.get(str(r["year"]))
    store.save("admission_records", recs)
    base = [{"id": "mkx-" + s, "month": "2026-10", "subject": s, "score": sc,
             "full_mark": D.FULL_MARKS[s]}
            for s, sc in (("math", 105), ("cs408", 108), ("english", 72), ("politics", 68))]

    def probs(mult):
        store.save("mock_scores", [dict(m, score=m["score"] * mult) for m in base])
        d = client.get("/api/decision/probability/" + tid).get_json()
        return d["p_final"]
    low, high = probs(0.7), probs(1.15)
    assert high >= low


# ---------------- admission records ----------------

def test_admission_update_requires_source(client):
    recs = client.get("/api/admission/records?year=2027").get_json()["items"]
    rid = recs[0]["id"]
    rv = client.put("/api/admission/records/" + rid, json={
        "retest_line": 340, "source_name": "", "source_url": ""})
    assert rv.status_code == 400 and "来源" in rv.get_json()["error"]
    rv = client.put("/api/admission/records/" + rid, json={
        "retest_line": 340, "source_name": "哈工大研究生院官网",
        "source_url": "https://yz.hit.edu.cn/"})
    assert rv.status_code == 200
    ch = client.get("/api/admission/changes").get_json()
    assert ch and ch[0]["changes"][0]["field"] == "retest_line"
    assert ch[0]["year"] == recs[0]["year"]


def test_admission_2028_marked_unpublished(client):
    items = client.get("/api/admission/records?year=2028").get_json()["items"]
    assert items and all(r["data_status"].startswith("官方未公开") for r in items)
    assert all(r["plan_total"] is None and r["retest_line"] is None for r in items)


# ---------------- 分类与可信度等级 ----------------

def test_category_mapping():
    R = __import__("app.radar", fromlist=["x"])
    assert R.classify_category("hot", "27考研择校指南:报录比怎么查") == "choose"
    assert R.classify_category("hot", "二战失败复盘,我错在哪") == "fail"
    assert R.classify_category("method", "英语阅读刷题方法") == "method"
    assert R.classify_category("mindset", "考研焦虑") == "mind"
    assert R.classify_category("warn", "这些坑别踩") == "avoid"
    assert R.classify_category("policy", "2027 招生简章") == "hot"


def test_trust_levels():
    assert T.radar_level({"platform": "研招网(官方)"}) == "S"
    assert T.radar_level({"platform": "GitHub", "verify_status": "api"}) == "A"
    assert T.radar_level({"platform": "知乎", "verify_status": "snippet_only"}) == "B"
    assert T.question_level({"source_type": "AI 生成练习题", "ai_generated": True}) == "AI"
    assert T.question_level({"source_type": "真题", "verified_at": None}) == "B"
    assert T.motivation_level({"source_type": "public_classic"}) == "S"
    assert T.university_level({"verified_at": "x", "admission_source": "y"}) == "S"


def test_radar_api_returns_category_and_level(client, monkeypatch):
    R = __import__("app.radar", fromlist=["x"])
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    monkeypatch.setattr(R, "search_ddg", lambda q, p, timeout=15: [
        {"title": "27考研择校 报录比解析", "url": "https://zhuanlan.zhihu.com/p/v2x",
         "snippet": "择校与报录比方法"}])
    monkeypatch.setattr(R, "fetch_chsi", lambda p: [])
    monkeypatch.setattr(R, "search_github", lambda q: [])
    client.post("/api/radar/refresh")
    d = client.get("/api/radar?bucket=all").get_json()
    assert "categories" in d and "levels" in d
    for i in d["items"]:
        assert "category" in i and "source_level" in i
        assert i["source_level"] in ("S", "A", "B", "AI", None)
