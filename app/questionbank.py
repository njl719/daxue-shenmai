# -*- coding: utf-8 -*-
"""题库模块:题目结构、内容哈希去重、版权状态管理。

原则:
- 不声称拥有历年真题;每题必须带 source_type 与 copyright_status;
- AI 生成题永远标 ai_generated,不得冒充真题;
- 去重以题干归一化哈希为准,导入时返回新增/重复/无效明细。
"""
import datetime
import hashlib
import json
import re


_PUNCT_RE = re.compile("[\\s,。;:、()()【】\\[\\]?？,.“”‘’\"'—_$\\\\{}^~`-]*", re.UNICODE)


def normalize_question(text):
    """题干归一化:去空白/标点/大小写,用于哈希去重。"""
    return _PUNCT_RE.sub("", (text or "").lower())


def question_hash(text, subject):
    h = hashlib.sha256()
    h.update((subject + "|" + normalize_question(text)).encode("utf-8"))
    return h.hexdigest()[:16]


SOURCE_TYPES = ("真题", "模拟题", "教材例题", "AI 生成练习题", "自录题")
COPYRIGHT_STATUS = ("合法使用(授权/开放许可)", "来源不明-待核验", "AI 原创", "自述/本人记录")


def validate_question(q):
    """校验单题字段,返回 (normalized, error)。"""
    if q.get("subject") not in ("math", "cs408", "english", "politics"):
        return None, "subject 必须是 math/cs408/english/politics"
    text = (q.get("question_md") or "").strip()
    if not text:
        return None, "题干不能为空"
    source_type = q.get("source_type") or ""
    if source_type not in SOURCE_TYPES:
        return None, "source_type 必须是:%s" % "/".join(SOURCE_TYPES)
    # AI 生成题强制标注
    if "AI" in source_type and q.get("copyright_status") != "AI 原创":
        q = dict(q, copyright_status="AI 原创", ai_generated=True)
    elif "真题" in source_type and q.get("copyright_status") not in (
            "合法使用(授权/开放许可)", "来源不明-待核验"):
        return None, ("真题必须声明版权状态:合法使用(需授权依据)或 来源不明-待核验;"
                      "禁止默认当作可自由使用")
    q = dict(q)
    q["question_md"] = text
    q["qtype"] = q.get("qtype") or ""
    q["year"] = int(q["year"]) if str(q.get("year") or "").strip().isdigit() else None
    q["difficulty"] = max(1, min(5, int(q.get("difficulty") or 3)))
    q["options"] = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
    q["answer"] = str(q.get("answer") or "").strip().upper()
    q["solution_md"] = q.get("solution_md") or ""
    q["source_desc"] = q.get("source_desc") or ""
    q["knowledge_ids"] = q.get("knowledge_ids") or []
    if q["options"] and len(q["options"]) >= 2:
        if q["answer"] not in [chr(65 + i) for i in range(len(q["options"]))]:
            return None, "选择题 answer 必须是 A-%s" % chr(64 + len(q["options"]))
    else:
        q["options"], q["answer"] = [], ""
    q["ai_generated"] = bool(q.get("ai_generated")) or "AI" in source_type
    q["content_hash"] = question_hash(text, q["subject"])
    return q, None


def import_questions(items):
    """批量导入:返回 (valid, report)。report 含新增/重复/无效明细。"""
    valid, invalid, dup = [], [], []
    seen = set()
    for i, raw in enumerate(items):
        q, err = validate_question(raw if isinstance(raw, dict) else {})
        if err:
            invalid.append({"index": i, "error": err})
            continue
        if q["content_hash"] in seen:
            dup.append({"index": i, "hash": q["content_hash"]})
            continue
        seen.add(q["content_hash"])
        valid.append(q)
    return valid, {"total": len(items), "added": len(valid),
                   "duplicates": dup, "invalid": invalid}


def new_question_record(q, seq):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    return {"id": "qb-%04d" % seq, **{k: q[k] for k in (
        "subject", "question_md", "qtype", "year", "source_type",
        "copyright_status", "ai_generated", "options", "answer",
        "solution_md", "source_desc", "knowledge_ids", "difficulty",
        "content_hash")},
        "created": now, "archived": False}
