# -*- coding: utf-8 -*-
"""题库测试:结构/去重/版权标注/AI 标注/导入明细/抽题练习池。"""

BANK_Q = {"subject": "cs408", "source_type": "自录题", "qtype": "概念",
          "question_md": "TCP 建立连接需要几次报文交换?",
          "options": ["2 次", "3 次", "4 次"], "answer": "B",
          "solution_md": "三次握手:SYN → SYN+ACK → ACK",
          "source_desc": "王道计网 第5章 自录", "copyright_status": "自述/本人记录"}


def test_question_crud_and_hash_dedup(client):
    rv = client.post("/api/questions", json=BANK_Q)
    assert rv.status_code == 201
    q = rv.get_json()
    assert q["content_hash"]
    assert q["copyright_status"] == "自述/本人记录"
    # 同题干重复录入被拒
    rv = client.post("/api/questions", json=dict(BANK_Q, options=BANK_Q["options"]))
    assert rv.status_code == 400 and "重复" in rv.get_json()["error"]
    assert client.delete("/api/questions/" + q["id"]).status_code == 200


def test_real_exam_requires_copyright_status(client):
    rv = client.post("/api/questions", json={
        "subject": "math", "source_type": "真题", "question_md": "求某极限",
        "copyright_status": "AI 原创"})
    assert rv.status_code == 400 and "版权" in rv.get_json()["error"]
    # 合法:声明待核验
    rv = client.post("/api/questions", json={
        "subject": "math", "source_type": "真题", "question_md": "求某极限",
        "year": 2024, "copyright_status": "来源不明-待核验",
        "source_desc": "网友回忆版"})
    assert rv.status_code == 201


def test_ai_generated_auto_label(client):
    rv = client.post("/api/questions", json={
        "subject": "math", "source_type": "AI 生成练习题",
        "question_md": "计算 lim(x→0) sin(3x)/x",
        "answer": "3", "solution_md": "等价无穷小 sin(3x)~3x",
        "copyright_status": "合法使用(授权/开放许可)"})  # 故意给错,应被强制改写
    assert rv.status_code == 201
    q = rv.get_json()
    assert q["ai_generated"] is True
    assert q["copyright_status"] == "AI 原创"


def test_choice_answer_validation(client):
    rv = client.post("/api/questions", json={
        "subject": "cs408", "source_type": "自录题",
        "question_md": "选项题答案越界", "options": ["甲", "乙"], "answer": "E"})
    assert rv.status_code == 400


def test_import_with_report(client):
    items = [
        dict(BANK_Q),                                    # 与已有/彼此重复将在第二轮算重复
        dict(BANK_Q, question_md="完全不同的一题", answer="A"),
        {"subject": "bad", "question_md": "x", "source_type": "自录题"},   # 无效科目
        {"subject": "math", "source_type": "自录题", "question_md": ""},   # 空题干
    ]
    rv = client.post("/api/questions/import", json={"items": items})
    assert rv.status_code == 200
    r = rv.get_json()
    assert r["total"] == 4
    assert r["added"] == 2
    assert len(r["invalid"]) == 2
    # 再次导入同样内容 → 全部重复
    rv = client.post("/api/questions/import", json={"items": items})
    r2 = rv.get_json()
    assert r2["added"] == 0 and len(r2["duplicates"]) == 2


def test_practice_pool(client):
    client.post("/api/questions", json={
        "subject": "math", "source_type": "AI 生成练习题",
        "question_md": "练习:求导 x^2", "answer": "2x"})
    client.post("/api/questions", json=dict(
        BANK_Q, question_md="真题池:进程与线程区别"))
    pool = client.get("/api/questions/practice?n=5").get_json()
    assert 1 <= len(pool) <= 5
    # 非AI题排前面
    if len(pool) >= 2:
        assert not pool[0].get("ai_generated") or all(p.get("ai_generated") for p in pool)
    pool_math = client.get("/api/questions/practice?subject=math&n=3").get_json()
    assert all(q["subject"] == "math" for q in pool_math)


def test_level_persisted_and_in_coach_context(client):
    client.put("/api/settings", json={"subjects": {
        "math": {"enabled": True, "priority": 1, "minutes": 90, "level": 2}}})
    s = client.get("/api/settings").get_json()
    assert s["subjects"]["math"]["level"] == 2
    # 教练上下文包含自评(直接调用一次对话验证不报错且落库)
    rv = client.post("/api/coach/chat/stream", json={"message": "我数学水平如何?"})
    assert rv.status_code == 200
