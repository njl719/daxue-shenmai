# -*- coding: utf-8 -*-
"""profile.py 测试:薄弱点证据链、状态模型、周报九问。"""
import datetime

from app import profile


TODAY = datetime.date(2026, 10, 24)


def mk(m_id, kps, lapses=0, subject="math", reviews=None, error_reason="", created="2026-10-20"):
    return {"id": m_id, "subject": subject, "knowledge_ids": kps, "lapses": lapses,
            "archived": False, "reviews": reviews or [], "error_reason": error_reason,
            "created": created, "question_md": "求极限 lim(x→0) (tan x-sin x)/x^3"}


def kp(k_id, name, subject="math", status="not_started"):
    return {"id": k_id, "name": name, "subject": subject, "status": status}


def test_new_user_no_weak_labels():
    """验收标准 9:新用户不被随意贴薄弱标签。"""
    wp = profile.compute_weak_points([], [], [], [], TODAY)
    assert wp == []


def test_weak_from_repeated_lapses():
    ms = [mk("mk-1", ["kp-a"], lapses=2)]
    wp = profile.compute_weak_points(ms, [], [], [kp("kp-a", "等价无穷小")], TODAY)
    assert len(wp) == 1
    w = wp[0]
    assert w["status"] == "confirmed"
    assert w["confidence"] >= 0.5
    assert any("错题" in e["text"] for e in w["evidence"])
    assert w["recommended_action"]


def test_weak_from_low_accuracy():
    records = [{"date": "2026-10-20", "subject": "math", "knowledge_ids": ["kp-b"],
                "total": 3, "correct": 1,
                "detail": [{"ref": "r1", "correct": False, "knowledge_ids": ["kp-b"]},
                            {"ref": "r2", "correct": False, "knowledge_ids": ["kp-b"]},
                            {"ref": "r3", "correct": True, "knowledge_ids": ["kp-b"]}]}]
    wp = profile.compute_weak_points([], records, [], [kp("kp-b", "中值定理")], TODAY)
    assert len(wp) == 1 and wp[0]["status"] == "confirmed"
    assert "正确率" in wp[0]["evidence"][0]["text"]


def test_reflection_only_is_suspected():
    """反思说薄弱但没有练习数据 → 待验证,不是结论。"""
    refs = [{"id": "rf-1", "date": "2026-10-23",
             "extracted": {"subjects": ["math"], "weak_points": ["积分换元思路"]}}]
    wp = profile.compute_weak_points([], [], refs, [], TODAY)
    assert len(wp) == 1
    assert wp[0]["status"] == "suspected"
    assert wp[0]["confidence"] <= 0.4


def test_reflection_conflicts_with_practice():
    """反思说薄弱但练习数据不差 → 标记矛盾,待辨析。"""
    refs = [{"id": "rf-1", "date": "2026-10-23",
             "extracted": {"subjects": ["math"], "weak_points": ["等价无穷小"]}}]
    records = [{"date": "2026-10-22", "subject": "math",
                "knowledge_ids": [], "total": 5, "correct": 5,
                "detail": [{"ref": "r", "correct": True, "knowledge_ids": []}]}]
    # 知识点名与反思标签匹配,练习全对 → conflict
    ks = [kp("kp-a", "等价无穷小替换")]
    records[0]["knowledge_ids"] = ["kp-a"]
    records[0]["detail"][0]["knowledge_ids"] = ["kp-a"]
    wp = profile.compute_weak_points([], records, refs, ks, TODAY)
    assert len(wp) == 1
    assert wp[0]["status"] == "conflict"
    assert "矛盾" in wp[0]["judgment"] or "辨析" in wp[0]["judgment"]


def test_status_model_six_levels():
    assert profile.STATUS_TXT["consolidating"] == "需要巩固"
    assert profile.norm_status("reviewing") == "initial"  # 旧数据兼容
    assert profile.norm_status("mastered") == "mostly"


def test_error_patterns_counts():
    ms = [mk("mk-1", ["kp-a"], error_reason="计算失误",
             reviews=[{"date": "2026-10-23", "result": "again", "interval": 1}]),
          mk("mk-2", ["kp-b"], error_reason="计算失误",
             reviews=[{"date": "2026-10-23", "result": "again", "interval": 1}])]
    pats = profile.error_patterns(ms, days=7, today=TODAY)
    assert pats[0]["reason"] == "计算失误"
    assert pats[0]["count"] >= 2


def test_weekly_report_nine_questions():
    records = [{"date": "2026-10-21", "subject": "math", "total": 10, "correct": 8,
                "duration_min": 40, "detail": []}]
    mistakes = [mk("mk-1", ["kp-a"], error_reason="计算失误",
                   reviews=[{"date": "2026-10-22", "result": "again", "interval": 1}])]
    reflections = [{"id": "rf-1", "date": "2026-10-21",
                    "extracted": {"content": "做了强化题", "weak_points": ["积分换元"]}}]
    plan_days = {"2026-10-21": {"tasks": [
        {"id": "t1", "status": "done", "kind": "review", "title": "复习错题"},
        {"id": "t2", "status": "skipped", "kind": "study", "title": "学习新知"}]}}
    r = profile.weekly_report("2026-10-24", records, mistakes, reflections,
                              plan_days, [], TODAY)
    assert r["week_start"] == "2026-10-19"
    assert r["tasks"]["done"] == 1 and r["tasks"]["skipped"] == 1
    assert r["per_subject"]["math"]["accuracy"] == 80
    assert r["review"]["total"] == 1 and r["review"]["again"] == 1
    assert any("计算失误" == p["reason"] for p in r["error_patterns"])
    assert r["compare"]["this_week"]["total"] == 10
    assert r["compare"]["last_week"]["total"] == 0
    assert r["next_week_advice"] and len(r["next_week_advice"]) <= 3
    # 不足 5 题?本周 10 题 → 不该报练习量不足
    assert not any("练习量不足" in g for g in r["data_gaps"])


def test_weekly_report_flags_sparse_data():
    r = profile.weekly_report("2026-10-24", [], [], [], {}, [], TODAY)
    assert any("反思" in g or "练习" in g or "学习" in g for g in r["data_gaps"])
    assert "数据不足" in r["next_week_advice"][0] or "补" in r["next_week_advice"][0]


def test_profile_no_score_only_output():
    """画像不是单一分数:有状态分布与缺口提示。"""
    prof = profile.compute_profile(
        [], [], [], [kp("kp-a", "x"), kp("kp-b", "y", status="learning")],
        {}, {}, TODAY)
    assert prof["subjects"]["math"]["status_dist"]["learning"] == 1
    assert prof["subjects"]["math"]["progress_pct"] == 50
    assert any("练习记录" in g for g in prof["data_gaps"])
