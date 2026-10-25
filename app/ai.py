# -*- coding: utf-8 -*-
"""AI 能力层:默认本地 Ollama,云端 OpenAI 兼容接口为可选扩展。

- 本地模式:不需要 API Key,通过 http://localhost:11434 的 OpenAI 兼容端点(/v1)复用统一调用逻辑;
  模型列表通过 Ollama 原生 /api/tags 发现,不假设任何模型已安装。
- 云端模式:默认关闭,必须用户主动填写 Key 才启用。
- 未配置/服务未运行时绝不伪造 AI 结果,反思走透明的规则解析(标注来源)。
"""
import base64
import json
import re
import time
import urllib.error
import urllib.request

DEFAULT_TIMEOUT = 60
LOCAL_BASE_URL = "http://localhost:11434/v1"

SETUP_HINT = (
    "本地 AI 未就绪。两种解决方式:"
    "① 启动本地 Ollama 服务(开始菜单打开 Ollama,或在终端运行 ollama serve),"
    "然后在设置页选择已下载的模型;"
    "② 或在设置页改用云端 API(需自行填写 Key)。"
    "配置前,系统使用规则解析(非 AI),基础功能不受影响。"
)


def local_service_ok(timeout=1.5):
    """探测本地 Ollama 服务是否在运行。"""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/version",
                                    timeout=timeout) as r:
            json.loads(r.read().decode("utf-8"))
        return True
    except Exception:
        return False


def list_local_models():
    """通过 /api/tags 发现本机已下载的模型(不假设任何模型存在)。"""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags",
                                    timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
        out = []
        for m in data.get("models") or []:
            name = m.get("name", "")
            out.append({
                "name": name,
                "size_gb": round((m.get("size") or 0) / 1e9, 1),
                "vision": any(k in name.lower() for k in ("vl", "vision", "llava", "-v")),
                "cloud": "cloud" in name,
            })
        return sorted(out, key=lambda x: (not x["vision"], x["name"]))
    except Exception:
        return []


