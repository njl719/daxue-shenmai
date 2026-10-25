# -*- coding: utf-8 -*-
"""app.js 粗检:剥离字符串/模板/注释后查括号配平。"""
import io
import re
import sys

src = io.open(sys.argv[1] if len(sys.argv) > 1 else 'app/static/app.js',
              encoding='utf-8').read()


def strip_code(s):
    out, i, n = [], 0, len(s)
    BS = chr(92)
    while i < n:
        c = s[i]
        if c == '`':
            i += 1
            while i < n and s[i] != '`':
                if s[i] == BS:
                    i += 1
                i += 1
            i += 1
            out.append(' ')
        elif c in ('"', "'"):
            q = c
            i += 1
            while i < n and s[i] != q:
                if s[i] == BS:
                    i += 1
                i += 1
            i += 1
            out.append(' ')
        elif c == '/' and i + 1 < n and s[i + 1] == '/':
            while i < n and s[i] != '\n':
                i += 1
        elif c == '/' and i + 1 < n and s[i + 1] == '*':
            i += 2
            while i + 1 < n and not (s[i] == '*' and s[i + 1] == '/'):
                i += 1
            i += 2
            out.append(' ')
        else:
            out.append(c)
            i += 1
    return ''.join(out)


code = strip_code(src)
ok = True
for o, cl in (('{', '}'), ('(', ')'), ('[', ']')):
    a, b = code.count(o), code.count(cl)
    flag = 'OK' if a == b else '!!! 不配平'
    if a != b:
        ok = False
    print("%s%s: %d/%d %s" % (o, cl, a, b, flag))
print("总行数: %d | 大小: %d B" % (src.count('\n') + 1, len(src)))
sys.exit(0 if ok else 1)
