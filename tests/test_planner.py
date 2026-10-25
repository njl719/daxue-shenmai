# -*- coding: utf-8 -*-
"""planner.py 单元测试:薄弱点识别、每日计划、周复盘。"""
import datetime

from app import planner


def D(s):
    return datetime.date.fromisoformat(s)


def mk_mistake(mid, subject="math", lapses=0, next_review=None, kps=None,
               archived=False):
    return {"id": mid, "subject": subject, "qtype": "计算", "difficulty": 3,
            "question_md": "题", "knowledge_ids": kps or [],
            "lapses": lapses, "next_review": next_review, "archived": archived}


def test_weak_by_low_accuracy():
    mistakes = [mk_mistake("mk-1", kps=["kp-a"])]
    records = [
        {"date": "2026-10-01", "subject": "math", "knowledge_ids": ["kp-a"],
         "total": 1, "correct": 1,
         "detail": [{"ref": "r1", "correct": True, "knowledge_ids": ["kp-a"]}]},
    ]
    # 3 次练习只对 1 次 → 薄弱
    for i in range(2):
        records.append({
            "date": "2026-10-0%d" % (i + 2), "subject": "math",
            "knowledge_ids": ["kp-a"], "total": 1, "correct": 0,
            "detail": [{"ref": "r%d" % i, "correct": False, "knowledge_ids": ["kp-a"]}]})
    weak = planner.weak_knowledge_ids(mistakes, records)
    assert "kp-a" in weak


def test_weak_by_lapses():
    mistakes = [mk_mistake("mk-1", lapses=2, kps=["kp-b"])]
    assert "kp-b" in planner.weak_knowledge_ids(mistakes, [])


def test_not_weak_with_enough_correct():
    mistakes = []
    records = [{
        "date": "2026-10-01", "subject": "math", "knowledge_ids": ["kp-c"],
        "total": 4, "correct": 4,
        "detail": [{"ref": "r%d" % i, "correct": True, "knowledge_ids": ["kp-c"]}
                   for i in range(4)]}]
    assert "kp-c" not in planner.weak_knowledge_ids(mistakes, records)


def test_plan_respects_daily_cap():
    settings = {"daily_minutes": 30, "subjects": {
        "math": {"enabled": True, "priority": 1, "minutes": 90},
        "cs408": {"enabled": True, "priority": 2, "minutes": 90},
        "english": {"enabled": True, "priority": 3, "minutes": 45}}}
    mistakes = [mk_mistake("mk-%d" % i, next_review="2026-10-23")
                for i in range(10)]
    tasks = planner.generate_day_plan("2026-10-24", settings, mistakes, [], [], [])
    total = sum(t["est_minutes"] for t in tasks)
    assert total <= 30
    # 到期复习优先于其他科目任务
    kinds = [t["kind"] for t in tasks]
    assert "review" in kinds


def test_plan_skips_disabled_subject():
    settings = {"daily_minutes": 240, "subjects": {
        "math": {"enabled": False, "priority": 1, "minutes": 90},
        "english": {"enabled": True, "priority": 3, "minutes": 45}}}
    mistakes = [mk_mistake("mk-1", subject="math", next_review="2026-10-23")]
    tasks = planner.generate_day_plan("2026-10-24", settings, mistakes, [], [], [])
    assert all(t["subject"] != "math" for t in tasks)


def test_plan_weekly_review_on_sunday():
    settings = {"daily_minutes": 240, "weekly_review_weekday": 6, "subjects": {
        "math": {"enabled": True, "priority": 1, "minutes": 90}}}
    # 2026-10-25 是周日
    tasks = planner.generate_day_plan("2026-10-25", settings, [], [], [], [])
    assert any(t["kind"] == "weekly_review" for t in tasks)
    # 2026-10-26 是周一
    tasks = planner.generate_day_plan("2026-10-26", settings, [], [], [], [])
    assert not any(t["kind"] == "weekly_review" for t in tasks)


def test_no_exam_phase_without_date():
    assert planner.exam_phase(None) is None
    assert planner.exam_phase("bad-date") is None


def test_exam_phase_stages():
    assert planner.exam_phase("2026-12-01", D("2026-10-24"))["phase"].startswith("冲刺")
    assert planner.exam_phase("2027-03-01", D("2026-10-24"))["phase"].startswith("强化")
    assert planner.exam_phase("2027-08-01", D("2026-10-24"))["phase"].startswith("基础")
    assert planner.exam_phase("2026-10-01", D("2026-10-24"))["days_left"] < 0


def test_weekly_summary_counts():
    records = [{"date": "2026-10-20", "subject": "math", "total": 10,
                "correct": 8, "duration_min": 30}]
    mistakes = [{"id": "mk-1", "knowledge_ids": ["kp-a"], "archived": False,
                 "reviews": [{"date": "2026-10-21", "result": "again", "interval": 1}]}]
    plan_days = {"2026-10-20": {"tasks": [
        {"id": "t1", "status": "done"}, {"id": "t2", "status": "skipped"}]}}
    # 2026-10-24 是周六,所在周从 10-19(周一)开始
    s = planner.weekly_summary("2026-10-24", records, mistakes, plan_days)
    assert s["week_start"] == "2026-10-19"
    assert s["reviewed"] == 1 and s["review_again"] == 1
    assert s["tasks_done"] == 1 and s["tasks_skipped"] == 1
    assert s["per_subject"]["math"]["total"] == 10
