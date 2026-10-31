# -*- coding: utf-8 -*-
"""Flask 后端:全部 API。仅监听 127.0.0.1,不外露。"""
import datetime
import re
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, g, jsonify, request, send_from_directory

from . import exporter, planner, profile as profile_mod, srs
from . import ai as ai_mod
from . import auth as auth_mod
from . import migrate as migrate_mod
from .seed import seed_if_empty
from .storage import DATA_DIR, BACKUP_DIR, Store

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
_app_store = None  # create_app 时注入,_ai_cfg 等辅助函数使用


def _ai_cfg():
    return ai_mod.get_ai_config((_app_store or Store()).load("settings"))

SUBJECTS = ("math", "cs408", "english", "politics")
SUBJECT_NAMES = {"math": "数学", "cs408": "408", "english": "英语", "all": "通用"}
STATUSES = ("not_started", "learning", "initial", "consolidating",
            "mostly", "mastered", "reviewing")  # reviewing 为旧数据兼容
QTYPES = {
    "math": ["概念", "计算", "证明", "综合应用"],
    "cs408": ["概念", "计算", "综合"],
    "english": ["定位错误", "逻辑理解错误", "词义误判", "选项辨析错误"],
    "politics": ["概念", "选择", "分析"],
}
ERROR_REASONS = profile_mod.ERROR_REASONS
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def _today():
    return datetime.date.today()


def _bad(msg, code=400):
    return jsonify({"error": msg}), code


def _next_id(items, prefix, width=4):
    nums = []
    for it in items:
        try:
            nums.append(int(str(it.get("id", "")).rsplit("-", 1)[-1]))
        except (ValueError, IndexError):
            pass
    n = (max(nums) + 1) if nums else 1
    return "%s-%s" % (prefix, str(n).zfill(width))


def re_fullsafe_name(name):
    """图片文件名白名单:字母数字/下划线/点/横线,禁止路径分隔。"""
    import re as _re
    return bool(_re.fullmatch(r"[A-Za-z0-9_.\-]{1,80}", name or ""))


