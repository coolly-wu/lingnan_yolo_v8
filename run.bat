@echo off
REM 廉江红橙病虫害智能检测防治系统 - Windows 启动脚本
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else (
    python app.py
)
pause
