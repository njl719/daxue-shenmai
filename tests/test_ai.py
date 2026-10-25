# -*- coding: utf-8 -*-
"""ai.py 测试:规则解析、无 Key 诚实降级、配置合并。"""
from app import ai


def test_get_ai_config_empty():
    cfg = ai.get_ai_config({})
    assert cfg["available"] is False


def test_get_ai_config_from_settings():
    cfg = ai.get_ai_config({"ai": {
        "mode": "cloud", "base_url": "https://x/v4",
        "api_key": "sk-test", "model": "m1"}})
    assert cfg["mode"] == "cloud"
    assert cfg["available"] is True  # 云端模式不依赖本地 Ollama
    assert cfg["model"] == "m1"


def test_get_ai_config_env_fallback(monkeypatch):
    monkeypatch.setenv("ZHIPUAI_API_KEY", "zk-123")
    cfg = ai.get_ai_config({"ai": {"mode": "cloud"}})
    assert cfg["available"] is True
    assert "bigmodel" in cfg["base_url"]
    assert cfg["model"]  # 云端 env 兜底自动带默认模型名


def test_local_mode_is_default_and_needs_no_key():
    """本地模式是默认:无 Key、有 Ollama 服务即可用。"""
    cfg = ai.get_ai_config({})
    assert cfg["mode"] == "local"
    assert cfg["base_url"].startswith("http://localhost:11434")
    # available 只取决于服务是否运行 + 是否选了模型,与 Key 无关
    if cfg["service_ok"]:
        assert cfg["available"] == bool(cfg.get("model"))


def test_list_local_models_returns_real_data():
    models = ai.list_local_models()
    assert isinstance(models, list)
    for m in models:
        assert "name" in m and "vision" in m and "cloud" in m


def test_recognize_without_key_is_honest():
    r = ai.recognize_mistake(b"fake-image-bytes", cfg={})
    assert r["ai_available"] is False
    assert r["ok"] is False
    assert r["data"]["needs_confirmation"] is True
    assert r["data"]["confidence"] == 0.0
    assert "未配置" in r["error"] or "配置" in r["error"]
    # 不伪造识别文本
    assert r["data"]["question_text"] == ""


def test_coach_without_key_is_honest():
    r = ai.coach_reply("我数学不行", "context", cfg={})
    assert r["reply"] is None
    assert r["ai_available"] is False
    assert "配置" in r["error"]


def test_rule_extract_subjects_and_time():
    r = ai.rule_extract_reflection("今天408看了两个小时操作系统,进程同步还是混乱,效率不高。")
    ex = r["extracted"]
    assert r["ai_available"] is False
    assert ex["source"] == "rule"
    assert "cs408" in ex["subjects"]
    assert ex["minutes"] == 120
    assert any("混乱" in w for w in ex["weak_points"])
    assert ex["mood"]


def test_rule_extract_counts_and_plan():
    r = ai.rule_extract_reflection(
        "今天张宇强化题做了十道,三道不会,两道是积分换元思路没想到。明天继续积分专项。")
    ex = r["extracted"]
    assert "math" in ex["subjects"]
    assert "十道" in ex["tasks_done"] or ex["tasks_done"]
    assert any("积分" in w for w in ex["weak_points"])
    assert "明天" in ex["next_plan"]


def test_rule_extract_neutral_text():
    r = ai.rule_extract_reflection("今天背了 100 个单词。")
    ex = r["extracted"]
    assert "english" in ex["subjects"]
    # 没有薄弱信号就不该硬造薄弱点
    assert ex["weak_points"] == []


def test_extract_reflection_falls_back_to_rule():
    r = ai.extract_reflection("今天英语阅读错了一篇,定位总是找不到。", cfg={})
    assert r["extracted"]["source"] == "rule"
    assert r["ai_available"] is False


def test_parse_json_loose():
    assert ai._parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
    assert ai._parse_json_loose("好的,结果如下 {\"a\": 2} 请查收") == {"a": 2}
    assert ai._parse_json_loose("没有json") is None
