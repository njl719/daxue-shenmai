# -*- coding: utf-8 -*-
"""storage.py 单元测试:原子写、损坏恢复、备份轮转。"""
import json
import os

import pytest

from app.storage import Store


@pytest.fixture
def store(tmp_path):
    s = Store(data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    # 关闭自动备份以免干扰计数断言
    s._maybe_daily_backup = lambda: None
    return s


def test_save_load_roundtrip(store):
    store.save("mistakes", [{"id": "mk-1", "question_md": "测试"}])
    assert store.load("mistakes")[0]["id"] == "mk-1"


def test_missing_file_returns_default(store):
    assert store.load("mistakes") == []
    assert store.load("settings") == {}
    assert store.load("plan") == {}


def test_corrupt_file_returns_default(store):
    path = os.path.join(store.data_dir, "knowledge.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write("{broken json!!!")
    assert store.load("knowledge") == []


def test_unknown_collection_rejected(store):
    with pytest.raises(KeyError):
        store.load("nope")
    with pytest.raises(KeyError):
        store.save("nope", [])


def test_atomic_write_no_tmp_leftover(store):
    store.save("records", [{"id": "rc-1"}])
    files = os.listdir(store.data_dir)
    assert "records.json" in files
    assert "records.json.tmp" not in files


def test_backup_and_rotate(store):
    for i in range(3):
        store.save("mistakes", [{"i": i}])
    store._last_backup_day = None  # 允许再次备份
    store.backup("manual")
    store.backup("manual")
    backups = [d for d in os.listdir(store.backup_dir) if d.startswith("backup-")]
    assert len(backups) == 2
    # 备份内容可读
    data = json.load(open(os.path.join(
        store.backup_dir, sorted(backups)[-1], "mistakes.json"), encoding="utf-8"))
    assert data == [{"i": 2}]


def test_rotate_keeps_max(store, tmp_path):
    settings = {"max_backups": 3}
    store.save("settings", settings)
    for i in range(5):
        store._last_backup_day = None
        store.backup("manual")
    backups = [d for d in os.listdir(store.backup_dir) if d.startswith("backup-")]
    assert len(backups) == 3