def get_ai_config(settings):
    """合并设置与环境变量。mode=local(默认)无需 Key;mode=cloud 走 OpenAI 兼容。"""
    import os
    cfg = dict((settings or {}).get("ai") or {})
    mode = cfg.get("mode") or "local"
    cfg["mode"] = mode
    if mode == "local":
        cfg["base_url"] = cfg.get("base_url") or LOCAL_BASE_URL
        cfg["api_key"] = cfg.get("api_key") or "local"  # 占位,本地服务不校验
        cfg.setdefault("model", "")
        cfg.setdefault("vision_model", "")
        cfg["service_ok"] = local_service_ok()
        cfg["available"] = bool(cfg["service_ok"] and cfg.get("model"))
        return cfg

    # 云端模式
    env_map = [
        ("OPENAI_API_KEY", "OPENAI_BASE_URL", None),
        ("ZHIPUAI_API_KEY", None, "https://open.bigmodel.cn/api/paas/v4"),
        ("DEEPSEEK_API_KEY", None, "https://api.deepseek.com"),
        ("MOONSHOT_API_KEY", None, "https://api.moonshot.cn/v1"),
        ("DASHSCOPE_API_KEY", None, "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        ("SILICONFLOW_API_KEY", None, "https://api.siliconflow.cn/v1"),
    ]
    if not cfg.get("api_key"):
        default_model = {
            "ZHIPUAI_API_KEY": "glm-4-flash",
            "DEEPSEEK_API_KEY": "deepseek-chat",
            "MOONSHOT_API_KEY": "moonshot-v1-8k",
            "DASHSCOPE_API_KEY": "qwen-plus",
            "SILICONFLOW_API_KEY": "Qwen/Qwen2.5-7B-Instruct",
            "OPENAI_API_KEY": "gpt-4o-mini",
        }
        for kenv, benv, bdefault in env_map:
            key = os.environ.get(kenv)
            if key:
                cfg["api_key"] = key
                env_base = os.environ.get(benv) if benv else None
                cfg["base_url"] = cfg.get("base_url") or env_base or bdefault
                cfg["model"] = cfg.get("model") or default_model.get(kenv, "")
                cfg["source"] = "env:" + kenv
                break
    cfg.setdefault("base_url", "")
    cfg.setdefault("model", "")
    cfg.setdefault("vision_model", "")
    cfg["available"] = bool(cfg.get("api_key") and cfg.get("base_url") and cfg.get("model"))
    return cfg


def _post_chat(cfg, messages, timeout=DEFAULT_TIMEOUT, json_mode=False):
    """调用 OpenAI 兼容 /chat/completions(本地 Ollama 与云端同构)。

    - json_mode=True 时尝试 response_format=json_object,不支持则自动去掉重试;
    - 返回空内容时重试一次(本地偶发 content=None),仍为空则如实报错,不伪造回复;
    - num_ctx=8192 防止长上下文被默认 4096 截断。
    """
    url = cfg["base_url"].rstrip("/") + "/chat/completions"

    def _payload(with_json, with_ctx=True):
        p = {"model": cfg["model"], "messages": messages, "temperature": 0.2}
        if with_json:
            p["response_format"] = {"type": "json_object"}
        if with_ctx:
            p["options"] = {"num_ctx": 8192}
        return p

    def _do(payload):
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + cfg["api_key"]},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"].get("content"), None
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            if json_mode and e.code in (400, 422):
                return _do(_payload(False))
            msg = ""
            try:
                msg = json.loads(body).get("error", {})
                msg = msg.get("message", "") if isinstance(msg, dict) else str(msg)
            except Exception:
                msg = body[:200]
            return None, "模型接口返回 %s %s" % (e.code, msg)
        except Exception as e:
            return None, "连接模型失败:%s" % str(e)[:200]

    text, err = _do(_payload(json_mode))
    if not err and not (text or "").strip():
        # 本地模型偶发空回复:重试一次(去掉 num_ctx 选项)
        text, err = _do(_payload(json_mode, with_ctx=False))
    if not err and not (text or "").strip():
        return None, "模型返回了空内容,请重试;若反复出现请换模型或减小上下文"
    return text, err


def _image_data_url(image_bytes, mime="image/jpeg"):
    return "data:%s;base64,%s" % (mime, base64.b64encode(image_bytes).decode("ascii"))


def _parse_json_loose(text):
    """从模型回复中提取 JSON(容忍 ```json 包裹与前后废话)。"""
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        try:
            return json.loads(m.group(0).replace("\n", " ").replace(",}", "}").replace(",]", "]"))
        except json.JSONDecodeError:
            return None


# ---------------- 错题图片识别 ----------------

RECOGNIZE_PROMPT = """你是考研错题整理助手。请识别图片中的题目(可能包含手写解题过程和批注),输出 JSON:
{
 "question_text": "题目的完整文字(数学公式用 LaTeX,如 $\\\\lim_{x\\\\to 0}$)",
 "subject": "math|cs408|english 之一",
 "chapter_guess": "推测的章节名",
 "knowledge_names": ["涉及的知识点,最多3个"],
 "qtype": "概念|计算|证明|综合应用|综合|定位错误|逻辑理解错误|词义误判|选项辨析错误 之一",
 "difficulty": 1到5的整数,
 "error_reason": "从这些里选最可能的一个:概念不清/公式或定理使用错误/计算失误/推导不严谨/建模或思路错误/审题错误/方法不熟练/时间分配不合理/知识遗忘/暂时无法判断",
 "solution_draft": "图中的正确解法或批注要点(若看不清写'看不清,需补充')",
 "user_work_seen": "图中用户的手写解题过程摘要(没有则空字符串)",
 "confidence": 0到1的小数(整体识别置信度),
 "notes": "识别模糊、存疑之处的说明;没有则空字符串"
}
要求:看不清的内容明确说"看不清",不要编造;整图包含多道题时,只识别其中第一道,并在 notes 里说明"图中还有N道题"。只输出 JSON。"""


