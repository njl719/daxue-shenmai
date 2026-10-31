# -*- coding: utf-8 -*-
"""ai.py 测试(V2.0 云端-only):配置合并、规则降级、JSON 容错、Ollama 移除红线。"""
from app import ai


def test_get_ai_config_empty():
    cfg = ai.get_ai_config({})
    assert cfg["available"] is False
    assert cfg["mode"] == "cloud"


def test_get_ai_config_from_settings():
    cfg = ai.get_ai_config({"ai": {
        "base_url": "https://x/v4", "api_key": "sk-test", "model": "m1"}})
    assert cfg["mode"] == "cloud"
    assert cfg["available"] is True
    assert cfg["model"] == "m1"


def test_get_ai_config_env_fallback(monkeypatch):
    monkeypatch.setenv("ZHIPUAI_API_KEY", "zk-123")
    cfg = ai.get_ai_config({"ai": {}})
    assert cfg["available"] is True
    assert "bigmodel" in cfg["base_url"]
    assert cfg["model"]


def test_no_local_ollama_artifacts():
    """第四轮红线:本地 Ollama 相关代码必须不存在。"""
    src = open("app/ai.py", encoding="utf-8").read()
    for bad in ("11434", "list_local_models", "local_service_ok", "ollama serve",
                "LOCAL_BASE_URL", 'mode == "local"'):
        assert bad not in src, bad


def test_extract_reflection_honest_without_key():
    r = ai.extract_reflection("今天408看了两个小时操作系统,进程同步还是混乱。", cfg={})
    assert r["ai_available"] is False and r["ok"] is False
    assert "配置" in r["error"]
    ex = r["extracted"]
    assert ex["source"] == "rule"
    assert "cs408" in ex["subjects"]
    assert ex["minutes"] == 120


def test_rule_extract_subjects_and_time():
    r = ai.rule_extract_reflection("今天408看了两个小时操作系统,进程同步还是混乱,效率不高。")
    ex = r["extracted"]
    assert "cs408" in ex["subjects"]
    assert ex["minutes"] == 120
    assert any("混乱" in w for w in ex["weak_points"])
    assert ex["mood"]


def test_rule_extract_math_and_plan():
    r = ai.rule_extract_reflection("今天积分换元思路没想到,明天继续积分专项。")
    assert "math" in r["extracted"]["subjects"]
    assert any("积分" in w for w in r["extracted"]["weak_points"])


def test_rule_extract_neutral_text():
    r = ai.rule_extract_reflection("今天背了 100 个单词。")
    assert "english" in r["extracted"]["subjects"]
    assert r["extracted"]["weak_points"] == []  # 没有薄弱信号不硬造


def test_rule_extract_minutes_fallback():
    r = ai.rule_extract_reflection("今天复习 45 分钟计算机网络。")
    assert r["extracted"]["minutes"] == 45
    assert "cs408" in r["extracted"]["subjects"]


def test_extract_reflection_rule_shape_matches_api():
    r = ai.extract_reflection("今天英语阅读错了一篇,定位总是找不到。", cfg={})
    ex = r["extracted"]
    assert "english" in ex["subjects"] and ex["source"] == "rule"
    for f in ("content", "mood", "next_plan"):
        assert f in ex


def test_parse_json_loose():
    assert ai._parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
    assert ai._parse_json_loose("好的,结果如下 {\"a\": 2} 请查收") == {"a": 2}
    assert ai._parse_json_loose("没有json") is None
