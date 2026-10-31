# -*- coding: utf-8 -*-
"""第四轮手术 v2:精确边界删除 server.py 中的刷题/顾问/Ollama 块。"""
import io

PATH = "app/server.py"
lines = io.open(PATH, encoding="utf-8").read().split("\n")


def line_of(needle, start=0):
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i
    raise SystemExit("未找到: " + needle)


# [start, end) 区间:end 为保留的边界行
spans = [
    # 错题本 + 生词(308..stats 前) — 含 _due_filter 定义(在其上方,单独删)
    (line_of('def _due_filter'), line_of('def _due_filter') + 4),
    (line_of('@app.get("/api/mistakes")'), line_of("# ---------- stats ----------")),
    # 练习会话(到 images/AI 节前)
    (line_of('@app.get("/api/practice/session")'), line_of("# ---------- images / AI ----------")),
    # images/AI 节(上传/取图/ai-status/ai-models/ai-recognize)
    (line_of("# ---------- images / AI ----------"), line_of("# ---------- reflections ----------")),
    # 顾问对话 + 历史(到成长时间线节前)
    (line_of('@app.post("/api/coach/chat")'), line_of("# ---------- 成长时间线 ----------")),
    # 题库 + 每日训练(到经验帖节前)
    (line_of('@app.get("/api/questions")'), line_of("# ---------- 经验帖 ----------")),
    # 流式顾问 + 工具执行(到 data-quality 前)
    (line_of('@app.post("/api/coach/chat/stream")'), line_of('@app.get("/api/data-quality")')),
]
spans = sorted([(a, b) for a, b in spans if b > a], reverse=True)
prev_end = None
for a, b in spans:
    if prev_end is not None and b > prev_end:
        raise SystemExit("区间重叠异常: %d-%d vs %d" % (a, b, prev_end))
    while b < len(lines) and lines[b].strip() == "":
        b += 1
    print("删除 %d 行 [%d,%d): %s" % (b - a, a + 1, b, lines[a][:50]))
    del lines[a:b]
    prev_end = a

io.open(PATH, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
print("完成")