def recognize_mistake(image_bytes, hint="", cfg=None, mime="image/jpeg"):
    """识别错题图片。返回 {ok, ai_available, data|error}。"""
    cfg = cfg or {}
    if not cfg.get("available"):
        return {"ok": False, "ai_available": False, "error": SETUP_HINT,
                "data": _empty_recognition(hint)}
    vision_model = cfg.get("vision_model") or cfg["model"]
    content = [{"type": "text", "text": RECOGNIZE_PROMPT + ("\n用户补充说明:" + hint if hint else "")},
               {"type": "image_url", "image_url": {"url": _image_data_url(image_bytes, mime)}}]
    messages = [{"role": "user", "content": content}]
    call_cfg = dict(cfg)
    call_cfg["model"] = vision_model
    text, err = _post_chat(call_cfg, messages, timeout=90)
    if err:
        return {"ok": False, "ai_available": True, "error": err,
                "data": _empty_recognition(hint)}
    data = _parse_json_loose(text)
    if not data:
        return {"ok": False, "ai_available": True,
                "error": "模型返回内容无法解析为 JSON,请重试或更换模型",
                "data": _empty_recognition(hint)}
    data.setdefault("confidence", 0.5)
    data["needs_confirmation"] = True
    data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))
    if data["confidence"] < 0.6:
        data.setdefault("notes", "")
        data["notes"] = (data["notes"] + " " if data["notes"] else "") + "置信度较低,请仔细校对"
    return {"ok": True, "ai_available": True, "data": data}


def _empty_recognition(hint=""):
    return {
        "question_text": "", "subject": "", "chapter_guess": "",
        "knowledge_names": [], "qtype": "", "difficulty": None,
        "error_reason": "暂时无法判断", "solution_draft": "",
        "user_work_seen": "", "confidence": 0.0,
        "needs_confirmation": True,
        "notes": "AI 未配置或识别失败。请手动填写题目,或先只保存图片稍后补充。" + SETUP_HINT,
    }


# ---------------- 反思提取 ----------------

REFLECT_PROMPT = """你是考研学习教练。用户写了一段学习反思,请提取为 JSON:
{
 "subjects": ["math|cs408|english 中出现的科目"],
 "knowledge_names": ["提到的知识点/章节,尽量具体,最多5个"],
 "content": "一句话概括学了什么",
 "minutes": 估计的学习分钟数(没提则为 null),
 "tasks_done": "完成的任务概述",
 "difficulties": ["遇到的困难,最多4条"],
 "weak_points": ["用户自认为的薄弱点,最多4条"],
 "mood": "从积极/平稳/疲惫/焦虑/低落 中选,或原文关键词",
 "next_plan": "用户说的下一步计划",
 "hypotheses": ["需要后续练习验证的假设,最多3条,没有则空数组"]
}
只输出 JSON。"""


# 科目归一化:模型可能返回中文名
_SUBJECT_NORMALIZE = {
    "数学": "math", "高数": "math", "高等数学": "math", "math": "math",
    "408": "cs408", "计算机": "cs408", "数据结构": "cs408", "操作系统": "cs408",
    "组成原理": "cs408", "计算机组成原理": "cs408", "计算机网络": "cs408", "计网": "cs408",
    "cs408": "cs408", "英语": "english", "english": "english",
}
# 中文数字时长兜底(模型可能返回"两个小时"或缺失)——复用文件头部的 _CN_NUM
_KNOWN_TOPIC_KW = {
    "cs408": ["进程", "线程", "信号量", "同步", "死锁", "内存", "页面", "虚拟", "文件",
              "磁盘", "排序", "链表", "队列", "树", "图", "堆", "栈", "哈希", "查找",
              "TCP", "UDP", "IP", "路由", "以太网", "交换", "Cache", "缓存", "流水线",
              "中断", "总线", "指令", "补码", "浮点", "协议", "子网", "王道", "操作系统",
              "数据结构", "组成原理", "计网", "计算机网络"],
    "math": ["极限", "导数", "积分", "级数", "矩阵", "行列式", "特征值", "二次型",
             "概率", "向量", "微分", "方程", "泰勒", "洛必达", "换元", "卷积", "期望",
             "方差", "张宇", "660", "880", "1000题"],
    "english": ["阅读", "单词", "词汇", "作文", "长难句", "完形", "翻译", "精读",
                "真题", "背词", "Text", "阅读理解"],
}


