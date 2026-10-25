# -*- coding: utf-8 -*-
"""复习计划引擎。纯函数集合,便于单元测试。

原则:
- 只在用户设定的每日时间内排任务,装不下就少排;
- 到期复习优先于新任务;薄弱知识点练习优先于新知学习;
- 任务粒度可手动调整(done/skip/move),算法不越权。
"""
import datetime
import uuid

from . import srs

MINUTES_PER_MISTAKE = 2.5
MINUTES_PER_VOCAB = 1.0
STUDY_BLOCK_MINUTES = 30
PRACTICE_TASK_ITEMS = 6
WEAK_ACCURACY = 0.60   # 正确率低于此值且练习>=3次 → 薄弱
WEAK_MIN_ATTEMPTS = 3
WEAK_LAPSES = 2        # 反复出错次数达到此值 → 薄弱


def parse_date(s):
    return datetime.date.fromisoformat(s)


def exam_phase(exam_date, today=None):
    """返回 {days_left, phase} 或 None。阶段划分是建议性的,不锁定计划。"""
    if not exam_date:
        return None
    today = today or datetime.date.today()
    try:
        exam = parse_date(exam_date)
    except (ValueError, TypeError):
        return None
    days_left = (exam - today).days
    if days_left < 0:
        phase = "已考完,请更新设置"
    elif days_left <= 45:
        phase = "冲刺阶段(真题+查漏)"
    elif days_left <= 150:
        phase = "强化阶段(专题+综合)"
    else:
        phase = "基础阶段(教材+基础题)"
    return {"days_left": days_left, "phase": phase}


def knowledge_accuracy(records):
    """由练习记录统计每个知识点的 (尝试数, 正确数)。"""
    stats = {}
    for rec in records:
        for d in rec.get("detail") or []:
            for kid in d.get("knowledge_ids") or rec.get("knowledge_ids") or []:
                if kid not in stats:
                    stats[kid] = [0, 0]
                stats[kid][0] += 1
                if d.get("correct"):
                    stats[kid][1] += 1
    return stats


def weak_knowledge_ids(mistakes, records):
    """薄弱知识点:正确率低且练习量足够,或反复出错(lapses)。"""
    weak = set()
    for kid, (attempts, correct) in knowledge_accuracy(records).items():
        if attempts >= WEAK_MIN_ATTEMPTS and correct / attempts < WEAK_ACCURACY:
            weak.add(kid)
    for m in mistakes:
        if m.get("archived"):
            continue
        if int(m.get("lapses", 0)) >= WEAK_LAPSES:
            for kid in m.get("knowledge_ids") or []:
                weak.add(kid)
    return weak


def _enabled_subjects(settings):
    subs = [
        (name, cfg)
        for name, cfg in (settings.get("subjects") or {}).items()
        if cfg.get("enabled")
    ]
    return sorted(subs, key=lambda kv: (kv[1].get("priority", 9), kv[0]))


