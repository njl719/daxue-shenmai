# -*- coding: utf-8 -*-
"""学习画像引擎:六级知识点状态、有证据的薄弱点追踪、每周诊断报告。

核心原则:
- 每个结论必须携带证据与置信度;数据不足时明确输出"数据不足",不预设薄弱点。
- 反思中的主观薄弱判断与练习数据交叉验证:一致→置信度↑;矛盾→标记"待辨析"。
- 不输出无解释的单一分数。
"""
import datetime

from . import srs

# 六级状态模型(可解释,不用单一分数)
STATUS_MODEL = ["not_started", "learning", "initial", "consolidating", "mostly", "mastered"]
STATUS_TXT = {
    "not_started": "未学习", "learning": "学习中", "initial": "初步掌握",
    "consolidating": "需要巩固", "mostly": "基本掌握", "mastered": "稳定掌握",
}
# 兼容旧四值数据
STATUS_COMPAT = {"not_started": "not_started", "learning": "learning",
                 "reviewing": "initial", "mastered": "mostly"}

ERROR_REASONS = ["概念不清", "公式或定理使用错误", "计算失误", "推导不严谨",
                 "建模或思路错误", "审题错误", "方法不熟练", "时间分配不合理",
                 "知识遗忘", "暂时无法判断"]

RETEST_PASS_NEEDED = 2  # 连续独立答对次数→认为方法已掌握


def norm_status(s):
    return STATUS_COMPAT.get(s, s if s in STATUS_MODEL else "not_started")


def parse_d(s):
    try:
        return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


# ---------------- 薄弱点引擎 ----------------

def _fmt_evidence_mistake(m, kp_names):
    return {
        "type": "mistake", "ref": m["id"],
        "text": "错题《%s…》%s" % ((m.get("question_md") or "")[:24].strip(),
                                 "(已忘%d次)" % m.get("lapses", 0) if m.get("lapses") else ""),
        "date": (m.get("created") or "")[:10],
    }


