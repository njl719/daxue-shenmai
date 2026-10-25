# -*- coding: utf-8 -*-
"""本地模型考研任务评测集(A-G)。

前置:Flask 服务运行于 127.0.0.1:8321,且已在设置中选择本地模型。
运行:python tests/benchmark_local.py
输出:docs/BENCHMARK.md + 控制台表格

原则:数学题用已知标准答案核验;失败如实记录,不修饰。
"""
import json
import os
import re
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8321"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "BENCHMARK.md")


def call(path, data=None, method=None, timeout=180):
    url = BASE + "/api" + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"},
                                 method=method or ("POST" if body else "GET"))
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), time.time() - t0, None
    except Exception as e:
        try:
            return {}, time.time() - t0, str(e)[:150]
        except Exception:
            return {}, time.time() - t0, str(e)[:150]


RESULTS = []


def record(task, desc, passed, detail, seconds):
    RESULTS.append({"task": task, "desc": desc, "passed": passed,
                    "detail": detail, "seconds": round(seconds, 1)})
    print("[%s] %s — %s (%.1fs)" % ("PASS" if passed else "FAIL", task, detail, seconds))


# ---------------- A. 中文学习记录整理 ----------------
def bench_A():
    text = ("今天408看了两个小时操作系统,主要在看进程同步和信号量,"
            "PV操作的题做了五道错了三道,有两道是完全没思路,一道是算错了。"
            "感觉生产者消费者那块还是混乱,明天重看王道课件再练。")
    r, sec, err = call("/reflections/extract", {"text": text}, timeout=240)
    ex = r.get("extracted") or {}
    checks = {
        "AI 参与(extract 生效)": r.get("ai_available") is True,
        "科目含 cs408": "cs408" in (ex.get("subjects") or []),
        "时长≈120分钟": ex.get("minutes") == 120,
        "薄弱点提到同步/信号量/PV": any(
            re.search(r"同步|信号量|PV|生产者", w)
            for w in (ex.get("weak_points") or [])),
        "含下一步计划": bool((ex.get("next_plan") or "").strip())
                        or bool(re.search(r"王道|课件|重看", json.dumps(ex, ensure_ascii=False))),
        "标记需确认": ex.get("needs_confirmation") is True,
    }
    passed = all(checks.values())
    detail = "; ".join(k + ("✓" if v else "✗") for k, v in checks.items())
    if err:
        detail = "请求失败:" + err
    record("A 中文学习记录整理", "反思→结构化(科目/时长/薄弱点/计划)", passed, detail, sec)
    return ex


# ---------------- B. 数学题目讲解(标准答案核验) ----------------
# 数学答案的合法表达(分数有多种写法:1/2、½、0.5、\frac{1}{2})
HALF = r"(1\s*[/_\\]\s*2|½|0\.5|\\\\frac\{1\}\{2\}|frac\{1\}\{2\})"
MATH_CASES = [
    {
        "q": "求极限:lim(x→0) (tan x − sin x) / x³。请给出完整推导和最终结果。",
        "accept": [HALF],
        "answer": "1/2",
    },
    {
        "q": "计算定积分 ∫₀^(π/2) sin(x)·cos(x) dx,给出过程和数值结果。",
        "accept": [HALF],
        "answer": "1/2",
    },
    {
        "q": "已知 f(x)=x³−3x,求它的极小值点(用坐标表示)。",
        "accept": [r"\(?1\s*,\s*-2\)?|x\s*=\s*1|极小值点.{0,6}1"],
        "answer": "(1, −2)",
    },
]


def bench_B():
    total_pass = 0
    total_sec = 0
    details = []
    for i, case in enumerate(MATH_CASES, 1):
        r, sec, err = call("/coach/chat", {"message": case["q"]}, timeout=300)
        reply = r.get("reply") or ""
        ok = bool(reply) and any(re.search(p, reply) for p in case["accept"])
        total_pass += ok
        total_sec += sec
        hit = next((p for p in case["accept"] if re.search(p, reply)), "未命中")
        details.append("题%d:%s(标准答案 %s,匹配 %s,%.0fs%s)"
                       % (i, "✓" if ok else "✗", case["answer"], hit, sec,
                          ";应用层错误:" + (r.get("error") or "")[:60]
                          if (not ok and r.get("error")) else ""))
        if err:
            details.append("错误:" + err)
    passed = total_pass >= 2  # 3 题至少对 2 才算该任务通过
    record("B 数学题目讲解", "3 题按标准答案核验(≥2 题正确算通过)",
           passed, "; ".join(details), total_sec / len(MATH_CASES))


