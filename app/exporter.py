# -*- coding: utf-8 -*-
"""导出:Markdown / CSV / zip 全量备份。导出文件写入 exports/ 目录。"""
import csv
import io
import os
import zipfile
from datetime import datetime

EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports"
)

SUBJECT_NAMES = {"math": "数学", "cs408": "408", "english": "英语", "all": "全部"}


def _ensure_dir():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    return EXPORT_DIR


def _md_escape_table(rows):
    if not rows:
        return ""
    header = rows[0]
    lines = ["| " + " | ".join(header) + " |",
             "|" + "---|" * len(header)]
    for r in rows[1:]:
        lines.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in r) + " |")
    return "\n".join(lines)


def mistakes_to_md(mistakes, knowledge):
    kp = {k["id"]: k["name"] for k in knowledge}
    out = ["# 错题本导出", "", "导出时间:%s" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    for m in mistakes:
        out.append("## %s" % (m.get("question_md") or "(无题面)").strip().splitlines()[0][:60])
        out.append("")
        out.append("- 科目:%s | 题型:%s | 难度:%s" % (
            SUBJECT_NAMES.get(m.get("subject"), m.get("subject")),
            m.get("qtype", "-"), m.get("difficulty", "-")))
        out.append("- 知识点:%s" % "、".join(kp.get(k, k) for k in m.get("knowledge_ids") or []) or "-")
        out.append("- 来源:%s" % m.get("source", "-"))
        out.append("- 错误原因:%s" % m.get("error_reason", "-"))
        out.append("- 间隔:%s 天 | 难度系数:%s | 已忘记 %s 次 | 下次复习:%s" % (
            m.get("interval_days", 0), m.get("ease", "-"),
            m.get("lapses", 0), m.get("next_review", "-")))
        out.append("")
        out.append("**题面**")
        out.append("")
        out.append(m.get("question_md", ""))
        out.append("")
        if m.get("my_answer_md"):
            out.append("**我的做法**")
            out.append("")
            out.append(m["my_answer_md"])
            out.append("")
        out.append("**正确解答(可核验过程)**")
        out.append("")
        out.append(m.get("solution_md") or m.get("correct_answer_md") or "")
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


def knowledge_to_md(knowledge, catalog):
    ch = {}
    for track in (catalog.get("tracks") or {}).values():
        for c in track.get("chapters") or []:
            ch[c["id"]] = "%s · %s" % (track.get("name", ""), c.get("name", ""))
    out = ["# 知识库导出", "", "导出时间:%s" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    by_subject = {}
    for k in knowledge:
        by_subject.setdefault(k.get("subject", "?"), []).append(k)
    for subj, items in by_subject.items():
        out.append("# %s" % SUBJECT_NAMES.get(subj, subj))
        out.append("")
        for k in items:
            status = k.get("status", "not_started")
            out.append("## %s(%s)" % (k["name"], status))
            out.append("")
            out.append("- 章节:%s" % ch.get(k.get("chapter_id"), k.get("chapter_id", "-")))
            out.append("- 标签:%s" % "、".join(k.get("tags") or []))
            out.append("- 前置:%s" % "、".join(k.get("prerequisites") or []) or "-")
            out.append("- 依据:%s" % k.get("source", "-"))
            out.append("")
            out.append(k.get("content_md", ""))
            out.append("")
            for f in k.get("formulas") or []:
                out.append("**公式**:`%s`" % f.get("latex", ""))
                out.append("- 适用条件:%s" % f.get("condition", "-"))
                out.append("- 常见误用:%s" % f.get("misuse", "-"))
                out.append("")
            for c in k.get("comparisons") or []:
                out.append("**对比:%s**" % c.get("with", ""))
                out.append("")
                for dim, vals in (c.get("table") or {}).items():
                    out.append("- %s:%s" % (dim, " / ".join(vals)))
                out.append("")
            out.append("---")
            out.append("")
    return "\n".join(out)


def records_to_csv(records):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "date", "subject", "session_type", "total",
                "correct", "accuracy", "duration_min"])
    for r in records:
        total = r.get("total", 0) or 0
        correct = r.get("correct", 0) or 0
        acc = ("%.0f%%" % (100.0 * correct / total)) if total else ""
        w.writerow([r.get("id"), r.get("date"), r.get("subject"),
                    r.get("session_type"), total, correct, acc,
                    r.get("duration_min")])
    return buf.getvalue()