def compute_weak_points(mistakes, records, reflections, knowledge, today=None):
    """综合错题/练习/反思三类证据生成薄弱点列表。

    每条:{id, subject, name, knowledge_id?, judgment, confidence, evidence[],
          status: confirmed|suspected|unverified|conflict,
          last_verified, retest: {attempts, correct}, trend, recommended_action}
    """
    today = today or datetime.date.today()
    kp = {k["id"]: k for k in knowledge}
    weak = {}

    def slot(key, subject, name, knowledge_id=None):
        if key not in weak:
            weak[key] = {
                "id": key, "subject": subject, "name": name,
                "knowledge_id": knowledge_id,
                "judgment": "", "confidence": 0.0, "evidence": [],
                "status": "unverified", "last_verified": None,
                "retest": {"attempts": 0, "correct": 0}, "trend": "",
                "recommended_action": "", "source_tags": [],
            }
        return weak[key]

    # 证据 A:错题(反复出错 lapses>=2,或未到期又错)
    for m in mistakes:
        if m.get("archived"):
            continue
        for kid in m.get("knowledge_ids") or []:
            k = kp.get(kid)
            key = "kp:" + kid
            sl = slot(key, k["subject"] if k else m.get("subject", "math"),
                      k["name"] if k else kid, kid)
            if m.get("lapses", 0) >= 2:
                sl["evidence"].append(_fmt_evidence_mistake(m, kp))
                sl["source_tags"].append("反复出错")
            reviews = [r for r in m.get("reviews") or []]
            if reviews:
                sl["retest"]["attempts"] += len(reviews)
                sl["retest"]["correct"] += sum(1 for r in reviews if r.get("result") != "again")
                last = reviews[-1]["date"]
                sl["last_verified"] = max(sl["last_verified"] or "", last)
                recent = reviews[-3:]
                if len(recent) == 3 and all(r.get("result") != "again" for r in recent):
                    sl["trend"] = "最近3次复测全部通过,正在好转"
                elif recent and recent[-1].get("result") == "again":
                    sl["trend"] = "最近一次复测仍未通过"

    # 证据 B:练习正确率(>=3次且<60%)
    acc = {}
    for rec in records:
        for d in rec.get("detail") or []:
            for kid in d.get("knowledge_ids") or rec.get("knowledge_ids") or []:
                a = acc.setdefault(kid, [0, 0])
                a[0] += 1
                if d.get("correct"):
                    a[1] += 1
    for kid, (n, c) in acc.items():
        if n >= 3 and c / n < 0.6:
            k = kp.get(kid)
            sl = slot("kp:" + kid, k["subject"] if k else "math",
                      k["name"] if k else kid, kid)
            sl["evidence"].append({
                "type": "accuracy", "ref": kid,
                "text": "相关练习 %d 次仅对 %d 次(正确率 %d%%)" % (n, c, round(100 * c / n)),
                "date": today.isoformat()})
            sl["source_tags"].append("正确率低")
            if sl["retest"]["attempts"]:
                sl["last_verified"] = sl["last_verified"] or today.isoformat()

    # 确认级:有练习/复测证据的
    for sl in weak.values():
        if sl["source_tags"]:
            sl["status"] = "confirmed"
            sl["confidence"] = min(0.9, 0.5 + 0.1 * len(sl["evidence"]))
            sl["judgment"] = "%s(%s)" % ("、".join(sorted(set(sl["source_tags"]))),
                                         "复测%d次对%d次" % (sl["retest"]["attempts"],
                                                         sl["retest"]["correct"])
                                         if sl["retest"]["attempts"] else "尚无复测")
            sl["recommended_action"] = "安排该知识点的错题复测与专项练习(见计划页)"
        elif sl["knowledge_id"]:
            # 有错题挂在名下但还没复测过:数据不足,不下结论
            sl["status"] = "unverified"
            sl["confidence"] = 0.0
            sl["judgment"] = "该知识点有错题记录但尚未复测,数据不足,暂时无法判断"
            sl["recommended_action"] = "复测 1-2 次后再看是否需要专项"

    # 证据 C:反思中的主观薄弱点(未经练习验证 → suspected/conflict)
    for ref in reflections:
        for wp in ref.get("extracted", {}).get("weak_points") or []:
            label = (wp or "").strip()[:40]
            if not label:
                continue
            key = "ref:" + label
            sl = slot(key, ref.get("extracted", {}).get("subjects", ["math"])[0]
                      if ref.get("extracted", {}).get("subjects") else "math", label)
            sl["evidence"].append({
                "type": "reflection", "ref": ref["id"],
                "text": "你在 %s 的反思中写到:%s" % (ref.get("date", ""), label),
                "date": ref.get("date", "")})
            if "source_tags" not in sl or "自我反思" not in sl["source_tags"]:
                sl["source_tags"].append("自我反思")

    # 交叉验证:反思类薄弱点 vs 练习数据
    for sl in weak.values():
        if "自我反思" not in sl["source_tags"]:
            continue
        if sl["status"] == "confirmed":
            sl["confidence"] = min(0.95, sl["confidence"] + 0.2)
            sl["judgment"] = "自我反思与练习数据一致:" + sl["judgment"]
            continue
        # 无练习数据 → 查该标签关联的练习
        n_attempts = 0
        for rec in records:
            joined = " ".join(kp.get(i, {}).get("name", "") for i in rec.get("knowledge_ids") or [])
            if sl["name"][:6] and sl["name"][:6] in joined:
                n_attempts += rec.get("total", 0)
        if n_attempts == 0:
            sl["status"] = "suspected"
            sl["confidence"] = 0.3
            sl["judgment"] = "仅来自自我反思,尚无练习数据支持"
            sl["recommended_action"] = "先做 2-3 道相关基础题验证,再决定是否投入专项时间"
        else:
            sl["status"] = "conflict"
            sl["confidence"] = 0.4
            sl["judgment"] = "反思觉得薄弱,但已有 %d 次相关练习记录——需辨析是信心不足还是方法缺陷" % n_attempts
            sl["recommended_action"] = "做 3 道不同角度的题并记录思路,区分概念/建模/计算问题"

    order = {"confirmed": 0, "conflict": 1, "suspected": 2, "unverified": 3}
    return sorted(weak.values(),
                  key=lambda s: (order[s["status"]], -s["confidence"], -len(s["evidence"])))


