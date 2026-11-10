# -*- coding: utf-8 -*-
"""
錸億精密工業有限公司 (LAI YI Precision Industrial Co., Ltd.)
PyWebView Desktop Application Wrapper
Usage: python desktop_app.py
"""

import os
import time
import socket
import threading
import webview
from app import app


def _find_free_port(default_port: int = 5055) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", default_port)) != 0:
            return default_port
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    port = _find_free_port(5055)
    server_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True
    )
    server_thread.start()
    time.sleep(0.8)

    window = webview.create_window(
        title="錸億精密工業有限公司 (LAI YI Precision) — 企業形象官網暨智慧詢價管理平台",
        url=f"http://127.0.0.1:{port}",
        width=1440,
        height=920,
        min_size=(1024, 700),
        resizable=True,
        text_select=True
    )
    webview.start()


if __name__ == "__main__":
    main()

