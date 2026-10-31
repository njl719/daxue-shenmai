# -*- coding: utf-8 -*-
"""题库库函数测试(第四轮起题库 HTTP 端点移除,逻辑保留为导入工具):
结构校验/版权红线/AI 自动标注/哈希去重/导入明细/来源字段。"""
from app.questionbank import import_questions, new_question_record, question_hash, validate_question

BANK_Q = {"subject": "cs408", "source_type": "自录题", "qtype": "概念",
          "question_md": "TCP 建立连接需要几次报文交换?",
          "options": ["2 次", "3 次", "4 次"], "answer": "B",
          "solution_md": "三次握手:SYN → SYN+ACK → ACK",
          "source_desc": "王道计网 第5章 自录", "copyright_status": "自述/本人记录"}


def test_validate_and_hash():
    q, err = validate_question(dict(BANK_Q))
    assert err is None and q["content_hash"]
    assert q["copyright_status"] == "自述/本人记录"
    assert question_hash(q["question_md"], "cs408") == q["content_hash"]


def test_duplicate_hash_detected():
    q1, _ = validate_question(dict(BANK_Q))
    q2, _ = validate_question(dict(BANK_Q, options=BANK_Q["options"]))
    assert q1["content_hash"] == q2["content_hash"]


def test_real_exam_requires_copyright_status():
    q, err = validate_question({"subject": "math", "source_type": "真题",
                                "question_md": "求某极限", "copyright_status": "AI 原创"})
    assert q is None and "版权" in err
    q, err = validate_question({"subject": "math", "source_type": "真题",
                                "question_md": "求某极限", "year": 2024,
                                "copyright_status": "来源不明-待核验",
                                "source_desc": "网友回忆版"})
    assert err is None and q["year"] == 2024  # 真题只能以待核验身份入库


def test_ai_generated_auto_label():
    q, err = validate_question({"subject": "math", "source_type": "AI 生成练习题",
                                "question_md": "计算 lim(x→0) sin(3x)/x",
                                "answer": "3", "solution_md": "等价无穷小 sin(3x)~3x"})
    assert err is None
    assert q["ai_generated"] is True
    assert q["copyright_status"] == "AI 原创"


def test_choice_answer_validation():
    q, err = validate_question(dict(BANK_Q, answer="D"))
    assert q is None and "answer" in err
    q, err = validate_question(dict(BANK_Q, answer="b"))  # 小写归一
    assert err is None and q["answer"] == "B"


def test_import_with_report():
    items = [
        dict(BANK_Q),
        dict(BANK_Q, question_md="完全不同的一题", answer="A"),
        {"subject": "bad", "question_md": "x", "source_type": "自录题"},
        {"subject": "math", "source_type": "自录题", "question_md": ""},
    ]
    valid, r = import_questions(items)
    assert r["total"] == 4 and r["added"] == 2 and len(r["invalid"]) == 2
    valid2, r2 = import_questions(items)
    # 库函数去重仅限单次调用;跨调用去重由存储层 content_hash 负责
    assert r2["added"] == 2 and len(r2["duplicates"]) == 0
    # 统一来源字段(v7 标准)
    assert valid[0]["source_url"] == "" and valid[0]["verified_at"] is None


def test_new_question_record_fields():
    q, err = validate_question(dict(BANK_Q))
    assert err is None
    rec = new_question_record(q, 1)
    assert rec["id"] == "qb-0001" and rec["source_name"] == BANK_Q["source_desc"]
    assert rec["verified_at"] is None and rec["updated_at"] is None