def error_patterns(mistakes, days=14, today=None):
    """近 N 天高频错误原因模式(按科目)。"""
    today = today or datetime.date.today()
    cutoff = today - datetime.timedelta(days=days)
    patt = {}
    for m in mistakes:
        if m.get("archived"):
            continue
        reason = m.get("error_reason") or "未标注"
        recent = [r for r in m.get("reviews") or []
                  if (parse_d(r.get("date")) or today) >= cutoff and r.get("result") == "again"]
        hits = len(recent) + (1 if (parse_d((m.get("created") or "")[:10]) or today) >= cutoff
                              and m.get("lapses", 0) == 0 else 0)
        if hits:
            p = patt.setdefault(reason, {"reason": reason, "count": 0, "subjects": set()})
            p["count"] += hits
            p["subjects"].add(m.get("subject"))
    out = [{"reason": p["reason"], "count": p["count"],
            "subjects": sorted(p["subjects"])}
           for p in sorted(patt.values(), key=lambda x: -x["count"])]
    return out


# ---------------- 学习画像 ----------------

def compute_profile(mistakes, records, reflections, knowledge, catalog, settings, today=None):
    today = today or datetime.date.today()
    weak = compute_weak_points(mistakes, records, reflections, knowledge, today)

    subjects = {}
    for subj in ("math", "cs408", "english"):
        kps = [k for k in knowledge if k.get("subject") == subj]
        dist = {}
        for k in kps:
            st = norm_status(k.get("status"))
            dist[st] = dist.get(st, 0) + 1
        recs = [r for r in records if r.get("subject") == subj]
        total = sum(r.get("total", 0) for r in recs)
        correct = sum(r.get("correct", 0) for r in recs)
        subjects[subj] = {
            "knowledge_total": len(kps),
            "status_dist": dist,
            "progress_pct": (round(100 * sum(v for s, v in dist.items() if s != "not_started") / len(kps))
                             if kps else 0),
            "attempted": total,
            "accuracy": round(100 * correct / total) if total else None,
            "mistakes": len([m for m in mistakes
                             if m.get("subject") == subj and not m.get("archived")]),
        }

    # 近 14 天趋势
    trend = []
    for i in range(13, -1, -1):
        d = today - datetime.timedelta(days=i)
        day_recs = [r for r in records if r.get("date") == d.isoformat()]
        t = sum(r.get("total", 0) for r in day_recs)
        c = sum(r.get("correct", 0) for r in day_recs)
        trend.append({"date": d.isoformat(), "total": t, "correct": c,
                      "accuracy": round(100 * c / t) if t else None})

    exam = settings.get("exam_date")
    days_left = None
    if exam:
        ed = parse_d(exam)
        if ed:
            days_left = (ed - today).days
    stage = ("冲刺" if days_left is not None and 0 <= days_left <= 45 else
             "强化" if days_left is not None and days_left <= 150 else
             "基础" if days_left is not None else None)

    # 数据缺口提示
    gaps = []
    if not records:
        gaps.append("还没有练习记录:做几组题并录入结果,才能验证主观薄弱点")
    if not reflections:
        gaps.append("还没有反思记录:每天 30 秒文字反思,能显著提升画像准确度")
    n_ret = sum(len(m.get("reviews") or []) for m in mistakes)
    if mistakes and n_ret < len(mistakes):
        gaps.append("部分错题尚未复测过:复测是判断真实掌握的主要依据")
    return {
        "generated_at": today.isoformat(),
        "stage": stage, "days_left": days_left,
        "subjects": subjects,
        "weak_points": weak,
        "error_patterns": error_patterns(mistakes, today=today),
        "trend_14d": trend,
        "data_gaps": gaps,
    }


# ---------------- 每周诊断报告 ----------------

