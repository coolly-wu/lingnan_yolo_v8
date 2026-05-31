@echo off
REM 一键打包 Windows 安装包（PyInstaller + Inno Setup）
REM
REM 前置：
REM   1) pip install pyinstaller
REM   2) 如需 .exe 安装包：从 https://jrsoftware.org/isinfo.php 下载 Inno Setup 6
REM
REM 产物：
REM   dist/Lingnan/Lingnan.exe          （绿色版文件夹）
REM   dist/Lingnan_Setup_x64.exe        （Inno Setup 安装向导，若已装 Inno Setup）

setlocal
cd /d "%~dp0"

echo ============================================================
echo  1/3  清理上次产物
echo ============================================================
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo.
echo ============================================================
echo  2/4  准备真实模型权重（best.pt -^> yolov8s_xh_best.pt）
echo ============================================================
if exist "models\best.pt" (
    if not exist "models\yolov8s_xh_best.pt" (
        copy /y "models\best.pt" "models\yolov8s_xh_best.pt" >nul
        echo 已复制 best.pt 为候选标准名 yolov8s_xh_best.pt
    ) else (
        echo 已存在 models\yolov8s_xh_best.pt，跳过复制
    )
) else (
    echo [警告] 未找到 models\best.pt，将仅打包占位/已有模型
)

echo.
echo ============================================================
echo  3/4  PyInstaller 打包
echo ============================================================
if exist ".venv\Scripts\pyinstaller.exe" (
    ".venv\Scripts\pyinstaller.exe" build.spec
) else (
    pyinstaller build.spec
)
if errorlevel 1 (
    echo [ERR] PyInstaller 失败
    exit /b 1
)

echo.
echo ============================================================
echo  4/4  Inno Setup 制作安装包（若已安装）
echo ============================================================
where iscc >nul 2>nul
if errorlevel 1 (
    echo [跳过] 未检测到 Inno Setup 6 (iscc)，仅生成绿色版。
    echo        绿色版位置: dist\Lingnan\Lingnan.exe
) else (
    iscc installer.iss
    if errorlevel 1 (
        echo [ERR] Inno Setup 失败
        exit /b 1
    )
    echo 安装向导生成完毕: dist\Lingnan_Setup_x64.exe
)

echo.
echo ============================================================
echo  打包流程结束
echo ============================================================
pause