# ---------------- C. 408 知识分析 ----------------
CS_CASES = [
    {
        "q": "快速排序的平均时间复杂度是多少?当输入已经有序且以第一个元素为主元时,最坏时间复杂度是多少?分别说明原因。",
        "accept": [r"O\(n[^)]{0,3}[²2^]\)|n\^?2|平方级", r"O\(n\s*\\?log|n\s*\\?log\s*n|O\(nlgn\)"],
        "answer": "平均 O(n log n);已有序时最坏 O(n²)",
    },
    {
        "q": "TCP 为什么需要三次握手,两次为什么不行?",
        "accept": [r"三次|3次", r"失效|旧|重复|确认|半连接|同步|资源"],
        "answer": "防止失效的连接请求到达导致资源浪费/状态不一致",
    },
]


def bench_C():
    total_pass = 0
    details = []
    total_sec = 0
    for i, case in enumerate(CS_CASES, 1):
        r, sec, err = call("/coach/chat", {"message": case["q"]}, timeout=300)
        reply = r.get("reply") or ""
        ok = bool(reply) and all(re.search(p, reply) for p in case["accept"])
        total_pass += ok
        total_sec += sec
        details.append("题%d:%s(%.0fs%s)" % (i, "✓" if ok else "✗", sec,
                      ";应用层错误:" + (r.get("error") or "")[:60] if (not ok and r.get("error")) else ""))
        if err:
            details.append("错误:" + err)
    record("C 408 知识分析", "%d/%d 题要点命中" % (total_pass, len(CS_CASES)),
           total_pass == len(CS_CASES), "; ".join(details), total_sec / len(CS_CASES))


# ---------------- D. 错因分析 ----------------
def bench_D():
    msg = (
        "这是学生的一道错题,请分析错误原因,并从以下类别中选择最准确的一个:"
        "概念不清/公式或定理使用错误/计算失误/推导不严谨/建模或思路错误/审题错误/方法不熟练/知识遗忘。\n"
        "题目:lim(x→0) (e^x − 1 − x)/x²\ n"
        "学生的解答:当 x→0 时 e^x−1 ~ x,所以分子 e^x−1−x ~ x−x = 0,故极限为 0。\n"
        "标准答案:1/2(泰勒展开 e^x = 1+x+x²/2+o(x²))。请指出学生错在哪一步、属于哪类错误。"
    ).replace("\\ n", "\n")
    r, sec, err = call("/coach/chat", {"message": msg}, timeout=300)
    reply = r.get("reply") or ""
    checks = {
        "指出等价无穷小加减误用": bool(re.search(r"等价无穷小|加减|相减|泰勒|展开", reply)),
        "归类正确(公式/定理使用错误 或 方法类)": bool(re.search(
            r"公式或定理|使用错误|方法|思路|概念", reply)),
        "结论正确(1/2)": bool(re.search(HALF, reply)),
    }
    passed = all(checks.values())
    detail = "; ".join(k + ("✓" if v else "✗") for k, v in checks.items())
    if err:
        detail = "请求失败:" + err
    record("D 错因分析", "定位等价无穷小误用并正确归类", passed, detail, sec)


# ---------------- E. 结构化输出 ----------------
def bench_E(extracted_from_A):
    ex = extracted_from_A or {}
    required = ["subjects", "content", "weak_points", "difficulties",
                "mood", "next_plan", "needs_confirmation"]
    missing = [k for k in required if k not in ex]
    passed = not missing and isinstance(ex.get("subjects"), list)
    record("E 结构化输出", "反思提取 JSON 字段完整性(%d/%d)" %
           (len(required) - len(missing), len(required)),
           passed, ("缺失:" + ",".join(missing)) if missing else "字段齐全且类型正确", 0)


