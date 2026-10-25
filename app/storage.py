# -*- coding: utf-8 -*-
"""存储层:JSON 文件读写(原子写)、启动/每日备份与轮转。"""
import json
import os
import shutil
import threading
import time

_BASE = os.environ.get("DX_DATA_DIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE, "data")
BACKUP_DIR = os.path.join(_BASE, "backups")

COLLECTIONS = {
    "settings": dict,
    "catalog": dict,
    "knowledge": list,
    "mistakes": list,
    "records": list,
    "vocab": list,
    "plan": dict,
    "reflections": list,
    "coach": list,
    "users": list,
    "sessions": list,
    "goals": dict,
    "motivations": list,
    "institutions": list,
    "sources": list,
    "search_records": list,
    "universities": list,
    "questions": list,
    "train": dict,
    "train_state": dict,
    "experience_posts": list,
}


def _default(name):
    return {} if COLLECTIONS[name] is dict else []


class Store:
    """按集合读写 data/ 下的 JSON 文件。所有写操作原子化。"""

    def __init__(self, data_dir=DATA_DIR, backup_dir=BACKUP_DIR):
        self.data_dir = data_dir
        self.backup_dir = backup_dir
        self._lock = threading.RLock()
        self._last_backup_day = None
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(backup_dir, exist_ok=True)
        self._cache = {}

    def _path(self, name):
        return os.path.join(self.data_dir, name + ".json")

    def load(self, name):
        if name not in COLLECTIONS:
            raise KeyError("unknown collection: %s" % name)
        with self._lock:
            path = self._path(name)
            if not os.path.exists(path):
                return _default(name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                # 文件损坏时不要崩:返回默认值,调用方重新保存即可覆盖
                return _default(name)

    def save(self, name, data):
        if name not in COLLECTIONS:
            raise KeyError("unknown collection: %s" % name)
        with self._lock:
            path = self._path(name)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            self._maybe_daily_backup()

    def update(self, name, mutate):
        """读-改-写一体,带锁,适合并发不高的本地场景。"""
        with self._lock:
            data = self.load(name)
            result = mutate(data)
            self.save(name, data)
            return result if result is not None else data

    # ---------- 备份 ----------
    def backup(self, tag="manual"):
        with self._lock:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            dest = os.path.join(self.backup_dir, "backup-%s-%s" % (stamp, tag))
            n = 1
            while os.path.exists(dest):
                n += 1
                dest = os.path.join(
                    self.backup_dir, "backup-%s-%s-%d" % (stamp, tag, n))
            shutil.copytree(self.data_dir, dest)
            self._rotate()
            return dest

    def _maybe_daily_backup(self):
        today = time.strftime("%Y-%m-%d")
        if self._last_backup_day == today:
            return
        self._last_backup_day = today
        try:
            self.backup("auto")
        except OSError:
            pass  # 备份失败不阻塞主流程

    def _rotate(self):
        settings = self.load("settings")
        keep = int(settings.get("max_backups", 14))
        backups = sorted(
            d for d in os.listdir(self.backup_dir) if d.startswith("backup-")
        )
        for old in backups[:-keep] if keep > 0 else []:
            shutil.rmtree(os.path.join(self.backup_dir, old), ignore_errors=True)
