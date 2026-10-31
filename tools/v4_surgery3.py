# -*- coding: utf-8 -*-
"""第四轮手术 v3:精确边界(以真实节注释为准)。"""
import io

PATH = "app/server.py"
lines = io.open(PATH, encoding="utf-8").read().split("\n")


def line_of(needle, start=0):
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i
    raise SystemExit("未找到: " + needle)


spans = [
    (line_of('def _due_filter'), line_of('def _due_filter') + 4),
    (line_of('@app.get("/api/mistakes")'), line_of("# ---------- records ----------")),
    (line_of('@app.get("/api/practice/session")'), line_of("# ---------- plan ----------")),
    (line_of("# ---------- images / AI ----------"), line_of("# ---------- reflections ----------")),
    (line_of("# ---------- coach ----------"), line_of("# ---------- profile & weekly report ----------")),
    (line_of('@app.get("/api/questions")'), line_of("# ---------- 经验帖 ----------")),
    (line_of('@app.post("/api/coach/chat/stream")'), line_of('@app.get("/api/data-quality")')),
]
spans = sorted([(a, b) for a, b in spans if b > a], reverse=True)
prev = None
for a, b in spans:
    if prev is not None and b > prev:
        raise SystemExit("区间异常: %d-%d 越过 %d" % (a, b, prev))
    while b < len(lines) and lines[b].strip() == "":
        b += 1
    print("删除 %d 行 [%d,%d): %s" % (b - a, a + 1, b, lines[a][:46]))
    del lines[a:b]
    prev = a

io.open(PATH, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
print("完成")