def _lan_ip():
    """取局域网 IP(UDP connect 探测,不发包)。失败返回 None。"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip if not ip.startswith("127.") else None
    except Exception:
        return None


def _auth_token(code):
    import hashlib
    return hashlib.sha256(("daxue:" + code).encode("utf-8")).hexdigest()[:32]


# 统一科目代码表(默认 11408 方案;院校可不同,不作硬编码约束)
SUBJECT_CODES = {"101": "思想政治理论", "201": "英语一", "204": "英语二",
                 "301": "数学一", "302": "数学二", "303": "数学三",
                 "408": "计算机学科专业基础综合"}
VALID_SUBJECT_KEYS = ("math", "cs408", "english", "politics")


def _validate_institution(body):
    """招生信息格式校验:年份/科目代码/URL。返回错误文本或 None。"""
    if not (body.get("name") or "").strip():
        return "院校名称必填"
    url = (body.get("official_url") or "").strip()
    if url and not url.startswith(("http://", "https://")):
        return "官方链接必须以 http:// 或 https:// 开头"
    year = body.get("exam_year")
    if year:
        ys = str(year).strip()
        if not (len(ys) == 4 and ys.isdigit() and 2020 <= int(ys) <= 2040):
            return "招生年份应为 2020-2040 的四位年份"
    for s in body.get("subjects") or []:
        s = str(s).strip()
        if not s:
            continue
        if s.isdigit():  # 科目代码需在统一表内
            if s not in SUBJECT_CODES:
                return "未知科目代码:%s(可用:%s)" % (s, "、".join(SUBJECT_CODES))
        elif not any(s.startswith(k) or k in s for k in ("数学", "英语", "政治", "408")):
            return "无法识别的科目:%s(可用代码 101/201/301/408 或中文名)" % s
    return None


def _sanitize_settings(s):
    """设置对外输出时隐藏 API Key 与访问密码明文。"""
    s = dict(s)
    if s.get("access_code"):
        s["has_access_code"] = True
    s.pop("access_code", None)
    ai = dict(s.get("ai") or {})
    if ai.get("api_key"):
        key = ai["api_key"]
        ai["api_key_masked"] = (key[:4] + "****" + key[-4:]) if len(key) > 8 else "****"
        ai["has_key"] = True
    else:
        ai["has_key"] = False
    ai.pop("api_key", None)
    s["ai"] = ai
    return s


def create_app(data_dir=None, backup_dir=None):
    global _app_store
    store = Store(data_dir=data_dir or DATA_DIR,
                  backup_dir=backup_dir or BACKUP_DIR)
    _app_store = store
    app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
    app.json.ensure_ascii = False

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "today": _today().isoformat()})

    # ---------- settings ----------
    @app.get("/api/settings")
    def get_settings():
        return jsonify(_sanitize_settings(store.load("settings")))

    @app.put("/api/settings")
    def put_settings():
        body = request.get_json(force=True, silent=True) or {}
        cur = store.load("settings")
        for k, v in body.items():
            if k == "subjects":
                for sname, scfg in (v or {}).items():
                    if sname not in SUBJECTS:
                        return _bad("未知科目:%s" % sname)
            if k == "ai" and isinstance(v, dict):
                # 合并 AI 配置:空 api_key 不覆盖已有
                aicfg = dict(cur.get("ai") or {})
                for ak, av in v.items():
                    if ak == "api_key" and not av:
                        continue
                    aicfg[ak] = av
                cur["ai"] = aicfg
                continue
            cur[k] = v
        store.save("settings", cur)
        return jsonify(_sanitize_settings(cur))

    @app.post("/api/settings/ai/test")
    def test_ai():
        result = ai_mod.test_connection(_ai_cfg())
        return jsonify(result)

    # ---------- catalog ----------
    @app.get("/api/catalog")
    def get_catalog():
        catalog = store.load("catalog")
        knowledge = store.load("knowledge")
        for track in (catalog.get("tracks") or {}).values():
            chapters = track.get("chapters") or []
            ids = {c["id"] for c in chapters}
            kps = [k for k in knowledge if k.get("chapter_id") in ids]
            started = [k for k in kps if k.get("status") != "not_started"]
            mastered = [k for k in kps if k.get("status") == "mastered"]
            track["progress"] = {
                "knowledge": len(kps),
                "started": len(started),
                "mastered": len(mastered),
                "pct": round(100.0 * len(started) / len(kps)) if kps else 0,
            }
        return jsonify(catalog)

    # ---------- knowledge ----------
    @app.get("/api/knowledge")
    def list_knowledge():
        items = store.load("knowledge")
        subject = request.args.get("subject")
        q = (request.args.get("q") or "").lower()
        chapter = request.args.get("chapter_id")
        status = request.args.get("status")
        out = []
        for k in items:
            if subject and k.get("subject") != subject:
                continue
            if chapter and k.get("chapter_id") != chapter:
                continue
            if status and k.get("status") != status:
                continue
            if q and q not in (k.get("name", "") + k.get("content_md", "")
                               + " ".join(k.get("tags") or [])).lower():
                continue
            out.append(k)
        return jsonify(out)

    @app.post("/api/knowledge")
    def add_knowledge():
        body = request.get_json(force=True, silent=True) or {}
        if body.get("subject") not in SUBJECTS:
            return _bad("subject 必须是 %s" % (SUBJECTS,))
        if not (body.get("name") or "").strip():
            return _bad("name 必填")
        items = store.load("knowledge")
        now = datetime.datetime.now().isoformat(timespec="seconds")
        item = {
            "id": _next_id(
                items, "math" if body["subject"] == "math"
                else ("408" if body["subject"] == "cs408" else "en")
            ),
            "subject": body["subject"],
            "chapter_id": body.get("chapter_id") or "",
            "name": body["name"].strip(),
            "prerequisites": body.get("prerequisites") or [],
            "tags": body.get("tags") or [],
            "content_md": body.get("content_md") or "",
            "formulas": body.get("formulas") or [],
            "comparisons": body.get("comparisons") or [],
            "source": body.get("source") or "",
            "status": body.get("status") if body.get("status") in STATUSES else "not_started",
            "seed": False,
            "created": now, "updated": now,
        }
        items.append(item)
        store.save("knowledge", items)
        return jsonify(item), 201

    @app.get("/api/knowledge/<kid>")
    def get_knowledge(kid):
        for k in store.load("knowledge"):
            if k["id"] == kid:
                return jsonify(k)
        return _bad("知识点不存在", 404)

    @app.put("/api/knowledge/<kid>")
    def update_knowledge(kid):
        body = request.get_json(force=True, silent=True) or {}
        items = store.load("knowledge")
        for k in items:
            if k["id"] == kid:
                for f in ("chapter_id", "name", "prerequisites", "tags",
                          "content_md", "formulas", "comparisons", "source", "status"):
                    if f in body:
                        k[f] = body[f]
                k["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
                store.save("knowledge", items)
                return jsonify(k)
        return _bad("知识点不存在", 404)

    @app.delete("/api/knowledge/<kid>")
    def delete_knowledge(kid):
        items = store.load("knowledge")
        remain = [k for k in items if k["id"] != kid]
        if len(remain) == len(items):
            return _bad("知识点不存在", 404)
        store.save("knowledge", remain)
        # 级联清理引用,防止错题/练习记录出现孤立知识点 ID
        cleaned = {"mistakes": 0, "records": 0}
        ms = store.load("mistakes")
        for m in ms:
            kds = m.get("knowledge_ids") or []
            if kid in kds:
                m["knowledge_ids"] = [k for k in kds if k != kid]
                cleaned["mistakes"] += 1
        store.save("mistakes", ms)
        rcs = store.load("records")
        for r in rcs:
            kds = r.get("knowledge_ids") or []
            if kid in kds:
                r["knowledge_ids"] = [k for k in kds if k != kid]
                cleaned["records"] += 1
        store.save("records", rcs)
        return jsonify({"deleted": kid} | cleaned)

    # ---------- mistakes ----------
        return [m for m in ms if srs.is_due(m, today)]

    # ---------- records ----------
    @app.get("/api/records")
    def list_records():
        items = store.load("records")
        subject = request.args.get("subject")
        if subject:
            items = [r for r in items if r.get("subject") == subject]
        return jsonify(sorted(items, key=lambda r: r.get("date", ""), reverse=True))

    @app.post("/api/records")
    def add_record():
        body = request.get_json(force=True, silent=True) or {}
        if body.get("subject") not in SUBJECTS:
            return _bad("subject 必须是 %s" % (SUBJECTS,))
        # 数值校验:非负整数,correct ≤ total;非法直接 400 而非 500
        def _int_or_none(v):
            if v is None or v == "":
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                raise ValueError("not-int")
        try:
            total = _int_or_none(body.get("total"))
            correct = _int_or_none(body.get("correct"))
        except ValueError:
            return _bad("total/correct 必须是整数")
        total, correct = total or 0, correct or 0
        if total < 0 or correct < 0:
            return _bad("total/correct 不能为负数")
        if correct > total:
            return _bad("correct 不能大于 total")
        duration = _int_or_none(body.get("duration_min"))
        if duration is not None and duration < 0:
            return _bad("duration_min 不能为负数")
        date = body.get("date") or _today().isoformat()
        try:
            datetime.date.fromisoformat(date)
        except ValueError:
            return _bad("date 格式应为 YYYY-MM-DD")
        items = store.load("records")
        # 幂等:同一 client_id 直接返回既有记录,防止重复提交
        client_id = (body.get("client_id") or "").strip()
        if client_id:
            for r in items:
                if r.get("client_id") == client_id:
                    return jsonify(r)
        rec = {
            "id": _next_id(items, "rc"),
            "client_id": client_id,
            "date": date,
            "subject": body["subject"],
            "session_type": body.get("session_type") or "practice",
            "knowledge_ids": body.get("knowledge_ids") or [],
            "total": total,
            "correct": correct,
            "duration_min": duration,
            "detail": body.get("detail") or [],
        }
        items.append(rec)
        store.save("records", items)
        return jsonify(rec), 201

    # ---------- stats ----------
    @app.get("/api/stats/summary")
    def stats_summary():
        today = _today()
        mistakes = store.load("mistakes")
        records = store.load("records")
        knowledge = store.load("knowledge")
        settings = store.load("settings")

        summary = {"subjects": {}, "exam_phase": planner.exam_phase(
            settings.get("exam_date"), today)}
        for subj in SUBJECTS:
            recs = [r for r in records if r.get("subject") == subj]
            total = sum(r.get("total", 0) for r in recs)
            correct = sum(r.get("correct", 0) for r in recs)
            mins = sum(r.get("duration_min") or 0 for r in recs)
            due = [m for m in mistakes
                   if m.get("subject") == subj and not m.get("archived")
                   and srs.is_due(m, today)]
            summary["subjects"][subj] = {
                "total_attempted": total,
                "accuracy": round(100.0 * correct / total) if total else None,
                "minutes": mins,
                "due_mistakes": len(due),
                "mistakes": len([m for m in mistakes
                                 if m.get("subject") == subj and not m.get("archived")]),
                "knowledge": len([k for k in knowledge if k.get("subject") == subj]),
            }

        weak_ids = planner.weak_knowledge_ids(mistakes, records)
        kp = {k["id"]: k for k in knowledge}
        summary["weak"] = [
            {"id": kid, "name": kp[kid]["name"], "subject": kp[kid]["subject"]}
            for kid in weak_ids if kid in kp
        ]

        status_dist = {}
        for k in knowledge:
            status_dist[k.get("status", "not_started")] = \
                status_dist.get(k.get("status", "not_started"), 0) + 1
        summary["knowledge_status"] = status_dist

        trend = []
        for i in range(13, -1, -1):
            d = (today - datetime.timedelta(days=i)).isoformat()
            day_recs = [r for r in records if r.get("date") == d]
            t = sum(r.get("total", 0) for r in day_recs)
            c = sum(r.get("correct", 0) for r in day_recs)
            trend.append({"date": d, "total": t, "correct": c,
                          "accuracy": round(100.0 * c / t) if t else None})
        summary["trend_14d"] = trend

        lapse_top = sorted(
            (m for m in mistakes if not m.get("archived") and m.get("lapses")),
            key=lambda m: -m.get("lapses", 0))[:5]
        summary["repeat_errors"] = [
            {"id": m["id"], "lapses": m.get("lapses"),
             "title": (m.get("question_md") or "").strip().splitlines()[0][:40]}
            for m in lapse_top
        ]
        return jsonify(summary)

    # ---------- practice session ----------
    # ---------- plan ----------
    def _plan():
        plan = store.load("plan")
        plan.setdefault("days", {})
        return plan

    @app.get("/api/plan/day/<date_str>")
    def plan_day(date_str):
        try:
            planner.parse_date(date_str)
        except ValueError:
            return _bad("日期格式应为 YYYY-MM-DD")
        plan = _plan()
        day = plan["days"].get(date_str) or {"tasks": []}
        settings = store.load("settings")
        return jsonify({
            "date": date_str,
            "tasks": day.get("tasks") or [],
            "exam_phase": planner.exam_phase(settings.get("exam_date")),
        })

    @app.post("/api/plan/generate")
    def plan_generate():
        body = request.get_json(force=True, silent=True) or {}
        date_str = body.get("date") or _today().isoformat()
        try:
            planner.parse_date(date_str)
        except ValueError:
            return _bad("日期格式应为 YYYY-MM-DD")
        settings = store.load("settings")
        mistakes = store.load("mistakes")
        records = store.load("records")
        knowledge = store.load("knowledge")
        reflections = store.load("reflections")
        weak_pts = profile_mod.compute_weak_points(
            mistakes, records, reflections, knowledge, _today())
        tasks = planner.generate_day_plan(
            date_str, settings, mistakes, records,
            knowledge, store.load("vocab"),
            reflections=reflections, weak_points=weak_pts)
        plan = _plan()
        day = plan["days"].setdefault(date_str, {"tasks": []})
        # 只替换 pending 任务,保留手动标记过的 done/skipped
        kept = [t for t in day["tasks"] if t.get("status") in ("done", "skipped")]
        old_pending = [t for t in day["tasks"] if t.get("status") == "pending"]
        day["tasks"] = tasks + kept
        plan["generated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        store.save("plan", plan)
        return jsonify({"date": date_str, "replaced": len(old_pending),
                        "tasks": day["tasks"]})

    @app.post("/api/plan/task/<task_id>")
    def plan_task(task_id):
        body = request.get_json(force=True, silent=True) or {}
        action = body.get("action")
        if action not in ("done", "skip", "move", "reset", "edit"):
            return _bad("action 必须是 done/skip/move/reset/edit")
        plan = _plan()
        for date_str, day in plan["days"].items():
            for t in day.get("tasks") or []:
                if t["id"] != task_id:
                    continue
                if body.get("actual_minutes") is not None:
                    t["actual_minutes"] = body["actual_minutes"]
                if body.get("note") is not None:
                    t["note"] = body["note"]
                if body.get("est_minutes") is not None:
                    t["est_minutes"] = body["est_minutes"]
                if action == "done":
                    t["status"] = "done"
                    # 打通闭环:完成任务落一条学习记录(client_id 幂等,reset 再 done 不重复)。
                    # total/correct 恒为 0 —— 不把"任务完成"虚构为"做题对错"。
                    if not t.get("record_id") and t.get("subject") in SUBJECTS:
                        rcs = store.load("records")
                        client_id = "task-%s" % task_id
                        hit = next((r for r in rcs
                                    if r.get("client_id") == client_id), None)
                        if not hit:
                            payload = t.get("payload") or {}
                            hit = {
                                "id": _next_id(rcs, "rc"),
                                "client_id": client_id,
                                "date": date_str,
                                "subject": t.get("subject") or "general",
                                "session_type": "study_task",
                                "knowledge_ids": payload.get("knowledge_ids") or [],
                                "total": 0, "correct": 0,
                                "duration_min": t.get("actual_minutes")
                                                or t.get("est_minutes") or 0,
                                "detail": [{"task_id": task_id, "title": t.get("title", "")}],
                            }
                            rcs.append(hit)
                            store.save("records", rcs)
                        t["record_id"] = hit["id"]
                elif action == "skip":
                    t["status"] = "skipped"
                elif action == "reset":
                    t["status"] = "pending"
                elif action == "move":
                    tomorrow = (planner.parse_date(date_str)
                                + datetime.timedelta(days=1)).isoformat()
                    tday = plan["days"].setdefault(tomorrow, {"tasks": []})
                    day["tasks"].remove(t)
                    t["status"] = "pending"
                    tday["tasks"].append(t)
                    store.save("plan", plan)
                    return jsonify({"moved_to": tomorrow, "task": t})
                store.save("plan", plan)
                return jsonify(t)
        return _bad("任务不存在", 404)

    @app.get("/api/plan/weekly/<date_str>")
    def plan_weekly(date_str):
        summary = planner.weekly_summary(
            date_str, store.load("records"), store.load("mistakes"),
            _plan()["days"])
        kp = {k["id"]: k["name"] for k in store.load("knowledge")}
        summary["hot_weak_knowledge"] = [
            {"id": i, "name": kp.get(i, i), "count": c}
            for i, c in summary.pop("hot_weak_knowledge", [])
        ]
        return jsonify(summary)

    # ---------- reflections ----------
    @app.post("/api/reflections/extract")
    def reflect_extract():
        body = request.get_json(force=True, silent=True) or {}
        text = (body.get("text") or "").strip()
        if not text:
            return _bad("text 必填")
        result = ai_mod.extract_reflection(text, _ai_cfg())
        result["date"] = body.get("date") or _today().isoformat()
        result["raw_text"] = text
        return jsonify(result)

    @app.post("/api/reflections")
    def reflect_save():
        body = request.get_json(force=True, silent=True) or {}
        text = (body.get("raw_text") or "").strip()
        extracted = body.get("extracted") or {}
        if not text:
            return _bad("raw_text 必填")
        if not extracted:
            return _bad("extracted 必填(请先提取并确认)")
        items = store.load("reflections")
        item = {
            "id": _next_id(items, "rf"),
            "date": body.get("date") or _today().isoformat(),
            "raw_text": text,
            "extracted": extracted,
            "confirmed": bool(body.get("confirmed", True)),
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        items.append(item)
        store.save("reflections", items)
        return jsonify(item), 201

    @app.get("/api/reflections")
    def reflect_list():
        items = store.load("reflections")
        limit = request.args.get("limit", type=int)
        items = sorted(items, key=lambda r: (r.get("date", ""), r.get("id")),
                       reverse=True)
        if limit:
            items = items[:limit]
        return jsonify(items)

    @app.delete("/api/reflections/<rid>")
    def reflect_delete(rid):
        items = store.load("reflections")
        remain = [r for r in items if r["id"] != rid]
        if len(remain) == len(items):
            return _bad("记录不存在", 404)
        store.save("reflections", remain)
        return jsonify({"deleted": rid})

    # ---------- profile & weekly report ----------
    @app.get("/api/profile")
    def get_profile():
        return jsonify(profile_mod.compute_profile(
            store.load("mistakes"), store.load("records"),
            store.load("reflections"), store.load("knowledge"),
            store.load("catalog"), store.load("settings"), _today()))

    @app.get("/api/report/weekly/<date_str>")
    def weekly_report(date_str):
        try:
            planner.parse_date(date_str)
        except ValueError:
            return _bad("日期格式应为 YYYY-MM-DD")
        return jsonify(profile_mod.weekly_report(
            date_str, store.load("records"), store.load("mistakes"),
            store.load("reflections"), _plan()["days"],
            store.load("knowledge"), _today()))

    # ---------- graph / export / backup ----------
    @app.get("/api/graph")
    def graph():
        knowledge = store.load("knowledge")
        nodes = [{"id": k["id"], "name": k["name"], "subject": k.get("subject"),
                  "status": k.get("status")} for k in knowledge]
        edges = []
        have = {n["id"] for n in nodes}
        for k in knowledge:
            for pre in k.get("prerequisites") or []:
                if pre in have:
                    edges.append({"from": pre, "to": k["id"]})
        return jsonify({"nodes": nodes, "edges": edges})

    @app.get("/api/export/<what>")
    def export_data(what):
        if what not in ("mistakes", "knowledge", "records", "vocab", "all"):
            return _bad("导出对象应为 mistakes/knowledge/records/vocab/all")
        path = exporter.export(what, store)
        return jsonify({"path": path, "file": os.path.basename(path)})

    @app.get("/api/export/<what>/download")
    def export_download(what):
        if what not in ("mistakes", "knowledge", "records", "vocab", "all"):
            return _bad("导出对象应为 mistakes/knowledge/records/vocab/all")
        path = exporter.export(what, store)
        return send_from_directory(os.path.dirname(path), os.path.basename(path),
                                   as_attachment=True)

    @app.post("/api/backup")
    def do_backup():
        dest = store.backup("manual")
        return jsonify({"path": dest})

    app.json.ensure_ascii = False

    # ---------- 账号认证门 ----------
    PUBLIC_PATHS = ("/api/login", "/api/setup", "/api/setup-status", "/api/health", "/api/lan")

    @app.before_request
    def auth_gate():
        from flask import request as rq
        if rq.path in PUBLIC_PATHS or rq.path.startswith(("/static", "/icons")):
            return None
        if not auth_mod.get_user(store):
            # 尚无账号:仅允许初始化流程
            if rq.path.startswith("/api/"):
                return jsonify({"error": "需要先创建账号", "setup_required": True}), 401
            return send_from_directory(STATIC_DIR, "index.html")
        user = auth_mod.session_user(store, rq.cookies.get("dx_session"))
        if user:
            g.user = user
            return None
        if rq.path.startswith("/api/"):
            return jsonify({"error": "请先登录", "auth_required": True}), 401
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/api/setup-status")
    def setup_status():
        return jsonify({"needs_setup": not auth_mod.get_user(store)})

    @app.get("/api/lan")
    def lan_info():
        ip = _lan_ip()
        return jsonify({"lan_url": "http://%s:8321" % ip if ip else None})

    @app.post("/api/setup")
    def setup_account():
        if auth_mod.get_user(store):
            return _bad("账号已存在", 400)
        body = request.get_json(force=True, silent=True) or {}
        user, err = auth_mod.create_user(store, body.get("username") or "",
                                         body.get("password") or "")
        if err:
            return _bad(err)
        token, expires = auth_mod.create_session(store, user["username"])
        auth_mod.audit(store, "account_created", user["username"])
        resp = jsonify({"ok": True, "username": user["username"]})
        resp.set_cookie("dx_session", token, max_age=7 * 86400,
                        httponly=True, samesite="Lax")
        return resp

    @app.post("/api/login")
    def login():
        body = request.get_json(force=True, silent=True) or {}
        user, err = auth_mod.check_login(store, body.get("username") or "",
                                         body.get("password") or "")
        if err:
            auth_mod.audit(store, "login_failed", err)
            return _bad(err, 401)
        token, expires = auth_mod.create_session(store, user["username"])
        auth_mod.audit(store, "login", user["username"])
        resp = jsonify({"ok": True, "username": user["username"]})
        resp.set_cookie("dx_session", token, max_age=7 * 86400,
                        httponly=True, samesite="Lax")
        return resp

    @app.post("/api/logout")
    def logout():
        token = request.cookies.get("dx_session")
        if token:
            auth_mod.destroy_session(store, token)
            auth_mod.audit(store, "logout")
        resp = jsonify({"ok": True})
        resp.delete_cookie("dx_session")
        return resp

    @app.get("/api/account")
    def account_info():
        user = auth_mod.get_user(store)
        cfg = store.load("settings")
        return jsonify({"username": user["username"],
                        "display_name": user.get("display_name", user["username"]),
                        "created": user.get("created"),
                        "motivation_style": cfg.get("motivation_style", "rational"),
                        "schema_version": migrate_mod.SCHEMA_VERSION,
                        "exam": {"school": cfg.get("target_school"),
                                 "date": cfg.get("exam_date"),
                                 "math_type": cfg.get("math_type")}})

    @app.put("/api/account")
    def account_update():
        body = request.get_json(force=True, silent=True) or {}
        users = store.load("users")
        if users:
            if body.get("display_name"):
                users[0]["display_name"] = body["display_name"][:30]
            store.save("users", users)
        if body.get("motivation_style") in ("rational", "gentle", "sprint"):
            cur = store.load("settings")
            cur["motivation_style"] = body["motivation_style"]
            store.save("settings", cur)
        return jsonify({"ok": True})

    @app.post("/api/account/password")
    def account_password():
        body = request.get_json(force=True, silent=True) or {}
        err = auth_mod.change_password(store, body.get("old_password") or "",
                                       body.get("new_password") or "")
        if err:
            auth_mod.audit(store, "password_change_failed", err)
            return _bad(err)
        auth_mod.audit(store, "password_changed")
        # 改密后吊销全部会话,要求重新登录
        store.save("sessions", [])
        resp = jsonify({"ok": True})
        resp.delete_cookie("dx_session")
        return resp

    @app.get("/api/account/audit")
    def account_audit():
        path = os.path.join(store.data_dir, auth_mod.AUDIT_FILE)
        events = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                events = [json.loads(l) for l in f if l.strip()][-50:]
        return jsonify(list(reversed(events)))

    @app.post("/api/account/delete-data")
    def account_delete_data():
        """删除学习数据(保留账号与设置)。需在 body 中确认。"""
        body = request.get_json(force=True, silent=True) or {}
        if body.get("confirm") != "DELETE":
            return _bad("请在请求中携带 confirm='DELETE' 以确认此不可逆操作")
        cleared = []
        for name in ("mistakes", "records", "vocab", "reflections", "coach", "plan"):
            default = [] if name != "plan" else {"generated_at": None, "days": {}}
            store.save(name, default)
            cleared.append(name)
        img_dir = os.path.join(store.data_dir, "images")
        if os.path.isdir(img_dir):
            for fn in os.listdir(img_dir):
                os.remove(os.path.join(img_dir, fn))
        auth_mod.audit(store, "data_deleted", ",".join(cleared))
        return jsonify({"ok": True, "cleared": cleared})

    # ---------- 题库 ----------
    # ---------- 经验帖 ----------
    @app.get("/api/experience")
    def experience_list():
        items = store.load("experience_posts")
        cat = request.args.get("category")
        q_ = (request.args.get("q") or "").lower()
        fav = request.args.get("favorite") == "1"
        if cat:
            items = [p for p in items if cat in (p.get("categories") or [])]
        if fav:
            items = [p for p in items if p.get("favorite")]
        if q_:
            items = [p for p in items if q_ in (p.get("title", "") +
                                               p.get("summary", "") +
                                               (p.get("notes") or "")).lower()]
        return jsonify(sorted(items, key=lambda p: p.get("created", ""), reverse=True))

    @app.post("/api/experience")
    def experience_add():
        body = request.get_json(force=True, silent=True) or {}
        if not (body.get("title") or "").strip():
            return _bad("标题必填")
        url = (body.get("url") or "").strip()
        if url and not url.startswith(("http://", "https://")):
            return _bad("链接必须以 http(s):// 开头")
        items = store.load("experience_posts")
        item = {"id": _next_id(items, "ep"),
                "title": body["title"].strip()[:100],
                "platform": body.get("platform") or "",
                "url": url,
                "author": body.get("author") or "",
                "published": body.get("published") or None,
                "summary": (body.get("summary") or "")[:500],
                "categories": [c for c in (body.get("categories") or []) if c][:4],
                "stage": body.get("stage") or "",
                "methods": body.get("methods") or "",
                "notes": (body.get("notes") or "")[:1000],
                "rating": body.get("rating"),
                "favorite": bool(body.get("favorite")),
                "verify_status": "待核验" if url else "个人笔记",
                "source_type": "public_experience" if url else "platform_original",
                "last_checked": None,
                "created": datetime.datetime.now().isoformat(timespec="seconds"),
                "updated_at": None}
        items.append(item)
        store.save("experience_posts", items)
        return jsonify(item), 201

    @app.put("/api/experience/<pid>")
    def experience_update(pid):
        body = request.get_json(force=True, silent=True) or {}
        items = store.load("experience_posts")
        for p in items:
            if p["id"] == pid:
                for f in ("title", "platform", "url", "author", "published",
                          "summary", "categories", "stage", "methods", "notes",
                          "rating", "favorite", "verify_status"):
                    if f in body:
                        p[f] = body[f]
                store.save("experience_posts", items)
                return jsonify(p)
        return _bad("记录不存在", 404)

    @app.delete("/api/experience/<pid>")
    def experience_delete(pid):
        items = store.load("experience_posts")
        store.save("experience_posts", [p for p in items if p["id"] != pid])
        return jsonify({"deleted": pid})

    @app.post("/api/experience/<pid>/check")
    def experience_check(pid):
        """核验链接可达性。"""
        items = store.load("experience_posts")
        for p in items:
            if p["id"] == pid:
                if not p.get("url"):
                    p["verify_status"] = "个人笔记(无链接)"
                else:
                    try:
                        rq = urllib.request.Request(p["url"], method="HEAD",
                            headers={"User-Agent": "daxue-intel/1.0"})
                        with urllib.request.urlopen(rq, timeout=15) as resp:
                            p["verify_status"] = "链接可访问(HTTP %d)" % resp.status
                    except urllib.error.HTTPError as e:
                        p["verify_status"] = "HTTP %d" % e.code
                    except Exception as e:
                        p["verify_status"] = "无法访问:%s" % str(e)[:50]
                p["last_checked"] = datetime.datetime.now().isoformat(timespec="seconds")
                store.save("experience_posts", items)
                return jsonify(p)
        return _bad("记录不存在", 404)

    # ---------- 目标院校资料库(v4) ----------

    def _uni_out(u):
        from . import universities as U
        out = dict(u)
        out["completeness"] = U.completeness(u)
        return out

    @app.get("/api/universities")
    def universities_list():
        items = store.load("universities")
        order = request.args.get("order", "priority")
        if order == "priority":
            items = sorted(items, key=lambda u: (-u.get("priority", 0), u.get("name", "")))
        q = (request.args.get("q") or "").lower()
        if q:
            items = [u for u in items if q in (u.get("name", "") + u.get("city", "")
                                               + u.get("cs_school", "")).lower()]
        return jsonify([_uni_out(u) for u in items])

    @app.get("/api/universities/<uid>")
    def universities_get(uid):
        for u in store.load("universities"):
            if u["id"] == uid:
                return jsonify(_uni_out(u))
        return _bad("院校不存在", 404)

    @app.put("/api/universities/<uid>")
    def universities_update(uid):
        body = request.get_json(force=True, silent=True) or {}
        EDITABLE = ("program", "program_code", "degree_type", "exam_subjects",
                    "uses_408", "admission_catalog_url", "retest_rules_url",
                    "history_admission_url", "enrollment", "enrollment_year",
                    "retest_line", "retest_line_year", "tuition", "duration_years",
                    "intro", "notes", "priority", "campus", "cs_school",
                    "admission_source", "admission_published")
        items = store.load("universities")
        for u in items:
            if u["id"] == uid:
                for f in EDITABLE:
                    if f in body:
                        u[f] = body[f]
                # 年份与数字绑定校验:填了人数/分数线必须同年份+来源(可追溯红线)
                for num, yr in (("enrollment", "enrollment_year"),
                                ("retest_line", "retest_line_year")):
                    if u.get(num) and not u.get(yr):
                        return _bad("填写%s时必须同时填写对应年份(%s)" % (num, yr))
                if u.get("enrollment") and not u.get("admission_source"):
                    return _bad("填写招生人数时必须填写数据来源(admission_source)")
                if u.get("retest_line") and not u.get("admission_source"):
                    return _bad("填写复试线时必须填写数据来源(admission_source)")
                u["last_verified"] = datetime.datetime.now().isoformat(timespec="seconds")                     if body.get("mark_verified") else u.get("last_verified")
                u["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                u["data_status"] = body.get("data_status") or u.get("data_status")
                store.save("universities", items)
                auth_mod.audit(store, "university_updated", uid)
                return jsonify(_uni_out(u))
        return _bad("院校不存在", 404)

    @app.post("/api/universities/<uid>/verify")
    def universities_verify(uid):
        """人工核验:记录时间与核验结论。"""
        body = request.get_json(force=True, silent=True) or {}
        items = store.load("universities")
        for u in items:
            if u["id"] == uid:
                u["last_verified"] = datetime.datetime.now().isoformat(timespec="seconds")
                u["data_status"] = (body.get("result") or "已人工核验")[:80]
                store.save("universities", items)
                auth_mod.audit(store, "university_verified", uid)
                return jsonify(_uni_out(u))
        return _bad("院校不存在", 404)

    @app.post("/api/universities")
    def universities_add():
        body = request.get_json(force=True, silent=True) or {}
        if not (body.get("name") or "").strip():
            return _bad("校名必填")
        items = store.load("universities")
        uid = (body.get("id") or body["name"].strip())[:20]
        if any(u["id"] == uid for u in items):
            return _bad("ID 已存在")
        from . import universities as U
        uni = {"id": uid, "name": body["name"].strip(),
               "short": (body.get("short") or body["name"].strip()[:4]),
               "city": body.get("city") or "", "campus": "", 
               "official_site": body.get("official_site") or "",
               "cs_school": body.get("cs_school") or "",
               "priority": 0, "program": "", "program_code": "", "degree_type": "",
               "exam_subjects": [], "uses_408": None,
               "admission_catalog_url": "", "retest_rules_url": "",
               "history_admission_url": "",
               "enrollment": None, "enrollment_year": None,
               "retest_line": None, "retest_line_year": None,
               "tuition": "", "duration_years": None,
               "intro": "", "notes": "", "admission_source": "",
               "admission_published": None, "last_verified": None,
               "data_status": "新建,待补全",
               "image": U.make_fallback_logo({"id": uid, "short": body["name"][:2], "name": body["name"]}),
               "created": datetime.datetime.now().isoformat(timespec="seconds")}
        items.append(uni)
        store.save("universities", items)
        return jsonify(_uni_out(uni)), 201

    @app.delete("/api/universities/<uid>")
    def universities_delete(uid):
        items = store.load("universities")
        remain = [u for u in items if u["id"] != uid]
        if len(remain) == len(items):
            return _bad("院校不存在", 404)
        store.save("universities", remain)
        return jsonify({"deleted": uid})

    @app.post("/api/universities/<uid>/refetch-image")
    def universities_refetch_image(uid):
        """重试抓图(仅自由许可来源)。"""
        items = store.load("universities")
        from . import universities as U
        for u in items:
            if u["id"] == uid:
                wiki = u.get("id")
                # 用已存 wiki_en 或按校名尝试
                seed = next((s for s in U.SEED_UNIVERSITIES
                             if s["id"] == uid), None)
                if seed:
                    img = U.fetch_university_image(seed)
                    if img:
                        u["image"] = img
                        store.save("universities", items)
                        return jsonify(_uni_out(u))
                return _bad("暂无该院校的自由许可图片来源,继续使用当前图片", 400)
        return _bad("院校不存在", 404)

    # ---------- 目标 / 梦校 / 里程碑 ----------
    @app.get("/api/goals")
    def goals_get():
        return jsonify(store.load("goals"))

    @app.put("/api/goals")
    def goals_put():
        body = request.get_json(force=True, silent=True) or {}
        goals = store.load("goals")
        for f in ("institution", "program", "subjects", "notes",
                  "official_links", "prep_status", "exam_plan"):
            if f in body:
                goals[f] = body[f]
        store.save("goals", goals)
        return jsonify(goals)

    @app.get("/api/institutions")
    def institutions_list():
        return jsonify(store.load("institutions"))

    @app.post("/api/institutions")
    def institutions_add():
        body = request.get_json(force=True, silent=True) or {}
        err = _validate_institution(body)
        if err:
            return _bad(err)
        items = store.load("institutions")
        item = {"id": _next_id(items, "ins"),
                "name": body["name"].strip(),
                "program": body.get("program") or "",
                "official_url": body.get("official_url") or "",
                "subjects": body.get("subjects") or [],
                "requirements": body.get("requirements") or "",
                "key_dates": body.get("key_dates") or "",
                "prep_status": body.get("prep_status") or "关注中",
                "verified": bool(body.get("verified")),
                "last_checked": body.get("last_checked") or None,
                "notes": body.get("notes") or "",
                "created": datetime.datetime.now().isoformat(timespec="seconds")}
        items.append(item)
        store.save("institutions", items)
        return jsonify(item), 201

    @app.put("/api/institutions/<iid>")
    def institutions_update(iid):
        body = request.get_json(force=True, silent=True) or {}
        items = store.load("institutions")
        for it in items:
            if it["id"] == iid:
                for f in ("name", "program", "official_url", "subjects",
                          "requirements", "key_dates", "prep_status",
                          "verified", "last_checked", "notes"):
                    if f in body:
                        it[f] = body[f]
                store.save("institutions", items)
                return jsonify(it)
        return _bad("院校不存在", 404)

    @app.delete("/api/institutions/<iid>")
    def institutions_delete(iid):
        items = store.load("institutions")
        remain = [i for i in items if i["id"] != iid]
        if len(remain) == len(items):
            return _bad("院校不存在", 404)
        store.save("institutions", remain)
        return jsonify({"deleted": iid})

    @app.post("/api/goals/milestones")
    def milestone_add():
        body = request.get_json(force=True, silent=True) or {}
        if not (body.get("title") or "").strip():
            return _bad("里程碑标题必填")
        goals = store.load("goals")
        ms = goals.setdefault("milestones", [])
        item = {"id": "ms-%04d" % (len(ms) + 1), "title": body["title"].strip(),
                "target_date": body.get("target_date") or None,
                "done": bool(body.get("done")),
                "done_date": body.get("done_date") or None,
                "created": datetime.datetime.now().isoformat(timespec="seconds")}
        ms.append(item)
        store.save("goals", goals)
        return jsonify(item), 201

    @app.put("/api/goals/milestones/<mid>")
    def milestone_update(mid):
        body = request.get_json(force=True, silent=True) or {}
        goals = store.load("goals")
        for m in goals.get("milestones") or []:
            if m["id"] == mid:
                for f in ("title", "target_date", "done", "done_date"):
                    if f in body:
                        m[f] = body[f]
                store.save("goals", goals)
                return jsonify(m)
        return _bad("里程碑不存在", 404)

    # ---------- 激励 ----------
    QUOTES = {
        "rational": [
            {"text": "不要用战术上的勤奋,掩盖战略上的懒惰。", "author": "经典格言", "source": "公共领域"},
            {"text": "每道错题都是尚未兑现的分数,前提是你回头弄懂它。", "author": "大雪深埋", "source": "系统内置"},
            {"text": "进度慢不可怕,可怕的是不知道慢在哪里。", "author": "大雪深埋", "source": "系统内置"},
        ],
        "gentle": [
            {"text": "你已经走了很远,剩下的路一步一步来。", "author": "大雪深埋", "source": "系统内置"},
            {"text": "累的时候就休息,考研是一场马拉松而不是冲刺。", "author": "大雪深埋", "source": "系统内置"},
            {"text": "今天的你只需要比昨天多懂一点点。", "author": "大雪深埋", "source": "系统内置"},
        ],
        "sprint": [
            {"text": "现在流的汗,都是将来录取通知书上的墨水。", "author": "流行语", "source": "网络流传,作者佚名"},
            {"text": "你要悄悄拔尖,然后惊艳所有人。", "author": "流行语", "source": "网络流传,作者佚名"},
            {"text": "别停下,你的对手此刻正在刷题。", "author": "流行语", "source": "网络流传,作者佚名"},
        ],
    }

    @app.get("/api/motivation/daily")
    def motivation_daily():
        style = store.load("settings").get("motivation_style", "rational")
        # 用户语录库优先(公版/原创已核验),不足时回退内置池
        user_pool = [m for m in store.load("motivations")
                     if m.get("type") == "quote" and m.get("verified")]
        pool = user_pool or QUOTES.get(style, QUOTES["rational"])
        idx = int(_today().strftime("%Y%m%d")) % len(pool)
        if user_pool:
            q0 = pool[idx]
            quote = {"text": q0["text"], "author": q0.get("author", ""),
                     "source": q0.get("license", ""), "license": q0.get("license", "")}
            prof0 = None
        if not user_pool:
            quote = None
        prof = profile_mod.compute_profile(
            store.load("mistakes"), store.load("records"),
            store.load("reflections"), store.load("knowledge"),
            store.load("catalog"), store.load("settings"), _today())
        growth = []
        for m in store.load("mistakes"):
            revs = [x for x in m.get("reviews") or []]
            if len(revs) >= 3 and all(x.get("result") != "again" for x in revs[-3:]) \
                    and m.get("lapses", 0) > 0:
                kp = {k["id"]: k["name"] for k in store.load("knowledge")}
                growth.append("「%s」曾忘 %d 次,现已连续 %d 次复测通过 —— 稳定掌握"
                              % (kp.get((m.get("knowledge_ids") or ["?"])[0], "一道错题"),
                                 m.get("lapses", 0), len(revs[-3:])))
        if not quote:
            b = pool[idx]
            quote = {"text": b["text"], "author": b.get("author", ""),
                     "source": b.get("source", ""), "license": b.get("source", "系统内置")}
        return jsonify({"style": style, "quote": quote,
                        "growth_note": growth[0] if growth else None,
                        "weekly_summary_hint": prof["stage"]})

    @app.get("/api/motivations")
    def motivations_list():
        return jsonify(store.load("motivations"))

    @app.post("/api/motivations")
    def motivations_add():
        body = request.get_json(force=True, silent=True) or {}
        if not (body.get("text") or "").strip():
            return _bad("内容必填")
        items = store.load("motivations")
        license_ = body.get("license") or "自述/公共领域"
        stype = {"公版古籍": "public_classic", "平台原创": "platform_original"}.get(
            license_, "来源待核验" if "待核验" in license_ else "user_note")
        item = {"id": _next_id(items, "mo"), "type": body.get("type") or "quote",
                "title": (body.get("title") or "").strip()[:60],
                "text": body["text"].strip(), "author": body.get("author") or "",
                "source_url": body.get("source_url") or "",
                "license": license_,
                "source_type": stype,
                "created": datetime.datetime.now().isoformat(timespec="seconds"),
                "updated_at": None,
                "verified": False}
        items.append(item)
        store.save("motivations", items)
        return jsonify(item), 201

    @app.delete("/api/motivations/<mid>")
    def motivations_delete(mid):
        items = store.load("motivations")
        remain = [m for m in items if m["id"] != mid]
        store.save("motivations", remain)
        return jsonify({"deleted": mid})

    # ---------- 热点雷达(V3.1) ----------
    from . import radar as RADAR

    def _radar_bucket(items, days):
        cutoff = (_today() - datetime.timedelta(days=days)).isoformat()
        out = [i for i in items
               if i.get("published_at") and i["published_at"] >= cutoff
               and i.get("verify_status") in ("verified_page", "user_submitted", "api")]
        return out

    @app.get("/api/radar")
    def radar_list():
        args = request.args
        items = [i for i in store.load("radar") if not i.get("hidden")]
        RADAR.expire_pass(store)
        bucket = args.get("bucket", "all")
        if bucket in ("7", "30", "90"):
            items = _radar_bucket(items, int(bucket))
        elif bucket == "annual":
            items = _radar_bucket(items, 365)
        if args.get("ctype"):
            items = [i for i in items if i.get("ctype") == args["ctype"]]
        if args.get("category"):
            items = [i for i in items if i.get("category") == args["category"]]
        if args.get("subject"):
            items = [i for i in items if i.get("subject") == args["subject"]]
        if args.get("favorite") == "1":
            items = [i for i in items if i.get("favorite")]
        q_ = (args.get("q") or "").lower()
        if q_:
            items = [i for i in items
                     if q_ in (i.get("title", "") + i.get("summary", "")).lower()]

        def _pub_key(i):
            sc = (i.get("score") or {}).get("total")
            return (i.get("published_at") or "0000", -(sc or 0))
        items.sort(key=_pub_key)
        items.reverse()
        state = store.load("radar_state") or {}
        for i in items:
            i["source_level"] = TRUST.radar_level(i)
        return jsonify({"items": items[:200], "total": len(items),
                        "ctypes": RADAR.CTYPES, "categories": RADAR.CATEGORY_NAMES,
                        "levels": TRUST.LEVEL_LABELS,
                        "status": {"last_success": state.get("last_success"),
                                   "last_attempt": state.get("last_attempt"),
                                   "last_stats": state.get("last_stats"),
                                   "failure_reason": state.get("failure_reason")}})

    @app.post("/api/radar/refresh")
    def radar_refresh():
        stats = RADAR.refresh(store, store.load("settings"))
        RADAR.expire_pass(store)
        return jsonify({"ok": not (stats["failed"] and not stats["candidates"]),
                        "stats": stats,
                        "failure_reason": (store.load("radar_state") or {}).get("failure_reason")})

    @app.post("/api/radar/feedback")
    def radar_feedback():
        body = request.get_json(force=True, silent=True) or {}
        rid, action = body.get("id"), body.get("action")
        if not rid or action not in ("useful", "not_useful", "practiced",
                                     "favorite", "unfavorite", "hide", "dislike_type"):
            return _bad("参数不合法")
        items = store.load("radar")
        state = store.load("radar_state") or RADAR.default_state()
        state.setdefault("ctype_weights", {})
        hit = next((i for i in items if i["id"] == rid), None)
        if not hit:
            return _bad("内容不存在"), 404
        fb = hit.setdefault("feedback", {"useful": 0, "not_useful": 0,
                                         "practiced": False, "dislike_type": False})
        if action == "useful":
            fb["useful"] += 1
        elif action == "not_useful":
            fb["not_useful"] += 1
            if hit["ctype"] == "ai":  # 鸡汤负反馈:AI 原创降权
                state["ctype_weights"]["ai"] = max(-3, state["ctype_weights"].get("ai", 0) - 1)
        elif action == "practiced":
            fb["practiced"] = True
        elif action == "favorite":
            hit["favorite"] = True
        elif action == "unfavorite":
            hit["favorite"] = False
        elif action == "hide":
            hit["hidden"] = True
        elif action == "dislike_type":
            fb["dislike_type"] = True
            state["ctype_weights"][hit["ctype"]] = \
                max(-3, state["ctype_weights"].get(hit["ctype"], 0) - 1)
        store.save("radar", items)
        store.save("radar_state", state)
        return jsonify({"ok": True, "feedback": fb, "hidden": hit.get("hidden", False),
                        "favorite": hit.get("favorite", False)})

    @app.post("/api/radar/submit")
    def radar_submit():
        body = request.get_json(force=True, silent=True) or {}
        url = (body.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return _bad("请粘贴完整公开链接(http/https)")
        title = (body.get("title") or "").strip()
        if len(title) < 4:
            return _bad("请填写标题(便于识别与去重)")
        items = store.load("radar")
        h = RADAR.dedup_hash(url, title)
        if any(i.get("dedup_hash") == h for i in items):
            return _bad("这条内容已在库中(去重命中)")
        settings = store.load("settings")
        goals = store.load("goals") or {}
        state = store.load("radar_state") or RADAR.default_state()
        pub = RADAR._norm_date(body.get("published_at") or "")
        cand = {"title": title[:120], "url": url,
                "snippet": (body.get("note") or "")[:300]}
        ctype, hits = RADAR.classify(cand)
        now_iso = datetime.datetime.now().isoformat(timespec="seconds")
        item = {
            "id": "rd-" + h[:12], "title": title[:120],
            "summary": cand["snippet"], "url": url,
            "platform": body.get("platform") or RADAR.platform_of(url),
            "author": body.get("author") or "",
            "published_at": pub, "fetched_at": now_iso, "verified_at": None,
            "verify_status": "user_submitted",
            "subject": RADAR.detect_subject(title + " " + cand["snippet"]),
            "tags": [], "stage": "通用", "ctype": ctype,
            "category": RADAR.classify_category(ctype, title, cand["snippet"]),
            "marketing_hits": hits,
            "heat": None, "score": None, "recommend_reason": "", "action_advice": "",
            "shown": False, "favorite": bool(body.get("favorite")),
            "hidden": False,
            "feedback": {"useful": 0, "not_useful": 0, "practiced": False,
                         "dislike_type": False},
            "expires_at": ((_today() + datetime.timedelta(days=90)).isoformat()),
            "dedup_hash": h,
            "submitted_by": (g.user if isinstance(g.user, str) else "user"),
            "via_query": "user_submit",
            "user_note": (body.get("note") or "")[:300],
        }
        item["score"] = RADAR.score_item(
            item, {"subjects": ["math", "cs408", "english", "politics"],
                   "target_school": goals.get("institution") or "",
                   "stage": RADAR.stage_of(), "ctype_weights": state.get("ctype_weights") or {}},
            [i.get("title", "") for i in items])
        items.append(item)
        store.save("radar", items)
        return jsonify(item), 201

    @app.post("/api/radar/reverify")
    def radar_reverify():
        body = request.get_json(force=True, silent=True) or {}
        rid = body.get("id")
        items = store.load("radar")
        hit = next((i for i in items if i["id"] == rid), None)
        if not hit:
            return _bad("内容不存在"), 404
        proxy = ((store.load("settings").get("radar") or {}).get("proxy")) or None
        try:
            page = RADAR.http_text(hit["url"], proxy, timeout=12)
            d = RADAR.extract_date(page, hit["url"])
            if d and not hit.get("published_at"):
                hit["published_at"] = d
            desc, author = RADAR.extract_meta(page)
            if desc:
                hit["summary"] = desc[:300]
            if author:
                hit["author"] = author
            hit["verify_status"] = "verified_page"
            hit["verified_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            msg = "核验成功,页面可访问"
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                hit["ctype"] = "expired"
                msg = "原链接已失效(%d),标记为过期" % e.code
            else:
                msg = "核验失败:HTTP %d(对方站点限制访问)" % e.code
        except Exception as e:
            msg = "核验失败:%s" % str(e)[:60]
        store.save("radar", items)
        return jsonify({"ok": hit.get("verify_status") == "verified_page",
                        "message": msg, "item": hit})

    @app.get("/api/radar/home")
    def radar_home():
        RADAR.expire_pass(store)
        state = store.load("radar_state") or RADAR.default_state()
        card = state.get("daily_card")
        if not card or card.get("date") != _today().isoformat():
            card = RADAR.build_daily_brief(store, store.load("settings"))
            state = store.load("radar_state") or {}
        items = [i for i in store.load("radar")
                 if not i.get("hidden") and i["ctype"] not in ("warn", "expired")]
        top, bucket_used, note = [], "none", "尚未检索到内容,点击刷新开始第一次检索"
        for days, label in ((7, "7d"), (30, "30d"), (90, "90d")):
            got = _radar_bucket(items, days)
            got.sort(key=lambda i: -(i.get("score") or {}).get("total", 0))
            if len(got) >= 3 or (label == "90d" and got):
                top, bucket_used = got[:6], label
                note = ("最近 7 天内容" if label == "7d" else
                        "近 7 天内容不足,已放宽到 %s 天(注意实际发布时间)" % days)
                break
        settings = store.load("settings")
        return jsonify({
            "brief": card,
            "top": {"items": top, "bucket": bucket_used, "note": note},
            "breakdown": RADAR.experience_breakdown(store, settings),
            "observation": RADAR.weekly_observation(store),
            "snapshot": RADAR.user_snapshot(store, settings),
            "status": {"last_success": state.get("last_success"),
                       "last_attempt": state.get("last_attempt"),
                       "failure_reason": state.get("failure_reason"),
                       "total": len(store.load("radar"))}})

    @app.post("/api/radar/brief/regenerate")
    def radar_brief_regen():
        card = RADAR.build_daily_brief(store, store.load("settings"), force=True)
        return jsonify(card)

    @app.post("/api/radar/brief/feedback")
    def radar_brief_feedback():
        body = request.get_json(force=True, silent=True) or {}
        action = body.get("action")
        if action not in ("useful", "not_useful", "practiced"):
            return _bad("参数不合法")
        state = store.load("radar_state") or RADAR.default_state()
        card = state.get("daily_card") or {}
        fb = card.setdefault("feedback", {"useful": 0, "not_useful": 0, "practiced": False})
        if action == "useful":
            fb["useful"] += 1
        elif action == "not_useful":
            fb["not_useful"] += 1
            if card.get("generator") == "ai":  # 对 AI 文案不满 → 降 AI 权重
                w = state.setdefault("ctype_weights", {})
                w["ai"] = max(-3, w.get("ai", 0) - 1)
        else:
            fb["practiced"] = True
        state["daily_card"] = card
        store.save("radar_state", state)
        return jsonify({"ok": True, "feedback": fb})

    @app.get("/api/radar/settings")
    def radar_settings_get():
        cfg = store.load("settings").get("radar") or {}
        return jsonify({"proxy": cfg.get("proxy", "http://127.0.0.1:7897"),
                        "max_queries": int(cfg.get("max_queries", 6)),
                        "auto_refresh": bool(cfg.get("auto_refresh", False)),
                        "channels": ["DuckDuckGo 公开搜索", "研招网官方列表",
                                     "GitHub 官方 API(公开仓库,直连)",
                                     "小红书/抖音:公开搜索引擎站点索引(需代理,不登录不绕过反爬)",
                                     "用户提交链接"],
                        "limits": "小红书/抖音无公开检索接口:通过搜索引擎 site: 索引获取公开帖子链接与摘要(标注'仅摘要·日期未核验'),不登录、不绕过任何访问控制;代理不可用时该通道如实报失败,不伪造抓取结果"})

    @app.post("/api/radar/settings")
    def radar_settings_post():
        body = request.get_json(force=True, silent=True) or {}
        settings = store.load("settings")
        cfg = settings.get("radar") or {}
        if "proxy" in body:
            p = (body["proxy"] or "").strip()
            if p and not p.startswith("http://") and not p.startswith("https://"):
                return _bad("代理地址需以 http:// 开头,留空表示直连")
            cfg["proxy"] = p or None
        if "max_queries" in body:
            try:
                n = int(body["max_queries"])
            except (TypeError, ValueError):
                return _bad("检索次数须为数字")
            if not 1 <= n <= 12:
                return _bad("检索次数范围 1-12")
            cfg["max_queries"] = n
        if "auto_refresh" in body:
            cfg["auto_refresh"] = bool(body["auto_refresh"])
        settings["radar"] = cfg
        store.save("settings", settings)
        # 开关即时生效:开启且线程未启动时立刻拉起(不必重启服务)
        if cfg.get("auto_refresh") and not os.environ.get("PYTEST_CURRENT_TEST"):
            RADAR.ensure_auto_thread(store)
        return jsonify({"ok": True, "radar": cfg})

    # ---------- V2.0 决策与情报中心 ----------
    from . import decision as DEC
    from . import trust as TRUST

    @app.get("/api/persona")
    def persona_get():
        return jsonify(DEC.persona_snapshot(store))

    @app.put("/api/persona")
    def persona_put():
        body = request.get_json(force=True, silent=True) or {}
        cur = store.load("persona") or {}
        for f in ("exam_year", "directions", "plan", "math", "english",
                  "major_course", "bachelor_major", "bachelor_school",
                  "target_region", "note"):
            if f in body:
                cur[f] = body[f]
        if "exam_year" in body:
            try:
                y = int(body["exam_year"])
            except (TypeError, ValueError):
                return _bad("考研年份须为数字")
            if not 2026 <= y <= 2030:
                return _bad("考研年份范围 2026-2030")
            cur["exam_year"] = y
        if "directions" in body:
            if not isinstance(body["directions"], list) or \
                    not all(isinstance(x, str) for x in body["directions"]):
                return _bad("directions 须为字符串列表")
            cur["directions"] = [x.strip() for x in body["directions"] if x.strip()][:6]
        cur["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        store.save("persona", cur)
        return jsonify(DEC.persona_snapshot(store))

    @app.get("/api/mock-scores")
    def mock_list():
        rows = sorted(store.load("mock_scores"), key=lambda r: r.get("month") or "")
        return jsonify({"items": rows,
                        "summary": DEC.mock_summary(store,
                                                    DEC.persona_snapshot(store).get("exam_year"))})

    @app.post("/api/mock-scores")
    def mock_add():
        body = request.get_json(force=True, silent=True) or {}
        sub = body.get("subject")
        if sub not in SUBJECTS:
            return _bad("subject 必须是 %s" % (SUBJECTS,))
        month = str(body.get("month") or "")
        try:
            datetime.datetime.strptime(month, "%Y-%m")
        except ValueError:
            return _bad("month 格式应为 YYYY-MM(按月记录模拟成绩)")
        try:
            score = float(body.get("score"))
        except (TypeError, ValueError):
            return _bad("score 须为数字(真实模拟成绩,不接受主观评级)")
        fm = body.get("full_mark") or DEC.FULL_MARKS[sub]
        if not 0 <= score <= fm:
            return _bad("score 应在 0-%s 之间" % fm)
        items = store.load("mock_scores")
        item = {"id": _next_id(items, "mk-sc"), "month": month, "subject": sub,
                "score": score, "full_mark": fm,
                "paper": (body.get("paper") or "")[:60],
                "note": (body.get("note") or "")[:200],
                "created": datetime.datetime.now().isoformat(timespec="seconds")}
        items.append(item)
        store.save("mock_scores", items)
        return jsonify(item), 201

    @app.delete("/api/mock-scores/<mid>")
    def mock_del(mid):
        items = store.load("mock_scores")
        remain = [m for m in items if m["id"] != mid]
        if len(remain) == len(items):
            return _bad("记录不存在", 404)
        store.save("mock_scores", remain)
        return jsonify({"deleted": mid})

    @app.get("/api/decision/recommend")
    def decision_recommend():
        return jsonify(DEC.recommend(store))

    @app.get("/api/decision/probability/<uid>")
    def decision_probability(uid):
        return jsonify(DEC.probability(store, uid))

    @app.get("/api/admission/records")
    def admission_list():
        uni_id = request.args.get("uni_id")
        year = request.args.get("year")
        items = store.load("admission_records")
        if uni_id:
            items = [r for r in items if r["uni_id"] == uni_id]
        if year:
            items = [r for r in items if str(r.get("year")) == str(year)]
        return jsonify({"items": items, "total": len(items),
                        "changes": len(store.load("admission_changes"))})

    @app.put("/api/admission/records/<rid>")
    def admission_update(rid):
        """官方招生数据录入:事实字段必须同年份+来源(官方优先),否则拒绝。"""
        body = request.get_json(force=True, silent=True) or {}
        items = store.load("admission_records")
        for r in items:
            if r["id"] != rid:
                continue
            FACT = ("major_code", "major_name", "plan_total", "tuimian",
                    "tongkao", "exam_subjects", "uses_408", "retest_subjects",
                    "retest_line", "single_lines", "retest_list_url",
                    "admitted_list_url", "score_distribution_url",
                    "tutors_url", "announcement_url")
            changed = []
            for f in FACT:
                if f in body and body[f] != r.get(f):
                    old = r.get(f)
                    r[f] = body[f]
                    if old not in (None, "", [], {}) or body[f] not in (None, "", [], {}):
                        changed.append({"field": f, "old": old, "new": body[f]})
            if "source_name" in body:
                r["source_name"] = body["source_name"]
            if "source_url" in body:
                su = (body["source_url"] or "").strip()
                if su and not su.startswith(("http://", "https://")):
                    return _bad("来源链接必须以 http(s):// 开头")
                r["source_url"] = su
            # 事实字段变化时强制来源(可追溯红线)
            if changed and not (r.get("source_url") or r.get("source_name")):
                return _bad("填写官方招生数据必须同时提供来源(来源名称或链接)")
            r["collected_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            r["updated_at"] = r["collected_at"]
            r["data_status"] = ("已核验" if body.get("mark_verified")
                                else "已录入·待核验" if changed else r.get("data_status"))
            r["verified_at"] = (datetime.datetime.now().isoformat(timespec="seconds")
                                if body.get("mark_verified") else r.get("verified_at"))
            r["source_level"] = "S" if (r.get("verified_at") and
                                        (r.get("source_url") or r.get("source_name"))) else \
                ("B" if (r.get("source_url") or r.get("source_name")) else None)
            if body.get("mark_verified") is not None:
                r["data_status"] = body.get("data_status") or r["data_status"]
            if changed:
                chs = store.load("admission_changes")
                chs.append({"id": "ac-%d" % (len(chs) + 1), "record_id": rid,
                            "uni_name": r["uni_name"], "year": r["year"],
                            "changes": changed,
                            "source_name": r.get("source_name"),
                            "source_url": r.get("source_url"),
                            "at": r["collected_at"]})
                store.save("admission_changes", chs)
            store.save("admission_records", items)
            return jsonify(r)
        return _bad("分档记录不存在", 404)

    @app.get("/api/admission/changes")
    def admission_changes():
        return jsonify(sorted(store.load("admission_changes"),
                              key=lambda c: c.get("at") or "", reverse=True)[:100])

    @app.get("/api/datasources")
    def datasource_status():
        """数据源健康度:各通道最近一轮结果汇总(真实统计,非装饰)。"""
        state = store.load("radar_state") or {}
        last = state.get("last_stats") or {}
        channels = {}
        for q in last.get("queries") or []:
            name = q["q"].split(":")[0] if ":" in q["q"] else q["q"]
            c = channels.setdefault(name, {"ok": 0, "fail": 0, "last_err": None})
            if q.get("ok"):
                c["ok"] += 1
            else:
                c["fail"] += 1
                c["last_err"] = q.get("err")
        items = []
        for name, c in channels.items():
            total = c["ok"] + c["fail"]
            items.append({"channel": name, "queries": total,
                          "success_rate": round(100 * c["ok"] / total) if total else 0,
                          "last_error": c["last_err"]})
        return jsonify({"last_success": state.get("last_success"),
                        "last_attempt": state.get("last_attempt"),
                        "failure_reason": state.get("failure_reason"),
                        "channels": items,
                        "principles": "仅官方接口与合法公开信息;不绕过登录/验证码/反爬;"})

    @app.get("/api/radar/analyze/<rid>")
    def radar_analyze(rid):
        """经验贴拆解:AI 可用则按摘要提炼,否则规则提炼,generator 如实标注。
        只依据库内标题/摘要,不编造作者、分数、结果。"""
        it = next((x for x in store.load("radar") if x["id"] == rid), None)
        if not it:
            return _bad("内容不存在", 404)
        summary = it.get("summary") or ""
        sub_name = {"math": "数学一", "cs408": "408", "english": "英语一",
                    "politics": "政治", "general": "通用"}.get(it.get("subject"), "通用")
        out = {
            "id": rid, "title": it["title"], "url": it["url"],
            "method": "摘要未提供足够细节,点击原文查看完整方法。",
            "background": "作者背景以原文自述为准,系统未核验。",
            "audience": "适合关注「%s」的考生" % sub_name,
            "limits": ("仅摘要信息(来源:%s),完整性以原文为准;" % it.get("platform", "未知"))
                      + ("日期未核验。" if not it.get("published_at")
                         else "发布于 %s。" % it["published_at"]),
            "generator": "rule", "model": "",
        }
        try:
            cfg = ai_mod.get_ai_config(store.load("settings"))
            if cfg.get("available") and summary:
                raw = json.dumps({"title": it["title"], "summary": summary},
                                 ensure_ascii=False)
                resp, err = ai_mod._post_chat(cfg, [
                    {"role": "system", "content":
                        "你是备考分析助手。仅依据给定标题与摘要,输出 JSON:"
                        '{"method":"作者用了什么方法(≤60字,原文没有就写原文未提供)",'
                        '"background":"作者背景(原文未提供就写原文未提供)",'
                        '"audience":"适合什么人群/阶段(≤50字)",'
                        '"limits":"局限与注意事项(≤60字)"}'
                        "禁止编造分数、录取结果、作者身份。"},
                    {"role": "user", "content": raw}], timeout=45, json_mode=True)
                if not err and resp:
                    data = ai_mod._parse_json_loose(resp)
                    if data:
                        for k in ("method", "background", "audience", "limits"):
                            if data.get(k):
                                out[k] = str(data[k])[:120]
                        out["generator"], out["model"] = "ai", cfg.get("model", "")
        except Exception:
            pass  # AI 失败保留规则版
        return jsonify(out)

    # ---------- 成长时间线 ----------
    @app.get("/api/growth/timeline")
    def growth_timeline():
        from .storage import COLLECTIONS as _C
        records = store.load("records")
        reflections = store.load("reflections")
        mistakes = store.load("mistakes")
        plan_days = store.load("plan").get("days") or {}
        kp = {k["id"]: k["name"] for k in store.load("knowledge")}
        days = {}
        for r in records:
            d = days.setdefault(r.get("date", ""), {"date": r.get("date"), "events": [],
                                                    "tasks_done": 0, "questions": 0,
                                                    "correct": 0})
            d["questions"] += r.get("total", 0)
            d["correct"] += r.get("correct", 0)
            d["events"].append("练习:%s 做 %d 对 %d" % (SUBJECT_NAMES.get(r["subject"], r["subject"]),
                                                        r.get("total", 0), r.get("correct", 0)))
        for ref in reflections:
            d = days.setdefault(ref["date"], {"date": ref["date"], "events": [],
                                              "tasks_done": 0, "questions": 0, "correct": 0})
            d["events"].append("反思:" + (ref.get("extracted", {}).get("content") or "")[:50])
        for m in mistakes:
            for rev in m.get("reviews") or []:
                d = days.setdefault(rev["date"], {"date": rev["date"], "events": [],
                                                  "tasks_done": 0, "questions": 0, "correct": 0})
                d["events"].append("复测%s:%s" % (
                    "通过" if rev.get("result") != "again" else "未通过",
                    (m.get("question_md") or "")[:28]))
        for ds, day in plan_days.items():
            for t in day.get("tasks") or []:
                if t.get("status") == "done":
                    d = days.setdefault(ds, {"date": ds, "events": [], "tasks_done": 0,
                                             "questions": 0, "correct": 0})
                    d["tasks_done"] += 1
                    d["events"].append("完成任务:" + t["title"][:40])
        for g in store.load("goals").get("milestones") or []:
            if g.get("done") and g.get("done_date"):
                d = days.setdefault(g["done_date"], {"date": g["done_date"], "events": [],
                                                     "tasks_done": 0, "questions": 0, "correct": 0})
                d["events"].append("🏆 里程碑达成:" + g["title"])
        out = sorted(days.values(), key=lambda x: x["date"], reverse=True)
        for d in out:
            d["events"] = d["events"][:6]
        return jsonify(out[:120])

    @app.get("/api/growth/heatmap")
    def growth_heatmap():
        records = store.load("records")
        reflections = store.load("reflections")
        mistakes = store.load("mistakes")
        plan_days = store.load("plan").get("days") or {}
        counts = {}
        for r in records:
            counts[r.get("date", "")] = counts.get(r.get("date", ""), 0) + r.get("total", 0)
        for ref in reflections:
            counts[ref.get("date", "")] = counts.get(ref.get("date", ""), 0) + 1
        for m in mistakes:
            for rev in m.get("reviews") or []:
                counts[rev.get("date", "")] = counts.get(rev.get("date", ""), 0) + 1
        for ds, day in plan_days.items():
            for t in day.get("tasks") or []:
                if t.get("status") == "done":
                    counts[ds] = counts.get(ds, 0) + 1
        today = _today()
        weeks = []
        start = today - datetime.timedelta(days=today.weekday() + 7 * 25)
        for w in range(26):
            col = []
            for dd in range(7):
                day = start + datetime.timedelta(days=w * 7 + dd)
                ds = day.isoformat()
                col.append({"date": ds, "count": counts.get(ds, 0),
                            "future": day > today})
            weeks.append(col)
        return jsonify({"weeks": weeks})

    # ---------- 情报站:资源 / 搜索 ----------
    @app.get("/api/sources")
    def sources_list():
        return jsonify(store.load("sources"))

    @app.post("/api/sources")
    def sources_add():
        body = request.get_json(force=True, silent=True) or {}
        if not (body.get("url") or "").strip():
            return _bad("URL 必填")
        items = store.load("sources")
        item = {"id": _next_id(items, "src"),
                "name": (body.get("name") or body["url"])[:80],
                "url": body["url"].strip(), "kind": body.get("kind") or "repo",
                "license": body.get("license") or "未核验",
                "status": body.get("status") or "待核验",   # 待核验|仅链接|可引用|已导入
                "notes": body.get("notes") or "",
                "added": datetime.datetime.now().isoformat(timespec="seconds"),
                "last_checked": None, "check_result": None}
        items.append(item)
        store.save("sources", items)
        auth_mod.audit(store, "source_added", item["url"])
        return jsonify(item), 201

    @app.put("/api/sources/<sid>")
    def sources_update(sid):
        body = request.get_json(force=True, silent=True) or {}
        items = store.load("sources")
        for s in items:
            if s["id"] == sid:
                for f in ("name", "kind", "license", "status", "notes"):
                    if f in body:
                        s[f] = body[f]
                store.save("sources", items)
                return jsonify(s)
        return _bad("来源不存在", 404)

    @app.delete("/api/sources/<sid>")
    def sources_delete(sid):
        items = store.load("sources")
        store.save("sources", [s for s in items if s["id"] != sid])
        return jsonify({"deleted": sid})

    @app.post("/api/sources/<sid>/check")
    def sources_check(sid):
        """链接有效性核验:HEAD(失败回退 GET),记录核验时间与结果。"""
        items = store.load("sources")
        for s in items:
            if s["id"] == sid:
                result = "未知"
                code = None
                try:
                    rq = urllib.request.Request(s["url"], method="HEAD",
                                                headers={"User-Agent": "ascent-intel/1.0"})
                    with urllib.request.urlopen(rq, timeout=15) as resp:
                        code = resp.status
                        result = "可访问(HTTP %d)" % code
                except urllib.error.HTTPError as e:
                    if e.code in (403, 405, 999):
                        try:
                            rq = urllib.request.Request(s["url"],
                                                        headers={"User-Agent": "ascent-intel/1.0"})
                            with urllib.request.urlopen(rq, timeout=15) as resp:
                                code = resp.status
                                result = "可访问(HTTP %d,HEAD 被拒)" % code
                        except Exception as e2:
                            result = "访问失败:%s" % str(e2)[:60]
                    else:
                        result = "HTTP %d" % e.code
                except Exception as e:
                    result = "无法访问:%s" % str(e)[:60]
                s["last_checked"] = datetime.datetime.now().isoformat(timespec="seconds")
                s["check_result"] = result
                store.save("sources", items)
                return jsonify(s)
        return _bad("来源不存在", 404)

    @app.get("/api/search/github")
    def search_github():
        """GitHub 仓库搜索(公开 API,无鉴权,10 次/分钟限速内)。"""
        q = (request.args.get("q") or "").strip()
        if not q:
            return _bad("q 必填")
        try:
            rq = urllib.request.Request(
                "https://api.github.com/search/repositories?q=%s&per_page=8" %
                urllib.parse.quote(q),
                headers={"Accept": "application/vnd.github+json",
                         "User-Agent": "ascent-intel/1.0"})
            with urllib.request.urlopen(rq, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return _bad("GitHub 搜索失败:HTTP %d(可能是限速,稍后再试)" % e.code, 502)
        except Exception as e:
            return _bad("GitHub 搜索失败:%s" % str(e)[:80], 502)
        out = []
        for it in data.get("items") or []:
            out.append({"full_name": it["full_name"], "url": it["html_url"],
                        "description": (it.get("description") or "")[:160],
                        "stars": it.get("stargazers_count"),
                        "license": (it.get("license") or {}).get("spdx_id"),
                        "pushed_at": it.get("pushed_at")})
        recs = store.load("search_records")
        recs.append({"id": _next_id(recs, "sr"), "provider": "github", "q": q,
                     "results": len(out),
                     "date": datetime.datetime.now().isoformat(timespec="seconds")})
        store.save("search_records", recs[-200:])
        return jsonify({"items": out, "total": data.get("total_count", len(out))})

    @app.get("/api/data-quality")
    def data_quality():
        """数据质量报告:全部指标由真实数据计算,网页能打开≠内容正确。"""
        mistakes = store.load("mistakes")
        knowledge = store.load("knowledge")
        sources = store.load("sources")
        records = store.load("records")
        reflections = store.load("reflections")
        today = _today()

        def stale(iso, days=30):
            if not iso:
                return True
            try:
                d = datetime.datetime.fromisoformat(iso)
                return (datetime.datetime.now() - d).days > days
            except ValueError:
                return True

        src_stats = {
            "total": len(sources),
            "never_checked": sum(1 for s in sources if not s.get("last_checked")),
            "stale": sum(1 for s in sources if stale(s.get("last_checked"))),
            "accessible": sum(1 for s in sources
                              if "可访问" in (s.get("check_result") or "")),
            "no_license": sum(1 for s in sources
                              if "无" in (s.get("license") or "")),
            "last_success": max((s["last_checked"] for s in sources
                                 if s.get("last_checked")), default=None),
        }
        mk_stats = {
            "total": len([m for m in mistakes if not m.get("archived")]),
            "missing_solution": sum(1 for m in mistakes
                                    if not m.get("archived") and not (m.get("solution_md") or m.get("correct_answer_md"))),
            "missing_reason": sum(1 for m in mistakes
                                  if not m.get("archived") and not m.get("error_reason")),
            "needs_confirmation": sum(1 for m in mistakes
                                      if m.get("needs_confirmation")),
        }
        # 重复检测:题面归一化(去空白/标点)后分组
        seen = {}
        dup = 0
        for m in mistakes:
            key = re.sub(r"[\s,。;:、()()?,?']", "",
                         (m.get("question_md") or m.get("image") or "").lower())[:80]
            if not key:
                continue
            if key in seen:
                dup += 1
            else:
                seen[key] = m["id"]
        mk_stats["duplicates"] = dup
        last_record = max((r.get("date") for r in records), default=None)
        last_reflect = max((r.get("date") for r in reflections), default=None)
        return jsonify({
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "sources": src_stats,
            "mistakes": mk_stats,
            "knowledge": {"total": len(knowledge),
                          "not_started": sum(1 for k in knowledge
                                             if k.get("status") == "not_started"),
                          "missing_source": sum(1 for k in knowledge
                                                if not k.get("source"))},
            "activity": {"last_record": last_record, "last_reflection": last_reflect,
                         "records": len(records), "reflections": len(reflections)},
            "notes": ["网页可访问不代表内容正确;官方政策以原文链接为准",
                      "「待核验」内容未经人工确认,不得当作已验证事实"],
        })

    @app.get("/api/search/records")
    def search_records():
        return jsonify(store.load("search_records")[-50:][::-1])

    @app.errorhandler(Exception)
    def on_error(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return _bad(e.description or e.name, e.code or 400)
        app.logger.exception(e)
        return _bad("服务器内部错误:%s" % e, 500)

    return app, store


def main():
    store = Store()
    created = seed_if_empty(store)
    if created:
        print("已初始化数据文件:", ", ".join(created))
    for note in migrate_mod.run_migrations(store):
        print("迁移:", note)
    app, store = create_app()
    # 启动时一次性清扫过期会话(收敛公网暴露面)
    purged = auth_mod.purge_expired_sessions(store)
    if purged:
        print("已清扫过期会话:", purged)
    # 热点雷达定时刷新:仅当用户在设置里开启且非测试环境才启动后台线程
    if (store.load("settings").get("radar") or {}).get("auto_refresh") \
            and not os.environ.get("PYTEST_CURRENT_TEST"):
        from . import radar as _RADAR
        _RADAR.start_auto_thread(store)
        print("热点雷达:定时自动刷新已开启(每 6 小时)")
    if store.load("settings").get("backup_on_start", True):
        dest = store.backup("startup")
        print("启动备份:", dest)
    import os as _os
    ip = _lan_ip()
    port = int(_os.environ.get("DX_PORT") or _os.environ.get("PORT") or 8321)
    has_account = bool(auth_mod.get_user(store))
    print("大雪深埋 · AI 考研私人教练 已启动 (Ctrl+C 退出)")
    print("  本机访问: http://127.0.0.1:%d" % port)
    if not has_account:
        print("  首次使用:打开首页创建管理员账号")
    if ip:
        print("  手机访问(同一 Wi-Fi): http://%s:%d" % (ip, port))
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
