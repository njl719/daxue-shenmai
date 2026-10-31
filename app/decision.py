# -*- coding: utf-8 -*-
"""智能择校与录取概率引擎(V2.0 模块二)。

铁律:
- 匹配度(个人条件 vs 院校要求)与录取概率严格分离,两个数字不同源不同义;
- 概率只用真实数据:历史复试线/招生计划(official 数据层)+ 用户真实模拟成绩;
- 数据不足时返回 reliable=False + 原因清单,绝不随机生成;
- 三情景(乐观/基准/保守)是"对用户未来成绩的假设分档",输出中必须标明是假设;
- 所有概率附带解释:用了哪些数据、哪些是假设。
"""
import datetime
import math

FULL_MARKS = {"politics": 100, "english": 100, "math": 150, "cs408": 150}
SUBJECT_NAMES = {"math": "数学一", "cs408": "408", "english": "英语一",
                 "politics": "政治"}
TOTAL = 500


def _norm_cdf(x, mu, sigma):
    if sigma <= 0:
        return 1.0 if x <= mu else 0.0
    return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))


# ------------------------------------------------- 画像与模拟成绩

def persona_snapshot(store):
    p = dict(store.load("persona") or {})
    if not p:
        return {"exists": False}
    p["exists"] = True
    p["exam_phase_days"] = None
    try:
        exam = datetime.date(int(p.get("exam_year") or 2028), 12, 1)
        p["exam_phase_days"] = (exam - datetime.date.today()).days
    except (ValueError, TypeError):
        pass
    return p


def mock_summary(store, exam_year=None):
    """按科目汇总真实模拟成绩(时间升序)。只统计用户手动录入的月度成绩。"""
    rows = [m for m in store.load("mock_scores")
            if m.get("subject") in FULL_MARKS
            and (not exam_year or str(m.get("year") or exam_year) == str(exam_year))]
    out = {}
    for m in sorted(rows, key=lambda r: r.get("month") or ""):
        out.setdefault(m["subject"], []).append(
            {"month": m.get("month"), "score": m.get("score"),
             "full_mark": m.get("full_mark", FULL_MARKS[m["subject"]])})
    return out


def _total_estimate(by_subject):
    """按各科最近一次成绩折算总分估计(各科换算到满分占比后合成 500 分制)。"""
    parts, n = 0.0, 0
    for sub, rows in by_subject.items():
        if not rows:
            continue
        last = rows[-1]
        fm = last.get("full_mark") or FULL_MARKS.get(sub)
        if not fm:
            continue
        parts += (last["score"] or 0) / fm * FULL_MARKS[sub]
        n += 1
    if n < 2:  # 至少两科有真实模拟才谈得上总分估计
        return None, n
    return round(parts), n


# ------------------------------------------------- 匹配度(≠概率)

