# -*- coding: utf-8 -*-
"""统一数据可信度等级(V2.0 模块五)。

S   官方原始数据(研招网/高校官网,GitHub 官方 API 元数据亦属权威来源)
A   可信公开信息 + 可追溯真实经验(已核验原文/官方 API)
B   有明确来源但尚未完全核验(仅摘要/用户提交待核验)
AI  模型分析与原创建议(平台原创/AI 生成)
demo 演示数据(seed 标记,永不进入正式内容流)

映射函数只依据已有字段判定,不做任何猜测;判定不了的返回 None(前端显示"来源未定")。
"""
LEVELS = ("S", "A", "B", "AI", "demo")
LEVEL_LABELS = {"S": "S·官方原始", "A": "A·可信公开", "B": "B·来源待核验",
                "AI": "AI·模型/原创", "demo": "演示数据"}


def level_label(level):
    return LEVEL_LABELS.get(level, "来源未定")


def radar_level(item):
    if item.get("source_level"):
        return item["source_level"]
    vs = item.get("verify_status")
    platform = item.get("platform", "")
    if "官方" in platform or item.get("official"):
        return "S"
    if vs == "api":
        return "A"
    if vs == "verified_page":
        return "A"
    if vs in ("snippet_only", "user_submitted"):
        return "B"
    return None


def question_level(q):
    st = q.get("source_type")
    if st == "真题":
        return "S" if q.get("verified_at") else "B"
    if q.get("ai_generated") or st == "AI 生成练习题":
        return "AI"
    if st == "自录题":
        return "AI"  # 平台原创,归 AI/原创层
    return None


def motivation_level(m):
    st = m.get("source_type")
    return {"public_classic": "S", "platform_original": "AI",
            "unverified": "B", "user_note": "B"}.get(st)


def university_level(u):
    if u.get("verified_at") and u.get("admission_source"):
        return "S"
    if u.get("admission_source"):
        return "B"
    return None


def experience_level(p):
    return {"public_experience": "B", "platform_original": "AI"}.get(
        p.get("source_type"))