def vocab_to_md(vocab):
    out = ["# 生词与长难句导出", "",
           "导出时间:%s" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    for v in vocab:
        kind = "单词" if v.get("kind") == "word" else "长难句"
        out.append("## [%s] %s" % (kind, v.get("text", "")))
        out.append("")
        if v.get("context_md"):
            out.append("原文:%s" % v["context_md"])
            out.append("")
        out.append(v.get("meaning_md", ""))
        out.append("")
        out.append("- 出处:%s | 忘记次数:%s | 下次复习:%s" % (
            v.get("source", "-"), v.get("lapses", 0), v.get("next_review", "-")))
        out.append("")
    return "\n".join(out)


def reflections_to_md(reflections):
    out = ["# 反思记录导出", "",
           "导出时间:%s" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    for r in reflections:
        ex = r.get("extracted") or {}
        out.append("## %s(%s)" % (r.get("date", ""), "AI 提取" if ex.get("source") == "ai" else "规则提取"))
        out.append("")
        out.append(r.get("raw_text", ""))
        out.append("")
        if ex.get("subjects"):
            out.append("- 科目:%s" % "、".join(ex["subjects"]))
        if ex.get("weak_points"):
            out.append("- 自我薄弱点:%s" % "、".join(ex["weak_points"]))
        if ex.get("mood"):
            out.append("- 状态:%s" % ex["mood"])
        if ex.get("next_plan"):
            out.append("- 下一步:%s" % ex["next_plan"])
        out.append("")
    return "\n".join(out)


def export(what, store):
    """what: mistakes | knowledge | records | vocab | all(→zip)。返回文件路径。"""
    _ensure_dir()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if what == "mistakes":
        path = os.path.join(EXPORT_DIR, "错题本-%s.md" % stamp)
        with open(path, "w", encoding="utf-8") as f:
            f.write(mistakes_to_md(store.load("mistakes"), store.load("knowledge")))
        return path
    if what == "knowledge":
        path = os.path.join(EXPORT_DIR, "知识库-%s.md" % stamp)
        with open(path, "w", encoding="utf-8") as f:
            f.write(knowledge_to_md(store.load("knowledge"), store.load("catalog")))
        return path
    if what == "records":
        path = os.path.join(EXPORT_DIR, "练习记录-%s.csv" % stamp)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(records_to_csv(store.load("records")))
        return path
    if what == "vocab":
        path = os.path.join(EXPORT_DIR, "生词长难句-%s.md" % stamp)
        with open(path, "w", encoding="utf-8") as f:
            f.write(vocab_to_md(store.load("vocab")))
        return path
    if what == "all":
        path = os.path.join(EXPORT_DIR, "全量数据-%s.zip" % stamp)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for name in ("settings", "catalog", "knowledge", "mistakes",
                         "records", "vocab", "plan", "reflections", "coach"):
                p = os.path.join(store.data_dir, name + ".json")
                if os.path.exists(p):
                    z.write(p, name + ".json")
            img_dir = os.path.join(store.data_dir, "images")
            if os.path.isdir(img_dir):
                for fn in os.listdir(img_dir):
                    fp = os.path.join(img_dir, fn)
                    if os.path.isfile(fp):
                        z.write(fp, "images/" + fn)
            z.writestr("错题本.md", mistakes_to_md(store.load("mistakes"), store.load("knowledge")))
            z.writestr("知识库.md", knowledge_to_md(store.load("knowledge"), store.load("catalog")))
            z.writestr("练习记录.csv", records_to_csv(store.load("records")))
            z.writestr("生词长难句.md", vocab_to_md(store.load("vocab")))
            z.writestr("反思记录.md", reflections_to_md(store.load("reflections")))
        return path
    raise ValueError("unknown export target: %s" % what)