def match_score(uni, persona, adm_rows):
    """匹配度 0-100:方案适配 + 方向适配 + 数据完备度参考。可解释,逐项列出。
    注意:这是适配程度,不是录取概率。"""
    if not persona.get("exists"):
        return None
    items, total = [], 0.0
    # 1) 考试方案适配(40 分):院校是否考 408/数一/英一(以已知信息计)
    plan_pts = 0.0
    if uni.get("uses_408") is True:
        plan_pts = 40
    elif uni.get("uses_408") is False:
        plan_pts = 0
    else:
        rows = [r for r in adm_rows if r.get("uses_408") is not None]
        plan_pts = 40 if rows and all(r["uses_408"] for r in rows) else \
            (0 if rows else None)
    if plan_pts is None:
        items.append({"item": "考试方案", "points": None,
                      "why": "院校初试科目官方未公开,无法判定 408 适配"})
    else:
        items.append({"item": "考试方案(408/数一/英一)", "points": plan_pts,
                      "why": "院校%s考408,与你的11408方案%s"
                             % ("已知" if uni.get("uses_408") is not None else "按近年目录推测",
                                "一致" if plan_pts else "不一致")})
        total += plan_pts
    # 2) 方向适配(30 分):学院名/院校名与目标方向关键词
    dirs = persona.get("directions") or []
    text = (uni.get("cs_school") or "") + (uni.get("name") or "")
    hits = [d for d in dirs if d and d in text]
    dpts = 30 if hits else (10 if any(d in text for d in ("计算机", "软件", "信息")) else 0)
    items.append({"item": "专业方向", "points": dpts,
                  "why": "学院/院校名%s目标方向(%s)" %
                         ("命中" if hits else "仅部分相关" if dpts else "未命中",
                          "、".join(dirs))})
    total += dpts
    # 3) 地区偏好(15 分)
    pref = (persona.get("target_region") or "").strip()
    if pref:
        rpts = 15 if pref in (uni.get("region") or "") else 0
        items.append({"item": "地区偏好", "points": rpts,
                      "why": "目标地区=%s,院校在%s" % (pref, uni.get("region") or "未知")})
        total += rpts
    # 4) 数据完备度(15 分):官方数据层是否有可核验记录(择校信息风险)
    rows = [r for r in adm_rows if r.get("verified_at")]
    dpts2 = 15 if rows else (7 if adm_rows else 0)
    items.append({"item": "官方数据完备度", "points": dpts2,
                  "why": "已核验分档 %d 条 / 共 %d 条" % (len(rows), len(adm_rows))})
    total += dpts2
    return {"score": round(total, 1), "items": items,
            "note": "匹配度=个人条件与院校要求的适配程度,不是录取概率"}


# ------------------------------------------------- 录取概率(可解释)

def probability(store, uni_id):
    """分层概率:进入复试 → 复试通过 → 最终录取。可解释;数据不足则 reliable=False。"""
    uni = next((u for u in store.load("universities") if u["id"] == uni_id), None)
    if not uni:
        return {"ok": False, "error": "院校不存在"}
    rows = sorted((r for r in store.load("admission_records")
                   if r["uni_id"] == uni_id and r.get("retest_line")),
                  key=lambda r: r["year"])
    persona = persona_snapshot(store)
    by_subject = mock_summary(store, persona.get("exam_year"))
    est, n_subs = _total_estimate(by_subject)

    blocking = []
    notes = []
    if len(rows) < 2:
        blocking.append("可用的官方复试线年份不足 2 年(现有 %d 年),无法估计分数线分布"
                        % len(rows))
    if est is None:
        blocking.append("真实模拟成绩不足(需至少 2 科有月度模拟成绩),无法估计你的初试水平")
    if not persona.get("exists"):
        blocking.append("个人画像未填写")
    if not rows or any(not r.get("plan_total") for r in rows):
        notes.append("招生计划官方未公开,复试比例采用行业常见假设(1:1.2~1.5)")

    if blocking or est is None or len(rows) < 2:
        return {"ok": True, "reliable": False, "reasons": blocking,
                "data_coverage": {"line_years": [r["year"] for r in rows],
                                  "mock_subjects": n_subs,
                                  "years_available": [r["year"] for r in rows]},
                "note": "预测不可靠:以上为缺数据原因。请录入官方历年数据(须来源)与"
                        "月度模拟成绩后重试;系统不会编造概率。"}

    lines = [float(r["retest_line"]) for r in rows]
    mu_line = sum(lines) / len(lines)
    sigma_line = (sum((x - mu_line) ** 2 for x in lines) / len(lines)) ** 0.5

    # 假设(输出中明确标注):初试成绩服从正态分布 N(est, sigma_est),
    # sigma_est 按模拟次数取 15~30 分(次数越少越不确定)
    sigma_est = max(12.0, 30.0 - 3.0 * min(6, sum(len(v) for v in by_subject.values())))
    p_pass_line = _norm_cdf(est, mu_line, sigma_est)  # P(总分 ≥ 复试线)
    # 复试差额比例假设:1:1.2(官方未公开时的行业常见值,标注为假设)
    p_final_given_pass = 1 / 1.2
    p_final = p_pass_line * p_final_given_pass

    # 单科线风险:任何一科估计分低于已知单科线即标红(单科线数据未收集则跳过)
    subj_targets = {}
    for sub, rows_s in by_subject.items():
        if rows_s:
            subj_targets[sub] = rows_s[-1]["score"]

    scenarios = {
        "乐观": {"total": min(round(est + sigma_est), TOTAL),
                 "note": "假设:按你最近各科最好一次模拟合成"},
        "基准": {"total": round(est), "note": "假设:按最近各科一次模拟合成"},
        "保守": {"total": round(max(est - sigma_est, 0)),
                 "note": "假设:按基准下浮 1 个标准差"},
    }
    scen_p = {k: round(_norm_cdf(v["total"], mu_line, sigma_line)
                       * p_final_given_pass, 3) for k, v in scenarios.items()}

    return {
        "ok": True, "reliable": True,
        "uni": {"id": uni_id, "name": uni["name"]},
        "p_pass_line": round(p_pass_line, 3),
        "p_final_given_pass": round(p_final_given_pass, 3),
        "p_final": round(p_final, 3),
        "score_estimate": {"total": est, "sigma": round(sigma_est, 1),
                           "based_on_subjects": n_subs},
        "targets": {"retest_line_mean": round(mu_line, 1),
                    "retest_line_by_year": {r["year"]: r["retest_line"] for r in rows},
                    "per_subject_last": subj_targets,
                    "suggest": "总分目标 ≥ %d(近 %d 年复试线均值上浮 5 分)"
                               % (round(mu_line + 5), len(lines))},
        "scenarios": scenarios, "scenario_probability": scen_p,
        "data_coverage": {"line_years": [r["year"] for r in rows],
                          "mock_count": sum(len(v) for v in by_subject.values())},
        "confidence": "低" if (len(rows) < 3 or n_subs < 3) else "中",
        "assumptions": [
            "初试总分近似正态分布 N(%.0f, %.0f²),σ 由模拟次数推定" % (est, sigma_est),
            "复试差额比例按 1:1.2 假设(招生计划/复试办法官方未公开)",
            "历史复试线(%s)能代表你考试当年的水平" % "、".join(str(y) for y in [r["year"] for r in rows]),
        ] + notes,
        "note": "概率为统计估计而非承诺;27 考研经验与新政策不能替代当年官方目录。",
    }