def normalize_extraction(ex, raw_text=""):
    """对提取结果做确定性归一化:科目转枚举、时长转分钟、按知识点关键词补科目。"""
    ex = ex or {}
    subs = []
    for s in ex.get("subjects") or []:
        key = str(s).strip().lower()
        if key in _SUBJECT_NORMALIZE:
            v = _SUBJECT_NORMALIZE[key]
        else:
            v = next((t for cn, t in _SUBJECT_NORMALIZE.items() if cn in key), None)
        if v and v not in subs:
            subs.append(v)

    # 从知识点/学习内容关键词推断科目(与模型判断取并集,最多3个)
    blob = " ".join(str(x) for x in (ex.get("knowledge_names") or [])) + " " + \
           str(ex.get("content") or "") + " " + (raw_text or "")
    scores = {sub: sum(1 for kw in kws if kw.lower() in blob.lower())
              for sub, kws in _KNOWN_TOPIC_KW.items()}
    inferred = [s for s, n in sorted(scores.items(), key=lambda kv: -kv[1]) if n > 0]
    for s in inferred:
        if s not in subs and len(subs) < 3:
            subs.append(s)
    ex["subjects"] = subs or ["math"]

    minutes = ex.get("minutes")
    if not isinstance(minutes, (int, float)) or minutes in (0, ""):
        minutes = None
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:个)?小时", raw_text)
        if m:
            minutes = int(float(m.group(1)) * 60)
        else:
            m = re.search(r"([0-9一二两三四五六七八九十]+)\s*(?:个)?小时", raw_text)
            if m:
                s = m.group(1)
                v = int(s) if s.isdigit() else (
                    10 if s == "十" else
                    (_CN_NUM.get(s[0], 1) * 10 + _CN_NUM.get(s[-1], 0) if "十" in s else _CN_NUM.get(s)))
                minutes = int(v * 60)
            else:
                m = re.search(r"(\d+)\s*分钟", raw_text)
                if m:
                    minutes = int(m.group(1))
    ex["minutes"] = int(minutes) if minutes else None
    return ex


def extract_reflection(text, cfg=None):
    """提取反思。优先 AI;未配置时用规则解析(明确标注 source='rule')。"""
    cfg = cfg or {}
    if cfg.get("available"):
        messages = [{"role": "user", "content": REFLECT_PROMPT + "\n\n反思原文:\n" + text}]
        reply, err = _post_chat(cfg, messages, json_mode=True, timeout=120)
        if reply:
            data = _parse_json_loose(reply)
            if data:
                data = normalize_extraction(data, text)
                data["source"] = "ai"
                data["needs_confirmation"] = True
                return {"ok": True, "ai_available": True, "extracted": data}
        # AI 失败 → 回退规则解析,并附错误说明
        result = rule_extract_reflection(text)
        result["ai_error"] = err
        return result
    return rule_extract_reflection(text)


_CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
           "七": 7, "八": 8, "九": 9, "十": 10}


def _cn_to_int(s):
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if "十" in s:
        a, _, b = s.partition("十")
        return (_CN_NUM.get(a, 1)) * 10 + (_CN_NUM.get(b, 0) if b else 0)
    return _CN_NUM.get(s, None)


