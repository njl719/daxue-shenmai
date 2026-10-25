# -*- coding: utf-8 -*-
"""每日训练引擎:按科目配额抽题、防短期重复、作答记录、错题自动入本。

设计:
- settings.daily_train = {quotas: {math:5, cs408:5, english:5, politics:5}};
- 「train」集合存当日清单与作答(按日期一次性生成,全天稳定);
- 「train_state」记录每题最近出现日期,默认 7 天内不重复;
- 错题 → mistakes(来源=题库,自动关联知识点),练习结果 → records 明细。
"""
import datetime
import random


def parse_d(s):
    try:
        return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _day_seed(date_str):
    y, m, d = date_str.split("-")
    return random.Random(int(y) * 10000 + int(m) * 100 + int(d))


def build_daily(store, date_str, force=False):
    """生成(或返回已存在的)某日训练清单。题库不足时如实标注缺口。"""
    settings = store.load("settings")
    quotas = ((settings.get("daily_train") or {}).get("quotas")
              or {"math": 5, "cs408": 5, "english": 5, "politics": 5})
    train = store.load("train")
    if not force and train.get("date") == date_str and train.get("questions"):
        return train

    questions = [q for q in store.load("questions") if not q.get("archived")]
    state = store.load("train_state")  # {qid: last_served}
    today = parse_d(date_str)
    rng = _day_seed(date_str)
    picked, shortage = [], {}
    for subject, quota in quotas.items():
        if quota <= 0:
            continue
        pool = [q for q in questions if q["subject"] == subject]
        # 7 天内做过的优先排除
        fresh = []
        for q in pool:
            last = state.get(q["id"])
            if not last or (today - parse_d(last)).days > 7:
                fresh.append(q)
        src_pool = fresh if len(fresh) >= quota else fresh + [
            q for q in pool if q not in fresh]
        take = rng.sample(src_pool, min(quota, len(src_pool)))
        if len(take) < quota:
            shortage[subject] = quota - len(take)
        picked.extend(take)
        for q in take:
            state[q["id"]] = date_str
    train = {"date": date_str,
             "questions": [{"id": q["id"], "subject": q["subject"]} for q in picked],
             "answers": {},      # {qid: {picked, correct, seconds, error_tag}}
             "shortage": shortage,
             "generated_at": datetime.datetime.now().isoformat(timespec="seconds")}
    store.save("train", train)
    store.save("train_state", state)
    return train


def record_answer(store, qid, picked, correct, seconds=None, error_tag=None):
    """记录一次作答;错题自动入错题本。返回更新后的 train。"""
    import datetime as _dt
    train = store.load("train")
    if train.get("date") != _dt.date.today().isoformat():
        train = build_daily(store, _dt.date.today().isoformat())
    train["answers"][qid] = {"picked": picked, "correct": bool(correct),
                             "seconds": seconds, "error_tag": error_tag or ""}
    store.save("train", train)
    if correct:
        return train
    # 错题入本(幂等:同题当日只建一条)
    questions = {q["id"]: q for q in store.load("questions")}
    q = questions.get(qid)
    if not q:
        return train
    mistakes = store.load("mistakes")
    key = qid + "-" + train["date"]
    for m in mistakes:
        if m.get("client_id") == key:
            if error_tag:
                m["error_reason"] = error_tag  # 补标错因时更新已入本记录
                store.save("mistakes", mistakes)
            return train
    from .server import _next_id  # 延迟导入避免环
    mistakes.append({
        "id": _next_id(mistakes, "mk"), "client_id": key,
        "subject": q["subject"], "knowledge_ids": q.get("knowledge_ids") or [],
        "qtype": q.get("qtype") or "", "question_md": q["question_md"],
        "options": q.get("options") or [], "answer": q.get("answer") or "",
        "my_answer_md": "每日训练作答:" + str(picked),
        "correct_answer_md": q.get("answer") or "",
        "error_reason": error_tag or "暂未标注",
        "solution_md": q.get("solution_md") or "",
        "source": "题库:" + q.get("source_desc", q["id"]),
        "difficulty": q.get("difficulty", 3),
        "reviews": [], "interval_days": 0, "ease": 2.5, "lapses": 0,
        "next_review": None, "archived": False, "seed": False,
        "needs_confirmation": False,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    store.save("mistakes", mistakes)
    return train