def generate_day_plan(date_str, settings, mistakes, records, knowledge, vocab,
                      today=None, reflections=None, weak_points=None):
    """生成某日任务列表。只产出新任务,不修改已有计划存储。

    每个任务带 goal(学习目标)/standard(完成标准)/reason(推荐理由)。
    weak_points: profile.compute_weak_points 的输出(可选,用于待验证任务)。
    """
    today = today or datetime.date.today()
    day = parse_date(date_str)
    daily_total = int(settings.get("daily_minutes", 240))
    tasks = []
    used_total = 0
    tid_prefix = day.strftime("%Y%m%d")
    reflections = reflections or []

    def add_task(subject, kind, title, est, payload, goal="", standard="", reason=""):
        nonlocal used_total
        est = int(round(est))
        if used_total + est > daily_total:
            return False
        used_total += est
        tasks.append({
            "id": "tk-%s-%03d-%s" % (tid_prefix, len(tasks) + 1,
                                     uuid.uuid4().hex[:4]),
            "subject": subject, "kind": kind, "title": title,
            "payload": payload, "est_minutes": est,
            "goal": goal, "standard": standard, "reason": reason,
            "status": "pending", "actual_minutes": None, "note": "",
        })
        return True

    weak_ids = weak_knowledge_ids(mistakes, records)
    kp_by_id = {k["id"]: k for k in knowledge}

    for subject, cfg in _enabled_subjects(settings):
        cap = int(cfg.get("minutes", daily_total // 3))

        # 1) 到期错题复习(欠账优先)
        due = [
            m for m in mistakes
            if m.get("subject") == subject and not m.get("archived")
            and _due_on(m, day)
        ]
        if due:
            take = due
            est = len(take) * MINUTES_PER_MISTAKE
            while est > cap and len(take) > 1:
                take = take[:-1]
                est = len(take) * MINUTES_PER_MISTAKE
            add_task(subject, "review",
                     "复习到期错题 %d 题" % len(take), est,
                     {"mistake_ids": [m["id"] for m in take]},
                     goal="不看答案独立完成复测,检验错误原因是否已消除",
                     standard="每题先自己写/说思路,再对照解析评分",
                     reason="间隔复习到期:这些题按遗忘曲线安排在今天")

        # 2) 薄弱知识点练习(取该知识点未到期且未归档的错题重组)
        weak_here = [
            kid for kid in weak_ids
            if (kid in kp_by_id and kp_by_id[kid].get("subject") == subject)
            or any(m.get("subject") == subject and kid in (m.get("knowledge_ids") or [])
                   for m in mistakes)
        ]
        pool = [
            m for m in mistakes
            if m.get("subject") == subject and not m.get("archived")
            and set(m.get("knowledge_ids") or []) & set(weak_here)
            and not _due_on(m, day)
        ][:PRACTICE_TASK_ITEMS]
        if pool and used_total < daily_total:
            names = sorted({kp_by_id[k]["name"] for k in weak_here if k in kp_by_id})
            label = "、".join(names[:3]) + ("等" if len(names) > 3 else "")
            add_task(subject, "practice",
                     "薄弱知识点练习:%s(%d 题)" % (label or "综合", len(pool)),
                     len(pool) * MINUTES_PER_MISTAKE,
                     {"mistake_ids": [m["id"] for m in pool],
                      "knowledge_ids": list(weak_here)},
                     goal="针对薄弱知识点做变式训练,不看原题解析",
                     standard="独立完成 %d 题,每题说明所用方法的适用条件" % len(pool),
                     reason="这些知识点正确率低于 60%% 或反复出错(共 %d 题相关错题)" % len(pool))

        # 3) 新知学习(每天每科最多一块)
        fresh = [
            k for k in knowledge
            if k.get("subject") == subject
            and k.get("status") in ("not_started", "learning")
        ][:1]
        if fresh and used_total + STUDY_BLOCK_MINUTES <= daily_total:
            add_task(subject, "study",
                     "学习:“%s”" % fresh[0]["name"], STUDY_BLOCK_MINUTES,
                     {"knowledge_ids": [fresh[0]["id"]]},
                     goal="过一遍概念与公式,标记看不懂的地方",
                     standard="能复述核心定义,并在知识库中更新掌握状态",
                     reason="该知识点尚未开始或正在学习中")

    # 4) 错误模式专项(近 7 天同类错误 >=2 次)
    if weak_points is None:
        from . import profile as _profile
        weak_points = _profile.compute_weak_points(mistakes, records, reflections, knowledge, today)
    for wp in weak_points:
        if wp["status"] != "confirmed" or used_total + 20 > daily_total:
            continue
        if wp["subject"] not in [s for s, _ in _enabled_subjects(settings)]:
            continue
        pool = [m for m in mistakes
                if not m.get("archived") and wp["knowledge_id"] in (m.get("knowledge_ids") or [])
                and m.get("subject") == wp["subject"]][:6]
        add_task(wp["subject"], "practice",
                 "专项:突破「%s」" % wp["name"], 20,
                 {"mistake_ids": [m["id"] for m in pool],
                  "knowledge_ids": [wp["knowledge_id"]] if wp["knowledge_id"] else [],
                  "weak_point_id": wp["id"]},
                 goal="验证薄弱点判断:独立完成并解释每一步依据",
                 standard="3 题中至少 2 题完全独立做对",
                 reason="有证据的薄弱点:%s(证据 %d 条)" % (wp["judgment"], len(wp["evidence"])))
        break  # 每天最多一个专项,避免超载

    # 5) 待验证任务(反思中的 suspected/conflict 薄弱点)
    for wp in weak_points:
        if wp["status"] not in ("suspected", "conflict") or used_total + 15 > daily_total:
            continue
        subj = wp["subject"] if wp["subject"] in [s for s, _ in _enabled_subjects(settings)] else "math"
        add_task(subj, "verify",
                 "验证:「%s」是否真的薄弱" % wp["name"][:24], 15,
                 {"weak_point_id": wp["id"]},
                 goal="做 2-3 道不同角度的基础题,记录每题卡在哪一步",
                 standard="完成并标注:概念不懂/有思路但做错/完全没思路",
                 reason="该判断%s,需要练习数据验证" % (
                     "与已有练习记录矛盾" if wp["status"] == "conflict" else "仅来自自我反思"))
        break  # 每天最多一个验证任务

    # 6) 英语生词/长难句到期复习
    due_vocab = [v for v in vocab if srs.is_due(v, day) and not v.get("archived")]
    if due_vocab:
        take = due_vocab[:40]
        add_task("english", "review",
                 "复习到期生词/长难句 %d 条" % len(take),
                 len(take) * MINUTES_PER_VOCAB,
                 {"vocab_ids": [v["id"] for v in take]},
                 goal="先回忆词义/句子结构,再对照释义",
                 standard="自评忘了/勉强/会了/轻松",
                 reason="间隔复习到期")

    # 7) 周复盘
    weekly_day = int(settings.get("weekly_review_weekday", 6))
    if day.weekday() == weekly_day:
        add_task("all", "weekly_review", "每周复盘:查看周报并确认下周重点", 30, {},
                 goal="过一遍周报的九个问题",
                 standard="确认或更正系统对薄弱点的判断",
                 reason="每周固定复盘日")

    return tasks


def _due_on(item, day):
    nr = item.get("next_review")
    if not nr:
        return True
    try:
        return parse_date(nr) <= day
    except ValueError:
        return True


def weekly_summary(any_date_str, records, mistakes, plan_days, today=None):
    """周复盘数据:any_date 所在周的周一~周日统计。"""
    day = parse_date(any_date_str)
    monday = day - datetime.timedelta(days=day.weekday())
    week = [monday + datetime.timedelta(days=i) for i in range(7)]
    week_strs = [d.isoformat() for d in week]

    per_subject = {}
    for rec in records:
        if rec.get("date") in week_strs:
            s = per_subject.setdefault(
                rec["subject"], {"total": 0, "correct": 0, "minutes": 0}
            )
            s["total"] += rec.get("total", 0)
            s["correct"] += rec.get("correct", 0)
            s["minutes"] += rec.get("duration_min", 0) or 0

    reviewed = 0
    again = 0
    for m in mistakes:
        for r in m.get("reviews") or []:
            if r.get("date") in week_strs:
                reviewed += 1
                if r.get("result") == "again":
                    again += 1

    tasks_done = tasks_skipped = 0
    for ds in week_strs:
        for t in (plan_days.get(ds) or {}).get("tasks") or []:
            if t.get("status") == "done":
                tasks_done += 1
            elif t.get("status") == "skipped":
                tasks_skipped += 1

    top_errors = {}
    for m in mistakes:
        for r in m.get("reviews") or []:
            if r.get("date") in week_strs and r.get("result") == "again":
                for kid in m.get("knowledge_ids") or []:
                    top_errors[kid] = top_errors.get(kid, 0) + 1

    return {
        "week_start": week_strs[0],
        "week_end": week_strs[-1],
        "per_subject": per_subject,
        "reviewed": reviewed,
        "review_again": again,
        "tasks_done": tasks_done,
        "tasks_skipped": tasks_skipped,
        "hot_weak_knowledge": sorted(top_errors.items(), key=lambda kv: -kv[1])[:5],
    }