_SUBJECT_PATTERNS = [
    (r"高数|微积分|极限|导数|积分|级数|微分方程", "math"),
    (r"线性代数|线代|矩阵|行列式|特征值", "math"),
    (r"概率|随机变量|数理统计", "math"),
    (r"408|数据结构|组成原理|计组|操作系统|计网|计算机网络|算法|树|图|排序|进程|内存|协议", "cs408"),
    (r"英语|阅读|单词|背词|作文|写作|翻译|长难句|完形", "english"),
]
_TIME_PATTERNS = [
    (r"(\d+(?:\.\d+)?)\s*(?:个)?小时", "hour"),
    (r"([0-9一二两三四五六七八九十]+)\s*(?:个)?半\s*小时", "halfhour"),
    (r"(\d+)\s*分钟", "minute"),
    (r"([0-9一二两三四五六七八九十]+)\s*(?:个)?小时", "hour"),
]
_DONE_PATTERNS = [
    r"做了\s*([0-9一二两三四五六七八九十]+)\s*(?:道|个|题)",
    r"完成\s*([0-9一二两三四五六七八九十]+)\s*(?:道|个|题)",
    r"刷了\s*([0-9一二两三四五六七八九十]+)\s*(?:道|个|题)",
    r"错\s*([0-9一二两三四五六七八九十]+)\s*道",
]
_WEAK_HINTS = r"(不会|不熟|混乱|薄弱|没思路|想不到|没想到|想不出|记不住|模糊|陌生|易错|老是错|反复错|搞不懂|分不清)"
_MOOD_PATTERNS = [
    (r"效率(不高|低)|睡得?太晚|熬夜|累|疲惫|没状态|烦|焦虑|浮躁", "疲惫/低落"),
    (r"状态(不错|很好)|效率(高|不错)|顺利|有成就感|状态好", "积极"),
]
_PLAN_PATTERN = r"(明天|下次|接下来|之后|计划|打算|准备|后续)[^。\n]{2,40}"


def rule_extract_reflection(text):
    """确定性规则解析(非 AI)。只提取有明确语言信号的事实,宁缺勿猜。"""
    out = {
        "subjects": [], "knowledge_names": [], "content": "", "minutes": None,
        "tasks_done": "", "difficulties": [], "weak_points": [], "mood": "",
        "next_plan": "", "hypotheses": [], "source": "rule", "needs_confirmation": True,
    }
    for pat, subj in _SUBJECT_PATTERNS:
        if re.search(pat, text) and subj not in out["subjects"]:
            out["subjects"].append(subj)
    minutes = None
    for pat, unit in _TIME_PATTERNS:
        m = re.search(pat, text)
        if m:
            v = _cn_to_int(m.group(1))
            if v is None:
                continue
            minutes = {"hour": int(v * 60), "halfhour": int(v * 90),
                       "minute": int(v)}[unit] if unit != "halfhour" else int(v * 90)
            if unit == "hour":
                minutes = int(v * 60)
            elif unit == "minute":
                minutes = int(v)
            break
    out["minutes"] = minutes
    for pat in _DONE_PATTERNS:
        m = re.search(pat, text)
        if m:
            n = _cn_to_int(m.group(1))
            out["tasks_done"] = "完成约 %s 题(按原文)" % (n if n else m.group(1))
            break
    for sent in re.split(r"[。;,\n]", text):
        if re.search(_WEAK_HINTS, sent) and len(sent.strip()) > 2:
            s = sent.strip()[:60]
            out["weak_points"].append(s)
            out["difficulties"].append(s)
    for pat, mood in _MOOD_PATTERNS:
        if re.search(pat, text):
            out["mood"] = mood
            break
    m = re.search(_PLAN_PATTERN, text)
    if m:
        out["next_plan"] = m.group(0)[:60]
    out["weak_points"] = out["weak_points"][:4]
    out["difficulties"] = out["difficulties"][:4]
    out["content"] = text.strip().replace("\n", " ")[:80]
    out["notes"] = ("本结果由内置规则解析生成(未调用 AI),只提取了有明确语言信号的内容,"
                    "请核对补全。")
    return {"ok": True, "ai_available": False, "extracted": out}


# ---------------- 教练对话 ----------------

