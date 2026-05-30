#!/usr/bin/env bash
# 廉江红橙病虫害智能检测防治系统 - Linux / macOS 启动脚本
cd "$(dirname "$0")"
if [ -x ".venv/bin/python" ]; then
    ".venv/bin/python" app.py
else
    python3 app.py
fi