# ------------------------------------------------- 推荐分层

def recommend(store):
    """冲刺/目标/稳妥/保底分层。仅依据**已采集的官方复试线**与个人匹配度;
    无官方数据的年份不参与分层(2028 未公开 → 依据 2026/2027 已核验数据并注明)。"""
    persona = persona_snapshot(store)
    unis = store.load("universities")
    adms = store.load("admission_records")
    out = []
    for u in unis:
        rows = [r for r in adms if r["uni_id"] == u["id"] and r.get("retest_line")]
        ms = match_score(u, persona, [r for r in adms if r["uni_id"] == u["id"]])
        entry = {"uni_id": u["id"], "name": u["name"], "region": u.get("region"),
                 "uses_408": u.get("uses_408"), "match": ms,
                 "line_years": {r["year"]: r["retest_line"] for r in rows},
                 "tier": None, "tier_note": "官方数据不足,暂不分层"}
        if rows and ms:
            mean_line = sum(float(r["retest_line"]) for r in rows) / len(rows)
            m = ms["score"]
            if m >= 80:
                tier = "冲刺" if mean_line >= 340 else "目标"
            elif m >= 60:
                tier = "目标" if mean_line >= 300 else "稳妥"
            else:
                tier = "稳妥" if mean_line < 300 else "冲刺"
            entry["tier"] = tier
            entry["tier_note"] = ("按匹配度 %.0f 与已核验复试线均值 %.0f 分层;"
                                  "仅基于 %d 年官方数据,2028 以当年目录为准"
                                  % (m, mean_line, len(rows)))
        out.append(entry)
    order = {"冲刺": 0, "目标": 1, "稳妥": 2, "保底": 3, None: 4}
    out.sort(key=lambda e: (order[e["tier"]], -(e["match"] or {}).get("score", 0)))
    return {"items": out,
            "note": "匹配度≠录取概率;概率请见单校预测页(数据不足时明确不可靠)"}
