# -*- coding: utf-8 -*-
"""AI 题库生成器:本地 Ollama(qwen2.5)分主题生成练习题,结构校验+哈希去重后入库。

诚实标注:全部题目 source_type="AI 生成练习题"、copyright_status="AI 原创"、
source_desc 注明模型。禁止冒充真题。质量门槛:选项≥3、答案字母合法、解析非空、
选项互异、题干≥10字;哈希去重。
"""
import json
import random
import re
import sys
import time
import urllib.request

BASE = "http://localhost:11434/v1/chat/completions"
MODEL = "qwen2.5:7b-instruct-q4_K_M"

# 每科主题池(对应 catalog 章节名,强制多样性)
TOPICS = {
    "math": ["函数极限与连续", "导数与微分", "中值定理", "不定积分", "定积分与应用",
             "多元函数微分", "二重积分", "常数项级数", "幂级数", "行列式", "矩阵运算与逆",
             "向量组线性相关性", "线性方程组", "特征值与特征向量", "二次型",
             "随机事件与概率", "一维随机变量", "二维随机变量与独立性", "期望与方差",
             "大数定律与中心极限", "数理统计基本概念", "参数估计"],
    "cs408": ["时间复杂度分析", "线性表", "栈与队列", "串与KMP", "二叉树性质与遍历",
              "二叉排序树与平衡树", "堆", "哈夫曼树", "图存储与遍历", "最短路径",
              "最小生成树", "拓扑排序", "顺序查找与折半查找", "B树与散列表",
              "插入排序", "快速排序", "归并排序与堆排序", "基数排序与外部排序",
              "数据的机器表示与运算", "浮点数IEEE754", "存储层次与Cache",
              "指令系统与寻址", "CPU数据通路与流水线", "总线", "中断与I/O",
              "进程与线程", "进程同步与信号量", "死锁", "内存管理与页面置换",
              "文件系统", "I/O管理与磁盘调度", "网络体系结构", "物理层与数据链路层",
              "滑动窗口与可靠传输", "TCP与UDP", "IP与路由", "应用层协议"],
    "english": ["核心词汇辨析-动词", "核心词汇辨析-名词", "核心词汇辨析-形容词",
                "固定搭配与短语动词", "长难句主干分析", "定语从句", "状语从句",
                "非谓语动词", "倒装与强调", "虚拟语气", "阅读推理题", "阅读主旨题",
                "阅读细节题", "完形逻辑衔接", "翻译-被动语态", "翻译-定语从句处理"],
    "politics": ["唯物论基本概念", "辩证法-对立统一", "认识论-实践与认识",
                 "历史唯物主义", "毛泽东思想形成与发展", "新民主主义理论",
                 "社会主义改造理论", "近现代史纲要时间线", "思想道德与法治基本概念"],
}

PROMPT = """你是考研出题助手。围绕主题「%s」出 %d 道%s选择题(单项选择)。
要求:
1. 题干清晰完整,考察概念理解或简单计算,难度适中;
2. 每题恰好4个选项,只有一个正确答案,干扰项要有迷惑性但明确错误;
3. 附 1-2 句解析,说明正确答案依据;
4. 只输出 JSON 数组,不要输出任何其他文字:
[{"q":"题干","opts":["A选项","B选项","C选项","D选项"],"ans":"A","exp":"解析"}]
再次强调:主题必须紧扣「%s」,题与题之间不要重复考点。"""


def gen_batch(topic, n):
    payload = {"model": MODEL, "temperature": 0.7,
               "messages": [{"role": "user", "content": PROMPT % (topic, n, "", topic)}],
               "options": {"num_ctx": 4096, "temperature": 0.7}}
    req = urllib.request.Request(BASE, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        text = json.loads(r.read().decode())["choices"][0]["message"]["content"]
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return []


def main():
    sys.path.insert(0, ".")
    from app.storage import Store
    from app import questionbank as QB
    store = Store()
    plan = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {
        "math": 110, "cs408": 150, "english": 130, "politics": 70}
    total_added = {}
    for subject, target in plan.items():
        added = 0
        topics = TOPICS[subject] * 10
        random.shuffle(topics)
        existing = {q["content_hash"] for q in store.load("questions")}
        for topic in topics:
            if added >= target:
                break
            try:
                raw = gen_batch(topic, 6)
            except Exception as e:
                print("[%s] %s 批次失败:%s" % (subject, topic, str(e)[:60]), flush=True)
                time.sleep(2)
                continue
            for item in raw:
                if added >= target:
                    break
                if not isinstance(item, dict):
                    continue
                q = {
                    "subject": subject, "source_type": "AI 生成练习题",
                    "qtype": "概念" if subject in ("politics",) else "选择",
                    "question_md": str(item.get("q") or "").strip(),
                    "options": [str(o).strip() for o in (item.get("opts") or []) if str(o).strip()],
                    "answer": str(item.get("ans") or "").strip().upper()[:1],
                    "solution_md": str(item.get("exp") or "").strip(),
                    "source_desc": MODEL + " 本地生成(结构校验通过)",
                    "copyright_status": "AI 原创", "difficulty": random.choice([2, 2, 3, 3, 3, 4]),
                }
                # 质量门槛
                if len(q["question_md"]) < 10 or len(q["options"]) != 4:
                    continue
                if len(set(q["options"])) != 4:
                    continue
                if q["answer"] not in "ABCD" or len(q["solution_md"]) < 8:
                    continue
                v, err = QB.validate_question(q)
                if err or v["content_hash"] in existing:
                    continue
                existing.add(v["content_hash"])
                items = store.load("questions")
                items.append(QB.new_question_record(v, len(items) + 1))
                store.save("questions", items)
                added += 1
            print("[%s] %s → 累计 %d/%d" % (subject, topic, added, target), flush=True)
        total_added[subject] = added
    print("=== 生成完成:", json.dumps(total_added), flush=True)


if __name__ == "__main__":
    main()
