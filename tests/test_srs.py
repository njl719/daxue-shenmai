# -*- coding: utf-8 -*-
"""srs.py 单元测试:间隔算法边界。"""
import datetime

import pytest

from app import srs


def test_first_good_gives_1_day():
    item = {"interval_days": 0, "ease": 2.5, "lapses": 0, "reviews": []}
    out = srs.apply_review(item, "good", datetime.date(2026, 10, 24))
    assert out["interval_days"] == 1
    assert out["next_review"] == "2026-10-25"
    assert out["lapses"] == 0


def test_first_easy_gives_3_days():
    item = {"interval_days": 0, "ease": 2.5, "lapses": 0, "reviews": []}
    out = srs.apply_review(item, "easy", datetime.date(2026, 10, 24))
    assert out["interval_days"] == 3


def test_again_resets_and_counts_lapse():
    item = {"interval_days": 20, "ease": 2.5, "lapses": 0, "reviews": []}
    out = srs.apply_review(item, "again", datetime.date(2026, 10, 24))
    assert out["interval_days"] == 1
    assert out["lapses"] == 1
    assert out["ease"] == pytest.approx(2.3)


def test_good_multiplies_by_ease():
    item = {"interval_days": 10, "ease": 2.5, "lapses": 0, "reviews": []}
    out = srs.apply_review(item, "good", datetime.date(2026, 10, 24))
    assert out["interval_days"] == 25


def test_hard_at_least_1_day():
    item = {"interval_days": 1, "ease": 2.5, "lapses": 0, "reviews": []}
    out = srs.apply_review(item, "hard", datetime.date(2026, 10, 24))
    assert out["interval_days"] == 1


def test_ease_clamped():
    item = {"interval_days": 5, "ease": 1.35, "lapses": 3, "reviews": []}
    out = srs.apply_review(item, "again", datetime.date(2026, 10, 24))
    assert out["ease"] == srs.EASE_MIN

    item = {"interval_days": 5, "ease": 2.75, "lapses": 0, "reviews": []}
    out = srs.apply_review(item, "easy", datetime.date(2026, 10, 24))
    assert out["ease"] == srs.EASE_MAX


def test_interval_capped_60():
    item = {"interval_days": 58, "ease": 2.5, "lapses": 0, "reviews": []}
    out = srs.apply_review(item, "good", datetime.date(2026, 10, 24))
    assert out["interval_days"] <= srs.INTERVAL_MAX


def test_review_history_appended():
    item = {"interval_days": 0, "ease": 2.5, "lapses": 0, "reviews": []}
    out = srs.apply_review(item, "good", datetime.date(2026, 10, 24))
    assert len(out["reviews"]) == 1
    assert out["reviews"][0]["result"] == "good"


def test_invalid_grade_rejected():
    with pytest.raises(ValueError):
        srs.apply_review({"interval_days": 0, "ease": 2.5, "lapses": 0, "reviews": []}, "ok")


def test_is_due():
    assert srs.is_due({"next_review": "2026-10-23"}, datetime.date(2026, 10, 24))
    assert not srs.is_due({"next_review": "2026-10-25"}, datetime.date(2026, 10, 24))
    assert srs.is_due({"next_review": None}, datetime.date(2026, 10, 24))
    assert srs.is_due({}, datetime.date(2026, 10, 24))


def test_original_item_not_mutated():
    item = {"interval_days": 10, "ease": 2.5, "lapses": 0, "reviews": []}
    srs.apply_review(item, "good", datetime.date(2026, 10, 24))
    assert item["interval_days"] == 10 and len(item["reviews"]) == 0
