# -*- coding: utf-8 -*-
"""数据库迁移:JSON 存储的 schema 版本管理与升级。

当前版本 SCHEMA_VERSION=3:
  v1 → v2:引入账号体系(users/sessions),settings.access_code 弃用;
          新增 goals/motivations/institutions/sources/search_records 集合。
  v2 → v3:目录补充政治科目与英语题型模块(11408 默认方案,标注待核验);
          settings.subjects 增加 politics 配置(默认停用,由用户启用)。
每次启动自动执行未应用的迁移,并记录 schema_version,保证老数据无损升级。
"""
import datetime
import json
import os

from .storage import Store

MIGRATIONS = []
SCHEMA_VERSION = 5

POLITICS_TRACK = {
    "name": "思想政治理论(101)", "subject": "politics",
    "source": "依据公开考研政治大纲模块结构整理,章节命名待对照当年大纲核验",
    "chapters": [
        {"id": "pol-ch1", "name": "马克思主义基本原理"},
        {"id": "pol-ch2", "name": "毛泽东思想和中国特色社会主义理论体系概论"},
        {"id": "pol-ch3", "name": "中国近现代史纲要"},
        {"id": "pol-ch4", "name": "思想道德与法治"},
        {"id": "pol-ch5", "name": "形势与政策以及当代世界经济与政治"},
    ],
}
ENGLISH_EXTRA = [
    {"id": "en-ch5", "name": "完形填空"},
    {"id": "en-ch6", "name": "阅读理解 A(传统阅读)"},
    {"id": "en-ch7", "name": "阅读理解 B(新题型)"},
    {"id": "en-ch8", "name": "翻译(英译汉)"},
    {"id": "en-ch9", "name": "写作 A(小作文/应用文)"},
    {"id": "en-ch10", "name": "写作 B(大作文)"},
]


def migration(from_ver):
    def deco(fn):
        MIGRATIONS.append((from_ver, fn))
        return fn
    return deco


@migration(1)
def _v1_to_v2(store):
    """v1→v2:迁移访问码为账号体系提示;初始化新集合默认值。"""
    settings = store.load("settings")
    if settings.get("access_code"):
        # 旧访问码不再用于认证(改由账号密码承担),移除明文
        settings.pop("access_code", None)
        store.save("settings", settings)
    if not store.load("goals"):
        store.save("goals", {"institution": None, "program": "", "subjects": [],
                             "milestones": [], "notes": ""})
    for name, default in (("motivations", []), ("institutions", []),
                          ("sources", []), ("search_records", [])):
        if not store.load(name):
            store.save(name, default)
    return "v1→v2 完成:账号体系就绪,新集合已初始化"


@migration(2)
def _v2_to_v3(store):
    """v2→v3:11408 目录补全(政治科目/英语题型/数一标注),默认方案可配置非硬编码。"""
    catalog = store.load("catalog")
    tracks = catalog.setdefault("tracks", {})
    changed = False
    if "politics" not in [t.get("subject") for t in tracks.values()]:
        tracks["politics"] = dict(POLITICS_TRACK)
        changed = True
    en = tracks.get("english-rd")
    if en is not None:
        have = {c["id"] for c in en.get("chapters") or []}
        for c in ENGLISH_EXTRA:
            if c["id"] not in have:
                en.setdefault("chapters", []).append(c)
                changed = True
    # 目录来源与核验标注
    if "source" not in catalog:
        catalog["source"] = "章节结构依据公开考试大纲整理;具体范围以当年官方大纲为准(待核验)"
        catalog["catalog_version"] = 3
        changed = True
    if changed:
        store.save("catalog", catalog)
    settings = store.load("settings")
    subs = settings.setdefault("subjects", {})
    if "politics" not in subs:
        subs["politics"] = {"enabled": False, "priority": 4, "minutes": 30}
        settings["daily_minutes"] = int(settings.get("daily_minutes", 240))
        store.save("settings", settings)
    return "v2→v3 完成:政治/英语模块补全(待核验标注),politics 科目配置已加入(默认停用)"


@migration(3)
def _v3_to_v4(store):
    """v3→v4:目标院校资料库(10 所候选,含自由许可图片管线与完整度追踪)。"""
    from . import universities as U
    n = U.seed_universities(store, fetch_images=True)
    return "v3→v4 完成:目标院校资料库初始化(%d 所)" % n


@migration(4)
def _v4_to_v5(store):
    """v4→v5:题库种子(平台原创 45 题,幂等;AI 生成题由 tools/gen_questions.py 本地补充)。"""
    from . import questionseed as QS
    added = QS.seed_original_questions(store)
    return "v4→v5 完成:原创题入库 %d 题" % added


def run_migrations(store):
    """按顺序执行未应用的迁移,返回执行的描述列表。"""
    applied = []
    ver_path = os.path.join(store.data_dir, "schema_version.json")
    current = 1
    if os.path.exists(ver_path):
        try:
            with open(ver_path, encoding="utf-8") as f:
                current = json.load(f).get("version", 1)
        except (OSError, json.JSONDecodeError):
            current = 1
    if current < 1:
        current = 1
    for from_ver, fn in sorted(MIGRATIONS):
        if current <= from_ver:
            note = fn(store)
            applied.append(note)
            current = from_ver + 1
    current = max(current, SCHEMA_VERSION)
    with open(ver_path, "w", encoding="utf-8") as f:
        json.dump({"version": SCHEMA_VERSION,
                   "migrated_at": datetime.datetime.now().isoformat(timespec="seconds")},
                  f, ensure_ascii=False, indent=2)
    return applied
