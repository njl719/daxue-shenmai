# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app.seed import seed_if_empty
from app.server import create_app


@pytest.fixture
def client(tmp_path):
    app, store = create_app(
        data_dir=str(tmp_path / "data"), backup_dir=str(tmp_path / "backups"))
    seed_if_empty(store)
    from app import migrate as migrate_mod
    from app import universities as _U
    # 测试离线化(N4):迁移链不抓 Wikimedia 远程图,直接走本地 fallback,
    # 消除夹具级网络超时(无代理时每夹具拖慢数十秒);生产迁移路径不受影响
    _U.fetch_university_image = lambda uni: None
    migrate_mod.run_migrations(store)  # 与 main 一致:种子之后迁移
    store._maybe_daily_backup = lambda: None  # 测试中关闭自动备份
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.store = store
        # 建号并登录(认证后的会话)
        c.post("/api/setup", json={"username": "tester", "password": "secret123"})
        yield c
