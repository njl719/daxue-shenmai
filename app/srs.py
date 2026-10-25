# -*- coding: utf-8 -*-
"""间隔复习引擎(SM-2 变体)。纯函数,无 IO,便于单元测试。

评分等级: again(忘了) / hard(勉强) / good(会) / easy(轻松)
规则见 docs/DESIGN.md 第 5 节。
"""
import datetime

EASE_MIN = 1.3
EASE_MAX = 2.8
EASE_DEFAULT = 2.5
INTERVAL_MAX = 60

GRADES = ("again", "hard", "good", "easy")


def clamp_ease(ease):
    return max(EASE_MIN, min(EASE_MAX, ease))


def next_interval(item, grade):
    """根据当前间隔/难度与评分计算下一个间隔(天)。"""
    interval = int(item.get("interval_days", 0) or 0)
    ease = float(item.get("ease", EASE_DEFAULT))
    if grade == "again":
        return 1
    if grade == "hard":
        return max(1, round(interval * 1.2)) if interval > 0 else 1
    if grade == "good":
        return 1 if interval == 0 else min(INTERVAL_MAX, round(interval * ease))
    # easy
    if interval == 0:
        return 3
    return min(INTERVAL_MAX, round(interval * ease * 1.3))


def apply_review(item, grade, today=None):
    """对带 SRS 字段的条目(错题/生词)应用一次复习,返回更新后的新 dict。

    item 需含: interval_days, ease, lapses, reviews(列表), next_review
    """
    if grade not in GRADES:
        raise ValueError("grade must be one of %s" % (GRADES,))
    today = today or datetime.date.today()

    item = dict(item)
    old_interval = int(item.get("interval_days", 0) or 0)
    ease = float(item.get("ease", EASE_DEFAULT))

    if grade == "again":
        ease -= 0.20
        item["lapses"] = int(item.get("lapses", 0)) + 1
    elif grade == "hard":
        ease -= 0.15
    elif grade == "easy":
        ease += 0.15

    interval = next_interval(
        {"interval_days": old_interval, "ease": ease}, grade
    )
    item["ease"] = round(clamp_ease(ease), 2)
    item["interval_days"] = interval
    next_date = today + datetime.timedelta(days=interval)
    item["next_review"] = next_date.isoformat()

    reviews = list(item.get("reviews") or [])
    reviews.append(
        {"date": today.isoformat(), "result": grade, "interval": interval}
    )
    item["reviews"] = reviews
    return item


def is_due(item, today=None):
    """next_review <= today 即到期。"""
    today = today or datetime.date.today()
    nr = item.get("next_review")
    if not nr:
        return True
    try:
        return datetime.date.fromisoformat(nr) <= today
    except ValueError:
        return True
