# -*- coding: utf-8 -*-
"""把本地 8321 端口的大雪深埋发布到公网(Cloudflare 临时隧道,免账号)。
用法: python tools/publish.py
行为:
  1. 本地服务器没开就自动启动 (python run.py)
  2. 启动 cloudflared 隧道,解析出 https://xxx.trycloudflare.com
  3. 网址写入 tools/public_url.txt 并打印
  4. 保持运行; Ctrl+C 退出时会同时关闭隧道
注意: 临时隧道每次启动网址会变,以本脚本打印/写入的为准。
"""
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CF = os.path.join(ROOT, "tools", "cloudflared.exe")
URL_FILE = os.path.join(ROOT, "tools", "public_url.txt")
PORT = 8321


def log(msg):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(msg, flush=True)


def local_alive():
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:%d/api/health" % PORT, timeout=3
        ) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    if not os.path.exists(CF):
        log("[错误] 缺少 tools/cloudflared.exe,请先下载:")
        log(
            "  https://github.com/cloudflare/cloudflared/releases/latest/download/"
            "cloudflared-windows-amd64.exe"
        )
        sys.exit(1)

    server = None
    if local_alive():
        log("[1/3] 本地服务器已在运行 :%d" % PORT)
    else:
        log("[1/3] 本地服务器未运行,正在启动 python run.py ...")
        server = subprocess.Popen(
            [sys.executable, "run.py"], cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(40):
            if local_alive():
                break
            time.sleep(0.5)
        if not local_alive():
            log("[错误] 本地服务器启动失败,请手动排查 python run.py")
            if server:
                server.terminate()
            sys.exit(1)
        log("      本地服务器已就绪")

    log("[2/3] 正在建立 Cloudflare 隧道(约 5-15 秒)...")
    env = dict(os.environ)
    env.setdefault("HTTPS_PROXY", "http://127.0.0.1:7897")
    proc = subprocess.Popen(
        [CF, "tunnel", "--url", "http://127.0.0.1:%d" % PORT,
         "--no-autoupdate", "--protocol", "http2"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
    )

    url_holder = {}
    found = threading.Event()

    def reader():
        for line in io_text(proc.stdout):
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and not found.is_set():
                url_holder["url"] = m.group(0)
                found.set()

    def io_text(stream):
        import io
        return io.TextIOWrapper(stream, encoding="utf-8", errors="replace")

    threading.Thread(target=reader, daemon=True).start()

    if not found.wait(60):
        log("[错误] 60 秒内未拿到公网网址。可能原因: 代理未开(Clash)/网络阻断。")
        log("       请确认 Clash 在 127.0.0.1:7897 运行后重试。")
        proc.terminate()
        if server:
            server.terminate()
        sys.exit(1)

    url = url_holder["url"]
    with open(URL_FILE, "w", encoding="utf-8") as f:
        f.write(url + "\n")
    log("[3/3] 上线成功!")
    log("")
    log("========================================")
    log("  公网网址: " + url)
    log("  (已存到 tools/public_url.txt)")
    log("========================================")
    log("保持本窗口开着即在线;关掉窗口=下线。")
    log("再次启动会分配新网址,以窗口里打印的为准。")
    log("")
    try:
        proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        if server:
            server.terminate()
        log("已下线。")


if __name__ == "__main__":
    main()