# ---------------- F. 本地持久化 ----------------
def bench_F():
    text = "评测专用反思:今天英语精读一篇,定位题仍会错,明天复盘。"
    r1, _, err1 = call("/reflections/extract", {"text": text}, timeout=240)
    ex = r1.get("extracted") or {}
    ex.setdefault("subjects", ["english"])
    r2, _, err2 = call("/reflections", {"raw_text": text, "extracted": ex,
                                        "confirmed": True})
    rid = r2.get("id")
    lst, _, err3 = call("/reflections?limit=50")
    found = any(x.get("id") == rid for x in lst) if rid else False
    # 再查一次(模拟重启后查询:服务无状态读盘,等价验证)
    lst2, _, err4 = call("/reflections?limit=50")
    found2 = any(x.get("id") == rid for x in lst2) if rid else False
    passed = bool(rid) and found and found2
    detail = ("保存 %s,查询 %s,二次查询 %s" %
              ("✓" if rid else "✗", "✓" if found else "✗", "✓" if found2 else "✗"))
    for e in (err1, err2, err3, err4):
        if e:
            detail += ";错误:" + e
    record("F 本地持久化", "反思保存→查询→二次查询", passed, detail, 0)
    return rid


# ---------------- G. 故障降级 ----------------
def bench_G():
    """要求:Ollama 已被停止(由外部执行),验证基础功能可用且 AI 诚实报错。"""
    checks = {}
    st, _, _ = call("/ai/status")
    checks["AI 状态正确报告不可用"] = st.get("available") is False
    m, _, e1 = call("/mistakes")
    checks["错题列表可用"] = isinstance(m, list) and not e1
    p, _, e2 = call("/profile")
    checks["画像可用"] = "subjects" in p and not e2
    r, _, e3 = call("/report/weekly/" + time.strftime("%Y-%m-%d"))
    checks["周报可用"] = "week_start" in r and not e3
    ex, _, e4 = call("/reflections/extract", {"text": "今天数学做了一套卷子,计算失误多。"}, timeout=60)
    checks["反思回退规则解析"] = (ex.get("extracted") or {}).get("source") == "rule"
    ch, _, e5 = call("/coach/chat", {"message": "测试"})
    checks["对话诚实报错而非伪造"] = ch.get("reply") is None and ch.get("ai_available") is False
    passed = all(checks.values())
    detail = "; ".join(k + ("✓" if v else "✗") for k, v in checks.items())
    record("G 故障降级", "Ollama 停止后基础功能与诚实降级", passed, detail, 0)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    # 前置检查
    st, _, err = call("/ai/status")
    print("AI 状态:", json.dumps({k: st.get(k) for k in
                                  ("mode", "available", "service_ok", "model")},
                                 ensure_ascii=False))
    if err:
        print("无法连接评测目标服务:", err)
        return
    if only == "G":
        bench_G()
    else:
        ex = bench_A()
        bench_B()
        bench_C()
        bench_D()
        bench_E(ex)
        bench_F()

    # 输出报告
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    lines = ["# 本地模型考研任务评测报告", "",
             "- 时间:" + time.strftime("%Y-%m-%d %H:%M:%S"),
             "- 模型:%s(本地 Ollama)" % st.get("model", "?"),
             "- 评测对象:系统真实 HTTP API(非直接调用模型)", "",
             "| 任务 | 说明 | 结果 | 耗时 | 详情 |", "|---|---|---|---|---|"]
    npass = sum(1 for r in RESULTS if r["passed"])
    for r in RESULTS:
        lines.append("| %s | %s | %s | %.0fs | %s |" %
                     (r["task"], r["desc"], "✅" if r["passed"] else "❌",
                      r["seconds"], r["detail"].replace("|", "\\|")))
    lines.insert(5, "")
    lines.insert(5, "**总评:%d/%d 项通过**" % (npass, len(RESULTS)))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n报告已写入", OUT)
    print("总评:%d/%d 项通过" % (npass, len(RESULTS)))


if __name__ == "__main__":
    main()
