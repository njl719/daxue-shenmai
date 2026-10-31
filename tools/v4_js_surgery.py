# -*- coding: utf-8 -*-
"""app.js 手术:删除刷题/错题/题库/生词/知识库操作/顾问/Ollama 相关块。"""
import io
import re

PATH = "app/static/app.js"
lines = io.open(PATH, encoding="utf-8").read().split("\n")
TOP = re.compile(r"^(async function |function |ROUTES\.[A-Za-z_]+ =|let |const )" )


def line_of(needle, start=0):
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i
    raise SystemExit("未找到: " + needle)


def top_end(start):
    for j in range(start + 1, len(lines)):
        if TOP.match(lines[j]):
            return j
    return len(lines)


spans = []
for start_marker, end_marker in [
    ("async function refreshDueBadge", "__AUTO__"),
    ("let studyTab", "ROUTES.coach"),
    ("ROUTES.coach", "let growthTab"),
    ("async function renderMotivation", "async function renderMilestones"),
    ("async function renderSearch", "async function renderSources"),
    ("async function renderExperience", "async function renderQuality"),
]:
    a = line_of(start_marker)
    b = line_of(end_marker) if end_marker != "__AUTO__" else top_end(a)
    spans.append((a, b))

spans = sorted(spans, reverse=True)
prev = None
for a, b in spans:
    if prev is not None and b > prev:
        raise SystemExit("区间异常 %d-%d 越过 %d" % (a, b, prev))
    while b < len(lines) and lines[b].strip() == "":
        b += 1
    print("删除 %d 行 [%d,%d): %s" % (b - a, a + 1, b, lines[a][:40]))
    del lines[a:b]
    prev = a

# navigate() 去掉 due 徽章调用
src = "\n".join(lines)
src = re.sub(r"\n  if \(view !== \"login\" && view !== \"setup\"\) refreshDueBadge\(\);", "", src)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
print("完成")
