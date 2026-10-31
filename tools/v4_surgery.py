# -*- coding: utf-8 -*-
"""第四轮手术:从 server.py 移除刷题/顾问/Ollama 端点块(按块边界动态定位)。"""
import io
import re

PATH = "app/server.py"
src = io.open(PATH, encoding="utf-8").read()
lines = src.split("\n")

DEC = re.compile(r"^    @app\.")
SEC = re.compile(r"^    # ----------")


def find_block(start_idx):
    """返回 [start, end) 行号区间:end=下一个装饰器/小节注释行。"""
    end = len(lines)
    for j in range(start_idx + 1, len(lines)):
        if DEC.match(lines[j]) or SEC.match(lines[j]):
            end = j
            break
    return start_idx, end


def find(pattern):
    for i, l in enumerate(lines):
        if pattern in l:
            return i
    return -1


# 收集要删的起始行(装饰器行)
starts = []
for pat in ('@app.get("/api/mistakes")',
            '@app.get("/api/practice/session")',
            '@app.get("/api/ai/status")',
            '@app.post("/api/coach/chat")',
            '@app.get("/api/questions")',
            '@app.post("/api/coach/chat/stream")',
            '@app.post("/api/tools/execute")'):
    i = find(pat)
    assert i >= 0, pat
    starts.append(i)

# images/AI 小节:从节注释行开始(含 upload/ai/status/ai/models/ai/recognize)
i = find("# ---------- images / AI ----------")
assert i >= 0
sec_end = find("@app.post(\"/api/reflections/extract\")")
starts.append(("sec", i, sec_end))

# 删除(从后往前)
spans = []
for s in starts:
    if isinstance(s, tuple):
        spans.append((s[1], s[2]))
    else:
        spans.append(find_block(s))
spans.sort(reverse=True)
removed = 0
for a, b in spans:
    # 吸收块后的连续空行
    while b < len(lines) and lines[b].strip() == "":
        b += 1
    del lines[a:b]
    removed += b - a
    print("删除 %d 行: %s ... %s" % (b - a, lines[a][:40] if a < len(lines) else "", (lines[a - 1] or "")[:40]))

io.open(PATH, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
print("共删除", removed, "行")
