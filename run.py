# -*- coding: utf-8 -*-
"""个人考研复习平台入口。

用法:
    python run.py
自动打开浏览器访问 http://127.0.0.1:8321
"""
import os
import threading
import webbrowser

from app.server import main

if __name__ == "__main__":
    # 生产容器/无桌面环境跳过自动开浏览器
    if os.name == "nt" and not os.environ.get("DX_PORT") and not os.environ.get("PORT"):
        threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:8321")).start()
    main()
