# -*- coding: utf-8 -*-
"""第四轮测试修剪:删除指向已移除端点的用例(块级,def→next def)。"""
import io
import re

FILES = {
    "tests/test_api.py": [
        "test_mistake_full_lifecycle", "test_mistake_qtype_validation",
        "test_mistake_choice_question", "test_practice_session",
        "test_vocab_flow", "test_seed_not_overwritten"],
    "tests/test_api_v2.py": [
        "test_upload_and_fetch_image", "test_mistake_with_image_and_ai_fields",
        "test_ai_recognize_without_key_honest",
        "test_coach_chat_without_key_saves_honest_reply",
        "test_review_with_duration_and_hint"],
    "tests/test_v3.py": [
        "test_train_daily_generated_and_stable", "test_train_answer_and_auto_mistake",
        "test_train_finish_idempotent_records", "test_train_quota_settings",
        "test_train_shortage_honest", "test_questions_pagination"],
    "tests/test_learning_loop.py": [
        "test_recognition_normalizes_chinese_subject",
        "test_recognition_unknown_subject_left_blank",
        "test_recognize_prompt_includes_politics",
        "test_mistake_filters_error_reason_and_knowledge"],
    "tests/test_reliability.py": [
        "test_tools_whitelist", "test_stream_endpoint_requires_ai"],
    "tests/test_backend_fix.py": [
        "test_mistake_difficulty_validation"],
}

DEF = re.compile(r"^(def |class )")
for path, names in FILES.items():
    lines = io.open(path, encoding="utf-8").read().split("\n")
    spans = []
    for name in names:
        start = None
        for i, l in enumerate(lines):
            if l.startswith("def %s(" % name):
                start = i
                break
        if start is None:
            print("跳过(未找到): %s:%s" % (path, name))
            continue
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if DEF.match(lines[j]) and not lines[j].startswith("def _"):
                end = j
                break
        spans.append((start, end, name))
    for a, b, name in sorted(spans, reverse=True):
        while b < len(lines) and lines[b].strip() == "":
            b += 1
        del lines[a:b]
        print("删 %s::%s (%d 行)" % (path.split("/")[-1], name, b - a))
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
print("完成")
