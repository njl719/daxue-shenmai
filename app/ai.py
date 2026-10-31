# -*- coding: utf-8 -*-
"""AI 能力层(V2.0 精简版):仅云端 OpenAI 兼容接口,本地 Ollama 已移除。

- 未配置 Key 时 available=False,调用方走规则降级并如实标注,绝不伪造 AI 结果;
- 不再要求用户安装/启动任何本地模型。
"""
import json
import re
import urllib.error
import urllib.request

DEFAULT_TIMEOUT = 60

SETUP_HINT = (
    "云端 AI 未配置:在「设置中心 → AI」填写 OpenAI 兼容接口的 Base URL / API Key / 模型名后即可启用。"
    "未配置时所有功能使用规则解析(非 AI),基础功能不受影响。"
)

# 云端 Key 环境变量映射(键名 → (BaseURL 默认, 模型默认))
ENV_PROVIDERS = [
    ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
    ("ZHIPUAI_API_KEY", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
    ("DEEPSEEK_API_KEY", "https://api.deepseek.com", "deepseek-chat"),
    ("MOONSHOT_API_KEY", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
    ("DASHSCOPE_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    ("SILICONFLOW_API_KEY", "https://api.siliconflow.cn/v1", "Qwen/Qwen2.5-7B-Instruct"),
]


def get_ai_config(settings):
    """云端配置:settings["ai"] 优先,其次环境变量;无 Key 则 available=False。"""
    import os
    cfg = dict((settings or {}).get("ai") or {})
    cfg["mode"] = "cloud"
    cfg.pop("local", None)
    if not cfg.get("api_key"):
        for kenv, bdefault, mdefault in ENV_PROVIDERS:
            if os.environ.get(kenv):
                cfg["api_key"] = os.environ[kenv]
                cfg["base_url"] = cfg.get("base_url") or bdefault
                cfg["model"] = cfg.get("model") or mdefault
                cfg["source"] = "env:" + kenv
                break
    cfg.setdefault("base_url", "")
    cfg.setdefault("model", "")
    cfg["available"] = bool(cfg.get("api_key") and cfg.get("base_url") and cfg.get("model"))
    return cfg


def test_connection(cfg):
    """连通性自检:发一条最小消息,如实返回结果。"""
    if not cfg.get("available"):
        return {"ok": False, "error": SETUP_HINT}
    text, err = _post_chat(cfg, [{"role": "user", "content": "回复:OK"}], timeout=20)
    if err:
        return {"ok": False, "error": err}
    return {"ok": True, "reply": (text or "")[:40], "model": cfg.get("model", "")}


def _post_chat(cfg, messages, timeout=DEFAULT_TIMEOUT, json_mode=False):
    """调用 OpenAI 兼容 /chat/completions。

    - json_mode=True 时尝试 response_format=json_object,不支持则自动去掉重试;
    - 空回复重试一次,仍为空则如实报错,不伪造回复。
    """
    url = cfg["base_url"].rstrip("/") + "/chat/completions"

    def _payload(with_json):
        p = {"model": cfg["model"], "messages": messages, "temperature": 0.2}
        if with_json:
            p["response_format"] = {"type": "json_object"}
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
        text, err = _do(_payload(False))
    if not err and not (text or "").strip():
        return None, "模型返回了空内容,请重试;若反复出现请换模型"
    return text, err


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


# ---------------- 反思提取(每日反思,成长记录保留) ----------------

REFLECT_PROMPT = """你是考研学习教练。用户写了一段学习反思,请提取为 JSON:
{
 "subjects": ["math|cs408|english|politics 中出现的科目"],
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
    "政治": "politics", "politics": "politics", "马原": "politics",
    "毛中特": "politics", "史纲": "politics", "思修": "politics", "时政": "politics",
}


def normalize_extraction(ex, raw_text=""):
    """对提取结果做确定性归一化:科目转枚举、时长转分钟。"""
    ex = ex or {}
    subs = []
    for s in ex.get("subjects") or []:
        key = str(s).strip().lower()
        v = _SUBJECT_NORMALIZE.get(key) or next(
            (t for cn, t in _SUBJECT_NORMALIZE.items() if cn in key), None)
        if v and v not in subs:
            subs.append(v)
    ex["subjects"] = subs or []
    minutes = ex.get("minutes")
    if not isinstance(minutes, (int, float)) or minutes in (0, ""):
        m = re.search(r"(\d+)\s*(?:小时|h|hours?)", raw_text or "")
        if m:
            minutes = int(m.group(1)) * 60
        else:
            m = re.search(r"(\d+)\s*(?:分钟|min)", raw_text or "")
            minutes = int(m.group(1)) if m else None
    ex["minutes"] = minutes if isinstance(minutes, (int, float)) else None
    for f in ("content", "next_plan", "tasks_done"):
        ex[f] = str(ex.get(f) or "")[:200]
    for f in ("knowledge_names", "difficulties", "weak_points", "hypotheses"):
        ex[f] = [str(x)[:60] for x in (ex.get(f) or []) if str(x).strip()][:6]
    ex["mood"] = str(ex.get("mood") or "")[:20]
    return ex


def extract_reflection(text, cfg=None):
    """每日反思结构化。AI 不可用时返回规则降级(如实标注)。"""
    cfg = cfg or {}
    if not cfg.get("available"):
        r = rule_extract_reflection(text)
        return {"ok": False, "ai_available": False, "error": SETUP_HINT,
                "extracted": r["extracted"]}


def rule_extract_reflection(text):
    """无 AI 时的确定性规则解析:科目关键词、时长、薄弱点信号。"""
    t = text or ""
    subjects = []
    for cn, code in (("数学", "math"), ("高数", "math"), ("积分", "math"),
                     ("极限", "math"), ("408", "cs408"), ("操作系统", "cs408"),
                     ("数据结构", "cs408"), ("组成原理", "cs408"), ("计算机网络", "cs408"),
                     ("英语", "english"), ("阅读", "english"), ("单词", "english"),
                     ("政治", "politics"), ("马原", "politics")):
        if cn in t and code not in subjects:
            subjects.append(code)
    minutes = None
    t_num = t.replace("两", "2").replace("半", "0.5")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:个?小时|h)", t_num)
    if m:
        minutes = int(float(m.group(1)) * 60)
    else:
        m = re.search(r"(\d+)\s*(?:分钟|min)", t_num)
        if m:
            minutes = int(m.group(1))
    weak = [seg.strip()[:40] for seg in re.split(r"[,。;;,;]", t)
            if any(k in seg for k in ("混乱", "不会", "错", "卡", "忘了", "模糊",
                                      "薄弱", "没想到", "想不出", "思路"))][:4]
    mood = ("疲惫" if any(k in t for k in ("累", "疲惫")) else
            "焦虑" if any(k in t for k in ("焦虑", "慌")) else
            "积极" if any(k in t for k in ("顺利", "搞定", "掌握")) else "平稳")
    return {"ok": False, "ai_available": False,
            "error": SETUP_HINT,
            "extracted": {"subjects": subjects, "content": t[:120],
                          "knowledge_names": [], "minutes": minutes,
                          "tasks_done": "", "difficulties": [],
                          "weak_points": weak, "mood": mood,
                          "next_plan": "", "hypotheses": [],
                          "source": "rule"}}


def extract_reflection(text, cfg=None):
    """每日反思结构化。AI 不可用时返回规则降级(如实标注)。"""
    cfg = cfg or {}
    if not cfg.get("available"):
        r = rule_extract_reflection(text)
        return {"ok": False, "ai_available": False, "error": SETUP_HINT,
                "extracted": r["extracted"]}
    out, err = _post_chat(cfg, [
        {"role": "system", "content": REFLECT_PROMPT},
        {"role": "user", "content": text}], timeout=45, json_mode=True)
    if err or not out:
        return {"ok": False, "ai_available": True, "error": err or "空回复",
                "extracted": {"subjects": [], "content": str(text)[:120],
                              "minutes": None, "source": "规则降级"}}
    data = _parse_json_loose(out)
    if not data:
        return {"ok": False, "ai_available": True, "error": "返回无法解析为 JSON",
                "extracted": {"subjects": [], "content": str(text)[:120],
                              "minutes": None, "source": "规则降级"}}
    return {"ok": True, "ai_available": True, "extracted": normalize_extraction(data, text)}