def weekly_report(any_date, records, mistakes, reflections, plan_days, knowledge, today=None):
    """回答九个问题的结构化周报。所有数字来自真实记录,不足处标注。"""
    today = today or datetime.date.today()
    day = parse_d(any_date) or today
    monday = day - datetime.timedelta(days=day.weekday())
    week = [monday + datetime.timedelta(days=i) for i in range(7)]
    strs = [d.isoformat() for d in week]

    in_week = lambda ds: ds in strs
    # 1 学了什么
    learned = []
    for ref in reflections:
        if in_week(ref.get("date", "")):
            learned.append({"date": ref["date"],
                            "content": ref.get("extracted", {}).get("content", "")})
    study_tasks = []
    for ds in strs:
        for t in (plan_days.get(ds) or {}).get("tasks") or []:
            if t.get("status") == "done" and t.get("kind") == "study":
                study_tasks.append({"date": ds, "title": t["title"]})

    # 2 任务完成情况
    done = skip = pending = 0
    for ds in strs:
        for t in (plan_days.get(ds) or {}).get("tasks") or []:
            st = t.get("status")
            done += st == "done"
            skip += st == "skipped"
            pending += st == "pending"

    # 3/4/5 练习、错误、模式
    week_recs = [r for r in records if in_week(r.get("date", ""))]
    per_subject = {}
    for r in week_recs:
        s = per_subject.setdefault(r["subject"], {"total": 0, "correct": 0, "minutes": 0})
        s["total"] += r.get("total", 0)
        s["correct"] += r.get("correct", 0)
        s["minutes"] += r.get("duration_min") or 0
    for s in per_subject.values():
        s["accuracy"] = round(100 * s["correct"] / s["total"]) if s["total"] else None

    reviewed = again = 0
    for m in mistakes:
        for r in m.get("reviews") or []:
            if in_week(r.get("date", "")):
                reviewed += 1
                again += r.get("result") == "again"
    patterns = error_patterns(mistakes, days=7, today=week[-1])

    # 6 优先薄弱点(本周证据)
    weak = compute_weak_points(mistakes, records, reflections, knowledge, week[-1])
    top_weak = [w for w in weak if w["status"] in ("confirmed", "conflict")][:3]

    # 9 与上周对比
    last_week = [(d - datetime.timedelta(days=7)).isoformat() for d in week]
    lw = [r for r in records if r.get("date") in last_week]
    lw_total = sum(r.get("total", 0) for r in lw)
    lw_correct = sum(r.get("correct", 0) for r in lw)
    tw_total = sum(r.get("total", 0) for r in week_recs)
    tw_correct = sum(r.get("correct", 0) for r in week_recs)
    compare = {
        "this_week": {"total": tw_total, "accuracy": round(100 * tw_correct / tw_total) if tw_total else None},
        "last_week": {"total": lw_total, "accuracy": round(100 * lw_correct / lw_total) if lw_total else None},
    }

    # 8 证据不足的判断
    unverified = [w for w in weak if w["status"] in ("suspected", "unverified")]
    data_gaps = []
    if tw_total < 5:
        data_gaps.append("本周练习量不足 5 题,正确率波动大,不宜下强结论")
    if not learned and not study_tasks:
        data_gaps.append("本周没有反思或新知学习记录,无法评估学习内容覆盖")
    if reviewed == 0 and mistakes:
        data_gaps.append("本周没有错题复测记录,掌握判断缺少复测依据")

    return {
        "week_start": strs[0], "week_end": strs[-1],
        "learned": learned[:10],
        "study_tasks": study_tasks[:10],
        "tasks": {"done": done, "skipped": skip, "pending": pending},
        "per_subject": per_subject,
        "review": {"total": reviewed, "again": again},
        "error_patterns": patterns[:5],
        "top_weak": top_weak,
        "compare": compare,
        "unverified_judgments": unverified[:5],
        "data_gaps": data_gaps,
        "next_week_advice": _next_week_advice(top_weak, patterns, tw_total),
    }


def _next_week_advice(top_weak, patterns, week_total):
    advice = []
    for w in top_weak[:2]:
        advice.append("优先解决「%s」:%s。%s" % (w["name"], w["judgment"], w["recommended_action"]))
    if patterns:
        p = patterns[0]
        advice.append("近期高频错误模式是「%s」(%d 次):做题时刻意检查这一环节" % (p["reason"], p["count"]))
    if week_total == 0:
        advice.append("数据不足:本周没有有效练习记录,先建立基线——每天 3-5 题练习加到期复测")
    elif week_total < 10:
        advice.append("本周练习量偏少(%d 题):先保证每天有最少 5 题的有效练习(含复测),再考虑扩展新内容" % week_total)
    if not advice:
        advice.append("数据不足,暂无可靠建议。先补几天的错题与反思记录")
    return advice[:3]