COACH_SYSTEM = """你是考研私人教练。基于提供的用户真实学习证据回答,要求:
1) 明确区分【有数据支持】和【待验证】的结论;
2) 结论必须引用证据(如"最近3次练习对2次"而不是"我觉得");
3) 给出的行动建议要具体、少量、可执行(不超过3条);
4) 数据不足时直说"数据不足,暂时无法判断",不要编造;
5) 回答简洁,不超过250字;
6) 数学计算、正确率、学习时长等以系统提供的证据为准,不要自己算一遍再否定;
7) 若你的建议需要落实到系统(创建复习任务或里程碑),在回答最末尾另起一行输出:
   PROPOSE:{"tools":[{"tool":"create_task","subject":"math","title":"...","est_minutes":20}]}
   只允许 create_task(需要 subject/title/est_minutes)和 create_milestone(需要 title/target_date)两种。
   没有必要动作就不要输出 PROPOSE 行。"""


def coach_reply(message, context_brief, cfg=None, history=None):
    """非流式回复(流式不可用时的降级路径)。"""
    cfg = cfg or {}
    if not cfg.get("available"):
        return {"ok": False, "ai_available": False, "error": SETUP_HINT, "reply": None}
    messages = [{"role": "system", "content": COACH_SYSTEM +
                 "\n\n用户学习证据(系统检索):\n" + context_brief}]
    for h in (history or [])[-6:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})
    reply, err = _post_chat(cfg, messages,
                            timeout=180 if cfg.get("mode") == "local" else DEFAULT_TIMEOUT)
    if err:
        return {"ok": False, "ai_available": True, "error": err, "reply": None}
    return {"ok": True, "ai_available": True, "reply": reply}


def coach_stream(message, context_brief, cfg=None, history=None):
    """流式教练回复(生成器)。

    逐段产出 dict:{"delta": 文本片段};结束时 {"done": True, "reply": 全文, "elapsed": 秒,
    "proposal": 解析出的工具建议或 None};错误产出 {"error": 文本}。
    仅当 cfg 可用时才应调用;调用方负责持久化对话与审计。
    """
    cfg = cfg or {}
    start = time.time()
    messages = [{"role": "system", "content": COACH_SYSTEM +
                 "\n\n用户学习证据(系统检索):\n" + context_brief}]
    for h in (history or [])[-6:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    payload = {"model": cfg["model"], "messages": messages, "temperature": 0.2,
               "stream": True, "options": {"num_ctx": 8192}}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + cfg["api_key"]},
        method="POST")
    full = []
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if body == "[DONE]":
                    break
                try:
                    chunk = json.loads(body)
                    delta = chunk["choices"][0].get("delta", {}).get("content")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    full.append(delta)
                    yield {"delta": delta}
    except urllib.error.HTTPError as e:
        yield {"error": "模型接口返回 %d" % e.code}
        return
    except Exception as e:
        yield {"error": "连接模型失败:%s" % str(e)[:120]}
        return
    text = "".join(full)
    if not text.strip():
        # 流式偶发空回复:同步重试一次
        text, err = _post_chat(cfg, messages, timeout=180)
        if err:
            yield {"error": err}
            return
        if text:
            yield {"delta": text}
    elapsed = round(time.time() - start, 1)
    proposal = None
    # PROPOSE 行按整行解析(正则花括号匹配会被嵌套 JSON 截断)
    clean_lines = []
    for ln in text.split("\n"):
        s = ln.strip()
        if s.startswith("PROPOSE:"):
            try:
                p = json.loads(s[len("PROPOSE:"):].strip())
                tools = [t for t in p.get("tools", [])
                         if t.get("tool") in ("create_task", "create_milestone")]
                if tools:
                    proposal = {"tools": tools}
            except json.JSONDecodeError:
                pass
            continue  # 不在正文中展示原始提案行
        clean_lines.append(ln)
    clean = "\n".join(clean_lines).strip()
    yield {"done": True, "reply": clean, "elapsed": elapsed, "proposal": proposal}


def test_connection(cfg):
    if not cfg.get("available"):
        return {"ok": False, "error": SETUP_HINT}
    text, err = _post_chat(cfg, [{"role": "user", "content": "回复:OK"}], timeout=20)
    if err:
        return {"ok": False, "error": err}
    return {"ok": True, "sample": (text or "")[:50]}
